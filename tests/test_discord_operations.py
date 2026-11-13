import asyncio
import copy
import io
import json
import logging
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,MagicMock
import aiohttp
from aiohttp.test_utils import TestClient,TestServer
import discord
from discord.http import handle_message_parameters
import pytest
from ripper_zone import ui
from ripper_zone.bot import RipperBot
from ripper_zone.service import Service,role_safe,tier_for
from ripper_zone.operations import start_health,Recovery,RestartBudget
from ripper_zone.coordination import Registry
from conftest import open_raffle


class Response:
    def __init__(self):self.done=False;self.modal=None
    def is_done(self):return self.done
    async def defer(self,**kwargs):
        assert not self.done
        self.done=True
    async def send_message(self,**kwargs):
        assert not self.done
        self.done=True
    async def send_modal(self,modal):
        assert not self.done
        self.done=True;self.modal=modal


def interaction(user=3):
    i=NS(guild_id=1,guild=NS(id=1,members=[],chunked=True),user=NS(id=user),id=1000+user)
    i.response=Response();i.followup=NS(send=AsyncMock())
    i.edit_original_response=AsyncMock()
    return i


def fake_bot(db):
    b=NS(db=db,report_error=lambda e:None)
    b.member=NS(id=3,display_name='Alice',roles=[],bot=False)
    async def access(i,active=False):return b.member,(await db.config(1))[0]
    b.member_access=access;b.authorize=AsyncMock();b.service=Service(b)
    return b


def payload(screen):
    files=screen.files()
    try:
        params=handle_message_parameters(view=screen,files=files,allowed_mentions=ui.MENTIONS)
        body=params.payload
        if body is None:
            body=json.loads(next(x['value'] for x in params.multipart if x['name']=='payload_json'))
        assert body['flags']&32768
        assert screen.content_length()<=4000
        assert len(list(screen.walk_children()))<=40
        ids=[x.custom_id for x in screen.walk_children() if getattr(x,'custom_id',None)]
        assert len(ids)==len(set(ids))
        return body
    finally:
        for f in files:f.close()


@pytest.mark.parametrize('page',['home','balance','spin','tasks','raffles','leaders','progress','history','help'])
async def test_every_member_page_serializes_through_real_discord_http(db,page):
    cfg,v=await db.config(1)
    cfg.update(roles_enabled=True,tiers=[dict(role=10+n,earned=100*n,tasks=n,events=n) for n in (1,2,3)])
    await db.save_config(1,cfg,v,2)
    # Fill history with long reasons to exercise Discord's total text budget.
    for n in range(12):await db.award(1,{3:'Alice'},2,2,'x'*500,str(n))
    b=fake_bot(db);i=interaction()
    await ui.member_page(b,i,page)
    screen=i.followup.send.call_args.kwargs['view']
    body=payload(screen)
    assert body['components'][0]['type']==17
    assert i.response.done
    assert not await screen.interaction_check(interaction(4))


async def test_persistent_gateway_and_raffle_buttons_survive_restart_shapes(db,spec):
    b=fake_bot(db);screen=ui.gateway(b)
    assert screen.is_persistent();payload(screen)
    rid=await open_raffle(db,spec)
    for state in ('open','closing','drawn','cancelled'):
        r=await db.raffle(1,rid);r['status']=state
        screen=ui.raffle_view(b,r);assert screen.is_persistent();payload(screen)
        buy=next(x for x in screen.walk_children() if getattr(x,'custom_id','')==f'rz:buy:{rid}')
        assert buy.disabled==(state!='open')


async def test_spin_click_credits_once_and_shows_saved_result(db,monkeypatch):
    monkeypatch.setattr(ui,'sleep',AsyncMock())
    b=fake_bot(db)
    for n in range(2):
        i=interaction();i.id=100+n
        await ui.spin(b,i)
        screen=i.edit_original_response.call_args.kwargs['view'];payload(screen)
    assert len(await db.query('SELECT * FROM spin_claims'))==1
    assert len(await db.query('SELECT * FROM ledger'))==1


async def test_modal_has_initial_response_and_private_purchase_confirm_is_idempotent(db,spec):
    b=fake_bot(db);b.service.eligible=AsyncMock(return_value=b.member)
    await db.award(1,{3:'Alice'},100,2,'fund','op');rid=await open_raffle(db,spec)
    initial=interaction();await ui.buy_modal(b,initial,rid)
    assert isinstance(initial.response.modal,discord.ui.Modal)
    i=interaction();await i.response.defer(ephemeral=True)
    await ui.purchase_preview(b,i,rid,{'quantity':'2'})
    screen=i.followup.send.call_args.kwargs['view'];payload(screen)
    button=next(x for x in screen.walk_children() if isinstance(x,discord.ui.Button))
    await button.callback(interaction());await button.callback(interaction())
    assert len(await db.query('SELECT * FROM purchases'))==1
    assert (await db.account(1,3))['reserved']==20


async def test_permission_revocation_is_checked_at_confirmation(db,spec):
    b=fake_bot(db);b.service.eligible=AsyncMock(return_value=b.member)
    await db.award(1,{3:'Alice'},100,2,'fund','op');rid=await open_raffle(db,spec)
    i=interaction();await i.response.defer(ephemeral=True)
    await ui.purchase_preview(b,i,rid,{'quantity':'1'})
    screen=i.followup.send.call_args.kwargs['view']
    async def denied(*args,**kwargs):raise ValueError('Access role revoked')
    b.member_access=denied
    button=next(x for x in screen.walk_children() if isinstance(x,discord.ui.Button))
    await button.callback(interaction())
    assert not await db.query('SELECT * FROM purchases')


async def test_authorization_uses_fresh_member_roles_not_stale_interaction(db,monkeypatch):
    monkeypatch.setenv('DISCORD_GUILD_ID','1');monkeypatch.setenv('OWNER_IDS','2')
    b=RipperBot();b.db=db
    cfg,v=await db.config(1);cfg['manager_roles']=[50];await db.save_config(1,cfg,v,2)
    i=interaction();i.guild.owner_id=9
    b.service.eligible=AsyncMock(return_value=NS(id=3,roles=[NS(id=50)]))
    await b.authorize(i)
    with pytest.raises(ValueError):await b.authorize(i,primary=True)
    b.service.eligible=AsyncMock(return_value=NS(id=3,roles=[]))
    with pytest.raises(ValueError):await b.authorize(i)
    owner=interaction(2);owner.guild.owner_id=9
    await b.authorize(owner,primary=True)


async def test_http_forbidden_is_not_ineligible_but_not_found_is(db):
    b=fake_bot(db);guild=NS(fetch_member=AsyncMock())
    response=NS(status=403,reason='Forbidden')
    guild.fetch_member.side_effect=discord.Forbidden(response,{'code':50013,'message':'Missing Permissions'})
    with pytest.raises(discord.Forbidden):await b.service.eligible(guild,3,99)
    guild.fetch_member.side_effect=discord.NotFound(NS(status=404,reason='Not Found'),{'code':10007,'message':'Unknown Member'})
    assert await b.service.eligible(guild,3,99) is None
    guild.fetch_member.side_effect=asyncio.TimeoutError()
    with pytest.raises(asyncio.TimeoutError):await b.service.eligible(guild,3)


async def test_timeout_during_raffle_check_leaves_all_reservations_intact(db,spec):
    b=fake_bot(db);await db.award(1,{3:'Alice',4:'Bob'},100,2,'fund','op')
    rid=await open_raffle(db,spec)
    await db.buy(1,rid,3,1,'a');await db.buy(1,rid,4,1,'b')
    b.service.eligible=AsyncMock(side_effect=asyncio.TimeoutError())
    with pytest.raises(asyncio.TimeoutError):await b.service.close_raffle(NS(id=1),rid,early=True)
    assert (await db.raffle(1,rid))['status']=='closing'
    assert (await db.account(1,3))['reserved']==10
    assert (await db.account(1,4))['reserved']==10
    assert not await db.query('SELECT * FROM prizes')


async def test_announcement_failure_does_not_change_saved_winners(db,spec):
    b=fake_bot(db);b.user=NS(id=99)
    await db.award(1,{3:'Alice',4:'Bob'},100,2,'fund','op');rid=await open_raffle(db,spec)
    await db.buy(1,rid,3,1,'a');await db.buy(1,rid,4,1,'b')
    await db.freeze_raffle(1,rid,early=True)
    r=await db.finalize_raffle(1,rid,[{'user':3,'eligible':True},{'user':4,'eligible':True}])
    channel=NS(fetch_message=AsyncMock(side_effect=asyncio.TimeoutError()))
    guild=NS(id=1,emojis=[],get_channel=lambda _:channel)
    with pytest.raises(asyncio.TimeoutError):await b.service.update_raffle(guild,r)
    assert (await db.raffle(1,rid))['rounds']==r['rounds']
    assert (await db.raffle(1,rid))['announcement_state']=='pending'


def test_role_selection_requires_all_metrics_and_selects_only_highest():
    tiers=[dict(role=n,earned=n*10,tasks=n,events=n) for n in (1,2,3)]
    assert tier_for(dict(earned=100,tasks=2,events=3),tiers)==tiers[1]
    assert tier_for(dict(earned=100,tasks=0,events=3),tiers) is None


@pytest.mark.parametrize('case',['permissions','managed','hierarchy','protected','default','missing'])
def test_unsafe_achievement_roles_rejected(case):
    role=MagicMock();role.id=30;role.is_default.return_value=False;role.managed=False;role.permissions.value=0
    role.__ge__.return_value=False
    guild=NS(me=NS(top_role=NS(id=100),guild_permissions=NS(manage_roles=True)))
    protected=[]
    if case=='permissions':role.permissions.value=8
    if case=='managed':role.managed=True
    if case=='hierarchy':role.__ge__.return_value=True
    if case=='protected':protected=[30]
    if case=='default':role.is_default.return_value=True
    if case=='missing':role=None
    with pytest.raises(ValueError):role_safe(guild,role,protected)


async def test_local_health_http_authentication_and_healthy_ready(db,monkeypatch):
    b=fake_bot(db);b.guild_id=1;b.is_ready=lambda:True;b.get_guild=lambda _:NS(id=1)
    b.started=time.time();b.service.last_tick=time.time()
    secret='s'*48;monkeypatch.setenv('HEALTH_SECRET',secret);monkeypatch.setenv('HEALTH_PORT','0')
    runner=await start_health(b)
    port=next(iter(runner.sites))._server.sockets[0].getsockname()[1]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://127.0.0.1:{port}/health') as response:
                assert response.status==200 and (await response.json())['ok']
            async with session.get(f'http://127.0.0.1:{port}/doctor') as response:assert response.status==401
            b.service.last_tick=time.time()-301
            async with session.get(f'http://127.0.0.1:{port}/health') as response:assert response.status==503
    finally:await runner.cleanup()


async def test_recovery_fatal_marker_stops_restart_before_budget(db,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',db.path);monkeypatch.setenv('DISCORD_GUILD_ID','1');monkeypatch.setenv('HEALTH_SECRET','s'*48);monkeypatch.setenv('OWNER_IDS','2')
    helper=Recovery()
    from pathlib import Path
    Path(db.path+'.fatal').write_text('intents')
    with pytest.raises(ValueError,match='Token or privileged'):await helper.restart()
    assert not helper.budget.data['restarts']


def simulated_guild(bot_id=99):
    guild=NS(id=1,emojis=[],owner_id=2,members=[],chunked=True)
    guild.me=NS(id=bot_id,top_role=NS(id=1000),guild_permissions=NS(manage_roles=True))
    guild.default_role=NS(id=1)
    roles={}
    for rid in (50,90,101,102,103):
        role=MagicMock();role.id=rid;role.is_default.return_value=False;role.managed=False;role.permissions.value=0;role.__ge__.return_value=False
        roles[rid]=role
    guild.get_role=lambda rid:roles.get(rid)
    channels={}
    for cid in (11,12,13,14,15):
        channel=MagicMock(spec=discord.TextChannel);channel.id=cid;channel.name=str(cid)
        def permission(who,cid=cid):
            return NS(**{k:True for k in ('send_messages','read_message_history','attach_files','embed_links','create_public_threads','send_messages_in_threads','manage_threads','manage_messages','add_reactions')},view_channel=who is guild.me or cid!=15)
        channel.permissions_for.side_effect=permission
        channel.send=AsyncMock(return_value=NS(id=700+cid,jump_url=f'https://discord.com/channels/1/{cid}/{700+cid}'))
        channels[cid]=channel
    thread=MagicMock(spec=discord.Thread);thread.id=555;thread.guild=guild;thread.parent_id=12;thread.owner_id=99;thread.mention='<#555>'
    thread.send=AsyncMock(return_value=NS(id=900));thread.edit=AsyncMock()
    async def empty_history(**kwargs):
        for item in ():yield item
    thread.history=empty_history
    thread.archived=False
    channels[12].create_thread=AsyncMock(return_value=thread)
    guild.get_channel=lambda cid:channels.get(cid)
    guild.get_thread=lambda cid:thread if cid==555 else None
    guild.get_channel_or_thread=lambda cid:guild.get_channel(cid) or guild.get_thread(cid)
    return guild,roles,channels,thread


async def test_complete_setup_wizard_skips_roles_then_activates(db,tmp_path):
    b=fake_bot(db);b.user=NS(id=99);b.guild_id=1
    b.registry=Registry(tmp_path/'registry.db','bot:99');await b.registry.open()
    guild,roles,channels,thread=simulated_guild()
    current=ui.Setup(b,2)
    for n,choice in enumerate((11,12,13,14,15,90,50)):
        select=current.children[0]
        select._values=[NS(id=choice)]
        i=interaction(2);i.guild=guild
        await select.callback(i)
        current=i.followup.send.call_args.kwargs['view']
    assert isinstance(current,ui.Screen)
    skip=next(x for x in current.walk_children() if isinstance(x,discord.ui.Button) and x.label=='Skip Roles')
    i=interaction(2);i.guild=guild;await skip.callback(i)
    activate=i.followup.send.call_args.kwargs['view']
    button=next(x for x in activate.walk_children() if isinstance(x,discord.ui.Button))
    i=interaction(2);i.guild=guild;await button.callback(i)
    cfg,_=await db.config(1)
    assert cfg['active'] and cfg['member_role']==90 and cfg['manager_roles']==[50]
    assert not cfg['roles_enabled']
    assert not await db.query('SELECT * FROM accounts')


async def test_task_form_publishes_real_layout_and_durable_thread_brief(db,tmp_path):
    b=fake_bot(db);b.user=NS(id=99);guild,roles,channels,thread=simulated_guild()
    b.registry=Registry(tmp_path/'registry.db','bot:99');await b.registry.open()
    initial=interaction(2);initial.guild=guild
    await ui.task_form(b,initial)
    page=initial.followup.send.call_args.kwargs['view']
    pick=next(x for x in page.walk_children() if isinstance(x,discord.ui.Button) and x.label=='Daily')
    chosen=interaction(2);chosen.guild=guild;await pick.callback(chosen);modal=chosen.response.modal
    for key,value in {'title':'Collector Story','body':'Share a photo and a story','reward':'5','cooldown':'60s','duration':'24h'}.items():modal.inputs[key]._value=value
    i=interaction(2);i.guild=guild;await modal.on_submit(i)
    task=(await db.query('SELECT * FROM tasks'))[0]
    assert task['status']=='active' and task['thread']==555 and task['period']==86400
    job=await db.claim_job();b.get_guild=lambda _:guild
    await b.service.job(job);await db.finish_job(job)
    assert 'Collector Story' in thread.send.call_args.kwargs['view'].box.children[0].children[0].content
    payload(thread.send.call_args.kwargs['view'])


async def test_role_add_failure_keeps_old_tier_and_retry_uses_same_earnings(db,tmp_path):
    b=fake_bot(db);b.registry=Registry(tmp_path/'registry.db','bot:99');await b.registry.open()
    guild,roles,channels,thread=simulated_guild()
    cfg,v=await db.config(1)
    cfg.update(roles_enabled=True,tiers=[dict(role=100+n,earned=n*10,tasks=0,events=0) for n in (1,2,3)])
    await b.service.configure(guild,cfg,v,2)
    await db.award(1,{3:'Alice'},25,2,'fund','op')
    member=NS(bot=False,roles=[roles[101]],add_roles=AsyncMock(side_effect=discord.Forbidden(NS(status=403,reason='Forbidden'),{'message':'Missing Permissions','code':50013})),remove_roles=AsyncMock())
    b.service.eligible=AsyncMock(return_value=member)
    with pytest.raises(discord.Forbidden):await b.service.role_job(guild,3)
    member.remove_roles.assert_not_called()
    member.add_roles.side_effect=None
    await b.service.role_job(guild,3)
    member.add_roles.assert_awaited_with(roles[102],reason='Ripper Zone achievement progress')
    member.remove_roles.assert_awaited()
    assert (await db.account(1,3))['earned']==25


async def test_server_reaction_deduplicates_moderators_with_separate_task_snapshot(db,monkeypatch):
    monkeypatch.setenv('DISCORD_GUILD_ID','1');monkeypatch.setenv('OWNER_IDS','2,4')
    b=RipperBot();b.db=db;b.service.db=db
    b._connection.user=NS(id=99)
    guild,roles,channels,thread=simulated_guild()
    b.get_guild=lambda _:guild
    tid=await db.create_task(1,2,'Task','Photo',5,0,0);await db.bind_task(1,tid,555)
    await db.accept_message(1,tid,3,201,int(time.time()))
    thread.fetch_message=AsyncMock(return_value=NS(id=201,author=NS(id=3,bot=False)))
    async def fetch(uid):return NS(id=uid,bot=False,roles=[],display_name='Alice' if uid==3 else 'Mod')
    guild.fetch_member=fetch
    for uid in (2,4):
        await b.on_raw_reaction_add(NS(guild_id=1,channel_id=555,message_id=201,user_id=uid,emoji='✅'))
    for job in await db.query("SELECT * FROM jobs WHERE kind='reaction'"):
        job['payload']=json.loads(job['payload']);await b.service.job(job)
    assert (await db.account(1,3))['earned']==5
    assert await db.task_award(1,tid,{3:'Alice'},0,2,'snapshot')==1
    assert (await db.account(1,3))['earned']==10 # task participation is separate from server-wide reactions
