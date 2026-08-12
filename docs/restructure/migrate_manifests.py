#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Commit 3/4: migrate the frozen manifests' INTERNAL relative paths.

The manifests are the frozen record of the P2 / P4-A products. Their `inputs[*].file` and
`budgets[*].model` fields are paths relative to the tree root -- which used to be `paper1/`
and is now the repository root. Two things therefore change, and only these two:

  1. paths that pointed OUT of the tree lose one level     ../../OpenCOOD/... -> ../OpenCOOD/...
  2. paths into directories the restructure moved are remapped through RESTRUCTURE_MAP.csv
     results/p2_dataprep/... -> results/manifests/... , results/bler_sionna/... -> results/channel/...

Nothing else is touched: no hash, no timestamp, no selection field. Every recorded md5/sha256 is
RE-VERIFIED against the file at its new location before the manifest is written -- if a hash no
longer matches, the migration aborts rather than committing a manifest whose pins are decorative.

  python docs/restructure/migrate_manifests.py --check     # report only
  python docs/restructure/migrate_manifests.py --write
"""
import csv
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OLD_ROOT = os.path.join(ROOT, 'paper1')                 # the tree root before the restructure
MANIFESTS = ['results/manifests/FROZEN_MANIFEST.json', 'results/manifests/P4A_MANIFEST.json']
PATH_KEYS = ('file', 'model')


def _hash(p, algo):
    h = hashlib.new(algo)
    h.update(open(p, 'rb').read())
    return h.hexdigest()


def load_map():
    files, dirs = {}, {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'RESTRUCTURE_MAP.csv'))):
        if r['row_type'] != 'FILE' or not r['old_path'].startswith('paper1/'):
            continue
        if r['disposition'] == 'DELETE':
            continue
        old = r['old_path'][len('paper1/'):]
        new = r['new_path'].split(' + ')[0].strip()
        files[old] = new
        od, nd = os.path.dirname(old), os.path.dirname(new)
        dirs.setdefault(od, set()).add(nd)
    dirs = {k: v.pop() for k, v in dirs.items() if len(v) == 1 and k}
    return files, dirs


def remap(rel, files, dirs):
    """old relpath (relative to paper1/) -> new relpath (relative to the repo root)."""
    if rel.startswith('../'):                            # points outside the tree: lose one level
        return rel[3:] if rel.startswith('../../') else rel
    if rel in files:
        return files[rel]
    parts = rel.split('/')
    for i in range(len(parts), 0, -1):
        pre = '/'.join(parts[:i])
        if pre in dirs:
            return '/'.join(([dirs[pre]] if dirs[pre] else []) + parts[i:])
    return rel                                           # unchanged (e.g. data/p2/, git-excluded)


def walk(obj, files, dirs, changes, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in PATH_KEYS and isinstance(v, str):
                nv = remap(v, files, dirs)
                if nv != v:
                    changes.append((path + '/' + k, v, nv))
                    obj[k] = nv
            else:
                walk(v, files, dirs, changes, path + '/' + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, files, dirs, changes, path + '[%d]' % i)


def verify(obj, path='', bad=None, checked=None):
    """Every recorded hash must match the file the (migrated) relpath now points at."""
    bad = [] if bad is None else bad
    checked = [] if checked is None else checked
    if isinstance(obj, dict):
        rel = obj.get('file') or obj.get('model')
        if isinstance(rel, str):
            p = os.path.normpath(os.path.join(ROOT, rel))
            if not os.path.exists(p):
                bad.append('%s: does not resolve -> %s' % (path or '/', rel))
            else:
                for algo in ('md5', 'sha256'):
                    if algo in obj:
                        got = _hash(p, algo)
                        checked.append((rel, algo, got == obj[algo]))
                        if got != obj[algo]:
                            bad.append('%s: %s mismatch for %s (manifest %s, file %s)'
                                       % (path or '/', algo, rel, obj[algo][:12], got[:12]))
        for k, v in obj.items():
            verify(v, path + '/' + str(k), bad, checked)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            verify(v, path + '[%d]' % i, bad, checked)
    return bad, checked


def main():
    write = '--write' in sys.argv
    files, dirs = load_map()
    rc = 0
    for rel in MANIFESTS:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print('%s ABSENT' % rel)
            continue
        raw = open(p, encoding='utf-8').read()
        obj = json.loads(raw)
        changes = []
        walk(obj, files, dirs, changes)
        print('\n%s: %d relpath(s) migrated' % (rel, len(changes)))
        for where, a, b in changes:
            print('   %-28s %s\n   %-28s -> %s' % (where, a, '', b))
        bad, checked = verify(obj)
        ok = sum(1 for _, _, good in checked if good)
        print('   hash re-verification: %d/%d recorded hashes match at the new location'
              % (ok, len(checked)))
        for b in bad:
            print('   FAIL %s' % b)
        if bad:
            rc = 1
            continue
        if write and changes:
            out = json.dumps(obj, indent=2) + '\n'
            if not raw.endswith('\n'):
                out = out[:-1]
            open(p, 'w', encoding='utf-8').write(out)
            # A relabel must not change the OBSERVABLE freeze ordering. tests/test_data_leakage.py
            # check (4) asserts every test/Culver grid was built AFTER the freeze, using mtime;
            # rewriting the file would bump its mtime past the grids and fake a violation. Restore
            # it from the manifest's OWN freeze_timestamp -- derived from the file, not invented.
            ts = obj.get('freeze_timestamp')
            if ts:
                import datetime
                epoch = datetime.datetime.fromisoformat(ts).timestamp()
                os.utime(p, (epoch, epoch))
                print('   mtime restored to freeze_timestamp %s' % ts)
            print('   WRITTEN')
    return rc


if __name__ == '__main__':
    sys.exit(main())
