"""Discord effects run after durable decisions. No HTTP inside ledger transactions."""
import asyncio
import json
import logging
import time
from pathlib import Path
import discord
from .config import settings

log=logging.getLogger(__name__)


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
        for key in ('panel_channel','tasks_channel','leaderboard_channel','raffle_channel','log_channel'):
            if not cfg[key]:continue
            channel=guild.get_channel(cfg[key])
            if not isinstance(channel,discord.TextChannel):raise ValueError(f"{key} must be a text channel in this server.")
            p=channel.permissions_for(guild.me)
            needed=['view_channel','send_messages','read_message_history','attach_files','embed_links']
            if key=='tasks_channel':needed+=['create_public_threads','send_messages_in_threads','manage_threads','manage_messages','add_reactions']
            if not all(getattr(p,k) for k in needed):raise ValueError(f"Missing permissions in #{channel.name}: "+', '.join(k for k in needed if not getattr(p,k)))
        if cfg['log_channel'] and cfg['log_channel'] in [cfg[x] for x in ('panel_channel','tasks_channel','leaderboard_channel','raffle_channel')]:
            raise ValueError("Use a separate private moderator log channel.")
        if cfg['log_channel']:
            channel=guild.get_channel(cfg['log_channel'])
            if channel.permissions_for(guild.default_role).view_channel:
                raise ValueError("Hide the moderator log channel from @everyone.")
            role=guild.get_role(cfg['member_role']) if cfg['member_role'] else None
            if role and channel.permissions_for(role).view_channel:
                raise ValueError("Hide the moderator log channel from the community access role.")
        for key in ('member_role','spin_role'):
            if cfg[key] and not guild.get_role(cfg[key]):raise ValueError(f"{key} was deleted.")
        for rid in cfg['manager_roles']:
            if not guild.get_role(rid):raise ValueError("A moderator role was deleted.")
        for tier in cfg['tiers']:
            role_safe(guild,guild.get_role(tier['role']),{cfg['member_role'],cfg['spin_role'],*cfg['manager_roles']})
            await self.bot.registry.check_role(guild.id,tier['role'])
        return cfg

    async def configure(self,guild,cfg,revision,actor):
        cfg=await self.validate_config(guild,cfg)
        # Reserve roles first. A private save failure leaves a safe ownership claim.
        for tier in cfg['tiers']:
            await self.bot.registry.record(guild.id,tier['role'],'role',str(tier['role']))
        return await self.db.save_config(guild.id,cfg,revision,actor)

    async def publish_task(self,guild,tid):
        task=await self.db.task(guild.id,tid);cfg,_=await self.db.config(guild.id)
        if task['status']!='creating':raise ValueError("Task already has a thread.")
        channel=guild.get_channel(cfg['tasks_channel'])
        # Any uncertain create result is left for explicit ID recovery, never repeated.
        await self.db.execute("UPDATE tasks SET status='publishing' WHERE id=? AND status='creating'",(tid,))
        period={0:'One-time',86400:'Daily UTC',604800:'Weekly, anchored to creation day UTC'}[task['period']]
        text=f"Task #{tid}: {task['title']}\n\n{task['body']}\n\nBase reward: {task['reward']} RC · {period}\nPosting cooldown: {task['cooldown']} seconds.\nPost your contribution here. Moderators approve with the configured reward reactions."
        if task['ends']:text+=f"\nDeadline: <t:{task['ends']}:F>"
        thread=await channel.create_thread(name=f"Task {tid} · {task['title']}"[:100],type=discord.ChannelType.public_thread,auto_archive_duration=1440,reason="Ripper Zone community task")
        # Bind before sending the brief. Failed brief delivery becomes a retry job.
        await self.db.execute("UPDATE tasks SET thread=?,status='active' WHERE id=? AND guild=? AND status='publishing'",(thread.id,tid,guild.id))
        await self.db.enqueue(f"taskbrief:{tid}",'notice',guild.id,{'channel':thread.id,'text':text})
        await self.db.audit(guild.id,task['actor'],'task_published',f"{tid}:{thread.id}")
        return thread

    async def publish_raffle(self,guild,rid,actor):
        from .ui import raffle_view
        cfg,_=await self.db.config(guild.id)
        r=await self.db.begin_publish(guild.id,rid,actor,cfg['raffle_channel'])
        channel=guild.get_channel(r['channel'])
        # The saved publishing state disables buying; the worker enables it only
        # after the message ID is durably bound.
        msg=await channel.send(view=raffle_view(self.bot,r),allowed_mentions=discord.AllowedMentions.none())
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
        msg=await channel.fetch_message(r['message'])
        if msg.author.id!=self.bot.user.id:raise ValueError("Refusing to edit another bot's message.")
        await msg.edit(view=raffle_view(self.bot,r),allowed_mentions=discord.AllowedMentions.none())
        # Update the original public post, so uncertain delivery never creates duplicates.
        await self.db.execute("UPDATE raffles SET announcement_state='done',error='' WHERE id=?",(r['id'],))

    async def job(self,job):
        guild=self.bot.get_guild(job['guild'])
        if not guild:raise ValueError("Server is unavailable.")
        p=job['payload']
        if job['kind']=='role':await self.role_job(guild,p['user'])
        elif job['kind']=='notice':
            channel=guild.get_channel_or_thread(p['channel']) or await self.bot.fetch_channel(p['channel'])
            # Log sends are best-effort with durable retries. Duplicate audit lines after
            # a network timeout are harmless; they never apply financial changes.
            await channel.send(p['text'][:2000],allowed_mentions=discord.AllowedMentions.none())
        elif job['kind']=='taskclose':
            task=await self.db.task(guild.id,p['task'])
            if task['thread']:
                thread=guild.get_thread(task['thread']) or await self.bot.fetch_channel(task['thread'])
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
