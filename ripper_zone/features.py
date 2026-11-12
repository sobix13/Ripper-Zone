"""Daily spin and community-task transaction boundaries."""
import secrets
from datetime import datetime, timezone
from fractions import Fraction
from .config import canonical, clean, ident, integer

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
        clean(title,100);clean(body,2000);integer(reward,1,1000);integer(cooldown,0,604800)
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
                count+=self._entry(c,guild,uid,reward,0,reward,'task',kind,ref,f"Task #{task_id} {kind} reward",actor,key,name)
            self._audit(c,guild,actor,'task_reward',f"{ref}; {kind}; {count} members")
            return count
        return await self.run(award)
