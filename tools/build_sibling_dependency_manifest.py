#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R20 D-3 — register the sibling-OpenCOOD files the v2 products depend on.

WHY THIS EXISTS, AND WHY THE IMPORT GATE WAS RIGHT
--------------------------------------------------
`tests/test_eval_determinism.py` imports `catosg_eval_rng`, which is not in this repository. The
intra-repo import gate flagged it, and **that was not a false positive**: the module lives only in
one person's sibling checkout, so a fresh clone of this repository cannot reproduce a single v2
product. The gate found a real reproducibility hole; its wording was just too coarse to say which.

The remedy is **not** to exempt the import. It is to make the dependency explicit, versioned and
checkable — one registered external module, pinned to a base commit and to content hashes, with
everything else still forbidden.

WHAT IS REGISTERED
------------------
* the upstream repository and the **base commit** the patches apply to;
* every file this project adds to or modifies in `opencood/`, by **SHA-256 of the resulting file**;
* which of them the v2 evaluation path actually depends on;
* the SHA-256 of each patch in `patches/opencood/`, so the portable form is pinned too.

THE HONEST LIMIT, STATED RATHER THAN GLOSSED (D-7)
--------------------------------------------------
V2-R20 D-2/D-6 asked for the three files to be committed and pushed in the sibling checkout first,
so the main repository could reference a fetchable commit. **That is not currently possible**: the
sibling's only remote is `https://github.com/DerrickXuNu/OpenCOOD.git`, the upstream project, which
this account cannot push to; no fork exists and no `gh` CLI is installed. Committing locally would
be worse than useless — it would produce an unfetchable commit **and** break
`tools/apply_opencood_patches.py --export`, which reads `git status --porcelain` and would then see
nothing to export.

So this is the D-7 route: **base commit + patches + hashes, held in this repository.** It is weaker
than a pushed commit in exactly one way, and the weakness is named here so it is not discovered
later: *the base commit is upstream's and is fetchable, but the modifications are carried as
patches rather than as history, so there is no signed, dated record of when each change was made
outside this repository's own change log.* Everything else — exact content, apply order,
verification — is covered.

Note also that D-3's "the sibling worktree must be clean for these three files" **cannot hold under
this route and is not claimed**: the files are modified relative to the base commit by construction,
which is the whole point. The invariant that replaces it is stronger and checkable: **the file
content hashes must equal the registered ones.**

    python tools/build_sibling_dependency_manifest.py            # write
    python tools/build_sibling_dependency_manifest.py --check    # verify against the sibling
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.abspath(os.path.join(os.path.dirname(ROOT), 'OpenCOOD'))
PATCHES = os.path.join(ROOT, 'patches', 'opencood')
OUT = os.path.join(ROOT, 'results', 'manifests', 'V2_SIBLING_DEPENDENCY.json')
SCHEMA = 'catosg-v2-sibling-dependency/1'

# The ONLY external module any file in this repository may import. One entry, not a category.
REGISTERED_IMPORTS = [{
    'module': 'catosg_eval_rng',
    'importer': 'tests/test_eval_determinism.py',
    'resolves_to': 'opencood/utils/catosg_eval_rng.py',
    'why': 'V2-R16 per-sample deterministic RNG. The determinism gate must exercise the very '
           'derivation the products used, so it imports the real module rather than a copy; a '
           'copy in this repository would be a second definition free to drift from the one the '
           'evaluation path runs.',
}]

# Files the v2 evaluation path depends on. Others in patches/ belong to earlier arms.
V2_CRITICAL = [
    'opencood/utils/catosg_eval_rng.py',
    'opencood/utils/pcd_utils.py',
    'opencood/data_utils/datasets/intermediate_fusion_dataset.py',
    'opencood/utils/catosg_collab_subset.py',
]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def git(*args, target=TARGET):
    return subprocess.run(['git', '-C', target, *args], capture_output=True, text=True)


def touched_paths():
    """Every opencood/ path the patch set covers, read from the patches themselves."""
    out = []
    for name in sorted(os.listdir(PATCHES)):
        if not name.endswith('.patch'):
            continue
        rel = None
        with open(os.path.join(PATCHES, name), encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.startswith('+++ b/'):
                    rel = line[6:].strip()
                    break
                if line.startswith('--- a/'):
                    rel = line[6:].strip()
        out.append((name, rel))
    return out


def build():
    if not os.path.isdir(os.path.join(TARGET, '.git')):
        raise SystemExit(f'sibling checkout not found: {TARGET}')
    base = git('rev-parse', 'HEAD').stdout.strip()
    url = git('config', '--get', 'remote.origin.url').stdout.strip()
    files = {}
    for name, rel in touched_paths():
        p = os.path.join(TARGET, rel)
        if not os.path.exists(p):
            raise SystemExit(f'patch {name} names {rel}, which does not exist in the sibling')
        files[rel] = {
            'sha256': sha256_file(p),
            'patch': f'patches/opencood/{name}',
            'patch_sha256': sha256_file(os.path.join(PATCHES, name)),
            'v2_critical': rel in V2_CRITICAL,
        }
    return {
        'schema': SCHEMA,
        'why': 'The v2 products cannot be reproduced from this repository alone. This pins exactly '
               'what else is needed. The intra-repo import gate flagged the gap and was RIGHT: it '
               'is narrowed against this manifest rather than exempted.',
        'upstream': {'url': url, 'base_commit': base,
                     'note': 'The base commit is upstream and fetchable. The modifications are '
                             'carried as patches in this repository, not as pushed history -- see '
                             'the module docstring for what that costs.'},
        'apply': 'python tools/apply_opencood_patches.py --apply --target <checkout of base_commit>',
        'verify': 'python tools/apply_opencood_patches.py --check',
        'registered_external_imports': REGISTERED_IMPORTS,
        'files': files,
        'counts': {'files': len(files),
                   'v2_critical': sum(1 for v in files.values() if v['v2_critical'])},
    }


def check(man):
    """Every registered file present, and its content hash unchanged."""
    fails = []
    base = git('rev-parse', 'HEAD').stdout.strip()
    if base != man['upstream']['base_commit']:
        fails.append(f'sibling HEAD {base[:12]} != registered base '
                     f'{man["upstream"]["base_commit"][:12]}')
    for rel, rec in man['files'].items():
        p = os.path.join(TARGET, rel)
        if not os.path.exists(p):
            fails.append(f'MISSING  {rel}')
            continue
        got = sha256_file(p)
        if got != rec['sha256']:
            fails.append(f'HASH     {rel}: {got[:12]} != registered {rec["sha256"][:12]}')
        pp = os.path.join(ROOT, rec['patch'])
        if not os.path.exists(pp):
            fails.append(f'NOPATCH  {rec["patch"]}')
        elif sha256_file(pp) != rec['patch_sha256']:
            fails.append(f'PATCH    {rec["patch"]} content moved')
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        if not os.path.exists(OUT):
            print(f'FAIL: no manifest at {os.path.relpath(OUT, ROOT)}')
            return 1
        man = json.load(open(OUT))
        fails = check(man)
        print(f'sibling dependency: {man["counts"]["files"]} registered file(s), '
              f'{man["counts"]["v2_critical"]} v2-critical, base '
              f'{man["upstream"]["base_commit"][:12]}')
        for f in fails:
            print(f'  {f}')
        print('SIBLING DEPENDENCY ' + ('PASS' if not fails else 'FAIL'))
        return 0 if not fails else 1
    man = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(man, f, indent=1)
    print(f'wrote {os.path.relpath(OUT, ROOT)}: {man["counts"]["files"]} file(s), '
          f'{man["counts"]["v2_critical"]} v2-critical')
    print(f'  base commit {man["upstream"]["base_commit"]}')
    for rel, rec in man['files'].items():
        if rec['v2_critical']:
            print(f'  v2  {rec["sha256"][:16]}  {rel}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
