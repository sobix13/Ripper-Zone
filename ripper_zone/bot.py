"""Ripper Zone application. One guild, one token and one private ledger."""
import asyncio
import csv
import fcntl
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Literal, Optional
import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv
from . import __version__, sources
from .config import canonical,digest,ident, integer, settings, emoji_key
from .coordination import Registry
from .features import cycle
from .copy import phrase
from .storage import Database
from .service import Service
from . import ui

log=logging.getLogger(__name__)


class RipperBot(discord.Client):
    def __init__(self):
        intents=discord.Intents.default()
        intents.members=True;intents.message_content=True
        super().__init__(intents=intents,allowed_mentions=ui.MENTIONS)
        self.guild_id=ident(os.environ['DISCORD_GUILD_ID'])
        self.owners={ident(x.strip()) for x in os.environ.get('OWNER_IDS','').split(',') if x.strip()}
        self.db=Database(os.environ.get('DATABASE_PATH','data/ripper-zone.sqlite3'))
        self.tree=app_commands.CommandTree(self)
        self.tree.on_error=self.command_error
        self.registry=None;self.worker=None;self.health_server=None
        self.service=Service(self);self.started=time.time();self.last_error=''
        commands(self)

    def report_error(self,exc):
        if isinstance(exc,ValueError):return
        self.last_error=type(exc).__name__
        log.error("Operation failed: %s",type(exc).__name__,exc_info=(type(exc),exc,exc.__traceback__))

    async def command_error(self,i,error):
        error=getattr(error,'original',error)
        self.report_error(error)
        await ui.failure(i,error)

    async def setup_hook(self):
        await self.db.open()
        await self.db.reconcile(self.guild_id)
        path=os.environ.get('COORDINATION_DB',str(Path(self.db.path).parent/'coordination.sqlite3'))
        self.registry=Registry(path,f"bot:{self.application_id}")
        await self.registry.open()
        self.add_view(ui.gateway(self))
        self.add_view(ui.public_leaderboard(self,[]))
        rows=await self.db.query("SELECT id FROM raffles WHERE guild=? AND message IS NOT NULL",(self.guild_id,))
        for row in rows:self.add_view(ui.raffle_view(self,await self.db.raffle(self.guild_id,row['id'])))
        guild=discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        from .operations import start_health
        self.health_server=await start_health(self)
        self.worker=asyncio.create_task(self.service.loop(),name='zone-worker')

    async def close(self):
        self.service.running=False
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker,return_exceptions=True)
        if self.health_server:await self.health_server.cleanup()
        await super().close()

    async def on_ready(self):
        log.info("Ripper Zone %s connected as %s; configured guild %s",__version__,self.user.id,self.guild_id)
        if not self.get_guild(self.guild_id):log.error("Configured server is unavailable. Invite this application to the server.")

    async def member_access(self,i,active=False):
        if not i.guild or i.guild_id!=self.guild_id:raise ValueError("Use Ripper Zone in its configured server.")
        cfg,_=await self.db.config(i.guild_id)
        member=await self.service.eligible(i.guild,i.user.id,cfg['member_role'])
        if member is None:raise ValueError("Complete server verification and obtain the community access role first.")
        if active and not cfg['active']:raise ValueError("The community program is paused.")
        return member,cfg

    async def authorize(self,i,primary=False):
        if not i.guild or i.guild_id!=self.guild_id:raise ValueError("Use administration in the configured server.")
        member=await self.service.eligible(i.guild,i.user.id)
        if member is None:raise ValueError("Only server members may administer Ripper Zone.")
        cfg,_=await self.db.config(i.guild_id)
        principal=i.user.id in (self.owners|{i.guild.owner_id}|set(cfg['primary_users']))
        moderator=bool(set(cfg['manager_roles'])&{r.id for r in member.roles})
        if not principal and (primary or not moderator):raise ValueError("This action requires a primary administrator." if primary else "This action requires a configured moderator.")
        return member

    async def publish_panel_action(self,i):
        await ui.defer(i);await self.authorize(i,primary=True)
        cfg,rev=await self.db.config(i.guild_id)
        await self.service.validate_config(i.guild,cfg)
        channel=i.guild.get_channel(cfg['panel_channel'])
        if not channel:raise ValueError("Select the member-panel channel first.")
        if cfg['panel_message']:
            message=await channel.fetch_message(cfg['panel_message'])
            if message.author.id!=self.user.id:raise ValueError("Saved message belongs to another application.")
            screen=ui.gateway(self,cfg)
            await message.edit(view=screen,attachments=screen.files(),allowed_mentions=ui.MENTIONS)
            await ui.reply(i,content=f"Member panel refreshed: {message.jump_url}");return
        if cfg['panel_state'] not in ('new','missing'):raise ValueError("A previous send requires review. Use /ripper panel_recover with its message ID.")
        cfg['panel_state']='sending';await self.db.save_config(i.guild_id,cfg,rev,i.user.id)
        screen=ui.gateway(self,cfg)
        message=await channel.send(view=screen,files=screen.files(),allowed_mentions=ui.MENTIONS)
        # Save the returned ID even if another administrator edited settings meanwhile.
        def bind(c):
            current,v=self.db._config(c,i.guild_id)
            current.update(panel_message=message.id,panel_state='active')
            self.db._put_config(c,i.guild_id,current,v+1)
        await self.db.run(bind)
        await self.registry.record(i.guild_id,message.id,'message','panel:'+str(message.id))
        await ui.reply(i,content=f"Member panel published: {message.jump_url}")

    async def refresh_leaderboard(self,guild,publish=False):
        cfg,revision=await self.db.config(guild.id)
        if not cfg['leaderboard_channel']:return
        channel=guild.get_channel(cfg['leaderboard_channel'])
        rows=await self.db.leaders(guild.id)
        text='\n'.join(f"{n}. <@{r['user']}> · **{r['earned']} RC**" for n,r in enumerate(rows,1)) or "Be the first to earn Ripper Credits."
        screen=ui.public_leaderboard(self,rows,cfg)
        if cfg['leaderboard_message']:
            msg=await channel.fetch_message(cfg['leaderboard_message'])
            if msg.author.id!=self.user.id:raise ValueError("Leaderboard message belongs to another application.")
            await msg.edit(view=screen,allowed_mentions=ui.MENTIONS)
        elif publish:
            # Financially harmless; ambiguity still requires manual binding.
            await self.db.execute("INSERT OR IGNORE INTO meta_flags VALUES('leaderboard_sending','1')")
            msg=await channel.send(view=screen,allowed_mentions=ui.MENTIONS)
            cfg['leaderboard_message']=msg.id;await self.db.save_config(guild.id,cfg,revision,0)
            await self.db.execute("DELETE FROM meta_flags WHERE key='leaderboard_sending'")
            await self.registry.record(guild.id,msg.id,'message','leaderboard:'+str(msg.id))

    async def doctor_action(self,i):
        await ui.defer(i);await self.authorize(i)
        from .operations import doctor
        data=await doctor(self)
        await ui.reply(i,content="Ripper Zone health report",file=discord.File(io.BytesIO(json.dumps(data,indent=2).encode()),filename='ripper-zone-health.json'))

    async def on_message(self,message):
        if message.author.bot or not message.guild or message.guild.id!=self.guild_id:return
        try:
            cfg,_=await self.db.config(message.guild.id)
            if message.channel.id==cfg['tasks_channel']:
                member=await self.service.eligible(message.guild,message.author.id)
                if member and (member.id in self.owners|set(cfg['primary_users'])|{message.guild.owner_id} or set(cfg['manager_roles'])&{r.id for r in member.roles}):return
                await message.delete()
                await message.channel.send('Please post inside the matching community task thread. Open Community Tasks in your panel.',delete_after=10,allowed_mentions=ui.MENTIONS)
                return
            if not isinstance(message.channel,discord.Thread):return
            task=await self.db.task_for_thread(message.guild.id,message.channel.id)
            if not task:return
            cfg,_=await self.db.config(message.guild.id)
            # Fetch fresh roles for cooldown bypass, not cached member privileges.
            member=await self.service.eligible(message.guild,message.author.id,cfg['member_role'])
            if member is None:return
            bypass=member.id in self.owners|set(cfg['primary_users'])|{message.guild.owner_id} or bool(set(cfg['manager_roles'])&{r.id for r in member.roles})
            at=int(message.created_at.timestamp())
            remaining=await self.db.accept_message(message.guild.id,task['id'],member.id,message.id,at,bypass)
            if remaining==0:
                try:await member.send(phrase(cfg,'task_received'))
                except discord.Forbidden:pass
            if remaining>0:
                await message.delete()
                try:await member.send(phrase(cfg,'cooldown',remaining=remaining))
                except discord.Forbidden:
                    await message.channel.send(phrase(cfg,'cooldown',remaining=remaining),delete_after=10,allowed_mentions=ui.MENTIONS)
        except Exception as exc:self.report_error(exc)

    async def on_raw_reaction_add(self,event):
        if event.guild_id!=self.guild_id or event.user_id==self.user.id:return
        try:
            task=await self.db.task_for_thread(event.guild_id,event.channel_id)
            if not task:return
            cfg,_=await self.db.config(event.guild_id)
            if not cfg['reactions_enabled']:return
            rule={emoji_key(k):v for k,v in cfg['reactions'].items()}.get(emoji_key(event.emoji))
            if not rule:return
            payload=dict(guild_id=event.guild_id,channel_id=event.channel_id,message_id=event.message_id,user_id=event.user_id,emoji=emoji_key(event.emoji),rule=rule)
            await self.db.execute('INSERT OR IGNORE INTO jobs(key,kind,guild,payload) VALUES(?,?,?,?)',(f'reaction:{event.guild_id}:{event.message_id}:{event.user_id}:{emoji_key(event.emoji)}','reaction',event.guild_id,canonical(payload)))
        except Exception as exc:self.report_error(exc)

    async def process_reaction(self,event,rule):
        guild=self.get_guild(event.guild_id)
        if not guild:raise ValueError('Server unavailable.')
        task=await self.db.task_for_thread(guild.id,event.channel_id)
        if not task:return
        cfg,_=await self.db.config(guild.id)
        actor=await self.service.eligible(guild,event.user_id)
        if not actor or (actor.id not in self.owners|set(cfg['primary_users'])|{guild.owner_id} and not set(cfg['manager_roles'])&{r.id for r in actor.roles}):return
        channel=guild.get_thread(event.channel_id) or await self.fetch_channel(event.channel_id)
        message=await channel.fetch_message(event.message_id)
        if message.author.bot or message.id==channel.id:return
        recipient=await self.service.eligible(guild,message.author.id,cfg['member_role'])
        if recipient is None:return
        if actor.id==recipient.id:raise ValueError('Another moderator must review your own contribution.')
        accepted=await self.db.query("SELECT cycle FROM task_messages WHERE task=? AND message=? AND user=?",(task['id'],message.id,recipient.id))
        if not accepted:raise ValueError("This post was not recorded while the bot was online. Review it using /ripper task_reward with the intended cycle.")
        await self.db.task_award(guild.id,task['id'],{recipient.id:recipient.display_name},accepted[0]['cycle'],actor.id,f"reaction:{message.id}:{emoji_key(event.emoji)}",rule['kind'],rule['amount'])
    async def on_member_join(self,member):
        if member.guild.id==self.guild_id:await self.db.enqueue(f"role:{member.guild.id}:{member.id}",'role',member.guild.id,{'user':member.id})

    async def on_member_update(self,before,after):
        if after.guild.id==self.guild_id and before.roles!=after.roles:
            await self.db.enqueue(f"role:{after.guild.id}:{after.id}",'role',after.guild.id,{'user':after.id})


def commands(bot):
    group=app_commands.Group(name='ripper',description='Ripper Zone community program',guild_only=True)
    bot.tree.add_command(group)

    async def message_award(i:discord.Interaction,message:discord.Message):
        from .admin_ui import message_award_form
        await message_award_form(bot,i,message)
    bot.tree.add_command(app_commands.ContextMenu(name='Award RC',callback=message_award))

    @group.command(description='Open your private Ripper Zone panel')
    async def panel(i:discord.Interaction):await ui.member_page(bot,i)

    @group.command(description='Open moderator administration')
    async def admin(i:discord.Interaction):await ui.admin_page(bot,i)

    @group.command(description='Configure Ripper Zone channels and access roles')
    async def setup(i:discord.Interaction):await ui.setup_start(bot,i)

    @group.command(description='Download a health and consistency report')
    async def doctor(i:discord.Interaction):await bot.doctor_action(i)

    @group.command(description='Preview and pay participation RC from an event export')
    async def snapshot(i:discord.Interaction,event_file:discord.Attachment,amount:int):
        await ui.defer(i);await bot.authorize(i)
        integer(amount,1,1000)
        if event_file.size>200000:raise ValueError("Event export exceeds 200 KB.")
        data=sources.validate(json.loads(await event_file.read()),i.guild_id)
        async def pay(j):
            await j.response.defer(ephemeral=True,thinking=True);await bot.authorize(j)
            count=await bot.db.snapshot(j.guild_id,data['source'],data['event'],data['participants'],amount,j.user.id)
            await ui.reply(j,content=f"{count} new participation rewards issued. {amount} RC each. Repeated imports pay zero.")
        screen=ui.Screen(bot,'Review Event Participation',f"Source: {data['source']}\nEvent: {data['event']}\nMembers: {len(data['participants'])}\nReward: {amount} RC each\nTotal: {len(data['participants'])*amount} RC\nWinners and other eligible participants receive the same participation reward.\nExport hash: {data['hash']}",owner=i.user.id)
        screen.button('Confirm Snapshot Rewards',pay,discord.ButtonStyle.success);await ui.show(i,screen)

    @group.command(description='Award accepted task contributors once per task cycle')
    async def task_snapshot(i:discord.Interaction,task_id:int,cycle_id:int,kind:Literal['base','quality']='base',quality_amount:int=5):
        await ui.defer(i);await bot.authorize(i)
        task=await bot.db.task(i.guild_id,task_id)
        rows=await bot.db.query("SELECT DISTINCT user FROM task_messages WHERE task=? AND cycle=?",(task_id,cycle_id))
        cfg,_=await bot.db.config(i.guild_id);people={}
        for row in rows:
            member=await bot.service.eligible(i.guild,row['user'],cfg['member_role'])
            if member:people[member.id]=member.display_name
        amount=task['reward'] if kind=='base' else integer(quality_amount,1,1000);op=str(i.id)
        async def confirm(j):
            await j.response.defer(ephemeral=True,thinking=True);await bot.authorize(j)
            count=await bot.db.task_award(j.guild_id,task_id,people,cycle_id,j.user.id,op,kind,amount)
            await ui.reply(j,content=f"{count} {kind} task rewards issued. Each base reward is paid once per task cycle.")
        screen=ui.Screen(bot,'Review Task Snapshot',f"Task #{task_id} · Cycle {cycle_id} · {kind}\nAccepted, eligible contributors: {len(people)}\n{amount} RC each · Maximum total {amount*len(people)} RC",owner=i.user.id)
        screen.button('Confirm Task Rewards',confirm,discord.ButtonStyle.success);await ui.show(i,screen)

    @group.command(description='Manage task lifecycle, cooldowns or recover a created thread')
    async def task_manage(i:discord.Interaction,action:Literal['list','close','archive','cooldown','reset_cooldown','bind_thread','resend_brief'],task_id:int=0,value:int=0):
        await ui.defer(i);await bot.authorize(i)
        if action=='list':
            rows=await bot.db.query("SELECT * FROM tasks WHERE guild=? ORDER BY id DESC LIMIT 30",(i.guild_id,))
            return await ui.reply(i,content='\n'.join(f"#{t['id']} {ui.escape(t['title'])} · {t['status']} · current cycle {cycle(t,int(time.time()))}" for t in rows)[:1900] or "No tasks.")
        task=await bot.db.task(i.guild_id,task_id)
        if action=='bind_thread':
            await bot.authorize(i,primary=True)
            thread=i.guild.get_thread(ident(value)) or await bot.fetch_channel(value)
            cfg,_=await bot.db.config(i.guild_id)
            if not isinstance(thread,discord.Thread) or thread.guild.id!=i.guild_id or thread.parent_id!=cfg['tasks_channel'] or thread.owner_id!=bot.user.id:
                raise ValueError("Use a thread created by this application in its task channel.")
            if task['status'] not in ('creating','publishing'):raise ValueError("Task is already bound or closed.")
            await bot.db.execute("UPDATE tasks SET thread=?,status='active' WHERE guild=? AND id=?",(value,i.guild_id,task_id))
            await bot.db.enqueue(f"taskbrief-recovered:{task_id}",'notice',i.guild_id,{'channel':value,'text':f"Task #{task_id}: {task['title']}\n{task['body']}\nBase reward: {task['reward']} RC"})
        elif action in ('close','archive'):
            await bot.db.close_task(i.guild_id,task_id,i.user.id)
            if task['thread']:
                thread=i.guild.get_thread(task['thread']) or await bot.fetch_channel(task['thread'])
                await thread.edit(locked=True,archived=action=='archive',reason="Ripper Zone task closed")
        elif action=='cooldown':
            integer(value,0,604800);await bot.db.edit_task(i.guild_id,task_id,{'cooldown':value},i.user.id,digest(task))
        elif action=='reset_cooldown':
            if value:await bot.db.execute("DELETE FROM cooldowns WHERE task=? AND user=?",(task_id,ident(value)))
            else:await bot.db.execute("DELETE FROM cooldowns WHERE task=?",(task_id,))
        elif action=='resend_brief':
            if not task['thread']:raise ValueError("Bind a thread first.")
            await bot.db.enqueue(f"taskbrief:{task_id}",'notice',i.guild_id,{'channel':task['thread'],'text':f"Task #{task_id}: {task['title']}\n{task['body']}\nBase reward: {task['reward']} RC"})
        await bot.db.audit(i.guild_id,i.user.id,'task_manage',f"{action}:{task_id}:{value}")
        await ui.reply(i,content="Task operation saved.")

    @group.command(description='Record a reviewed task contribution, including posts made during downtime')
    async def task_reward(i:discord.Interaction,task_id:int,cycle_id:int,member:discord.Member,kind:Literal['base','quality']='base',quality_amount:int=5,reason:str='Reviewed task contribution'):
        await ui.defer(i);await bot.authorize(i)
        cfg,_=await bot.db.config(i.guild_id)
        recipient=await bot.service.eligible(i.guild,member.id,cfg['member_role'])
        if not recipient:raise ValueError("The member does not meet community access requirements.")
        if recipient.id==i.user.id:raise ValueError("Another moderator must review your own task contribution.")
        count=await bot.db.task_award(i.guild_id,task_id,{member.id:recipient.display_name},cycle_id,i.user.id,str(i.id),kind,quality_amount)
        await bot.db.audit(i.guild_id,i.user.id,'manual_task_review',f"{task_id}:{cycle_id}:{member.id}:{kind}:{reason[:300]}")
        await ui.reply(i,content=f"{count} reviewed task rewards issued. An existing base reward for this cycle is not paid again.")

    @group.command(description='Operate RC raffles, prizes and publication recovery')
    async def raffle_manage(i:discord.Interaction,action:Literal['list','publish','close','cancel','delivered','forfeit','replace','bind_message','refresh'],raffle_id:int=0,member:Optional[discord.Member]=None,message_id:str='',reason:str='Administrator operation'):
        await ui.defer(i);await bot.authorize(i)
        if action=='list':
            rows=await bot.db.query("SELECT id,status,error FROM raffles WHERE guild=? ORDER BY id DESC LIMIT 25",(i.guild_id,))
            return await ui.reply(i,content='\n'.join(f"#{r['id']} {r['status']} {ui.escape(r['error'])}" for r in rows)[:1900] or "No RC raffles.")
        r=await bot.db.raffle(i.guild_id,raffle_id)
        if action=='publish':await bot.service.publish_raffle(i.guild,raffle_id,i.user.id)
        elif action=='close':await bot.service.close_raffle(i.guild,raffle_id,i.user.id,early=True)
        elif action=='cancel':await bot.db.cancel_raffle(i.guild_id,raffle_id,i.user.id,reason)
        elif action in ('delivered','forfeit'):
            if not member:raise ValueError("Select a prize winner.")
            await bot.db.prize_status(i.guild_id,raffle_id,member.id,'delivered' if action=='delivered' else 'forfeited',i.user.id,reason)
        elif action=='replace':await bot.service.replace_winners(i.guild,raffle_id,i.user.id,reason)
        elif action=='bind_message':
            await bot.authorize(i,primary=True)
            msg=await i.guild.get_channel(r['channel']).fetch_message(ident(message_id))
            if msg.author.id!=bot.user.id or not any(f"rz:buy:{raffle_id}"==getattr(child,'custom_id',None) for item in discord.ui.LayoutView.from_message(msg).walk_children() for child in [item]):
                raise ValueError("The message is not this application's matching raffle post.")
            await bot.db.bind_raffle(i.guild_id,raffle_id,msg.id)
            await bot.registry.record(i.guild_id,msg.id,'message',f"raffle:{raffle_id}")
        elif action=='refresh':await bot.service.update_raffle(i.guild,r)
        await ui.reply(i,content="Raffle operation completed. Financial decisions are saved before display updates.")

    @group.command(description='Primary administrator ledger correction with a recorded reason')
    async def correction(i:discord.Interaction,member:discord.Member,amount:int,reason:str):
        await ui.defer(i);await bot.authorize(i,primary=True)
        integer(amount,-100000,100000)
        if not amount:raise ValueError("Amount must not be zero.")
        async def confirm(j):
            await j.response.defer(ephemeral=True,thinking=True);await bot.authorize(j,primary=True)
            await bot.db.adjust(j.guild_id,member.id,amount,j.user.id,reason,str(i.id))
            await ui.reply(j,content="Correction recorded in the append-only RC ledger.")
        screen=ui.Screen(bot,'Confirm Ledger Correction',f"Member: <@{member.id}>\nAvailable and earned RC correction: {amount:+}\nReason: {ui.escape(reason)}\nA negative balance blocks new ticket purchases until covered by future earnings.",owner=i.user.id)
        screen.button('Record Correction',confirm,discord.ButtonStyle.danger);await ui.show(i,screen)

    @group.command(description='Export current settings without runtime message bindings')
    async def settings_export(i:discord.Interaction):
        await ui.defer(i);await bot.authorize(i,primary=True)
        cfg,_=await bot.db.config(i.guild_id)
        for k in ('panel_message','leaderboard_message'):cfg[k]=0
        cfg['panel_state']='new'
        await ui.reply(i,file=discord.File(io.BytesIO(json.dumps(cfg,indent=2).encode()),filename='ripper-zone-settings.json'))

    @group.command(description='Revoke one invalid contribution reward and its achievement metric')
    async def revoke_reward(i:discord.Interaction,ledger_id:int,reason:str):
        await ui.defer(i);await bot.authorize(i,primary=True)
        rows=await bot.db.query("SELECT * FROM ledger WHERE guild=? AND id=?",(i.guild_id,ledger_id))
        if not rows:raise ValueError("Ledger record not found.")
        row=rows[0]
        async def confirm(j):
            await j.response.defer(ephemeral=True,thinking=True);await bot.authorize(j,primary=True)
            done=await bot.db.revoke(j.guild_id,ledger_id,j.user.id,reason)
            await ui.reply(j,content="Invalid reward reversed. Related contribution metrics were removed." if done else "This reward was already reversed.")
        screen=ui.Screen(bot,'Revoke Invalid Reward',f"Ledger #{ledger_id}: <@{row['user']}> · {row['de']} earned RC\n{ui.escape(row['reason'])}\nReason for revocation: {ui.escape(reason)}\nThis records a reversal without deleting history.",owner=i.user.id)
        screen.button('Confirm Reward Revocation',confirm,discord.ButtonStyle.danger);await ui.show(i,screen)

    @group.command(description='Preview validated settings before importing')
    async def settings_import(i:discord.Interaction,attachment:discord.Attachment):
        await ui.defer(i);await bot.authorize(i,primary=True)
        if attachment.size>50000:raise ValueError("Settings file exceeds 50 KB.")
        proposed=settings(json.loads(await attachment.read()));current,rev=await bot.db.config(i.guild_id)
        for k in ('panel_message','leaderboard_message','panel_state'):proposed[k]=current[k]
        await bot.service.validate_config(i.guild,proposed)
        changed=[k for k in proposed if proposed[k]!=current[k]]
        async def save(j):
            await j.response.defer(ephemeral=True,thinking=True);await bot.authorize(j,primary=True)
            await bot.service.configure(j.guild,proposed,rev,j.user.id)
            await ui.reply(j,content="Validated settings imported.")
        screen=ui.Screen(bot,'Review Settings Import',"Changed fields: "+', '.join(changed)+f"\nExpected current revision: {rev}",owner=i.user.id)
        screen.button('Confirm Import',save,discord.ButtonStyle.success);await ui.show(i,screen)

    @group.command(description='List saved settings history or preview a previous revision')
    async def settings_history(i:discord.Interaction,history_id:int=0):
        await ui.defer(i);await bot.authorize(i,primary=True)
        rows=await bot.db.config_history(i.guild_id)
        if not history_id:return await ui.reply(i,content='\n'.join(f"#{r['id']} <t:{r['at']}:F> by <@{r['actor']}>" for r in rows) or "No previous settings.")
        chosen=next((r for r in rows if r['id']==history_id),None)
        if not chosen:raise ValueError("History entry not found.")
        cfg,rev=await bot.db.config(i.guild_id);old=settings(json.loads(chosen['data']))
        for k in ('panel_message','leaderboard_message','panel_state'):old[k]=cfg[k]
        async def restore(j):
            await j.response.defer(ephemeral=True,thinking=True);await bot.authorize(j,primary=True)
            await bot.service.configure(j.guild,old,rev,j.user.id);await ui.reply(j,content="Previous settings restored after validation.")
        screen=ui.Screen(bot,'Restore Settings',f"History entry #{history_id}. Current permissions and roles will be validated.\nChanged fields: "+', '.join(k for k in old if old[k]!=cfg[k]),owner=i.user.id)
        screen.button('Restore This Configuration',restore,discord.ButtonStyle.danger);await ui.show(i,screen)

    @group.command(description='Export leaderboard or complete RC transaction CSV')
    async def report(i:discord.Interaction,kind:Literal['leaderboard','ledger','tasks','raffles','audit']):
        await ui.defer(i);await bot.authorize(i)
        sql={'leaderboard':"SELECT * FROM accounts WHERE guild=? ORDER BY earned DESC,user",'ledger':"SELECT * FROM ledger WHERE guild=? ORDER BY id",'tasks':"SELECT * FROM tasks WHERE guild=? ORDER BY id",'raffles':"SELECT id,guild,actor,channel,message,status,spec,created,error FROM raffles WHERE guild=? ORDER BY id",'audit':"SELECT * FROM audit WHERE guild=? ORDER BY id"}[kind]
        rows=await bot.db.query(sql,(i.guild_id,));buffer=io.StringIO();writer=csv.writer(buffer)
        if rows:
            writer.writerow(rows[0].keys())
            for row in rows:
                # Spreadsheet formula injection is disabled in member-controlled text.
                writer.writerow("'"+v if isinstance(v,str) and (v.lstrip().startswith(('=','+','-','@')) or v.startswith(('\t','\r','\n'))) else v for v in row.values())
        raw=buffer.getvalue().encode('utf-8-sig')
        if len(raw)>7_000_000:raise ValueError("Report exceeds the upload budget. Use the local operator export command.")
        await ui.reply(i,file=discord.File(io.BytesIO(raw),filename=f"ripper-zone-{kind}.csv"))

    @group.command(description='Configure primary user IDs, moderator roles or daily-spin role')
    async def access(i:discord.Interaction,field:Literal['primary_users','manager_roles','spin_role'],ids:str):
        await ui.defer(i);await bot.authorize(i,primary=True)
        cfg,rev=await bot.db.config(i.guild_id);values=[ident(x.strip()) for x in ids.split(',') if x.strip() and x.strip()!='0']
        if field=='spin_role':
            if len(values)>1:raise ValueError("Select one role or 0 to disable the extra requirement.")
            cfg[field]=values[0] if values else 0
        else:cfg[field]=values
        await bot.service.configure(i.guild,cfg,rev,i.user.id);await ui.reply(i,content="Access settings saved.")

    @group.command(description='Configure a moderator reward reaction')
    async def reactions(i:discord.Interaction,emoji:str,kind:Literal['base','quality','remove'],amount:int=5):
        await ui.defer(i);await bot.authorize(i,primary=True)
        cfg,rev=await bot.db.config(i.guild_id);key=emoji_key(emoji)
        cfg['reactions']={emoji_key(k):v for k,v in cfg['reactions'].items()}
        if kind=='remove':cfg['reactions'].pop(key,None)
        else:cfg['reactions'][key]={'kind':kind,'amount':0 if kind=='base' else integer(amount,1,1000)}
        await bot.service.configure(i.guild,cfg,rev,i.user.id);await ui.reply(i,content="Moderator reward reactions saved.")

    @group.command(description='Recover a known panel or leaderboard message without creating duplicates')
    async def panel_recover(i:discord.Interaction,kind:Literal['panel','leaderboard'],message_id:str):
        await ui.defer(i);await bot.authorize(i,primary=True)
        cfg,rev=await bot.db.config(i.guild_id);mid=ident(message_id);channel=i.guild.get_channel(cfg[kind+'_channel'])
        msg=await channel.fetch_message(mid)
        if msg.author.id!=bot.user.id:raise ValueError("Use this application's own message.")
        children=list(discord.ui.LayoutView.from_message(msg).walk_children())
        if kind=='panel' and not any(getattr(x,'custom_id',None)=='rz:panel:v1' for x in children):raise ValueError("Not a Ripper Zone member panel.")
        cfg[kind+'_message']=mid
        if kind=='panel':cfg['panel_state']='active'
        await bot.db.save_config(i.guild_id,cfg,rev,i.user.id)
        await bot.service.finish_move(i.guild,kind,mid)
        if kind=='leaderboard':await bot.db.execute("DELETE FROM meta_flags WHERE key='leaderboard_sending'")
        await ui.reply(i,content="Saved message binding recovered.")

    @group.command(description='Publish or refresh the public leaderboard')
    async def leaderboard_publish(i:discord.Interaction):
        await ui.defer(i);await bot.authorize(i,primary=True)
        if await bot.db.query("SELECT 1 FROM meta_flags WHERE key='leaderboard_sending'"):raise ValueError("A previous send requires message-ID recovery.")
        await bot.refresh_leaderboard(i.guild,publish=True);await ui.reply(i,content="Public leaderboard published or refreshed.")

    @group.command(description='Primary recovery tools, backed by consistency checks')
    async def recovery(i:discord.Interaction,action:Literal['retry_jobs','clear_accounting_pause','restart','mark_panel_missing']):
        await ui.defer(i);await bot.authorize(i,primary=True)
        if action=='retry_jobs':await bot.db.execute("UPDATE jobs SET state='pending',attempts=0,next_at=0 WHERE guild=? AND state='failed'",(i.guild_id,))
        elif action=='clear_accounting_pause':await bot.db.clear_financial_block(i.guild_id,i.user.id)
        elif action=='mark_panel_missing':
            cfg,rev=await bot.db.config(i.guild_id)
            if cfg['panel_message']:
                try:await i.guild.get_channel(cfg['panel_channel']).fetch_message(cfg['panel_message'])
                except discord.NotFound:pass
                else:raise ValueError("The existing panel still exists. Refresh it instead.")
            elif cfg['panel_state']=='sending':raise ValueError("An uncertain send needs message-ID recovery or local operator review, not an automatic repost.")
            cfg.update(panel_message=0,panel_state='missing');await bot.db.save_config(i.guild_id,cfg,rev,i.user.id)
        elif action=='restart':
            token=os.environ.get('HEALTH_SECRET','')
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(f"http://127.0.0.1:{os.environ.get('RECOVERY_PORT','3041')}/restart",headers={'Authorization':'Bearer '+token}) as response:
                    if response.status!=200:raise ValueError("Recovery refused the restart. Inspect the recovery health report.")
        await bot.db.audit(i.guild_id,i.user.id,'recovery',action)
        await ui.reply(i,content="Recovery action accepted.")


def main():
    load_dotenv(os.environ.get('ENV_FILE','.env'))
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
    token=os.environ.get('DISCORD_TOKEN','').strip()
    if len(token)<30:raise SystemExit("Set DISCORD_TOKEN in the private environment file.")
    ident(os.environ.get('DISCORD_GUILD_ID',''))
    path=Path(os.environ.get('DATABASE_PATH','data/ripper-zone.sqlite3'))
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=open(str(path)+'.process.lock','a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit("Another Ripper Zone process already owns this database.")
    os.umask(0o077)
    bot=RipperBot()
    try:bot.run(token,log_handler=None)
    except (discord.LoginFailure,discord.PrivilegedIntentsRequired):
        Path(str(path)+'.fatal').write_text('credentials-or-intents')
        log.error("Token or privileged intents require administrator correction.")
        raise SystemExit(78)
    finally:lock.close()
