#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R42 A-7 / C-3 — the v2 publication manifest, kept SEPARATE from the experiment close-out.

Two things are versioned independently on purpose: `V2_CLOSEOUT.json` fixes the experiment and must
never move again, while the manuscript will iterate. Folding the paper's hashes into the close-out
would make every wording edit look like an experimental change.

It also re-verifies the v1 freeze witness. The v2 draft lives in `paper/v2_draft/`; if any v1 file
has moved, that is a freeze breach and this fails.

    python tools/build_v2_publication_manifest.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', 'manifests', 'V2_PUBLICATION.json')
WITNESS = os.path.join(ROOT, 'results', 'manifests', 'V1_FREEZE_WITNESS.json')
DRAFT = os.path.join(ROOT, 'paper', 'v2_draft')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def v1_breaches():
    """Compare v1 against what is COMMITTED, not against the working tree.

    The freeze invariant is "nothing that changes v1 gets committed". The working tree is a
    different question: `tests/test_compile.py` rewrites paper/main.pdf and paper/supplementary.pdf
    on every run -- a documented side effect the stop-work order tells you to `git restore` -- so a
    working-tree comparison fails inside the suite every single time, on a self-inflicted change
    that was never committed. That would be a gate with a guaranteed false positive, which is worse
    than no gate.

    Checking the committed blob is also STRICTER where it matters: it catches a v1 edit that someone
    committed and then restored locally, which a working-tree check would miss entirely.
    """
    import subprocess
    w = json.load(open(WITNESS))['files']
    bad = []
    for rel, want in w.items():
        r = subprocess.run(['git', '-C', ROOT, 'show', f'HEAD:{rel}'],
                           capture_output=True)
        if r.returncode != 0:
            bad.append(f'{rel}: not in HEAD')
            continue
        got = hashlib.sha256(r.stdout).hexdigest()
        if got != want:
            bad.append(f'{rel}: COMMITTED CHANGE ({got[:12]} != {want[:12]}) -- v1 is frozen')
    return bad


def build():
    files = {}
    for dp, _, fs in os.walk(DRAFT):
        for f in sorted(fs):
            if f.endswith(('.tex', '.bib', '.pdf', '.md', '.png', '.pdf')):
                p = os.path.join(dp, f)
                files[os.path.relpath(p, ROOT)] = sha(p)
    return {'schema': 'catosg-v2-publication/1',
            'why': 'The manuscript versions independently of the experiment. V2_CLOSEOUT.json fixes '
                   'the experiment and does not move; this file moves with the paper.',
            'experiment_closeout': sha(os.path.join(ROOT, 'results/manifests/V2_CLOSEOUT.json')),
            'v1_freeze_verified': True, 'files': files, 'n_files': len(files)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    b = v1_breaches()
    if b:
        print('V2 PUBLICATION FAIL: the v1 freeze is breached:')
        for x in b:
            print('  ' + x)
        return 1
    m = build()
    if a.check:
        if not os.path.exists(OUT):
            print('V2 PUBLICATION FAIL: no manifest'); return 1
        old = json.load(open(OUT))
        moved = [k for k, v in m['files'].items() if old['files'].get(k) != v]
        gone = [k for k in old['files'] if k not in m['files']]
        print(f'v2 publication: {m["n_files"]} draft file(s); v1 freeze witness intact')
        if moved or gone:
            print(f'  {len(moved)} changed, {len(gone)} removed since the manifest -- re-run the '
                  f'generator if this is intended')
            return 1
        print('V2 PUBLICATION PASS')
        return 0
    json.dump(m, open(OUT, 'w'), indent=1)
    print(f'wrote {os.path.relpath(OUT, ROOT)}: {m["n_files"]} files; v1 freeze verified intact')
    return 0


if __name__ == '__main__':
    sys.exit(main())
