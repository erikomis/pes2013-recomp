#!/usr/bin/env python3
"""Stage the port's own sources and tools for the launcher bundle.

    python3 launcher/scripts/stage_port.py [--out launcher/stage/port]

The repository is private, so the app cannot clone it: it carries exactly what
an install needs, and copies it to ~/Library/Application Support/pes13-recomp/port/.
The layout is the repository's:

    port/BUILD_INFO.json         commit the sources come from (no git there)
    port/LICENSE, CREDITS*.md
    port/port/                   CMakeLists.txt, config.toml, main.cpp, stubs.cpp,
                                 pes_leagues.cpp, lifted_overrides.txt
    port/patches/                the ps3recomp toolkit patch setup_toolkit.sh applies
    port/tools/                  the scripts the install and Play run (TOOLS below)

Not the Brazil-2026 data tools, nothing lifted (port/spu), no game file and no
key: only the files listed here, each of which must exist and be one git does
not ignore, so nothing local can slip in. check_bundle.py then verifies the app.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_OUT = os.path.join(REPO, 'launcher', 'stage', 'port')

TOOLS = [
    'env.sh', 'run.sh', 'rebuild.sh', 'build.sh', 'lift_spu.sh', 'lift_jobs.sh',
    'setup_toolkit.sh', 'decrypt_self.py', 'install_savedata.py', 'pes2013_edit.py',
    'weaken_lifted.py',
]
WANT = (['LICENSE', 'CREDITS.md', 'CREDITS.pt-BR.md',
         'port/CMakeLists.txt', 'port/config.toml', 'port/main.cpp', 'port/stubs.cpp',
         'port/pes_leagues.cpp', 'port/lifted_overrides.txt',
         'patches/ps3recomp-675ed39-pes13.patch']
        + ['tools/' + t for t in TOOLS])


def git(*args, check=True):
    return subprocess.run(['git', '-C', REPO, *args], check=check, capture_output=True, text=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=DEFAULT_OUT, help='staging folder (default: %(default)s); emptied first')
    a = ap.parse_args(argv)

    missing = [p for p in WANT if not os.path.isfile(os.path.join(REPO, p))]
    if missing:
        sys.exit('stage_port: missing: %s' % ', '.join(missing))
    ignored = [p for p in WANT if git('check-ignore', '-q', p, check=False).returncode == 0]
    if ignored:
        sys.exit('stage_port: ignored by git (local files, not sources): %s' % ', '.join(ignored))
    untracked = sorted(set(WANT) - set(git('ls-files', '--', *WANT).stdout.split()))

    out = os.path.abspath(a.out)
    if os.path.isdir(out) and os.listdir(out) and not os.path.isfile(os.path.join(out, 'BUILD_INFO.json')):
        sys.exit('stage_port: refusing to empty %s (not a previous staging folder)' % out)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    total = 0
    for rel in WANT:
        src = os.path.join(REPO, *rel.split('/'))
        dst = os.path.join(out, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if rel.endswith('.sh') or rel.endswith('.py'):
            os.chmod(dst, 0o755)
        total += os.path.getsize(dst)

    try:
        commit = git('rev-parse', '--short', 'HEAD').stdout.strip()
        dirty = bool(git('status', '--porcelain', '--', *WANT).stdout.strip())
    except subprocess.CalledProcessError:
        commit, dirty = '', False
    info = {
        'schema': 1,
        'port_commit': commit + ('-dirty' if dirty else ''),
        'staged_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'files': len(WANT),
    }
    with open(os.path.join(out, 'BUILD_INFO.json'), 'w') as f:
        json.dump(info, f, indent=2)
        f.write('\n')
    print('staged %d files (%d KB) from %s into %s' % (len(WANT), total // 1024, info['port_commit'] or '?', out))
    if untracked:
        print('stage_port: not committed yet (staged anyway): %s' % ', '.join(untracked))
    return 0


if __name__ == '__main__':
    sys.exit(main())
