"""Private SQLite ledger. A transaction owns its connection until commit/rollback."""
import asyncio
import json
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from .config import canonical, clean, digest, ident, integer, settings, LEGACY_KEYS
from .features import Features
from .raffles import Raffles

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS meta_flags(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(guild INTEGER PRIMARY KEY,data TEXT NOT NULL,revision INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS settings_history(id INTEGER PRIMARY KEY,guild INTEGER,actor INTEGER,data TEXT,at INTEGER);
CREATE TABLE IF NOT EXISTS accounts(guild INTEGER,user INTEGER,name TEXT NOT NULL DEFAULT '',available INTEGER NOT NULL DEFAULT 0,
 reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved>=0),earned INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(guild,user));
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,guild INTEGER NOT NULL,user INTEGER NOT NULL,
 da INTEGER NOT NULL,dr INTEGER NOT NULL,de INTEGER NOT NULL,source TEXT NOT NULL,kind TEXT NOT NULL,
 ref TEXT NOT NULL,reason TEXT NOT NULL,actor INTEGER NOT NULL,key TEXT NOT NULL UNIQUE,at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS ledger_member ON ledger(guild,user,at);
CREATE TABLE IF NOT EXISTS financial_blocks(guild INTEGER PRIMARY KEY,reason TEXT NOT NULL,at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS revocations(ledger INTEGER PRIMARY KEY,guild INTEGER,actor INTEGER,reason TEXT,at INTEGER);
CREATE TABLE IF NOT EXISTS spin_claims(guild INTEGER,user INTEGER,day TEXT,amount INTEGER,roll INTEGER,version INTEGER,at INTEGER,
 PRIMARY KEY(guild,user,day));
CREATE TABLE IF NOT EXISTS spin_requests(guild INTEGER,user INTEGER,request TEXT,day TEXT,PRIMARY KEY(guild,user,request));
CREATE TABLE IF NOT EXISTS spin_tables(version INTEGER PRIMARY KEY,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(guild INTEGER,source TEXT,event TEXT,hash TEXT,amount INTEGER,actor INTEGER,at INTEGER,
 PRIMARY KEY(guild,source,event));
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,guild INTEGER NOT NULL,title TEXT,body TEXT,reward INTEGER,
 period INTEGER,cooldown INTEGER,created INTEGER,ends INTEGER,thread INTEGER UNIQUE,status TEXT NOT NULL DEFAULT 'creating',actor INTEGER);
CREATE TABLE IF NOT EXISTS task_messages(message INTEGER PRIMARY KEY,task INTEGER,user INTEGER,cycle INTEGER,at INTEGER);
CREATE TABLE IF NOT EXISTS cooldowns(task INTEGER,user INTEGER,at INTEGER,PRIMARY KEY(task,user));
CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY,kind TEXT,guild INTEGER,payload TEXT,state TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0,next_at INTEGER NOT NULL DEFAULT 0,token TEXT,lease_until INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(state,next_at);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,guild INTEGER,actor INTEGER,area TEXT,detail TEXT,at INTEGER);
CREATE TABLE IF NOT EXISTS owned_roles(guild INTEGER,role INTEGER,PRIMARY KEY(guild,role));
CREATE TABLE IF NOT EXISTS raffles(id INTEGER PRIMARY KEY,guild INTEGER NOT NULL,actor INTEGER,channel INTEGER,
 message INTEGER,status TEXT NOT NULL,spec TEXT NOT NULL,contract TEXT,hash TEXT,seed TEXT,commitment TEXT,
 frozen TEXT NOT NULL DEFAULT '[]',checks TEXT NOT NULL DEFAULT '[]',rounds TEXT NOT NULL DEFAULT '[]',
 announcement INTEGER,announcement_state TEXT NOT NULL DEFAULT 'pending',error TEXT NOT NULL DEFAULT '',created INTEGER);
CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,raffle INTEGER,guild INTEGER,user INTEGER,quantity INTEGER,cost INTEGER,
 request TEXT UNIQUE,state TEXT NOT NULL DEFAULT 'reserved',at INTEGER);
CREATE TABLE IF NOT EXISTS prizes(raffle INTEGER,user INTEGER,round INTEGER,state TEXT NOT NULL DEFAULT 'pending',note TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(raffle,user));
"""


class Conflict(ValueError):
    pass


class Database(Features, Raffles):
    def __init__(self, path, clock=time.time):
        self.path = str(path)
        self.clock = clock
        self.lock = asyncio.Lock()

    def _run(self, fn):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = fn(conn)
            conn.commit()
            return result
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def run(self, fn):
        async with self.lock:
            task = asyncio.create_task(asyncio.to_thread(self._run, fn))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise

    async def open(self):
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        def initialize():
            conn = sqlite3.connect(self.path, timeout=15)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone()
                if exists:
                    row = conn.execute("SELECT version FROM meta").fetchone()
                    if row and row[0] != 1:
                        raise ValueError("Unsupported database version. Do not downgrade this database.")
                conn.executescript("BEGIN IMMEDIATE;" + SCHEMA + "COMMIT;")
                if not conn.execute("SELECT 1 FROM meta").fetchone():
                    conn.execute("INSERT INTO meta VALUES(1)")
                conn.commit()
            finally:
                conn.close()
            path.chmod(0o600)
        await asyncio.to_thread(initialize)

    async def query(self, sql, args=()):
        return await self.run(lambda c: [dict(r) for r in c.execute(sql, args)])

    async def execute(self, sql, args=()):
        return await self.run(lambda c: c.execute(sql, args).rowcount)

    @staticmethod
    def _config(c, guild):
        row = c.execute("SELECT data,revision FROM settings WHERE guild=?", (guild,)).fetchone()
        data=json.loads(row[0]) if row else {}
        extra=c.execute('SELECT value FROM meta_flags WHERE key=?',(f'settings_extra:{guild}',)).fetchone()
        if extra:data.update(json.loads(extra[0]))
        return settings(data),row[1] if row else 0

    @staticmethod
    def _put_config(c,guild,data,revision):
        # Keep the v1 settings row readable by the previous release during rollback.
        legacy={k:v for k,v in data.items() if k in LEGACY_KEYS}
        extra={k:v for k,v in data.items() if k not in LEGACY_KEYS}
        c.execute('INSERT INTO settings VALUES(?,?,?) ON CONFLICT(guild) DO UPDATE SET data=excluded.data,revision=excluded.revision',(guild,canonical(legacy),revision))
        c.execute('INSERT OR REPLACE INTO meta_flags VALUES(?,?)',(f'settings_extra:{guild}',canonical(extra)))

    async def config(self, guild):
        return await self.run(lambda c: self._config(c, ident(guild)))

    def _save_history(self,c,guild,actor,data):
        legacy={k:v for k,v in data.items() if k in LEGACY_KEYS}
        extra={k:v for k,v in data.items() if k not in LEGACY_KEYS}
        hid=c.execute('INSERT INTO settings_history(guild,actor,data,at) VALUES(?,?,?,?)',(guild,actor,canonical(legacy),int(self.clock()))).lastrowid
        c.execute('INSERT INTO meta_flags VALUES(?,?)',(f'settings_history_extra:{hid}',canonical(extra)))
        stale=[r[0] for r in c.execute('SELECT id FROM settings_history WHERE guild=? ORDER BY id DESC LIMIT -1 OFFSET 30',(guild,))]
        for old in stale:
            c.execute('DELETE FROM settings_history WHERE id=?',(old,))
            c.execute('DELETE FROM meta_flags WHERE key=?',(f'settings_history_extra:{old}',))

    async def config_history(self,guild):
        def read(c):
            rows=[dict(r) for r in c.execute('SELECT * FROM settings_history WHERE guild=? ORDER BY id DESC LIMIT 30',(guild,))]
            for row in rows:
                extra=c.execute('SELECT value FROM meta_flags WHERE key=?',(f'settings_history_extra:{row["id"]}',)).fetchone()
                if extra:row['data']=canonical({**json.loads(row['data']),**json.loads(extra[0])})
            return rows
        return await self.run(read)

    async def save_config(self, guild, data, expected, actor):
        guild = ident(guild)
        actor = 0 if type(actor) is int and actor == 0 else ident(actor)
        data = settings(data)
        def save(c):
            old, revision = self._config(c, guild)
            if expected != revision:
                raise Conflict("Settings changed. Reopen the setup page.")
            self._save_history(c,guild,actor,old)
            self._put_config(c,guild,data,revision+1)
            for tier in data["tiers"]:
                c.execute("INSERT OR IGNORE INTO owned_roles VALUES(?,?)", (guild, tier["role"]))
            if any(old[k]!=data[k] for k in ('tiers','roles_enabled','member_role','manager_roles','spin_role')):
                for row in c.execute("SELECT user FROM accounts WHERE guild=?", (guild,)):
                    self._enqueue(c, f"role:{guild}:{row[0]}", "role", guild, {"user":row[0]})
            if any(old[k]!=data[k] for k in ('panel_title','welcome_text')):
                self._enqueue(c,f"panel:{guild}",'panel_refresh',guild,{})
            if old['messages']!=data['messages']:
                self._enqueue(c,f'leaderboard:{guild}','leaderboard_refresh',guild,{})
                for row in c.execute('SELECT id FROM raffles WHERE guild=? AND message IS NOT NULL',(guild,)):
                    self._enqueue(c,f'raffle-copy:{row[0]}','raffle_refresh',guild,{'raffle':row[0]})
            if old['task_footer']!=data['task_footer'] or old['messages']['task_closed']!=data['messages']['task_closed']:
                for row in c.execute("SELECT id FROM tasks WHERE guild=? AND thread IS NOT NULL",(guild,)):
                    self._enqueue(c,f'tasksync:{row[0]}','task_sync',guild,{'task':row[0]})
            self._audit(c,guild,actor,"settings",f"revision {revision+1}")
            return revision+1
        return await self.run(save)

    def _audit(self, c, guild, actor, area, detail):
        c.execute("INSERT INTO audit(guild,actor,area,detail,at) VALUES(?,?,?,?,?)", (guild,actor,area,str(detail)[:1000],int(self.clock())))
        c.execute("DELETE FROM audit WHERE id < (SELECT COALESCE(MAX(id),0)-10000 FROM audit)")

    async def audit(self,guild,actor,area,detail):
        await self.run(lambda c:self._audit(c,guild,actor,area,detail))

    def _enqueue(self,c,key,kind,guild,payload):
        c.execute("""INSERT INTO jobs(key,kind,guild,payload) VALUES(?,?,?,?)
         ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,state='pending',next_at=0,attempts=0,token=NULL,lease_until=0,error=''""",
         (key,kind,guild,canonical(payload)))

    async def enqueue(self,key,kind,guild,payload):
        await self.run(lambda c:self._enqueue(c,key,kind,guild,payload))

    async def claim_job(self):
        def claim(c):
            now=int(self.clock())
            row=c.execute("SELECT * FROM jobs WHERE (state='pending' AND next_at<=?) OR (state='running' AND lease_until<?) ORDER BY next_at LIMIT 1",(now,now)).fetchone()
            if not row:return None
            token=secrets.token_hex(16)
            c.execute("UPDATE jobs SET state='running',token=?,lease_until=? WHERE key=?",(token,now+180,row['key']))
            return {**dict(row),"token":token,"payload":json.loads(row['payload'])}
        return await self.run(claim)

    async def finish_job(self,job,error=None):
        attempts=job['attempts']+1
        await self.execute("UPDATE jobs SET state=?,attempts=?,next_at=?,token=NULL,lease_until=0,error=? WHERE key=? AND token=?",
         ('done' if not error else 'failed' if attempts>=8 else 'pending',attempts,int(self.clock())+min(900,10*2**min(attempts,6)),str(error or '')[:500],job['key'],job['token']))

    def _live(self,c,guild):
        cfg,_=self._config(c,guild)
        if not cfg['active']:raise ValueError("Ripper Zone is paused. An administrator must finish setup and activate it.")
        if c.execute("SELECT 1 FROM financial_blocks WHERE guild=?",(guild,)).fetchone():
            raise ValueError("RC accounting is paused for administrator review.")
        return cfg

    def _entry(self,c,guild,user,da,dr,de,source,kind,ref,reason,actor,key,name=''):
        old=c.execute("SELECT * FROM ledger WHERE key=?",(key,)).fetchone()
        identity=(guild,user,da,dr,de,source,kind,ref)
        if old:
            if tuple(old[x] for x in ('guild','user','da','dr','de','source','kind','ref'))!=identity:
                raise Conflict("A previous operation has different accounting data.")
            return False
        c.execute("INSERT OR IGNORE INTO accounts(guild,user,name) VALUES(?,?,?)",(guild,user,name[:128]))
        c.execute("INSERT INTO ledger(guild,user,da,dr,de,source,kind,ref,reason,actor,key,at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
          (*identity[:5],source,kind,ref,reason[:500],actor,key,int(self.clock())))
        c.execute("UPDATE accounts SET available=available+?,reserved=reserved+?,earned=earned+?,name=CASE WHEN ?!='' THEN ? ELSE name END WHERE guild=? AND user=?",
          (da,dr,de,name[:128],name[:128],guild,user))
        self._enqueue(c,f"role:{guild}:{user}","role",guild,{"user":user})
        cfg,_=self._config(c,guild)
        if cfg['log_channel']:
            text=f"<@{user}> received {da} RC." if da>0 and da==de and dr==0 else f"RC record {key}: <@{user}> | available {da:+}, reserved {dr:+}, earned {de:+}. {reason[:300]}"
            self._enqueue(c,'notice:'+key,'notice',guild,{'channel':cfg['log_channel'],'text':text})
        return True

    async def account(self,guild,user,name=''):
        guild,user=ident(guild),ident(user)
        def get(c):
            c.execute("INSERT OR IGNORE INTO accounts(guild,user,name) VALUES(?,?,?)",(guild,user,name[:128]))
            row=dict(c.execute("SELECT * FROM accounts WHERE guild=? AND user=?",(guild,user)).fetchone())
            row['rank']=1+c.execute("SELECT COUNT(*) FROM accounts WHERE guild=? AND earned>?",(guild,row['earned'])).fetchone()[0] if row['earned']>0 else None
            row['tasks']=c.execute("SELECT COUNT(DISTINCT ref) FROM ledger WHERE guild=? AND user=? AND source='task' AND kind='base' AND de>0 AND NOT EXISTS(SELECT 1 FROM revocations r WHERE r.ledger=ledger.id)",(guild,user)).fetchone()[0]
            row['events']=c.execute("SELECT COUNT(DISTINCT source||':'||ref) FROM ledger WHERE guild=? AND user=? AND source IN ('rumble','raffle') AND de>0 AND NOT EXISTS(SELECT 1 FROM revocations r WHERE r.ledger=ledger.id)",(guild,user)).fetchone()[0]
            return row
        return await self.run(get)

    async def award(self,guild,users,amount,actor,reason,operation,source='manual',kind='award',ref=None):
        guild,actor=ident(guild),ident(actor);integer(amount,1,1000);clean(reason,500)
        if not 1<=len(users)<=5000:raise ValueError("Select 1..5000 recipients.")
        users={ident(uid):str(name)[:128] for uid,name in users.items()}
        def pay(c):
            self._live(c,guild)
            count=0
            for user,name in users.items():
                key=f"{source}:{guild}:{ref or operation}:{user}:{kind}"
                count+=self._entry(c,guild,user,amount,0,amount,source,kind,str(ref or operation),reason,actor,key,name)
            self._audit(c,guild,actor,'award',f"{operation}; {count} recipients; {amount} RC each")
            return count
        return await self.run(pay)

    async def adjust(self,guild,user,amount,actor,reason,operation):
        guild,user,actor=ident(guild),ident(user),ident(actor)
        integer(amount,-100000,100000);clean(reason,500)
        if not amount:raise ValueError("Adjustment cannot be zero.")
        return await self.run(lambda c:self._entry(c,guild,user,amount,0,amount,'adjustment','correction',str(operation),reason,actor,f"adjust:{guild}:{operation}"))

    async def snapshot(self,guild,source,event,participants,amount,actor):
        if source not in ('rumble','raffle'):raise ValueError("Select rumble or raffle.")
        guild,actor=ident(guild),ident(actor);integer(amount,1,1000)
        ids=sorted(set(ident(x) for x in participants))
        if not ids or len(ids)>5000:raise ValueError("Snapshot requires 1..5000 participants.")
        event=clean(str(event),100);hash_=digest(ids)
        def pay(c):
            self._live(c,guild)
            old=c.execute("SELECT hash,amount FROM snapshots WHERE guild=? AND source=? AND event=?",(guild,source,event)).fetchone()
            if old:
                if old[0]!=hash_ or old[1]!=amount:raise Conflict("This event was already paid with different recipients or amount.")
                return 0
            for user in ids:
                self._entry(c,guild,user,amount,0,amount,source,'participation',event,f"{source.title()} participation #{event}",actor,f"{source}:{guild}:{event}:{user}:participation")
            c.execute("INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)",(guild,source,event,hash_,amount,actor,int(self.clock())))
            self._audit(c,guild,actor,'snapshot',f"{source}:{event}; {len(ids)} members; {amount} RC")
            return len(ids)
        return await self.run(pay)

    async def revoke(self,guild,ledger_id,actor,reason):
        guild,actor=ident(guild),ident(actor);clean(reason,500)
        def undo(c):
            old=c.execute("SELECT * FROM ledger WHERE guild=? AND id=?",(guild,ledger_id)).fetchone()
            if not old or old['de']<=0 or old['da']!=old['de'] or old['dr']!=0 or old['source'] not in ('task','manual','spin','rumble','raffle'):
                raise ValueError("Select an original positive contribution reward, not a purchase, refund or correction.")
            if c.execute("SELECT 1 FROM revocations WHERE ledger=?",(ledger_id,)).fetchone():return False
            self._entry(c,guild,old['user'],-old['da'],0,-old['de'],'adjustment','revocation',str(ledger_id),reason,actor,f"revoke:{guild}:{ledger_id}")
            c.execute("INSERT INTO revocations VALUES(?,?,?,?,?)",(ledger_id,guild,actor,reason,int(self.clock())))
            self._audit(c,guild,actor,'reward_revoked',f"{ledger_id}: {reason}")
            return True
        return await self.run(undo)

    async def history(self,guild,user,offset=0):
        return await self.query("SELECT * FROM ledger WHERE guild=? AND user=? ORDER BY id DESC LIMIT 10 OFFSET ?",(ident(guild),ident(user),max(0,offset)))

    async def leaderboard(self,guild,user=0,since=0,offset=0):
        guild=ident(guild);integer(offset,0,1000000)
        def read(c):
            if since:
                sql="SELECT a.user,a.name,SUM(l.de) earned FROM ledger l JOIN accounts a USING(guild,user) WHERE l.guild=? AND l.at>=? GROUP BY a.user HAVING SUM(l.de)>0"
                args=(guild,since)
            else:
                sql="SELECT user,name,earned FROM accounts WHERE guild=? AND earned>0";args=(guild,)
            ranked=f"WITH scores AS ({sql}), ranked AS (SELECT *,RANK() OVER(ORDER BY earned DESC) rank,ROW_NUMBER() OVER(ORDER BY earned DESC,user) position FROM scores) "
            rows=[dict(r) for r in c.execute(ranked+"SELECT * FROM ranked ORDER BY position LIMIT 10 OFFSET ?",(*args,offset))]
            mine=c.execute(ranked+"SELECT * FROM ranked WHERE user=?",(*args,user)).fetchone()
            total=c.execute(f"SELECT COUNT(*) FROM ({sql})",args).fetchone()[0]
            return {'rows':rows,'mine':dict(mine) if mine else None,'total':total}
        return await self.run(read)

    async def leaders(self,guild,since=0):
        return (await self.leaderboard(guild,since=since))['rows']

    async def reconcile(self,guild):
        def check(c):
            bad=c.execute("""SELECT a.user FROM accounts a LEFT JOIN
              (SELECT user,SUM(da) da,SUM(dr) dr,SUM(de) de FROM ledger WHERE guild=? GROUP BY user) l ON l.user=a.user
              WHERE a.guild=? AND (a.available!=COALESCE(l.da,0) OR a.reserved!=COALESCE(l.dr,0) OR a.earned!=COALESCE(l.de,0))""",(guild,guild)).fetchall()
            holds=c.execute("""SELECT a.user FROM accounts a WHERE a.guild=? AND a.reserved!=
              COALESCE((SELECT SUM(p.cost) FROM purchases p WHERE p.guild=a.guild AND p.user=a.user AND p.state='reserved'),0)""",(guild,)).fetchall()
            missing=c.execute("SELECT user FROM spin_claims s WHERE guild=? AND NOT EXISTS(SELECT 1 FROM ledger l WHERE l.key='spin:'||s.guild||':'||s.user||':'||s.day)",(guild,)).fetchall()
            invalid=c.execute("""SELECT s.user FROM spin_claims s JOIN ledger l ON l.key='spin:'||s.guild||':'||s.user||':'||s.day
              WHERE s.guild=? AND (l.da!=s.amount OR l.dr!=0 OR l.de!=s.amount OR l.source!='spin' OR l.guild!=s.guild OR l.user!=s.user)""",(guild,)).fetchall()
            orphan=c.execute("""SELECT l.user FROM ledger l WHERE l.guild=? AND l.source='spin' AND NOT EXISTS
              (SELECT 1 FROM spin_claims s WHERE l.key='spin:'||s.guild||':'||s.user||':'||s.day)""",(guild,)).fetchall()
            no_account=c.execute("SELECT user FROM ledger l WHERE guild=? AND NOT EXISTS(SELECT 1 FROM accounts a WHERE a.guild=l.guild AND a.user=l.user)",(guild,)).fetchall()
            errors=sorted(set(r[0] for r in [*bad,*holds,*missing,*invalid,*orphan,*no_account]))
            if errors:c.execute("INSERT INTO financial_blocks VALUES(?,?,?) ON CONFLICT(guild) DO UPDATE SET reason=excluded.reason,at=excluded.at",(guild,'Ledger/claim/reservation mismatch: '+str(errors[:20]),int(self.clock())))
            return errors
        return await self.run(check)

    async def clear_financial_block(self,guild,actor):
        if await self.reconcile(guild):raise ValueError("Accounting still differs. Restore/reconcile verified records before resuming.")
        await self.execute("DELETE FROM financial_blocks WHERE guild=?",(guild,))
        await self.audit(guild,actor,'accounting','Verified consistency; resumed')

    async def backup(self,target):
        target=Path(target);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        def copy():
            src=sqlite3.connect(Path(self.path).resolve().as_uri()+'?mode=ro',uri=True)
            dest=sqlite3.connect(str(target)+'.tmp')
            try:
                src.backup(dest)
                if dest.execute("PRAGMA quick_check").fetchone()[0]!='ok':raise ValueError("Backup integrity check failed.")
            finally:src.close();dest.close()
            tmp=Path(str(target)+'.tmp');tmp.chmod(0o600);tmp.replace(target)
        await asyncio.to_thread(copy)
