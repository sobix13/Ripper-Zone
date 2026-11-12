# Validation record

Release: 1.0.1. Date: 2026-11-12. Python: 3.12. Dependencies installed into a fresh isolated venv from the pinned versions.

## Automated coverage

The pytest suite exercises:

| Area | Evidence |
| --- | --- |
| Spin distribution | Exhaustive evaluation of all 10,000 integer rolls, exact outcome counts, expected value and jackpot probability |
| Daily claim | UTC midnight, original request replay across midnight, paused spin, guild separation and immutable reward identity |
| Concurrency | 60 concurrent requests through six SQLite connections; five actual independent Python processes |
| Process interruption | Actual subprocess death before commit and after commit; cancelled coroutine waits for transaction completion |
| Ledger | Stable award/event identities, explicit corrections and reward revocation; mismatch pause; reservation/claim/account consistency |
| Community Tasks | Reactions from two moderators, later snapshot, daily/weekly cycles, quality separation, cooldown and moderator bypass |
| Paid raffles | Concurrent overspending, ticket caps, repeated confirmations, fixed contract, unique-member minimum, refunds, original weighted pool and result replay |
| Prize handling | Claim, delivery, forfeiture, replacement without another charge, original weights and no previous winners |
| Failure behavior | Discord 403/404/timeout classification, unknown eligibility keeps every reservation, failed result edit preserves winners |
| Discord UI | Every member screen serialized through the installed discord.py HTTP payload builder, V2 flags, text/component limits, persistent button identities and owner checks |
| Connected flows | Complete setup wizard with role skip and activation; task form creates a thread and durable brief; actual reaction handler deduplicates awards |
| Permissions/roles | Fresh-role authorization, revoked access at purchase confirmation, unsafe role refusal, highest eligible tier and add-before-remove failure behavior |
| Source integration | Rumble complete ranking + game count; original ordinary-raffle eligible pool including losers; incomplete/unknown source rejection; read-only export |
| Coordination | Mirrored protocol 2 leases; conflicting controller refusal; foreign role preservation |
| Recovery | Real localhost HTTP authentication/readiness, persisted restart budget, pause, corrupt budget refusal and fatal-credentials restart refusal |
| Deployment | Real installer shell in isolated paths, real release staging/venv control flow/core financial tests/SQLite backup and copy checks; simulated systemd/user/package/health calls |
| Upgrade failure | Fresh installation, successful upgrade, failed activation restores previous code and preserves a real 25 RC ledger |
| Packaging | Explicit release allowlist, secret/runtime exclusion, symlink rejection, exact file hashes and atomic current/previous code switch |

The installer simulation does not invoke the host's real systemctl, create host users or change /etc, /opt or /var/lib. It runs against temporary directories with recorded host-command substitutes. Its operator subprocess also simulates the service-user switch, retaining the fixture owner's UID/GID even when pytest runs as root. Actual SQLite backups, isolated-copy checks, release activation and rollback still run. The production privilege-drop function is unchanged and tested separately. Pinned package installation was separately performed in the fresh venv.

Version 1.0.0 let the simulated operator call the host's real service-user switch. A root-run test on an installed VPS then failed while traversing pytest's private root directory, or failed account lookup on a clean root runner. Version 1.0.1 isolates that host-dependent effect inside the test shim. The full suite is configured to run as both the ordinary runner and root in GitHub Actions.

## Commands

```bash
python -m pytest -q
bash -n scripts/install.sh scripts/rollback.sh
python -m compileall -q ripper_zone scripts main.py
python scripts/build_release.py /tmp/ripper-zone-1.0.1.zip
```

The delivery summary reports the final pytest count. Test parametrization represents distinct boundary cases; it is not a count of live Discord events.

## Material limits

No production Discord token was supplied. No login, live Discord interaction, real role/channel permission check, live Gateway reconnect or production Rumble/Raffle event export was performed. The installed discord.py classes and serialization were exercised, while Discord network effects were simulated.

No connection to the production VPS was made. Real systemd execution, the installed server's existing port/resource permissions, OS restart behavior and its actual shared registry require the [live acceptance checklist](OPERATIONS.md#live-acceptance). Unit syntax is checked separately with the executable path adapted to the local environment.

No offsite backup destination is configured. The independent recovery helper diagnoses/contains known failure classes and performs bounded main-service restarts; it does not repair corrupt finances or change another bot.
