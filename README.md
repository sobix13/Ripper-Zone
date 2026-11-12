# Ripper Zone

Rip Cars community participation, powered by Ripper Credits (RC). Release 1.1.0.

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
| Home, My RC, Daily Spin | Dashboard and current status |
| Select active or past task; open its thread | Create, inspect, edit, duplicate, close and archive tasks |
| Recorded posts and base reward status | Participants, reviewed contributions, extra quality RC, cycle snapshots, cooldown reset and reaction recovery |
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
- **Task Cycle:** choose a task and cycle. Base payments share their identity with reaction and individual review awards.
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

Default moderator reactions:

| Reaction | Award |
| --- | --- |
| ✅ | Task base RC, once per member per cycle |
| 🏅 | Separate 5 RC quality bonus, once per message and emoji |

Settings → Reward Reactions changes emojis and amounts. Base reads the task reward; quality is an integer from 1 to 1000 RC. Rules support Unicode and server emojis. New reaction events can be paused. A recorded inbox retains the original rule while retrying temporary failures. Existing payments are never topped up after changing a rule. Another moderator must review your own task contribution.

Presence recording is not individual content approval. Cycle snapshots are moderator-approved batch rewards. Review the people and period before confirming. Posts made during downtime need Reviewed Contribution; reaction recovery scans up to 200 recent messages and does not invent missing post records. Moderators bypass posting cooldown. Members receive a cooldown explanation, with a thread fallback if DMs are closed.

## Daily RC spin

A member explicitly presses **Spin · Free**, once per UTC day. Opening a panel does not claim it.

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

Reset is 00:00 UTC (03:30 Tehran). Exact long-run mean is 5 RC, not a guaranteed 500 RC per 100 spins. Secure integer sampling, request binding and an atomic claim/ledger transaction prevent duplicate rewards across concurrent clicks, midnight and restart. Odds remain fixed in distribution version 1.

## Public RC raffles and roles

Draft rules are editable until publication. Publishing freezes ticket price, cap, winner ceiling, minimum eligible entrants, deadline and the access-role contract. Purchases reserve RC atomically. Closing checks every entrant's current eligibility against the frozen contract. An uncertain HTTP lookup stops settlement rather than excluding an entrant. Cancellation, insufficient eligible entrants and definitely ineligible purchases refund reservations. Results commit before the public post is refreshed.

Draws use a prepublished seed commitment and deterministic weighted HMAC selection without repeated winners. Prize claim, delivery, forfeiture and replacement are recorded. Replacement retains original weights, excludes all prior winners and charges no new RC. Verify Draw downloads the proof. A proof checks selection consistency, not an operator's honesty or independent truth of Discord observations.

Exactly three optional achievement tiers use earned RC, rewarded task cycles and paid events. All three thresholds apply; only the highest eligible role remains. Skip during setup or save disabled and enable later. Use dedicated zero-permission roles below the bot, not Ripper, OG, staff or another bot's role. Validation protects configured access/staff roles and foreign registered resources; it cannot identify every manually created role's intended purpose from its name.

## First installation

Create a separate Discord application. Enable **Server Members Intent** and **Message Content Intent**. Invite using **bot** and **applications.commands**. Grant View Channels, Send Messages, Send Messages in Threads, Read Message History, Embed Links, Attach Files, Add Reactions, Manage Messages, Create Public Threads and Manage Threads. Grant Manage Roles for achievement tiers. Do not grant Administrator.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv curl
git clone https://github.com/sobix13/Ripper-Zone.git
cd Ripper-Zone
sudo bash scripts/install.sh
```

The installer privately requests the token, server ID (default 1560350027631562923) and required owner user IDs. Invalid fields are re-prompted individually. Prepare five text channels, including a private moderator log. Open `/ripper setup`, select channels/access, skip or configure roles, activate, then publish the panel and leaderboard using the setup completion buttons. Health checks permissions and accounting.

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
