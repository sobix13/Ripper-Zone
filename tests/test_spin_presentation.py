"""Spin media uses real SDK payloads and durable claims before any display effect."""
import asyncio
import json
from unittest.mock import AsyncMock,MagicMock
import discord
from discord.http import handle_message_parameters
import pytest
from ripper_zone import ui
from test_discord_operations import fake_bot,interaction,payload


def text(view):
    return '\n'.join(c.content for c in view.walk_children() if isinstance(c,discord.ui.TextDisplay))


def buttons(view):
    return [c for c in view.walk_children() if isinstance(c,discord.ui.Button)]


def serialize_edit(kwargs):
    with handle_message_parameters(view=kwargs['view'],attachments=kwargs['attachments'],allowed_mentions=kwargs['allowed_mentions']) as params:
        body=params.payload
        if body is None:body=json.loads(next(p['value'] for p in params.multipart if p['name']=='payload_json'))
        assert body['flags']&32768
        assert body['allowed_mentions']=={'parse':[]}
        return body


async def test_spin_edits_one_private_message_after_committing_and_then_shows_balance(db,monkeypatch):
    b=fake_bot(db);i=interaction();edits=[]
    async def edit(**kwargs):
        claim=await db.spin_today(1,3)
        assert claim and (await db.account(1,3))['available']==claim['amount']
        edits.append((kwargs['view'],serialize_edit(kwargs)))
    i.edit_original_response.side_effect=edit
    pause=AsyncMock();monkeypatch.setattr(ui,'sleep',pause)
    await ui.spin(b,i)
    assert len(edits)==2 and i.followup.send.await_count==0
    busy,final=edits[0][0],edits[1][0]
    assert busy.owner==final.owner==3
    assert not await final.interaction_check(interaction(4))
    assert busy.art=='spin-decelerating.gif' and final.art=='spin-start.png'
    assert edits[0][1]['components'][0]['components'][0]['type']==12
    assert len(buttons(busy))==1 and buttons(busy)[0].disabled
    assert 'received' not in text(busy) and ' RC**' not in text(busy)
    pause.assert_awaited_once_with(4)
    claim=await db.spin_today(1,3)
    assert f"{claim['amount']} RC" in text(final) and 'Available balance:' in text(final)
    assert next(c for c in buttons(final) if c.label=='Claim Recorded').disabled
    # A new click against an old screen shows the saved result without animation.
    j=interaction();j.id+=1;await ui.spin(b,j)
    assert j.edit_original_response.await_count==1
    assert j.edit_original_response.call_args.kwargs['view'].art=='spin-start.png'
    assert pause.await_count==1 and len(await db.query('SELECT * FROM ledger'))==1


async def test_claimed_page_reopens_with_saved_amount_and_still_art(db):
    b=fake_bot(db);claim=await db.spin(1,3,'Alice',100)
    i=interaction();await ui.member_page(b,i,'spin')
    s=i.followup.send.call_args.kwargs['view'];body=payload(s)
    assert s.art=='spin-start.png' and body['components'][0]['components'][0]['type']==12
    assert f"{claim['amount']} RC" in text(s)
    assert not any(c.label=='Spin · Free' for c in buttons(s))
    assert len(await db.query('SELECT * FROM spin_claims'))==1


@pytest.mark.parametrize('failures',[{1},{2},{1,2}])
async def test_media_failures_still_report_the_committed_reward(db,monkeypatch,failures):
    b=fake_bot(db);b.report_error=MagicMock();i=interaction();calls=0
    async def edit(**kwargs):
        nonlocal calls
        calls+=1
        for attachment in kwargs['attachments']:attachment.close()
        if calls in failures:raise OSError('simulated media failure')
    i.edit_original_response.side_effect=edit
    pause=AsyncMock();monkeypatch.setattr(ui,'sleep',pause)
    await ui.spin(b,i)
    claim=await db.spin_today(1,3)
    assert claim and len(await db.query('SELECT * FROM ledger'))==1
    assert b.report_error.call_count==len(failures)
    assert pause.await_count==(0 if 1 in failures else 1)
    if 2 in failures:
        assert f"{claim['amount']} RC" in i.followup.send.call_args.kwargs['content']
        assert i.followup.send.call_args.kwargs['ephemeral'] is True


async def test_concurrent_clicks_animate_once_and_cancellation_keeps_claim(db,monkeypatch):
    b=fake_bot(db);entered=asyncio.Event();release=asyncio.Event()
    async def pause(seconds):entered.set();await release.wait()
    monkeypatch.setattr(ui,'sleep',pause)
    first=interaction();task=asyncio.create_task(ui.spin(b,first))
    await asyncio.wait_for(entered.wait(),2)
    second=interaction();second.id+=1;await ui.spin(b,second)
    assert second.edit_original_response.await_count==1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    # A recreated client reads the committed claim even after the animation was cut off.
    restarted=fake_bot(db);third=interaction();third.id+=2;await ui.spin(restarted,third)
    assert third.edit_original_response.await_count==1
    assert len(await db.query('SELECT * FROM spin_claims'))==1
    assert len(await db.query('SELECT * FROM ledger'))==1


async def test_spin_crossing_midnight_preserves_old_result_and_unlocks_next_day(db,clock,monkeypatch):
    b=fake_bot(db);clock.now=clock.now//86400*86400+86399
    async def pause(seconds):clock.now+=4
    monkeypatch.setattr(ui,'sleep',pause)
    i=interaction();await ui.spin(b,i)
    s=i.edit_original_response.call_args.kwargs['view']
    assert 'next daily spin is ready' in text(s)
    assert await db.spin_today(1,3) is None
    page=interaction();await ui.member_page(b,page,'spin')
    s=page.followup.send.call_args.kwargs['view']
    assert any(c.label=='Spin · Free' and not c.disabled for c in buttons(s))


@pytest.mark.parametrize('setting,value',[('active',False),('spin_enabled',False),('spin_role',123)])
async def test_spin_checks_current_access_before_awarding_or_animating(db,setting,value):
    cfg,revision=await db.config(1);cfg[setting]=value;await db.save_config(1,cfg,revision,2)
    b=fake_bot(db);i=interaction()
    with pytest.raises(ValueError):await ui.spin(b,i)
    assert not await db.query('SELECT * FROM spin_claims')
    i.edit_original_response.assert_not_awaited()
