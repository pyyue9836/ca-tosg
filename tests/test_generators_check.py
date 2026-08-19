#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate (R43-4): every generator runs its own substitutions in `--check` mode, and a pattern that
matches anything other than exactly once is a FAIL.

The failure this exists for has now happened twice. A generator owns a sentence or a table body
through a regex; someone edits the delivered text; the regex stops matching; the generator writes
nothing and says so only if you run it. R23-8 found one dead pattern that had been rewriting nothing
"on every run"; R41's compression of observation (iii) created another, and it survived a full
sixteen-gate suite because *no gate runs the generators*. The suite checked what the documents say,
never that the tools which own those sentences can still find them.

Each registered generator must therefore support `--check` with the same contract:

  * run every substitution it would run for real -- so `sub_once`/`splice` raise on a non-1 match;
  * write nothing;
  * exit 0 only if the delivered artefact already equals what the generator produces.

Adding a generator here is the price of a generator owning delivered text.

    python tests/test_generators_check.py [--self-test]
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

# (label, argv, what it owns)
GENERATORS = [
    ('build_paper_tables', ['tools/build_paper_tables.py', '--check'],
     'tab:headline, tab:headline_agg, tab:ablation, tab:gen_headline, observation (iii)'),
    ('build_r9_claims', ['tools/build_r9_claims.py', '--check'],
     'results/provenance/r9_result_claims.md (the locked R9 wording)'),
    ('build_readme_tables', ['tools/build_readme_tables.py', '--check'],
     "README.md's model-zoo table"),
    ('claims_ledger', ['tests/test_result_consistency.py', '--check'],
     'docs/claims.md'),
    # R44-4: reports the figure/caption/body three-way, and fails on the one row class that is a
    # defect rather than a reading -- a number the figures draw that nothing states.
    ('check_figure_consistency', ['tools/check_figure_consistency.py', '--check'],
     'docs/figure_text_consistency.md (and the drawn-but-never-stated set)'),
    # R45-5: the handoff's commit field is generated; --check fails when the recorded commit is not
    # an ancestor of HEAD, i.e. when the file describes a state the branch has left.
    ('build_handoff_header', ['tools/build_handoff_header.py', '--check'],
     "docs/HANDOFF.md's commit header"),
    # R46-4: how many gates exist, and how many a clean clone can run, are computed from the runner.
    ('build_gate_counts', ['tools/build_gate_counts.py', '--check'],
     'the gate counts in docs/reproducibility.md and verify_results.py'),
]


def run(argv):
    return subprocess.run([PY] + argv, cwd=ROOT, capture_output=True, text=True, timeout=900)


def self_test():
    """Inject the R41 fault -- unhook one owned sentence -- and require the gate to fire.

    The file is restored in `finally`, byte for byte, because a self-test that leaves the paper
    edited is worse than no self-test.
    """
    tex = os.path.join(ROOT, 'paper', 'main.tex')
    original = open(tex, encoding='utf-8').read()
    probe = '(iii) Channel-averaged, the selector spends'
    if probe not in original:
        print('SELF-TEST: probe sentence not found -- cannot inject the R41 fault')
        return 1
    try:
        open(tex, 'w', encoding='utf-8').write(
            original.replace(probe, '(iii) Channel-averaged it spends', 1))
        r = run(GENERATORS[0][1])
        fired = r.returncode != 0
        print('SELF-TEST: observation (iii) unhooked (the R41 fault) -> %s'
              % ('FIRES' if fired else 'DOES NOT FIRE'))
    finally:
        open(tex, 'w', encoding='utf-8').write(original)
    clean = run(GENERATORS[0][1]).returncode == 0
    print('SELF-TEST: restored text -> %s' % ('silent' if clean else 'FALSE POSITIVE'))
    return 0 if (fired and clean) else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    bad = []
    for label, argv, owns in GENERATORS:
        r = run(argv)
        ok = r.returncode == 0
        print(f'  {"PASS" if ok else "FAIL"}  {label}: {owns}')
        if not ok:
            tail = (r.stdout + r.stderr).strip().split('\n')[-1][:160]
            print(f'        {tail}')
            bad.append(label)
    print(f'generators: {len(GENERATORS)} checked in --check mode')
    if bad:
        print(f'GENERATOR GATE FAIL: {len(bad)} generator(s) cannot reproduce what they own '
              f'({", ".join(bad)}) -- a pattern stopped matching, or the artefact is stale (R43-4)')
        return 1
    print('GENERATOR GATE PASS: every generator matched its patterns exactly once and reproduces '
          'the delivered artefact.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
