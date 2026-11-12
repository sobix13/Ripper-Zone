#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID == 0 ]] || { echo "Run with sudo."; exit 1; }
BASE=/opt/ripper-zone
exec 9>"$BASE/install.lock"
flock -n 9 || { echo "Another installer is running."; exit 1; }
PREVIOUS="$(readlink -f "$BASE/previous")"
[[ "$PREVIOUS" == "$BASE/releases/"* && -f "$PREVIOUS/RELEASE-MANIFEST.json" ]] || { echo "No verified previous release."; exit 1; }
WAS_MAIN=0
WAS_RECOVERY=0
systemctl is-active --quiet ripper-zone.service && WAS_MAIN=1
systemctl is-active --quiet ripper-zone-recovery.service && WAS_RECOVERY=1
OLD_CURRENT="$(readlink -f "$BASE/current")"
restore_current() {
  status=$?
  trap - ERR
  ln -sfn "$OLD_CURRENT" "$BASE/current.next"
  mv -Tf "$BASE/current.next" "$BASE/current"
  install -m 644 "$OLD_CURRENT/systemd/ripper-zone.service" /etc/systemd/system/ripper-zone.service
  install -m 644 "$OLD_CURRENT/systemd/ripper-zone-recovery.service" /etc/systemd/system/ripper-zone-recovery.service
  systemctl daemon-reload
  [[ $WAS_MAIN == 0 ]] || systemctl start ripper-zone.service || true
  [[ $WAS_RECOVERY == 0 ]] || systemctl start ripper-zone-recovery.service || true
  exit "$status"
}
trap restore_current ERR
CHECK="/var/lib/ripper-zone/backups/rollback-check-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
"$OLD_CURRENT/.venv/bin/python" "$OLD_CURRENT/scripts/rzctl.py" backup "$CHECK"
"$PREVIOUS/.venv/bin/python" "$PREVIOUS/scripts/preflight.py" --database "$CHECK"
rm -f "$CHECK" "$CHECK-wal" "$CHECK-shm"
systemctl stop ripper-zone-recovery.service ripper-zone.service
"$PREVIOUS/.venv/bin/python" "$PREVIOUS/scripts/release.py" switch "$BASE" "$PREVIOUS"
install -m 644 "$PREVIOUS/systemd/ripper-zone.service" /etc/systemd/system/ripper-zone.service
install -m 644 "$PREVIOUS/systemd/ripper-zone-recovery.service" /etc/systemd/system/ripper-zone-recovery.service
systemctl daemon-reload
systemctl reset-failed ripper-zone.service ripper-zone-recovery.service || true
systemctl start ripper-zone.service ripper-zone-recovery.service
echo "Previous code activated. Current RC ledger preserved."
