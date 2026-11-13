"""Daily spin and community-task transaction boundaries."""
import secrets
from datetime import datetime, timezone
from fractions import Fraction
import json
from .config import canonical, clean, digest, ident, integer,emoji_key,validate_emoji
from .durations import MAX_TASK_TIME

SPIN = ((2,3300),(3,2200),(4,1400),(5,900),(6,700),(8,500),(10,400),(15,300),(20,250),(100,50))
assert sum(w for _,w in SPIN)==10000
assert Fraction(sum(a*w for a,w in SPIN),10000)==5


def spin_reward(roll):
    integer(roll,0,9999)
    for amount,weight in SPIN:
        if roll<weight:return amount
        roll-=weight
    raise AssertionError("Invalid spin weights")


def cycle(task, at):
    anchor=task['created']//86400*86400
    return max(0,(int(at)-anchor)//task['period']) if task['period'] else 0


class Features:
    async def reaction_award(self,guild,user,name,actor,message,emoji,amount):
        guild,user,actor,message=map(ident,(guild,user,actor,message));integer(amount,1,1000)
        emoji=emoji_key(validate_emoji(emoji))
        if user==actor:raise ValueError('Another moderator must reward your message.')
        key=f'reaction:{guild}:{message}:{emoji}:{user}'
        def pay(c):
            self._live(c,guild)
            # Rule edits, a second moderator, and remove/re-add never top up a message.
            if c.execute('SELECT 1 FROM ledger WHERE key IN (?,?)',(key,f'quality:{guild}:reaction:{message}:{emoji}:{user}')).fetchone():return False
            legacy=c.execute("""SELECT 1 FROM task_messages m JOIN ledger l
                ON l.guild=? AND l.user=m.user AND l.source='task' AND l.kind='base' AND l.ref=m.task||':'||m.cycle
                JOIN jobs j ON j.guild=l.guild AND j.kind='reaction' AND j.state='done'
                AND json_extract(j.payload,'$.user_id')=l.actor
                AND json_extract(j.payload,'$.message_id')=m.message
                AND json_extract(j.payload,'$.emoji')=? AND json_extract(j.payload,'$.rule.kind')='base'
                WHERE m.message=? AND m.user=? LIMIT 1""",(guild,emoji,message,user)).fetchone()
            if legacy:return False
            return self._entry(c,guild,user,amount,0,amount,'reaction','award',str(message),'Reaction '+emoji,actor,key,name)
        return await self.run(pay)

    async def voice_capture(self,guild,channel,capture,actor,people,amount):
        guild,channel,capture,actor=map(ident,(guild,channel,capture,actor));integer(amount,1,1000)
        if not 1<=len(people)<=5000:raise ValueError('A voice snapshot requires 1–5000 human participants.')
        people={str(ident(u)):str(name)[:128] for u,name in people.items()}
        data=dict(guild=guild,channel=channel,id=capture,actor=actor,people=people,amount=amount,at=int(self.clock()),paid=False)
        key=f'voice_capture:{guild}:{capture}'
        def save(c):
            self._live(c,guild)
            c.execute('INSERT OR IGNORE INTO meta_flags VALUES(?,?)',(key,canonical(data)))
            return json.loads(c.execute('SELECT value FROM meta_flags WHERE key=?',(key,)).fetchone()[0])
        return await self.run(save)

    async def update_voice_capture(self,guild,capture,actor,expected,amount=None):
        key=f'voice_capture:{ident(guild)}:{ident(capture)}';actor=ident(actor)
        if amount is not None:integer(amount,1,1000)
        def save(c):
            self._live(c,guild)
            row=c.execute('SELECT value FROM meta_flags WHERE key=?',(key,)).fetchone()
            if not row:raise ValueError('Voice snapshot not found.')
            data=json.loads(row[0])
            if data['actor']!=actor:raise ValueError('Open your own voice snapshot.')
            if data['paid'] and amount is None:return 0
            if data['paid'] or digest(data)!=expected:raise ValueError('This snapshot changed or was already paid. Reopen it.')
            if amount is not None:data['amount']=amount
            else:
                for user,name in data['people'].items():
                    self._entry(c,guild,int(user),data['amount'],0,data['amount'],'voice','participation',f"{data['channel']}:{capture}",'Voice call participation',actor,f'voice:{guild}:{capture}:{user}',name)
                data['paid']=True
                self._audit(c,guild,actor,'voice_snapshot',f"{capture}: {len(data['people'])} participants, {data['amount']} RC each")
            c.execute('UPDATE meta_flags SET value=? WHERE key=?',(canonical(data),key))
            return data if amount is not None else len(data['people'])
        return await self.run(save)

    async def spin_today(self,guild,user):
        day=datetime.fromtimestamp(self.clock(),timezone.utc).date().isoformat()
        rows=await self.query("SELECT * FROM spin_claims WHERE guild=? AND user=? AND day=?",(ident(guild),ident(user),day))
        return rows[0] if rows else None

    async def spin(self,guild,user,name,request):
        guild,user=ident(guild),ident(user);request=str(ident(request))
        def claim(c):
            cfg=self._live(c,guild)
            if not cfg['spin_enabled']:raise ValueError("Daily spin is paused.")
            old=c.execute("SELECT s.* FROM spin_requests r JOIN spin_claims s USING(guild,user,day) WHERE r.guild=? AND r.user=? AND r.request=?",(guild,user,request)).fetchone()
            if old:return {**dict(old),'created':False}
            now=int(self.clock());day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
            old=c.execute("SELECT * FROM spin_claims WHERE guild=? AND user=? AND day=?",(guild,user,day)).fetchone()
            created=old is None
            if created:
                definition=canonical(SPIN)
                saved=c.execute("SELECT data FROM spin_tables WHERE version=1").fetchone()
                if saved and saved[0]!=definition:raise ValueError("Spin distribution was modified. Accounting review required.")
                c.execute("INSERT OR IGNORE INTO spin_tables VALUES(1,?)",(definition,))
                roll=secrets.randbelow(10000);amount=spin_reward(roll)
                if not self._entry(c,guild,user,amount,0,amount,'spin','daily',day,'Daily RC spin',0,f"spin:{guild}:{user}:{day}",name):
                    raise ValueError("Spin ledger exists without its claim. Accounting review required.")
                c.execute("INSERT INTO spin_claims VALUES(?,?,?,?,?,?,?)",(guild,user,day,amount,roll,1,now))
                old=c.execute("SELECT * FROM spin_claims WHERE guild=? AND user=? AND day=?",(guild,user,day)).fetchone()
            c.execute("INSERT INTO spin_requests VALUES(?,?,?,?)",(guild,user,request,day))
            return {**dict(old),'created':created}
        return await self.run(claim)

    async def create_task(self,guild,actor,title,body,reward,period,cooldown,ends=0):
        guild,actor=ident(guild),ident(actor)
        clean(title,100);clean(body,2000);integer(reward,1,1000);integer(cooldown,0,MAX_TASK_TIME)
        if period not in (0,86400,604800):raise ValueError("Period must be once, daily or weekly.")
        if ends and (type(ends) is not int or ends<=self.clock()):raise ValueError("Task deadline must be in the future.")
        def create(c):
            self._live(c,guild)
            return c.execute("INSERT INTO tasks(guild,title,body,reward,period,cooldown,created,ends,actor) VALUES(?,?,?,?,?,?,?,?,?)",
             (guild,title,body,reward,period,cooldown,int(self.clock()),ends,actor)).lastrowid
        return await self.run(create)

    async def bind_task(self,guild,task_id,thread):
        changed=await self.execute("UPDATE tasks SET thread=?,status='active' WHERE guild=? AND id=? AND status='creating'",(ident(thread),ident(guild),task_id))
        if not changed:raise ValueError("Task is already bound or unavailable.")

    async def task(self,guild,task_id):
        rows=await self.query("SELECT * FROM tasks WHERE guild=? AND id=?",(ident(guild),task_id))
        if not rows:raise ValueError("Task not found in this server.")
        return rows[0]

    async def task_for_thread(self,guild,thread):
        rows=await self.query("SELECT * FROM tasks WHERE guild=? AND thread=?",(ident(guild),ident(thread)))
        return rows[0] if rows else None

    async def edit_task(self,guild,task_id,changes,actor,expected):
        guild,actor=ident(guild),ident(actor)
        if not changes or set(changes)-{'title','body','reward','cooldown','ends'}:raise ValueError("Unsupported task edit.")
        changes=dict(changes)
        for k,limit in (('title',100),('body',2000)):
            if k in changes:changes[k]=clean(changes[k],limit)
        if 'reward' in changes:integer(changes['reward'],1,1000)
        if 'cooldown' in changes:integer(changes['cooldown'],0,MAX_TASK_TIME)
        if 'ends' in changes:
            integer(changes['ends'],0,253402300799)
            if changes['ends'] and changes['ends']<=self.clock():raise ValueError("Choose a future deadline, or none for no deadline.")
        def edit(c):
            row=c.execute("SELECT * FROM tasks WHERE guild=? AND id=?",(guild,task_id)).fetchone()
            if not row or digest(dict(row))!=expected:raise ValueError("This task changed. Reopen it before editing.")
            if row['status'] not in ('creating','active','closed'):raise ValueError("Recover this task's publication before editing it.")
            if row['status']=='closed' and set(changes)&{'reward','cooldown','ends'}:raise ValueError('Closed task timing and reward are fixed. Duplicate this task for a new activity.')
            if 'reward' in changes and changes['reward']!=row['reward']:
                started=c.execute("SELECT 1 FROM task_messages WHERE task=? LIMIT 1",(task_id,)).fetchone()
                paid=c.execute("SELECT 1 FROM ledger WHERE guild=? AND source='task' AND ref LIKE ? LIMIT 1",(guild,f"{task_id}:%")).fetchone()
                if started or paid:raise ValueError("Base reward is fixed after participation starts. Duplicate this task to use a new reward.")
            fields=','.join(k+'=?' for k in changes)
            c.execute(f"UPDATE tasks SET {fields} WHERE guild=? AND id=?",(*changes.values(),guild,task_id))
            self._enqueue(c,f"tasksync:{task_id}",'task_sync',guild,{'task':task_id})
            self._audit(c,guild,actor,'task_edited',f"{task_id}: "+', '.join(changes))
        await self.run(edit)

    async def close_task(self,guild,task_id,actor):
        guild,actor=ident(guild),ident(actor)
        def close(c):
            row=c.execute("SELECT * FROM tasks WHERE guild=? AND id=?",(guild,task_id)).fetchone()
            if not row:raise ValueError("Task not found.")
            c.execute("UPDATE tasks SET status='closed',ends=CASE WHEN ends=0 OR ends>? THEN ? ELSE ends END WHERE id=?",(int(self.clock()),int(self.clock()),task_id))
            self._enqueue(c,f"taskclose:{task_id}",'taskclose',guild,{'task':task_id})
            self._audit(c,guild,actor,'task_closed',str(task_id))
        await self.run(close)

    async def accept_message(self,guild,task_id,user,message,at,bypass=False):
        guild,user,message=ident(guild),ident(user),ident(message)
        def accept(c):
            row=c.execute("SELECT * FROM tasks WHERE guild=? AND id=?",(guild,task_id)).fetchone()
            if not row or row['status']!='active' or (row['ends'] and at>row['ends']):return -1
            if c.execute("SELECT 1 FROM task_messages WHERE message=?",(message,)).fetchone():return 0
            old=c.execute("SELECT at FROM cooldowns WHERE task=? AND user=?",(task_id,user)).fetchone()
            if old and not bypass and at-old[0]<row['cooldown']:return max(1,int(row['cooldown']-(at-old[0])))
            c.execute("INSERT INTO task_messages VALUES(?,?,?,?,?)",(message,task_id,user,cycle(row,at),at))
            if not bypass:c.execute("INSERT INTO cooldowns VALUES(?,?,?) ON CONFLICT(task,user) DO UPDATE SET at=excluded.at",(task_id,user,at))
            return 0
        return await self.run(accept)

    async def task_award(self,guild,task_id,participants,cycle_id,actor,operation,kind='base',amount=None):
        guild,actor=ident(guild),ident(actor)
        if kind not in ('base','quality'):raise ValueError("Select base or quality reward.")
        ids={ident(u):str(n) for u,n in participants.items()}
        if not 1<=len(ids)<=5000:raise ValueError("Select 1..5000 recipients.")
        def award(c):
            self._live(c,guild)
            task=c.execute("SELECT * FROM tasks WHERE guild=? AND id=?",(guild,task_id)).fetchone()
            if not task:raise ValueError("Task not found.")
            integer(cycle_id,0,1_000_000)
            maximum=cycle(task,min(int(self.clock()),task['ends'] or int(self.clock())))
            if cycle_id>maximum:raise ValueError("This task cycle has not started.")
            reward=task['reward'] if kind=='base' else integer(amount,1,1000)
            ref=f"{task_id}:{cycle_id}"
            count=0
            for uid,name in ids.items():
                key=f"task:{guild}:{ref}:{uid}:base" if kind=='base' else f"quality:{guild}:{operation}:{uid}"
                old=c.execute("SELECT guild,user,source,kind,ref FROM ledger WHERE key=?",(key,)).fetchone()
                if old:
                    if tuple(old)!=(guild,uid,'task',kind,ref):raise ValueError("Task reward operation identity conflict.")
                    continue
                count+=self._entry(c,guild,uid,reward,0,reward,'task',kind,ref,f"Task #{task_id} {kind} reward",actor,key,name)
            self._audit(c,guild,actor,'task_reward',f"{ref}; {kind}; {count} members")
            return count
        return await self.run(award)
