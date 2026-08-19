#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R48-5: re-derive `payload_anchor_sensitivity.csv` from its own inputs, cell by cell.

The anchor sensitivity is now load-bearing: the paper quotes three share ranges from it and rests an
ordering claim on it. Nothing checked it. Worse, its generator (`tools/second_payload_and_bler.py`)
had silently broken once already, by parsing a sentence `main.tex` no longer contained — a product
can be stale for a whole batch and look fine, because a CSV never announces that it is old.

Three things are re-derived here, all from committed inputs and none from the generator:

  1. the action mix (`rho_E`, `rho_L`, `rho_F`) against the frozen decision logs;
  2. `policy_msym`, recomputed as `rho_L * B_L + rho_F * B_F` from the row's own mix and `B_F`,
     and `policy_over_fixedF` as the ratio of that to `B_F`;
  3. each anchor's `B_F`: the deployed conventions against `payload_conventions.csv`, the declared
     anchor against `main.tex`'s Eq.(7) value, the 1-bit counterfactual against the reference
     geometry.

    python tools/check_anchor_sensitivity.py [--check]
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENS = os.path.join(ROOT, 'results/channel/payload_anchor_sensitivity.csv')
CONV = os.path.join(ROOT, 'results/channel/payload_conventions.csv')
MAIN = os.path.join(ROOT, 'paper/main.tex')
LOG = os.path.join(ROOT, 'results/main/r10c_decision_log_{split}_B{b}.csv')
TOL = 5e-6


def declared_b_f():
    tex = open(MAIN, encoding='utf-8').read()
    return float(re.search(r'B_\{C_\{16\}\} \\approx ([0-9.]+)\$~Msym', tex).group(1))


def declared_b_l():
    tex = open(MAIN, encoding='utf-8').read()
    return float(re.search(r'B_L = ([0-9.]+)\$~Msym', tex).group(1))


def reference_elements():
    tex = open(MAIN, encoding='utf-8').read()
    m = re.search(r'\$?(\d+) \\times (\d+) \\times (\d+) \\approx 2\.16', tex)
    return int(m.group(1)) * int(m.group(2)) * int(m.group(3))


def expected_b_f():
    """{anchor: B_F in Msym}, each from the product that owns it."""
    conv = pd.read_csv(CONV)
    pp = conv[conv.backbone == 'pointpillar'].set_index('convention')
    declared = declared_b_f()
    source_mbit = float(re.search(r'fixed source budget of \$B_C \\approx ([0-9.]+)\$~Mbit',
                                  open(MAIN, encoding='utf-8').read()).group(1))
    one_bit_mbit = reference_elements() / 1e6
    return {
        'declared_anchor': declared,
        'reanchor_1bit_per_element': declared * one_bit_mbit / source_mbit,
        'deployed_precompression_tensor': float(pp.loc['pre_compression', 'B_F_msym_16qam']),
        'transmitted_bottleneck': float(pp.loc['transmitted_bottleneck', 'B_F_msym_16qam']),
    }


def log_mix(split, budget):
    """(rho_E, rho_L, rho_F) from the frozen decision log.

    Raises rather than returning None: the first draft silently skipped every row, because the
    sensitivity CSV stores the budget as 10/20/30 while the logs are named B010/B020/B030, and a
    check that skips is a check that passes for the wrong reason (it printed "0 rows
    cross-checked" and PASS).
    """
    b = float(budget)
    tag = f'{int(round(b)):03d}' if b >= 1 else f'{int(round(b * 100)):03d}'
    p = LOG.format(split=split, b=tag)
    if not os.path.exists(p):
        raise SystemExit(f'ANCHOR SENSITIVITY CHECK FUSE: no frozen decision log at '
                         f'{os.path.relpath(p, ROOT)} for {split}/{budget}')
    d = pd.read_csv(p)
    col = next((c for c in ('rf', 'action', 'mode', 'choice') if c in d.columns), None)
    if col is None:
        raise SystemExit(f'ANCHOR SENSITIVITY CHECK FUSE: {os.path.relpath(p, ROOT)} carries no '
                         f'action column (looked for rf/action/mode/choice)')
    a = d[col]
    if a.dtype == object:
        a = a.map({'E': 0, 'L': 1, 'F': 2, 'C': 2, 'C16': 2})
        if a.isna().any():
            raise SystemExit(f'ANCHOR SENSITIVITY CHECK FUSE: unmapped action labels in '
                             f'{os.path.relpath(p, ROOT)}')
        a = a.astype(int)
    n = len(a)
    return (float((a == 0).sum()) / n, float((a == 1).sum()) / n, float((a == 2).sum()) / n)


def main() -> int:
    if not os.path.exists(SENS):
        print(f'ANCHOR SENSITIVITY CHECK FAIL: {os.path.relpath(SENS, ROOT)} is missing')
        return 1
    d = pd.read_csv(SENS)
    want = expected_b_f()
    bad, checked, mix_checked = [], 0, 0

    names = set(d.anchor.unique())
    if names != set(want):
        bad.append(f'anchor names {sorted(names)} != the conventions this check knows '
                   f'{sorted(want)} -- a renamed or added convention must be registered here')

    for _, r in d.iterrows():
        checked += 1
        if r.anchor in want and abs(float(r.B_F_msym) - want[r.anchor]) > TOL:
            bad.append(f'{r.split}/{r.budget}/{r.anchor}: B_F {r.B_F_msym} != '
                       f'{want[r.anchor]:.6f} from its own product')
        pay = float(r.rho_L) * declared_b_l() + float(r.rho_F) * float(r.B_F_msym)
        if abs(pay - float(r.policy_msym)) > TOL:
            bad.append(f'{r.split}/{r.budget}/{r.anchor}: policy_msym {r.policy_msym} != '
                       f'rho_L*B_L + rho_F*B_F = {pay:.6f}')
        if abs(float(r.policy_msym) / float(r.B_F_msym) - float(r.policy_over_fixedF)) > TOL:
            bad.append(f'{r.split}/{r.budget}/{r.anchor}: policy_over_fixedF disagrees with '
                       f'policy_msym / B_F')
        if abs(float(r.rho_E) + float(r.rho_L) + float(r.rho_F) - 1.0) > 1e-6:
            bad.append(f'{r.split}/{r.budget}: the action mix does not sum to 1')
        mix = log_mix(r.split, float(r.budget))
        if mix is not None:
            mix_checked += 1
            for name, got, exp in (('rho_E', r.rho_E, mix[0]), ('rho_L', r.rho_L, mix[1]),
                                   ('rho_F', r.rho_F, mix[2])):
                if abs(float(got) - exp) > 1e-6:
                    bad.append(f'{r.split}/{r.budget}: {name} {got} != {exp:.6f} in the frozen '
                               f'decision log')

    print(f'anchor sensitivity: {checked} row(s) re-derived, {len(names)} conventions, '
          f'{mix_checked} row(s) cross-checked against the frozen decision logs')
    for b in bad[:12]:
        print(f'  MISMATCH: {b}')
    if bad:
        print(f'ANCHOR SENSITIVITY CHECK FAIL: {len(bad)} disagreement(s) with the committed '
              'inputs -- re-run: python tools/second_payload_and_bler.py (R48-5)')
        return 1
    print('ANCHOR SENSITIVITY CHECK PASS: every B_F matches its product, every payload recomputes, '
          'and the action mix matches the frozen decision logs.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
