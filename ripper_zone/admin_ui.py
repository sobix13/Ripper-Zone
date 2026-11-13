"""Private moderator controls. Every mutation rechecks current authority."""
import asyncio
import datetime
import json
import time
from pathlib import Path
import discord
from . import ui,sources
from .config import canonical,clean,digest,emoji_key,ident,integer,settings,validate_emoji,display_emoji
from .features import cycle
from .durations import parse_duration,duration_input,format_duration
from .copy import COPY,FIELDS,phrase,validate_copy

async def guard(bot,i,primary=False):
    await ui.defer(i);await bot.authorize(i,primary=primary)

async def invoke(bot,i,name,**values):
    await bot.tree.get_command('ripper').get_command(name).callback(i,**values)

def screen(bot,i,title,text,art='health.png'):
    return ui.Screen(bot,title,text,art,owner=i.user.id)

async def finish(bot,i,title,text):
    cfg,_=await bot.db.config(i.guild_id)
    key={'RC Award Recorded':'award_success','Snapshot Recorded':'snapshot_success','Event Rewards Recorded':'snapshot_success','Task Closed':'task_closed'}.get(title)
    if key:text=phrase(cfg,key)+'\n\n'+text
    s=screen(bot,i,title,text);s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def confirm(bot,i,title,text,action,primary=False):
    await guard(bot,i,primary)
    async def run(j):
        await guard(bot,j,primary);await action(j)
    s=screen(bot,i,title,text);s.button('Confirm',run,discord.ButtonStyle.success);s.button('Cancel',lambda j:home(bot,j));await ui.show(i,s)

async def home(bot,i):
    await guard(bot,i);cfg,rev=await bot.db.config(i.guild_id)
    counts=await bot.db.query("SELECT (SELECT COUNT(*) FROM tasks WHERE guild=? AND status='active') tasks,(SELECT COUNT(*) FROM raffles WHERE guild=? AND status IN ('draft','open','closing')) raffles,(SELECT COUNT(*) FROM jobs WHERE guild=? AND state='failed') failed",(i.guild_id,)*3)
    s=screen(bot,i,'Ripper Zone Administration',f"Program: {'active' if cfg['active'] else 'paused'} · Revision {rev}\nTasks: {counts[0]['tasks']} · Unfinished raffles: {counts[0]['raffles']} · Failed jobs: {counts[0]['failed']}\nChoose an operation. Settings, access, corrections and recovery require a primary administrator.")
    for label,action in [('Community Tasks',tasks),('RC and Members',members),('Snapshots',snapshots),('RC Raffles',raffles),('Settings',settings_page),('Reports',reports),('Health / Recovery',health)]:s.button(label,lambda j,a=action:a(bot,j))
    from .guides import admin_guide
    s.button('Admin Guide',lambda j:admin_guide(bot,j));await ui.show(i,s)

async def settings_page(bot,i):
    await guard(bot,i,True);cfg,rev=await bot.db.config(i.guild_id)
    text=f"Revision {rev}\nProgram: {cfg['active']} · Daily spin: {cfg['spin_enabled']} · Achievement roles: {cfg['roles_enabled']}\n"
    text+='\n'.join(f"{dict(log_channel='Public RC Activity',audit_channel='Private Operations').get(key,key.replace('_',' ').title())}: <#{cfg[key]}>" for key in ('panel_channel','tasks_channel','leaderboard_channel','raffle_channel','log_channel','audit_channel'))
    text+=f"\nAccess role: <@&{cfg['member_role']}>\nModerator roles: "+', '.join(f'<@&{x}>' for x in cfg['manager_roles'])
    s=screen(bot,i,'Settings',text)
    for label,fn in [('Channels and Access',channels),('Reward Reactions',reactions),('Messages and Branding',messages),('Achievement Roles',tiers),('Program Controls',controls),('Settings History',history)]:s.button(label,lambda j,a=fn:a(bot,j))
    s.button('Move Public Message',lambda j:move_public(bot,j))
    s.button('Setup Wizard',lambda j:ui.setup_start(bot,j));s.button('Publish / Refresh Panel',lambda j:bot.publish_panel_action(j))
    s.button('Publish / Refresh Leaders',lambda j:invoke(bot,j,'leaderboard_publish'))
    s.button('Export Settings',lambda j:invoke(bot,j,'settings_export'))
    s.button('Import Settings',lambda j:file_modal(bot,j,'Import Settings',lambda k,a:invoke(bot,k,'settings_import',attachment=a)))
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def channels(bot,i,field=None):
    await guard(bot,i,True);cfg,rev=await bot.db.config(i.guild_id)
    fields=dict(ui.Setup.STEPS);fields.update(audit_channel='Private operations channel (optional)',support_channel='Crew support / ticket channel',spin_role='Extra daily spin role',primary_users='Primary administrators')
    s=screen(bot,i,'Channels and Access','Choose one setting. Existing public message bindings must be recovered or moved explicitly before changing their channel. Access-role changes also reconcile achievement roles.')
    if field is None:
        s.select(discord.ui.Select(placeholder='Choose a setting',options=[discord.SelectOption(label=v,value=k) for k,v in fields.items()]),lambda j,v:channels(bot,j,v[0]))
    else:
        async def save(j,values):
            await guard(bot,j,True)
            ids=[x.id for x in values];cfg[field]=ids if field in ('manager_roles','primary_users') else ids[0] if ids else 0
            await bot.service.configure(j.guild,cfg,rev,j.user.id);await finish(bot,j,'Saved',fields[field]+' updated.')
        if 'channel' in field:item=discord.ui.ChannelSelect(placeholder=fields[field],channel_types=[discord.ChannelType.text],min_values=0 if field in ('audit_channel','support_channel') else 1)
        elif field=='primary_users':item=discord.ui.UserSelect(placeholder=fields[field],min_values=0,max_values=25)
        else:item=discord.ui.RoleSelect(placeholder=fields[field],min_values=0,max_values=25 if field=='manager_roles' else 1)
        s.select(item,save)
    s.button('Settings',lambda j:settings_page(bot,j));await ui.show(i,s)

async def controls(bot,i):
    await guard(bot,i,True);cfg,rev=await bot.db.config(i.guild_id)
    s=screen(bot,i,'Program Controls','Pausing new earnings or purchases does not cancel existing raffle reservations. Existing raffles still settle when accounting is consistent.')
    for key,label in [('active','Program'),('spin_enabled','Daily Spin'),('roles_enabled','Achievement Roles')]:
        async def toggle(j,k=key):
            await guard(bot,j,True);new=dict(cfg);new[k]=not cfg[k]
            await bot.service.configure(j.guild,new,rev,j.user.id);await finish(bot,j,'Program Updated',f'{k}: {new[k]}')
        s.button(f"{label}: {'ON' if cfg[key] else 'OFF'}",toggle)
    s.button('Settings',lambda j:settings_page(bot,j));await ui.show(i,s)

async def reactions(bot,i,key=None,offset=0):
    await guard(bot,i,True);cfg,rev=await bot.db.config(i.guild_id)
    rules={emoji_key(k):v for k,v in cfg['reactions'].items()};items=list(rules.items())[offset:offset+20]
    text='\n'.join(f"{display_emoji(k)} · {v['amount']} RC" for k,v in items)
    s=screen(bot,i,'Reaction Rewards',text+f'\n\nPage {offset//20+1} of {(len(rules)+19)//20} · {len(rules)} configured emojis (up to 100).\nWorks on human messages in all accessible server chats and threads. Only authorized moderators award RC. Each emoji pays once per message, regardless of moderator or re-adds. Task participation rewards are separate.')
    async def form(j,old=None):
        async def save(k,v):
            await bot.authorize(k,primary=True);emoji=emoji_key(validate_emoji(v['emoji']))
            parsed=discord.PartialEmoji.from_str(v['emoji'])
            if parsed.id and not any(e.id==parsed.id for e in k.guild.emojis):raise ValueError('Select an emoji from this server.')
            if emoji in rules and emoji!=old:raise ValueError('This emoji already has a rule.')
            new=dict(rules)
            if old:new.pop(old)
            new[emoji]={'kind':'fixed','amount':integer(int(v['amount']),1,1000)}
            cfg['reactions']=new;await bot.service.configure(k.guild,cfg,rev,k.user.id)
            await finish(bot,k,'Reaction Saved',f"{display_emoji(emoji)} · {new[emoji]['amount']} RC per message.")
        previous=str(next((e for e in j.guild.emojis if old=='custom:'+str(e.id)),old)) if old else ''
        await j.response.send_modal(ui.Form(bot,'Reaction Reward',j.user.id,[('emoji','Emoji',previous),('amount','RC amount (1–1000)',rules.get(old,{}).get('amount',5))],save))
    async def toggle(j):
        await guard(bot,j,True);cfg['reactions_enabled']=not cfg['reactions_enabled']
        await bot.service.configure(j.guild,cfg,rev,j.user.id);await finish(bot,j,'Reactions Updated',f"New rewards: {'ON' if cfg['reactions_enabled'] else 'OFF'}. Already queued reviews retain their original rules.")
    s.button('Reactions: '+('ON' if cfg['reactions_enabled'] else 'OFF'),toggle)
    s.button('Add Reaction',lambda j:form(j))
    options=[]
    for emoji,rule in items:
        custom=next((e for e in i.guild.emojis if emoji=='custom:'+str(e.id)),None)
        options.append(discord.SelectOption(label=f"{custom.name if custom else emoji} · {rule['amount']} RC",value=emoji,emoji=custom or (discord.PartialEmoji(name='reward',id=int(emoji[7:])) if emoji.startswith('custom:') else emoji)))
    s.select(discord.ui.Select(placeholder='Choose a reaction',options=options),lambda j,v:reactions(bot,j,v[0],offset))
    if key in rules:
        s.button('Edit Selected',lambda j:form(j,key))
        async def remove(j):
            await guard(bot,j,True);new=dict(rules);new.pop(key);cfg['reactions']=new
            await bot.service.configure(j.guild,cfg,rev,j.user.id);await finish(bot,j,'Reaction Removed',display_emoji(key))
        s.button('Remove Selected',remove,discord.ButtonStyle.danger)
    s.button('Previous',lambda j:reactions(bot,j,offset=max(0,offset-20)),disabled=not offset)
    s.button('Next',lambda j:reactions(bot,j,offset=offset+20),disabled=offset+20>=len(rules))
    s.button('Settings',lambda j:settings_page(bot,j));await ui.show(i,s)

async def messages(bot,i):
    await guard(bot,i,True);cfg,rev=await bot.db.config(i.guild_id)
    keys={'panel_title':'Public Panel Title','welcome_text':'Welcome Message','about_text':'About','support_text':'Support Instructions','task_footer':'Task Instructions Footer'}
    keys.update({k:k.replace('_',' ').title() for k in COPY})
    s=screen(bot,i,'Messages and Branding','Select a message to edit. The preview shows your saved copy. Public welcome changes refresh the existing panel. Task footer changes refresh task briefs. Mention notifications remain disabled.')
    async def edit(j,values):
        key=values[0]
        async def submit(k,v):
            await bot.authorize(k,primary=True);candidate={**cfg,'messages':dict(cfg['messages'])}
            if key in COPY:candidate['messages'][key]=validate_copy(key,v[key])
            else:candidate[key]=v[key]
            candidate=settings(candidate)
            async def save(n):
                await bot.service.configure(n.guild,candidate,rev,n.user.id)
                await finish(bot,n,'Message Saved','Saved. Reopen private panels to see the new copy. Relevant public displays are queued for refresh. Financial rules are unchanged.')
            await confirm(bot,k,'Message Preview',ui.escape(candidate['messages'][key] if key in COPY else candidate[key]),save,True)
        await j.response.send_modal(ui.Form(bot,keys[key],j.user.id,[(key,keys[key]+(' · '+', '.join(FIELDS[key]) if key in FIELDS else ''),cfg['messages'][key] if key in COPY else cfg[key])],submit))
    s.select(discord.ui.Select(placeholder='Message to edit',options=[discord.SelectOption(label=v,value=k) for k,v in keys.items()]),edit)
    s.button('Settings',lambda j:settings_page(bot,j));await ui.show(i,s)

async def tiers(bot,i,values=None,revision=None,step=0):
    await guard(bot,i,True);cfg,rev=await bot.db.config(i.guild_id)
    revision=rev if revision is None else revision
    values=list(cfg['tiers']) if values is None else values
    if step==3:
        text='\n'.join(f"Tier {n}: <@&{t['role']}> · {t['earned']} earned RC · {t['tasks']} rewarded task cycles · {t['events']} paid events" for n,t in enumerate(values,1))
        s=screen(bot,i,'Review Three Achievement Roles',text+'\nOnly the highest eligible tier remains. Use dedicated roles with no server permissions. All three requirements apply.')
        async def save(j,enabled):
            await guard(bot,j,True);cfg.update(tiers=values,roles_enabled=enabled)
            await bot.service.configure(j.guild,cfg,revision,j.user.id);await finish(bot,j,'Roles Saved','Role reconciliation is queued.')
        s.button('Save Disabled',lambda j:save(j,False));s.button('Save and Enable',lambda j:save(j,True),discord.ButtonStyle.success)
    else:
        s=screen(bot,i,f'Achievement Tier {step+1}/3','Choose a dedicated achievement role. Do not choose Ripper, OG, staff or another bot’s role. Task count means rewarded task cycles; event count means paid Rumble / ordinary-raffle participation.')
        async def choose(j,v):
            old=values[step] if len(values)>step else dict(earned=(step+1)*100,tasks=0,events=0)
            async def submit(k,data):
                await bot.authorize(k,primary=True);tier=dict(role=v[0].id,**{key:integer(int(data[key]),0) for key in ('earned','tasks','events')})
                new=values[:step]+[tier]
                await tiers(bot,k,new,revision,step+1)
            await j.response.send_modal(ui.Form(bot,f'Tier {step+1} Requirements',j.user.id,[(k,label,old[k]) for k,label in [('earned','Minimum lifetime earned RC'),('tasks','Minimum rewarded task cycles'),('events','Minimum paid events')]],submit))
        s.select(discord.ui.RoleSelect(placeholder='Achievement role'),choose)
    s.button('Skip / Disable Roles',lambda j:ui.skip_roles(bot,j));s.button('Settings',lambda j:settings_page(bot,j));await ui.show(i,s)

async def picker(bot,i,title,sql,params,action,offset=0):
    await guard(bot,i);rows=await bot.db.query(sql+' LIMIT 10 OFFSET ?',(*params,offset))
    s=screen(bot,i,title,'Select an item below.' if rows else 'No items on this page.')
    if rows:s.select(discord.ui.Select(placeholder='Choose an item',options=[discord.SelectOption(label=f"#{r['id']} {r.get('title',r.get('status',''))}"[:100],value=str(r['id'])) for r in rows]),lambda j,v:action(j,int(v[0])))
    s.button('Previous',lambda j:picker(bot,j,title,sql,params,action,max(0,offset-10)),disabled=offset==0)
    s.button('Next',lambda j:picker(bot,j,title,sql,params,action,offset+10),disabled=len(rows)<10)
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def tasks(bot,i):
    await guard(bot,i);s=screen(bot,i,'Community Tasks','Manage active, past and publication-review tasks. Each task has its own reviewed contributions, cycles and reward history.')
    s.button('New Task',lambda j:task_create(bot,j))
    for label,where in [('Active',"status='active'"),('Past',"status='closed'"),('Publication Review',"status IN ('creating','publishing')")]:
        s.button(label,lambda j,w=where:picker(bot,j,'Community Tasks',f'SELECT * FROM tasks WHERE guild=? AND {w} ORDER BY id DESC',(j.guild_id,),lambda k,t:task_detail(bot,k,t)))
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def task_create(bot,i,template=None):
    await guard(bot,i);s=screen(bot,i,'New Community Task','Choose recurrence. Daily cycles reset at UTC midnight. Weekly cycles start from the creation date at UTC midnight.')
    async def choose(j,period):
        async def submit(k,v):
            await bot.authorize(k);duration=parse_duration(v['duration'],allow_none=True)
            tid=await bot.db.create_task(k.guild_id,k.user.id,v['title'],v['body'],int(v['reward']),period,parse_duration(v['cooldown'],allow_none=True),int(time.time())+duration if duration else 0)
            await bot.service.publish_task(k.guild,tid);await task_detail(bot,k,tid)
        t=template or {};fields=[('title','Task title',t.get('title','')),('body','Instructions',t.get('body','')),('reward','Base RC per member per cycle',t.get('reward',5)),('cooldown','Cooldown: 30m or none (max 90d)',duration_input(t.get('cooldown',0))),('duration','Open for: 2d or none (max 90d)','3d')]
        await j.response.send_modal(ui.Form(bot,'New Community Task',j.user.id,fields,submit))
    for label,p in [('One-time',0),('Daily',86400),('Weekly',604800)]:s.button(label,lambda j,p=p:choose(j,p))
    s.button('Tasks',lambda j:tasks(bot,j));await ui.show(i,s)

async def task_detail(bot,i,tid):
    await guard(bot,i);t=await bot.db.task(i.guild_id,tid);cy=cycle(t,min(int(time.time()),t['ends'] or int(time.time())))
    stats=(await bot.db.query('SELECT COUNT(*) posts,COUNT(DISTINCT user) people FROM task_messages WHERE task=? AND cycle=?',(tid,cy)))[0]
    text=f"{ui.escape(t['title'])}\n{ui.escape(t['body'])[:1800]}\nStatus: {t['status']} · Thread: <#{t['thread']}>\nBase: {t['reward']} RC · Cycle {cy} · Cooldown: {format_duration(t['cooldown'])}\nDeadline: "+(f"<t:{t['ends']}:F>" if t['ends'] else 'none')+f"\nRecorded posts: {stats['posts']} · Contributors: {stats['people']}\nRecorded presence does not mean individual content approval. Review recipients before paying a cycle snapshot."
    s=screen(bot,i,f'Task #{tid}',text,'tasks.png')
    async def edit(j,timing=False):
        async def save(k,v):
            await bot.authorize(k);changes={key:parse_duration(value,allow_none=True) if key=='cooldown' else int(value) if key=='reward' else value for key,value in v.items()}
            await bot.db.edit_task(k.guild_id,tid,changes,k.user.id,digest(t));await finish(bot,k,'Task Saved','Refreshing the original brief is queued.')
        fields=[('reward','Base RC (fixed after participation)',t['reward']),('cooldown','Cooldown: 30m or none (max 90d)',duration_input(t['cooldown']))] if timing else [('title','Title',t['title']),('body','Instructions',t['body'])]
        await j.response.send_modal(ui.Form(bot,'Edit Task',j.user.id,fields,save))
    s.button('Set Deadline',lambda j:deadline_form(bot,j,t))
    s.button('Edit Details',edit);s.button('Timing and Reward',lambda j:edit(j,True));s.button('Duplicate',lambda j:task_create(bot,j,t))
    s.button('Participants',lambda j:picker(bot,j,'Task Contributors','SELECT DISTINCT user id FROM task_messages WHERE task=? AND cycle=? ORDER BY user',(tid,cy),lambda k,u:member_account(bot,k,u)))
    s.button('Extra RC Bonus',lambda j:review_member(bot,j,tid,cy,quality=True))
    s.button('Cycle Snapshot',lambda j:task_snapshot_form(bot,j,tid,cy));s.button('Reviewed Contribution',lambda j:review_member(bot,j,tid,cy))
    s.button('Reset Member Cooldown',lambda j:select_member(bot,j,'Reset Member Cooldown',lambda k,ids:invoke(bot,k,'task_manage',action='reset_cooldown',task_id=tid,value=ids[0]),1))
    s.button('Recover Reactions',lambda j:reconcile_reactions(bot,j,tid));s.button('Refresh Brief',lambda j:refresh_task(bot,j,tid))
    if t['thread']:s.button('Recover Brief Binding',lambda j:brief_binding(bot,j,tid))
    if t['status'] in ('creating','publishing'):s.button('Bind Thread',lambda j:binding_form(bot,j,'task',tid))
    if t['status']=='active':
        async def close(j):
            await bot.db.close_task(j.guild_id,tid,j.user.id);await finish(bot,j,'Task Closed','Thread locking and archival are queued.')
        s.button('Close and Archive',lambda j:confirm(bot,j,'Close Task',f'Close task #{tid}? Existing accepted cycles remain reviewable.',close),discord.ButtonStyle.danger)
    s.button('Tasks',lambda j:tasks(bot,j));await ui.show(i,s)

async def refresh_task(bot,i,tid):
    await guard(bot,i);await bot.db.enqueue(f'tasksync:{tid}','task_sync',i.guild_id,{'task':tid});await finish(bot,i,'Refresh Queued','The original task brief will be synchronized.')

async def task_snapshot_form(bot,i,tid,cy,offset=0):
    await guard(bot,i);t=await bot.db.task(i.guild_id,tid)
    s=screen(bot,i,'Choose Task Cycle','Choose a recorded reward period. Task participation rewards are shared with individual reviews. Fixed reaction rewards are separate.')
    options=[discord.SelectOption(label=f'Cycle {n}'+(' · current / final' if n==cy else ''),value=str(n)) for n in range(cy-offset,max(-1,cy-offset-25),-1)]
    async def selected(j,v):
        await invoke(bot,j,'task_snapshot',task_id=tid,cycle_id=int(v[0]),kind='base',quality_amount=5)
    s.select(discord.ui.Select(placeholder='Task reward cycle',options=options),selected)
    s.button('More Recent Cycles',lambda j:task_snapshot_form(bot,j,tid,cy,max(0,offset-25)),disabled=not offset)
    s.button('Earlier Cycles',lambda j:task_snapshot_form(bot,j,tid,cy,offset+25),disabled=cy-offset<25)
    s.button('Task',lambda j:task_detail(bot,j,tid));await ui.show(i,s)

async def select_member(bot,i,title,action,maximum=25):
    await guard(bot,i);s=screen(bot,i,title,'Choose members from this server.')
    s.select(discord.ui.UserSelect(placeholder='Choose members',max_values=maximum),lambda j,v:action(j,[x.id for x in v]))
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def review_member(bot,i,tid,cy,quality=False):
    async def selected(j,ids):
        async def submit(k,v):
            await invoke(bot,k,'task_reward',task_id=tid,cycle_id=int(v['cycle']),member=discord.Object(ids[0]),kind='quality' if quality else 'base',quality_amount=int(v.get('amount',5)),reason=v['reason'])
        await j.response.send_modal(ui.Form(bot,'Reviewed Contribution',j.user.id,[('cycle','Reviewed cycle',cy),('reason','Review reason','Extra extra RC bonus' if quality else 'Reviewed task contribution')]+([('amount','Extra quality RC',5)] if quality else []),submit))
    await select_member(bot,i,'Review Task Contribution',selected,1)

async def reconcile_reactions(bot,i,tid,hours=None):
    if hours is None:
        async def submit(j,v):await reconcile_reactions(bot,j,tid,integer(int(v['hours']),1,168))
        return await i.response.send_modal(ui.Form(bot,'Recover Task Reactions',i.user.id,[('hours','Hours back (1–168); max 200 messages',24)],submit))
    await guard(bot,i);t=await bot.db.task(i.guild_id,tid)
    thread=i.guild.get_thread(t['thread']) or await bot.fetch_channel(t['thread']);examined=queued=0;members={}
    async with asyncio.timeout(90):
        async for msg in thread.history(limit=200,after=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=hours)):
            examined+=1
            for reaction in msg.reactions:
                async for user in reaction.users(limit=None):
                    if user.bot:continue
                    cfg,_=await bot.db.config(i.guild_id)
                    if user.id not in members:members[user.id]=await bot.service.eligible(i.guild,user.id)
                    observed=members[user.id]
                    if observed and (user.id in (set(bot.owners)|set(cfg['primary_users'])|{i.guild.owner_id}) or set(cfg['manager_roles'])&{r.id for r in observed.roles}):
                        from types import SimpleNamespace
                        await bot.on_raw_reaction_add(SimpleNamespace(guild_id=i.guild_id,channel_id=thread.id,message_id=msg.id,user_id=user.id,emoji=reaction.emoji));queued+=1
    await finish(bot,i,'Reaction Recovery Queued',f'Examined {examined} messages from the last {hours} hours (limit 200). Queued {queued} moderator reactions. Existing reaction rewards are not paid again. Task participation reviews remain separate.')

async def members(bot,i):
    await guard(bot,i);s=screen(bot,i,'RC and Members','Choose members to award RC, inspect their account or review a recorded reward.')
    s.button('Award RC',lambda j:award_members(bot,j));s.button('Member Account',lambda j:select_member(bot,j,'Member Account',lambda k,ids:member_account(bot,k,ids[0]),1))
    s.button('Snapshots',lambda j:snapshots(bot,j));s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def award_members(bot,i):
    async def selected(j,ids):
        async def submit(k,v):
            await bot.authorize(k);amount=integer(int(v['amount']),1,1000);reason=clean(v['reason'],500);op=str(k.id)
            cfg,_=await bot.db.config(k.guild_id);people={}
            for uid in ids:
                member=await bot.service.eligible(k.guild,uid,cfg['member_role'])
                if member:people[uid]=member.display_name
            async def pay(n):
                count=await bot.db.award(n.guild_id,people,amount,n.user.id,reason,op)
                await finish(bot,n,'RC Award Recorded',f'{count} new awards · {amount} RC each · Receipt {op}.')
            await confirm(bot,k,'Review RC Award',f'Eligible: {len(people)} / {len(ids)}\nEach: {amount} RC · Total: {amount*len(people)} RC\n{ui.escape(reason)}',pay)
        await j.response.send_modal(ui.Form(bot,'Award RC',j.user.id,[('amount','RC per member',5),('reason','Reason','Community contribution')],submit))
    await select_member(bot,i,'Award RC',selected)

async def member_account(bot,i,uid,offset=0):
    await guard(bot,i);a=await bot.db.account(i.guild_id,uid);rows=await bot.db.history(i.guild_id,uid,offset)
    s=screen(bot,i,'Member Account',f"<@{uid}>\nAvailable: {a['available']} RC · Reserved: {a['reserved']} RC · Earned: {a['earned']} RC\nTasks: {a['tasks']} · Events: {a['events']}\n"+'\n'.join(f"#{r['id']} {r['da']:+} RC · {ui.escape(r['reason'])[:110]}" for r in rows))
    async def correct(j):
        async def submit(k,v):await invoke(bot,k,'correction',member=discord.Object(uid),amount=int(v['amount']),reason=v['reason'])
        await j.response.send_modal(ui.Form(bot,'Correct Member RC',j.user.id,[('amount','Signed RC correction',0),('reason','Reason','')],submit))
    s.button('Correction',correct)
    if rows:
        async def revoke(j,values):
            async def submit(k,v):await invoke(bot,k,'revoke_reward',ledger_id=int(values[0]),reason=v['reason'])
            await j.response.send_modal(ui.Form(bot,'Revoke Invalid Reward',j.user.id,[('reason','Reason','')],submit))
        s.select(discord.ui.Select(placeholder='Select a reward to revoke',options=[discord.SelectOption(label=f"#{r['id']} {r['de']} earned RC"[:100],value=str(r['id'])) for r in rows if r['de']>0]) ,revoke) if any(r['de']>0 for r in rows) else None
    s.button('Previous',lambda j:member_account(bot,j,uid,max(0,offset-10)),disabled=not offset);s.button('Next',lambda j:member_account(bot,j,uid,offset+10),disabled=len(rows)<10)
    s.button('Members',lambda j:members(bot,j));await ui.show(i,s)

async def raffles(bot,i):
    await guard(bot,i);s=screen(bot,i,'RC Raffle Management','Draft rules remain editable until publication. Published financial rules are fixed.')
    s.button('New RC Raffle',lambda j:raffle_create(bot,j))
    s.button('Manage Raffles',lambda j:picker(bot,j,'RC Raffles','SELECT id,status FROM raffles WHERE guild=? ORDER BY id DESC',(j.guild_id,),lambda k,r:raffle_detail(bot,k,r)))
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def raffle_create(bot,i):
    async def submit(j,v):
        await bot.authorize(j)
        await raffle_rules(bot,j,dict(title=clean(v['title'],100),prize=clean(v['body'],1500)),None)
    await i.response.send_modal(ui.Form(bot,'New RC Raffle',i.user.id,[('title','Raffle title',''),('body','Prize and claim instructions','')],submit))

async def raffle_rules(bot,i,data,rid):
    await guard(bot,i);s=screen(bot,i,'Raffle Draft','Set ticket rules in separate fields, then review before publishing.')
    async def form(j):
        async def submit(k,v):
            await bot.authorize(k);spec={**data,**{x:int(v[x]) for x in ('price','max_tickets','winners','minimum')}}
            spec['ends']=int(time.time())+integer(int(v['hours']),1,2160)*3600
            if rid is None:r=await bot.db.create_raffle(k.guild_id,k.user.id,spec)
            else:
                await bot.db.edit_raffle(k.guild_id,rid,spec,k.user.id,digest(data));r=rid
            await raffle_detail(bot,k,r)
        await j.response.send_modal(ui.Form(bot,'RC Raffle Ticket Rules',j.user.id,[(k,label,data.get(k,d)) for k,label,d in [('price','RC per ticket',10),('max_tickets','Ticket cap per member',10),('winners','Maximum winners',1),('minimum','Minimum eligible members',3),('hours','Duration hours',24)]],submit))
    s.button('Set Ticket Rules',form);s.button('Raffles',lambda j:raffles(bot,j));await ui.show(i,s)

async def raffle_detail(bot,i,rid):
    await guard(bot,i);r=await bot.db.raffle(i.guild_id,rid);spec=r['spec']
    prizes=await bot.db.query('SELECT * FROM prizes WHERE raffle=? ORDER BY round,user',(rid,))
    text=f"{ui.escape(spec['title'])}\n{spec['prize']}\nStatus: {r['status']}\n{spec['price']} RC per ticket · Cap {spec['max_tickets']}\nUp to {spec['winners']} winners · Minimum {spec['minimum']} people\nEnds <t:{spec['ends']}:F>\n"+'\n'.join(f"<@{p['user']}>: {p['state']} (round {p['round']})" for p in prizes)+f"\n{ui.escape(r['error'])}"
    s=screen(bot,i,f'RC Raffle #{rid}',text,'raffles.png')
    async def operate(j,action):
        if action in ('cancel','replace','close'):
            async def submit(k,v):
                async def run(n):await invoke(bot,n,'raffle_manage',action=action,raffle_id=rid,reason=v['reason'])
                await confirm(bot,k,'Confirm Raffle Operation',f'{action.title()} raffle #{rid}. Reason: {ui.escape(v["reason"])}',run)
            await j.response.send_modal(ui.Form(bot,'Raffle Operation',j.user.id,[('reason','Reason','Administrator reviewed operation')],submit))
        else:await invoke(bot,j,'raffle_manage',action=action,raffle_id=rid)
    if r['status']=='draft':
        s.button('Edit Ticket Rules',lambda j:raffle_rules(bot,j,spec,rid))
        async def details(j):
            async def save(k,v):
                await bot.authorize(k);new={**spec,'title':v['title'],'prize':v['body']};await bot.db.edit_raffle(k.guild_id,rid,new,k.user.id,digest(spec));await raffle_detail(bot,k,rid)
            await j.response.send_modal(ui.Form(bot,'Edit Raffle Details',j.user.id,[('title','Title',spec['title']),('body','Prize / claim instructions',spec['prize'])],save))
        s.button('Edit Details',details);s.button('Publish Public Raffle',lambda j:confirm(bot,j,'Publish RC Raffle',text,lambda k:operate(k,'publish')))
    if r['status'] in ('draft','publishing','open'):s.button('Cancel and Refund',lambda j:operate(j,'cancel'))
    if r['status'] in ('open','closing'):s.button('Close / Retry Draw',lambda j:operate(j,'close'))
    if r['message']:s.button('Refresh Public Post',lambda j:operate(j,'refresh'))
    if r['status']=='publishing':s.button('Recover Message Binding',lambda j:binding_form(bot,j,'raffle',rid))
    if r['rounds']:s.button('Download Draw Proof',lambda j:ui.proof(bot,j,rid))
    if any(p['state']=='forfeited' for p in prizes):s.button('Replace Forfeited Prizes',lambda j:operate(j,'replace'))
    pending=[p for p in prizes if p['state'] in ('pending','claimed')]
    if pending:
        async def select(j,v):
            uid=int(v[0]);await guard(bot,j)
            page=screen(bot,j,'Prize Status',f'Raffle #{rid} · <@{uid}>')
            for label,action in [('Record Delivery','delivered'),('Forfeit Prize','forfeit')]:
                async def choose(k,a=action):
                    async def submit(n,data):await invoke(bot,n,'raffle_manage',action=a,raffle_id=rid,member=discord.Object(uid),reason=data['reason'])
                    await k.response.send_modal(ui.Form(bot,'Prize Status',k.user.id,[('reason','Reason / delivery reference','')],submit))
                page.button(label,choose)
            await ui.show(j,page)
        s.select(discord.ui.Select(placeholder='Manage a prize',options=[discord.SelectOption(label=f"Member {p['user']} · {p['state']}",value=str(p['user'])) for p in pending]),select)
    s.button('Raffles',lambda j:raffles(bot,j));await ui.show(i,s)

async def reports(bot,i):
    await guard(bot,i);s=screen(bot,i,'Reports','Download records as CSV. Formula-like member text is escaped. RC accounting records keep the actor and reason.')
    for kind in ('leaderboard','ledger','tasks','raffles','audit'):s.button(kind.title()+' CSV',lambda j,k=kind:invoke(bot,j,'report',kind=k))
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def history(bot,i,offset=0):
    await guard(bot,i,True);rows=(await bot.db.config_history(i.guild_id))[offset:offset+10]
    s=screen(bot,i,'Settings History','Select a revision to preview its restoration. Current role/channel permissions are checked again. Runtime message bindings are retained.')
    if rows:s.select(discord.ui.Select(placeholder='Configuration revision',options=[discord.SelectOption(label=f"#{r['id']} · saved by {r['actor']}",value=str(r['id'])) for r in rows]),lambda j,v:invoke(bot,j,'settings_history',history_id=int(v[0])))
    s.button('Previous',lambda j:history(bot,j,max(0,offset-10)),disabled=not offset)
    s.button('Next',lambda j:history(bot,j,offset+10),disabled=len(rows)<10)
    s.button('Settings',lambda j:settings_page(bot,j));await ui.show(i,s)

async def health(bot,i):
    await guard(bot,i)
    from .operations import doctor
    data=await doctor(bot)
    text=f"Version: {data['version']} · Ready: {data['ready']}\nSQLite: {', '.join(data['database_check'])}\nLedger mismatches: {len(data['ledger_mismatches'])} · Failed jobs: {len(data['failed_jobs'])}\nPanel: {data['panel_state']}\n"+'\n'.join(data['permission_issues'])+'\n'+'\n'.join(f"{k}: {v}" for k,v in data['worker_issues'].items())
    text+=f"\nPublic RC channel: <#{data['public_rc_channel']}>\nRC receipts: "+', '.join(f'{state}: {count}' for state,count in data['receipt_delivery'].items())
    text+='\nFailed jobs:\n'+'\n'.join(f"{r['key']}: {r['error'][:100]}" for r in data['failed_jobs'][:8])
    text+='\nPending task publications: '+', '.join(str(r['id']) for r in data['task_publication_review'])
    text+='\nPending raffle publications: '+', '.join(str(r['id']) for r in data['raffle_publication_review'])
    folder=Path(bot.db.path).parent/'backups';latest=max(folder.glob('*.sqlite3'),key=lambda p:p.stat().st_mtime,default=None)
    text+='\nLatest local backup: '+(f'<t:{int(latest.stat().st_mtime)}:F>' if latest else 'none')+'\nOffsite backup: not configured'
    s=screen(bot,i,'Health and Recovery',text)
    s.button('Check Rumble Connection',lambda j:event_list(bot,j,'rumble'));s.button('Check Raffle Connection',lambda j:event_list(bot,j,'raffle'))
    s.button('Download Details',lambda j:bot.doctor_action(j))
    async def retry_receipts(j):
        await guard(bot,j,True)
        count=await bot.db.execute("UPDATE jobs SET state='pending',attempts=0,next_at=0,error='' WHERE guild=? AND kind='notice' AND key LIKE 'notice:%' AND state='failed'",(j.guild_id,))
        await finish(bot,j,'RC Receipts Retried',f'{count} failed receipts queued. No RC awards were repeated.')
    s.button('Retry RC Receipts',retry_receipts)
    for action,label in [('retry_jobs','Retry Failed Jobs'),('clear_accounting_pause','Verify and Resume Accounting'),('restart','Bounded Restart'),('mark_panel_missing','Verify Deleted Panel')]:
        s.button(label,lambda j,a=action:confirm(bot,j,'Confirm Recovery',a.replace('_',' '),lambda k:invoke(bot,k,'recovery',action=a),True))
    async def backup(j):
        await guard(bot,j,True);target=folder/f'manual-{int(time.time())}.sqlite3';await bot.db.backup(target);await finish(bot,j,'Backup Verified','A private SQLite backup was saved on the VPS.')
    s.button('Backup Now',backup);s.button('Task Recovery',lambda j:tasks(bot,j));s.button('Raffle Recovery',lambda j:raffles(bot,j))
    for kind,label in [('panel','Recover Panel Binding'),('leaderboard','Recover Leaderboard Binding')]:s.button(label,lambda j,k=kind:binding_form(bot,j,k))
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def binding_form(bot,i,kind,object_id=0):
    async def submit(j,v):
        if kind in ('panel','leaderboard'):await invoke(bot,j,'panel_recover',kind=kind,message_id=v['id'])
        elif kind=='task':await invoke(bot,j,'task_manage',action='bind_thread',task_id=object_id,value=ident(v['id']))
        else:await invoke(bot,j,'raffle_manage',action='bind_message',raffle_id=object_id,message_id=v['id'])
    await i.response.send_modal(ui.Form(bot,'Publication Binding Recovery',i.user.id,[('id','Existing message / thread ID','')],submit))

class Upload(discord.ui.Modal):
    def __init__(self,bot,owner,title,callback):
        super().__init__(title=title,timeout=600);self.bot=bot;self.owner=owner;self.action=callback
        self.upload=discord.ui.FileUpload(min_values=1,max_values=1)
        self.add_item(discord.ui.Label(text='JSON settings file',component=self.upload))
    async def on_submit(self,i):
        if i.user.id!=self.owner:return await ui.reply(i,content='Open your own form.')
        try:await self.action(i,self.upload.values[0])
        except Exception as exc:self.bot.report_error(exc);await ui.failure(i,exc)

async def file_modal(bot,i,title,callback):await i.response.send_modal(Upload(bot,i.user.id,title,callback))

async def snapshots(bot,i):
    await guard(bot,i);s=screen(bot,i,'Participation Snapshots','Choose a source. Preview recipients and the total before confirmation. Repeated finalized event imports never pay twice.')
    s.button('Rumble Event',lambda j:event_list(bot,j,'rumble'));s.button('Ordinary Raffle Event',lambda j:event_list(bot,j,'raffle'))
    s.button('Voice / Stage Call',lambda j:voice_snapshot(bot,j))
    s.button('Task Cycle',lambda j:tasks(bot,j));s.button('Channel / Thread Window',lambda j:window_snapshot(bot,j));s.button('Message Reactions',lambda j:reaction_snapshot(bot,j))
    s.button('Administration',lambda j:home(bot,j));await ui.show(i,s)

async def source_request(source,event=None):
    import os,aiohttp
    params={'source':source}
    if event is not None:params['event']=str(ident(event))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.get('http://127.0.0.1:'+os.getenv('RECOVERY_PORT','3041')+'/events',params=params,headers={'Authorization':'Bearer '+os.getenv('HEALTH_SECRET','')}) as response:
            data=await response.json()
            if response.status!=200:raise ValueError(data.get('error','Event source unavailable. Check Health / Recovery and source connection.'))
            return data

async def event_list(bot,i,source):
    await guard(bot,i);rows=await source_request(source)
    s=screen(bot,i,source.title()+' Finalized Events','Choose an event. Source data are read only by the local helper. No file upload is needed.')
    if rows:s.select(discord.ui.Select(placeholder='Finalized event',options=[discord.SelectOption(label=f"{source.title()} #{r['id']}",value=str(r['id'])) for r in rows]),lambda j,v:event_amount(bot,j,source,int(v[0])))
    else:s.box.add_item(discord.ui.TextDisplay('No finalized events found.'))
    s.button('Snapshots',lambda j:snapshots(bot,j));await ui.show(i,s)

async def event_amount(bot,i,source,event):
    async def submit(j,v):
        await bot.authorize(j);amount=integer(int(v['amount']),1,1000);data=sources.validate(await source_request(source,event),j.guild_id)
        async def pay(k):
            count=await bot.db.snapshot(k.guild_id,source,data['event'],data['participants'],amount,k.user.id)
            await finish(bot,k,'Event Rewards Recorded',f'{count} new participants · {amount} RC each · {source} #{event}.')
        await confirm(bot,j,'Event Participation Preview',f"{source} #{event}\nFinalized eligible participants, including non-winners: {len(data['participants'])}\n{amount} RC each · Total {amount*len(data['participants'])} RC\nRoster checksum: {data['hash']}\nOrdinary raffle uses its original eligible pool. Rumble uses its complete final ranking.",pay)
    await i.response.send_modal(ui.Form(bot,'Event Participation Reward',i.user.id,[('amount','RC per participant',5)],submit))

async def window_snapshot(bot,i):
    await guard(bot,i);s=screen(bot,i,'Channel / Thread Snapshot','Choose a channel. A thread link is also accepted in Message Reactions for a reaction snapshot. Only human authors in the scanned window are included.')
    async def selected(j,values):
        channel_id=values[0].id
        async def submit(k,v):
            channel=k.guild.get_channel_or_thread(channel_id) or await bot.fetch_channel(channel_id)
            if channel.guild.id!=k.guild_id:raise ValueError('Wrong server.')
            await bot.authorize(k);hours=integer(int(v['hours']),1,720);amount=integer(int(v['amount']),1,1000);reason=clean(v['reason'],500);people={};scanned=0
            import datetime
            after=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=hours)
            async with asyncio.timeout(90):
                async for msg in channel.history(limit=5000,after=after):
                    scanned+=1
                    if not msg.author.bot:people[msg.author.id]=msg.author.display_name
            if scanned>=5000:raise ValueError('Scan limit reached. Choose a smaller time window; no awards were made.')
            await snapshot_people(bot,k,people,amount,reason,f'Channel {channel.id}, last {hours} hours; {scanned} messages')
        await j.response.send_modal(ui.Form(bot,'Channel Window',j.user.id,[('hours','Hours back (1–720)',24),('amount','RC per human author',5),('reason','Reason','Community participation')],submit))
    s.select(discord.ui.ChannelSelect(placeholder='Channel or active thread',channel_types=[discord.ChannelType.text,discord.ChannelType.public_thread]),selected)
    s.button('Snapshots',lambda j:snapshots(bot,j));await ui.show(i,s)

async def reaction_snapshot(bot,i):
    async def submit(j,v):
        await bot.authorize(j)
        import re
        match=re.fullmatch(r'https://(?:discord.com|discordapp.com)/channels/(\d+)/(\d+)/(\d+)',v['url'])
        if not match or int(match[1])!=j.guild_id:raise ValueError('Paste a message link from this server.')
        channel=j.guild.get_channel_or_thread(int(match[2])) or await bot.fetch_channel(int(match[2]))
        if channel.guild.id!=j.guild_id:raise ValueError('Wrong server.')
        msg=await channel.fetch_message(int(match[3]));key=emoji_key(v['emoji']);reaction=next((r for r in msg.reactions if emoji_key(r.emoji)==key),None)
        if reaction is None:raise ValueError('That reaction is not on this message.')
        people={}
        async with asyncio.timeout(90):
            async for user in reaction.users(limit=None):
                if not user.bot:people[user.id]=user.display_name
                if len(people)>5000:raise ValueError('Snapshot exceeds 5000 participants.')
        await snapshot_people(bot,j,people,integer(int(v['amount']),1,1000),clean(v['reason'],500),f'Message {msg.id}; reaction {key}')
    await i.response.send_modal(ui.Form(bot,'Message Reaction Snapshot',i.user.id,[('url','Discord message link',''),('emoji','Emoji','✅'),('amount','RC per participant',5),('reason','Reason','Community participation')],submit))

async def snapshot_people(bot,i,people,amount,reason,source):
    if not people:raise ValueError('No human participants found.')
    op=str(i.id)
    async def pay(j):
        count=await bot.db.award(j.guild_id,people,amount,j.user.id,reason,op)
        await finish(bot,j,'Snapshot Recorded',f'{count} new awards · Receipt {op}.')
    cfg,_=await bot.db.config(i.guild_id)
    source=phrase(cfg,'snapshot_preview')+'\n'+source
    roster='\n'.join(f'<@{uid}>' for uid in list(people)[:25])
    await confirm(bot,i,'Review Participation Snapshot',f'{source}\nHuman participants: {len(people)}\n{amount} RC each · Total {amount*len(people)} RC\n{ui.escape(reason)}\n{roster}\nThis is a new manual snapshot operation. Reusing this confirmation does not pay twice. Starting another window/reaction snapshot is a separate award.',pay)


async def move_public(bot,i,kind=None):
    await guard(bot,i,True);cfg,revision=await bot.db.config(i.guild_id)
    s=screen(bot,i,'Move Public Message','Choose the public message and its new channel. The existing post becomes a link to its new location after successful publication. A timed-out send stays in binding recovery; it is never blindly repeated.')
    if kind is None:
        s.button('Member Panel',lambda j:move_public(bot,j,'panel'));s.button('Leaderboard',lambda j:move_public(bot,j,'leaderboard'))
    else:
        async def choose(j,v):
            channel_id=v[0].id
            async def run(k):
                msg=await bot.service.move_public(k.guild,kind,channel_id,k.user.id,revision)
                await finish(bot,k,'Public Message Moved',msg.jump_url)
            await confirm(bot,j,'Confirm Channel Move',f'Move {kind} to <#{channel_id}>?',run,True)
        s.select(discord.ui.ChannelSelect(placeholder='New public channel',channel_types=[discord.ChannelType.text]),choose)
    s.button('Settings',lambda j:settings_page(bot,j));await ui.show(i,s)


async def message_award_form(bot,i,message):
    async def submit(j,v):
        await bot.authorize(j)
        if not message.guild or message.guild.id!=j.guild_id or message.author.bot:raise ValueError('Select a human contribution in this server.')
        cfg,_=await bot.db.config(j.guild_id);member=await bot.service.eligible(j.guild,message.author.id,cfg['member_role'])
        if not member:raise ValueError('The author no longer meets community access requirements.')
        amount=integer(int(v['amount']),1,1000);reason=clean(v['reason'],500);op='message:'+str(j.id)
        async def pay(k):
            count=await bot.db.award(k.guild_id,{member.id:member.display_name},amount,k.user.id,reason,op)
            await finish(bot,k,'RC Award Recorded',f'{count} extra manual awards · {amount} RC · Receipt {op}.')
        await confirm(bot,j,'Review Message Award',f'<@{member.id}> · {amount} RC\nThis is an extra manual award, separate from a task base reward.\n{ui.escape(reason)}',pay)
    await i.response.send_modal(ui.Form(bot,'Award RC for a Message',i.user.id,[('amount','Extra manual RC bonus',5),('reason','Reason','Useful community contribution')],submit))


async def deadline_form(bot,i,task):
    import datetime
    old=datetime.datetime.fromtimestamp(task['ends'],datetime.timezone.utc).strftime('%Y-%m-%d %H:%M') if task['ends'] else 'none'
    async def submit(j,v):
        await bot.authorize(j)
        try:
            value=v['deadline'].strip()
            if value.lower()=='none':ends=0
            elif ' ' in value and '-' in value:ends=int(datetime.datetime.strptime(value,'%Y-%m-%d %H:%M').replace(tzinfo=datetime.timezone.utc).timestamp())
            else:ends=int(time.time())+parse_duration(value)
        except ValueError:raise ValueError('Use 12s, 12m, 12h, 12d (up to 90d), YYYY-MM-DD HH:MM in UTC, or none.')
        await bot.db.edit_task(j.guild_id,task['id'],{'ends':ends},j.user.id,digest(task));await finish(bot,j,'Deadline Saved','The original task brief will be refreshed.')
    await i.response.send_modal(ui.Form(bot,'Task Deadline',i.user.id,[('deadline','Deadline: 2d, UTC date, or none',old)],submit))

async def brief_binding(bot,i,tid):
    async def submit(j,v):
        await bot.authorize(j,primary=True);t=await bot.db.task(j.guild_id,tid)
        thread=j.guild.get_thread(t['thread']) or await bot.fetch_channel(t['thread'])
        msg=await thread.fetch_message(ident(v['message']))
        if msg.author.id!=bot.user.id:raise ValueError('Use this bot’s own task brief.')
        content=msg.content or ''
        if not (content.startswith(f'Task #{tid}:') or any(str(getattr(x,'content','')).startswith(f'## Task #{tid} ·') for x in discord.ui.LayoutView.from_message(msg).walk_children())):raise ValueError('This message does not match the selected task.')
        await bot.db.execute('INSERT OR REPLACE INTO meta_flags VALUES(?,?)',(f'task_brief:{tid}',canonical({'state':'active','message':msg.id})))
        await refresh_task(bot,j,tid)
    await i.response.send_modal(ui.Form(bot,'Recover Task Brief',i.user.id,[('message','Existing task brief message ID','')],submit))


async def voice_snapshot(bot,i,channel=None,amount=5):
    await guard(bot,i);integer(amount,1,1000)
    channel=channel or getattr(i,'channel',None)
    if not isinstance(channel,(discord.VoiceChannel,discord.StageChannel)):
        s=screen(bot,i,'Voice Snapshot','Choose a voice or stage channel. The connected human roster is captured when you select it. Stream watching is not verified.')
        async def choose(j,values):
            selected=j.guild.get_channel(values[0].id)
            await voice_snapshot(bot,j,selected,amount)
        s.select(discord.ui.ChannelSelect(placeholder='Voice or stage channel',channel_types=[discord.ChannelType.voice,discord.ChannelType.stage_voice]),choose)
        s.button('Snapshots',lambda j:snapshots(bot,j));return await ui.show(i,s)
    if not bot.is_ready() or getattr(i.guild,'unavailable',False) is True:raise ValueError('Wait for the bot to finish reconnecting before capturing voice presence.')
    if channel.guild.id!=i.guild_id or not channel.permissions_for(i.guild.me).view_channel:raise ValueError('The voice channel must be visible to this bot in this server.')
    ids=tuple(channel.voice_states);people={}
    if len(ids)>5000:raise ValueError('Voice snapshot exceeds 5000 connected members.')
    for uid in ids:
        member=await bot.service.eligible(i.guild,uid)
        if member:people[uid]=member.display_name
    capture=await bot.db.voice_capture(i.guild_id,channel.id,i.id,i.user.id,people,amount)
    await voice_preview(bot,i,capture)


async def voice_preview(bot,i,capture,offset=0):
    await guard(bot,i)
    people=list(capture['people'].items());amount=capture['amount']
    text=f"Channel: <#{capture['channel']}> · Captured <t:{capture['at']}:F>\nSnapshot #{capture['id']}\n**{len(people)} connected human members · {amount} RC each · Total {len(people)*amount} RC**\n\n"+'\n'.join(f'<@{uid}>' for uid,_ in people[offset:offset+20])
    text+=f'\n\nPage {offset//20+1} of {(len(people)+19)//20}. The roster is frozen; later joins and departures do not change it. Bots are excluded. This records call presence, not verified stream watching.'
    s=screen(bot,i,'Review Voice Snapshot',text)
    async def pay(j):
        await guard(bot,j)
        count=await bot.db.update_voice_capture(j.guild_id,capture['id'],j.user.id,digest(capture))
        await finish(bot,j,'Voice Rewards Recorded',f'{count} new awards · {amount} RC each. Public RC receipts are queued. Reusing this confirmation never pays twice.')
    async def edit(j):
        async def save(k,v):
            await bot.authorize(k)
            updated=await bot.db.update_voice_capture(k.guild_id,capture['id'],k.user.id,digest(capture),integer(int(v['amount']),1,1000))
            await voice_preview(bot,k,updated)
        await j.response.send_modal(ui.Form(bot,'Voice Snapshot Reward',j.user.id,[('amount','RC per connected member (1–1000)',amount)],save))
    s.button('Set RC Amount',edit);s.button('Confirm Voice Rewards',pay,discord.ButtonStyle.success)
    s.button('Previous',lambda j:voice_preview(bot,j,capture,max(0,offset-20)),disabled=not offset)
    s.button('Next',lambda j:voice_preview(bot,j,capture,offset+20),disabled=offset+20>=len(people))
    s.button('Cancel',lambda j:snapshots(bot,j));await ui.show(i,s)
