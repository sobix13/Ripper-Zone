# Panel administration · 1.1.0

Open `/ripper admin`, or Administration from your member home when authorized. Routine tasks do not require command names or numeric member IDs.

| Section | Actions |
| --- | --- |
| Community Tasks | New, active/past/review lists, details, participant accounts, edit title/body/reward/cooldown, human-readable UTC deadline, duplicate, close/archive, cycle snapshot, reviewed base/quality contribution, reset cooldown, reaction recovery, brief refresh and binding recovery |
| RC and Members | Native member selector, account/history, award preview, signed correction and invalid reward reversal |
| Snapshots | Rumble/ordinary raffle finalized events, task cycle, channel/thread window, message reactions |
| RC Raffles | Draft create/edit, publish preview, close/retry, cancel/refund, proof, prize delivery/forfeit and replacement |
| Settings | Channels/access, message movement, reactions, 25 editable copy fields, three-role wizard, program toggles, export/import/history and restore |
| Reports | Leaderboard, ledger, tasks, raffles and audit CSV |
| Health / Recovery | Readiness, accounting, failed-job details, pending publications, source connection checks, JSON detail, retry, verified resume, backup now and bounded restart |
| Guides | Contextual member and moderator instructions |

Primary administrators: server owner, OWNER_IDS and configured primary users. Moderators: configured manager roles. Primary access is required for settings, access, correction/revoke and recovery. Fresh permissions are checked on submitted operations. Discord Administrator alone does not grant Zone's configured moderator authority.

## Copy editing

Settings → Messages and Branding lists five core fields (panel title, welcome, About, support and task footer), plus twenty bounded message templates. Select, edit, preview and confirm. Supported placeholders are shown beside the field. Attribute/index expressions, conversions, format specifiers and unknown names are rejected. Dynamic financial facts remain visible independently of custom copy.

Reopen private pages after saving. Relevant existing public posts are queued for refresh; no blind duplicate publication is used. Changes to copy do not change published raffle financial contracts. The message catalog and public synchronization are tested separately from cosmetic rendering in a real Discord client.

## Settings and message moves

Channels and Access edits one field at a time. A channel containing a bound public panel/leaderboard cannot be changed by an ordinary settings save, import or history restore. Use **Move Public Message**. The new send is durably marked, bound, and the old post becomes a link. An uncertain send remains in recovery; it is not retried as a new send. Bind an observed message from Health if a response was lost.

History retains thirty snapshots. Base fields and extended presentation fields are stored separately for compatibility with 1.0.1. Reverting code preserves financial data. Older code does not understand the new presentation jobs; re-upgrade to resume those workflows and retry failed jobs. Do not restore an older ledger to fix a display failure.

## Participation rules

Task base awards share task/cycle/member identity across reactions, manual review and cycle snapshots. Quality bonuses are extra operations. Removing a reaction does not reverse RC. Revoke a specific invalid reward with a reason. That also removes its relevant achievement metric.

Recorded task messages represent presence, not a content approval queue. Cycle snapshot confirmation approves the batch. General window/reaction snapshots are new manual award operations. Their confirmation is repeat-safe, but starting a new snapshot intentionally creates a new award. Finalized event snapshots have stronger event-level deduplication.

Ordinary raffle participation uses its initial eligible pool, including losing entrants. Accounts excluded by that source raffle are not included. Rumble uses its complete finalized ranking. These are explicit source rules; a chat/reaction scan is not a substitute for a finalized game roster.

## Source connection

Health → Check Rumble Connection / Check Raffle Connection lists the latest 25 completed events. Defaults match the existing deployment layouts. For a custom path, a VPS owner sets RUMBLE_DATABASE_PATH or RAFFLE_DATABASE_PATH in the private Zone environment and restarts the recovery helper. No source bot's credentials, database ownership or service are changed.

The advanced `/ripper snapshot` attachment import and `scripts/export_event.py` remain available for manual transfers. They are not required by the normal event picker. JSON checksums detect corruption; they do not authenticate a manually fabricated file. Snapshot access is a financial moderator permission.

## Recovery boundaries

Health displays failed job keys/errors and publication review IDs. Retry repeats effects with their original financial identities. An accounting pause clears only after reconciliation succeeds. Backup Now writes a private verified SQLite copy on the VPS, never uploads the ledger to Discord. Restart uses the helper's fixed target and persisted budget. Independent pulse reactions accept environment OWNER_IDS only.

If a task brief send is uncertain, inspect the thread and use Recover Brief Binding with its existing message ID. If the thread itself was never bound, select the task under Publication Review and use Bind Thread. Message/thread IDs are needed for exceptional binding recovery, not routine task creation or participant selection.
