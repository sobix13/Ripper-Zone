"""Native Discord Components V2, branded with original Rumble artwork."""
import io
import calendar
import json
import time
from asyncio import sleep
from pathlib import Path
import discord
from .config import canonical, clean, ident, settings
from .copy import phrase
from .features import SPIN
from .service import tier_for
from .durations import format_duration

ASSETS=Path(__file__).resolve().parents[1]/'assets'
INK=0x6C2029
CREAM=0xD7BD93
TEAL=0x397D82
GOLD=0xC89A45
MENTIONS=discord.AllowedMentions.none()


def escape(text):
    return discord.utils.escape_markdown(discord.utils.escape_mentions(str(text)))


async def reply(i,**kwargs):
    kwargs.setdefault('ephemeral',True);kwargs.setdefault('allowed_mentions',MENTIONS)
    if i.response.is_done():return await i.followup.send(**kwargs)
    return await i.response.send_message(**kwargs)


async def failure(i,exc):
    client=getattr(i,'client',None);cfg={}
    if client and hasattr(client,'db') and i.guild_id:
        try:cfg,_=await client.db.config(i.guild_id)
        except Exception:pass
    await reply(i,content=str(exc)[:1000] if isinstance(exc,ValueError) else phrase(cfg,'operation_unknown'))


def private_component(i):
    message=getattr(i,'message',None)
    return getattr(i,'type',None)==discord.InteractionType.component and bool(message and message.flags.ephemeral)


async def defer(i,*,update=False):
    if not i.response.is_done():
        if update and private_component(i):await i.response.defer()
        else:await i.response.defer(ephemeral=True,thinking=True)


class Screen(discord.ui.LayoutView):
    def __init__(self,bot,title,text,art=None,owner=None,persistent=False,full_art=False,accent=INK):
        super().__init__(timeout=None if persistent else 600)
        self.bot=bot;self.owner=owner;self.art=art
        self.box=discord.ui.Container(accent_colour=accent)
        self.add_item(self.box)
        heading=discord.ui.TextDisplay(f"## {title[:250]}\n{text[:3650]}")
        if art and full_art:
            self.box.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(f"attachment://{art}",description=title)))
            self.box.add_item(heading)
        elif art:self.box.add_item(discord.ui.Section(heading,accessory=discord.ui.Thumbnail(f"attachment://{art}",description=title)))
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

    def select(self,item,action):
        async def callback(i):
            try:await action(i,item.values)
            except Exception as exc:self.bot.report_error(exc);await failure(i,exc)
        item.callback=callback
        self.box.add_item(discord.ui.ActionRow(item))
        self.rows=[]
        return self


async def show(i,screen,*,update=False):
    if update and private_component(i):
        await i.edit_original_response(view=screen,attachments=screen.files(),allowed_mentions=MENTIONS)
    else:await reply(i,view=screen,files=screen.files())


def gateway(bot,cfg=None):
    cfg=settings(cfg)
    screen=Screen(bot,escape(cfg['panel_title']),escape(cfg['welcome_text']),'welcome-banner.webp',persistent=True,full_art=True)
    screen.button('Open My Panel',lambda i:member_page(bot,i,'home'),discord.ButtonStyle.primary,custom_id='rz:panel:v1')
    return screen


async def member_page(bot,i,page='home',offset=0,since=0):
    from .member_ui import page_view
    return await page_view(bot,i,page,offset,since)


async def spin(bot,i):
    # A component update preserves this member's existing private message.
    if not i.response.is_done():await i.response.defer()
    member,cfg=await bot.member_access(i,active=True)
    if cfg['spin_role'] and cfg['spin_role'] not in {r.id for r in member.roles}:raise ValueError("You do not have the configured daily-spin role.")
    result=await bot.db.spin(i.guild_id,i.user.id,member.display_name,i.id)
    if result['created']:
        busy=Screen(bot,'Daily RC Spin','Spinning…','spin-decelerating.gif',owner=i.user.id,full_art=True,accent=GOLD)
        busy.button('Spinning…',lambda j:spin(bot,j),disabled=True)
        try:await i.edit_original_response(view=busy,attachments=busy.files(),allowed_mentions=MENTIONS)
        except (discord.HTTPException,OSError) as exc:bot.report_error(exc)
        else:await sleep(4)
    account=await bot.db.account(i.guild_id,i.user.id)
    reset=calendar.timegm(time.strptime(result['day'],'%Y-%m-%d'))+86400
    next_spin=f'Next spin: <t:{reset}:R> · 00:00 UTC' if bot.db.clock()<reset else 'Your next daily spin is ready. Open Daily Spin.'
    text=phrase(cfg,'spin_result',amount=result['amount'])+f"\n**{result['amount']} RC** "+('added to your balance.' if result['created'] else 'was already credited.')+f"\nAvailable balance: **{account['available']} RC**\nClaim date: {result['day']} UTC\n{next_spin}"
    screen=Screen(bot,'Daily Spin Result',text,'spin-start.png',owner=i.user.id,full_art=True,accent=GOLD)
    screen.button('Claim Recorded',lambda j:spin(bot,j),disabled=True)
    screen.button('My Dashboard',lambda j:member_page(bot,j,'dashboard'))
    screen.button('Daily Spin',lambda j:member_page(bot,j,'spin'))
    screen.button('Home',lambda j:member_page(bot,j,'home'))
    try:await i.edit_original_response(view=screen,attachments=screen.files(),allowed_mentions=MENTIONS)
    except (discord.HTTPException,OSError) as exc:
        bot.report_error(exc)
        await reply(i,content=text)


def raffle_view(bot,r,cfg=None):
    cfg=settings(cfg)
    s=r['spec'];status=r['status']
    text=f"{s['prize']}\n\n**{s['price']} RC per ticket** · Up to {s['max_tickets']} tickets per member\nUp to {s['winners']} winners · Minimum eligible members: {s['minimum']}\nCloses: <t:{s['ends']}:F>\nStatus: **{status}**\n\nTickets are reserved on purchase. Eligible tickets are spent at closing. Cancelled raffles and ineligible entries are refunded. One prize per member. Eligibility uses the access role fixed when this raffle was published."
    if r['commitment']:text+=f"\n\nSeed commitment: `{r['commitment']}`\nRules hash: `{r['hash']}`"
    if r['rounds']:
        winners=[p['user'] for p in r.get('prizes',[]) if p['state'] not in ('forfeited','replaced')] if 'prizes' in r else [u for rnd in r['rounds'] for u in rnd['winners']]
        text+=phrase(cfg,'raffle_result')+f"\n\nCurrent winners, through round {r['rounds'][-1]['round']}: "+(', '.join(f"<@{u}>" for u in winners) or "No draw. All reservations were refunded.")+"\nFull round history is available in Verify Draw."
    text=phrase(cfg,'raffle_howto')+'\n\n'+text
    screen=Screen(bot,f"RC Raffle #{r['id']} · {escape(s['title'])}",text,persistent=True,accent=GOLD)
    screen.button('Buy Tickets',lambda i:buy_modal(bot,i,r['id']),discord.ButtonStyle.primary,disabled=status!='open',custom_id=f"rz:buy:{r['id']}")
    screen.button('My Entry',lambda i:entry(bot,i,r['id']),custom_id=f"rz:entry:{r['id']}")
    screen.button('Verify Draw',lambda i:proof(bot,i,r['id']),disabled=not r['rounds'],custom_id=f"rz:proof:{r['id']}")
    screen.button('Claim Prize',lambda i:claim(bot,i,r['id']),disabled=status!='drawn',custom_id=f"rz:claim:{r['id']}")
    return screen


async def buy_modal(bot,i,rid):
    # Opening a modal must be the initial response; all checks are repeated on submit.
    modal=Form(bot,'Buy RC Raffle Tickets',i.user.id,[('quantity','Number of tickets','1')],lambda j,v:purchase_preview(bot,j,rid,v))
    await i.response.send_modal(modal)


async def purchase_preview(bot,i,rid,values):
    member,cfg=await bot.member_access(i,active=True)
    r=await bot.db.raffle(i.guild_id,rid);quantity=int(values['quantity'])
    if not 1<=quantity<=r['spec']['max_tickets']:raise ValueError("Ticket quantity exceeds this raffle's limit.")
    account=await bot.db.account(i.guild_id,i.user.id)
    cost=quantity*r['spec']['price'];request=str(i.id)
    text=f"Raffle #{rid}: {escape(r['spec']['title'])}\nTickets: **{quantity}**\nTotal reserved cost: **{cost} RC**\nAvailable balance: {account['available']} RC\n\nConfirm to reserve RC and register your tickets."
    async def confirm(j):
        await defer(j,update=True)
        m,_=await bot.member_access(j,active=True)
        current=await bot.db.raffle(j.guild_id,rid)
        if not await bot.service.eligible(j.guild,i.user.id,current['contract']['member_role']):raise ValueError("You no longer meet this raffle's access-role requirement.")
        paid=await bot.db.buy(j.guild_id,rid,j.user.id,quantity,request,m.display_name)
        receipt=Screen(bot,'Tickets Recorded',phrase(cfg,'purchase_receipt')+'\n'+f"{paid['quantity']} tickets registered for raffle #{rid}. {paid['cost']} RC reserved. Receipt #{paid['id']}.",owner=j.user.id,accent=GOLD)
        receipt.button('My Entry',lambda k:entry(bot,k,rid));receipt.button('My Dashboard',lambda k:member_page(bot,k,'dashboard'));receipt.button('Home',lambda k:member_page(bot,k))
        await show(j,receipt,update=True)
    screen=Screen(bot,'Confirm Ticket Purchase',text,owner=i.user.id,accent=GOLD)
    screen.button('Confirm Purchase',confirm,discord.ButtonStyle.success)
    screen.button('Cancel',lambda j:member_page(bot,j,'raffles'))
    await show(i,screen)


async def entry(bot,i,rid):
    await defer(i,update=True);await bot.member_access(i)
    rows=await bot.db.query("SELECT quantity,cost,state FROM purchases WHERE guild=? AND raffle=? AND user=? ORDER BY id",(i.guild_id,rid,i.user.id))
    screen=Screen(bot,'My Raffle Entry',f'Raffle #{rid}\n'+'\n'.join(f"{r['quantity']} tickets · {r['cost']} RC · {r['state']}" for r in rows) if rows else 'You have no tickets in this raffle.',owner=i.user.id,accent=GOLD)
    screen.button('RC Raffles',lambda j:member_page(bot,j,'raffles'));screen.button('My Dashboard',lambda j:member_page(bot,j,'dashboard'));screen.button('Home',lambda j:member_page(bot,j))
    await show(i,screen,update=True)


async def proof(bot,i,rid):
    await defer(i);await bot.member_access(i)
    data=await bot.db.raffle_proof(i.guild_id,rid)
    await reply(i,content="Published seed, frozen rules and weighted selection proof.",file=discord.File(io.BytesIO(json.dumps(data,indent=2).encode()),filename=f"raffle-{rid}-proof.json"))


async def claim(bot,i,rid):
    await defer(i,update=True);await bot.member_access(i)
    _,cfg=await bot.member_access(i)
    changed=await bot.db.prize_status(i.guild_id,rid,i.user.id,'claimed',i.user.id)
    text=(phrase(cfg,'prize_claim') if changed else 'Your prize claim is already recorded.')+'\n'+cfg['support_text']
    screen=Screen(bot,'Prize Claim',text,owner=i.user.id,accent=TEAL)
    if cfg['support_channel']:screen.box.add_item(discord.ui.ActionRow(discord.ui.Button(label='Open Support Tickets',url=f"https://discord.com/channels/{i.guild_id}/{cfg['support_channel']}")))
    screen.button('My Prizes',lambda j:member_page(bot,j,'prizes'));screen.button('My Dashboard',lambda j:member_page(bot,j,'dashboard'));screen.button('Home',lambda j:member_page(bot,j))
    await show(i,screen,update=True)


class Form(discord.ui.Modal):
    def __init__(self,bot,title,owner,fields,submit):
        super().__init__(title=title[:45],timeout=600)
        self.bot=bot;self.owner=owner;self.submit=submit;self.inputs={}
        for key,label,default in fields:
            paragraph=key in ('body','json','welcome_text','about_text','support_text','task_footer')
            item=discord.ui.TextInput(label=label[:45],default=str(default),max_length=2000 if paragraph else 500,style=discord.TextStyle.paragraph if paragraph else discord.TextStyle.short)
            self.inputs[key]=item;self.add_item(item)

    async def on_submit(self,i):
        if i.user.id!=self.owner:return await reply(i,content="This form belongs to another member.")
        await defer(i)
        try:await self.submit(i,{k:str(v).strip() for k,v in self.inputs.items()})
        except Exception as exc:self.bot.report_error(exc);await failure(i,exc)

    async def on_error(self,i,error):
        self.bot.report_error(error);await failure(i,error)


async def admin_page(bot,i):
    from .admin_ui import home
    return await home(bot,i)

async def task_form(bot,i):
    from .admin_ui import task_create
    return await task_create(bot,i)

async def reward_form(bot,i):
    from .admin_ui import award_members
    return await award_members(bot,i)

async def raffle_form(bot,i):
    from .admin_ui import raffle_create
    return await raffle_create(bot,i)

async def tiers_form(bot,i):
    from .admin_ui import tiers
    return await tiers(bot,i)

async def flags_form(bot,i):
    from .admin_ui import controls
    return await controls(bot,i)

class Setup(discord.ui.View):
    STEPS=[('panel_channel','Member panel channel'),('tasks_channel','Community tasks channel'),('leaderboard_channel','Leaderboard channel'),('raffle_channel','Public RC raffle channel'),('log_channel','Public RC activity channel'),('member_role','Access role, e.g. Ripper'),('manager_roles','Moderator roles')]
    def __init__(self,bot,owner,step=0):
        super().__init__(timeout=600);self.bot=bot;self.owner=owner;self.step=step
        key,label=self.STEPS[step];self.key=key
        if 'channel' in key:select=discord.ui.ChannelSelect(placeholder=label,channel_types=[discord.ChannelType.text])
        else:select=discord.ui.RoleSelect(placeholder=label,min_values=0,max_values=10 if key=='manager_roles' else 1)
        async def selected(i):
            await defer(i);await bot.authorize(i,primary=True)
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
    await defer(i);await bot.authorize(i,primary=True)
    await reply(i,content="Setup 1/7: Member panel channel. Each selection is saved. Run the wizard again to change channels.",view=Setup(bot,i.user.id))


async def skip_roles(bot,i):
    await defer(i);await bot.authorize(i,primary=True)
    cfg,rev=await bot.db.config(i.guild_id);cfg['roles_enabled']=False
    await bot.service.configure(i.guild,cfg,rev,i.user.id)
    screen=Screen(bot,'Achievement Roles Skipped',"Enable and configure the three tiers later from Administration → Achievement Roles.",owner=i.user.id)
    screen.button('Activate Program',lambda j:activate(bot,j),discord.ButtonStyle.success);await show(i,screen)


async def activate(bot,i):
    await defer(i);await bot.authorize(i,primary=True)
    cfg,rev=await bot.db.config(i.guild_id);cfg['active']=True
    await bot.service.configure(i.guild,cfg,rev,i.user.id)
    screen=Screen(bot,'Setup Ready','The program is active. Publish the public panel and leaderboard, then check Health.',owner=i.user.id)
    screen.button('Publish Member Panel',lambda j:bot.publish_panel_action(j))
    from .admin_ui import invoke,health,settings_page
    screen.button('Publish Leaderboard',lambda j:invoke(bot,j,'leaderboard_publish'))
    screen.button('Health Check',lambda j:health(bot,j));screen.button('Settings',lambda j:settings_page(bot,j))
    await show(i,screen)


async def report_page(bot,i):
    from .admin_ui import reports
    return await reports(bot,i)


def task_view(bot,task,cfg):
    period={0:'One-time',86400:'Daily UTC',604800:'Weekly from creation date UTC'}[task['period']]
    text=task['body']+f"\n\nBase reward: {task['reward']} RC · {period}\nCooldown: {format_duration(task['cooldown'])} · Status: {task['status']}"
    if task['ends']:text+=f"\nDeadline: <t:{task['ends']}:F>"
    text+='\n\n'+cfg['task_footer']
    if task['status']=='closed':text+='\n'+phrase(cfg,'task_closed')
    view=Screen(bot,f"Task #{task['id']} · {escape(task['title'])}",text,'tasks.png',persistent=True)
    view.button('Open My Panel',lambda i:member_page(bot,i),custom_id='rz:panel:v1')
    return view


def public_leaderboard(bot,rows,cfg=None):
    cfg=settings(cfg)
    text='\n'.join(f"#{r.get('rank',n)} · <@{r['user']}> · **{r['earned']} RC**" for n,r in enumerate(rows,1)) or 'Be the first to earn Ripper Credits.'
    text+=f"\n\nLifetime earned RC · Updated <t:{int(time.time())}:T>\nEqual scores share a rank. Spending does not lower your score. Open a private view below."
    view=Screen(bot,'Ripper Zone · Community Leaderboard',phrase(cfg,'leaderboard_intro')+'\n\n'+text,persistent=True,accent=TEAL)
    from .member_ui import page_view
    for label,period in [('All Time','all'),('This Week','week'),('This Month','month'),('Today','today')]:
        view.button(label,lambda i,p=period:page_view(bot,i,'leaders',period=p),custom_id='rz:leaders:'+period)
    view.button('My Rank',lambda i:page_view(bot,i,'leaders'),custom_id='rz:leaders:mine')
    view.button('My Dashboard',lambda i:member_page(bot,i,'dashboard'),custom_id='rz:leaders:balance')
    return view
