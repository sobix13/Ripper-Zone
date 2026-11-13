"""Only leaderboard visibility changes for the two designated server roles."""
import csv
import io
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import discord
import pytest
from ripper_zone import member_ui
from ripper_zone.service import leaderboard_exclusions
from test_panel_workflows import panel,shown

ROLE_A=1560351679700799588
ROLE_B=1560351676718780617


def member(uid,*roles):return NS(id=uid,roles=[NS(id=r) for r in roles])
def text(view):return '\n'.join(c.content for c in view.walk_children() if isinstance(c,discord.ui.TextDisplay))


@pytest.mark.parametrize('period',['all','today','week','month'])
async def test_role_holders_hidden_in_every_period_with_correct_ties_and_pagination(panel,period,clock):
    b,g,_,_,fresh=panel;clock.now=int(time.time())
    g.members=[member(3,ROLE_A),member(4,ROLE_B),member(5,999)]
    await b.db.award(1,{3:'Hidden A'},100,2,'Reward','A')
    await b.db.award(1,{4:'Hidden B'},90,2,'Reward','B')
    await b.db.award(1,{u:str(u) for u in range(5,28)},20,2,'Reward','visible')
    before=await b.db.query('SELECT * FROM ledger')
    excluded=await leaderboard_exclusions(g);assert set(excluded)=={3,4}
    since=member_ui.period_start(period,clock.now)
    board=await b.db.leaderboard(1,25,since,excluded=excluded)
    assert board['total']==23 and len(board['rows'])==10
    assert all(r['user'] not in (3,4) and r['rank']==1 for r in board['rows'])
    assert board['mine']['rank']==1 and board['mine']['position']==21
    last=await b.db.leaderboard(1,25,since,20,excluded=excluded)
    assert [r['user'] for r in last['rows']]==[25,26,27]
    assert (await b.db.account(1,25,excluded=excluded))['rank']==1
    assert (await b.db.account(1,3,excluded=excluded))['rank'] is None
    i=fresh(3);await member_ui.page_view(b,i,'leaders',period=period)
    content=text(shown(i));assert '<@3>' not in content and '<@4>' not in content and 'Your rank: Not listed' in content
    i=fresh(3);await member_ui.page_view(b,i,'dashboard')
    assert '100 RC available' in text(shown(i)) and 'Rank: Not listed' in text(shown(i))
    assert (await b.db.account(1,3))['earned']==100 and (await b.db.account(1,4))['earned']==90
    assert await b.db.query('SELECT * FROM ledger')==before


async def test_public_refresh_and_public_move_apply_the_same_exclusion(panel):
    b,g,channels,_,_=panel;g.members=[member(3,ROLE_A,ROLE_B),member(4)]
    await b.db.award(1,{3:'Hidden'},100,2,'Reward','hidden');await b.db.award(1,{4:'Visible'},5,2,'Reward','visible')
    await b.refresh_leaderboard(g,publish=True)
    content=text(channels[13].send.call_args.kwargs['view'])
    assert '<@3>' not in content and '<@4>' in content
    cfg,rev=await b.db.config(1);await b.service.move_public(g,'leaderboard',11,2,rev)
    moved=text(channels[11].send.call_args.kwargs['view'])
    assert '<@3>' not in moved and '<@4>' in moved


async def test_incomplete_cache_loads_offline_role_holders_and_failure_never_publishes(panel):
    b,g,channels,_,_=panel;g.chunked=False;g.members=[];g.chunk=AsyncMock(return_value=[member(3,ROLE_B)])
    assert await leaderboard_exclusions(g)==(3,)
    g.chunk.assert_awaited_once_with(cache=True)
    g.chunk.side_effect=TimeoutError()
    with pytest.raises(TimeoutError):await b.refresh_leaderboard(g,publish=True)
    channels[13].send.assert_not_awaited()
    g.chunked=True;await b.refresh_leaderboard(g,publish=True)
    before,revision=await b.db.config(1);g.chunked=False
    with pytest.raises(TimeoutError):await b.service.move_public(g,'leaderboard',11,2,revision)
    assert (await b.db.config(1))[0]==before


async def test_role_addition_and_removal_update_visibility_without_changing_rc(panel):
    b,g,_,_,_=panel;await b.db.award(1,{3:'Alice'},12,2,'Reward','award')
    before=member(3);after=member(3,ROLE_A);before.guild=after.guild=g
    g.members=[after];await b.on_member_update(before,after)
    assert await b.db.query("SELECT 1 FROM jobs WHERE key='leaderboard:1' AND state='pending'")
    assert not (await b.db.leaderboard(1,3,excluded=await leaderboard_exclusions(g)))['rows']
    g.members=[before];await b.on_member_update(after,before)
    assert (await b.db.leaderboard(1,3,excluded=await leaderboard_exclusions(g)))['mine']['rank']==1
    assert (await b.db.account(1,3))['available']==12
    assert len(await b.db.query('SELECT * FROM ledger'))==1


async def test_leaderboard_csv_hides_roles_but_ledger_export_retains_all_records(panel):
    b,g,_,_,fresh=panel;g.members=[member(3,ROLE_B),member(4)]
    await b.db.award(1,{3:'Hidden',4:'Visible'},5,2,'Reward','award')
    for kind,expected in [('leaderboard',{'4'}),('ledger',{'3','4'})]:
        i=fresh();await b.tree.get_command('ripper').get_command('report').callback(i,kind=kind)
        file=i.followup.send.call_args.kwargs['file'];file.fp.seek(0)
        rows=list(csv.DictReader(io.StringIO(file.fp.read().decode('utf-8-sig'))))
        assert {r['user'] for r in rows}==expected
