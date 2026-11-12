import copy
import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest
from ripper_zone.config import ident,settings,emoji_key
from ripper_zone.sources import export,validate
from ripper_zone.coordination import Registry
from ripper_zone import suite_protocol
from ripper_zone.operations import RestartBudget,atomic_json

ROOT=Path(__file__).resolve().parents[1]
_spec=importlib.util.spec_from_file_location('release',ROOT/'scripts/release.py')
release=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(release)


@pytest.mark.parametrize('value',[0,-1,True,False,None,'1.0','-1','',2**63,1.1,'abc'])
def test_invalid_discord_ids(value):
    with pytest.raises(ValueError):ident(value)


def tiers():
    return [dict(role=10+n,earned=100*n,tasks=n,events=n) for n in (1,2,3)]


@pytest.mark.parametrize('case',['unknown','bool','channels','two','same','zero','decrease','same_metrics','access_collision','staff_collision','enabled_without_tiers','bad_reaction','bad_period'])
def test_configuration_rejects_invalid_boundaries(case):
    cfg=settings();cfg['tiers']=tiers()
    if case=='unknown':cfg['x']=3
    if case=='bool':cfg['active']=1
    if case=='channels':cfg['active']=True
    if case=='two':cfg['tiers'].pop()
    if case=='same':cfg['tiers'][2]['role']=11
    if case=='zero':cfg['tiers'][0].update(earned=0,tasks=0,events=0)
    if case=='decrease':cfg['tiers'][1]['earned']=20
    if case=='same_metrics':cfg['tiers'][1].update(earned=100,tasks=1,events=1)
    if case=='access_collision':cfg['member_role']=11
    if case=='staff_collision':cfg['manager_roles']=[11]
    if case=='enabled_without_tiers':cfg.update(roles_enabled=True,tiers=[])
    if case=='bad_reaction':cfg['reactions']['✅']['amount']=True
    if case=='bad_period':cfg['panel_state']='guess'
    with pytest.raises(ValueError):settings(cfg)


def test_default_configuration_can_skip_roles_and_has_no_removed_features():
    cfg=settings();assert cfg['tiers']==[] and not cfg['roles_enabled']
    assert not {'quiz','reviews','content_panel'}&set(cfg)
    assert settings({**cfg,'tiers':tiers(),'roles_enabled':True})['roles_enabled']
    assert emoji_key('✅️')=='✅'
    assert emoji_key('<:ripper:123>')=='custom:123'


def rumble_db(path):
    c=sqlite3.connect(path)
    c.executescript("CREATE TABLE game_results(game_id INTEGER,guild_id INTEGER,payload TEXT);CREATE TABLE games(id INTEGER,guild_id INTEGER,players INTEGER,status TEXT);")
    payload={'ranking_text':'1. Alice · 2 eliminations · ID 3\n2. Bob · 0 eliminations · ID 4\n3. Carol · 0 eliminations · ID 5','winner_id':3}
    c.execute('INSERT INTO game_results VALUES(10,1,?)',(json.dumps(payload),))
    c.execute("INSERT INTO games VALUES(10,1,3,'finished')");c.commit();c.close()


def test_rumble_export_includes_everyone_and_never_writes_source(tmp_path):
    path=tmp_path/'rumble.db';rumble_db(path);before=path.read_bytes()
    data=export(path,'rumble',1,10)
    assert data['participants']==[3,4,5]
    assert validate(data,1)==data
    assert before==path.read_bytes()
    assert 'seed' not in json.dumps(data)
    with pytest.raises(ValueError):validate(data,2)
    bad=copy.deepcopy(data);bad['participants'].pop()
    with pytest.raises(ValueError):validate(bad,1)


@pytest.mark.parametrize('change',["UPDATE games SET players=4","UPDATE games SET status='interrupted'","UPDATE game_results SET payload='{}'"])
def test_rumble_partial_or_unknown_results_fail_closed(tmp_path,change):
    path=tmp_path/'rumble.db';rumble_db(path)
    with sqlite3.connect(path) as c:c.execute(change)
    with pytest.raises(ValueError):export(path,'rumble',1,10)


def test_ordinary_raffle_exports_original_eligible_losers_not_reroll_pool(tmp_path):
    path=tmp_path/'raffle.db';c=sqlite3.connect(path)
    c.execute('CREATE TABLE raffles(id INTEGER,guild INTEGER,status TEXT,rounds TEXT,frozen TEXT,seed TEXT)')
    rounds=[{'round':0,'pool':[{'user':3,'weight':1},{'user':4,'weight':2},{'user':5,'weight':1}],'winners':[3]},
            {'round':1,'pool':[{'user':4,'weight':2}],'winners':[4]}]
    c.execute("INSERT INTO raffles VALUES(10,1,'drawn',?,?,'secret')",(json.dumps(rounds),json.dumps([3,4,5,6])));c.commit();c.close()
    data=export(path,'raffle',1,10)
    assert data['participants']==[3,4,5] and 'secret' not in json.dumps(data)


async def test_shared_registry_protocol_mirrors_locks_and_guards_foreign_roles(tmp_path):
    path=tmp_path/'coordination.sqlite3'
    a=Registry(path,'bot:3');b=Registry(path,'bot:4')
    await a.open();await b.open()
    await a.record(1,111,'role','111')
    with pytest.raises(ValueError):await b.check_role(1,111)
    with pytest.raises(ValueError):await b.record(1,111,'role','111')
    async with a.lease(1):
        with pytest.raises(ValueError):
            async with b.lease(1):pass
        report=suite_protocol.inspect(path,1)
        assert report['leases'][0]['mirrored']
    assert not suite_protocol.inspect(path,1)['leases']
    assert path.stat().st_mode&0o777==0o660
    assert suite_protocol.inspect(path,1)['resources'][0]['owner']=='bot:3'


def test_release_staging_excludes_secrets_and_preserves_previous(tmp_path):
    source=tmp_path/'source';source.mkdir()
    for p in release.files(ROOT):
        dest=source/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
    (source/'.env').write_text('TOP SECRET')
    (source/'ledger.sqlite3').write_text('private')
    base=tmp_path/'install';first=release.stage(source,base/'releases/1.0.0-first')
    assert not (first/'.env').exists() and not (first/'ledger.sqlite3').exists()
    assert json.loads((first/'RELEASE-MANIFEST.json').read_text())==release.manifest(first)
    release.switch(base,first)
    second=release.stage(source,base/'releases/1.0.0-second');release.switch(base,second)
    assert (base/'current').resolve()==second
    assert (base/'previous').resolve()==first
    release.switch(base,first)
    assert (base/'current').resolve()==first
    (second/'main.py').write_text('tampered')
    with pytest.raises(ValueError):release.switch(base,second)
    assert (base/'current').resolve()==first


def test_release_rejects_external_symlink(tmp_path):
    (tmp_path/'assets').mkdir()
    (tmp_path/'assets/stolen').symlink_to('/etc/passwd')
    with pytest.raises(ValueError):release.files(tmp_path)


def test_restart_budget_survives_helper_restarts(tmp_path,clock):
    path=tmp_path/'recovery/state.json'
    for _ in range(3):
        budget=RestartBudget(path,clock);budget.reserve();clock.now+=121
    with pytest.raises(ValueError):RestartBudget(path,clock).reserve()
    clock.now+=901;budget=RestartBudget(path,clock);budget.reserve()
    budget.data['paused']=True;budget.save();clock.now+=121
    with pytest.raises(ValueError):RestartBudget(path,clock).reserve()
    assert path.stat().st_mode&0o777==0o600
    assert not path.with_suffix('.tmp').exists()


def test_corrupt_recovery_state_does_not_reset_budget(tmp_path):
    path=tmp_path/'state.json';path.write_text('{}')
    with pytest.raises(ValueError):RestartBudget(path)


def test_shell_scripts_parse_and_preflight_initializes_isolated_db(tmp_path):
    subprocess.run(['bash','-n','scripts/install.sh','scripts/rollback.sh'],cwd=ROOT,check=True)
    path=tmp_path/'preflight.sqlite3'
    result=subprocess.run([sys.executable,'scripts/preflight.py','--database',str(path)],cwd=ROOT,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    assert 'consistency: OK' in result.stdout


@pytest.mark.parametrize('uid',[0,1000])
def test_local_maintenance_drops_root_before_opening_private_sqlite(monkeypatch,uid):
    from types import SimpleNamespace
    spec=importlib.util.spec_from_file_location('rzctl_check',ROOT/'scripts/rzctl.py')
    ctl=importlib.util.module_from_spec(spec);spec.loader.exec_module(ctl)
    calls=[]
    monkeypatch.setattr(ctl.os,'geteuid',lambda:uid)
    monkeypatch.setattr(ctl.pwd,'getpwnam',lambda name:SimpleNamespace(pw_name=name,pw_gid=5678,pw_uid=5678))
    monkeypatch.setattr(ctl.os,'initgroups',lambda name,gid:calls.append(('groups',name,gid)))
    monkeypatch.setattr(ctl.os,'setgid',lambda gid:calls.append(('gid',gid)))
    monkeypatch.setattr(ctl.os,'setuid',lambda uid:calls.append(('uid',uid)))
    ctl.drop_service_user()
    assert calls==([('groups','ripperzone',5678),('gid',5678),('uid',5678)] if uid==0 else [])


def test_recovery_unit_can_read_private_data_but_not_write_the_ledger():
    from configparser import ConfigParser
    def unit(name):
        cfg=ConfigParser(interpolation=None);cfg.read(ROOT/'systemd'/name);return cfg['Service']
    main=unit('ripper-zone.service');helper=unit('ripper-zone-recovery.service')
    assert main['User']=='ripperzone' and main['CapabilityBoundingSet']==''
    # UID 0 alone does not bypass a 0700 directory after all capabilities are dropped.
    assert helper['User']=='root' and helper['CapabilityBoundingSet']=='CAP_DAC_READ_SEARCH'
    assert helper['ProtectSystem']=='strict'
    assert helper['ReadWritePaths']=='/var/lib/ripper-zone/recovery'
    assert main['ReadOnlyPaths']=='/var/lib/ripper-zone/recovery'


def test_staged_public_code_is_readable_under_installer_private_umask(tmp_path):
    import os
    previous=os.umask(0o077)
    try:staged=release.stage(ROOT,tmp_path/'release')
    finally:os.umask(previous)
    assert staged.stat().st_mode&0o777==0o755
    assert all(p.stat().st_mode&0o055==0o055 for p in staged.rglob('*') if p.is_dir())
    assert all(p.stat().st_mode&0o044==0o044 for p in staged.rglob('*') if p.is_file())
    assert not (staged/'.env').exists()
