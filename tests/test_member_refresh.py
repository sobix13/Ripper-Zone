"""Member navigation and human-readable duration contracts."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import discord
import pytest
from ripper_zone import ui,member_ui,admin_ui
from ripper_zone.durations import parse_duration,duration_input,format_duration,MAX_TASK_TIME
from test_discord_operations import interaction,fake_bot,payload
from test_panel_workflows import panel,button,shown


@pytest.mark.parametrize('value,seconds',[('12s',12),('12m',720),('12h',43200),('12d',1036800),(' 12 H ',43200),('90d',MAX_TASK_TIME)])
def test_duration_inputs(value,seconds):
    assert parse_duration(value)==seconds
    assert parse_duration(duration_input(seconds))==seconds


@pytest.mark.parametrize('value',['12','0','0s','-2h','1.5h','1w','91d','999999999999999999d','1h30m','',chr(0x6f1)+'h'])
def test_invalid_time_never_silently_changes_units(value):
    with pytest.raises(ValueError):parse_duration(value)


def test_explicit_no_limit_and_readable_units():
    assert parse_duration('none',allow_none=True)==0 and duration_input(0)=='none'
    with pytest.raises(ValueError):parse_duration('none')
    assert format_duration(90061)=='1 day 1 hour 1 minute 1 second'
    assert format_duration(720)=='12 minutes'


def labels(view):return [x.label for x in view.walk_children() if isinstance(x,discord.ui.Button)]


async def test_home_dashboard_and_contextual_navigation(db):
    bot=fake_bot(db)
    for page,expected,accent in [('home',['Daily Spin','Community Tasks','RC Raffles','My Dashboard','Help'],ui.INK),('dashboard',['My Prizes','Leaderboard','My Activity','History','Home','Help'],ui.TEAL),('activity',['Back to Dashboard','Home','Help'],ui.TEAL)]:
        i=interaction();await member_ui.page_view(bot,i,page);s=i.followup.send.call_args.kwargs['view']
        assert labels(s)==expected
        assert payload(s)['components'][0]['accent_color']==accent
    i=interaction();await member_ui.page_view(bot,i,'spin');s=i.followup.send.call_args.kwargs['view']
    assert payload(s)['components'][0]['accent_color']==ui.GOLD
    assert 'Leaderboard' not in labels(s) and 'Spin Details' in labels(s)
    j=interaction();await button(s,'Spin Details').callback(j);details=j.followup.send.call_args.kwargs['view']
    text=' '.join(x.content for x in details.walk_children() if isinstance(x,discord.ui.TextDisplay))
    assert '0.5%' in text and '5 RC' in text


async def test_private_navigation_replaces_attachments_and_public_entry_stays_private(db):
    bot=fake_bot(db)
    for ephemeral in (True,False):
        i=interaction();i.type=discord.InteractionType.component;i.message=NS(flags=NS(ephemeral=ephemeral))
        i.response.defer=AsyncMock(side_effect=lambda **_:setattr(i.response,'done',True))
        await member_ui.page_view(bot,i,'dashboard')
        if ephemeral:
            assert i.edit_original_response.await_count==1 and i.followup.send.await_count==0
            kwargs=i.edit_original_response.call_args.kwargs
            assert kwargs['attachments'][0].filename=='balance.png'
            assert kwargs['allowed_mentions'].to_dict()=={'parse':[]}
            i.response.defer.assert_awaited_once_with()
        else:
            assert i.edit_original_response.await_count==0 and i.followup.send.await_count==1
            i.response.defer.assert_awaited_once_with(ephemeral=True,thinking=True)


async def test_task_duration_edit_and_relative_deadline_preserve_recurrence(panel,monkeypatch):
    b,g,_,_,fresh=panel
    tid=await b.db.create_task(1,2,'Timing','Read this',5,86400,720)
    await b.db.bind_task(1,tid,555)
    i=fresh();await admin_ui.task_detail(b,i,tid);view=shown(i)
    j=fresh();await button(view,'Timing and Reward').callback(j)
    assert j.response.modal.inputs['cooldown'].default=='12m'
    j.response.modal.inputs['cooldown']._value='12d';k=fresh();await j.response.modal.on_submit(k)
    assert (await b.db.task(1,tid))['cooldown']==1036800
    task=await b.db.task(1,tid);i=fresh();await admin_ui.deadline_form(b,i,task)
    i.response.modal.inputs['deadline']._value='12h';j=fresh();monkeypatch.setattr(admin_ui.time,'time',lambda:b.db.clock())
    await i.response.modal.on_submit(j);task=await b.db.task(1,tid)
    assert task['ends']==b.db.clock()+43200 and task['period']==86400


async def test_no_submission_or_cooldown_dm_and_thread_notice_is_throttled(panel,monkeypatch):
    b,g,_,thread,_=panel;member=NS(id=3,display_name='Alice',bot=False,roles=[],send=AsyncMock())
    b.service.eligible=AsyncMock(return_value=member)
    tid=await b.db.create_task(1,2,'Task','Post here',5,0,720);await b.db.bind_task(1,tid,555)
    monkeypatch.setattr('ripper_zone.bot.time.monotonic',lambda:100)
    async def post(mid,at):
        msg=NS(author=member,guild=g,channel=thread,id=mid,created_at=NS(timestamp=lambda:at),delete=AsyncMock())
        await b.on_message(msg);return msg
    first=await post(201,b.db.clock());first.delete.assert_not_awaited()
    second=await post(202,b.db.clock()+1);await post(203,b.db.clock()+2)
    second.delete.assert_awaited_once();member.send.assert_not_awaited()
    assert thread.send.await_count==1 and '11 minutes 59 seconds' in thread.send.call_args.args[0]
    assert thread.send.call_args.kwargs['delete_after']==10
    assert len(await b.db.query('SELECT * FROM task_messages'))==1


async def test_private_raffle_confirmation_keeps_its_message_and_one_reservation(db,spec):
    from conftest import open_raffle
    from test_spin_presentation import serialize_edit
    bot=fake_bot(db);bot.service.eligible=AsyncMock(return_value=bot.member)
    await db.award(1,{3:'Alice'},100,2,'Fund','op');rid=await open_raffle(db,spec)
    i=interaction();await ui.defer(i);await ui.purchase_preview(bot,i,rid,{'quantity':'2'})
    preview=i.followup.send.call_args.kwargs['view']
    for _ in range(2):
        j=interaction();j.type=discord.InteractionType.component;j.message=NS(flags=NS(ephemeral=True))
        await button(preview,'Confirm Purchase').callback(j)
        assert j.followup.send.await_count==0 and j.edit_original_response.await_count==1
        assert serialize_edit(j.edit_original_response.call_args.kwargs)['components'][0]['accent_color']==ui.GOLD
    assert (await db.account(1,3))['reserved']==20
