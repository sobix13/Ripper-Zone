# Validation record · 1.1.3

Date: 2026-11-13. Python 3.12. Dependencies installed into an isolated venv from requirements-lock.txt. No new runtime dependency was added.

The suite contains 198 cases. Local ordinary-user and UID-0 namespace runs passed all 198 tests. It retains the original accounting, secure spin distribution, multi-connection/multi-process, process death, cancellation, fixed-contract draw, refund, role safety, registry and installer tests. Tests exercise native admin/member screens through the installed SDK HTTP serializer, owner isolation, first/repeated leaderboard publication, equal ranks and pagination, message preview/save, stale revisions, template validation, task edits and financial locks, long brief synchronization, uncertain sends, concurrent task publication, durable reaction retries, native member awards, three-role configuration, draft publication, member prize navigation, public message movement, authenticated read-only event access, no-file event selection, correction from a native account screen, window snapshots and nested release secret rejection.

Spin presentation tests serialize real SDK edit payloads with replacement attachments, verify that the claim is committed before the first media edit, and exercise same-message animation/result delivery, disabled buttons, owner isolation, saved-claim reopening, concurrent clicks, cancellation/client recreation, media failure fallback, current access controls and UTC-midnight rollover. The approved static PNG and four-second one-shot GIF are bundled release assets. Offline checks verified 480 x 270 dimensions, 40 frames, 4000 ms including a final 880 ms hold, stationary frame/typography and decreasing angular speed. Real iOS/Android/Desktop autoplay, GIF restart and perceived timing have not been exercised here.

Settings and history compatibility tests verify that the legacy settings JSON retains only the keys accepted by 1.0.1 while extended copy survives older-row changes. Isolated rollback-shell tests inject failures both before stopping services and during release switching; they never execute host systemd. The installer simulation still uses real SQLite backup/staging/financial tests and simulated host effects. Production privilege dropping remains enabled.

## Required final commands

```bash
.venv/bin/python -m pytest -q
unshare -Ur .venv/bin/python -m pytest -q
bash -n scripts/install.sh scripts/rollback.sh
.venv/bin/python -m compileall -q ripper_zone scripts main.py
.venv/bin/pip check
.venv/bin/python scripts/build_release.py /tmp/ripper-zone-1.1.3.zip
```

GitHub Actions runs the complete suite as the ordinary Ubuntu runner and with sudo, then shell syntax and compilation. The final publication summary records the actual observed result and commit.

## What these results do not prove

Discord gateway, API effects, permissions and visual layout are simulated. Real SDK objects and HTTP payload generation are used, but this environment has no production token. Local helper event tests read isolated fixtures that follow the inspected source schemas, not the production databases. Successful SQL/serialization tests do not prove every live Discord client layout or server permission combination.

No production VPS was accessed. No existing source bot was modified. Complete the acceptance checklist after upgrading, especially source paths, actual final rosters including losing participants, private-log access, role hierarchy, public message recovery, recovery service execution, verified backups and mobile rendering. Offsite backup is unconfigured.

Receipt identity tests cover cached members, REST membership and user lookup, saved-name and ID fallbacks, safe link-label escaping, pending legacy notices, transient lookup failures and preservation of ledger balances. Visible receipt names link to profiles without relying on raw mention rendering or enabling notifications. Live Discord client rendering remains part of acceptance.
