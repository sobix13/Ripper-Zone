#!/usr/bin/env python3
"""Create a source distribution with exact file hashes and no runtime data."""
import argparse
import json
import tempfile
import zipfile
from pathlib import Path
from release import ROOT,stage


def build(target):
    target=Path(target).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root=stage(ROOT,Path(tmp)/'release')
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(root))
    return target


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('target');a=p.parse_args()
    print(build(a.target))
