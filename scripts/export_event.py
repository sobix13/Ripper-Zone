#!/usr/bin/env python3
"""Run as the source bot's service user. Never grant Zone access to its DB."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ripper_zone.sources import export

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',choices=['rumble','raffle'])
p.add_argument('database')
p.add_argument('guild',type=int)
p.add_argument('event',type=int)
if __name__=='__main__':
    a=p.parse_args()
    print(json.dumps(export(a.database,a.source,a.guild,a.event),indent=2))
