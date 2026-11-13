import asyncio
import collections
import json
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path
import pytest
from ripper_zone.config import settings
from ripper_zone.features import SPIN,spin_reward
from ripper_zone.storage import Database,Conflict


async def test_award_notifications_are_brief_and_replay_does_not_notify_again(db):
    assert await db.award(1,{3:'Alice',4:'Bob'},100,2,'Private review detail','brief-award')==2
    assert await db.award(1,{3:'Alice',4:'Bob'},100,2,'Private review detail','brief-award')==0
    jobs=await db.query("SELECT payload FROM jobs WHERE kind='notice' ORDER BY key")
    notices=[json.loads(row['payload']) for row in jobs]
    assert notices==[{'channel':15,'text':'<@3> received 100 RC.'},{'channel':15,'text':'<@4> received 100 RC.'}]
    rows=await db.query('SELECT actor,reason,da,dr,de FROM ledger ORDER BY user')
    assert rows==[dict(actor=2,reason='Private review detail',da=100,dr=0,de=100)]*2


@pytest.mark.parametrize('da,dr,de',[(10,-10,0),(-10,10,0),(-10,0,-10)])
async def test_non_earning_notifications_do_not_claim_a_new_reward(db,da,dr,de):
    await db.award(1,{3:'Alice'},20,2,'Initial credits','initial')
    if dr<0:
        await db.run(lambda c:db._entry(c,1,3,-10,10,0,'raffle','reserve','op','Reservation',2,'reserve'))
    await db.run(lambda c:db._entry(c,1,3,da,dr,de,'adjustment','test','op','Review detail',2,'non-earning'))
    row=(await db.query("SELECT payload FROM jobs WHERE key='notice:non-earning'"))[0]
    text=json.loads(row['payload'])['text']
    assert 'received' not in text
    assert f'available {da:+}, reserved {dr:+}, earned {de:+}' in text


def test_all_ten_thousand_rolls_exact_distribution():
    actual=collections.Counter(spin_reward(x) for x in range(10000))
    assert actual==dict(SPIN)
    assert Fraction(sum(a*n for a,n in actual.items()),10000)==5
    assert actual[100]==50 and min(actual)==2
    assert Fraction(sum(a*n for a,n in actual.items() if 2<a<100),sum(n for a,n in actual.items() if 2<a<100))==Fraction(768,133)


@pytest.mark.parametrize('roll',[-1,10000,True,1.1,'2',None])
def test_bad_rolls(roll):
    with pytest.raises(ValueError):spin_reward(roll)


async def test_parallel_connections_one_spin(db):
    others=[Database(db.path,db.clock) for _ in range(6)]
    results=await asyncio.gather(*(others[n%6].spin(1,3,'Alice',1000+n) for n in range(60)))
    assert sum(r['created'] for r in results)==1
    assert len({r['amount'] for r in results})==1
    assert (await db.account(1,3))['earned']==results[0]['amount']
    assert len(await db.query("SELECT * FROM ledger"))==1
    assert len(await db.query("SELECT * FROM spin_claims"))==1


async def test_midnight_and_original_request_binding(db,clock):
    clock.now=int(datetime(2026,11,12,23,59,59,tzinfo=timezone.utc).timestamp())
    old=await db.spin(1,3,'Alice',100)
    clock.now+=2
    replay=await db.spin(1,3,'Alice',100)
    assert replay['day']==old['day'] and not replay['created']
    assert await db.spin_today(1,3) is None
    fresh=await db.spin(1,3,'Alice',101)
    assert fresh['day']=='2026-11-13' and fresh['created']
    assert (await db.account(1,3))['earned']==old['amount']+fresh['amount']


async def test_spin_flags_and_server_isolation(db):
    await db.spin(1,3,'A',100)
    cfg,v=await db.config(1);cfg['spin_enabled']=False;await db.save_config(1,cfg,v,2)
    with pytest.raises(ValueError):await db.spin(1,3,'A',101)
    with pytest.raises(ValueError):await db.spin(2,3,'A',100)
    assert len(await db.query('SELECT * FROM spin_claims'))==1


async def test_spin_atomic_rollback_after_ledger_insert(db,monkeypatch):
    original=db._entry
    def fail(*args,**kwargs):
        original(*args,**kwargs);raise RuntimeError('simulated power loss before claim commit')
    monkeypatch.setattr(db,'_entry',fail)
    with pytest.raises(RuntimeError):await db.spin(1,3,'Alice',100)
    assert not await db.query('SELECT * FROM ledger')
    assert not await db.query('SELECT * FROM spin_claims')
    assert not await db.query('SELECT * FROM accounts')
    monkeypatch.setattr(db,'_entry',original)
    assert (await db.spin(1,3,'Alice',100))['created']


async def test_cancellation_waits_for_transaction_before_retry(db):
    started,release=threading.Event(),threading.Event()
    original=db._entry
    def wait(*args,**kwargs):
        started.set();release.wait(5);return original(*args,**kwargs)
    db._entry=wait
    task=asyncio.create_task(db.spin(1,3,'Alice',100))
    await asyncio.to_thread(started.wait,2)
    task.cancel();release.set()
    with pytest.raises(asyncio.CancelledError):await task
    db._entry=original
    assert not (await db.spin(1,3,'Alice',100))['created']
    assert len(await db.query('SELECT * FROM ledger'))==1


async def test_genuine_multiprocess_spin(db):
    code="""import asyncio,sys,json
from ripper_zone.storage import Database
async def run():
 d=Database(sys.argv[1]); print(json.dumps(await d.spin(1,3,'Alice',int(sys.argv[2]))))
asyncio.run(run())
"""
    def processes():
        ps=[subprocess.Popen([sys.executable,'-c',code,db.path,str(100+n)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for n in range(5)]
        results=[]
        for p in ps:
            out,err=p.communicate(timeout=30)
            assert p.returncode==0,err
            results.append(json.loads(out))
        return results
    results=await asyncio.to_thread(processes)
    assert sum(x['created'] for x in results)==1
    assert len(await db.query('SELECT * FROM ledger'))==1


async def test_process_death_uncommitted_sql_is_rolled_back(db):
    code="""import sqlite3,sys,os
c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE')
c.execute("INSERT INTO accounts VALUES(1,3,'A',999,0,999)")
os._exit(17)
"""
    p=await asyncio.create_subprocess_exec(sys.executable,'-c',code,db.path)
    assert await p.wait()==17
    assert not await db.query('SELECT * FROM accounts')
    assert not await db.reconcile(1)
    assert (await db.spin(1,3,'Alice',101))['created']


async def test_process_death_after_commit_preserves_claim(db):
    code="""import asyncio,sys,os
from ripper_zone.storage import Database
async def go():
 await Database(sys.argv[1]).spin(1,3,'Alice',100)
asyncio.run(go());os._exit(0)
"""
    p=await asyncio.create_subprocess_exec(sys.executable,'-c',code,db.path)
    assert await p.wait()==0
    assert not (await db.spin(1,3,'Alice',100))['created']
    assert len(await db.query('SELECT * FROM ledger'))==1


async def test_snapshot_stable_event_and_conflict(db):
    assert await db.snapshot(1,'rumble','44',[3,4,5],5,2)==3
    assert await db.snapshot(1,'rumble','44',[5,3,4,4],5,6)==0
    with pytest.raises(Conflict):await db.snapshot(1,'rumble','44',[3,4],5,2)
    with pytest.raises(Conflict):await db.snapshot(1,'rumble','44',[3,4,5],6,2)
    assert await db.snapshot(1,'raffle','44',[3,4,5],5,2)==3
    assert (await db.account(1,3))['events']==2
    assert not await db.reconcile(1)


async def test_corrections_and_replay(db):
    await db.award(1,{3:'Alice'},5,2,'participation','op')
    await db.adjust(1,3,-10,2,'duplicate contribution correction','fix')
    assert not await db.adjust(1,3,-10,2,'duplicate contribution correction','fix')
    a=await db.account(1,3)
    assert a['available']==a['earned']==-5
    assert len(await db.history(1,3))==2
    with pytest.raises(Conflict):await db.adjust(1,3,-11,2,'different','fix')


@pytest.mark.parametrize('kind',['balance','claim','claim_amount','orphan','reservation'])
async def test_reconciliation_detects_and_pauses_not_repairs(db,kind):
    claim=await db.spin(1,3,'Alice',100)
    if kind=='balance':await db.execute('UPDATE accounts SET available=available+1')
    if kind=='claim':await db.execute('DELETE FROM ledger')
    if kind=='claim_amount':await db.execute('UPDATE spin_claims SET amount=99')
    if kind=='orphan':await db.execute('DELETE FROM spin_claims')
    if kind=='reservation':await db.execute('UPDATE accounts SET reserved=1')
    assert await db.reconcile(1)==[3]
    assert await db.query('SELECT * FROM financial_blocks')
    with pytest.raises(ValueError):await db.award(1,{4:'Bob'},5,2,'test','new')
    with pytest.raises(ValueError):await db.clear_financial_block(1,2)


async def test_revision_conflicts_and_configuration_history(db):
    cfg,v=await db.config(1)
    await db.save_config(1,cfg,v,2)
    with pytest.raises(Conflict):await db.save_config(1,cfg,v,2)
    for n in range(35):
        cfg,v=await db.config(1);await db.save_config(1,cfg,v,2)
    assert len(await db.query('SELECT * FROM settings_history WHERE guild=1'))==30


async def test_verified_online_backup_and_restore_read(db,tmp_path):
    await db.spin(1,3,'Alice',100)
    target=tmp_path/'backups/copy.sqlite3';await db.backup(target)
    copied=Database(target,db.clock)
    assert (await copied.account(1,3))['earned']==(await db.account(1,3))['earned']
    assert target.stat().st_mode&0o777==0o600
    assert list((await copied.query('PRAGMA quick_check'))[0].values())==['ok']


async def test_job_leases_expiry_and_bounded_retries(db,clock):
    await db.enqueue('x','notice',1,{'text':'one'})
    old=await db.claim_job();assert old['key']=='x'
    assert await db.claim_job() is None
    clock.now+=181
    current=await db.claim_job()
    await db.finish_job(old)
    assert (await db.query("SELECT state FROM jobs WHERE key='x'"))[0]['state']=='running'
    for n in range(8):
        await db.finish_job(current,'HTTP failed')
        clock.now+=1000
        if n<7:current=await db.claim_job()
    assert (await db.query("SELECT state FROM jobs WHERE key='x'"))[0]['state']=='failed'
