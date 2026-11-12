"""Native Discord Components V2, branded with original Rumble artwork."""
import io
import calendar
import json
import time
from pathlib import Path
import discord
from .config import canonical, clean, ident
from .features import SPIN
from .service import tier_for

ASSETS=Path(__file__).resolve().parents[1]/'assets'
INK=0x6C2029
CREAM=0xD7BD93
MENTIONS=discord.AllowedMentions.none()


def escape(text):
    return discord.utils.escape_markdown(discord.utils.escape_mentions(str(text)))


async def reply(i,**kwargs):
    kwargs.setdefault('ephemeral',True);kwargs.setdefault('allowed_mentions',MENTIONS)
    if i.response.is_done():return await i.followup.send(**kwargs)
    return await i.response.send_message(**kwargs)


async def failure(i,exc):
    await reply(i,content=str(exc)[:1000] if isinstance(exc,ValueError) else "The action failed. No new result was generated. Please reopen the panel or contact a moderator.")


class Screen(discord.ui.LayoutView):
    def __init__(self,bot,title,text,art=None,owner=None,persistent=False):
        super().__init__(timeout=None if persistent else 600)
        self.bot=bot;self.owner=owner;self.art=art
        self.box=discord.ui.Container(accent_colour=INK)
        self.add_item(self.box)
        heading=discord.ui.TextDisplay(f"## {title[:250]}\n{text[:3650]}")
        if art:self.box.add_item(discord.ui.Section(heading,accessory=discord.ui.Thumbnail(f"attachment://{art}",description=title)))
        else:self.box.add_item(heading)
        self.box.add_item(discord.ui.Separator())
        self.rows=[]

    def button(self,label,action,style=discord.ButtonStyle.secondary,disabled=False,custom_id=None):
        if not self.rows or len(self.rows[-1].children)>=4:
            row=discord.ui.ActionRow();self.box.add_item(row);self.rows.append(row)
        button=discord.ui.Button(label=label,style=style,disabled=disabled,custom_id=custom_id)
        async def callback(i):
            try:await action(i)
            except Exception as exc:
                self.bot.report_error(exc);await failure(i,exc)
        button.callback=callback;self.rows[-1].add_item(button)
        return self

    async def interaction_check(self,i):
        if self.owner is not None and self.owner!=i.user.id:
            await reply(i,content="Open your own Ripper Zone panel.");return False
        return True

    async def on_error(self,i,error,item):
        self.bot.report_error(error);await failure(i,error)

    def files(self):
        return [discord.File(ASSETS/self.art,filename=self.art)] if self.art else []


async def show(i,screen):
    await reply(i,view=screen,files=screen.files())


def gateway(bot):
    screen=Screen(bot,'Ripper Zone',"Your community, your progress.\nEarn Ripper Credits through tasks, events and a free daily spin. Spend RC on public raffles.\nOpen your private panel to get started.",'welcome.webp',persistent=True)
    screen.button('Open My Panel',lambda i:member_page(bot,i,'home'),discord.ButtonStyle.primary,custom_id='rz:panel:v1')
    return screen


async def member_page(bot,i,page='home',offset=0,since=0):
    await i.response.defer(ephemeral=True,thinking=True)
    member,cfg=await bot.member_access(i)
    account=await bot.db.account(i.guild_id,i.user.id,member.display_name)
    text='';art=None;title='Ripper Zone'
    if page=='home':
        title=f"Welcome, {escape(member.display_name)}";art='welcome.webp'
        text=f"Available: **{account['available']} RC**\nReserved for raffles: {account['reserved']} RC\nLifetime earned: {account['earned']} RC · Rank #{account['rank']}\n\nChoose your next activity."
        if not cfg['active']:text+="\nThe community program is currently paused."
    elif page=='balance':
        title='My Ripper Credits';art='balance.png'
        text=f"**{account['available']} RC available**\n{account['reserved']} RC reserved for open raffles\n{account['earned']} RC lifetime earned\nAll-time rank: #{account['rank']}\n\nTicket spending does not reduce earned RC or achievement progress."
    elif page=='spin':
        claim=await bot.db.spin_today(i.guild_id,i.user.id)
        title='Daily RC Spin';art='waiting.webp' if claim else 'spin.png'
        reset=(int(time.time())//86400+1)*86400
        text=(f"Today you received **{claim['amount']} RC**." if claim else "Your free daily spin is ready. Press Spin to receive RC.")+f"\nNext reset: <t:{reset}:R> · 00:00 UTC\n\n"+' · '.join(f"{a} RC: {w/100:g}%" for a,w in SPIN)+"\n\nLong-run average: 5 RC per spin. Each spin is independent."
    elif page=='tasks':
        title='Community Tasks';art='tasks.png'
        clause="status='closed' OR (ends>0 AND ends<=?)" if since else "status='active' AND (ends=0 OR ends>?)"
        rows=await bot.db.query(f"SELECT * FROM tasks WHERE guild=? AND ({clause}) ORDER BY id DESC LIMIT 10 OFFSET ?",(i.guild_id,int(time.time()),offset))
        text='\n'.join(f"**#{r['id']} {escape(r['title'])}** · {r['reward']} RC\n<#{r['thread']}>" for r in rows) or "No active tasks yet."
        text+="\n\nPost in the task's thread. A moderator reviews and awards RC. Quality bonuses are separate from the base reward."
    elif page=='raffles':
        title='RC Raffles';art='raffles.png'
        rows=await bot.db.query("SELECT id,message,channel,spec FROM raffles WHERE guild=? AND status='open' ORDER BY id DESC LIMIT 12",(i.guild_id,))
        text='\n'.join(f"**#{r['id']} {escape(json.loads(r['spec'])['title'])}** · {json.loads(r['spec'])['price']} RC per ticket\nhttps://discord.com/channels/{i.guild_id}/{r['channel']}/{r['message']}" for r in rows) or "No open RC raffles."
        mine=await bot.db.query("SELECT p.raffle,SUM(p.quantity) tickets,SUM(p.cost) cost,p.state FROM purchases p WHERE p.guild=? AND p.user=? GROUP BY p.raffle,p.state ORDER BY p.raffle DESC LIMIT 8",(i.guild_id,i.user.id))
        if mine:text+="\n\nYour recent entries\n"+'\n'.join(f"#{r['raffle']}: {r['tickets']} tickets · {r['cost']} RC · {r['state']}" for r in mine)
    elif page=='leaders':
        title='Community Leaderboard';art='leaderboard.webp'
        rows=await bot.db.leaders(i.guild_id,since)
        text='\n'.join(f"{n}. <@{r['user']}> · **{r['earned']} RC**" for n,r in enumerate(rows,1)) or "No earned RC yet."
        text+="\n\nRankings use earned RC. Spending and reservations do not lower your score."
    elif page=='progress':
        if not cfg['roles_enabled']:raise ValueError("Achievement roles are not enabled yet.")
        title='My Community Progress';art='progress.png'
        current=tier_for(account,cfg['tiers'])
        text=f"Current tier: "+(f"<@&{current['role']}>" if current else "Getting started")+f"\nEarned: {account['earned']} RC · Tasks: {account['tasks']} · Events: {account['events']}\n\n"
        text+='\n'.join(f"<@&{t['role']}>: {t['earned']} earned RC, {t['tasks']} tasks, {t['events']} events" for t in cfg['tiers'])
        text+="\nOnly your highest eligible achievement role is kept."
    elif page=='history':
        title='My RC History';art='history.webp'
        rows=await bot.db.history(i.guild_id,i.user.id,offset)
        text='\n'.join(f"#{r['id']} <t:{r['at']}:d> · {r['da']:+} available / {r['dr']:+} reserved / {r['de']:+} earned\n{escape(r['reason'])[:140]}" for r in rows) or "No transactions on this page."
    elif page=='help':
        title='How Ripper Zone Works';art='help.webp'
        text="**Ripper Credits (RC)** reward your community participation.\n\nCommunity Tasks: contribute in the task thread and wait for moderator approval.\nEvents: eligible Rumble and ordinary-raffle participants receive RC after a moderator imports the event snapshot. Winning is not required.\nDaily Spin: one free claim per UTC day, with rewards from 2 to 100 RC.\nRC Raffles: buy tickets on the public raffle post. The cost is reserved, then spent when the draw completes. Cancelled raffles and ineligible entries receive automatic refunds.\nAchievement roles: optional milestones based on earned RC, tasks and events.\n\nRC have no cash value. No payment or wallet is required for this panel."
    else:raise ValueError("Unknown panel page.")
    screen=Screen(bot,title,text,art,owner=i.user.id)
    if page=='spin' and not claim:
        screen.button('Spin · Free',lambda j:spin(bot,j),discord.ButtonStyle.success,disabled=not cfg['spin_enabled'] or not cfg['active'])
    if page=='leaders':
        now=int(time.time());day=now//86400*86400
        for label,start in [('All Time',0),('This Month',calendar.timegm(time.strptime(time.strftime('%Y-%m-01',time.gmtime()),'%Y-%m-%d'))),('Last 7 Days',day-6*86400)]:
            screen.button(label,lambda j,s=start:member_page(bot,j,'leaders',since=s))
    if page=='history':
        screen.button('Previous',lambda j:member_page(bot,j,'history',max(0,offset-10)),disabled=offset==0)
        screen.button('Next',lambda j:member_page(bot,j,'history',offset+10),disabled=len(rows)<10)
    if page=='tasks':
        screen.button('Active',lambda j:member_page(bot,j,'tasks'))
        screen.button('Past',lambda j:member_page(bot,j,'tasks',since=1))
        screen.button('Previous',lambda j:member_page(bot,j,'tasks',max(0,offset-10),since),disabled=offset==0)
        screen.button('Next',lambda j:member_page(bot,j,'tasks',offset+10,since),disabled=len(rows)<10)
    pages=[('My RC','balance'),('Daily Spin','spin'),('Community Tasks','tasks'),('RC Raffles','raffles'),('Leaderboard','leaders'),('History','history'),('Help','help')]
    if cfg['roles_enabled']:pages.insert(5,('My Progress','progress'))
    for label,dest in pages:
        if dest!=page:screen.button(label,lambda j,p=dest:member_page(bot,j,p))
    await show(i,screen)


async def spin(bot,i):
    await i.response.defer(ephemeral=True,thinking=True)
    member,cfg=await bot.member_access(i,active=True)
    if cfg['spin_role'] and cfg['spin_role'] not in {r.id for r in member.roles}:raise ValueError("You do not have the configured daily-spin role.")
    result=await bot.db.spin(i.guild_id,i.user.id,member.display_name,i.id)
    screen=Screen(bot,'Daily Spin Result',f"**{result['amount']} RC** "+("added to your balance." if result['created'] else "was already credited for this UTC day.")+f"\nClaim date: {result['day']}\nYour next spin is available after 00:00 UTC.",'jackpot.gif' if result['amount']==100 else 'spin.png',owner=i.user.id)
    screen.button('My RC',lambda j:member_page(bot,j,'balance'))
    await show(i,screen)


def raffle_view(bot,r):
    s=r['spec'];status=r['status']
    text=f"{escape(s['prize'])[:1400]}\n\n**{s['price']} RC per ticket** · Up to {s['max_tickets']} tickets per member\nWinners: {s['winners']} · Minimum eligible members: {s['minimum']}\nCloses: <t:{s['ends']}:F>\nStatus: **{status}**\n\nTickets are reserved on purchase. Eligible tickets are spent at closing. Cancelled raffles and ineligible entries are refunded. One prize per member. Eligibility uses the access role fixed when this raffle was published."
    if r['commitment']:text+=f"\n\nSeed commitment: `{r['commitment']}`\nRules hash: `{r['hash']}`"
    if r['rounds']:
        winners=r['rounds'][-1]['winners']
        text+=f"\n\nLatest draw, round {r['rounds'][-1]['round']}: "+(', '.join(f"<@{u}>" for u in winners) or "No draw. All reservations were refunded.")+"\nFull round history is available in Verify Draw."
    screen=Screen(bot,f"RC Raffle #{r['id']} · {escape(s['title'])}",text,persistent=True)
    screen.button('Buy Tickets',lambda i:buy_modal(bot,i,r['id']),discord.ButtonStyle.success,disabled=status!='open',custom_id=f"rz:buy:{r['id']}")
    screen.button('My Entry',lambda i:entry(bot,i,r['id']),custom_id=f"rz:entry:{r['id']}")
    screen.button('Verify Draw',lambda i:proof(bot,i,r['id']),disabled=not r['rounds'],custom_id=f"rz:proof:{r['id']}")
    screen.button('Claim Prize',lambda i:claim(bot,i,r['id']),disabled=status!='drawn',custom_id=f"rz:claim:{r['id']}")
    return screen


async def buy_modal(bot,i,rid):
    # Opening a modal must be the initial response; all checks are repeated on submit.
    modal=Form(bot,'Buy RC Raffle Tickets',i.user.id,[('quantity','Number of tickets','1')],lambda j,v:purchase_preview(bot,j,rid,v))
    await i.response.send_modal(modal)


async def purchase_preview(bot,i,rid,values):
    member,_=await bot.member_access(i,active=True)
    r=await bot.db.raffle(i.guild_id,rid);quantity=int(values['quantity'])
    if not 1<=quantity<=r['spec']['max_tickets']:raise ValueError("Ticket quantity exceeds this raffle's limit.")
    account=await bot.db.account(i.guild_id,i.user.id)
    cost=quantity*r['spec']['price'];request=str(i.id)
    text=f"Raffle #{rid}: {escape(r['spec']['title'])}\nTickets: **{quantity}**\nTotal reserved cost: **{cost} RC**\nAvailable balance: {account['available']} RC\n\nConfirm to reserve RC and register your tickets."
    async def confirm(j):
        await j.response.defer(ephemeral=True,thinking=True)
        m,_=await bot.member_access(j,active=True)
        current=await bot.db.raffle(j.guild_id,rid)
        if not await bot.service.eligible(j.guild,i.user.id,current['contract']['member_role']):raise ValueError("You no longer meet this raffle's access-role requirement.")
        paid=await bot.db.buy(j.guild_id,rid,j.user.id,quantity,request,m.display_name)
        await reply(j,content=f"{paid['quantity']} tickets registered for raffle #{rid}. {paid['cost']} RC reserved. Receipt #{paid['id']}.")
    screen=Screen(bot,'Confirm Ticket Purchase',text,owner=i.user.id)
    screen.button('Confirm Purchase',confirm,discord.ButtonStyle.success)
    await show(i,screen)


async def entry(bot,i,rid):
    await i.response.defer(ephemeral=True,thinking=True);await bot.member_access(i)
    rows=await bot.db.query("SELECT quantity,cost,state FROM purchases WHERE guild=? AND raffle=? AND user=? ORDER BY id",(i.guild_id,rid,i.user.id))
    await reply(i,content='\n'.join(f"{r['quantity']} tickets · {r['cost']} RC · {r['state']}" for r in rows) or "You have no tickets in this raffle.")


async def proof(bot,i,rid):
    await i.response.defer(ephemeral=True,thinking=True);await bot.member_access(i)
    data=await bot.db.raffle_proof(i.guild_id,rid)
    await reply(i,content="Published seed, frozen rules and weighted selection proof.",file=discord.File(io.BytesIO(json.dumps(data,indent=2).encode()),filename=f"raffle-{rid}-proof.json"))


async def claim(bot,i,rid):
    await i.response.defer(ephemeral=True,thinking=True);await bot.member_access(i)
    changed=await bot.db.prize_status(i.guild_id,rid,i.user.id,'claimed',i.user.id)
    await reply(i,content="Your prize claim has been recorded. Contact the server's prize-support ticket team." if changed else "Your prize claim is already recorded.")


class Form(discord.ui.Modal):
    def __init__(self,bot,title,owner,fields,submit):
        super().__init__(title=title[:45],timeout=600)
        self.bot=bot;self.owner=owner;self.submit=submit;self.inputs={}
        for key,label,default in fields:
            item=discord.ui.TextInput(label=label[:45],default=str(default),max_length=2000 if key in ('body','json') else 500,style=discord.TextStyle.paragraph if key in ('body','json') else discord.TextStyle.short)
            self.inputs[key]=item;self.add_item(item)

    async def on_submit(self,i):
        if i.user.id!=self.owner:return await reply(i,content="This form belongs to another member.")
        await i.response.defer(ephemeral=True,thinking=True)
        try:await self.submit(i,{k:str(v).strip() for k,v in self.inputs.items()})
        except Exception as exc:self.bot.report_error(exc);await failure(i,exc)

    async def on_error(self,i,error):
        self.bot.report_error(error);await failure(i,error)


async def admin_page(bot,i):
    await i.response.defer(ephemeral=True,thinking=True)
    await bot.authorize(i)
    cfg,revision=await bot.db.config(i.guild_id)
    text=f"Program: {'active' if cfg['active'] else 'paused'} · Settings revision {revision}\nDaily Spin: {'enabled' if cfg['spin_enabled'] else 'paused'}\nAchievement tiers: {'enabled' if cfg['roles_enabled'] else 'skipped'}\n\nTasks, rewards and raffle operations are available below. Sensitive setup, corrections and recovery require a primary administrator.\n\nUse /ripper snapshot to preview an event export, /ripper task_manage for lifecycle tools and /ripper raffle_manage for results and prize handling."
    screen=Screen(bot,'Ripper Zone Administration',text,'health.png',owner=i.user.id)
    screen.button('Setup Wizard',lambda j:setup_start(bot,j),discord.ButtonStyle.primary)
    screen.button('New Task',lambda j:task_form(bot,j))
    screen.button('Award RC',lambda j:reward_form(bot,j))
    screen.button('New RC Raffle',lambda j:raffle_form(bot,j))
    screen.button('Achievement Roles',lambda j:tiers_form(bot,j))
    screen.button('Spin / Program',lambda j:flags_form(bot,j))
    screen.button('Publish Member Panel',lambda j:bot.publish_panel_action(j))
    screen.button('Health / Doctor',lambda j:bot.doctor_action(j))
    screen.button('Settings / Reports',lambda j:report_page(bot,j))
    await show(i,screen)


async def task_form(bot,i):
    async def submit(j,v):
        await bot.authorize(j)
        period,cooldown,hours=v['timing'].split(',')
        periods={'once':0,'daily':86400,'weekly':604800}
        if period.strip() not in periods:raise ValueError("Period must be once, daily or weekly.")
        tid=await bot.db.create_task(j.guild_id,j.user.id,v['title'],v['body'],int(v['reward']),periods[period.strip()],int(cooldown),int(time.time())+int(hours)*3600 if int(hours)>0 else 0)
        thread=await bot.service.publish_task(j.guild,tid)
        await reply(j,content=f"Task #{tid} published in {thread.mention}.")
    await i.response.send_modal(Form(bot,'New Community Task',i.user.id,[('title','Task title',''),('body','Instructions',''),('reward','Base RC reward','5'),('timing','Period, cooldown seconds, duration hours','once, 0, 72')],submit))


async def reward_form(bot,i):
    async def submit(j,v):
        await bot.authorize(j)
        ids=sorted(set(ident(x.strip()) for x in v['users'].split(',')))
        if len(ids)>100:raise ValueError("Use an event snapshot for more than 100 members.")
        recipients={}
        cfg,_=await bot.db.config(j.guild_id)
        for uid in ids:
            member=await bot.service.eligible(j.guild,uid,cfg['member_role'])
            if member:recipients[uid]=member.display_name
        amount=int(v['amount']);operation=str(j.id)
        async def confirm(k):
            await k.response.defer(ephemeral=True,thinking=True);await bot.authorize(k)
            count=await bot.db.award(k.guild_id,recipients,amount,k.user.id,v['reason'],operation)
            await reply(k,content=f"{count} members received {amount} RC each.")
        screen=Screen(bot,'Review RC Award',f"Eligible members: {len(recipients)} of {len(ids)}\n{amount} RC each · Total {amount*len(recipients)} RC\nReason: {escape(v['reason'])}",owner=j.user.id)
        screen.button('Confirm Award',confirm,discord.ButtonStyle.success);await show(j,screen)
    await i.response.send_modal(Form(bot,'Award Community RC',i.user.id,[('users','Member IDs, separated by commas',''),('amount','RC per member','5'),('reason','Reason','Community contribution')],submit))


async def raffle_form(bot,i):
    async def submit(j,v):
        await bot.authorize(j)
        price,cap,winners,minimum,hours=[int(x.strip()) for x in v['rules'].split(',')]
        if not 1<=hours<=2160:raise ValueError("Duration must be 1..2160 hours.")
        rid=await bot.db.create_raffle(j.guild_id,j.user.id,dict(title=v['title'],prize=v['body'],price=price,max_tickets=cap,winners=winners,minimum=minimum,ends=int(time.time())+hours*3600))
        async def publish(k):
            await k.response.defer(ephemeral=True,thinking=True);await bot.authorize(k)
            msg=await bot.service.publish_raffle(k.guild,rid,k.user.id)
            await reply(k,content=f"RC Raffle #{rid} published: {msg.jump_url}")
        r=await bot.db.raffle(j.guild_id,rid)
        screen=Screen(bot,'Review Raffle Draft',f"Draft #{rid}: {escape(v['title'])}\n{escape(v['body'])}\n{price} RC per ticket · Max {cap} per member\n{winners} winners · {minimum} eligible members minimum\nCloses <t:{r['spec']['ends']}:F>",owner=j.user.id)
        screen.button('Publish Public Raffle',publish,discord.ButtonStyle.success);await show(j,screen)
    await i.response.send_modal(Form(bot,'New RC Raffle',i.user.id,[('title','Raffle title',''),('body','Prize and claim instructions',''),('rules','Price, cap, winners, min members, hours','10, 10, 1, 3, 24')],submit))


async def tiers_form(bot,i):
    async def submit(j,v):
        await bot.authorize(j,primary=True)
        cfg,rev=await bot.db.config(j.guild_id);tiers=[]
        for n in range(1,4):
            rid,earned,tasks,events=[int(x.strip()) for x in v[str(n)].split(',')]
            tiers.append(dict(role=rid,earned=earned,tasks=tasks,events=events))
        cfg.update(tiers=tiers,roles_enabled=v['enable'].lower()=='true')
        await bot.service.configure(j.guild,cfg,rev,j.user.id)
        await reply(j,content="Three achievement tiers saved. Role reconciliation is queued.")
    cfg,_=await bot.db.config(i.guild_id)
    fields=[(str(n),f"Tier {n}: role ID, earned RC, tasks, events",f"{t['role']}, {t['earned']}, {t['tasks']}, {t['events']}") for n,t in enumerate(cfg['tiers'],1)]
    if not fields:fields=[(str(n),f"Tier {n}: role ID, earned RC, tasks, events",f"0, {n*100}, 0, 0") for n in range(1,4)]
    fields.append(('enable','Enable now? true / false',str(cfg['roles_enabled']).lower()))
    await i.response.send_modal(Form(bot,'Three Achievement Roles',i.user.id,fields,submit))


async def flags_form(bot,i):
    async def submit(j,v):
        await bot.authorize(j,primary=True)
        if any(v[k].lower() not in ('true','false') for k in ('active','spin','roles')):raise ValueError("Use true or false.")
        cfg,rev=await bot.db.config(j.guild_id)
        cfg.update(active=v['active'].lower()=='true',spin_enabled=v['spin'].lower()=='true',roles_enabled=v['roles'].lower()=='true')
        await bot.service.configure(j.guild,cfg,rev,j.user.id)
        await reply(j,content="Program settings saved.")
    cfg,_=await bot.db.config(i.guild_id)
    await i.response.send_modal(Form(bot,'Program Controls',i.user.id,[('active','Program active? true / false',str(cfg['active']).lower()),('spin','Daily spin active? true / false',str(cfg['spin_enabled']).lower()),('roles','Achievement roles active? true / false',str(cfg['roles_enabled']).lower())],submit))


class Setup(discord.ui.View):
    STEPS=[('panel_channel','Member panel channel'),('tasks_channel','Community tasks channel'),('leaderboard_channel','Leaderboard channel'),('raffle_channel','Public RC raffle channel'),('log_channel','Private moderator log channel'),('member_role','Access role, e.g. Ripper'),('manager_roles','Moderator roles')]
    def __init__(self,bot,owner,step=0):
        super().__init__(timeout=600);self.bot=bot;self.owner=owner;self.step=step
        key,label=self.STEPS[step];self.key=key
        if 'channel' in key:select=discord.ui.ChannelSelect(placeholder=label,channel_types=[discord.ChannelType.text])
        else:select=discord.ui.RoleSelect(placeholder=label,min_values=0,max_values=10 if key=='manager_roles' else 1)
        async def selected(i):
            await i.response.defer(ephemeral=True,thinking=True);await bot.authorize(i,primary=True)
            cfg,rev=await bot.db.config(i.guild_id)
            ids=[x.id for x in select.values];cfg[key]=ids if key=='manager_roles' else ids[0] if ids else 0
            await bot.service.configure(i.guild,cfg,rev,i.user.id)
            if step+1<len(self.STEPS):
                next_=Setup(bot,owner,step+1);await reply(i,content=f"Setup {step+2}/{len(self.STEPS)}: {self.STEPS[step+1][1]}",view=next_)
            else:
                screen=Screen(bot,'Setup: Achievement Roles',"Core channels and access are saved. Skip the three achievement roles for now, or configure their metrics. Activate the program when ready.",'progress.png',owner=owner)
                screen.button('Skip Roles',lambda j:skip_roles(bot,j))
                screen.button('Configure Three Roles',lambda j:tiers_form(bot,j))
                screen.button('Activate Program',lambda j:activate(bot,j),discord.ButtonStyle.success)
                await show(i,screen)
        select.callback=selected;self.add_item(select)

    async def interaction_check(self,i):
        if i.user.id!=self.owner:
            await reply(i,content="Open your own setup wizard.");return False
        return True

    async def on_error(self,i,error,item):
        self.bot.report_error(error);await failure(i,error)


async def setup_start(bot,i):
    await i.response.defer(ephemeral=True,thinking=True);await bot.authorize(i,primary=True)
    await reply(i,content="Setup 1/7: Member panel channel. Each selection is saved. Run the wizard again to change channels.",view=Setup(bot,i.user.id))


async def skip_roles(bot,i):
    await i.response.defer(ephemeral=True,thinking=True);await bot.authorize(i,primary=True)
    cfg,rev=await bot.db.config(i.guild_id);cfg['roles_enabled']=False
    await bot.service.configure(i.guild,cfg,rev,i.user.id)
    screen=Screen(bot,'Achievement Roles Skipped',"Enable and configure the three tiers later from Administration → Achievement Roles.",owner=i.user.id)
    screen.button('Activate Program',lambda j:activate(bot,j),discord.ButtonStyle.success);await show(i,screen)


async def activate(bot,i):
    await i.response.defer(ephemeral=True,thinking=True);await bot.authorize(i,primary=True)
    cfg,rev=await bot.db.config(i.guild_id);cfg['active']=True
    await bot.service.configure(i.guild,cfg,rev,i.user.id)
    await reply(i,content="Ripper Zone is active. Publish the member panel from /ripper admin.")


async def report_page(bot,i):
    await i.response.defer(ephemeral=True,thinking=True);await bot.authorize(i)
    screen=Screen(bot,'Reports and Settings',"Use /ripper report for ledger or leaderboard CSV.\n/ripper settings_export downloads current configuration.\n/ripper settings_import previews a configuration file before saving.\n/ripper settings_history lists previous revisions.\n/ripper access configures primary administrators and moderator roles.\n/ripper reactions configures moderator reward reactions.\n/ripper panel_recover binds a known panel message after an uncertain send.\n/ripper recovery handles verified accounting and failed jobs.",owner=i.user.id)
    screen.button('Back to Administration',lambda j:admin_page(bot,j));await show(i,screen)
