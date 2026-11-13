"""Member navigation, activity, task details and paginated rankings."""
import calendar
import json
import time
import discord
from . import ui
from .features import SPIN,cycle
from .copy import phrase
from .service import tier_for
from .durations import format_duration


def period_start(period,now=None):
    now=int(time.time() if now is None else now);day=now//86400*86400
    if period=='today':return day
    if period=='week':return day-time.gmtime(now).tm_wday*86400
    if period=='month':return calendar.timegm(time.strptime(time.strftime('%Y-%m-01',time.gmtime(now)),'%Y-%m-%d'))
    return 0


def nav(bot,i,s,page):
    if page=='home':
        links=[('Daily Spin','spin'),('Community Tasks','tasks'),('RC Raffles','raffles'),('My Dashboard','dashboard')]
    elif page=='dashboard':
        links=[('My Prizes','prizes'),('Leaderboard','leaders'),('My Activity','activity'),('History','history')]
    elif page in ('prizes','leaders','activity','history','progress'):
        links=[('Back to Dashboard','dashboard')]
    elif page=='task':links=[('Back to Tasks','tasks')]
    else:links=[]
    if page!='home':links.append(('Home','home'))
    links.append(('Help','help'))
    for label,dest in links:s.button(label,lambda j,p=dest:page_view(bot,j,p))


async def page_view(bot,i,page='home',offset=0,since=0,period='all',selected=0):
    if page=='balance':page='dashboard'
    if page=='help':
        from .guides import member_guide
        return await member_guide(bot,i)
    await ui.defer(i,update=True);member,cfg=await bot.member_access(i)
    a=await bot.db.account(i.guild_id,i.user.id,member.display_name)
    title='Ripper Zone';text='';art='welcome-banner.webp';rows=[];total=0;claim=None
    rank=f"#{a['rank']}" if a['rank'] else 'Not ranked yet'
    if page=='home':
        counts=(await bot.db.query("SELECT (SELECT COUNT(*) FROM tasks WHERE guild=? AND status='active' AND (ends=0 OR ends>?)) tasks,(SELECT COUNT(*) FROM raffles WHERE guild=? AND status='open') raffles",(i.guild_id,int(time.time()),i.guild_id)))[0]
        claim=await bot.db.spin_today(i.guild_id,i.user.id)
        title=f'Welcome, {ui.escape(member.display_name)}'
        text=f"**{a['available']} RC available** · Rank: {rank}\n\nDaily spin: "+(f"received {claim['amount']} RC today" if claim else 'ready' if cfg['active'] and cfg['spin_enabled'] else 'paused')+f"\nActive tasks: {counts['tasks']} · Open RC raffles: {counts['raffles']}\nChoose your next activity."
        if not cfg['active']:text+='\n'+phrase(cfg,'program_paused')
    elif page=='dashboard':
        title='My Dashboard';art='balance.png'
        text=f"**{a['available']} RC available**\n{a['reserved']} RC reserved for raffle tickets\n{a['earned']} RC lifetime earned · Rank: {rank}\n\nSpending does not reduce earned RC or achievement progress."
    elif page=='spin':
        title='Daily RC Spin';claim=await bot.db.spin_today(i.guild_id,i.user.id);art='spin-start.png'
        text=(phrase(cfg,'spin_result',amount=claim['amount']) if claim else 'Press Spin · Free to receive your daily RC.')+f"\nAvailable balance: **{a['available']} RC**\nNext reset: <t:{(int(bot.db.clock())//86400+1)*86400}:R>\n\nOne free spin per UTC day · 2–100 RC.\nOpen Spin Details for reward probabilities."
        if not cfg['active'] or not cfg['spin_enabled']:text+='\n'+phrase(cfg,'spin_paused')
        if cfg['spin_role'] and cfg['spin_role'] not in {r.id for r in member.roles}:text+=f"\nDaily spin also requires <@&{cfg['spin_role']}>."
    elif page=='leaders':
        title='Community Leaderboard';art='leaderboard.webp';start=period_start(period)
        board=await bot.db.leaderboard(i.guild_id,i.user.id,start,offset);rows=board['rows'];total=board['total'];mine=board['mine']
        text=f"Period: **{dict(all='All Time',week='This Week · Monday UTC',month='This Month · UTC',today='Today · UTC')[period]}**\nUpdated <t:{int(time.time())}:T>\n\n"+'\n'.join(f"{'🥇' if r['rank']==1 else '🥈' if r['rank']==2 else '🥉' if r['rank']==3 else str(r['rank'])+'.'} <@{r['user']}> · **{r['earned']} RC**" for r in rows)
        if not rows:text+='No earned RC in this period.'
        text+=f"\n\nYour rank: "+(f"**#{mine['rank']}** · {mine['earned']} RC" if mine else 'No earned RC in this period')+f"\nPage {offset//10+1} of {max(1,(total+9)//10)} · {total} ranked members\nEqual earned RC share the same rank. Ticket spending does not lower rankings."
    elif page=='tasks':
        title='Community Tasks';art='tasks.png';status='closed' if since else 'active'
        where="status='closed'" if since else "status='active' AND (ends=0 OR ends>?)"
        args=(i.guild_id,) if since else (i.guild_id,int(time.time()))
        rows=await bot.db.query(f'SELECT * FROM tasks WHERE guild=? AND thread IS NOT NULL AND {where} ORDER BY id DESC LIMIT 10 OFFSET ?',(*args,offset))
        total=(await bot.db.query(f'SELECT COUNT(*) n FROM tasks WHERE guild=? AND thread IS NOT NULL AND {where}',args))[0]['n']
        text=('Past' if since else 'Active')+' tasks\n\n'+'\n'.join(f"#{r['id']} · {ui.escape(r['title'])} · {r['reward']} RC" for r in rows)
        if not rows:text+='No tasks on this page.'
        text+='\nSelect a task for its full brief, your recorded participation and thread link.'
    elif page=='task':
        t=await bot.db.task(i.guild_id,selected)
        if not t['thread'] or t['status'] not in ('active','closed'):raise ValueError('This task is not published yet.')
        title=f"Task #{t['id']} · {ui.escape(t['title'])}";art='tasks.png';cy=cycle(t,min(int(time.time()),t['ends'] or int(time.time())))
        posts=(await bot.db.query('SELECT COUNT(*) n FROM task_messages WHERE task=? AND user=? AND cycle=?',(selected,i.user.id,cy)))[0]['n']
        paid=await bot.db.query("SELECT id FROM ledger WHERE guild=? AND user=? AND source='task' AND kind='base' AND ref=?",(i.guild_id,i.user.id,f'{selected}:{cy}'))
        text=t['body']+f"\n\nBase reward: {t['reward']} RC · Cycle {cy} · {t['status']}\nCooldown: {format_duration(t['cooldown'])}\nDeadline: "+(f"<t:{t['ends']}:F>" if t['ends'] else 'none')+f"\nYour recorded posts in this cycle: {posts}\n"+(phrase(cfg,'task_received')+'\n' if posts and not paid else '')+'Base reward: '+(phrase(cfg,'already_awarded') if paid else 'not recorded yet')+'\n\n'+cfg['task_footer']
    elif page in ('raffles','prizes'):
        title='My Prizes' if page=='prizes' else 'RC Raffles';art='raffles.png'
        if page=='prizes':
            rows=await bot.db.query('SELECT r.id,r.spec,p.state FROM prizes p JOIN raffles r ON r.id=p.raffle WHERE r.guild=? AND p.user=? ORDER BY r.id DESC LIMIT 10 OFFSET ?',(i.guild_id,i.user.id,offset))
            total=(await bot.db.query('SELECT COUNT(*) n FROM prizes p JOIN raffles r ON r.id=p.raffle WHERE r.guild=? AND p.user=?',(i.guild_id,i.user.id)))[0]['n']
            text='\n'.join(f"#{r['id']} {ui.escape(json.loads(r['spec'])['title'])} · {r['state']}" for r in rows) or 'No prizes on this page.'
            text+='\n\n'+cfg['support_text']
        else:
            rows=await bot.db.query("SELECT id,spec,status FROM raffles WHERE guild=? AND status IN ('open','closing','drawn','cancelled') ORDER BY id DESC LIMIT 10 OFFSET ?",(i.guild_id,offset))
            total=(await bot.db.query("SELECT COUNT(*) n FROM raffles WHERE guild=? AND status IN ('open','closing','drawn','cancelled')",(i.guild_id,)))[0]['n']
            text='\n'.join(f"#{r['id']} {ui.escape(json.loads(r['spec'])['title'])} · {r['status']} · {json.loads(r['spec'])['price']} RC/ticket" for r in rows) or 'No published raffles on this page.'
    elif page=='raffle':
        r=await bot.db.raffle(i.guild_id,selected)
        if r['status'] not in ('open','closing','drawn','cancelled'):raise ValueError('This raffle is not public yet.')
        s=ui.raffle_view(bot,r,cfg);s.owner=i.user.id;s.timeout=600
        s.button('My Prizes',lambda j:page_view(bot,j,'prizes'));s.button('RC Raffles',lambda j:page_view(bot,j,'raffles'))
        s.button('Back to Raffles',lambda j:page_view(bot,j,'raffles'));s.button('Home',lambda j:page_view(bot,j,'home'))
        return await ui.show(i,s,update=True)
    elif page=='progress':
        if not cfg['roles_enabled']:raise ValueError('Achievement roles are not enabled yet.')
        title='My Community Progress';art='progress.png';current=tier_for(a,cfg['tiers'])
        text='Current tier: '+(f"<@&{current['role']}>" if current else 'Getting started')+f"\nEarned: {a['earned']} RC · Rewarded task cycles: {a['tasks']} · Rewarded events: {a['events']}\n\n"
        text+='\n'.join(f"<@&{t['role']}> · Remaining: {max(0,t['earned']-a['earned'])} RC, {max(0,t['tasks']-a['tasks'])} task cycles, {max(0,t['events']-a['events'])} events" for t in cfg['tiers'])
        text+='\nAll three requirements apply. Only your highest eligible tier remains.'
    elif page=='activity':
        title='My Community Activity';art='progress.png'
        text=f"Rewarded task cycles: {a['tasks']}\nRewarded events: {a['events']}\nLifetime earned: {a['earned']} RC\n"
        for label,p in [('Today','today'),('This Week','week'),('This Month','month')]:
            score=(await bot.db.query('SELECT COALESCE(SUM(de),0) n FROM ledger WHERE guild=? AND user=? AND at>=?',(i.guild_id,i.user.id,period_start(p))))[0]['n'];text+=f'\n{label}: {score} net earned RC'
        text+='\n\nThese are recorded RC contributions, not estimated chat activity.'
    elif page=='history':
        title='My RC History';art='history.webp';total=(await bot.db.query('SELECT COUNT(*) n FROM ledger WHERE guild=? AND user=?',(i.guild_id,i.user.id)))[0]['n'];rows=await bot.db.history(i.guild_id,i.user.id,offset)
        text='\n'.join(f"#{r['id']} · <t:{r['at']}:d> · {r['source']}/{r['kind']}\n{r['da']:+} available / {r['dr']:+} reserved / {r['de']:+} earned\n{ui.escape(r['reason'])[:110]}" for r in rows) or 'No transactions on this page.'
        text+=f'\nPage {offset//10+1}'
    else:raise ValueError('Unknown panel page.')
    key={'leaders':'leaderboard_intro','progress':'progress_intro'}.get(page)
    if key:text=phrase(cfg,key)+'\n\n'+text
    if page=='spin':text=phrase(cfg,'spin_claimed',day=claim['day'])+'\n'+text if claim else phrase(cfg,'spin_ready')+'\n'+text
    accent=ui.TEAL if page in ('dashboard','leaders','prizes','activity','history','progress') else ui.GOLD if page in ('spin','raffles') else ui.INK
    s=ui.Screen(bot,title,text,art,owner=i.user.id,full_art=page in ('home','spin'),accent=accent)
    principal=False
    if page=='home':
        principal=i.user.id in (set(getattr(bot,'owners',()))|set(cfg['primary_users'])|{getattr(i.guild,'owner_id',0)}) or bool(set(cfg['manager_roles'])&{r.id for r in member.roles})

    if page=='spin' and not claim:s.button('Spin · Free',lambda j:ui.spin(bot,j),discord.ButtonStyle.success,disabled=not cfg['active'] or not cfg['spin_enabled'] or bool(cfg['spin_role'] and cfg['spin_role'] not in {r.id for r in member.roles}))
    if page=='spin':s.button('Spin Details',lambda j:spin_details(bot,j))
    if page=='leaders':
        for label,p in [('All Time','all'),('This Week','week'),('This Month','month'),('Today','today')]:s.button(label,lambda j,p=p:page_view(bot,j,'leaders',period=p))
        s.button('Previous',lambda j:page_view(bot,j,'leaders',max(0,offset-10),period=period),disabled=not offset)
        s.button('Next',lambda j:page_view(bot,j,'leaders',offset+10,period=period),disabled=offset+10>=total)
        minepos=(mine['position']-1)//10*10 if mine else 0
        s.button('My Rank',lambda j:page_view(bot,j,'leaders',minepos,period=period))
    if page in ('tasks','raffles','prizes') and rows:
        dest='task' if page=='tasks' else 'raffle'
        s.select(discord.ui.Select(placeholder='Select an item',options=[discord.SelectOption(label=f"#{r['id']} "+(r['title'] if page=='tasks' else json.loads(r['spec'])['title'])[:85],value=str(r['id'])) for r in rows]),lambda j,v:page_view(bot,j,dest,selected=int(v[0])))
    if page=='tasks':
        s.button('Active',lambda j:page_view(bot,j,'tasks'));s.button('Past',lambda j:page_view(bot,j,'tasks',since=1))
    if page in ('tasks','raffles','prizes','history'):
        s.button('Previous',lambda j:page_view(bot,j,page,max(0,offset-10),since),disabled=not offset)
        s.button('Next',lambda j:page_view(bot,j,page,offset+10,since),disabled=offset+10>=total)
    if page=='task':s.box.add_item(discord.ui.ActionRow(discord.ui.Button(label='Open Task Thread',url=f'https://discord.com/channels/{i.guild_id}/{t["thread"]}')))
    if cfg['roles_enabled'] and page=='dashboard':s.button('My Progress',lambda j:page_view(bot,j,'progress'))
    if cfg['support_channel'] and page in ('prizes','home'):s.box.add_item(discord.ui.ActionRow(discord.ui.Button(label='Open Support Tickets',url=f'https://discord.com/channels/{i.guild_id}/{cfg["support_channel"]}')))
    nav(bot,i,s,page)
    if principal:s.button('Administration',lambda j:ui.admin_page(bot,j))
    await ui.show(i,s,update=True)


async def spin_details(bot,i):
    await ui.defer(i,update=True);await bot.member_access(i)
    text='One free claim per UTC calendar day. Reset: 00:00 UTC.\n\n'+'\n'.join(f'{amount} RC · {weight/100:g}%' for amount,weight in SPIN)
    text+='\n\nLong-run average: 5 RC. Each spin is independent. Wheel symbols are decorative; your reward is shown as text. Your reward is saved before the animation.'
    s=ui.Screen(bot,'Daily Spin Details',text,'spin.png',owner=i.user.id,accent=ui.GOLD)
    s.button('Back to Spin',lambda j:page_view(bot,j,'spin'));s.button('Home',lambda j:page_view(bot,j,'home'))
    await ui.show(i,s,update=True)
