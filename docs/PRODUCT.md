# Product and implementation decisions

## Identity and scope

Name: Ripper Zone. Unit: Ripper Credit. Plural: Ripper Credits. Display: RC.

This version serves the Rip Cars community, including members who do not buy packs or use a wallet. It has one point account across community tasks, event participation, manual rewards and daily check-in. It starts with new balances. Melee data, quiz, content forms and peer review are not migrated.

## Architecture

| Module | Responsibility |
| --- | --- |
| storage.py | SQLite transactions, private ledger, account projections, settings/history, jobs, snapshots, backup and reconciliation |
| features.py | Versioned daily spin and task cycles/reward identities |
| raffles.py | Draft contract, ticket holds, pool freeze, atomic settlement/refund, prizes and replacement state |
| drawing.py | Committed deterministic weighted HMAC selection and proof verification |
| sources.py | Read-only export adapters for inspected Rumble/Raffle schemas |
| service.py | Fresh Discord eligibility, role validation, queue delivery, thread/raffle publication and maintenance |
| ui.py / member_ui.py / admin_ui.py / guides.py / copy.py | Native public/private controls, member workflows, moderator forms, guides and validated editable copy |
| bot.py | Application lifecycle, command permissions, task message/reaction events and handlers |
| coordination.py / suite_protocol.py | Shared Rip Cars protocol 2 ownership and mirrored setup leases |
| operations.py | Main health server and independent owner-controlled bounded recovery |
| scripts | Private configuration, staged installation, preflight, verified backups, proof verification and rollback |

Every database transaction runs on a short-lived connection in a worker thread, under BEGIN IMMEDIATE and SQLite's cross-process lock. No Discord call occurs inside the transaction. Cancellation waits for the transaction to finish before releasing the async lock. A process lock prevents two full bot instances from using the same private ledger.

Available/reserved/earned account columns are projections of immutable signed ledger deltas. Reconciliation compares projections, outstanding purchase holds and daily claims with their ledger records. A mismatch records a financial pause; it does not alter money records to make them appear consistent. Original rewards are invalidated by explicit reversal entries, not deletion.

Task base identity: guild + task + cycle + member + base. Quality-reaction identity: guild + message + emoji + member. Ordinary event identity: source + guild + event + member + participation. Spin identity: guild + member + UTC date. Purchase confirmation identity is the original submitted request, retained across retries.

The job queue separates external role/log effects from financial commits. Jobs lease for 180 seconds, retry up to eight times with bounded exponential delays, then appear in doctor for review. Failed jobs never rerun an RC award. Log lines may duplicate after a network timeout; balances do not.

## Daily economy

For the approved ten-outcome table:

```text
E[RC] = (2×3300 + 3×2200 + 4×1400 + 5×900 + 6×700
         + 8×500 + 10×400 + 15×300 + 20×250 + 100×50) / 10000 = 5
P(100 RC) = 50 / 10000 = 0.005
```

The long-run expected issuance is 5 × number of successful daily claims. A claim uses secrets.randbelow(10000), not floating-point probability comparisons. The first claim creates a durable result. Later requests return that result. A request first processed before midnight remains bound to its original day when retried afterward.

Opening the panel, refreshing it and background workers do not generate claims. There is no streak bonus or paid spin. The current table is version 1; changing economic odds requires a reviewed version change.

## RC raffle fairness and finality

The seed is generated before publication; only its SHA-256 commitment is shown before closing. The contract hash binds fixed rules and access role. A frozen eligible weighted pool is hashed and combined with contract hash and round index. HMAC-SHA256 rejection sampling avoids modulo bias. Winners are removed from the remaining weighted pool.

At closing all frozen entrants require definite eligibility evidence. Unknown HTTP results stop the entire finalization. Minimum is unique eligible members, not ticket quantity. Settlement, result and prize records commit together, before any public result edit.

A replacement round preserves original eligibility weights for remaining candidates, excludes all prior winners, checks current eligibility and charges no new RC. The proof verifies selection consistency, not external eligibility truth or an operator's integrity. An audit trail records moderator decisions.

## Roles and branding

Exactly three optional community roles use all configured metrics. Only the highest eligible tier is retained. Spending changes available RC but not earned RC. A revoked contribution changes earned RC and removes its contribution metric. Tier removal follows successful target addition.

The approved artwork is reused byte-for-byte from the inspected Rumble repository. assets/manifest.json records source paths and SHA-256 hashes. Panels use a burgundy accent, compact thumbnail, clear numbers and native Discord button styles. A single jackpot GIF is used only for a 100 RC result. No new artwork or external image host is needed.

## Deployment ownership

Private service/data: ripperzone, /var/lib/ripper-zone. Releases: /opt/ripper-zone/releases. Root-owned current/previous symlinks. Private configuration: /etc/ripper-zone.env. Shared registry: /var/lib/ripcars-bots/coordination.sqlite3.

The shared registry contains ownership and setup leases only. Financial data stays private. Zone records its own message/achievement-role keys, refuses foreign/manual bindings and mirrors the same protocol 2 lock tables as Gate/Crew/Raffle. It does not start, stop, rewrite or upgrade those services.

## Deliberate boundaries

Event integration uses an authenticated localhost endpoint in the existing independent helper. It reads finalized source data through fixed, root-configured read-only adapters. The Zone service account receives no access to source databases and no source service is changed. Export/import remains an advanced fallback. Channels and achievement roles are selected from existing server resources. The bot checks their permissions and ownership; it does not redesign the server or change Gate/Crew resources.

There is no offsite backup target configured, no payment integration, no cash redemption and no automatic repair of a corrupt ledger. These are not represented as completed features.
