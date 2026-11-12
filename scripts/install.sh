#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID == 0 ]] || { echo "Run with sudo."; exit 1; }
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
BASE=/opt/ripper-zone
DATA=/var/lib/ripper-zone
ENV_FILE=/etc/ripper-zone.env
export ENV_FILE
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ is required"'
command -v flock >/dev/null
install -d -m 755 "$BASE" "$BASE/releases"
exec 9>"$BASE/install.lock"
flock -n 9 || { echo "Another installer is running."; exit 1; }
[[ -f "$ENV_FILE" ]] || "$PYTHON" "$SOURCE/scripts/configure.py"
chown root:root "$ENV_FILE"
chmod 600 "$ENV_FILE"
getent group ripcars-bots >/dev/null || groupadd --system ripcars-bots
id ripperzone >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin ripperzone
usermod -a -G ripcars-bots ripperzone
install -d -o ripperzone -g ripperzone -m 700 "$DATA" "$DATA/backups"
install -d -o root -g root -m 700 "$DATA/recovery"
install -d -o root -g ripcars-bots -m 2770 /var/lib/ripcars-bots
VERSION="$(cat "$SOURCE/VERSION")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE="$BASE/releases/$VERSION-$STAMP"
"$PYTHON" "$SOURCE/scripts/release.py" stage "$SOURCE" "$RELEASE"
"$PYTHON" -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/pip" install --disable-pip-version-check -r "$RELEASE/requirements-lock.txt"
cd "$RELEASE"
"$RELEASE/.venv/bin/python" -m pytest -q "$RELEASE/tests"
ENV_FILE="$ENV_FILE" "$RELEASE/.venv/bin/python" "$RELEASE/scripts/preflight.py"
chown -R root:root "$RELEASE"
chmod -R go-w "$RELEASE"
WAS_MAIN=0
WAS_RECOVERY=0
systemctl is-active --quiet ripper-zone.service && WAS_MAIN=1
systemctl is-active --quiet ripper-zone-recovery.service && WAS_RECOVERY=1
OLD=""
[[ ! -L "$BASE/current" ]] || OLD="$(readlink -f "$BASE/current")"
SWITCHED=0
restore_on_failure() {
  status=$?
  trap - ERR
  if [[ -n "$OLD" ]]; then
    if [[ $SWITCHED == 1 ]]; then
      ln -sfn "$OLD" "$BASE/current.next"
      mv -Tf "$BASE/current.next" "$BASE/current"
      install -m 644 "$OLD/systemd/ripper-zone.service" /etc/systemd/system/ripper-zone.service
      install -m 644 "$OLD/systemd/ripper-zone-recovery.service" /etc/systemd/system/ripper-zone-recovery.service
    fi
    systemctl daemon-reload
    [[ $WAS_MAIN == 0 ]] || systemctl start ripper-zone.service || true
    [[ $WAS_RECOVERY == 0 ]] || systemctl start ripper-zone-recovery.service || true
    echo "Upgrade failed. Previous code restored; live ledger was not rewound."
  else
    echo "Installation failed before activation. Review the output and retry."
  fi
  exit "$status"
}
trap restore_on_failure ERR
systemctl stop ripper-zone-recovery.service 2>/dev/null || true
systemctl stop ripper-zone.service 2>/dev/null || true
if [[ -f "$DATA/ripper-zone.sqlite3" ]]; then
  "$RELEASE/.venv/bin/python" "$RELEASE/scripts/rzctl.py" backup "$DATA/backups/pre-$STAMP.sqlite3"
fi
# Validate an isolated copy before touching the live schema.
CHECK="$DATA/preflight-$STAMP.sqlite3"
if [[ -f "$DATA/ripper-zone.sqlite3" ]]; then
  "$RELEASE/.venv/bin/python" "$RELEASE/scripts/rzctl.py" backup "$CHECK"
else
  install -o ripperzone -g ripperzone -m 600 /dev/null "$CHECK"
fi
"$RELEASE/.venv/bin/python" "$RELEASE/scripts/preflight.py" --database "$CHECK"
rm -f "$CHECK" "$CHECK-wal" "$CHECK-shm"
ENV_FILE="$ENV_FILE" "$RELEASE/.venv/bin/python" "$RELEASE/scripts/preflight.py" --ports
"$RELEASE/.venv/bin/python" "$RELEASE/scripts/release.py" switch "$BASE" "$RELEASE"
SWITCHED=1
install -m 644 "$RELEASE/systemd/ripper-zone.service" /etc/systemd/system/ripper-zone.service
install -m 644 "$RELEASE/systemd/ripper-zone-recovery.service" /etc/systemd/system/ripper-zone-recovery.service
systemctl daemon-reload
systemctl reset-failed ripper-zone.service ripper-zone-recovery.service || true
systemctl enable --now ripper-zone.service ripper-zone-recovery.service
# Bound readiness wait with continuous user-visible status.
HEALTH_PORT_VALUE="$(ENV_FILE="$ENV_FILE" "$RELEASE/.venv/bin/python" -c 'from dotenv import load_dotenv; import os; load_dotenv(os.environ["ENV_FILE"]); print(int(os.getenv("HEALTH_PORT","3040")))')"
READY=0
for attempt in {1..15}; do
  if curl --max-time 3 -fsS "http://127.0.0.1:$HEALTH_PORT_VALUE/health" >/dev/null; then READY=1; break; fi
  echo "Waiting for Ripper Zone readiness ($attempt/15)..."
  sleep 4
done
[[ $READY == 1 ]] || { echo "Service did not become ready. Check token, invite and privileged intents."; false; }
echo "Ripper Zone $VERSION installed. Run /ripper setup, then /ripper admin."
