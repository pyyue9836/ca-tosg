#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate (R25-6): every explicit comparison in the text is evaluated against the canonical products.

The fingerprint sweep catches a retired *value*; the literal-coverage gate catches an *unbound*
value. Neither catches a sentence whose numbers are all correct and whose **direction** is wrong.
Three such sentences survived every gate until a human read them:

  * `sec:threshold` said the selector was "ahead of a threshold ... at $B_{\\max}=0.10$", when on
    test the nominal threshold is ahead at that budget (0.89247 vs 0.89148) -- and at all three;
  * the Conclusion repeated it as "ahead of it at the tightest budget";
  * `sec:threshold` also said the channel-only variant "does reach a higher F1 than the full
    selector" at `B_max=0.30`, contradicting `sec:ablation` two sections earlier, which says it is
    beaten on both axes (0.89529 vs 0.89783). The same fact, two directions.

This gate reads a table of (entity A, entity B, direction, metric, condition) tuples extracted from
the delivered text, looks each quantity up in the canonical product that owns it, and fails when the
claimed direction disagrees with the data. The tuples live in `tests/comparison_claims.md` so that
adding a comparison to the paper means adding a checkable row, not editing code.

    python tests/test_comparison_direction.py [--self-test]
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAIMS = os.path.join(ROOT, 'tests', 'comparison_claims.md')
TEX = os.path.join(ROOT, 'paper', 'main.tex')

# how a policy name resolves to (csv, row filter, column) -- all canonical products
SOURCES = {
    'RF': ('results/main/replay_summary.csv', 'F1_RF', 'B_RF'),
    'tau_nominal': ('results/main/replay_summary.csv', 'F1_tau', 'B_tau'),
    'tau_feasible': ('results/main/tau_feasible.csv', 'F1_tau_feasible', 'B_tau_feasible'),
    'channel_only': ('results/sensitivity/feature_ablation.csv', 'F1', 'payload'),
    'combined': ('results/sensitivity/feature_ablation.csv', 'F1', 'payload'),
    'hand_rule_3': ('results/baselines/two_gate_dgate.csv', 'F1_2G', 'B_2G'),
    'hand_rule_2': ('results/baselines/two_gate.csv', 'F1_2G', 'B_2G'),
    # R53-4: the common-volume diagnostic track. Its rows key on policy, and the paper's new
    # sentence asserts a SIGN CHANGE on test -- the ceiling below Fixed L inside a shared field of
    # view -- which is exactly the kind of claim that silently inverts when a table is regenerated.
    'ceiling_common_volume': ('results/diagnostics/common_volume_ap.csv',
                              'ap50_mean_crop', 'ap70_mean_crop'),
    # R57-4: the external arm's descriptive cells, on the intersection-GT track. Five of six favour
    # Where2comm and one does not; the reversed cell gets its own row so a regenerated table cannot
    # quietly align the sign pattern.
    'w2c_isect': ('results/diagnostics/intersection_gt_track.csv', 'ap50', 'ap70'),
    'catosg_isect': ('results/diagnostics/intersection_gt_track.csv', 'ap50', 'ap70'),
    'fixedL_common_volume': ('results/diagnostics/common_volume_ap.csv',
                             'ap50_mean_crop', 'ap70_mean_crop'),
}
# rows of the diagnostic track are selected by policy name, not by a `variant` column
POLICY_OF = {'ceiling_common_volume': 'Feature-ceiling', 'fixedL_common_volume': 'Fixed-L',
             'w2c_isect': 'Where2comm', 'catosg_isect': 'CA-TOSG'}
METRIC_COL = {'F1': 0, 'payload': 1}


def value(entity, metric, split, budget):
    rel, f1col, bcol = SOURCES[entity]
    d = pd.read_csv(os.path.join(ROOT, rel))
    if 'variant' in d.columns:                       # the ablation table keys on the variant name
        d = d[d.variant == entity]
    if entity in POLICY_OF:                          # R53-4: diagnostic track, keyed on policy
        want = POLICY_OF[entity]
        d = d[(d.policy.str.startswith(want)) & (d.split == split)]
        if entity.endswith('_isect'):                # R57-4: the arm has two descriptive budgets
            # compare numerically: pandas reads "0.10" as 0.1, so a string compare silently
            # matches nothing and the FUSE fires on a well-formed table
            d = d[d.budget.astype(float).round(2) == round(budget, 2)]
        if len(d) != 1:
            raise SystemExit(f'comparison gate FUSE: {entity} @ {split} matched {len(d)} rows '
                             f'in {rel}')
        return float(d[[f1col, bcol][METRIC_COL[metric]]].iloc[0])
    d = d[(d.split == split) & (d.budget.round(2) == round(budget, 2))]
    if len(d) != 1:
        raise SystemExit(f'comparison gate FUSE: {entity} @ {split}/{budget} matched {len(d)} rows '
                         f'in {rel}')
    return float(d[[f1col, bcol][METRIC_COL[metric]]].iloc[0])


def rows():
    """(label, A, B, direction, metric, split, budget, sentence-probe) from the claims table."""
    out = []
    for line in open(CLAIMS, encoding='utf-8'):
        if not line.startswith('|') or line.startswith('|---') or line.startswith('| label'):
            continue
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) != 8:
            continue
        label, a, b, direction, metric, split, budget, probe = c
        out.append((label, a, b, direction, metric, split, float(budget), probe.strip('`')))
    return out


def evaluate(a_val, direction, b_val):
    if direction == '>':
        return a_val > b_val
    if direction == '<':
        return a_val < b_val
    if direction == '~':                              # parity: within 0.0005 on the quantity
        return abs(a_val - b_val) < 5e-4
    raise SystemExit(f'comparison gate FUSE: unknown direction {direction!r}')


def check(tex, verbose=False):
    bad = []
    for label, a, b, direction, metric, split, budget, probe in rows():
        av, bv = value(a, metric, split, budget), value(b, metric, split, budget)
        ok = evaluate(av, direction, bv)
        present = probe in tex if probe else True
        if verbose:
            print(f'  {"PASS" if ok else "FAIL"}  {label}: {a}={av:.5f} {direction} {b}={bv:.5f} '
                  f'({metric}, {split} @ {budget})' + ('' if present else '  [probe ABSENT]'))
        if not ok:
            bad.append((label, a, av, direction, b, bv, metric, split, budget))
        elif probe and not present:
            bad.append((label + ' [probe]', a, av, 'probe absent from main.tex', b, bv,
                        metric, split, budget))
    return bad


def abstract_span(tex):
    """The abstract's character span, or None."""
    i = tex.find(r'\begin{abstract}')
    j = tex.find(r'\end{abstract}')
    return (i, j) if 0 <= i < j else None


def abstract_in_scope(tex):
    """R26-4: at least one registered comparison must be probed INSIDE the abstract.

    The abstract is where "On test there is therefore effectively nothing to contest" survived: it
    carries comparative claims, it is prose rather than a table, and nothing pointed a direction
    check at it. Making its coverage an assertion is what stops that recurring.
    """
    span = abstract_span(tex)
    if span is None:
        return ['no abstract found in main.tex -- the scope assertion cannot run']
    lo, hi = span
    inside = [r for r in rows() if r[7] and lo <= tex.find(r[7]) < hi]
    if not inside:
        return ['no registered comparison is probed inside the abstract (R26-4)']
    return []


def delivered():
    """main.tex plus supplementary.tex (R40)."""
    parts = [open(TEX, encoding='utf-8').read()]
    supp = os.path.join(os.path.dirname(TEX), 'supplementary.tex')
    if os.path.exists(supp):
        parts.append(open(supp, encoding='utf-8').read())
    return '\n'.join(parts)


def main():
    tex = delivered()
    if '--self-test' in sys.argv:
        # the regression cases: the three directions this batch corrected must FAIL when flipped
        controls = [('R25 flip 1', 'RF', 'tau_nominal', '>', 'F1', 'test', 0.10),
                    ('R25 flip 2', 'RF', 'tau_nominal', '>', 'F1', 'test', 0.20),
                    ('R25 flip 3', 'channel_only', 'combined', '>', 'F1', 'test', 0.30)]
        fired = 0
        for label, a, b, d, m, sp, bu in controls:
            av, bv = value(a, m, sp, bu), value(b, m, sp, bu)
            if not evaluate(av, d, bv):
                fired += 1
            print(f'SELF-TEST {label}: "{a} {d} {b}" -> '
                  f'{"FIRES" if not evaluate(av, d, bv) else "DOES NOT FIRE"} '
                  f'({av:.5f} vs {bv:.5f})')
        live = check(tex)
        print(f'SELF-TEST: the live table -> {len(live)} failure(s) (expected 0)')
        scope_ok = not abstract_in_scope(tex)
        print('SELF-TEST: abstract scope assertion -> %s'
              % ('covered' if scope_ok else 'NOT COVERED'))
        no_abs = abstract_in_scope(tex.replace(r'\begin{abstract}', r'\begin{gone}'))
        print('SELF-TEST: with the abstract removed -> %s'
              % ('FIRES' if no_abs else 'DOES NOT FIRE'))
        return 0 if (fired == len(controls) and not live and scope_ok and no_abs) else 1
    bad = check(tex, verbose='--verbose' in sys.argv)
    scope = abstract_in_scope(tex)
    for msg in scope:
        print(f'  SCOPE: {msg}')
    lo_hi = abstract_span(tex)
    n_abs = (len([r for r in rows() if r[7] and lo_hi and lo_hi[0] <= tex.find(r[7]) < lo_hi[1]])
             if lo_hi else 0)
    print(f'comparison direction: {len(rows())} claims evaluated against the canonical products '
          f'({n_abs} of them probed inside the abstract)')
    for label, a, av, direction, b, bv, metric, split, budget in bad:
        print(f'  WRONG DIRECTION [{label}]: the text says {a} {direction} {b} on {metric} '
              f'({split} @ B_max={budget}), the data says {a}={av:.5f}, {b}={bv:.5f}')
    if bad or scope:
        print(f'COMPARISON GATE FAIL: {len(bad)} claimed direction(s) disagree with the data, '
              f'{len(scope)} scope failure(s) (R25-6 / R26-4)')
        return 1
    print('COMPARISON GATE PASS: every registered comparison agrees with the canonical products.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
