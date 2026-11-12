# VPS operations

## Files and services

| Path/name | Ownership and purpose |
| --- | --- |
| /opt/ripper-zone/releases/VERSION-STAMP | Root-owned code and physical venv |
| /opt/ripper-zone/current | Active verified release |
| /opt/ripper-zone/previous | Previous code release |
| /etc/ripper-zone.env | root:root 0600, secret environment |
| /var/lib/ripper-zone | ripperzone:ripperzone 0700, private ledger |
| /var/lib/ripper-zone/backups | Verified online SQLite copies, seven daily copies plus pre-upgrade copies |
| /var/lib/ripper-zone/recovery | root:root 0700, helper state and persisted restart budget |
| /var/lib/ripcars-bots | root:ripcars-bots 2770, shared ownership registry only |
| ripper-zone.service | Main Discord gateway, queue, ledger and health server |
| ripper-zone-recovery.service | Independent root helper with one fixed systemctl restart target |

Both unit files use a read-only filesystem policy and restrict writable paths. The helper needs root for restarting the fixed main service. Its code/venv and environment are root-owned, and its writable recovery directory is inaccessible to the bot account. It uses the same bot token through REST; it opens no second gateway session.

## Health and recovery

Main endpoint: 127.0.0.1:3040/health. Detailed /doctor requires the HEALTH_SECRET bearer token. Helper endpoint: 127.0.0.1:3041/health, authenticated. Ports are configurable in the environment and checked before activation.

The helper observes readiness and worker progress. Three consecutive failed probes trigger a checked restart, subject to a persisted maximum of three restarts per 15 minutes and at least 120 seconds between attempts. A failed SQLite quick_check or a credential/intents fatal marker stops automatic restart. systemd separately limits repeated process failures.

After the private log channel is configured, the helper maintains a status post. Only OWNER_IDS reactions are accepted:

| Reaction | Action |
| --- | --- |
| 🩺 | Request the next health refresh |
| 🔄 | Request a restart through the same budget |
| ⏸️ | Toggle automatic recovery pause |

The bot needs Manage Messages in that private channel to clear processed owner reactions. The helper cannot fix missing Discord permissions, hierarchy, invalid credentials, disabled privileged intents, corrupt accounting or source schemas it does not understand. Its error is retained in helper state and the pulse. It does not modify RC records or redraw raffles.

The main worker retries failed roles/log delivery and result edits. A mismatch pauses new financial actions and settlement. Resolve its cause before /ripper recovery clear_accounting_pause. It succeeds only after verification.

## Common commands

```bash
sudo systemctl status ripper-zone.service ripper-zone-recovery.service --no-pager
sudo journalctl -u ripper-zone.service -n 100 --no-pager
sudo journalctl -u ripper-zone-recovery.service -n 100 --no-pager
curl --max-time 5 -fsS http://127.0.0.1:3040/health
sudo /opt/ripper-zone/current/.venv/bin/python /opt/ripper-zone/current/scripts/rzctl.py doctor
```

Use Administration → Health / Recovery or /ripper doctor for the authenticated detailed report without placing a secret in command arguments.

## Token/intents correction

Stop the helper before working on credentials:

```bash
sudo systemctl stop ripper-zone-recovery.service ripper-zone.service
sudoedit /etc/ripper-zone.env
# Correct the token and enable Server Members + Message Content intents in Discord.
sudo /opt/ripper-zone/current/.venv/bin/python /opt/ripper-zone/current/scripts/rzctl.py clear-fatal
sudo systemctl reset-failed ripper-zone.service ripper-zone-recovery.service
sudo systemctl start ripper-zone.service ripper-zone-recovery.service
```

The environment file is loaded by systemd before dropping main-service privileges. Do not make it readable by the service user or other accounts.

## Backup and rollback

```bash
sudo /opt/ripper-zone/current/.venv/bin/python /opt/ripper-zone/current/scripts/rzctl.py backup \
  /var/lib/ripper-zone/backups/manual-$(date -u +%Y%m%dT%H%M%SZ).sqlite3

sudo bash /opt/ripper-zone/current/scripts/rollback.sh
```

Backups use SQLite's online backup API and verify quick_check before atomic replacement. Copying a live .sqlite3 file alone is not a backup of uncheckpointed WAL data. Daily backups are local to the VPS; offsite delivery is unconfigured.

Rollback validates the current live database with the previous code and switches code only. It never restores an older ledger automatically. An operator should stop both services before any deliberate database restore, preserve the current database/WAL/SHM as evidence, verify the selected backup and understand which later awards/purchases would be lost. No automatic restore command hides that decision.

Failed upgrades before activation keep the old release. Failure after switching restores old code and its service units when a previous release exists. The live database is preserved.

## Publication and queue repair

Use Administration → Health / Recovery or /ripper doctor to identify pending publication reviews and failed jobs. Bind actual message/thread IDs using the primary recovery commands in the [admin guide](ADMIN.md).

If the helper's status send timed out, stop the helper and inspect the private log channel. Bind the known message with:

```bash
sudo /opt/ripper-zone/current/.venv/bin/python /opt/ripper-zone/current/scripts/rzctl.py bind-recovery MESSAGE_ID
sudo systemctl start ripper-zone-recovery.service
```

For an uncertain member-panel send confirmed absent by manual channel inspection:

```bash
sudo /opt/ripper-zone/current/.venv/bin/python /opt/ripper-zone/current/scripts/rzctl.py review-missing-panel
```

This requires an explicit typed review and records an audit event. It does not automatically decide that a timed-out message does not exist.

## Live acceptance

The repository was tested without a Discord token or access to the production VPS. Complete these checks after installation:

1. Main and helper services remain active; /health reports ready; /ripper doctor has no permission, ownership or consistency issue.
2. Verified member opens a private panel. A second member cannot operate the first member's screen.
3. One spin credits RC. Repeated clicks and a main-service restart return the same daily result.
4. A test task creates its thread. Member submits a post. Two moderators using ✅ credit its base reward only once. task_snapshot pays zero for that already-paid member.
5. Posting cooldown deletes a second premature post; a moderator bypasses it. Closing/expiry locks and archives the intended thread.
6. Export one actual finalized Rumble and ordinary raffle. Preview recipient counts against their source results. Confirm an eligible losing participant is included. Reimport pays zero.
7. Create a small test RC raffle. Buy tickets, confirm cost, inspect available/reserved balances. Close with the required unique eligible count. Check saved winners, spent/refunded RC and proof.
8. Cancel another test raffle. Confirm a single full refund. Record a forfeiture and replacement without another ticket charge.
9. Skip roles during setup, then enable three test achievement roles. Confirm highest-only assignment, hierarchy refusal and no change to Ripper/OG/staff.
10. Publish/refresh leaderboard. Spending does not reduce score. Export CSV and inspect a reward/correction with actor and reason.
11. Inspect a verified backup. Stop only the main service and observe bounded recovery and the private owner pulse. Test an owner-requested restart and pause/resume.
12. Review the other bot services. Their processes, data and resources should retain their previous state.

Use small reversible test RC amounts and a test prize during acceptance. The simulated suite does not claim these live checks were run.


## 1.1.0 source connection and rollback compatibility

The authenticated recovery endpoint `/events` accepts only source=rumble|raffle and an optional event ID. Source database paths come only from root-controlled environment configuration. Reads use SQLite mode=ro and query_only. No arbitrary Discord-supplied path or SQL is executed. Defaults are documented in README. The helper retains a read-only filesystem and its existing capability limit; no source database permissions are relaxed.

Presentation settings and their history are stored in meta_flags. The legacy settings JSON and financial schema remain readable by 1.0.1. A code rollback preserves RC, reservations, source snapshots and extended settings. Old code cannot process new presentation/reaction jobs; their durable records remain available for a later re-upgrade and retry. Rollback verifies an isolated backup before stopping the current services and restores their previous running state on failure.

This release's automated tests do not connect to the production VPS or Discord. Complete the live acceptance checklist after upgrade, especially permissions, real event roster counts, callback rendering, role hierarchy, recovery service and mobile layout.
