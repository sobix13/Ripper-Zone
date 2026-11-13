"""Readable receipt identities even without a Discord client's member cache."""
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,MagicMock
import discord
import pytest
from ripper_zone.service import Service


def missing():return discord.NotFound(NS(status=404,reason='Not Found'),'missing')


@pytest.fixture
async def receipt(db):
    await db.award(1,{3:'Saved Alice'},5,2,'Private detail','identity')
    row=(await db.query("SELECT * FROM jobs WHERE key LIKE 'notice:%'"))[0]
    job={**row,'payload':json.loads(row['payload'])}
    channel=NS(send=AsyncMock())
    guild=NS(id=1,get_member=MagicMock(return_value=None),fetch_member=AsyncMock(side_effect=missing()),get_channel_or_thread=lambda _:channel)
    bot=NS(db=db,get_guild=lambda _:guild,fetch_user=AsyncMock(side_effect=missing()))
    return Service(bot),guild,bot,channel,job


@pytest.mark.parametrize('source',['cache','member_api','user_api','saved','id'])
async def test_receipt_has_readable_clickable_identity_without_pings(receipt,source):
    service,guild,bot,channel,job=receipt
    person=NS(display_name='Current Alice')
    if source=='cache':guild.get_member.return_value=person
    elif source=='member_api':guild.fetch_member.side_effect=None;guild.fetch_member.return_value=person
    elif source=='user_api':bot.fetch_user.side_effect=None;bot.fetch_user.return_value=person
    elif source=='id':await bot.db.execute("UPDATE accounts SET name='' WHERE guild=1 AND user=3")
    await service.job(job)
    name='Current Alice' if source in ('cache','member_api','user_api') else 'Saved Alice' if source=='saved' else 'Member 3'
    assert channel.send.call_args.args[0]==f'[@{name}](https://discord.com/users/3) received 5 RC.'
    assert channel.send.call_args.kwargs['allowed_mentions'].to_dict()=={'parse':[]}
    assert channel.send.call_args.kwargs['suppress_embeds'] is True
    if source=='cache':guild.fetch_member.assert_not_awaited();bot.fetch_user.assert_not_awaited()
    assert (await bot.db.account(1,3))['earned']==5
    assert len(await bot.db.query('SELECT * FROM ledger'))==1


async def test_receipt_escapes_display_name_link_injection(receipt):
    service,guild,_,channel,job=receipt
    guild.get_member.return_value=NS(display_name='bad ](https://evil.example) @everyone **name**')
    await service.job(job)
    content=channel.send.call_args.args[0]
    assert '\\]\\(https://evil.example\\)' in content
    assert '@\u200beveryone' in content and '\\*\\*name\\*\\*' in content
    assert content.endswith('](https://discord.com/users/3) received 5 RC.')


async def test_pending_legacy_receipt_resolves_name_without_changing_accounting(receipt):
    service,guild,_,channel,job=receipt
    guild.get_member.return_value=NS(display_name='Alice')
    job['payload']['text']='RC record spin:1:3:day: <@!3> | available +5, reserved +0, earned +5.'
    await service.job(job)
    assert '[@Alice](https://discord.com/users/3)' in channel.send.call_args.args[0]
    assert 'available +5, reserved +0, earned +5.' in channel.send.call_args.args[0]


async def test_transient_identity_failure_retries_instead_of_posting_wrong_identity(receipt):
    service,guild,_,channel,job=receipt
    guild.fetch_member.side_effect=discord.HTTPException(NS(status=503,reason='Unavailable'),'retry')
    with pytest.raises(discord.HTTPException):await service.job(job)
    channel.send.assert_not_awaited()
    assert (await service.db.account(1,3))['earned']==5


async def test_non_ledger_notice_keeps_its_original_content(receipt):
    service,guild,_,channel,job=receipt
    job['key']='operator-note';job['payload']['text']='Original notice <@3>'
    await service.job(job)
    assert channel.send.call_args.args[0]=='Original notice <@3>'
    guild.get_member.assert_not_called()
