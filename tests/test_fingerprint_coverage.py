#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R49 A-3/B-3 — the fingerprint sweep must cover every delivered document, and its
withdrawal exemption must fire on the affirmative claim and stay quiet on the retraction.

**Why this exists (B-2).** The ruled sentence

    "...not a demonstration that a learned selector beats simple rules---at equal budget it does not"

matches the retired-claim pattern `beats ... simple rule` word for word. It sat in the 4-page brief
for two rounds without ever firing -- not because the sweep judged it, but because the brief lived
at `paper/v2_draft/main.tex`, a path that was not on the target list. **A rule that has never been
run against the text it governs has not been verified.** It is the same family as "a gate that
cannot fail" with a different cause: those are self-consistent judgements, this is a hole in
coverage.

Two checks:

  1. **coverage** -- every delivered document is a fingerprint target. Adding a `.tex` under
     `paper/` without adding it to `FINGERPRINT_TARGETS` fails here.
  2. **the withdrawal exemption** -- three injections, per A-3.

  python tests/test_fingerprint_coverage.py [--self-test]
"""
from __future__ import annotations
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from verify_results import FINGERPRINT_TARGETS, is_withdrawal, block_exit   # noqa: E402

# Delivered text = every .tex under paper/ (the live manuscript and the archived documents), plus
# the reader-facing documents. Table bodies under paper/tables/ are excluded BY GENERATOR: they are
# rebuilt byte for byte by tools/build_v2_paper_numbers.py --check, which is a stronger guarantee
# than a literal sweep and cannot drift from its source.
GENERATED_DIRS = ('paper/tables',)
READER_FACING = ('README.md', 'docs/model_zoo.md', 'docs/milestone_summary.md')


def delivered():
    out = []
    for dp, _, fs in os.walk(os.path.join(ROOT, 'paper')):
        rel_dir = os.path.relpath(dp, ROOT).replace(os.sep, '/')
        if any(rel_dir == d or rel_dir.startswith(d + '/') for d in GENERATED_DIRS):
            continue
        for f in sorted(fs):
            if f.endswith('.tex'):
                out.append(os.path.join(rel_dir, f).replace(os.sep, '/'))
    return sorted(out) + [r for r in READER_FACING if os.path.exists(os.path.join(ROOT, r))]


def coverage(targets=None):
    targets = set(FINGERPRINT_TARGETS if targets is None else targets)
    return [d for d in delivered() if d not in targets]


def self_test():
    ok = True
    miss = coverage()
    print('  coverage: %d delivered document(s), %d uncovered' % (len(delivered()), len(miss)))
    for m in miss:
        print('    ' + m)
    ok &= not miss

    # B-3: drop one covered document from the list -- the check must notice
    dropped = sorted(set(FINGERPRINT_TARGETS) & set(delivered()))[0]
    fired = bool(coverage([t for t in FINGERPRINT_TARGETS if t != dropped]))
    print('  %s  %s removed from the target list' % ('FIRES ' if fired else 'SILENT', dropped))
    ok &= fired

    # A-3: the withdrawal exemption, three injections
    aff = 'CA-TOSG beats the hand rule on F1 at every budget.'
    i = aff.index('beats')
    e = is_withdrawal(aff, i)
    print('  %s  affirmative claim ("CA-TOSG beats the hand rule")' % ('FIRES ' if not e else 'EXEMPT'))
    ok &= not e

    withdrawal = ('The contribution is therefore a granularity-control framework, not a\n'
                  'demonstration that a learned selector beats simple rules---at equal budget it '
                  'does not.')
    i = withdrawal.index('beats')
    e = is_withdrawal(withdrawal, i)
    print('  %s  the ruled withdrawal sentence (must be exempt)' % ('quiet ' if e else 'FIRES '))
    ok &= e

    stripped = withdrawal.replace('not a\ndemonstration that', 'a demonstration that')
    i = stripped.index('beats')
    e = is_withdrawal(stripped, i)
    print('  %s  the same sentence with the negation deleted' % ('FIRES ' if not e else 'EXEMPT'))
    ok &= not e

    print('FINGERPRINT COVERAGE SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    miss = coverage()
    print('fingerprint coverage: %d delivered document(s) checked against %d target(s)'
          % (len(delivered()), len(FINGERPRINT_TARGETS)))
    if miss:
        print('\nFINGERPRINT COVERAGE GATE FAIL: delivered but never swept:')
        for m in miss:
            print('  ' + m)
        print('  add them to FINGERPRINT_TARGETS in tools/verify_results.py')
        return 1
    print('FINGERPRINT COVERAGE GATE PASS: every delivered document is on the sweep list.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
