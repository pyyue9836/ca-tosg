#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply (or verify) this project's OpenCOOD modifications against a checkout.

The `opencood` package is upstream code that this project modifies in place: 11 files added and 5
modified. Until now those changes existed only in one working tree, which made the repository
unreproducible for anyone else — `patches/opencood/*.patch` is the portable form, and this script
is how they go on and how their presence is checked.

    python tools/apply_opencood_patches.py --check              # what is applied, what is missing
    python tools/apply_opencood_patches.py --apply              # apply anything missing
    python tools/apply_opencood_patches.py --export             # regenerate the patches from a tree

`--target` defaults to the sibling `../OpenCOOD` checkout.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCHES = os.path.join(ROOT, 'patches', 'opencood')
DEFAULT_TARGET = os.path.abspath(os.path.join(os.path.dirname(ROOT), 'OpenCOOD'))


def patch_files():
    return sorted(f for f in os.listdir(PATCHES) if f.endswith('.patch'))


def target_path(name):
    """`added__opencood_utils_foo.py.patch` -> the path the patch touches, read from the patch."""
    with open(os.path.join(PATCHES, name), encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith('+++ b/'):
                return line[6:].strip()
            if line.startswith('--- a/'):
                return line[6:].strip()
    return None


def git(target, *args):
    return subprocess.run(['git', '-C', target, *args], capture_output=True, text=True)


def check(target):
    missing, applied, unknown = [], [], []
    for name in patch_files():
        rel = target_path(name)
        if rel is None:
            unknown.append(name)
            continue
        r = git(target, 'apply', '--check', '--reverse', os.path.join(PATCHES, name))
        if r.returncode == 0:
            applied.append((name, rel))
            continue
        r2 = git(target, 'apply', '--check', os.path.join(PATCHES, name))
        (missing if r2.returncode == 0 else unknown).append((name, rel) if r2.returncode == 0
                                                            else (name, rel or '?'))
    print(f'target: {target}')
    print(f'  already applied : {len(applied)}')
    print(f'  applies cleanly : {len(missing)}')
    print(f'  neither         : {len(unknown)}   (modified by hand, or the file drifted)')
    for name, rel in missing:
        print(f'    MISSING   {rel}')
    for item in unknown:
        print(f'    CONFLICT  {item[1] if isinstance(item, tuple) else item}')
    return 0 if not unknown else 1


def apply(target):
    rc = 0
    for name in patch_files():
        p = os.path.join(PATCHES, name)
        if git(target, 'apply', '--check', '--reverse', p).returncode == 0:
            print(f'  skip (already applied)  {name}')
            continue
        r = git(target, 'apply', p)
        print(f'  {"applied" if r.returncode == 0 else "FAILED "}  {name}'
              + ('' if r.returncode == 0 else f'\n      {r.stderr.strip()[:200]}'))
        rc |= r.returncode
    return rc


def export(target):
    """Regenerate the patch set from the target tree's current state."""
    os.makedirs(PATCHES, exist_ok=True)
    status = git(target, 'status', '--porcelain').stdout.splitlines()
    n = 0
    for line in status:
        code, path = line[:2].strip(), line[3:].strip()
        if not path.startswith('opencood/'):
            continue
        flat = path.replace('/', '_')
        if code == 'M':
            out, diff = f'modified__{flat}.patch', git(target, 'diff', '--', path).stdout
        elif code == '??':
            out = f'added__{flat}.patch'
            diff = subprocess.run(['git', '-C', target, 'diff', '--no-index', '/dev/null', path],
                                  capture_output=True, text=True).stdout
        else:
            continue
        with open(os.path.join(PATCHES, out), 'w', encoding='utf-8') as f:
            f.write(diff)
        n += 1
        print(f'  exported {out}')
    print(f'{n} patch file(s) written to {os.path.relpath(PATCHES, ROOT)}')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', default=DEFAULT_TARGET)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--check', action='store_true')
    g.add_argument('--apply', action='store_true')
    g.add_argument('--export', action='store_true')
    a = ap.parse_args()
    if not os.path.isdir(os.path.join(a.target, '.git')):
        print(f'FAIL: {a.target} is not a git checkout')
        return 1
    if a.check:
        return check(a.target)
    if a.apply:
        return apply(a.target)
    return export(a.target)


if __name__ == '__main__':
    sys.exit(main())
