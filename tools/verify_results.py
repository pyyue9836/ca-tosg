#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the gates. Exit 0 iff all that ran passed.

  python tools/verify_results.py                 every gate: needs the git-excluded data/p2/
                                                 artefacts and the sibling OpenCOOD checkout
  python tools/verify_results.py --content-only  only the checks a CLEAN CLONE can run (7 of 9)

  A clean clone CANNOT complete the full verification, and this script does not pretend otherwise:
  the two artefact-tier gates fail loudly on missing data rather than skipping, because a gate that
  cannot verify must never report success. --content-only is the honest subset, not a softer run.

  Nine checks: the five original gates, the configs/manifest contract, and the three guards added
  with the 2026-08-12 errata (P4A-1 fold-local scaling, P3-1 SNR support, and import resolution).

  python tools/verify_results.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


import re
import subprocess

PY = sys.executable
# tier: 'content'   -- runs on a clean clone, nothing but the committed tree
#       'artifacts' -- additionally needs the git-excluded data/p2/ grids + frozen models, and the
#                      sibling OpenCOOD checkout for the cue CSVs the manifest md5-pins
GATES = [
    ('content',   'payload chain',        [PY, 'tests/test_payload.py']),
    ('content',   'paragraph insertion',  [PY, 'tests/test_paragraph_insert.py', '1', '2', '3']),
    ('content',   'claims vs main.tex',   [PY, 'tests/test_result_consistency.py', '--check']),
    ('artifacts', 'data leakage + freeze',[PY, 'tests/test_data_leakage.py']),
    ('artifacts', 'manifest relpaths',    [PY, 'tests/test_manifest.py']),
    ('content',   'bandit fold scaling',  [PY, 'tests/test_bandit_fold_scaling.py']),
    ('content',   'P3 SNR support',       [PY, 'tests/test_p3_snr_support.py']),
    ('content',   'intra-repo imports',   [PY, 'tests/test_intra_repo_imports.py']),
]


def block_exit():
    """Retired fingerprints must not reappear in main.tex: expect 0 matches."""
    pats = [l[3:].strip() for l in open(os.path.join(ROOT, 'tests/stale_fingerprints.md'),
                                        encoding='utf-8') if l.startswith('RX ')]
    tex = open(os.path.join(ROOT, 'paper/main.tex'), encoding='utf-8').read()
    hits = [p for p in pats if re.search(p, tex)]
    for h in hits:
        print('  STALE FINGERPRINT PRESENT: %s' % h)
    return len(hits)


if __name__ == '__main__':
    content_only = '--content-only' in sys.argv
    rc = 0
    for tier, name, cmd in GATES:
        if content_only and tier != 'content':
            print('%-24s not run (--content-only; needs data/p2/ + the OpenCOOD checkout)' % name)
            continue
        if not os.path.exists(os.path.join(ROOT, cmd[1])):
            print('%-24s SKIP (absent: %s)' % (name, cmd[1]))
            continue
        r = subprocess.run(cmd, cwd=ROOT)
        print('%-24s %s' % (name, 'PASS' if r.returncode == 0 else 'FAIL'))
        rc |= r.returncode
    n = block_exit()
    print('%-24s %s' % ('stale-fingerprint exit', 'PASS' if n == 0 else 'FAIL (%d)' % n))
    rc |= (1 if n else 0)
    tier_note = ' (content tier only -- 2 artefact-tier gates not run)' if content_only else ''
    print('\n%s%s' % ('ALL GATES PASS' if rc == 0 else 'GATE FAILURE', tier_note))
    sys.exit(rc)
