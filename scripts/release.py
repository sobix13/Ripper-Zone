#!/usr/bin/env python3
"""Stage only an explicit release file list. Runtime data and symlinks are refused."""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES=('VERSION','README.md','main.py','requirements.txt','requirements-dev.txt','requirements-lock.txt','pyproject.toml','.env.example','.gitignore')
FOLDERS=('ripper_zone','scripts','systemd','tests','assets','docs','.github')


def files(root):
    root=Path(root)
    selected=[root/name for name in ROOT_FILES if (root/name).is_file()]
    for folder in FOLDERS:
        for path in (root/folder).rglob('*') if (root/folder).exists() else []:
            if path.is_symlink():raise ValueError("Release symlinks are forbidden: "+str(path))
            if path.name=='.env' or path.name.endswith(('.sqlite3-wal','.sqlite3-shm','.db-wal','.db-shm','.pem','.key')):raise ValueError('Private runtime file in release folder: '+str(path))
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.db','.sqlite3'):
                selected.append(path)
    for path in selected:
        if path.is_symlink():raise ValueError("Release symlinks are forbidden.")
    return sorted(selected)


def manifest(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files(root)}


def stage(source,destination):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if destination.exists():raise ValueError("Release directory already exists.")
    version=(source/'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):raise ValueError("Invalid release version.")
    wanted=manifest(source)
    if not all(name in wanted for name in ('main.py','requirements-lock.txt','scripts/install.sh')):raise ValueError("Release is incomplete.")
    destination.mkdir(parents=True,mode=0o755)
    for relative in wanted:
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/relative,target)
        target.chmod(0o755 if relative.endswith('.sh') else 0o644)
    if manifest(destination)!=wanted:raise ValueError("Staged release checksum differs.")
    (destination/'RELEASE-MANIFEST.json').write_text(json.dumps(wanted,indent=2)+'\n')
    # The installer uses umask 077, but the non-root service must read public code.
    destination.chmod(0o755)
    for directory in destination.rglob('*'):
        if directory.is_dir():directory.chmod(0o755)
    (destination/'RELEASE-MANIFEST.json').chmod(0o644)
    return destination


def switch(base,release):
    base,release=Path(base).resolve(),Path(release).resolve()
    if release.parent!=base/'releases' or not (release/'RELEASE-MANIFEST.json').exists():raise ValueError("Use a verified release in this installation.")
    expected=json.loads((release/'RELEASE-MANIFEST.json').read_text())
    if manifest(release)!=expected:raise ValueError("Release files changed after staging.")
    current=base/'current';previous=base/'previous'
    if current.is_symlink():
        old=current.resolve()
        if old==release:return
        temp=base/'previous.next';temp.unlink(missing_ok=True);temp.symlink_to(old);temp.replace(previous)
    elif current.exists():raise ValueError("Current is not a managed symlink.")
    temp=base/'current.next';temp.unlink(missing_ok=True);temp.symlink_to(release);temp.replace(current)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('stage');a.add_argument('source');a.add_argument('destination')
    a=sub.add_parser('switch');a.add_argument('base');a.add_argument('release')
    a=p.parse_args()
    print(stage(a.source,a.destination) if a.action=='stage' else switch(a.base,a.release) or 'Release switched.')
