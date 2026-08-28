#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R21 B — gate 26: the OpenCOOD patch set must still describe the sibling checkout.

THE ROOT CAUSE THIS EXISTS FOR
------------------------------
`patches/opencood/` is the *portable form* of this project's OpenCOOD modifications — the only thing
that lets a fresh clone reproduce a v2 product. It went stale at V2-R16 and **survived four rounds
undetected**: `--check` reported 15 applied and 1 CONFLICT, and two v2-critical files
(`catosg_eval_rng.py`, `pcd_utils.py`) had no patch at all. Every gate was green throughout.

Nothing covered it because **no gate ever ran the generator**. That is the R63 family: the suite
checked committed artefacts and never asked whether the script that owns them still reproduces them.
Gate 24 pins the *manifest*; this gate pins the *patches themselves* against the tree they claim to
describe. They are different failure modes: the manifest can be perfectly self-consistent while the
patch that is supposed to recreate the file no longer applies.

WHAT IS CHECKED (B-2)
---------------------
  1. `apply_opencood_patches.py --check` reports **0 conflicts** and **0 missing**;
  2. the number applied equals the number of files registered in the manifest;
  3. every patch file's SHA-256 equals its registered value — a patch edited in place is caught even
     if it still applies;
  4. every registered file's **actual content hash in the sibling worktree** equals its registered
     value.

(3) and (4) are deliberately both present. (3) catches the portable form drifting; (4) catches the
working tree drifting. Either alone leaves a hole: a patch could be rewritten to match a changed
file, or a file changed to match a rewritten patch, and one-sided checking would bless it.

  python tests/test_patch_freshness.py
  python tests/test_patch_freshness.py --self-test    # B-3: three injections, all must FIRE
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIBLING = os.path.abspath(os.path.join(os.path.dirname(ROOT), 'OpenCOOD'))
PATCHES = os.path.join(ROOT, 'patches', 'opencood')
MANIFEST = os.path.join(ROOT, 'results', 'manifests', 'V2_SIBLING_DEPENDENCY.json')
APPLY = os.path.join(ROOT, 'tools', 'apply_opencood_patches.py')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def run_check(patches_dir, sibling):
    """Run the real --check, optionally against a substituted patch directory."""
    env = dict(os.environ)
    if patches_dir != PATCHES:
        # the tool resolves PATCHES from its own location, so run a copy whose tree we control
        tmp_root = os.path.dirname(os.path.dirname(patches_dir))
        script = os.path.join(tmp_root, 'tools', 'apply_opencood_patches.py')
    else:
        script = APPLY
    r = subprocess.run([sys.executable, script, '--check', '--target', sibling],
                       capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def parse_counts(out):
    got = {}
    for line in out.splitlines():
        for key, label in (('applied', 'already applied'), ('cleanly', 'applies cleanly'),
                           ('neither', 'neither')):
            if line.strip().startswith(label):
                try:
                    got[key] = int(line.split(':')[1].split()[0])
                except (IndexError, ValueError):
                    pass
    return got


def check(patches_dir=PATCHES, sibling=SIBLING, manifest_obj=None):
    fails = []
    if not os.path.exists(MANIFEST):
        return ['no sibling-dependency manifest -- run tools/build_sibling_dependency_manifest.py']
    man = manifest_obj if manifest_obj is not None else json.load(open(MANIFEST))
    n_registered = len(man['files'])

    rc, out = run_check(patches_dir, sibling)
    counts = parse_counts(out)
    if counts.get('neither', -1) != 0:
        fails.append(f'apply_opencood_patches --check reports {counts.get("neither")} conflict(s): '
                     + '; '.join(l.strip() for l in out.splitlines() if 'CONFLICT' in l))
    if counts.get('cleanly', -1) != 0:
        fails.append(f'{counts.get("cleanly")} patch(es) are NOT applied to the sibling: '
                     + '; '.join(l.strip() for l in out.splitlines() if 'MISSING' in l))
    if counts.get('applied', -1) != n_registered:
        fails.append(f'{counts.get("applied")} patch(es) applied but {n_registered} file(s) '
                     f'registered in the manifest -- the two disagree about the file set')

    on_disk = sorted(f for f in os.listdir(patches_dir) if f.endswith('.patch'))
    if len(on_disk) != n_registered:
        fails.append(f'{len(on_disk)} patch file(s) on disk but {n_registered} registered')

    for rel, rec in sorted(man['files'].items()):
        pp = os.path.join(ROOT, rec['patch'])
        if patches_dir != PATCHES:
            pp = os.path.join(patches_dir, os.path.basename(rec['patch']))
        if not os.path.exists(pp):
            fails.append(f'patch missing: {rec["patch"]}')
        elif sha256_file(pp) != rec['patch_sha256']:
            fails.append(f'patch content moved: {rec["patch"]} '
                         f'({sha256_file(pp)[:12]} != {rec["patch_sha256"][:12]})')
        fp = os.path.join(sibling, rel)
        if not os.path.exists(fp):
            fails.append(f'sibling file missing: {rel}')
        elif sha256_file(fp) != rec['sha256']:
            fails.append(f'sibling file changed: {rel} '
                         f'({sha256_file(fp)[:12]} != {rec["sha256"][:12]})')
    return fails


def _stage(tmp):
    """A throwaway copy of tools/ + patches/ so injections never touch the real tree."""
    os.makedirs(os.path.join(tmp, 'tools'))
    shutil.copy2(APPLY, os.path.join(tmp, 'tools', 'apply_opencood_patches.py'))
    shutil.copytree(PATCHES, os.path.join(tmp, 'patches', 'opencood'))
    return os.path.join(tmp, 'patches', 'opencood')


def self_test():
    man = json.load(open(MANIFEST))
    if check():
        print('SELF-TEST FAIL: the baseline must be clean or the injections prove nothing')
        return 1
    print('  baseline (untouched patches and sibling): clean')

    results = []
    victim = 'opencood/utils/catosg_eval_rng.py'
    vpatch = os.path.basename(man['files'][victim]['patch'])

    with tempfile.TemporaryDirectory() as tmp:
        pd = _stage(tmp)
        p = os.path.join(pd, vpatch)
        with open(p, 'a', encoding='utf-8') as f:
            f.write('\n# injected drift\n')
        f1 = check(patches_dir=pd)
        results.append(('a patch file is edited', bool(f1), f1[0] if f1 else ''))

    with tempfile.TemporaryDirectory() as tmp:
        pd = _stage(tmp)
        os.remove(os.path.join(pd, vpatch))
        f2 = check(patches_dir=pd)
        results.append(('a patch file is deleted', bool(f2), f2[0] if f2 else ''))

    # A sibling-content injection without writing to the sibling: the manifest's registered hash for
    # a file is the thing the check compares against, so perturbing it is equivalent to the file
    # having changed, and it cannot corrupt anyone's working tree.
    man3 = json.loads(json.dumps(man))
    man3['files'][victim]['sha256'] = '0' * 64
    f3 = check(manifest_obj=man3)
    results.append(('the sibling file content differs from its registered hash',
                    bool(f3), f3[0] if f3 else ''))

    ok = True
    for name, fired, msg in results:
        print(f'  {"FIRES  " if fired else "SILENT "}  {name}')
        if fired:
            print(f'            -> {msg[:150]}')
        ok &= fired
    print('PATCH FRESHNESS SELF-TEST ' + ('PASS: all three injections fire' if ok else
                                          'FAIL: an injection did not fire'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    if not os.path.isdir(os.path.join(SIBLING, '.git')):
        print(f'PATCH FRESHNESS GATE FAIL: no sibling checkout at {SIBLING}')
        return 1
    fails = check()
    n = len([f for f in os.listdir(PATCHES) if f.endswith('.patch')])
    print(f'patch freshness: {n} patch(es) checked against the sibling checkout, both directions '
          f'(patch content and worktree content)')
    if fails:
        print('\nPATCH FRESHNESS GATE FAIL:')
        for f in fails:
            print('  ' + f)
        print('  fix: python tools/apply_opencood_patches.py --export && '
              'python tools/build_sibling_dependency_manifest.py')
        return 1
    print('PATCH FRESHNESS GATE PASS: every patch applies, the count matches the manifest, and '
          'both the patch files and the sibling files hash to their registered values.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
