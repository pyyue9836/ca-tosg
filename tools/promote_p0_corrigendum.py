#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-5 promotion: make the N=1 corrigendum products the mainline products.

This is the one operation in the repository that deliberately overwrites deployed products. It is
authorised once, for one commit, by the P0-5 ruling, and it is a **pure byte move**: no product is
regenerated during the promotion, so what lands in `results/main/` is bit-identical to what the
corrigendum run produced and what `docs/p0_corrigendum.md` tabulates.

Four assertions, any one of which aborts before a single file is touched:

  a. the tag `pre-p0-corrigendum` exists and points at the current HEAD commit;
  b. every promoted file's sha256 at the destination equals the sha256 of its `results/p0_n1/`
     source (checked after the copy, per file);
  c. no `legacy/` or `archive/` directory is created — the retired products live in git history and
     under the tag, nowhere else;
  d. after promotion the moved sources are deleted from `p0_n1/` (logs and the corrigendum document
     stay), and the manifests / index / provenance / registry are repointed.

    python tools/promote_p0_corrigendum.py --dry-run
    python tools/promote_p0_corrigendum.py --promote
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARM = os.path.join(ROOT, 'results/p0_n1')
ARM_DATA = os.path.join(ROOT, 'data/p0_n1')
TAG = 'pre-p0-corrigendum'
KEEP_IN_ARM = ('.log',)                      # self-check + stage logs stay where they are


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def plan():
    """[(src_abs, dst_abs)] -- every promotion, derived from the arm tree, not typed out."""
    out = []
    # results/p0_n1/*.csv -> results/main/
    for f in sorted(os.listdir(ARM)):
        p = os.path.join(ARM, f)
        if os.path.isfile(p) and f.endswith('.csv'):
            out.append((p, os.path.join(ROOT, 'results/main', f)))
    # sensitivity/ and baselines/ mirror their deployed trees
    for sub, dest in (('sensitivity', 'results/sensitivity'), ('baselines', 'results/baselines')):
        base = os.path.join(ARM, sub)
        for dirpath, _d, files in os.walk(base):
            for f in files:
                src = os.path.join(dirpath, f)
                rel = os.path.relpath(src, base)
                out.append((src, os.path.join(ROOT, dest, rel)))
    # manifests: three are renamed to the deployed names they replace
    rename = {'N1_FROZEN_MANIFEST.json': 'FROZEN_MANIFEST.json',
              'N1_FEATURE_ABLATION_MANIFEST.json': 'FEATURE_ABLATION_MANIFEST.json'}
    prov = {'PROVENANCE_fa_n1.txt': 'PROVENANCE_fa.txt'}
    for f in sorted(os.listdir(os.path.join(ARM, 'manifests'))):
        src = os.path.join(ARM, 'manifests', f)
        if f.startswith('PROVENANCE'):
            out.append((src, os.path.join(ROOT, 'results/provenance', prov.get(f, f))))
        else:
            out.append((src, os.path.join(ROOT, 'results/manifests', rename.get(f, f))))
    # data/: grids, the three frozen selectors, the FA variant models, the N=1 cue tables
    for f in sorted(os.listdir(ARM_DATA)):
        src = os.path.join(ARM_DATA, f)
        if os.path.isfile(src):
            out.append((src, os.path.join(ROOT, 'data/p2', f)))
    for sub in ('model', 'fa'):
        d = os.path.join(ARM_DATA, sub)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                out.append((os.path.join(d, f), os.path.join(ROOT, 'data/p2', f)))
    return out


def assert_a():
    r = subprocess.run(['git', '-C', ROOT, 'rev-parse', f'{TAG}^{{commit}}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f'ASSERT (a) FAILED: tag {TAG} does not exist')
    head = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'],
                          capture_output=True, text=True).stdout.strip()
    if r.stdout.strip() != head:
        raise SystemExit(f'ASSERT (a) FAILED: {TAG} -> {r.stdout.strip()[:12]} but HEAD is '
                         f'{head[:12]}; tag the promotion-eve commit first')
    print(f'  (a) OK  tag {TAG} == HEAD {head[:12]}')


def assert_c(pairs):
    bad = [d for _s, d in pairs if any(x in d.split(os.sep) for x in ('legacy', 'archive'))]
    if bad:
        raise SystemExit(f'ASSERT (c) FAILED: promotion would create an archive dir: {bad[:3]}')
    for d in ('results/legacy_fullcollab', 'results/archive', 'results/legacy'):
        if os.path.exists(os.path.join(ROOT, d)):
            raise SystemExit(f'ASSERT (c) FAILED: {d} exists; retired products belong in git '
                             f'history and under {TAG}, nowhere else')
    print('  (c) OK  no legacy/archive directory involved')


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry-run', action='store_true')
    g.add_argument('--promote', action='store_true')
    a = ap.parse_args()
    pairs = plan()
    print(f'promotion plan: {len(pairs)} file(s)')
    print('pre-flight assertions:')
    assert_a()
    assert_c(pairs)
    new = [(s, d) for s, d in pairs if not os.path.exists(d)]
    print(f'  (info)  {len(pairs) - len(new)} replace an existing product, {len(new)} are new')
    if a.dry_run:
        for s, d in pairs:
            print(f'    {"NEW " if not os.path.exists(d) else "REPL"} '
                  f'{os.path.relpath(s, ROOT)} -> {os.path.relpath(d, ROOT)}')
        print('dry run: nothing written')
        return 0

    print('promoting (pure byte move):')
    moved = []
    for s, d in pairs:
        want = sha256(s)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(s, d)
        got = sha256(d)
        if got != want:                                    # assertion (b), per file
            raise SystemExit(f'ASSERT (b) FAILED on {os.path.relpath(d, ROOT)}: '
                             f'{got[:12]} != {want[:12]}')
        moved.append((s, d, want))
    print(f'  (b) OK  {len(moved)} file(s) byte-identical to their p0_n1 source')

    removed = 0
    for s, _d, _h in moved:                                # assertion (d), first half
        if not s.endswith(KEEP_IN_ARM):
            os.remove(s)
            removed += 1
    for base in (ARM, ARM_DATA):                           # drop the emptied directories
        for dirpath, dirs, files in os.walk(base, topdown=False):
            if not files and not dirs and dirpath not in (ARM, ARM_DATA):
                os.rmdir(dirpath)
    print(f'  (d) OK  {removed} promoted source(s) removed from p0_n1/; '
          f'{len(os.listdir(ARM))} item(s) kept (logs)')
    print('\nNEXT (still part of (d)): repoint FROZEN_MANIFEST paths, results/README.md index, '
          'the PROVENANCE headers and the canonical registry, then re-run every gate.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
