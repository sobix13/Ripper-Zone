#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo "Run with sudo."; exit 1; }
BASE=/opt/ripper-zone
exec 9>"$BASE/install.lock"
flock -n 9 || { echo "Another installer is running."; exit 1; }
PREVIOUS="$(readlink -f "$BASE/previous")"
[[ "$PREVIOUS" == "$BASE/releases/"* && -f "$PREVIOUS/RELEASE-MANIFEST.json" ]] || { echo "No verified previous release."; exit 1; }
systemctl stop ripper-zone-recovery.service ripper-zone.service
"$PREVIOUS/.venv/bin/python" "$PREVIOUS/scripts/preflight.py" --database /var/lib/ripper-zone/ripper-zone.sqlite3
"$PREVIOUS/.venv/bin/python" "$PREVIOUS/scripts/release.py" switch "$BASE" "$PREVIOUS"
install -m 644 "$PREVIOUS/systemd/ripper-zone.service" /etc/systemd/system/ripper-zone.service
install -m 644 "$PREVIOUS/systemd/ripper-zone-recovery.service" /etc/systemd/system/ripper-zone-recovery.service
systemctl daemon-reload
systemctl reset-failed ripper-zone.service ripper-zone-recovery.service || true
systemctl start ripper-zone.service ripper-zone-recovery.service
echo "Previous code activated. Current RC ledger preserved."
