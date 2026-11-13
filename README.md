# Ripper Zone

Rip Cars community participation, powered by Ripper Credits (RC). Release 1.2.0.

Public RC receipts use readable, clickable names and a short reward source: `@member received 8 RC for receiving 💜.`, `@member received 3 RC from the daily spin.`, or `@member received 5 RC from the Rumble #123 snapshot.` Names are resolved from Discord or the saved account. Notifications remain disabled. Pending receipts are formatted at delivery; already-posted messages are not edited. Technical accounting records stay in History, reports and the optional private operations channel.

Home has four actions: Daily Spin, Community Tasks, RC Raffles and My Dashboard, with Help secondary. My Dashboard holds balance details, My Prizes, Leaderboard, My Activity, History and optional My Progress. Private member navigation replaces the same message and its artwork. Public buttons open a new private panel and never edit the public post. Burgundy identifies home/tasks, teal identifies dashboard pages, and muted gold identifies spin/raffles. The existing Rumble artwork is reused without runtime image generation. No automatic submission or cooldown DMs are sent.

One account combines community tasks, finalized Rumble/ordinary-raffle participation, moderator awards and a free daily spin. Available RC buy public raffle tickets. Spending does not reduce lifetime earned RC, rank or achievement progress.

Quiz, content submission forms and peer review are excluded. Gate and Crew keep verification and support tickets. This application has its own token, service user, SQLite ledger and independent recovery helper.

## Upgrade an existing installation

```bash
cd ~/Ripper-Zone
git pull --ff-only
sudo bash scripts/install.sh
```

Existing credentials, settings and RC remain in place. Open the public member panel or `/ripper admin` after the upgrade. Existing member-panel buttons work after restart. In Settings, refresh the public panel and leaderboard. Use Messages and Branding to edit copy, and Channels and Access to select the existing Crew ticket channel.

## Daily operation through the panels

| Member | Moderator / primary administrator |
| --- | --- |
| Home, My Dashboard, Daily Spin | Dashboard and current status |
| Select active or past task; open its thread | Create, inspect, edit, duplicate, close and archive tasks |
| Recorded posts and base reward status | Participants, reviewed contributions, extra RC bonuses, cycle snapshots, cooldown reset and reaction recovery |
| Public / private leaderboard, personal rank and pagination | Publish, refresh or move the public leaderboard |
| All Time, Today, Monday-based This Week, This Month | Reaction editor: add, edit, remove, enable / pause |
| Raffle details, ticket confirmation and receipts | Draft editor, publish, close, cancel/refund and message recovery |
| My Prizes, claim and support instructions | Prize delivery, forfeiture, replacement and draw proof |
| Activity, progress and RC history | Native member selection, account history, corrections and reward reversal |
| Member guide and About | Editable messages, channels, access, three-role wizard and program controls |
| Existing Crew support channel | CSV reports, settings history/import/export, health, backups and bounded recovery |

Ordinary workflows are buttons, selectors and forms. Slash commands remain shortcuts. The Discord message menu also has **Award RC** for a reviewed extra manual contribution.

Primary administrators are OWNER_IDS, the server owner and configured primary users. Configured moderator roles handle routine operations. Permissions are fetched again for mutations. Private panels belong to their opener and expire after ten minutes.

## Snapshots without manual files

Open Administration → Snapshots:

- **Rumble Event / Ordinary Raffle Event:** choose a recent finalized event, enter RC per participant, inspect the roster count and total, then confirm.
- **Voice / Stage Call:** freeze the connected human roster, review/edit RC per person, inspect the total and confirm. `/ripper snapshot amount:10` in a voice/stage chat captures that call immediately. Later joins/departures do not change the roster; repeating a confirmation pays zero. Presence does not prove watching a stream.
- **Task Cycle:** choose a task and cycle. Task participation payments share their identity with individual task reviews; reaction rewards are separate.
- **Channel / Thread Window:** choose a channel or active thread and time window. Human authors are counted once. The 5000-message cap aborts an incomplete scan without paying it.
- **Message Reactions:** paste a message link and emoji. Human participants are read across API pages, then previewed.

The independent local helper reads only the two configured source databases with SQLite read-only connections. Zone's service account is not granted access to them. The authenticated endpoint is bound to localhost and accepts a fixed source name and event ID, never a Discord-supplied file path or SQL.

Defaults match the inspected VPS installations:

```text
RUMBLE_DATABASE_PATH=/opt/ripcars-rumble/shared/data/rumble.sqlite3
RAFFLE_DATABASE_PATH=/var/lib/ripcars-raffle/raffle.sqlite3
```

If the ordinary raffle uses another DB_PATH in `/etc/ripcars-raffle.env`, the helper reads that setting when no Zone override exists. For a custom installation, set the appropriate source path in `/etc/ripper-zone.env` and restart only `ripper-zone-recovery.service`. No source bot is stopped, upgraded or written by Zone.

Rumble exports its complete finalized ranking, including non-winners. Ordinary raffle exports the **initial eligible pool**, including eligible losing entrants, rather than later replacement pools or accounts excluded by the source raffle. This participation rule is displayed in the preview. Paid RC raffle purchases do not generate participation RC.

Finalized event identity is source + server + event + member. Reconfirming/importing the same event pays zero. A different roster or amount for an already-paid event is refused. General window/reaction snapshots are separate explicit manual award operations; the same confirmation is idempotent, but starting another snapshot is a new award. The export/import CLI remains an advanced transfer fallback.

## Community tasks and reactions

Create a task, choose one-time/daily/weekly recurrence, then enter title, instructions, base RC, cooldown and duration in separate fields. Each task gets a public thread and a durable brief. Editing refreshes the original brief. Base RC becomes fixed after participation starts; duplicate a task for a new reward policy. Daily cycles start at UTC midnight; weekly cycles use the task's creation date at UTC midnight.

All configured reactions use a fixed RC amount. The default ✅ and 🏅 each award 5 RC, once per message and emoji, across all accessible server chats and threads. Settings → Reward Reactions adds, edits, removes or pauses up to 100 rules with pagination and recognizable emoji labels. Amounts range from 1 to 1000 RC. Only authorized moderators award RC; bots and self-awards are excluded. Two moderators, re-adds and changed amounts never top up an existing message/emoji reward.

Legacy quality amounts are retained. A legacy task-base reaction had no fixed amount; it becomes a fixed 5 RC rule. Review these values after upgrading. Already-queued legacy reviews retain their original task/cycle contract. Task-cycle snapshots and individual task participation reviews remain a separate reward, once per member per cycle.

Task cooldown and duration fields accept English digits with s/m/h/d, for example 12s, 12m, 12h or 12d, up to 90d. Use `none` explicitly for no cooldown or no deadline. A bare number is rejected. Set Deadline accepts these durations from the time of saving, an absolute UTC date, or `none`. Existing stored integer times remain unchanged; recurrence stays separate. Public briefs and private task details show readable units. Submissions are recorded without a DM; cooldown rejections receive a short thread notice, limited to one per member/task per 30 seconds and deleted after ten seconds.

The setup channel formerly labeled moderator log is now **Public RC activity channel**. Select the community-visible destination in Settings → Channels and Access. **Private operations channel** is a separate optional field for technical notices and the recovery status controls. Receipt failures appear in Health; Retry RC Receipts only resends failed effects and never re-awards RC. Changing the public RC destination also retries failed receipts. Do not place recovery controls in the public activity channel.

## Daily RC spin

A member explicitly presses **Spin · Free**, once per UTC day. Opening a panel does not claim it.

Spin Details shows the complete probability table. The private spin page displays the bundled `spin-start.png`. A successful new claim commits its RC before the same private message shows `spin-decelerating.gif`: a shared four-second animation that slows down and stops. Its only button is disabled. The message then returns to the still artwork with the saved reward, current available balance and next reset. Wheel symbols are decorative; amounts appear in text. An already-claimed day skips animation, including after reconnect or service restart. A failed animation edit skips the wait; failed final media delivery falls back to a private text receipt. No images are generated at runtime and no web host or new dependency is required. GIF autoplay and timing on real Discord clients remain part of live acceptance.

| RC | Probability |
| ---: | ---: |
| 2 | 33% |
| 3 | 22% |
| 4 | 14% |
| 5 | 9% |
| 6 | 7% |
| 8 | 5% |
| 10 | 4% |
| 15 | 3% |
| 20 | 2.5% |
| 100 | 0.5% |

Reset is 00:00 UTC. Exact long-run mean is 5 RC, not a guaranteed 500 RC per 100 spins. Secure integer sampling, request binding and an atomic claim/ledger transaction prevent duplicate rewards across concurrent clicks, midnight and restart. Odds remain fixed in distribution version 1.

## Public RC raffles and roles

Draft rules are editable until publication. Publishing freezes ticket price, cap, winner ceiling, minimum eligible entrants, deadline and the access-role contract. Purchases reserve RC atomically. Closing checks every entrant's current eligibility against the frozen contract. An uncertain HTTP lookup stops settlement rather than excluding an entrant. Cancellation, insufficient eligible entrants and definitely ineligible purchases refund reservations. Results commit before the public post is refreshed.

Draws use a prepublished seed commitment and deterministic weighted HMAC selection without repeated winners. Prize claim, delivery, forfeiture and replacement are recorded. Replacement retains original weights, excludes all prior winners and charges no new RC. Verify Draw downloads the proof. A proof checks selection consistency, not an operator's honesty or independent truth of Discord observations.

Exactly three optional achievement tiers use earned RC, rewarded task cycles and rewarded events. All three thresholds apply; only the highest eligible role remains. Skip during setup or save disabled and enable later. Use dedicated zero-permission roles below the bot, not Ripper, OG, staff or another bot's role. Validation protects configured access/staff roles and foreign registered resources; it cannot identify every manually created role's intended purpose from its name.

## First installation

Create a separate Discord application. Enable **Server Members Intent** and **Message Content Intent**. Invite using **bot** and **applications.commands**. Grant View Channels, Send Messages, Send Messages in Threads, Read Message History, Embed Links, Attach Files, Add Reactions, Manage Messages, Create Public Threads and Manage Threads. Grant Manage Roles for achievement tiers. Do not grant Administrator.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv curl
git clone https://github.com/sobix13/Ripper-Zone.git
cd Ripper-Zone
sudo bash scripts/install.sh
```

The installer privately requests the token, server ID (default 1560350027631562923) and required owner user IDs. Invalid fields are re-prompted individually. Prepare five text channels, including the public RC activity feed. An optional separate private operations channel holds technical notices and recovery controls. Open `/ripper setup`, select channels/access, skip or configure roles, activate, then publish the panel and leaderboard using the setup completion buttons. Health checks permissions and accounting.

## Verification and operations

The installer stages and checks code, runs the full simulated suite, verifies an isolated SQLite copy, backs up existing data and activates only Zone's two services. Extended presentation settings are stored separately so the previous release still reads the legacy settings row. Rollback checks a backup before stopping the running service and restores the previous running state on failure. It switches code without rewinding the ledger.

The independent helper diagnoses readiness and worker progress, and requests bounded restarts: three failed probes, no more than three attempts per 15 minutes and at least 120 seconds apart. Credential/intents markers and failed SQLite integrity checks stop automatic restart. It does not repair corrupt financial records. Daily backups are verified and local; offsite storage is not configured.

```bash
sudo systemctl status ripper-zone.service ripper-zone-recovery.service --no-pager
curl -fsS http://127.0.0.1:3040/health
sudo journalctl -u ripper-zone.service -n 80 --no-pager
```

[Administration](docs/ADMIN.md) · [Operations](docs/OPERATIONS.md) · [Product](docs/PRODUCT.md) · [Validation](docs/VALIDATION.md) · [Acceptance](docs/ACCEPTANCE.md)

The test suite uses real SQLite, processes, SDK components and HTTP serialization with simulated Discord effects. Live Discord/VPS acceptance is separate and is not claimed by passing automated tests.
