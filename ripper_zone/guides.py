"""Contextual guides reachable from the member and moderator panels."""
from . import ui

MEMBER = [
    ('Ripper Credits', 'RC record your contributions to the Rip Cars community. Available RC are ready to spend. Reserved RC belong to open raffle tickets. Lifetime earned RC determine leaderboard rank and achievement progress. Spending does not lower lifetime earnings. RC have no cash value.'),
    ('Community Tasks', 'Open Community Tasks and follow the link to a task thread. Read its instructions, reward, deadline and posting cooldown. Post your contribution there. A moderator reviews it. The base reaction pays the task reward once per member per cycle, even across multiple posts. Quality reactions award separate bonuses. Removing a reaction does not reverse an award. Contact a moderator if a reward needs review.'),
    ('Daily Spin', 'Open Daily Spin and press Spin · Free. There is one claim per UTC calendar day, resetting at 00:00 UTC. Opening the panel alone does not claim it. Your reward is saved before a short wheel animation in the same private message. Wheel symbols are decorative; your actual RC amount appears as text. Reopening a claimed day shows its saved result without another animation. Rewards range from 2 to 100 RC. The 100 RC chance is 0.5%. The long-run average is 5 RC, not a guaranteed amount over any fixed number of spins.'),
    ('Events and Snapshots', 'Rumble and ordinary raffle participation rewards come from a finalized event snapshot imported by a moderator. Winning is not required. Reimporting the same event does not pay twice. This participation reward is separate from paid RC raffle ticket spending.'),
    ('RC Raffles and Prizes', 'Open a public RC raffle post, choose Buy Tickets, enter the quantity and confirm its total cost. RC are reserved until the draw. Eligible entries are spent at closing. Cancelled raffles and ineligible entries are refunded. One member receives at most one prize per raffle. Winners press Claim Prize and follow the prize-support instructions. Verify Draw provides the frozen rules and selection proof.'),
    ('Progress and Support', 'Achievement roles are optional. When enabled, the three tiers use lifetime earned RC, completed tasks and event participation. All three requirements must be met for a tier. Only your highest eligible achievement role remains. Open History for recorded rewards and spending.'),
]

ADMIN = [
    ('Setup and Access', 'Setup Wizard saves five channels, the community access role and moderator roles. Achievement roles are optional and skippable. Settings edits one field at a time without repeating the wizard. Move Public Message relocates a published panel or leaderboard and redirects its previous post. Primary administrators control settings, access, corrections and recovery. Moderators manage tasks, awards, snapshots, raffles and reports. Every submitted action checks current membership and permissions again.'),
    ('Reaction Rewards', 'Settings → Reward Reactions shows each emoji, its type and its RC value. Add Base Reaction pays the base reward configured on the task. Add Quality Reaction accepts a separate amount from 1 to 1000 RC. Select a rule to edit or remove it. Custom server emojis are supported. At most five rules are active. Only configured moderators and primary administrators trigger awards. Two moderators using the same reaction on the same post do not pay twice. Base awards are shared with task snapshots and manual reviews, so each member receives one base award per cycle.'),
    ('Task Lifecycle', 'Community Tasks → New Task selects one-time, daily or weekly recurrence, then separate fields for title, instructions, base RC, cooldown and duration. Each task gets its own public thread. Select a task to edit details, adjust timing, snapshot a cycle, record a reviewed contribution, reset cooldowns, duplicate it or close it. Edits refresh the original thread brief. Recurrence is fixed at creation. Base RC is fixed after the first accepted contribution or reward. Duplicate a task for a new reward policy.'),
    ('Awards and Event Snapshots', 'RC and Members → Award RC selects members and previews the total before confirmation. Event Snapshot lists the latest 25 finalized Rumble or ordinary raffle events from the local VPS connection. No manual file upload is needed. It checks server, source, roster and checksum. Confirmed event imports pay each participant once, including non-winners in the eligible exported pool. Member Account shows history. Corrections and invalid-reward reversals append entries without deleting the original history.'),
    ('Paid RC Raffles', 'RC Raffles → New RC Raffle creates a draft with separate fields. Review and edit the draft before publishing its public ticket post. Price, ticket cap, winners, minimum participants, deadline and access requirement freeze on publication. Manage the raffle to close early, cancel and refund, inspect prizes, record delivery or forfeiture, select replacement winners and download the proof. Replacements use the original frozen pool. An uncertain publication needs binding recovery, never a blind repost.'),
    ('Roles and Program Controls', 'Settings → Achievement Roles chooses three distinct roles with native role selectors, then earned RC, tasks and event thresholds. Review the complete set before saving. Save disabled to activate later. Roles must have no server permissions and sit below the bot. Settings → Program Controls pauses the program or daily spin. Pausing new earnings does not cancel existing raffle reservations or stop their settlement.'),
    ('Reports and Recovery', 'Reports downloads leaderboard, ledger, tasks, raffles or audit CSV. Settings provides JSON export, file import with a changed-fields preview and history restoration. Health checks database consistency, permissions and failed jobs. Primary administrators retry jobs, run a backup, clear an accounting pause only after reconciliation, and request a bounded service restart. Publication Recovery binds a verified existing panel, leaderboard, task thread or raffle post. Stored RC data stay on the VPS during upgrades.'),
]


async def member_guide(bot,i,page=0):
    if not i.response.is_done():await i.response.defer(ephemeral=True,thinking=True)
    _,cfg=await bot.member_access(i)
    title,text=MEMBER[page]
    from .copy import phrase
    if page==0:text=phrase(cfg,'help_intro')+'\n\n'+cfg['about_text']+'\n\n'+text
    if page==5:text+='\n\n'+cfg['support_text']
    screen=ui.Screen(bot,f'Help · {title}',text,'help.webp',owner=i.user.id)
    _navigation(screen,lambda j,p:member_guide(bot,j,p),MEMBER,page)
    screen.button('My Panel',lambda j:ui.member_page(bot,j))
    await ui.show(i,screen)


async def admin_guide(bot,i,page=0):
    from .admin_ui import guard,home
    await guard(bot,i)
    title,text=ADMIN[page]
    screen=ui.Screen(bot,f'Admin Guide · {title}',text,'help.webp',owner=i.user.id)
    _navigation(screen,lambda j,p:admin_guide(bot,j,p),ADMIN,page)
    screen.button('Administration',lambda j:home(bot,j))
    await ui.show(i,screen)


def _navigation(screen,action,pages,page):
    import discord
    selector=discord.ui.Select(placeholder='Choose a guide',options=[discord.SelectOption(label=title,value=str(n),default=n==page) for n,(title,_) in enumerate(pages)])
    screen.select(selector,lambda j,values:action(j,int(values[0])))
    screen.button('Previous',lambda j:action(j,page-1),disabled=page==0)
    screen.button('Next',lambda j:action(j,page+1),disabled=page==len(pages)-1)
