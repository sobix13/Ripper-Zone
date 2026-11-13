# Release 1.1.0 acceptance and traceability

The 138 baseline requirement IDs are retained. Automated checks cover the accounting, real SDK serialization, selected native UI workflows, source adapters, authorization, concurrent operations and deployment simulation. A requirement marked implemented below is not a claim that production Discord or VPS acceptance was performed.

Run all 64 live/operational gates from the baseline audit on the upgraded server where applicable. In particular: actual permissions and private logs, real source event roster counts, moderator reactions, role hierarchy, ticket reservations/refunds, public message recovery, source helper, backups and iOS/desktop rendering.

## Requirement matrix

| ID | Area / requirement | Release disposition |
| --- | --- | --- |
| R001 | Identity · Approved name: Ripper Zone | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R002 | Identity · RC means Ripper Credit; plural Ripper Credits | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R003 | Identity · Independent of Melee; no MC balance migration | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R004 | Economy · One RC account for tasks, events, manual rewards and spin | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R005 | Member panel · Public entry message and button | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R006 | Member panel · Useful home with available activities | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R007 | Member panel · Clear available, reserved and earned balances | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R008 | Member panel · Browsable history | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R009 | Member panel · Personal task participation and rewards | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R010 | Member panel · Weekly and monthly activity summaries | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R011 | Member panel · Personal raffle archive and prizes | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R012 | Member panel · Buttons and selectors for routine workflows | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R013 | Member panel · Back navigation, loading and session expiry | Back/Home navigation and same-message member updates are implemented. Expiry/reopen guidance is in Help; client timeout rendering remains a live gate. |
| R014 | Leaderboard · Publish and bind a working public leaderboard | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R015 | Leaderboard · Public period filters and My Rank | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R016 | Leaderboard · Consistent tied ranks across screens | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R017 | Leaderboard · Pagination beyond the top ten | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R018 | Leaderboard · Personal rank outside the top ten | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R019 | Leaderboard · Calendar-based weeks | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R020 | Leaderboard · Daily and monthly rankings | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R021 | Leaderboard · Rank by earned RC rather than spendable balance | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R022 | Leaderboard · Publish and refresh from administration | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R023 | Leaderboard · Active period, update time and empty state | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R024 | Tasks · Public task with a dedicated thread | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R025 | Tasks · Simple form with separate fields | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R026 | Tasks · Full brief, reward and deadline in the thread | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R027 | Tasks · Manage active and past tasks through the panel | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R028 | Tasks · Contributor and reward counts | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R029 | Tasks · Edit title and instructions after creation | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R030 | Tasks · Explicit policy for changing participation rewards | Base reward locks after participation; closed timing locks. Duplicate creates a new policy. |
| R031 | Tasks · Edit cooldown/deadline and synchronize the brief | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R032 | Tasks · Member task details inside the panel | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R033 | Tasks · One participation reward per member per cycle | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R034 | Tasks · Extra bonuses separate from participation rewards | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R035 | Tasks · End, close and archive with retry | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R036 | Tasks · Choose cycles without memorizing IDs | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R037 | Tasks · Moderator review of posts missed during downtime | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R038 | Tasks · Posting cooldown and moderator bypass | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R039 | Tasks · Reset one member's cooldown from the panel | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R040 | Tasks · Keep submissions inside matching task threads | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R041 | Tasks · Concurrent publication without duplicate threads | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R042 | Tasks · Recover threads and briefs without blind duplicate sends | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R043 | Reactions · View configured emojis and RC values | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R044 | Reactions · Add, edit and remove rules through forms | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R045 | Reactions · Distinguish task participation from fixed emoji rewards | Fixed server-wide emoji rewards replace the old base/quality editor. Task-cycle participation remains separate. |
| R046 | Reactions · Unicode and custom emojis beyond the five-rule baseline | Expanded to 100 configured Unicode/custom emojis with paginated editing. |
| R047 | Reactions · Reject zero fixed rewards, including imported settings | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R048 | Reactions · One reward despite different moderators | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R049 | Reactions · Temporary network failures do not lose awards | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R050 | Reactions · Recover missed reactions | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R051 | Reactions · New amounts affect future awards, not past payments | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R052 | Reactions · Removing a reaction does not reverse RC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R053 | Reactions · Prevent automatic self-rewards | Another moderator must approve automatic/reviewed task rewards. General manual bonuses remain explicit moderator actions. |
| R054 | Reactions · Rewards on messages outside task threads | Authorized moderator reactions now work across accessible server chats and threads, including forum starters. The Award RC message menu remains available. |
| R055 | Snapshots · File-free task snapshots | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R056 | Snapshots · Channel/thread snapshots over a time window | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R057 | Snapshots · Snapshot members reacting to a message | Reaction snapshot implemented with human filtering, paginated enumeration, cap and explicit confirmation. |
| R058 | Snapshots · Routine Rumble/raffle event snapshots without files | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R059 | Snapshots · Rumble includes winners and non-winners | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R060 | Snapshots · Ordinary raffle includes eligible losing participants | Preserves the original eligible pool including losers. Excluded source entrants are not silently reclassified as eligible. |
| R061 | Snapshots · Ordinary raffle participation separate from RC ticket spending | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R062 | Snapshots · Actual source data and valid event metadata | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R063 | Snapshots · Preview recipients and total RC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R064 | Snapshots · Reimporting the same finalized event never pays twice | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R065 | Snapshots · Recorded presence is distinct from moderator approval | Presence is explicitly labeled separately from approval; a cycle snapshot is deliberate moderator batch approval, not peer review. |
| R066 | Manual rewards · Native member selection | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R067 | Manual rewards · Preview and idempotent confirmation | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R068 | Manual rewards · View a member account in administration | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R069 | Manual rewards · Positive/negative corrections with reasons | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R070 | Manual rewards · Revoke invalid rewards and related metrics | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R071 | Manual rewards · Display failures do not contradict committed results | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R072 | RC raffles · Separate feature with public posts and ticket purchases | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R073 | RC raffles · Understandable rules in separate fields | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R074 | RC raffles · Save and edit drafts before publication | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R075 | RC raffles · Atomic reservations, balance checks and ticket caps | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R076 | RC raffles · Frozen price and eligibility contract | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R077 | RC raffles · Purchase cost preview and receipt | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R078 | RC raffles · Minimum entrants, refunds and uncertain eligibility | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R079 | RC raffles · Prize counts reflect eligible participant counts | Public rules say up to N winners; fewer eligible members never promise a guaranteed N prizes. |
| R080 | RC raffles · List, close, cancel and refresh from the panel | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R081 | RC raffles · Show current winners after replacement | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R082 | RC raffles · Claim through My Prizes without finding an old post | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R083 | RC raffles · Delivery, forfeiture and replacement with reasons | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R084 | RC raffles · Verify a saved result without drawing again | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R085 | Roles · Three optional tiers, skippable in the wizard | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R086 | Roles · Native role selection and separate metrics | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R087 | Roles · Save disabled and activate later | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R088 | Roles · Clear task and event counts | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R089 | Roles · Keep only the highest tier; add before removing | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R090 | Roles · Protect access, staff and other bots' registered resources | Configured access/staff and foreign registered roles protected; dedicated-role guidance added. Unknown manual role purpose is not guessed. |
| R091 | Spin · Ten outcomes between 2 and 100 RC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R092 | Spin · 100 RC has a 0.5 percent probability | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R093 | Spin · Overall mean 5 RC, minimum 2 RC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R094 | Spin · Explicit daily click after opening the panel | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R095 | Spin · UTC reset and requests crossing midnight | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R096 | Spin · Animation and a saved, reopenable result | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R097 | Spin · Enable or pause through administration | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R098 | Branding · Selected Rumble artwork | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R099 | Branding · Editable title and welcome message | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R100 | Branding · Configurable About and Support copy | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R101 | Branding · Editable notification and public-message copy | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R102 | Branding · Safe named placeholders without code execution | Whitelisted placeholders supported for twenty templates; five core copy fields use literal text. Financial facts remain separate. |
| R103 | Branding · Consistent copy across display paths | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R104 | Guides · Multipage member guide tailored to RC | Contextual member guide and configurable support copy; existing Crew channel link is selectable. |
| R105 | Guides · In-bot administration guide | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R106 | Setup · Show current configuration | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R107 | Setup · Edit one channel without repeating the wizard | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R108 | Setup · Moving a channel preserves message bindings | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R109 | Setup · Native moderator and primary administrator selection | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R110 | Setup · Configuration history, import and export | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R111 | Setup · Stale forms cannot overwrite newer settings | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R112 | Setup · Finish the wizard with clear publication actions | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R113 | Setup · Pausing new earnings preserves existing reservations | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R114 | Security · Another member cannot operate a private panel | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R115 | Security · Recheck current authority at operation time | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R116 | Security · Integer RC validation without fractional MC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R117 | Security · Private operations separate from public RC activity | Public RC receipts include a short source. Optional private operations retains restricted technical notices and recovery controls. |
| R118 | Accounting · Atomic operations, idempotency and retry safety | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R119 | Accounting · Never automatically restore an older ledger | Legacy configuration/financial schema stays readable; old code cannot execute new presentation jobs. Re-upgrade and retry those jobs. |
| R120 | Installation · Independent user, services, paths and ports | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R121 | Installation · Recoverable token/owner input validation | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R122 | Installation · Upgrade preserves environment and RC | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R123 | Installation · Failed rollback does not leave a healthy service stopped | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R124 | Installation · Exclude nested sensitive files from release bundles | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R125 | Operations · Readable in-panel health, not only JSON | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R126 | Operations · Button-driven retries and binding recovery | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R127 | Operations · Working local verified-missing recovery | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R128 | Operations · Verified daily SQLite backups | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R129 | Operations · Bounded independent automatic troubleshooting | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R130 | Operations · Offsite backup and Crew operational standards | Offsite backup remains unconfigured; no destination or credentials were supplied. |
| R131 | Quality · Exhaustive spin distribution and multiprocess races | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R132 | Quality · End-to-end UI workflows as well as core logic | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R133 | Quality · Ordinary-user and root CI runs | Implemented in the code/panel workflow; automated local checks where applicable. Production behavior remains pending live acceptance. |
| R134 | Quality · Real Discord and VPS acceptance | PENDING LIVE: no production Discord/VPS session was supplied to this implementation environment. |
| R135 | Scope · Exclude quiz, content-submission forms and peer review | Intentionally excluded: quiz, content submission and peer review. Task moderation remains implemented. |
| R136 | Scope · Enable achievement roles later through metrics | Exactly three tiers use earned RC, rewarded task cycles and rewarded events, including voice snapshots. Purchase/holder/onchain metrics are not implemented. |
| R137 | Scope · Record decisions and implementation maps | Baseline audit requirement IDs retained here; implementation and test scope recorded separately from live acceptance. |
| R138 | Scope · Distinguish unfinished local work from published releases | Integrated release 1.2.0 must pass staging and CI before installation. |

## Technical findings F01–F19

| Finding | Resolution |
| --- | --- |
| F01 | System actor zero is explicit; first leaderboard publication persists ID and clears marker. |
| F02 | A shared RANK query powers list and account, excludes zero scores and supports pagination/personal position. |
| F03 | Task briefs use Components V2 and persistent bindings; full 2000-character body and financial rules remain visible. |
| F04 | Reaction input is durable before external processing. Retries retain its original rule and financial identity. |
| F05 | Local verified-missing can persist the explicit system actor. |
| F06 | Task publication checks the conditional claim before creating a thread. |
| F07 | Unknown display failures no longer claim that no financial result exists. |
| F08 | New fixed reaction rules require 1–1000 RC and support up to 100 emojis with pagination. Legacy base markers migrate to 5 RC. Reactions have an explicit pause toggle. |
| F09 | Existing task quality identities return already recorded; rule changes do not top up old reactions. |
| F10 | Public raffle wording states an upper winner ceiling. |
| F11 | Bound-channel edits are refused; explicit movement durably publishes/binds then redirects the original post. |
| F12 | Forms retain the settings revision from opening. |
| F13 | Manual close uses the same durable archival job as automatic expiry. |
| F14 | Rollback checks an isolated backup before stopping services and restores prior active code/services on failure. |
| F15 | Member task lists require a bound thread and published status. |
| F16 | Source policy is explicit: original eligible ordinary-raffle participants including losers; complete Rumble final ranking. |
| F17 | Explicit log View Channel allows for unapproved roles/members are refused; actual server permission acceptance remains required. |
| F18 | Documentation and native tier setup state the exact protected scope and require dedicated roles; no claim of detecting unknown manual role purpose. |
| F19 | Nested env/key/WAL/SHM runtime artifacts are refused in release folders. |

## 1.2.0 acceptance additions

See OPERATIONS.md for the live gates covering grouped member navigation, attachment replacement, mobile colors/artwork, duration units, no DMs, server-wide moderator reactions, public/private receipt routing, failed-send retries and frozen voice/stage snapshots. These gates remain live acceptance tasks, not simulated test claims.
