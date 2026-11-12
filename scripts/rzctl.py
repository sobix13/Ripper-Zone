#!/usr/bin/env python3
"""Local maintenance. Recovery never rewrites balances or restores old ledgers."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from ripper_zone.storage import Database
from ripper_zone.drawing import verify


async def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('backup');a.add_argument('target')
    a=sub.add_parser('verify-proof');a.add_argument('file')
    a=sub.add_parser('doctor')
    a=sub.add_parser('clear-fatal')
    a=sub.add_parser('bind-recovery');a.add_argument('message',type=int)
    a=sub.add_parser('review-missing-panel')
    a=p.parse_args()
    if a.action=='verify-proof':
        if not verify(json.loads(Path(a.file).read_text())):raise SystemExit("Proof verification FAILED")
        print("Proof selection and hashes verified. Live Discord eligibility is separately audited.");return
    load_dotenv(os.environ.get('ENV_FILE','/etc/ripper-zone.env'))
    db=Database(os.environ.get('DATABASE_PATH','/var/lib/ripper-zone/ripper-zone.sqlite3'))
    guild=int(os.environ['DISCORD_GUILD_ID'])
    if a.action=='backup':
        if not Path(db.path).is_file():raise ValueError("Database does not exist.")
        await db.backup(a.target);print("Verified SQLite backup created.")
    elif a.action=='doctor':
        print(json.dumps({'integrity':await db.query('PRAGMA quick_check'),'ledger_mismatches':await db.reconcile(guild),
                          'blocks':await db.query('SELECT * FROM financial_blocks'),'failed_jobs':await db.query("SELECT key,error FROM jobs WHERE state='failed'")},indent=2))
    elif a.action=='clear-fatal':
        Path(str(db.path)+'.fatal').unlink(missing_ok=True);print("Credential/intents failure marker cleared. Restart only after correcting the cause.")
    elif a.action=='bind-recovery':
        if os.geteuid()!=0:raise ValueError("Run as root.")
        from ripper_zone.operations import RestartBudget
        budget=RestartBudget(Path(db.path).parent/'recovery/state.json')
        budget.data.update(message=a.message,message_state='active');budget.save();print("Recovery message binding saved.")
    elif a.action=='review-missing-panel':
        answer=input("Type VERIFIED MISSING after manually checking the configured channel for an uncertain panel send: ")
        if answer!='VERIFIED MISSING':raise ValueError("Review was not confirmed.")
        cfg,rev=await db.config(guild);cfg.update(panel_message=0,panel_state='missing');await db.save_config(guild,cfg,rev,0)
        await db.audit(guild,0,'operator_review','Uncertain panel verified missing')
        print("Panel is now eligible for explicit republication.")

if __name__=='__main__':asyncio.run(main())
