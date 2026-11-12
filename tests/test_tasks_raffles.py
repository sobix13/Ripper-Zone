import asyncio
import copy
import pytest
from ripper_zone import drawing
from ripper_zone.features import cycle
from ripper_zone.storage import Database
from conftest import open_raffle


async def test_task_base_shared_by_reaction_snapshot_and_moderators(db,clock):
    tid=await db.create_task(1,2,'Task','Post a collector photo',5,86400,60)
    await db.bind_task(1,tid,111)
    assert await db.accept_message(1,tid,3,201,clock.now)==0
    assert await db.task_award(1,tid,{3:'Alice'},0,2,'reaction:201')==1
    assert await db.task_award(1,tid,{3:'Alice'},0,4,'snapshot:22')==0
    assert await db.task_award(1,tid,{3:'Alice'},0,5,'reaction:201')==0
    clock.now=(clock.now//86400+1)*86400
    assert await db.task_award(1,tid,{3:'Alice'},1,2,'next')==1
    assert (await db.account(1,3))['earned']==10
    assert (await db.account(1,3))['tasks']==2
    assert await db.task_award(1,tid,{3:'Alice'},1,2,'quality:201','quality',3)==1
    assert await db.task_award(1,tid,{3:'Alice'},1,4,'quality:201','quality',3)==0
    assert (await db.account(1,3))['earned']==13


async def test_task_cooldown_and_moderator_bypass(db,clock):
    tid=await db.create_task(1,2,'Task','Instructions',5,0,60)
    await db.bind_task(1,tid,111)
    assert await db.accept_message(1,tid,3,201,clock.now)==0
    assert await db.accept_message(1,tid,3,202,clock.now+10)>0
    assert await db.accept_message(1,tid,3,203,clock.now+11,True)==0
    assert await db.accept_message(1,tid,3,204,clock.now+60)==0
    assert len(await db.query('SELECT * FROM task_messages'))==3
    with pytest.raises(ValueError):await db.task_award(1,tid,{3:'Alice'},1,2,'future')
    await db.execute("UPDATE tasks SET status='closed' WHERE id=?",(tid,))
    assert await db.accept_message(1,tid,3,205,clock.now+70)==-1
    # Review after closing still pays the original accepted cycle.
    assert await db.task_award(1,tid,{3:'Alice'},0,2,'review')==1


def test_weekly_cycles_anchor_to_creation_utc_day():
    task={'created':1794484800,'period':604800}
    anchor=task['created']//86400*86400
    assert cycle(task,anchor+604799)==0
    assert cycle(task,anchor+604800)==1
    assert cycle({**task,'period':0},anchor+900000)==0


async def test_overspending_race_across_connections(db,spec):
    await db.award(1,{3:'Alice'},100,2,'test','fund')
    rid=await open_raffle(db,{**spec,'price':30})
    connections=[Database(db.path,db.clock) for _ in range(5)]
    results=await asyncio.gather(*(connections[n%5].buy(1,rid,3,1,f'buy:{n}') for n in range(12)),return_exceptions=True)
    assert sum(isinstance(x,dict) for x in results)==3
    a=await db.account(1,3)
    assert (a['available'],a['reserved'],a['earned'])==(10,90,100)
    assert (await db.leaders(1))[0]['earned']==100
    assert not await db.reconcile(1)


async def test_duplicate_purchase_durable_replay_and_cap(db,spec):
    await db.award(1,{3:'Alice'},100,2,'test','fund')
    rid=await open_raffle(db,{**spec,'max_tickets':2})
    first=await db.buy(1,rid,3,2,'buy')
    assert not (await db.buy(1,rid,3,2,'buy'))['created']
    with pytest.raises(ValueError):await db.buy(1,rid,3,1,'buy')
    with pytest.raises(ValueError):await db.buy(1,rid,3,1,'another')
    await db.cancel_raffle(1,rid,2,'cancelled event')
    assert not await db.cancel_raffle(1,rid,2,'cancelled event')
    assert (await db.account(1,3))['available']==100
    assert (await db.buy(1,rid,3,2,'buy'))['state']=='refunded'
    assert len(await db.query("SELECT * FROM ledger WHERE kind='refund'"))==1


async def test_minimum_is_unique_eligible_people_not_tickets(db,spec):
    await db.award(1,{3:'Alice',4:'Bob'},100,2,'test','fund')
    rid=await open_raffle(db,{**spec,'minimum':3})
    await db.buy(1,rid,3,10,'a');await db.buy(1,rid,4,5,'b')
    await db.freeze_raffle(1,rid,early=True)
    r=await db.finalize_raffle(1,rid,[{'user':3,'eligible':True},{'user':4,'eligible':True}])
    assert r['status']=='cancelled' and not r['rounds'][0]['winners']
    assert (await db.account(1,3))['available']==100
    assert (await db.account(1,4))['reserved']==0
    assert drawing.verify(await db.raffle_proof(1,rid))


async def test_weighted_draw_refunds_excluded_and_never_redraws(db,spec):
    await db.award(1,{3:'Alice',4:'Bob',5:'Carol'},100,2,'test','fund')
    rid=await open_raffle(db,spec)
    for uid,quantity in ((3,3),(4,2),(5,1)):await db.buy(1,rid,uid,quantity,str(uid))
    await db.freeze_raffle(1,rid,early=True)
    checks=[{'user':3,'eligible':True},{'user':4,'eligible':True},{'user':5,'eligible':False}]
    r=await db.finalize_raffle(1,rid,checks)
    assert r['rounds'][0]['pool']==[{'user':3,'weight':3},{'user':4,'weight':2}]
    assert len(set(r['rounds'][0]['winners']))==2
    assert (await db.account(1,5))['available']==100
    assert (await db.account(1,3))['available']==70
    assert (await db.account(1,3))['earned']==100
    again=await db.finalize_raffle(1,rid,checks)
    assert r['rounds']==again['rounds']
    assert not await db.reconcile(1)
    proof=await db.raffle_proof(1,rid)
    assert drawing.verify(proof)
    for field in ('seed','commitment','contract_hash'):
        bad=copy.deepcopy(proof);bad[field]='0'*64;assert not drawing.verify(bad)
    bad=copy.deepcopy(proof);bad['rounds'][0]['pool'][0]['weight']+=1
    assert not drawing.verify(bad)
    bad=copy.deepcopy(proof);bad['rounds'][0]['winners'].pop()
    assert not drawing.verify(bad)


async def test_incomplete_or_duplicate_eligibility_never_settles(db,spec):
    await db.award(1,{3:'Alice',4:'Bob'},100,2,'test','fund')
    rid=await open_raffle(db,spec)
    await db.buy(1,rid,3,1,'a');await db.buy(1,rid,4,1,'b')
    await db.freeze_raffle(1,rid,early=True)
    for checks in ([{'user':3,'eligible':True}],[{'user':3,'eligible':True},{'user':3,'eligible':True}],[{'user':3,'eligible':True},{'user':4,'eligible':None}]):
        with pytest.raises(ValueError):await db.finalize_raffle(1,rid,checks)
    assert (await db.account(1,3))['reserved']==10
    assert (await db.raffle(1,rid))['status']=='closing'


async def test_replacement_uses_original_weights_and_never_charges_again(db,spec):
    await db.award(1,{3:'A',4:'B',5:'C',6:'D'},100,2,'fund','op')
    rid=await open_raffle(db,{**spec,'winners':1})
    for uid,qty in ((3,1),(4,2),(5,3),(6,4)):await db.buy(1,rid,uid,qty,str(uid))
    await db.freeze_raffle(1,rid,early=True)
    r=await db.finalize_raffle(1,rid,[{'user':u,'eligible':True} for u in (3,4,5,6)])
    winner=r['rounds'][0]['winners'][0]
    await db.prize_status(1,rid,winner,'claimed',winner)
    await db.prize_status(1,rid,winner,'forfeited',2,'Did not collect')
    before=await db.query('SELECT * FROM accounts ORDER BY user')
    rnd=await db.reroll_raffle(1,rid,[{'user':u,'eligible':True} for u in (3,4,5,6) if u!=winner],2,'replacement')
    assert winner not in rnd['winners'] and rnd['round']==1
    assert await db.query('SELECT * FROM accounts ORDER BY user')==before
    assert drawing.verify(await db.raffle_proof(1,rid))
    with pytest.raises(ValueError):await db.reroll_raffle(1,rid,[],2,'duplicate')
    replacement=rnd['winners'][0]
    await db.prize_status(1,rid,replacement,'delivered',2)
    with pytest.raises(ValueError):await db.prize_status(1,rid,replacement,'forfeited',2)


async def test_frozen_publication_rules_and_no_repeat_publish(db,spec):
    rid=await open_raffle(db,spec)
    r=await db.raffle(1,rid)
    cfg,v=await db.config(1);cfg['member_role']=99;await db.save_config(1,cfg,v,2)
    assert (await db.raffle(1,rid))['contract']['member_role']==0
    with pytest.raises(ValueError):await db.begin_publish(1,rid,2,14)
    with pytest.raises(ValueError):await db.bind_raffle(1,rid,200)
    with pytest.raises(ValueError):await db.raffle_proof(1,rid)


async def test_deadline_and_financial_pause_protect_purchases_and_settlement(db,spec,clock):
    await db.award(1,{3:'A'},100,2,'test','fund')
    rid=await open_raffle(db,{**spec,'minimum':1})
    await db.buy(1,rid,3,1,'one')
    clock.now=spec['ends']
    with pytest.raises(ValueError):await db.buy(1,rid,3,1,'late')
    await db.freeze_raffle(1,rid)
    await db.execute("INSERT INTO financial_blocks VALUES(1,'test',0)")
    with pytest.raises(ValueError):await db.finalize_raffle(1,rid,[{'user':3,'eligible':True}])
    assert (await db.account(1,3))['reserved']==10


async def test_invalid_task_reward_revocation_removes_metric_without_repaying(db):
    tid=await db.create_task(1,2,'Task','Instructions',5,0,0)
    await db.task_award(1,tid,{3:'Alice'},0,2,'review')
    record=(await db.history(1,3))[0]
    assert (await db.account(1,3))['tasks']==1
    assert await db.revoke(1,record['id'],2,'Invalid contribution')
    assert not await db.revoke(1,record['id'],2,'Invalid contribution')
    account=await db.account(1,3)
    assert account['earned']==0 and account['tasks']==0
    assert await db.task_award(1,tid,{3:'Alice'},0,2,'replay')==0
    assert not await db.reconcile(1)


async def test_invalid_spin_reward_reversal_does_not_grant_a_second_spin(db):
    await db.spin(1,3,'Alice',100)
    record=(await db.history(1,3))[0]
    await db.revoke(1,record['id'],2,'Invalid member participation')
    assert not (await db.spin(1,3,'Alice',101))['created']
    assert (await db.account(1,3))['earned']==0
    assert not await db.reconcile(1)
