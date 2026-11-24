"""Real SQLite and mount-namespace checks for the read-only recovery reader."""
import asyncio
import logging
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from ripper_zone.storage import Database


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_reads_idle_database_on_readonly_mount(tmp_path):
    if not shutil.which('unshare') or not shutil.which('mount'):
        pytest.skip('Linux mount/user namespace tools are unavailable')
    namespace = ['unshare', '--user', '--map-root-user', '--mount',
                 '--propagation', 'private']
    probe = subprocess.run([*namespace, 'true'], capture_output=True, text=True)
    if probe.returncode:
        pytest.skip('This host disables unprivileged mount/user namespaces')
    script = r'''
import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from ripper_zone.operations import Recovery
from ripper_zone.storage import Database

folder = Path(sys.argv[1]) / 'private-ledger'
folder.mkdir(mode=0o700)
path = folder / 'ripper-zone.sqlite3'

async def prepare():
    db = Database(path)
    await db.open()
    cfg, revision = await db.config(1)
    cfg.update(audit_channel=44, log_channel=55)
    await db.save_config(1, cfg, revision, 2)

asyncio.run(prepare())
os.environ.update(DATABASE_PATH=str(path), DISCORD_GUILD_ID='1',
                  HEALTH_SECRET='test-only-secret-' * 3, OWNER_IDS='2')
subprocess.run(['mount', '--bind', str(folder), str(folder)], check=True)
try:
    subprocess.run(['mount', '-o', 'remount,bind,ro', str(folder)], check=True)
    assert Recovery().config()['audit_channel'] == 44
    assert Recovery().config()['log_channel'] == 55
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        assert connection.execute('PRAGMA quick_check').fetchone() == ('ok',)
    finally:
        connection.close()
    print('read-only recovery and integrity check: OK')
finally:
    subprocess.run(['umount', str(folder)], check=True)
'''
    result = subprocess.run(
        [*namespace, sys.executable, '-c', script, str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'read-only recovery and integrity check: OK' in result.stdout


async def test_short_connections_keep_wal_available_and_checkpoint_growth(tmp_path):
    path = tmp_path / 'zone.sqlite3'
    db = Database(path)
    await db.open()
    await db.execute('CREATE TABLE wal_probe(id INTEGER PRIMARY KEY, value TEXT)')
    await db.execute('INSERT INTO wal_probe VALUES(1, ?)', ('x' * 5000,))
    for index in range(200):
        await db.execute('UPDATE wal_probe SET value=? WHERE id=1',
                         (f'{index}:' + 'x' * 5000,))
    wal = Path(str(path) + '-wal')
    assert wal.is_file()
    assert Path(str(path) + '-shm').is_file()
    # Without an explicit checkpoint, retained WAL grows past this limit.
    assert wal.stat().st_size < 1024 * 1024
    reader = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        assert reader.execute('SELECT value FROM wal_probe').fetchone()[0].startswith('199:')
        assert reader.execute('PRAGMA quick_check').fetchone() == ('ok',)
    finally:
        reader.close()


async def test_checkpoint_failure_does_not_fail_or_repeat_committed_reward(db, monkeypatch, caplog):
    connect = sqlite3.connect

    class CheckpointFailure(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == 'PRAGMA wal_checkpoint(PASSIVE)':
                raise sqlite3.OperationalError('simulated checkpoint I/O failure')
            return super().execute(sql, *args, **kwargs)

    def fail_checkpoint(*args, **kwargs):
        return connect(*args, **kwargs, factory=CheckpointFailure)

    with monkeypatch.context() as patch, caplog.at_level(logging.ERROR):
        patch.setattr(sqlite3, 'connect', fail_checkpoint)
        paid = await db.award(1, {3: 'Alice'}, 10, 2, 'Test reward', 'checkpoint-test')
    assert paid == 1
    assert 'SQLite WAL checkpoint failed' in caplog.text
    assert (await db.account(1, 3))['available'] == 10
    assert await db.award(1, {3: 'Alice'}, 10, 2, 'Test reward', 'checkpoint-test') == 0
    assert (await db.account(1, 3))['available'] == 10
    assert not await db.reconcile(1)


async def test_readonly_snapshot_does_not_block_award_checkpoint(db):
    await db.account(1, 3, 'Alice')
    reader = sqlite3.connect(Path(db.path).as_uri() + '?mode=ro', uri=True)
    try:
        reader.execute('BEGIN')
        assert reader.execute('SELECT available FROM accounts WHERE user=3').fetchone() == (0,)
        assert await asyncio.wait_for(
            db.award(1, {3: 'Alice'}, 10, 2, 'Test reward', 'reader-test'), 5
        ) == 1
        assert reader.execute('SELECT available FROM accounts WHERE user=3').fetchone() == (0,)
    finally:
        reader.close()
    assert (await db.account(1, 3))['available'] == 10
    assert not await db.reconcile(1)
