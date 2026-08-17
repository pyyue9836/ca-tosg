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
# Tier, re-derived from MEASURED dependencies (P0-4), not from how each gate was labelled when it
# was written. A gate was run with `torch`, `spconv` and `sionna` replaced by import-raising stubs;
# the local-artefact column was read off each file's own references.
#
#   'content'   -- no torch/spconv AND no git-excluded artefact: runs on a clean clone
#   'artifacts' -- needs torch (frozen .pt/.pkl models) or the git-excluded data/p2 + OpenCOOD caches
#
# What moved and why:
#   bandit fold scaling   content -> artifacts   loads data/p2/p4a_bandit_B0XX.pt, so it needs torch
#   payload chain         content -> artifacts   no torch, but it reads the sibling OpenCOOD
#                                                checkout (dataset_validate_v3.csv + a hypes yaml)
#   data leakage, manifest  stay artifacts       both read data/p2 + the OpenCOOD cue CSVs
#   assumptions ledger    content                its artefact references are STRINGS it scans for,
#                                                not files it opens
GATES = [
    ('artifacts', 'payload chain',        [PY, 'tests/test_payload.py']),
    ('content',   'paragraph insertion',  [PY, 'tests/test_paragraph_insert.py', '1', '2', '3']),
    ('content',   'claims vs main.tex',   [PY, 'tests/test_result_consistency.py', '--check']),
    ('artifacts', 'data leakage + freeze',[PY, 'tests/test_data_leakage.py']),
    ('artifacts', 'manifest relpaths',    [PY, 'tests/test_manifest.py']),
    ('artifacts', 'bandit fold scaling',  [PY, 'tests/test_bandit_fold_scaling.py']),
    ('content',   'P3 SNR support',       [PY, 'tests/test_p3_snr_support.py']),
    ('content',   'intra-repo imports',   [PY, 'tests/test_intra_repo_imports.py']),
    ('content',   'action-set wording',   [PY, 'tests/test_action_set_wording.py']),
    ('artifacts', 'numeric literals',     [PY, 'tests/test_numeric_literals.py']),
    ('content',   'canonical quantities', [PY, 'tests/test_canonical_quantities.py']),
    ('content',   'assumptions ledger',   [PY, 'tests/test_assumptions_ledger.py']),
]


# R20 9c: the fingerprint sweep covers the reader-facing docs too. It read main.tex only, so a
# retired number could (and did) survive in README and docs/ with every gate green.
FINGERPRINT_TARGETS = ('paper/main.tex', 'README.md', 'docs/model_zoo.md',
                       'docs/milestone_summary.md')
# NOT swept, by design: docs/p0_corrigendum.md and docs/canonical_quantities.md exist to record what
# the retired values WERE (old-vs-new tables, "which side flipped"), so a retired number is correct
# content there. Sweeping them would force the record to delete its own evidence.


def block_exit():
    """Retired fingerprints must not reappear in the paper or the reader-facing docs."""
    pats = [l[3:].strip() for l in open(os.path.join(ROOT, 'tests/stale_fingerprints.md'),
                                        encoding='utf-8') if l.startswith('RX ')]
    n = 0
    for rel in FINGERPRINT_TARGETS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        body = open(path, encoding='utf-8').read()
        for p in pats:
            # A retired VALUE is that value, not a prefix of a longer one. Without this, patterns
            # written for main.tex's 3-4 decimal prose fire on generated tables that print 5 --
            # 0.888 matched a per-class F1 of 0.8883, 0.081 matched a payload of 0.08102. This is the
            # same anchoring failure as the 0.248 / 27.5 / 18.4 / 0.895 collisions, fixed once here
            # instead of pattern by pattern.
            for m in re.finditer(p, body):
                tail = body[m.end():m.end() + 1]
                if tail.isdigit():
                    continue
                print('  STALE FINGERPRINT PRESENT in %s: %s' % (rel, p))
                n += 1
                break
    return n


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
    tier_note = (' (content tier only -- %d artefact-tier gates not run)'
                 % sum(1 for t, _n, _c in GATES if t != 'content')) if content_only else ''
    print('\n%s%s' % ('ALL GATES PASS' if rc == 0 else 'GATE FAILURE', tier_note))
    sys.exit(rc)
