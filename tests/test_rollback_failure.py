"""Failure paths use an isolated host; never invoke host systemd."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

@pytest.mark.parametrize('failure',['preflight','switch'])
def test_failed_rollback_restores_current_code_and_services(tmp_path,failure):
    root=Path(__file__).resolve().parents[1];base=tmp_path/'opt/ripper-zone';units=tmp_path/'etc/systemd/system';units.mkdir(parents=True)
    current=base/'releases/current';previous=base/'releases/previous'
    bin_=tmp_path/'bin';bin_.mkdir();log=tmp_path/'calls.jsonl'
    shim=bin_/'shim'
    shim.write_text('#!'+sys.executable+'\n'+'''import json,os,pathlib,sys
args=sys.argv[1:];name=pathlib.Path(sys.argv[0]).name
with open(os.environ['CALL_LOG'],'a') as f:f.write(json.dumps([name,*args])+'\\n')
if name=='systemctl':sys.exit(0)
if args and args[0].endswith('rzctl.py'):
 pathlib.Path(args[2]).write_text('isolated backup fixture');sys.exit(0)
if args and args[0].endswith('preflight.py'):sys.exit(7 if os.environ['FAIL_STAGE']=='preflight' else 0)
if args and args[0].endswith('release.py'):sys.exit(8)
sys.exit(9)
''');shim.chmod(0o755);(bin_/'systemctl').symlink_to(shim)
    for release in (current,previous):
        (release/'.venv/bin').mkdir(parents=True);(release/'.venv/bin/python').symlink_to(shim)
        (release/'systemd').mkdir()
        for name in ('ripper-zone.service','ripper-zone-recovery.service'):(release/'systemd'/name).write_text('fixture unit')
        (release/'RELEASE-MANIFEST.json').write_text('{}')
    (base/'current').symlink_to(current);(base/'previous').symlink_to(previous)
    data=tmp_path/'var/lib/ripper-zone/backups';data.mkdir(parents=True)
    text=(root/'scripts/rollback.sh').read_text().replace('[[ $EUID == 0 ]]','[[ 1 == 1 ]]').replace('/opt/ripper-zone',str(base)).replace('/var/lib/ripper-zone',str(data.parent)).replace('/etc/systemd/system',str(units))
    script=tmp_path/'rollback.sh';script.write_text(text)
    result=subprocess.run(['bash',str(script)],env={**os.environ,'PATH':str(bin_)+':'+os.environ['PATH'],'CALL_LOG':str(log),'FAIL_STAGE':failure},capture_output=True,text=True,timeout=15)
    assert result.returncode!=0
    assert (base/'current').resolve()==current
    calls=[json.loads(x) for x in log.read_text().splitlines()]
    assert ['systemctl','start','ripper-zone.service'] in calls
    assert ['systemctl','start','ripper-zone-recovery.service'] in calls
    if failure=='preflight':assert not any(x[:2]==['systemctl','stop'] for x in calls)
    assert not any('gate.service' in ' '.join(x) or 'crew.service' in ' '.join(x) for x in calls)
