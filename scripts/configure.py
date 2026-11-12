#!/usr/bin/env python3
"""Interactive root-only configuration; token never appears in arguments/logs."""
import getpass
import os
import secrets
import sys
from pathlib import Path

def main():
    if os.geteuid()!=0:raise SystemExit("Run with sudo.")
    path=Path('/etc/ripper-zone.env')
    if path.exists():raise SystemExit("Existing configuration preserved. Edit it with sudoedit /etc/ripper-zone.env.")
    if not sys.stdin.isatty():raise SystemExit("Run installation in an interactive terminal to enter the private bot token.")
    while True:
        token=getpass.getpass('New Ripper Zone bot token (hidden): ').strip()
        if len(token)>=30 and not any(x.isspace() for x in token):break
        print('Token is incomplete. Enter it again.')
    while True:
        guild=input('Discord server ID [1560350027631562923]: ').strip() or '1560350027631562923'
        if guild.isdecimal() and 0<int(guild)<2**63:break
        print('Enter a valid numeric Discord server ID.')
    while True:
        owners=input('Your Discord user ID(s), comma-separated (required): ').strip()
        if owners and all(x.strip().isdecimal() and 0<int(x.strip())<2**63 for x in owners.split(',')):break
        print('At least one Discord user ID is required. Right-click your profile and Copy User ID.')
    data=dict(DISCORD_TOKEN=token,DISCORD_GUILD_ID=guild,OWNER_IDS=owners.replace(' ',''),DATABASE_PATH='/var/lib/ripper-zone/ripper-zone.sqlite3',
              COORDINATION_DB='/var/lib/ripcars-bots/coordination.sqlite3',HEALTH_SECRET=secrets.token_urlsafe(48),HEALTH_PORT='3040',RECOVERY_PORT='3041',RECOVERY_CHANNEL_ID='0')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        for k,v in data.items():f.write(k+'='+v+'\n')
    print("Private environment file created.")

if __name__=='__main__':main()
