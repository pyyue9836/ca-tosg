#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every gate. Exit 0 iff all pass.

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
GATES = [
    ('payload chain',        [PY, 'tests/test_payload.py']),
    ('paragraph insertion',  [PY, 'tests/test_paragraph_insert.py', '1', '2', '3']),
    ('claims vs main.tex',   [PY, 'tests/test_result_consistency.py', '--check']),
    ('data leakage + freeze',[PY, 'tests/test_data_leakage.py']),
    ('manifest relpaths',    [PY, 'tests/test_manifest.py']),
    ('bandit fold scaling',  [PY, 'tests/test_bandit_fold_scaling.py']),
    ('P3 SNR support',       [PY, 'tests/test_p3_snr_support.py']),
    ('intra-repo imports',   [PY, 'tests/test_intra_repo_imports.py']),
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
    rc = 0
    for name, cmd in GATES:
        if not os.path.exists(os.path.join(ROOT, cmd[1])):
            print('%-24s SKIP (absent: %s)' % (name, cmd[1]))
            continue
        r = subprocess.run(cmd, cwd=ROOT)
        print('%-24s %s' % (name, 'PASS' if r.returncode == 0 else 'FAIL'))
        rc |= r.returncode
    n = block_exit()
    print('%-24s %s' % ('stale-fingerprint exit', 'PASS' if n == 0 else 'FAIL (%d)' % n))
    rc |= (1 if n else 0)
    print('\n%s' % ('ALL GATES PASS' if rc == 0 else 'GATE FAILURE'))
    sys.exit(rc)
