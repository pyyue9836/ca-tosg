#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R47 B-1/B-4 — the publication manifest for the ONE official manuscript, plus the archive
freeze check.

Two things are versioned independently on purpose: `V2_CLOSEOUT.json` fixes the experiment and must
never move again, while the manuscript will iterate. Folding the paper's hashes into the close-out
would make every wording edit look like an experimental change.

**The archive freeze.** `docs/STOP_WORK_v1_freeze.md` (amendment V2-R47 A) moved the superseded
documents to `paper/archive/` with `git mv` and did not lower their protection by one step: the
three `.tex` files and the two `.pdf` files named in `V1_FREEZE_WITNESS.json` keep their ORIGINAL
SHA-256 values and are still compared against what is **committed**. A one-byte edit to any of them
fails this gate. `--self-test` injects exactly that byte and proves the check fires.

History: the previous manifest for the 4-page brief is kept verbatim at
`results/manifests/V2_PUBLICATION.json` and is no longer regenerated. Its files were moved by
V2-R47 A-1 (`paper/v2_draft/**` -> `paper/archive/`); see `docs/history/protocol_changelog.md`.

    python tools/build_publication_manifest.py [--check] [--self-test]
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', 'manifests', 'PUBLICATION.json')
WITNESS = os.path.join(ROOT, 'results', 'manifests', 'V1_FREEZE_WITNESS.json')
SUPERSEDED = 'results/manifests/V2_PUBLICATION.json'

# The one official manuscript. No version-suffixed directory appears here, by A-3.
LIVE = ('paper/main.tex', 'paper/supplementary.tex', 'paper/references.bib')
LIVE_DIRS = ('paper/figures', 'paper/tables')
EXT = ('.tex', '.bib', '.pdf', '.png', '.json')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def committed_sha(rel):
    """The blob as COMMITTED, not as it sits in the working tree.

    The freeze invariant is "nothing that changes an archived document gets committed". A
    working-tree comparison would fail inside the suite every time the compile gate rewrites a PDF
    -- a guaranteed false positive, which is worse than no gate -- and would MISS an edit that was
    committed and then restored locally. Checking the committed blob is the stricter of the two.
    """
    r = subprocess.run(['git', '-C', ROOT, 'show', f'HEAD:{rel}'], capture_output=True)
    return None if r.returncode != 0 else hashlib.sha256(r.stdout).hexdigest()


def archive_breaches(override=None):
    """Every witnessed archived document, against its ORIGINAL hash. `override` is for --self-test."""
    w = json.load(open(WITNESS))['files']
    bad = []
    for rel, want in sorted(w.items()):
        got = (override or {}).get(rel, committed_sha(rel))
        if got is None:
            bad.append(f'{rel}: not in HEAD -- an archived frozen document has been deleted or '
                       f'moved without updating the witness')
        elif got != want:
            bad.append(f'{rel}: COMMITTED CHANGE ({got[:12]} != {want[:12]}) -- archived documents '
                       f'are frozen (docs/STOP_WORK_v1_freeze.md, amendment V2-R47 A-2)')
    return bad, len(w)


def build():
    files = {}
    for rel in LIVE:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            files[rel] = sha(p)
    for d in LIVE_DIRS:
        for dp, _, fs in os.walk(os.path.join(ROOT, d)):
            for f in sorted(fs):
                if f.endswith(EXT):
                    p = os.path.join(dp, f)
                    files[os.path.relpath(p, ROOT)] = sha(p)
    return {'schema': 'catosg-publication/1',
            'why': 'The manuscript versions independently of the experiment. V2_CLOSEOUT.json fixes '
                   'the experiment and does not move; this file moves with the paper.',
            'supersedes': SUPERSEDED,
            'supersedes_note': 'the 4-page brief, archived unchanged as paper/archive/'
                               'results_brief.tex by V2-R47 A-1',
            'experiment_closeout': sha(os.path.join(ROOT, 'results/manifests/V2_CLOSEOUT.json')),
            'archive_freeze_verified': True,
            'files': dict(sorted(files.items())), 'n_files': len(files)}


def self_test():
    """A gate that cannot fail is worse than none (docs/gate_design_principles.md, rule 4)."""
    w = json.load(open(WITNESS))['files']
    rel = sorted(w)[0]
    ok = True
    clean, n = archive_breaches()
    print('SELF-TEST: %d witnessed archived documents, unmodified -> %s'
          % (n, 'PASS' if not clean else 'UNEXPECTED FAIL: %s' % clean))
    ok &= not clean
    # inject one flipped byte into the recomputed digest of one archived document
    bad, _ = archive_breaches(override={rel: 'f' * 64})
    fired = any(rel in b and 'COMMITTED CHANGE' in b for b in bad)
    print('SELF-TEST: one byte changed in %s -> %s' % (rel, 'FIRES' if fired else 'DOES NOT FIRE'))
    ok &= fired
    # a deleted archived document must fire too, not pass silently
    missing, _ = archive_breaches(override={rel: None})
    fired2 = any(rel in b and 'not in HEAD' in b for b in missing)
    print('SELF-TEST: %s deleted from HEAD -> %s' % (rel, 'FIRES' if fired2 else 'DOES NOT FIRE'))
    ok &= fired2
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    b, n = archive_breaches()
    if b:
        print('PUBLICATION FAIL: the archive freeze is breached:')
        for x in b:
            print('  ' + x)
        return 1
    m = build()
    if a.check:
        if not os.path.exists(OUT):
            print('PUBLICATION FAIL: no manifest -- run the generator'); return 1
        old = json.load(open(OUT))
        moved = [k for k, v in m['files'].items() if old['files'].get(k) != v]
        gone = [k for k in old['files'] if k not in m['files']]
        print(f'publication: {m["n_files"]} manuscript file(s); {n} archived documents frozen intact')
        if moved or gone:
            print(f'  {len(moved)} changed, {len(gone)} removed since the manifest -- re-run the '
                  f'generator if this is intended')
            for k in (moved + gone)[:10]:
                print('    ' + k)
            return 1
        print('PUBLICATION PASS')
        return 0
    json.dump(m, open(OUT, 'w'), indent=1)
    print(f'wrote {os.path.relpath(OUT, ROOT)}: {m["n_files"]} manuscript files; '
          f'{n} archived documents verified frozen')
    return 0


if __name__ == '__main__':
    sys.exit(main())
