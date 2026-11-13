"""Discord effects run after durable decisions. No HTTP inside ledger transactions."""
import asyncio
import json
import logging
import re
import time
from pathlib import Path
import discord
from .config import settings, canonical
from .copy import phrase,receipt_text

log=logging.getLogger(__name__)
LEADERBOARD_EXCLUDED_ROLES=frozenset((1560351679700799588,1560351676718780617))


async def leaderboard_exclusions(guild):
    # A partial member cache must not expose offline holders of excluded roles.
    members=guild.members if guild.chunked else await asyncio.wait_for(guild.chunk(cache=True),30)
    return tuple(m.id for m in members if LEADERBOARD_EXCLUDED_ROLES&{r.id for r in m.roles})


def tier_for(account,tiers):
    found=None
    for tier in tiers:
        if all(account[k]>=tier[k] for k in ('earned','tasks','events')):found=tier
    return found


def role_safe(guild,role,protected=()):
    if not role or role.is_default() or role.managed or role.id in protected:
        raise ValueError("Select a separate, unmanaged achievement role.")
    if role.permissions.value:
        raise ValueError("Achievement roles must have no server permissions.")
    if not guild.me.guild_permissions.manage_roles or role>=guild.me.top_role:
        raise ValueError("Place the bot above achievement roles and grant Manage Roles.")


class Service:
    def __init__(self,bot):
        self.bot=bot;self.db=bot.db;self.last_tick=0;self.last_check=0;self.last_leaderboard=0;self.last_backup=''
        self.issues={};self.running=True

    async def eligible(self,guild,user,role=0):
        try:
            member=await asyncio.wait_for(guild.fetch_member(user),15)
        except discord.NotFound:return None
        # Forbidden, rate limits and timeouts are failures, never exclusions.
        if member.bot or (role and role not in {r.id for r in member.roles}):return None
        return member

    async def role_job(self,guild,user):
        cfg,_=await self.db.config(guild.id)
        account=await self.db.account(guild.id,user)
        member=await self.eligible(guild,user)
        if member is None:return
        owned=await self.db.query("SELECT role FROM owned_roles WHERE guild=?",(guild.id,))
        protected={cfg['member_role'],cfg['spin_role'],*cfg['manager_roles']}
        access=not cfg['member_role'] or cfg['member_role'] in {r.id for r in member.roles}
        target=tier_for(account,cfg['tiers']) if cfg['roles_enabled'] and access else None
        target_role=guild.get_role(target['role']) if target else None
        roles=[]
        for item in owned:
            role=guild.get_role(item['role'])
            if role:
                role_safe(guild,role,protected)
                await self.bot.registry.check_role(guild.id,role.id)
                roles.append(role)
        if target:
            role_safe(guild,target_role,protected)
            if target_role.id not in {r.id for r in member.roles}:
                await member.add_roles(target_role,reason="Ripper Zone achievement progress")
        remove=[r for r in roles if r!=target_role and r.id in {x.id for x in member.roles}]
        if remove:await member.remove_roles(*remove,reason="Ripper Zone keeps the highest eligible achievement tier")

    async def validate_config(self,guild,cfg):
        cfg=settings(cfg)
        for key in ('panel_channel','tasks_channel','leaderboard_channel','raffle_channel','log_channel','audit_channel'):
            if not cfg[key]:continue
            channel=guild.get_channel(cfg[key])
            if not isinstance(channel,discord.TextChannel):raise ValueError(f"{key} must be a text channel in this server.")
            p=channel.permissions_for(guild.me)
            needed=['view_channel','send_messages','read_message_history','attach_files','embed_links']
            if key=='tasks_channel':needed+=['create_public_threads','send_messages_in_threads','manage_threads','manage_messages','add_reactions']
            if not all(getattr(p,k) for k in needed):raise ValueError(f"Missing permissions in #{channel.name}: "+', '.join(k for k in needed if not getattr(p,k)))
        if cfg['audit_channel'] and cfg['audit_channel'] in [cfg[x] for x in ('panel_channel','tasks_channel','leaderboard_channel','raffle_channel','log_channel')]:
            raise ValueError("Use a separate private moderator log channel.")
        if cfg['audit_channel']:
            channel=guild.get_channel(cfg['audit_channel'])
            if channel.permissions_for(guild.default_role).view_channel:
                raise ValueError("Hide the moderator log channel from @everyone.")
            role=guild.get_role(cfg['member_role']) if cfg['member_role'] else None
            if role and channel.permissions_for(role).view_channel:
                raise ValueError("Hide the moderator log channel from the community access role.")
            allowed={guild.me.id,guild.owner_id,*cfg['primary_users'],*getattr(self.bot,'owners',set()),*cfg['manager_roles']}
            for target,overwrite in channel.overwrites.items():
                if overwrite.view_channel is True and target.id not in allowed:
                    if isinstance(target,discord.Role) and (target.permissions.administrator or getattr(getattr(target,'tags',None),'bot_id',None)==guild.me.id):continue
                    raise ValueError('Moderator log has a View Channel allow for an unapproved role or member.')
        if cfg['support_channel'] and not isinstance(guild.get_channel(cfg['support_channel']),discord.TextChannel):raise ValueError('Select a support channel in this server.')
        for key in ('member_role','spin_role'):
            if cfg[key] and not guild.get_role(cfg[key]):raise ValueError(f"{key} was deleted.")
        for rid in cfg['manager_roles']:
            if not guild.get_role(rid):raise ValueError("A moderator role was deleted.")
        for tier in cfg['tiers']:
            role_safe(guild,guild.get_role(tier['role']),{cfg['member_role'],cfg['spin_role'],*cfg['manager_roles']})
            await self.bot.registry.check_role(guild.id,tier['role'])
        return cfg

    async def configure(self,guild,cfg,revision,actor):
        old,_=await self.db.config(guild.id)
        for kind in ('panel','leaderboard'):
            if (old[kind+'_message'] or old['panel_state']=='sending' or await self.db.query('SELECT 1 FROM meta_flags WHERE key=?',(f'move:{guild.id}:{kind}',))) and cfg[kind+'_channel']!=old[kind+'_channel']:
                raise ValueError('This public message is bound to its existing channel. Use Move Public Message in Settings first.')
        cfg=await self.validate_config(guild,cfg)
        # Reserve roles first. A private save failure leaves a safe ownership claim.
        for tier in cfg['tiers']:
            await self.bot.registry.record(guild.id,tier['role'],'role',str(tier['role']))
        return await self.db.save_config(guild.id,cfg,revision,actor)

    async def move_public(self,guild,kind,channel_id,actor,revision):
        from . import ui
        if kind not in ('panel','leaderboard'):raise ValueError('Unknown public message type.')
        cfg,rev=await self.db.config(guild.id)
        if rev!=revision:raise ValueError('Settings changed. Reopen the move page.')
        if channel_id==cfg[kind+'_channel']:raise ValueError('Choose a different channel.')
        if not cfg[kind+'_message']:raise ValueError('Publish or recover the existing message first.')
        candidate=dict(cfg);candidate[kind+'_channel']=channel_id
        await self.validate_config(guild,candidate)
        excluded=await leaderboard_exclusions(guild) if kind=='leaderboard' else ()
        key=f'move:{guild.id}:{kind}'
        def begin(c):
            live,v=self.db._config(c,guild.id)
            if v!=revision or c.execute('SELECT 1 FROM meta_flags WHERE key=?',(key,)).fetchone():raise ValueError('A public message move is already pending or settings changed.')
            self.db._save_history(c,guild.id,actor,live)
            c.execute('INSERT INTO meta_flags VALUES(?,?)',(key,canonical({'channel':live[kind+'_channel'],'message':live[kind+'_message']})))
            live[kind+'_channel']=channel_id;live[kind+'_message']=0
            if kind=='panel':live['panel_state']='sending'
            else:c.execute("INSERT OR REPLACE INTO meta_flags VALUES('leaderboard_sending','1')")
            self.db._put_config(c,guild.id,live,v+1)
            self.db._audit(c,guild.id,actor,'public_message_move',kind)
        await self.db.run(begin)
        view=ui.gateway(self.bot,candidate) if kind=='panel' else ui.public_leaderboard(self.bot,await self.db.leaders(guild.id,excluded=excluded))
        msg=await guild.get_channel(channel_id).send(view=view,files=view.files(),allowed_mentions=ui.MENTIONS)
        def bind(c):
            live,v=self.db._config(c,guild.id)
            if live[kind+'_channel']!=channel_id:raise ValueError('Publication channel changed during move. Recover the sent message.')
            live[kind+'_message']=msg.id
            if kind=='panel':live['panel_state']='active'
            self.db._put_config(c,guild.id,live,v+1)
            if kind=='leaderboard':c.execute("DELETE FROM meta_flags WHERE key='leaderboard_sending'")
        await self.db.run(bind)
        await self.bot.registry.record(guild.id,msg.id,'message',kind+':'+str(msg.id))
        await self.finish_move(guild,kind,msg.id)
        return msg

    async def finish_move(self,guild,kind,message):
        key=f'move:{guild.id}:{kind}'
        rows=await self.db.query('SELECT value FROM meta_flags WHERE key=?',(key,))
        if not rows:return
        old=json.loads(rows[0]['value']);cfg,_=await self.db.config(guild.id)
        await self.db.enqueue(key,'redirect',guild.id,{**old,'key':key,'url':f'https://discord.com/channels/{guild.id}/{cfg[kind+"_channel"]}/{message}'})

    async def publish_task(self,guild,tid):
        task=await self.db.task(guild.id,tid);cfg,_=await self.db.config(guild.id)
        if task['status']!='creating':raise ValueError("Task already has a thread.")
        channel=guild.get_channel(cfg['tasks_channel'])
        # Any uncertain create result is left for explicit ID recovery, never repeated.
        if not await self.db.execute("UPDATE tasks SET status='publishing' WHERE id=? AND status='creating'",(tid,)):raise ValueError("Task publication is already in progress.")
        thread=await channel.create_thread(name=f"Task {tid} · {task['title']}"[:100],type=discord.ChannelType.public_thread,auto_archive_duration=1440,reason="Ripper Zone community task")
        # Bind before sending the brief. Failed brief delivery becomes a retry job.
        await self.db.execute("UPDATE tasks SET thread=?,status='active' WHERE id=? AND guild=? AND status='publishing'",(thread.id,tid,guild.id))
        await self.db.enqueue(f'tasksync:{tid}','task_sync',guild.id,{'task':tid})
        await self.db.audit(guild.id,task['actor'],'task_published',f"{tid}:{thread.id}")
        return thread

    async def sync_task(self,guild,tid):
        from .ui import task_view,MENTIONS
        task=await self.db.task(guild.id,tid)
        if not task['thread']:raise ValueError('Bind the task thread in Publication Recovery first.')
        thread=guild.get_thread(task['thread']) or await self.bot.fetch_channel(task['thread'])
        if thread.guild.id!=guild.id or thread.owner_id!=self.bot.user.id:raise ValueError('Task thread ownership differs.')
        key=f'task_brief:{tid}'
        rows=await self.db.query('SELECT value FROM meta_flags WHERE key=?',(key,))
        binding=json.loads(rows[0]['value']) if rows else {}
        message=None
        if binding.get('message'):
            try:message=await thread.fetch_message(binding['message'])
            except discord.NotFound:binding={}
        else:
            async for candidate in thread.history(limit=100,oldest_first=True):
                if candidate.author.id!=self.bot.user.id:continue
                content=candidate.content or ''
                if content.startswith(f'Task #{tid}:') or any(str(getattr(c,'content','')).startswith(f'## Task #{tid} ·') for c in discord.ui.LayoutView.from_message(candidate).walk_children()):
                    message=candidate;break
            if not message and binding.get('state')=='sending':raise ValueError('An uncertain task brief needs message binding recovery.')
        cfg,_=await self.db.config(guild.id);view=task_view(self.bot,task,cfg)
        if message and message.author.id!=self.bot.user.id:raise ValueError('Task brief belongs to another application.')
        archived=getattr(thread,'archived',False) is True
        if archived:await thread.edit(archived=False)
        try:
            if message:await message.edit(content=None,embeds=[],view=view,attachments=view.files(),allowed_mentions=MENTIONS)
            else:
                await self.db.execute('INSERT OR REPLACE INTO meta_flags VALUES(?,?)',(key,canonical({'state':'sending'})))
                message=await thread.send(view=view,files=view.files(),allowed_mentions=MENTIONS)
            await self.db.execute('INSERT OR REPLACE INTO meta_flags VALUES(?,?)',(key,canonical({'state':'active','message':message.id})))
            await thread.edit(name=f"Task {tid} · {task['title']}"[:100])
        finally:
            if archived or task['status']=='closed':await thread.edit(archived=True,locked=task['status']=='closed')

    async def refresh_panel(self,guild):
        from .ui import gateway,MENTIONS
        cfg,_=await self.db.config(guild.id)
        if not cfg['panel_message']:return
        message=await guild.get_channel(cfg['panel_channel']).fetch_message(cfg['panel_message'])
        if message.author.id!=self.bot.user.id:raise ValueError('Panel ownership differs.')
        view=gateway(self.bot,cfg)
        await message.edit(view=view,attachments=view.files(),allowed_mentions=MENTIONS)

    async def publish_raffle(self,guild,rid,actor):
        from .ui import raffle_view
        cfg,_=await self.db.config(guild.id)
        r=await self.db.begin_publish(guild.id,rid,actor,cfg['raffle_channel'])
        channel=guild.get_channel(r['channel'])
        # The saved publishing state disables buying; the worker enables it only
        # after the message ID is durably bound.
        msg=await channel.send(view=raffle_view(self.bot,r,cfg),allowed_mentions=discord.AllowedMentions.none())
        await self.db.bind_raffle(guild.id,rid,msg.id)
        await self.bot.registry.record(guild.id,msg.id,'message',f"raffle:{rid}")
        return msg

    async def checks(self,guild,pool,role):
        semaphore=asyncio.Semaphore(4)
        async def check(row):
            async with semaphore:
                member=await self.eligible(guild,row['user'],role)
                self.last_tick=time.time()
                return {'user':row['user'],'eligible':member is not None,'at':int(time.time()),'reason':'eligible' if member else 'left server, bot, or missing frozen access role'}
        return await asyncio.gather(*(check(x) for x in pool))

    async def close_raffle(self,guild,rid,actor=0,early=False):
        r=await self.db.freeze_raffle(guild.id,rid,actor,early)
        checks=await self.checks(guild,r['frozen'],r['contract']['member_role'])
        return await self.db.finalize_raffle(guild.id,rid,checks)

    async def replace_winners(self,guild,rid,actor,reason):
        r=await self.db.raffle(guild.id,rid)
        seen={u for rnd in r['rounds'] for u in rnd['winners']}
        pool=[x for x in r['rounds'][0]['pool'] if x['user'] not in seen]
        checks=await self.checks(guild,pool,r['contract']['member_role'])
        return await self.db.reroll_raffle(guild.id,rid,checks,actor,reason)

    async def update_raffle(self,guild,r):
        from .ui import raffle_view
        channel=guild.get_channel(r['channel'])
        if not channel or not r['message']:raise ValueError("Raffle message requires administrator binding recovery.")
        cfg,_=await self.db.config(guild.id)
        msg=await channel.fetch_message(r['message'])
        if msg.author.id!=self.bot.user.id:raise ValueError("Refusing to edit another bot's message.")
        await msg.edit(view=raffle_view(self.bot,r,cfg),allowed_mentions=discord.AllowedMentions.none())
        # Update the original public post, so uncertain delivery never creates duplicates.
        await self.db.execute("UPDATE raffles SET announcement_state='done',error='' WHERE id=?",(r['id'],))

    async def job(self,job):
        guild=self.bot.get_guild(job['guild'])
        if not guild:raise ValueError("Server is unavailable.")
        p=job['payload']
        if job['kind']=='redirect':
            from .ui import Screen,MENTIONS
            channel=guild.get_channel(p['channel'])
            try:msg=await channel.fetch_message(p['message'])
            except discord.NotFound:
                await self.db.execute('DELETE FROM meta_flags WHERE key=?',(p['key'],));return
            if msg.author.id!=self.bot.user.id:raise ValueError('Previous message ownership differs.')
            view=Screen(self.bot,'Ripper Zone · Moved','This public panel has moved. Open its new location below.')
            view.box.add_item(discord.ui.ActionRow(discord.ui.Button(label='Open New Location',url=p['url'])))
            await msg.edit(content=None,embeds=[],view=view,attachments=[],allowed_mentions=MENTIONS)
            await self.db.execute('DELETE FROM meta_flags WHERE key=?',(p['key'],))
        elif job['kind']=='reaction':
            from types import SimpleNamespace
            await self.bot.process_reaction(SimpleNamespace(**p),p['rule'])
        elif job['kind']=='leaderboard_refresh':await self.bot.refresh_leaderboard(guild)
        elif job['kind']=='raffle_refresh':await self.update_raffle(guild,await self.db.raffle(guild.id,p['raffle']))
        elif job['kind']=='task_sync':await self.sync_task(guild,p['task'])
        elif job['kind']=='panel_refresh':await self.refresh_panel(guild)
        elif job['kind']=='role':await self.role_job(guild,p['user'])
        elif job['kind']=='notice':
            if job['key'].startswith(('taskbrief:','taskbrief-recovered:')):
                task=await self.db.task_for_thread(guild.id,p['channel'])
                if task:return await self.sync_task(guild,task['id'])
            text=p['text'];channel_id=p['channel']
            if job['key'].startswith('notice:'):
                cfg,_=await self.db.config(guild.id)
                rows=await self.db.query('SELECT * FROM ledger WHERE guild=? AND key=?',(guild.id,job['key'][7:]))
                if not rows:raise ValueError('Receipt ledger entry is missing. Review the queued notice.')
                if rows:
                    rendered=receipt_text(rows[0])
                    if rendered is None:
                        if not cfg['audit_channel']:return
                        channel_id=cfg['audit_channel']
                    else:text=rendered;channel_id=cfg['log_channel']
                if not channel_id:raise ValueError('Configure the public RC activity channel.')
            channel=guild.get_channel_or_thread(channel_id) or await self.bot.fetch_channel(channel_id)
            if job['key'].startswith('notice:'):
                match=re.search(r'<@!?(\d+)>',text)
                if match:
                    uid=int(match[1]);person=guild.get_member(uid)
                    if person is None:
                        try:person=await guild.fetch_member(uid)
                        except (discord.NotFound,discord.Forbidden):
                            try:person=await self.bot.fetch_user(uid)
                            except (discord.NotFound,discord.Forbidden):person=None
                    rows=await self.db.query('SELECT name FROM accounts WHERE guild=? AND user=?',(guild.id,uid)) if person is None else []
                    name=person.display_name if person is not None else (rows[0]['name'] if rows else '') or f'Member {uid}'
                    label=re.sub(r'([\\`*_~|<>\[\]()])',r'\\\1',discord.utils.escape_mentions('@'+name[:128]))
                    text=text.replace(match[0],f'[{label}](https://discord.com/users/{uid})')
            # Log sends are best-effort with durable retries. Duplicate audit lines after
            # a network timeout are harmless; they never apply financial changes.
            await channel.send(text[:2000],allowed_mentions=discord.AllowedMentions.none(),suppress_embeds=True)
        elif job['kind']=='taskclose':
            task=await self.db.task(guild.id,p['task'])
            if task['thread']:
                thread=guild.get_thread(task['thread']) or await self.bot.fetch_channel(task['thread'])
                await self.sync_task(guild,task['id'])
                await thread.edit(locked=True,archived=True,reason="Ripper Zone task deadline reached")
        else:raise ValueError("Unknown background job.")

    async def tick(self):
        self.last_tick=time.time()
        for _ in range(10):
            job=await self.db.claim_job()
            if not job:break
            error=None
            try:await self.job(job)
            except Exception as exc:
                error=type(exc).__name__+': '+str(exc)[:250]
                log.warning("Background %s failed: %s",job['key'],error)
            await self.db.finish_job(job,error)
            self.last_tick=time.time()
        guild=self.bot.get_guild(self.bot.guild_id)
        if not guild:return
        def expire(c):
            for task in c.execute("SELECT id FROM tasks WHERE guild=? AND status='active' AND ends>0 AND ends<=?",(guild.id,int(time.time()))).fetchall():
                c.execute("UPDATE tasks SET status='closed' WHERE id=?",(task[0],))
                self.db._enqueue(c,f"taskclose:{task[0]}",'taskclose',guild.id,{'task':task[0]})
        await self.db.run(expire)
        rows=await self.db.query("SELECT id FROM raffles WHERE guild=? AND (status='closing' OR (status='open' AND json_extract(spec,'$.ends')<=?))",(guild.id,int(time.time())))
        for row in rows:
            try:
                await self.close_raffle(guild,row['id']);self.issues.pop(f"raffle:{row['id']}",None)
            except Exception as exc:
                self.issues[f"raffle:{row['id']}"]=type(exc).__name__+': '+str(exc)[:200]
                await self.db.execute("UPDATE raffles SET error=? WHERE id=?",(self.issues[f"raffle:{row['id']}"],row['id']))
        rows=await self.db.query("SELECT id FROM raffles WHERE guild=? AND message IS NOT NULL AND status IN ('open','drawn','cancelled') AND announcement_state='pending'",(guild.id,))
        for row in rows:
            try:
                await self.update_raffle(guild,await self.db.raffle(guild.id,row['id']))
                self.issues.pop(f"display:{row['id']}",None)
            except Exception as exc:self.issues[f"display:{row['id']}"]=type(exc).__name__+': '+str(exc)[:150]
        if time.time()-self.last_check>=300:
            self.last_check=time.time()
            if await self.db.reconcile(guild.id):self.issues['accounting']="RC ledger mismatch. Awards and purchases are paused."
            else:self.issues.pop('accounting',None)
        if time.time()-self.last_leaderboard>=300:
            self.last_leaderboard=time.time()
            try:await self.bot.refresh_leaderboard(guild)
            except Exception as exc:self.issues['leaderboard']=type(exc).__name__+': '+str(exc)[:150]
        day=time.strftime('%Y-%m-%d',time.gmtime())
        if self.last_backup!=day:
            folder=Path(self.db.path).parent/'backups'
            await self.db.backup(folder/f"ripper-zone-{day}.sqlite3")
            for old in sorted(folder.glob('ripper-zone-*.sqlite3'))[:-7]:old.unlink()
            self.last_backup=day

    async def loop(self):
        await self.bot.wait_until_ready()
        while self.running:
            try:await self.tick();self.issues.pop('worker',None)
            except asyncio.CancelledError:raise
            except Exception as exc:
                log.exception("Worker iteration failed")
                self.issues['worker']=type(exc).__name__+': '+str(exc)[:150]
            await asyncio.sleep(15)
