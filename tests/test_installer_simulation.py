"""Run the installer shell, real staging/SQLite/core tests, simulated host services."""
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_fresh_install_upgrade_and_failed_activation_preserve_ledger(tmp_path):
    spec=importlib.util.spec_from_file_location('release_installer',ROOT/'scripts/release.py')
    release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
    source=tmp_path/'checkout';source.mkdir()
    for path in release.files(ROOT):
        target=source/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
    base=tmp_path/'opt/ripper-zone';data=tmp_path/'var/lib/ripper-zone';etc=tmp_path/'etc'
    etc.mkdir();(etc/'systemd/system').mkdir(parents=True)
    envfile=etc/'ripper-zone.env'
    envfile.write_text(f"DISCORD_TOKEN={'x'*40}\nDISCORD_GUILD_ID=1\nOWNER_IDS=2\nDATABASE_PATH={data}/ripper-zone.sqlite3\nHEALTH_SECRET={'s'*48}\n")
    script=source/'scripts/install.sh'
    script.write_text(script.read_text().replace('[[ $EUID == 0 ]]','[[ 1 == 1 ]]')
                      .replace('/opt/ripper-zone',str(base)).replace('/var/lib/ripper-zone',str(data))
                      .replace('/var/lib/ripcars-bots',str(tmp_path/'var/lib/ripcars-bots'))
                      .replace('/etc/ripper-zone.env',str(envfile)).replace('/etc/systemd/system',str(etc/'systemd/system')))
    bin_=tmp_path/'bin';bin_.mkdir()
    shim=bin_/'host-shim'
    shim.write_text("""#!"""+sys.executable+"""
import json,os,pathlib,subprocess,sys
name=pathlib.Path(sys.argv[0]).name;args=sys.argv[1:]
with open(os.environ['SIM_LOG'],'a') as f:f.write(json.dumps([name,*args])+'\\n')
if name in ('chown','usermod','useradd','groupadd','getent','id'):sys.exit(0)
if name=='systemctl':
 if args[0]=='is-active':sys.exit(0 if pathlib.Path(os.environ['SIM_BASE'],'current').exists() else 3)
 if args[0]=='enable' and os.getenv('SIM_FAIL')=='1':sys.exit(1)
 sys.exit(0)
if name=='curl':print('{"ok":true}');sys.exit(0)
if name=='install':
 cleaned=[];i=0
 while i<len(args):
  if args[i] in ('-o','-g'):i+=2
  else:cleaned.append(args[i]);i+=1
 os.execv('/usr/bin/install',['install',*cleaned])
if name=='pip':sys.exit(0)
if args[:2]==['-m','venv']:
 dest=pathlib.Path(args[2]);(dest/'bin').mkdir(parents=True)
 for n in ('python','pip'):(dest/'bin'/n).symlink_to(pathlib.Path(sys.argv[0]).resolve().parent/n)
 sys.exit(0)
if args[:2]==['-m','pytest']:
 args=['-m','pytest','-q','tests/test_spin_ledger.py','tests/test_tasks_raffles.py']
elif args and args[0].endswith('preflight.py') and '--database' not in args:
 print('Environment preflight simulated');sys.exit(0)
elif args and args[0].endswith('rzctl.py'):
 import asyncio,importlib.util
 target=pathlib.Path(args[0]).resolve()
 assert target.is_relative_to(pathlib.Path(os.environ['SIM_BASE'])/'releases')
 spec=importlib.util.spec_from_file_location('simulated_rzctl',target)
 ctl=importlib.util.module_from_spec(spec);spec.loader.exec_module(ctl)
 def simulate_service_user():
  with open(os.environ['SIM_LOG'],'a') as f:
   print(json.dumps(['service-user-simulated',os.geteuid(),os.getegid()]),file=f)
 # Host accounts are simulated just like chown/useradd; real backups still run.
 ctl.drop_service_user=simulate_service_user
 sys.argv=[args[0],*args[1:]]
 asyncio.run(ctl.main());sys.exit(0)
os.execv(os.environ['SIM_PYTHON'],[os.environ['SIM_PYTHON'],*args])
""")
    shim.chmod(0o755)
    for name in ('python3','python','pip','systemctl','curl','chown','usermod','useradd','groupadd','getent','id','install'):(bin_/name).symlink_to(shim.name)
    env={**os.environ,'PATH':str(bin_)+':'+os.environ['PATH'],'SIM_LOG':str(tmp_path/'host.jsonl'),
         'SIM_BASE':str(base),'SIM_PYTHON':sys.executable,'DATABASE_PATH':str(data/'ripper-zone.sqlite3'),'DISCORD_GUILD_ID':'1'}
    def run(version,fail=False):
        (source/'VERSION').write_text(version+'\n')
        return subprocess.run(['bash',str(script)],cwd=source,env={**env,'SIM_FAIL':'1' if fail else '0'},text=True,capture_output=True,timeout=60)
    first=run('1.0.0')
    assert first.returncode==0,first.stdout+first.stderr
    original=(base/'current').resolve()
    assert (original/'.venv').stat().st_mode&0o055==0o055
    assert (original/'.venv/bin').stat().st_mode&0o055==0o055
    assert (original/'ripper_zone').stat().st_mode&0o055==0o055
    # A real private ledger is created between deployments.
    sys.path.insert(0,str(ROOT))
    from ripper_zone.storage import SCHEMA
    with sqlite3.connect(data/'ripper-zone.sqlite3') as c:
        c.executescript(SCHEMA);c.execute('INSERT INTO meta VALUES(1)')
        c.execute("INSERT INTO accounts VALUES(1,3,'Alice',25,0,25)")
        c.execute("INSERT INTO ledger(guild,user,da,dr,de,source,kind,ref,reason,actor,key,at) VALUES(1,3,25,0,25,'manual','award','op','earned',2,'manual:1:op:3:award',1)")
    second=run('1.0.1')
    assert second.returncode==0,second.stdout+second.stderr
    current=(base/'current').resolve()
    assert current!=original and (base/'previous').resolve()==original
    assert list((data/'backups').glob('pre-*.sqlite3'))
    failed=run('1.0.2',True)
    assert failed.returncode!=0 and 'Previous code restored' in failed.stdout,failed.stdout+failed.stderr
    assert (base/'current').resolve()==current
    with sqlite3.connect(data/'ripper-zone.sqlite3') as c:assert c.execute('SELECT available,earned FROM accounts').fetchone()==(25,25)
    calls=[json.loads(line) for line in (tmp_path/'host.jsonl').read_text().splitlines()]
    identities=[x for x in calls if x[0]=='service-user-simulated']
    assert identities and all(x[1:]==[os.geteuid(),os.getegid()] for x in identities)
    assert (source/'scripts/rzctl.py').read_bytes()==(ROOT/'scripts/rzctl.py').read_bytes()
    assert any(x[0]=='python' and x[1:3]==['-m','pytest'] for x in calls)
    assert not any(x[0]=='systemctl' and any('gate.service' in part or 'crew.service' in part or 'rumble.service' in part for part in x) for x in calls)
