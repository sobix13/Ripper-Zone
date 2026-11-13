"""Server-wide reactions, public receipt isolation and frozen live call snapshots."""
import asyncio
from pathlib import Path
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,MagicMock
import discord
import pytest
from ripper_zone import admin_ui as admin,ui
from ripper_zone.config import settings,digest
from test_panel_workflows import panel,shown,button,select
from test_notice_identity import receipt


@pytest.mark.parametrize('thread,starter',[(False,False),(True,False),(True,True)])
async def test_authorized_reaction_works_without_a_task_and_never_pays_twice(panel,thread,starter):
    b,g,channels,t,_=panel;b.owners.add(4)
    channel=t if thread else channels[11];channel.guild=g
    mid=channel.id if starter else 201
    channel.fetch_message=AsyncMock(return_value=NS(id=mid,author=NS(id=3,bot=False)))
    async def member(g,uid,role=0):return NS(id=uid,display_name=f'Member {uid}',roles=[],bot=False)
    b.service.eligible=member
    for actor in (2,4,2):
        await b.on_raw_reaction_add(NS(guild_id=1,channel_id=channel.id,message_id=mid,user_id=actor,emoji='✅'))
    jobs=await b.db.query("SELECT * FROM jobs WHERE kind='reaction'")
    await asyncio.gather(*(b.service.job({**r,'payload':json.loads(r['payload'])}) for r in jobs))
    assert (await b.db.account(1,3))['earned']==5
    cfg,rev=await b.db.config(1);cfg['reactions']['✅']['amount']=50;await b.db.save_config(1,cfg,rev,2)
    assert not await b.db.reaction_award(1,3,'Member 3',4,mid,'✅',50)
    assert await b.db.reaction_award(1,3,'Member 3',2,mid,'💜',8)
    assert (await b.db.account(1,3))['earned']==13
    notices=[json.loads(r['payload'])['text'] for r in await b.db.query("SELECT payload FROM jobs WHERE kind='notice'")]
    assert any('for receiving 💜' in s for s in notices)
    assert len(notices)==2


async def test_regular_members_bots_and_self_reactions_never_pay(panel):
    b,g,channels,_,_=panel;channel=channels[11];channel.guild=g
    channel.fetch_message=AsyncMock(return_value=NS(id=201,author=NS(id=3,bot=False)))
    async def member(g,uid,role=0):return NS(id=uid,roles=[],display_name='Alice',bot=False)
    b.service.eligible=member
    await b.process_reaction(NS(guild_id=1,channel_id=11,message_id=201,user_id=5,emoji='✅'),{'kind':'fixed','amount':5})
    channel.fetch_message.assert_not_awaited()
    with pytest.raises(ValueError):await b.db.reaction_award(1,3,'Alice',3,201,'✅',5)
    channel.fetch_message.return_value.author.bot=True
    await b.process_reaction(NS(guild_id=1,channel_id=11,message_id=201,user_id=2,emoji='✅'),{'kind':'fixed','amount':5})
    assert not await b.db.query('SELECT * FROM ledger')


async def test_more_than_five_emojis_paginates_and_roundtrips_settings(panel):
    b,g,channels,_,fresh=panel
    cfg,rev=await b.db.config(1);cfg['reactions']={chr(0x1f600+n):{'kind':'fixed','amount':n+1} for n in range(50)}
    await b.db.save_config(1,cfg,rev,2)
    restored,_=await b.db.config(1);assert restored['reactions']==cfg['reactions']
    i=fresh();await admin.reactions(b,i);view=shown(i)
    assert len(select(view).options)==20
    j=fresh();await button(view,'Next').callback(j);assert len(select(shown(j)).options)==20
    cfg['reactions']={f'custom:{n+100}':{'kind':'fixed','amount':5} for n in range(100)}
    assert len(settings(cfg)['reactions'])==100
    cfg['reactions']['custom:999']={'kind':'fixed','amount':5}
    with pytest.raises(ValueError):settings(cfg)


async def test_public_rc_channel_and_private_operations_channel_are_distinct(panel):
    b,g,channels,_,_=panel;cfg,_=await b.db.config(1)
    channels[15].permissions_for.side_effect=None;channels[15].permissions_for.return_value=NS(**{k:True for k in ('view_channel','send_messages','read_message_history','attach_files','embed_links')})
    await b.service.validate_config(g,cfg)
    cfg['audit_channel']=15
    with pytest.raises(ValueError,match='separate'):await b.service.validate_config(g,cfg)
    cfg['log_channel']=14
    with pytest.raises(ValueError,match='Hide'):await b.service.validate_config(g,cfg)


async def test_public_receipt_retry_uses_current_channel_without_repaying(receipt):
    service,guild,bot,channel,job=receipt
    first=discord.HTTPException(NS(status=503,reason='Unavailable'),'retry')
    channel.send.side_effect=first
    with pytest.raises(discord.HTTPException):await service.job(job)
    channel.send.side_effect=None
    cfg,rev=await bot.db.config(1);cfg['log_channel']=42;await bot.db.save_config(1,cfg,rev,2)
    guild.get_channel_or_thread=MagicMock(return_value=channel)
    await service.job(job)
    guild.get_channel_or_thread.assert_called_with(42)
    assert len(await bot.db.query('SELECT * FROM ledger'))==1
    assert 'Private detail' not in channel.send.call_args.args[0]


async def test_pending_technical_ledger_notice_never_leaks_to_public_channel(receipt):
    service,guild,bot,channel,job=receipt
    await bot.db.adjust(1,3,1,2,'Private operator detail','correction')
    job['key']='notice:adjust:1:correction';job['payload']['text']='Private internal record <@3>'
    await service.job(job);channel.send.assert_not_awaited()


async def test_source_specific_receipts(db):
    await db.spin(1,3,'Alice',100)
    await db.snapshot(1,'rumble','123',[4],8,2)
    await db.snapshot(1,'raffle','124',[5],9,2)
    text='\n'.join(json.loads(r['payload'])['text'] for r in await db.query("SELECT payload FROM jobs WHERE kind='notice'"))
    assert 'from the daily spin.' in text and 'Rumble #123 snapshot.' in text and 'raffle #124 snapshot.' in text


async def test_voice_snapshot_command_context_freezes_present_members_and_confirms_once(panel):
    b,g,channels,_,fresh=panel
    voice=MagicMock(spec=discord.VoiceChannel);voice.id=25;voice.guild=g;voice.voice_states={2:NS(),3:NS(),99:NS()};voice.permissions_for.return_value=NS(view_channel=True)
    async def member(g,uid,role=0):return None if uid==99 else NS(id=uid,display_name=f'Member {uid}',bot=False,roles=[])
    b.service.eligible=member
    i=fresh();i.channel=voice
    await admin.voice_snapshot(b,i,amount=10);view=shown(i)
    voice.voice_states.clear();voice.voice_states[4]=NS() # this later join is not part of the captured roster
    j=fresh();await button(view,'Confirm Voice Rewards').callback(j)
    assert (await b.db.account(1,2))['earned']==10 and (await b.db.account(1,3))['earned']==10
    assert (await b.db.account(1,4))['earned']==0 and (await b.db.account(1,99))['earned']==0
    await button(view,'Confirm Voice Rewards').callback(fresh())
    assert len(await b.db.query("SELECT * FROM ledger WHERE source='voice'"))==2
    assert (await b.db.account(1,3))['events']==1
    notice=json.loads((await b.db.query("SELECT payload FROM jobs WHERE key LIKE 'notice:voice:%'"))[0]['payload'])['text']
    assert 'voice snapshot #' in notice and '<#25>' in notice


async def test_voice_amount_edits_reject_stale_confirmation_and_survive_reopen(db):
    capture=await db.voice_capture(1,25,100,2,{3:'Alice',4:'Bob'},5)
    changed=await db.update_voice_capture(1,100,2,digest(capture),12)
    with pytest.raises(ValueError):await db.update_voice_capture(1,100,2,digest(capture))
    results=await asyncio.gather(*(db.update_voice_capture(1,100,2,digest(changed)) for _ in range(2)))
    assert sorted(results)==[0,2] and (await db.account(1,3))['earned']==12
    row=(await db.query("SELECT value FROM meta_flags WHERE key='voice_capture:1:100'"))[0]
    assert json.loads(row['value'])['paid'] is True
    with pytest.raises(ValueError):await db.update_voice_capture(1,100,4,digest(changed))
    assert await db.revoke(1,(await db.query("SELECT id FROM ledger WHERE user=3"))[0]['id'],2,'Review')
    assert (await db.account(1,3))['events']==0


async def test_snapshot_command_supports_voice_without_upload(panel):
    b,g,_,_,fresh=panel
    i=fresh();i.channel=NS()
    await b.tree.get_command('ripper').get_command('snapshot').callback(i,amount=5)
    assert any(isinstance(c,discord.ui.ChannelSelect) for c in shown(i).walk_children())


async def test_migrated_base_and_quality_rewards_do_not_top_up_old_messages(db):
    tid=await db.create_task(1,2,'Legacy task','Read',5,0,0);await db.bind_task(1,tid,555)
    await db.accept_message(1,tid,3,201,db.clock())
    await db.task_award(1,tid,{3:'Alice'},0,2,'reaction:201:✅')
    payload=dict(message_id=201,user_id=2,emoji='✅',rule={'kind':'base','amount':0})
    await db.execute("INSERT INTO jobs(key,kind,guild,payload,state) VALUES('old-base','reaction',1,?,'done')",(json.dumps(payload),))
    assert not await db.reaction_award(1,3,'Alice',4,201,'✅',8)
    await db.task_award(1,tid,{3:'Alice'},0,2,'reaction:201:💜','quality',10)
    assert not await db.reaction_award(1,3,'Alice',4,201,'💜',20)
    assert (await db.account(1,3))['earned']==15


async def test_legacy_base_config_migration_and_rollback_readable_row(db):
    cfg,rev=await db.config(1);cfg['reactions']={'✅':{'kind':'base','amount':0},'💜':{'kind':'quality','amount':8}}
    await db.save_config(1,cfg,rev,2);current,rev=await db.config(1)
    assert current['reactions']=={'✅':{'kind':'fixed','amount':5},'💜':{'kind':'fixed','amount':8}}
    raw=json.loads((await db.query('SELECT data FROM settings WHERE guild=1'))[0]['data'])
    extra=json.loads((await db.query("SELECT value FROM meta_flags WHERE key='settings_extra:1'"))[0]['value'])
    assert 'audit_channel' not in raw and 'audit_channel' not in extra
    assert len(raw['reactions'])<=5 and all(r['kind']=='quality' for r in raw['reactions'].values())


async def test_recovery_reads_private_operations_extension_and_never_public_rc(db):
    from ripper_zone.operations import Recovery
    cfg,rev=await db.config(1);cfg['audit_channel']=16;await db.save_config(1,cfg,rev,2)
    helper=object.__new__(Recovery);helper.database=Path(db.path);helper.guild=1
    cfg=helper.config()
    assert cfg['audit_channel']==16 and cfg['log_channel']==15


async def test_non_moderator_reactions_do_not_flood_the_background_queue(panel):
    b,_,_,_,_=panel
    await b.on_raw_reaction_add(NS(guild_id=1,channel_id=11,message_id=201,user_id=5,emoji='✅',member=NS(id=5,bot=False,roles=[])))
    assert not await b.db.query("SELECT * FROM jobs WHERE kind='reaction'")


async def test_recovery_refuses_public_rc_destination(monkeypatch):
    from ripper_zone.operations import Recovery
    helper=object.__new__(Recovery);helper.config=lambda:{'log_channel':15,'audit_channel':0};helper.api=AsyncMock()
    monkeypatch.setenv('RECOVERY_CHANNEL_ID','15')
    with pytest.raises(ValueError,match='separate private'):await helper.pulse()
    helper.api.assert_not_awaited()
