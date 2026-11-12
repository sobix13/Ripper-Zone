# Ripper Zone

Rip Cars community participation bot. Currency: Ripper Credits, displayed as RC.

Python 3.12+, discord.py 2.7.1, private SQLite ledger and systemd. This is an independent application, token, service and database. It does not reuse Melee balances or replace Gate, Crew, Rumble or the ordinary Raffle bot.

## Features

| Area | Behavior |
| --- | --- |
| Member panel | Private balance, daily spin, community tasks, RC raffles, leaderboard, history and help |
| Community Tasks | One public thread per task, member posts, moderator reward reactions, reviewed manual awards and cycle snapshots |
| Event participation | Import the finalized Rumble roster or ordinary-raffle initial eligible pool, including losers |
| RC accounting | Available, reserved and earned balances; atomic ledger; explicit corrections and reward revocation |
| Daily Spin | One free claim per member per UTC day; ten outcomes; exact mean 5 RC |
| RC raffles | Public ticket purchase, private cost confirmation, atomic reservations, weighted draws, refunds and prize handling |
| Achievement roles | Exactly three optional tiers; setup skip; earned RC, task and event metrics; highest eligible role |
| Operations | Setup wizard, access control, CSV reports, settings history, doctor, verified backups and independent bounded recovery |
| Branding | Original Rumble artwork in native Discord Components V2 panels |

Quiz, content submission forms and peer review are excluded from this version.

## Install on the VPS

Create a separate Discord application named **Ripper Zone**. In its Bot settings enable **Server Members Intent** and **Message Content Intent**. Invite it to the Rip Cars server using scopes **bot** and **applications.commands**.

Grant View Channels, Send Messages, Send Messages in Threads, Read Message History, Embed Links, Attach Files, Add Reactions, Manage Messages, Create Public Threads and Manage Threads. Grant Manage Roles if achievement tiers will be enabled. Do not grant Administrator. Put the bot role above its three achievement roles. Those roles must have zero server permissions.

On Ubuntu 24.04:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv curl
git clone https://github.com/sobix13/Ripper-Zone.git
cd Ripper-Zone
sudo bash scripts/install.sh
```

The installer prompts privately for the new bot token, server ID and your Discord user ID. The server defaults to **1560350027631562923**. No token belongs in GitHub, Discord messages or shell command arguments.

Installation stages a root-owned release and venv, installs the pinned dependency lock, runs the full simulated test suite, checks an isolated database copy, backs up an existing database and then activates this bot's two services. Existing credentials and the live RC ledger are preserved during upgrades.

The readiness wait is bounded. If startup fails, the previous code is restored when one exists. A new installation with a wrong token or disabled privileged intents needs the cause corrected before restarting.

## First Discord setup

1. Prepare five existing text channels: member panel, community tasks, leaderboard, public RC raffles and private moderator logs.
2. Run **/ripper setup** as the configured owner or server owner.
3. Select the five channels, the existing Ripper access role and moderator roles. The wizard saves each selection.
4. Skip achievement roles, or configure exactly three existing, unprivileged roles and their metrics. Role names and thresholds are your choices.
5. Activate the program.
6. Open **/ripper admin**, then **Publish Member Panel**.
7. Run **/ripper leaderboard_publish**.
8. Run **/ripper doctor** and complete the [live acceptance checklist](docs/OPERATIONS.md#live-acceptance).

The moderator log channel must be hidden from @everyone and the community access role. The bot does not change channel permission overwrites, Gate verification, OG/staff roles or other bots' settings.

Set extra primary administrators or moderator role IDs using **/ripper access**. Environment OWNER_IDS and the server owner remain primary administrators. Discord's Administrator permission alone does not grant Zone administration.

## Daily Spin

Opening the panel does not claim the reward. Members press **Spin · Free**.

| Reward | Probability |
| --- | ---: |
| 2 RC | 33% |
| 3 RC | 22% |
| 4 RC | 14% |
| 5 RC | 9% |
| 6 RC | 7% |
| 8 RC | 5% |
| 10 RC | 4% |
| 15 RC | 3% |
| 20 RC | 2.5% |
| 100 RC | 0.5% |

Reset: **00:00 UTC**, currently **03:30 Tehran**. Minimum 2, maximum 100, overall expected value exactly 5 RC. An individual set of 100 spins is not guaranteed to produce 500 RC. The conditional mean of the eight middle outcomes is 768/133 RC, approximately 5.774.

The distribution is versioned and immutable within v1. It uses secure integer sampling across 10,000 outcomes. Daily claim, ledger entry and request binding commit together. Parallel clicks, process death and a retried request crossing midnight do not create another reward.

## Community Tasks

Use **/ripper admin → New Task**. Set instructions, base reward, period (once/daily/weekly), posting cooldown and optional end time. The bot creates a public thread and posts the instructions.

Members post text, photos or links in that thread. Default moderator reactions:

| Reaction | Action |
| --- | --- |
| ✅ | Award the task's base RC once per member and cycle |
| 🏅 | Award a separate 5 RC quality bonus once per message and reaction |

Configure reactions using **/ripper reactions**. Multiple moderators and a later task snapshot share the same base reward identity. Quality rewards are separate and explicit.

**/ripper task_snapshot** previews accepted contributors for a selected cycle. **/ripper task_manage list** shows the current cycle number. Daily cycles reset at UTC midnight. Weekly cycles last seven days from the task's creation date at UTC midnight. One-time tasks use cycle 0.

Posting cooldown and reward period are separate. Moderators bypass posting cooldown. Over-cooldown posts are deleted and a DM is attempted. Permission failures appear in logs. Posts made while the bot was offline need moderator review through **/ripper task_reward**. The bot does not reconstruct missed participation from unrelated chat history.

Use **task_manage** to close/archive tasks, change/reset cooldowns, resend a brief or bind a created thread after an uncertain response. Deadlines close tasks and queue thread archival. Reviews of an already accepted cycle remain possible after closing.

## Event snapshots from existing bots

The source bots keep their databases private. Run the export tool as an account already allowed to read that source database, or as root. Zone never writes to the source database.

```bash
sudo /opt/ripper-zone/current/.venv/bin/python /opt/ripper-zone/current/scripts/export_event.py \
  rumble /ACTUAL/PATH/rumble.sqlite3 1560350027631562923 GAME_ID > rumble-event.json

sudo /opt/ripper-zone/current/.venv/bin/python /opt/ripper-zone/current/scripts/export_event.py \
  raffle /ACTUAL/PATH/raffle.sqlite3 1560350027631562923 RAFFLE_ID > raffle-event.json
```

Replace the path and event ID with actual values from the source bot. Upload the JSON to **/ripper snapshot**, choose RC per person, review the participant count and confirm.

Rumble support targets the inspected 1.2 schema: finalized games, complete ranking IDs and matching game player count. Ordinary Raffle support targets the inspected 1.1 schema: completed initial eligible draw pool, not winners only or replacement rounds. Truncated/unknown source formats fail closed.

An export contains source, guild, event ID, sorted participant IDs and checksum. It contains no seeds, tokens or personal profiles. The checksum detects accidental changes; it is not a signature that authenticates a moderator's source file. Snapshot permission is therefore a financial moderator permission.

Reimporting the same source/guild/event pays zero. Changing its amount or participant list is rejected. Invalid rewards are corrected with a recorded ledger operation, not another import.

## Public RC raffles

**/ripper admin → New RC Raffle** creates a reviewed draft. Publishing freezes price, per-member ticket cap, deadline, minimum unique eligible members, winner count and the current access role. The public post contains a seed commitment and rules hash.

Members press **Buy Tickets**, enter a quantity, review the private cost and confirm. Registration and RC reservation occur in one transaction. A receipt and the entry remain visible after message failures. More tickets mean proportionally more draw weight. A member wins at most once in each raffle.

At closing the bot freezes purchases and freshly checks each member with Discord. A confirmed departed/bot/missing-role account is excluded and refunded. A timeout, Forbidden response or other uncertain lookup pauses finalization and retries; it never silently removes a candidate.

If minimum unique eligibility is not met, all reservations are refunded. Otherwise eligible reservations are consumed. Earned RC and leaderboard scores do not fall when tickets are spent. Buying RC raffle tickets does not itself earn participation RC.

Results are saved before the original public post is updated. Failure to update the message never redraws or recharges. **My Entry** shows receipts. Winners press **Claim Prize**; moderators record delivery or forfeiture with **/ripper raffle_manage**. Replacement draws use the original eligible weights, exclude every previous winner and charge no new RC.

Download **Verify Draw** and run:

```bash
python scripts/rzctl.py verify-proof raffle-1-proof.json
```

Verification checks commitments, frozen rule hash, initial eligibility pool, requested winner counts, round hashes, deterministic HMAC selection and unchanged replacement weights. It does not independently verify the truth of Discord eligibility observations or prevent a dishonest operator with database access.

## Accounting and roles

Available RC is spendable. Reserved RC belongs to pending ticket purchases. Earned RC is the valid contribution score and the ranking/role metric. All financial effects are append-only ledger rows with stable identities.

**/ripper correction** records a reasoned account correction. **/ripper revoke_reward** reverses one invalid original reward and removes its task/event metric, without deleting the original record. Revoking a daily reward does not create another free spin. Negative corrected balances block purchases until covered by future earnings.

Task count is the number of rewarded task cycles, not posts. Event count is distinct paid Rumble and ordinary-raffle events. A revoked base contribution no longer counts. All enabled metrics in a tier must be met. Only the highest eligible achievement role is retained; the new role is added before old tiers are removed.

Gate's Ripper, OG, staff, claim roles and Raffle's temporary roles are protected through role validation and shared coordination protocol 2. Zone only claims its own messages and achievement roles. It never resets the shared registry or another controller's lease.

## Upgrade and inspect

```bash
cd ~/Ripper-Zone
git pull --ff-only
sudo bash scripts/install.sh
sudo systemctl status ripper-zone.service ripper-zone-recovery.service --no-pager
sudo journalctl -u ripper-zone.service -n 80 --no-pager
curl -fsS http://127.0.0.1:3040/health
```

If health ports conflict, change HEALTH_PORT and RECOVERY_PORT in **/etc/ripper-zone.env** before installation. Neither endpoint is exposed on a public interface.

Full operations, credential correction, backups and rollback: [docs/OPERATIONS.md](docs/OPERATIONS.md).
Command reference: [docs/ADMIN.md](docs/ADMIN.md).
Architecture and decisions: [docs/PRODUCT.md](docs/PRODUCT.md).
Test scope and verification limits: [docs/VALIDATION.md](docs/VALIDATION.md).

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
.venv/bin/python -m pytest -q
cp .env.example .env
# Edit .env locally. Local DATABASE_PATH and COORDINATION_DB may be relative paths.
.venv/bin/python main.py
```

The managed VPS installer uses the fixed private database/shared registry paths in the example. Direct local development supports other paths.
