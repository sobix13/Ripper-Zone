"""Private local health endpoints and an independent bounded recovery process."""
import asyncio
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path
import aiohttp
from aiohttp import web
from dotenv import load_dotenv
from . import __version__, suite_protocol

log=logging.getLogger(__name__)


def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,sort_keys=True));tmp.chmod(0o600);tmp.replace(path)


async def doctor(bot):
    check=await bot.db.query("PRAGMA quick_check")
    errors=await bot.db.reconcile(bot.guild_id)
    failed=await bot.db.query("SELECT key,attempts,error FROM jobs WHERE guild=? AND state='failed' LIMIT 30",(bot.guild_id,))
    blocks=await bot.db.query("SELECT * FROM financial_blocks WHERE guild=?",(bot.guild_id,))
    ambiguity=await bot.db.query("SELECT id,status FROM raffles WHERE guild=? AND status='publishing'",(bot.guild_id,))
    tasks=await bot.db.query("SELECT id,status FROM tasks WHERE guild=? AND status IN ('creating','publishing')",(bot.guild_id,))
    cfg,rev=await bot.db.config(bot.guild_id);permissions=[]
    guild=bot.get_guild(bot.guild_id)
    if guild:
        try:await bot.service.validate_config(guild,cfg)
        except ValueError as exc:permissions.append(str(exc))
    else:permissions.append("Configured server is unavailable.")
    shared=await asyncio.to_thread(suite_protocol.inspect,bot.registry.path,bot.guild_id) if bot.registry else {}
    return {'version':__version__,'ready':bot.is_ready(),'guild':bot.guild_id,'uptime_seconds':int(time.time()-bot.started),
            'database_check':[list(x.values())[0] for x in check],'ledger_mismatches':errors,'financial_blocks':blocks,
            'settings_revision':rev,'active':cfg['active'],'spin_enabled':cfg['spin_enabled'],'roles_enabled':cfg['roles_enabled'],
            'panel_state':cfg['panel_state'],'failed_jobs':failed,'raffle_publication_review':ambiguity,'task_publication_review':tasks,
            'permission_issues':permissions,'worker_issues':bot.service.issues,'coordination':shared,
            'backup_directory':str(Path(bot.db.path).parent/'backups'),'offsite_backup':'not configured'}


def authorized(request,secret):
    return bool(secret) and hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+secret)


async def start_health(bot):
    secret=os.environ.get('HEALTH_SECRET','')
    if len(secret)<32:raise ValueError("HEALTH_SECRET must contain at least 32 characters.")
    async def health(request):
        ready=bot.is_ready() and bool(bot.get_guild(bot.guild_id))
        age=time.time()-bot.service.last_tick if bot.service.last_tick else time.time()-bot.started
        body={'ok':ready and age<300,'ready':ready,'worker_age_seconds':int(age),'version':__version__}
        return web.json_response(body,status=200 if body['ok'] else 503)
    async def detail(request):
        if not authorized(request,secret):raise web.HTTPUnauthorized()
        return web.json_response(await doctor(bot))
    app=web.Application(client_max_size=1024)
    app.router.add_get('/health',health);app.router.add_get('/doctor',detail)
    runner=web.AppRunner(app,access_log=None);await runner.setup()
    await web.TCPSite(runner,'127.0.0.1',int(os.environ.get('HEALTH_PORT','3040'))).start()
    return runner


class RestartBudget:
    """Persisted across helper restarts, including the manual owner path."""
    def __init__(self,path,clock=time.time):
        self.path=Path(path);self.clock=clock
        if self.path.exists():
            self.data=json.loads(self.path.read_text())
            if not isinstance(self.data.get('restarts'),list):raise ValueError("Invalid recovery budget file. Operator review required.")
        else:self.data={'restarts':[],'paused':False,'message':0,'last_error':''}
        self.data.setdefault('paused',False);self.data.setdefault('message',0)

    def save(self):atomic_json(self.path,self.data)

    def reserve(self):
        now=self.clock();restarts=[x for x in self.data['restarts'] if now-x<900]
        if self.data['paused']:raise ValueError("Automatic recovery is paused by the owner.")
        if len(restarts)>=3 or (restarts and now-restarts[-1]<120):raise ValueError("Restart budget exhausted. Wait before retrying.")
        self.data['restarts']=[*restarts,now];self.save()


class Recovery:
    def __init__(self):
        self.database=Path(os.environ.get('DATABASE_PATH','data/ripper-zone.sqlite3'))
        self.budget=RestartBudget(self.database.parent/'recovery/state.json')
        self.secret=os.environ.get('HEALTH_SECRET','');self.failures=0;self.last_status={}
        if len(self.secret)<32:raise ValueError("Configure HEALTH_SECRET.")
        self.owners={int(x) for x in os.environ.get('OWNER_IDS','').split(',') if x.strip()}
        self.guild=int(os.environ['DISCORD_GUILD_ID']);self.session=None
        self.process_lock=asyncio.Lock();self.last_pulse=0;self.reaction_seen=set()

    def config(self):
        if not self.database.exists():return {}
        c=sqlite3.connect(self.database.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            row=c.execute("SELECT data FROM settings WHERE guild=?",(self.guild,)).fetchone()
            return json.loads(row[0]) if row else {}
        finally:c.close()

    async def restart(self):
        async with self.process_lock:
            if Path(str(self.database)+'.fatal').exists():raise ValueError("Token or privileged intents require operator correction.")
            def integrity():
                if not self.database.exists():return
                c=sqlite3.connect(self.database.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
                try:
                    if c.execute("PRAGMA quick_check").fetchone()[0]!='ok':raise ValueError("Database integrity failed. Automatic restart stopped.")
                finally:c.close()
            await asyncio.to_thread(integrity)
            self.budget.reserve()
            process=await asyncio.create_subprocess_exec('/usr/bin/systemctl','restart','ripper-zone.service',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            try:out,err=await asyncio.wait_for(process.communicate(),45)
            except asyncio.TimeoutError:
                process.kill();await process.wait();raise ValueError("Service restart timed out.")
            if process.returncode:raise ValueError("Service restart failed: "+err.decode(errors='replace')[:180])

    async def api(self,method,path,**kwargs):
        headers={'Authorization':'Bot '+os.environ['DISCORD_TOKEN']}
        async with self.session.request(method,'https://discord.com/api/v10'+path,headers=headers,**kwargs) as response:
            if response.status==429:
                raise ValueError("Discord rate limited the recovery pulse.")
            if response.status>=400:raise ValueError(f"Discord recovery request failed ({response.status}).")
            return await response.json() if response.status!=204 else None

    async def pulse(self):
        cfg=await asyncio.to_thread(self.config)
        channel=int(os.environ.get('RECOVERY_CHANNEL_ID','0')) or cfg.get('log_channel',0)
        if not channel:return
        paused=self.budget.data['paused']
        content=f"Ripper Zone recovery · {'PAUSED' if paused else 'monitoring'}\nMain service: {'healthy' if self.last_status.get('ok') else 'needs attention'}\nOwner controls: 🩺 refresh health · 🔄 bounded restart · ⏸️ pause/resume recovery\nLast check: <t:{int(time.time())}:T>\n{self.budget.data.get('last_error','')[:300]}"
        mid=self.budget.data['message']
        if not mid:
            # Persist an uncertain send marker. Never repeatedly post after timeout.
            if self.budget.data.get('message_state')=='sending':return
            self.budget.data['message_state']='sending';self.budget.save()
            msg=await self.api('POST',f'/channels/{channel}/messages',json={'content':content,'allowed_mentions':{'parse':[]}})
            self.budget.data.update(message=int(msg['id']),message_state='active');self.budget.save();mid=int(msg['id'])
            for emoji in ('🩺','🔄','⏸️'):
                from urllib.parse import quote
                await self.api('PUT',f'/channels/{channel}/messages/{mid}/reactions/{quote(emoji,safe="")}/@me')
        else:
            await self.api('PATCH',f'/channels/{channel}/messages/{mid}',json={'content':content,'allowed_mentions':{'parse':[]}})
        for emoji in ('🩺','🔄','⏸️'):
            from urllib.parse import quote
            code=quote(emoji,safe='')
            users=await self.api('GET',f'/channels/{channel}/messages/{mid}/reactions/{code}?limit=100')
            for user in users:
                uid=int(user['id']);marker=(uid,emoji)
                if uid not in self.owners or marker in self.reaction_seen:continue
                self.reaction_seen.add(marker)
                try:
                    if emoji=='🔄':await self.restart()
                    elif emoji=='⏸️':
                        self.budget.data['paused']=not self.budget.data['paused'];self.budget.save()
                    await self.api('DELETE',f'/channels/{channel}/messages/{mid}/reactions/{code}/{uid}')
                    self.reaction_seen.discard(marker)
                except Exception as exc:
                    self.budget.data['last_error']=str(exc)[:300];self.budget.save()

    async def loop(self):
        while True:
            try:
                async with self.session.get(f"http://127.0.0.1:{os.environ.get('HEALTH_PORT','3040')}/health") as response:
                    self.last_status=await response.json()
                    healthy=response.status==200 and self.last_status.get('ok') is True
            except (aiohttp.ClientError,asyncio.TimeoutError,ValueError):
                healthy=False;self.last_status={'ok':False}
            self.failures=0 if healthy else self.failures+1
            if self.failures>=3 and not self.budget.data['paused']:
                try:await self.restart();self.failures=0;self.budget.data['last_error']=''
                except Exception as exc:self.budget.data['last_error']=str(exc)[:300]
                self.budget.save()
            if time.time()-self.last_pulse>=60:
                self.last_pulse=time.time()
                try:await self.pulse()
                except Exception as exc:
                    log.warning("Recovery pulse: %s",type(exc).__name__)
                    self.budget.data['last_error']=str(exc)[:300];self.budget.save()
            await asyncio.sleep(20)

    async def serve(self):
        async def health(request):
            if not authorized(request,self.secret):raise web.HTTPUnauthorized()
            return web.json_response({'main':self.last_status,'paused':self.budget.data['paused'],'restart_count':len([x for x in self.budget.data['restarts'] if time.time()-x<900]),'last_error':self.budget.data.get('last_error','')})
        async def restart(request):
            if not authorized(request,self.secret):raise web.HTTPUnauthorized()
            # Do not deadlock the main bot waiting for its own restart.
            async def delayed():
                await asyncio.sleep(2)
                try:await self.restart()
                except Exception as exc:self.budget.data['last_error']=str(exc)[:300];self.budget.save()
            asyncio.create_task(delayed())
            return web.json_response({'accepted':True})
        app=web.Application(client_max_size=1024)
        app.router.add_get('/health',health);app.router.add_post('/restart',restart)
        runner=web.AppRunner(app,access_log=None);await runner.setup()
        await web.TCPSite(runner,'127.0.0.1',int(os.environ.get('RECOVERY_PORT','3041'))).start()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            self.session=session
            try:await self.loop()
            finally:await runner.cleanup()


def recovery_main():
    import fcntl
    load_dotenv(os.environ.get('ENV_FILE','.env'))
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    os.umask(0o077)
    path=Path(os.environ.get('DATABASE_PATH','data/ripper-zone.sqlite3')).parent/'recovery'
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=open(path/'process.lock','a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit("Recovery helper already running.")
    try:asyncio.run(Recovery().serve())
    finally:lock.close()


if __name__=='__main__':recovery_main()
