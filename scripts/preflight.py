#!/usr/bin/env python3
"""No Discord writes. Check environment, SQLite schema, consistency and free space."""
import argparse
import asyncio
import os
import shutil
import socket
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from ripper_zone.config import ident
from ripper_zone.storage import Database


async def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database');p.add_argument('--ports',action='store_true');a=p.parse_args()
    if a.database:
        db=Database(a.database);await db.open()
        rows=await db.query("PRAGMA quick_check")
        if list(rows[0].values())!=['ok']:raise ValueError("Database integrity failed.")
        guilds=await db.query("SELECT guild FROM settings")
        for row in guilds:
            if await db.reconcile(row['guild']):raise ValueError("RC records differ. Operator review required.")
        print("SQLite schema and ledger consistency: OK");return
    load_dotenv(os.environ.get('ENV_FILE','/etc/ripper-zone.env'))
    if len(os.environ.get('DISCORD_TOKEN',''))<30:raise ValueError("Missing bot token.")
    ident(os.environ.get('DISCORD_GUILD_ID',''))
    owners=os.environ.get('OWNER_IDS','')
    if not owners:raise ValueError("At least one OWNER_IDS entry is required for independent recovery.")
    for uid in owners.split(','):ident(uid.strip())
    if len(os.environ.get('HEALTH_SECRET',''))<32:raise ValueError("HEALTH_SECRET is too short.")
    path=Path(os.environ.get('DATABASE_PATH','/var/lib/ripper-zone/ripper-zone.sqlite3'))
    if path!=Path('/var/lib/ripper-zone/ripper-zone.sqlite3'):
        raise ValueError("The managed installer requires the default private database path.")
    if os.environ.get('COORDINATION_DB')!='/var/lib/ripcars-bots/coordination.sqlite3':
        raise ValueError("The managed installer requires the shared Rip Cars coordination path.")
    if shutil.disk_usage(path.parent).free<250_000_000:raise ValueError("At least 250 MB free disk is required.")
    if a.ports:
        for key,default in (('HEALTH_PORT','3040'),('RECOVERY_PORT','3041')):
            port=int(os.environ.get(key,default))
            with socket.socket() as s:s.bind(('127.0.0.1',port))
    print("Environment and local resources: OK")

if __name__=='__main__':asyncio.run(main())
