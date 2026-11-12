"""Ticket registration, reservation, settlement and refund are ledger transactions."""
import json
import secrets
from .config import canonical, clean, digest, ident, integer, raffle_spec
from . import drawing


def decode(row):
    if not row:raise ValueError("Raffle not found in this server.")
    row=dict(row)
    for k in ('spec','contract','frozen','checks','rounds'):
        row[k]=json.loads(row[k]) if row[k] else None
    return row


class Raffles:
    async def raffle(self,guild,rid):
        def read(c):
            r=decode(c.execute('SELECT * FROM raffles WHERE guild=? AND id=?',(ident(guild),rid)).fetchone())
            r['prizes']=[dict(p) for p in c.execute('SELECT * FROM prizes WHERE raffle=? ORDER BY round,user',(rid,))]
            return r
        return await self.run(read)

    async def create_raffle(self,guild,actor,spec):
        guild,actor=ident(guild),ident(actor);spec=raffle_spec(spec)
        if spec['ends']<=self.clock()+30:raise ValueError("Allow at least 30 seconds before closing.")
        def create(c):
            self._live(c,guild)
            if c.execute("SELECT COUNT(*) FROM raffles WHERE guild=? AND status IN ('draft','publishing','open','closing')",(guild,)).fetchone()[0]>=10:
                raise ValueError("At most ten unfinished RC raffles are allowed. Close or cancel existing drafts first.")
            rid=c.execute("INSERT INTO raffles(guild,actor,status,spec,created) VALUES(?,?,'draft',?,?)",(guild,actor,canonical(spec),int(self.clock()))).lastrowid
            self._audit(c,guild,actor,'raffle_created',str(rid));return rid
        return await self.run(create)

    async def begin_publish(self,guild,rid,actor,channel):
        def publish(c):
            cfg=self._live(c,guild)
            row=decode(c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,rid)).fetchone())
            if row['status']!='draft':raise ValueError("Publication already started. Recover the saved message instead of publishing again.")
            if row['spec']['ends']<=self.clock()+30:raise ValueError("The draft deadline is too close or has passed.")
            contract={'guild':guild,'raffle':rid,'spec':row['spec'],'member_role':cfg['member_role']}
            seed=secrets.token_hex(32)
            c.execute("UPDATE raffles SET status='publishing',channel=?,contract=?,hash=?,seed=?,commitment=? WHERE id=?",
             (channel,canonical(contract),digest(contract),seed,drawing.commitment(seed),rid))
            self._audit(c,guild,actor,'raffle_publish',str(rid))
        await self.run(publish)
        return await self.raffle(guild,rid)

    async def edit_raffle(self,guild,rid,spec,actor,expected):
        spec=raffle_spec(spec)
        if spec['ends']<=self.clock()+30:raise ValueError('Choose a future deadline.')
        def edit(c):
            row=decode(c.execute('SELECT * FROM raffles WHERE guild=? AND id=?',(guild,rid)).fetchone())
            if row['status']!='draft' or digest(row['spec'])!=expected:raise ValueError('This draft changed. Reopen it before editing.')
            c.execute('UPDATE raffles SET spec=? WHERE id=?',(canonical(spec),rid))
            self._audit(c,guild,actor,'raffle_edited',str(rid))
        await self.run(edit)

    async def bind_raffle(self,guild,rid,message):
        if not await self.execute("UPDATE raffles SET message=?,status='open',error='' WHERE guild=? AND id=? AND status='publishing'",(ident(message),guild,rid)):
            raise ValueError("Raffle is not awaiting publication recovery.")

    async def buy(self,guild,rid,user,quantity,request,name=''):
        guild,user=ident(guild),ident(user);integer(quantity,1,2000);request=clean(str(request),100)
        def purchase(c):
            self._live(c,guild)
            previous=c.execute("SELECT * FROM purchases WHERE request=?",(request,)).fetchone()
            if previous:
                if (previous['guild'],previous['raffle'],previous['user'],previous['quantity'])!=(guild,rid,user,quantity):
                    raise ValueError("Purchase request identity conflict.")
                return {**dict(previous),'created':False}
            r=decode(c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,rid)).fetchone())
            if r['status']!='open' or self.clock()>=r['spec']['ends']:raise ValueError("Ticket sales have closed.")
            held=c.execute("SELECT COALESCE(SUM(quantity),0) FROM purchases WHERE raffle=? AND user=? AND state!='refunded'",(rid,user)).fetchone()[0]
            if held+quantity>r['spec']['max_tickets']:raise ValueError("This purchase exceeds your ticket limit.")
            cost=quantity*r['spec']['price']
            account=c.execute("SELECT available FROM accounts WHERE guild=? AND user=?",(guild,user)).fetchone()
            if not account or account[0]<cost:raise ValueError("Insufficient available RC.")
            pid=c.execute("INSERT INTO purchases(raffle,guild,user,quantity,cost,request,at) VALUES(?,?,?,?,?,?,?)",(rid,guild,user,quantity,cost,request,int(self.clock()))).lastrowid
            self._entry(c,guild,user,-cost,cost,0,'rc_raffle','reserve',str(pid),f"Reserved for raffle #{rid}: {quantity} tickets",user,'purchase:'+request,name)
            return {**dict(c.execute("SELECT * FROM purchases WHERE id=?",(pid,)).fetchone()),'created':True}
        return await self.run(purchase)

    async def freeze_raffle(self,guild,rid,actor=0,early=False):
        def freeze(c):
            r=decode(c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,rid)).fetchone())
            if r['status']=='closing':return r
            if r['status']!='open' or (self.clock()<r['spec']['ends'] and not early):raise ValueError("Raffle is not ready to close.")
            pool=[dict(x) for x in c.execute("SELECT user,SUM(quantity) weight FROM purchases WHERE raffle=? AND state='reserved' GROUP BY user ORDER BY user",(rid,))]
            c.execute("UPDATE raffles SET status='closing',frozen=? WHERE id=?",(canonical(pool),rid))
            self._audit(c,guild,actor,'raffle_frozen',str(rid))
            return {**r,'status':'closing','frozen':pool}
        return await self.run(freeze)

    def _settle(self,c,r,eligible,cancel=False):
        for p in c.execute("SELECT * FROM purchases WHERE raffle=? AND state='reserved'",(r['id'],)).fetchall():
            refund=cancel or p['user'] not in eligible
            self._entry(c,r['guild'],p['user'],p['cost'] if refund else 0,-p['cost'],0,'rc_raffle','refund' if refund else 'spend',str(p['id']),
             f"Raffle #{r['id']} "+('refund' if refund else 'ticket cost'),0,f"settle:{p['id']}")
            c.execute("UPDATE purchases SET state=? WHERE id=?",('refunded' if refund else 'spent',p['id']))

    async def finalize_raffle(self,guild,rid,checks):
        def finish(c):
            if c.execute("SELECT 1 FROM financial_blocks WHERE guild=?",(guild,)).fetchone():raise ValueError("Accounting is paused. Settlement requires a verified ledger.")
            r=decode(c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,rid)).fetchone())
            if r['status'] in ('drawn','cancelled'):return r
            if r['status']!='closing':raise ValueError("Raffle is not closing.")
            frozen={x['user']:x['weight'] for x in r['frozen']}
            if len(checks)!=len(frozen) or {x['user'] for x in checks}!=set(frozen) or any(type(x['eligible']) is not bool for x in checks):
                raise ValueError("Eligibility evidence must cover every frozen entrant exactly once.")
            eligible={x['user'] for x in checks if x['eligible']}
            cancel=len(eligible)<r['spec']['minimum']
            self._settle(c,r,eligible,cancel)
            pool=[{'user':uid,'weight':frozen[uid]} for uid in sorted(eligible)]
            result=drawing.result(r['seed'],r['hash'],pool,0 if cancel else r['spec']['winners'])
            for uid in result['winners']:c.execute("INSERT INTO prizes(raffle,user,round) VALUES(?,?,0)",(rid,uid))
            status='cancelled' if cancel else 'drawn'
            c.execute("UPDATE raffles SET status=?,checks=?,rounds=?,error='',announcement_state='pending' WHERE id=?",(status,canonical(checks),canonical([result]),rid))
            self._audit(c,guild,0,'raffle_finalized',f"{rid}; {status}; {len(pool)} eligible")
            return {**r,'status':status,'checks':checks,'rounds':[result]}
        return await self.run(finish)

    async def cancel_raffle(self,guild,rid,actor,reason):
        clean(reason,500)
        def cancel(c):
            if c.execute("SELECT 1 FROM financial_blocks WHERE guild=?",(guild,)).fetchone():raise ValueError("Accounting is paused. Refunds require a verified ledger.")
            r=decode(c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,rid)).fetchone())
            if r['status']=='cancelled':return False
            if r['status']=='drawn':raise ValueError("A completed draw cannot be cancelled.")
            if r['status']=='closing':raise ValueError("Closing is in progress. Resolve eligibility before cancellation.")
            self._settle(c,r,set(),True)
            c.execute("UPDATE raffles SET status='cancelled',error=?,announcement_state='pending' WHERE id=?",(reason,rid))
            self._audit(c,guild,actor,'raffle_cancel',f"{rid}: {reason}");return True
        return await self.run(cancel)

    async def prize_status(self,guild,rid,user,status,actor,note=''):
        if status not in ('claimed','delivered','forfeited'):raise ValueError("Invalid prize state.")
        def update(c):
            r=decode(c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,rid)).fetchone())
            if r['status']!='drawn':raise ValueError("Results are not final.")
            p=c.execute("SELECT * FROM prizes WHERE raffle=? AND user=?",(rid,user)).fetchone()
            if not p:raise ValueError("This member has no prize in this raffle.")
            if p['state']==status:return False
            if p['state'] not in ('pending','claimed') or (status=='claimed' and p['state']!='pending'):
                raise ValueError("This prize has a final status.")
            c.execute("UPDATE prizes SET state=?,note=? WHERE raffle=? AND user=?",(status,note[:500],rid,user))
            self._audit(c,guild,actor,'prize_status',f"{rid}:{user}:{status}; {note}");return True
        return await self.run(update)

    async def reroll_raffle(self,guild,rid,checks,actor,reason):
        clean(reason,500)
        def reroll(c):
            r=decode(c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,rid)).fetchone())
            if r['status']!='drawn':raise ValueError("Only a completed raffle supports replacement draws.")
            targets=[x[0] for x in c.execute("SELECT user FROM prizes WHERE raffle=? AND state='forfeited' ORDER BY user",(rid,))]
            if not targets:raise ValueError("Mark an undelivered prize forfeited first.")
            seen={u for rnd in r['rounds'] for u in rnd['winners']}
            original={x['user']:x['weight'] for x in r['rounds'][0]['pool'] if x['user'] not in seen}
            if len(checks)!=len(original) or {x['user'] for x in checks}!=set(original) or any(type(x['eligible']) is not bool for x in checks):raise ValueError("Incomplete replacement eligibility evidence.")
            pool=[{'user':x['user'],'weight':original[x['user']]} for x in checks if x['eligible']]
            if not pool:raise ValueError("No eligible replacement remains.")
            rnd=drawing.result(r['seed'],r['hash'],pool,min(len(targets),25),len(r['rounds']))
            rounds=[*r['rounds'],rnd]
            for target in targets[:len(rnd['winners'])]:c.execute("UPDATE prizes SET state='replaced' WHERE raffle=? AND user=?",(rid,target))
            for user in rnd['winners']:c.execute("INSERT INTO prizes(raffle,user,round) VALUES(?,?,?)",(rid,user,rnd['round']))
            c.execute("UPDATE raffles SET rounds=?,announcement_state='pending',announcement=NULL WHERE id=?",(canonical(rounds),rid))
            self._audit(c,guild,actor,'raffle_replacement',f"{rid}; {reason}")
            return rnd
        return await self.run(reroll)

    async def raffle_proof(self,guild,rid):
        r=await self.raffle(guild,rid)
        if r['status'] not in ('drawn','cancelled') or not r['rounds']:raise ValueError("Proof becomes available after finalization.")
        return {k:r[k] for k in ('contract','seed','commitment','rounds')}|{'contract_hash':r['hash'],'checks':r['checks'],'frozen':r['frozen']}
