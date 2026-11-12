"""Read-only exports from the deployed Rumble 1.2 / Raffle 1.1 schemas."""
import json
import re
import sqlite3
from pathlib import Path
from .config import ident, digest


def validate(data,guild):
    if not isinstance(data,dict) or set(data)!={'version','source','guild','event','participants','hash'} or data['version']!=1:
        raise ValueError("Expected a Ripper Zone event export, version 1.")
    if data['source'] not in ('rumble','raffle') or ident(data['guild'])!=ident(guild):
        raise ValueError("Wrong source or server.")
    ident(data['event'])
    if not isinstance(data['participants'],list) or not 1<=len(data['participants'])<=5000:
        raise ValueError("An event requires 1..5000 participants.")
    ids=[ident(x) for x in data['participants']]
    if ids!=sorted(set(ids)):raise ValueError("Participant IDs must be sorted and unique.")
    if digest({k:v for k,v in data.items() if k!='hash'})!=data['hash']:
        raise ValueError("Export checksum differs. Export the original event again.")
    return data


def export(path,source,guild,event):
    guild,event=ident(guild),ident(event)
    p=Path(path).resolve()
    if not p.is_file():raise ValueError("Source database not found.")
    c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5);c.row_factory=sqlite3.Row
    try:
        c.execute("PRAGMA query_only=ON")
        if source=='rumble':
            row=c.execute("SELECT * FROM game_results WHERE guild_id=? AND game_id=?",(guild,event)).fetchone()
            if not row:raise ValueError("A finalized Rumble result is required.")
            payload=json.loads(row['payload'])
            text=payload.get('ranking_text','')
            lines=text.splitlines()
            if not lines or any(not re.search(r' · ID ([0-9]+)$',line) for line in lines):
                raise ValueError("Rumble ranking is incomplete or uses an unknown format.")
            ids=[ident(re.search(r' · ID ([0-9]+)$',line)[1]) for line in lines]
            game=c.execute("SELECT players,status FROM games WHERE guild_id=? AND id=?",(guild,event)).fetchone()
            expected=game['players'] if game else None
            if not game or game['status']!='finished':raise ValueError("Rumble game is not finalized.")
            if type(expected) is not int or expected!=len(ids) or len(set(ids))!=len(ids):
                raise ValueError("Ranking and player count differ. No partial export was created.")
            if payload.get('winner_id') not in ids:raise ValueError("Rumble winner is missing from ranking.")
        elif source=='raffle':
            row=c.execute("SELECT * FROM raffles WHERE guild=? AND id=?",(guild,event)).fetchone()
            if not row or row['status']!='drawn':raise ValueError("An ordinary raffle must have a completed initial draw.")
            rounds=json.loads(row['rounds']);frozen=set(json.loads(row['frozen']))
            if not rounds or rounds[0]['round']!=0:raise ValueError("Initial eligible pool is unavailable.")
            ids=[ident(p['user']) for p in rounds[0]['pool']]
            if not set(ids)<=frozen or len(ids)!=len(set(ids)):raise ValueError("Invalid initial eligible pool.")
        else:raise ValueError("Choose rumble or raffle.")
    finally:c.close()
    data={'version':1,'source':source,'guild':guild,'event':str(event),'participants':sorted(ids)}
    data['hash']=digest(data)
    return validate(data,guild)


def finalized_events(path,source,guild):
    if source not in ('rumble','raffle'):raise ValueError('Unknown event source.')
    path=Path(path).resolve()
    if not path.is_file():raise ValueError('Event source is not installed at the configured VPS path.')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5) as c:
        c.execute('PRAGMA query_only=ON')
        sql="SELECT id FROM games WHERE guild_id=? AND status='finished' ORDER BY id DESC LIMIT 25" if source=='rumble' else "SELECT id FROM raffles WHERE guild=? AND status='drawn' ORDER BY id DESC LIMIT 25"
        return [{'id':row[0]} for row in c.execute(sql,(ident(guild),))]


def local_event(source,guild,event=None):
    import os
    from dotenv import dotenv_values
    if source not in ('rumble','raffle'):raise ValueError('Choose rumble or raffle.')
    default='/opt/ripcars-rumble/shared/data/rumble.sqlite3' if source=='rumble' else '/var/lib/ripcars-raffle/raffle.sqlite3'
    path=os.getenv(('RUMBLE' if source=='rumble' else 'RAFFLE')+'_DATABASE_PATH',default)
    if source=='raffle' and path==default and Path('/etc/ripcars-raffle.env').is_file():
        path=dotenv_values('/etc/ripcars-raffle.env').get('DB_PATH',default)
    if not Path(path).is_absolute():raise ValueError('Configure an absolute source database path on the VPS.')
    return export(path,source,guild,ident(event)) if event is not None else finalized_events(path,source,guild)
