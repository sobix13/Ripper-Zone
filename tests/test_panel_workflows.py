"""Real SDK components with end-to-end private callbacks and isolated ledgers."""
import asyncio
import copy
import json
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,MagicMock
import discord
import pytest
from ripper_zone import ui,admin_ui as admin,member_ui
from ripper_zone.bot import RipperBot
from ripper_zone.config import digest,settings
from ripper_zone.copy import COPY,phrase
from ripper_zone.coordination import Registry
from ripper_zone.storage import Database,Conflict
from ripper_zone.sources import local_event
from test_discord_operations import fake_bot,interaction,payload,simulated_guild
from test_config_sources_release import rumble_db

@pytest.fixture
async def panel(db,tmp_path,monkeypatch):
    monkeypatch.setenv('DISCORD_GUILD_ID','1');monkeypatch.setenv('OWNER_IDS','2')
    b=RipperBot();b.db=db;b.service.db=db;b._connection.user=NS(id=99)
    guild,roles,channels,thread=simulated_guild()
    b.get_guild=lambda _:guild;b.authorize=AsyncMock();b.started=time.time();b.is_ready=lambda:True
    b.registry=Registry(tmp_path/'registry.sqlite3','bot:99');await b.registry.open()
    async def eligible(g,uid,role=0):return NS(id=uid,display_name='Alice',bot=False,roles=[])
    b.service.eligible=eligible
    def fresh(user=2):
        i=interaction(user);i.guild=guild;return i
    return b,guild,channels,thread,fresh


def shown(i):
    assert 'view' in i.followup.send.call_args.kwargs,i.followup.send.call_args
    s=i.followup.send.call_args.kwargs['view'];payload(s);return s


def button(s,label):return next(x for x in s.walk_children() if isinstance(x,discord.ui.Button) and x.label==label)
def select(s):return next(x for x in s.walk_children() if isinstance(x,(discord.ui.Select,discord.ui.UserSelect,discord.ui.RoleSelect,discord.ui.ChannelSelect)))

@pytest.mark.parametrize('name',['home','settings_page','channels','controls','reactions','messages','tiers','tasks','members','raffles','reports','history','health','snapshots','move_public'])
async def test_every_admin_section_real_sdk_payload(panel,name):
    b,_,_,_,fresh=panel;i=fresh()
    await getattr(admin,name)(b,i);s=shown(i)
    assert await s.interaction_check(i)
    assert not await s.interaction_check(fresh(4))

@pytest.mark.parametrize('page',['home','balance','spin','tasks','raffles','prizes','leaders','progress','history','activity','help'])
async def test_member_navigation_payload_and_no_commands(panel,page):
    b,_,_,_,fresh=panel
    cfg,rev=await b.db.config(1);cfg.update(roles_enabled=True,tiers=[dict(role=100+n,earned=n*100,tasks=0,events=0) for n in (1,2,3)])
    await b.db.save_config(1,cfg,rev,2)
    i=fresh(3);await ui.member_page(b,i,page);s=shown(i)
    text=' '.join(x.content for x in s.walk_children() if isinstance(x,discord.ui.TextDisplay))
    assert '/ripper' not in text

async def test_public_leaderboard_first_publish_repeat_and_persistent_controls(panel):
    b,g,channels,_,_=panel
    await b.refresh_leaderboard(g,publish=True)
    cfg,_=await b.db.config(1);assert cfg['leaderboard_message']==713
    assert not await b.db.query("SELECT 1 FROM meta_flags WHERE key='leaderboard_sending'")
    view=channels[13].send.call_args.kwargs['view'];assert view.is_persistent();payload(view)
    assert len([x for x in view.walk_children() if isinstance(x,discord.ui.Button)])==6
    msg=NS(author=NS(id=99),edit=AsyncMock());channels[13].fetch_message=AsyncMock(return_value=msg)
    await b.refresh_leaderboard(g,publish=True)
    assert channels[13].send.await_count==1 and msg.edit.await_count==1

async def test_rank_ties_pagination_and_mine(db):
    await db.award(1,{u:str(u) for u in range(3,26)},5,2,'tie','op')
    first=await db.leaderboard(1,25);third=await db.leaderboard(1,25,offset=20)
    assert first['total']==23 and len(first['rows'])==10 and len(third['rows'])==3
    assert first['mine']['rank']==1 and first['mine']['position']==23
    for x in first['rows']:assert x['rank']==(await db.account(1,x['user']))['rank']
    assert (await db.account(1,100))['rank'] is None
    assert len((await db.leaderboard(1,25,since=db.clock()+1))['rows'])==0

async def test_reaction_editor_and_stale_revision(panel):
    b,g,_,_,fresh=panel;i=fresh();await admin.reactions(b,i)
    s=shown(i);j=fresh();await button(s,'Add Quality Reaction').callback(j)
    modal=j.response.modal
    modal.inputs['emoji']._value='🔥';modal.inputs['amount']._value='8'
    k=fresh();await modal.on_submit(k)
    assert (await b.db.config(1))[0]['reactions']['🔥']['amount']==8
    # The old editor retains its opening revision and cannot overwrite new settings.
    old=fresh();await button(s,'Add Base Reaction').callback(old)
    old.response.modal.inputs['emoji']._value='⭐'
    k=fresh();await old.response.modal.on_submit(k)
    assert '⭐' not in (await b.db.config(1))[0]['reactions']
    assert 'changed' in k.followup.send.call_args.kwargs['content'].lower()

async def test_messages_preview_save_updates_rendering_and_queues_sync(panel):
    b,_,_,_,fresh=panel;i=fresh();await admin.messages(b,i);s=shown(i)
    item=select(s);item._values=['welcome_text'];j=fresh();await item.callback(j)
    j.response.modal.inputs['welcome_text']._value='Welcome to the new RC panel.'
    k=fresh();await j.response.modal.on_submit(k);preview=shown(k)
    n=fresh();await button(preview,'Confirm').callback(n)
    cfg,_=await b.db.config(1)
    assert cfg['welcome_text']=='Welcome to the new RC panel.'
    view=ui.gateway(b,cfg);payload(view)
    assert cfg['welcome_text'] in view.box.children[0].children[0].content
    assert await b.db.query("SELECT 1 FROM jobs WHERE kind='panel_refresh'")

@pytest.mark.parametrize('text',['{amount.__class__}','{amount[0]}','{amount!r}','{unknown}','{amount:10000}','{'])
def test_copy_rejects_expression_and_unknown_placeholders(text):
    cfg=settings();cfg['messages']['spin_result']=text
    with pytest.raises(ValueError):settings(cfg)

def test_copy_valid_placeholder():
    cfg=settings();cfg['messages']['spin_result']='Daily reward: {amount} RC'
    assert phrase(settings(cfg),'spin_result',amount=5)=='Daily reward: 5 RC'

async def test_task_edit_base_lock_and_stale_hash(db):
    tid=await db.create_task(1,2,'Old','Instructions',5,0,0)
    t=await db.task(1,tid);await db.edit_task(1,tid,{'title':'New','reward':8},2,digest(t))
    with pytest.raises(ValueError):await db.edit_task(1,tid,{'body':'stale'},2,digest(t))
    await db.accept_message(1,tid,3,999,db.clock()) # creating task does not accept a post
    await db.bind_task(1,tid,555);await db.accept_message(1,tid,3,999,db.clock())
    t=await db.task(1,tid)
    with pytest.raises(ValueError):await db.edit_task(1,tid,{'reward':10},2,digest(t))
    await db.edit_task(1,tid,{'body':'Updated instructions'},2,digest(t))

async def test_long_brief_sync_edits_same_message_and_handles_uncertain_send(panel):
    b,g,_,thread,_=panel;tid=await b.db.create_task(1,2,'A'*100,'X'*2000,5,0,0,int(time.time())+3600)
    await b.service.publish_task(g,tid);await b.service.sync_task(g,tid)
    view=thread.send.call_args.kwargs['view'];payload(view)
    text=view.box.children[0].children[0].content
    assert text.count('X')==2000 and 'Base reward: 5 RC' in text and 'Deadline:' in text
    msg=NS(id=900,author=NS(id=99),edit=AsyncMock());thread.fetch_message=AsyncMock(return_value=msg)
    await b.service.sync_task(g,tid)
    assert thread.send.await_count==1 and msg.edit.await_count==1
    # A send timeout with no definite message cannot automatically send another brief.
    await b.db.execute("INSERT OR REPLACE INTO meta_flags VALUES(?,?)",(f'task_brief:{tid}',json.dumps({'state':'sending'})))
    with pytest.raises(ValueError,match='uncertain'):await b.service.sync_task(g,tid)
    assert thread.send.await_count==1

async def test_task_publication_claim_serializes_race(panel):
    b,g,channels,_,_=panel;tid=await b.db.create_task(1,2,'Race','Instructions',5,0,0)
    results=await asyncio.gather(b.service.publish_task(g,tid),b.service.publish_task(g,tid),return_exceptions=True)
    assert channels[12].create_thread.await_count==1
    assert sum(isinstance(x,ValueError) for x in results)==1

async def test_quality_replay_after_rule_change_does_not_top_up(db):
    tid=await db.create_task(1,2,'Task','Instructions',5,0,0)
    assert await db.task_award(1,tid,{3:'Alice'},0,2,'reaction:1:medal','quality',5)==1
    assert await db.task_award(1,tid,{3:'Alice'},0,2,'reaction:1:medal','quality',10)==0
    assert await db.task_award(1,tid,{3:'Alice'},0,2,'reaction:2:medal','quality',10)==1
    assert (await db.account(1,3))['earned']==15

async def test_reaction_timeout_is_durable_and_retry_pays_once(panel):
    b,g,_,thread,_=panel;tid=await b.db.create_task(1,2,'Task','Instructions',5,0,0);await b.db.bind_task(1,tid,555)
    await b.db.accept_message(1,tid,3,201,b.db.clock())
    event=NS(guild_id=1,channel_id=555,message_id=201,user_id=2,emoji='✅')
    await b.on_raw_reaction_add(event)
    row=(await b.db.query("SELECT * FROM jobs WHERE kind='reaction'"))[0];row['payload']=json.loads(row['payload'])
    thread.fetch_message=AsyncMock(side_effect=asyncio.TimeoutError())
    with pytest.raises(asyncio.TimeoutError):await b.service.job(row)
    assert (await b.db.account(1,3))['earned']==0
    thread.fetch_message.side_effect=None;thread.fetch_message.return_value=NS(id=201,author=NS(id=3,bot=False))
    await b.service.job(row);await b.service.job(row)
    assert (await b.db.account(1,3))['earned']==5

async def test_new_task_and_member_detail_flow(panel):
    b,g,_,_,fresh=panel;i=fresh();await ui.task_form(b,i)
    j=fresh();await button(shown(i),'Daily').callback(j)
    values={'title':'Photo Task','body':'Post a collection photo.','reward':'5','cooldown':'60','hours':'72'}
    for key,value in values.items():j.response.modal.inputs[key]._value=value
    k=fresh();await j.response.modal.on_submit(k);shown(k)
    tid=(await b.db.query('SELECT id FROM tasks'))[0]['id']
    member=fresh(3);await member_ui.page_view(b,member,'task',selected=tid);s=shown(member)
    assert any(isinstance(x,discord.ui.Button) and x.url for x in s.walk_children())

async def test_raft_draft_edit_freeze_and_no_rule_changes_after_publication(panel):
    b,_,_,_,_=panel;spec=dict(title='Prize',prize='Collector car',price=5,max_tickets=10,winners=1,minimum=1,ends=int(time.time())+3600)
    rid=await b.db.create_raffle(1,2,spec);await b.db.edit_raffle(1,rid,{**spec,'price':8},2,digest(spec))
    await b.db.begin_publish(1,rid,2,14)
    with pytest.raises(ValueError):await b.db.edit_raffle(1,rid,spec,2,digest({**spec,'price':8}))

async def test_settings_channel_move_keeps_bindings_consistent(panel):
    b,g,channels,_,_=panel
    cfg,rev=await b.db.config(1);cfg.update(panel_message=711,panel_state='active');await b.db.save_config(1,cfg,rev,2)
    cfg,rev=await b.db.config(1)
    with pytest.raises(ValueError,match='Move'):await b.service.configure(g,{**cfg,'panel_channel':12},rev,2)
    await b.service.move_public(g,'panel',12,2,rev)
    new,_=await b.db.config(1);assert new['panel_channel']==12 and new['panel_message']==712 and new['panel_state']=='active'
    redirect=(await b.db.query("SELECT * FROM jobs WHERE kind='redirect'"))[0]
    old=NS(author=NS(id=99),edit=AsyncMock());channels[11].fetch_message=AsyncMock(return_value=old)
    redirect['payload']=json.loads(redirect['payload']);await b.service.job(redirect)
    assert old.edit.await_count==1
    assert not await b.db.query("SELECT 1 FROM meta_flags WHERE key='move:1:panel'")

async def test_no_file_event_picker_and_confirmation(panel,monkeypatch):
    b,_,_,_,fresh=panel
    from ripper_zone.config import digest
    data=dict(version=1,source='rumble',guild=1,event='10',participants=[3,4]);data['hash']=digest(data)
    async def source(source,event=None):return [{'id':10}] if event is None else data
    monkeypatch.setattr(admin,'source_request',source)
    i=fresh();await admin.event_list(b,i,'rumble');view=shown(i);item=select(view);item._values=['10']
    j=fresh();await item.callback(j);assert j.response.modal
    j.response.modal.inputs['amount']._value='5';k=fresh();await j.response.modal.on_submit(k)
    view=shown(k);await button(view,'Confirm').callback(fresh());await button(view,'Confirm').callback(fresh())
    assert (await b.db.account(1,3))['earned']==5 and (await b.db.account(1,4))['earned']==5
    assert len(await b.db.query('SELECT * FROM snapshots'))==1


def test_readonly_local_event_whitelist_and_custom_path(tmp_path,monkeypatch):
    path=tmp_path/'rumble.sqlite3';rumble_db(path);before=path.read_bytes()
    monkeypatch.setenv('RUMBLE_DATABASE_PATH',str(path))
    assert local_event('rumble',1)==[{'id':10}]
    assert local_event('rumble',1,10)['participants']==[3,4,5]
    assert path.read_bytes()==before
    with pytest.raises(ValueError):local_event('../../etc/passwd',1)
    with pytest.raises(ValueError):local_event('rumble',2,10)

async def test_native_member_award_confirm_replay(panel):
    b,_,_,_,fresh=panel;i=fresh();await admin.award_members(b,i)
    sel=select(shown(i));sel._values=[NS(id=3),NS(id=4)]
    j=fresh();await sel.callback(j);j.response.modal.inputs['amount']._value='8';j.response.modal.inputs['reason']._value='Helpful collectors'
    k=fresh();await j.response.modal.on_submit(k);view=shown(k)
    await button(view,'Confirm').callback(fresh());await button(view,'Confirm').callback(fresh())
    assert (await b.db.account(1,3))['earned']==8 and (await b.db.account(1,4))['earned']==8
    assert len(await b.db.query("SELECT * FROM ledger WHERE source='manual'"))==2

async def test_native_three_role_wizard_disabled_then_enable(panel):
    b,_,_,_,fresh=panel;i=fresh();await admin.tiers(b,i);view=shown(i)
    for n in (1,2,3):
        item=select(view);item._values=[NS(id=100+n)];j=fresh();await item.callback(j)
        for key,value in [('earned',str(n*100)),('tasks','0'),('events','0')]:j.response.modal.inputs[key]._value=value
        k=fresh();await j.response.modal.on_submit(k);view=shown(k)
    await button(view,'Save Disabled').callback(fresh())
    cfg,_=await b.db.config(1);assert len(cfg['tiers'])==3 and not cfg['roles_enabled']
    i=fresh();await admin.controls(b,i);view=shown(i)
    await button(view,'Achievement Roles: OFF').callback(fresh())
    assert (await b.db.config(1))[0]['roles_enabled']

async def test_native_raffle_creation_publish_and_member_access(panel):
    b,g,channels,_,fresh=panel;i=fresh();await admin.raffle_create(b,i)
    i.response.modal.inputs['title']._value='Collector Prize';i.response.modal.inputs['body']._value='One collector model.'
    j=fresh();await i.response.modal.on_submit(j);view=shown(j)
    k=fresh();await button(view,'Set Ticket Rules').callback(k)
    for key,value in [('price','5'),('max_tickets','10'),('winners','1'),('minimum','1'),('hours','24')]:k.response.modal.inputs[key]._value=value
    n=fresh();await k.response.modal.on_submit(n);view=shown(n)
    p=fresh();await button(view,'Publish Public Raffle').callback(p);preview=shown(p)
    await button(preview,'Confirm').callback(fresh())
    r=(await b.db.query('SELECT * FROM raffles'))[0];assert r['status']=='open' and r['message']==714
    member=fresh(3);await member_ui.page_view(b,member,'raffle',selected=r['id']);shown(member)

async def test_channel_move_send_timeout_requires_recovery(panel):
    b,g,channels,_,_=panel;cfg,rev=await b.db.config(1);cfg.update(panel_message=711,panel_state='active');await b.db.save_config(1,cfg,rev,2)
    _,rev=await b.db.config(1);channels[12].send.side_effect=asyncio.TimeoutError()
    with pytest.raises(asyncio.TimeoutError):await b.service.move_public(g,'panel',12,2,rev)
    cfg,rev=await b.db.config(1);assert cfg['panel_channel']==12 and cfg['panel_state']=='sending' and not cfg['panel_message']
    with pytest.raises(ValueError):await b.service.move_public(g,'panel',12,2,rev)
    assert channels[12].send.await_count==1

async def test_manual_close_always_has_durable_archival_job(db):
    tid=await db.create_task(1,2,'Task','Brief',5,0,0);await db.bind_task(1,tid,555)
    await db.close_task(1,tid,2)
    assert (await db.task(1,tid))['status']=='closed'
    assert await db.query("SELECT * FROM jobs WHERE kind='taskclose' AND state='pending'")

async def test_emoji_aliases_and_base_amount_are_rejected():
    cfg=settings();cfg['reactions']['✅️']={'kind':'base','amount':0}
    with pytest.raises(ValueError):settings(cfg)
    cfg=settings();cfg['reactions']['✅']['amount']=5
    with pytest.raises(ValueError):settings(cfg)

async def test_reaction_inbox_preserves_original_rule(panel):
    b,_,_,_,_=panel;tid=await b.db.create_task(1,2,'Task','Brief',5,0,0);await b.db.bind_task(1,tid,555)
    event=NS(guild_id=1,channel_id=555,message_id=201,user_id=2,emoji='🏅')
    await b.on_raw_reaction_add(event)
    cfg,rev=await b.db.config(1);cfg['reactions']['🏅']['amount']=10;await b.db.save_config(1,cfg,rev,2)
    await b.on_raw_reaction_add(event)
    saved=json.loads((await b.db.query("SELECT payload FROM jobs WHERE kind='reaction'"))[0]['payload'])
    assert saved['rule']['amount']==5

@pytest.mark.parametrize('now,period,expected',[(1794527999,'today',1794441600),(1794528001,'today',1794528000)])
def test_utc_period_boundary(now,period,expected):
    assert member_ui.period_start(period,now)==expected

async def test_authenticated_helper_event_endpoint(tmp_path,monkeypatch):
    from aiohttp import web
    from ripper_zone.operations import Recovery
    path=tmp_path/'rumble.sqlite3';rumble_db(path)
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'zone.sqlite3'));monkeypatch.setenv('DISCORD_GUILD_ID','1')
    monkeypatch.setenv('HEALTH_SECRET','s'*48);monkeypatch.setenv('OWNER_IDS','2');monkeypatch.setenv('RUMBLE_DATABASE_PATH',str(path))
    helper=Recovery()
    request=NS(headers={},query={'source':'rumble'})
    with pytest.raises(web.HTTPUnauthorized):await helper.source_response(request)
    request.headers={'Authorization':'Bearer '+'s'*48}
    response=await helper.source_response(request);assert response.status==200 and json.loads(response.body)==[{'id':10}]
    request.query={'source':'rumble','event':'10'}
    response=await helper.source_response(request);assert json.loads(response.body)['participants']==[3,4,5]
    request.query={'source':'../../etc/passwd'}
    assert (await helper.source_response(request)).status==400

async def test_nested_secret_and_wal_are_rejected(tmp_path):
    import importlib.util
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('release_check',root/'scripts/release.py');release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
    (tmp_path/'assets').mkdir()
    for name in ('.env','private.sqlite3-wal','private.sqlite3-shm','token.pem'):
        p=tmp_path/'assets'/name;p.write_text('non-sensitive test fixture')
        with pytest.raises(ValueError):release.files(tmp_path)
        p.unlink()

async def test_form_permission_revoked_before_message_save(panel):
    b,_,_,_,fresh=panel;i=fresh();await admin.messages(b,i);item=select(shown(i));item._values=['about_text']
    j=fresh();await item.callback(j);j.response.modal.inputs['about_text']._value='Unauthorized change'
    b.authorize=AsyncMock(side_effect=ValueError('Primary access revoked'))
    k=fresh();await j.response.modal.on_submit(k)
    assert (await b.db.config(1))[0]['about_text']!='Unauthorized change'
    assert 'revoked' in k.followup.send.call_args.kwargs['content']

async def test_extended_settings_keep_v1_row_readable_after_upgrade(db):
    from ripper_zone.config import LEGACY_KEYS
    cfg,rev=await db.config(1);cfg['welcome_text']='New welcome';cfg['messages']['spin_result']='Daily RC: {amount}'
    await db.save_config(1,cfg,rev,2)
    raw=json.loads((await db.query('SELECT data FROM settings WHERE guild=1'))[0]['data'])
    assert set(raw)==LEGACY_KEYS and 'welcome_text' not in raw
    # A previous-release operator changes its legacy row; new copy remains available.
    raw['spin_enabled']=False;await db.execute('UPDATE settings SET data=? WHERE guild=1',(json.dumps(raw),))
    current,_=await db.config(1)
    assert not current['spin_enabled'] and current['welcome_text']=='New welcome'
    assert current['messages']['spin_result']=='Daily RC: {amount}'

async def test_log_channel_rejects_another_public_role_allow(panel):
    b,g,channels,_,_=panel
    role=MagicMock(spec=discord.Role);role.id=1234;role.permissions.administrator=False
    role.tags=None;channels[15].overwrites={role:discord.PermissionOverwrite(view_channel=True)}
    cfg,_=await b.db.config(1)
    with pytest.raises(ValueError,match='unapproved'):await b.service.validate_config(g,cfg)

async def test_member_correction_from_native_picker(panel):
    b,_,_,_,fresh=panel;await b.db.award(1,{3:'Alice'},10,2,'Fund','op')
    i=fresh();await admin.member_account(b,i,3);view=shown(i)
    j=fresh();await button(view,'Correction').callback(j)
    j.response.modal.inputs['amount']._value='-3';j.response.modal.inputs['reason']._value='Correct invalid extra credit'
    k=fresh();await j.response.modal.on_submit(k);view=shown(k)
    await button(view,'Record Correction').callback(fresh())
    assert (await b.db.account(1,3))['earned']==7

async def test_channel_snapshot_resolves_native_channel_object(panel):
    b,_,_,thread,fresh=panel
    async def history(**kwargs):
        yield NS(author=NS(id=3,display_name='Alice',bot=False))
        yield NS(author=NS(id=3,display_name='Alice',bot=False))
        yield NS(author=NS(id=99,display_name='Bot',bot=True))
    thread.history=history
    i=fresh();await admin.window_snapshot(b,i);item=select(shown(i));item._values=[NS(id=555)]
    j=fresh();await item.callback(j)
    for k,v in [('hours','24'),('amount','5'),('reason','Useful participation')]:j.response.modal.inputs[k]._value=v
    k=fresh();await j.response.modal.on_submit(k);view=shown(k)
    await button(view,'Confirm').callback(fresh())
    assert (await b.db.account(1,3))['earned']==5 and (await b.db.account(1,99))['earned']==0

async def test_history_preserves_new_copy_and_old_row_shape(db):
    from ripper_zone.config import LEGACY_KEYS
    cfg,rev=await db.config(1);cfg['about_text']='Version A';await db.save_config(1,cfg,rev,2)
    cfg,rev=await db.config(1);cfg['about_text']='Version B';await db.save_config(1,cfg,rev,2)
    rows=await db.config_history(1)
    assert json.loads(rows[0]['data'])['about_text']=='Version A'
    raw=await db.query('SELECT data FROM settings_history ORDER BY id DESC LIMIT 1')
    assert set(json.loads(raw[0]['data']))==LEGACY_KEYS
