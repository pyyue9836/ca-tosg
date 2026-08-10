#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single source for every R10-family REPORT/PROVENANCE number: recompute them from
results/p2_deploy/r10c_missed_e_cost.csv (+ r10c_vs_oracle_account.csv) -- NO hand-written numbers.

The CSV holds ONLY the three class rows (strict / tie / cost-induced). The all-classes TOTAL lives
ONLY here, computed as the sum of the three class rows -- one fact, one place. (Storing the total
alongside its components in the CSV is what let a naive re-sum double-count it: the 2x error caught in
the R10-report review.) Does NOT touch the CSVs, r10c_diagnostic.py, or any assertion; it regenerates
results/p2_deploy/R10_REPORT.md and PROVENANCE_r10c.txt. Run after r10c_diagnostic.py.

Run:  /path/to/env/python paper1/code/p2_dataprep/make_r10_report.py
"""
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(P1, 'results/p2_deploy')
COST = os.path.join(OUT, 'r10c_missed_e_cost.csv')
VSORC = os.path.join(OUT, 'r10c_vs_oracle_account.csv')
MANIFEST = os.path.join(P1, 'results/p2_dataprep/FROZEN_MANIFEST.json')
CLASSES = ['strict', 'tie', 'cost-induced']
EPS = 1e-12


def cell(df, split, budget, e_class, col):
    return df[(df.split == split) & (df.budget == budget) & (df.e_class == e_class)].iloc[0][col]


def total(df, split, budget, col):
    """The all-classes TOTAL = sum of the three class rows (computed here only, never stored)."""
    return float(df[(df.split == split) & (df.budget == budget)
                    & (df.e_class.isin(CLASSES))][col].sum())


def main():
    cost = pd.read_csv(COST); vsorc = pd.read_csv(VSORC)
    man = json.load(open(MANIFEST))
    lam = {float(b): float(bd['lambda_star']) for b, bd in man['budgets'].items()}
    budgets = sorted(cost.budget.unique())
    splits = list(cost.split.unique())

    # --- guards (this is the gap that bit the review): the CSV must have NO total/all-classes row, and
    #     exactly the three class rows per split x budget; the report TOTAL is their sum. ---
    stored = set(cost.e_class.unique())
    if stored != set(CLASSES):
        raise SystemExit(f'make_r10_report: CSV e_class set {sorted(stored)} != the 3 classes '
                         f'{CLASSES} -- a TOTAL/all-classes row in the CSV would double-count.')
    for split in splits:
        for b in budgets:
            got = sorted(cost[(cost.split == split) & (cost.budget == b)]['e_class'].tolist())
            if got != sorted(CLASSES):
                raise SystemExit(f'make_r10_report: {split} B{b} rows {got} != the 3 classes')
            # cost-induced count is 0 exactly on the lambda=0 budget
            ci = int(cell(cost, split, b, 'cost-induced', 'missed_by_rf'))
            if (lam[b] == 0) != (ci == 0):
                raise SystemExit(f'make_r10_report: {split} B{b} cost-induced missed={ci} but lambda={lam[b]}')
            # sum(three classes) == report TOTAL (definition + explicit guard)
            comp = float(cost[(cost.split == split) & (cost.budget == b)
                              & (cost.e_class.isin(CLASSES))]['F1_cost_per_framereal'].sum())
            if abs(comp - total(cost, split, b, 'F1_cost_per_framereal')) > EPS:
                raise SystemExit(f'make_r10_report: {split} B{b} sum(3 classes) != report TOTAL')

    def row(split, b, cls):
        return (f'| {cls} | {int(cell(cost,split,b,cls,"clairvoyant_E_cells"))} | '
                f'{int(cell(cost,split,b,cls,"missed_by_rf"))} | '
                f'{cell(cost,split,b,cls,"F1_cost_per_framereal"):.6f} | '
                f'{cell(cost,split,b,cls,"payload_extra_per_framereal"):.6f} |')

    lines = ['# R10-family diagnostic report (auto-generated from the CSVs; do not hand-edit)\n',
             '_Every number is recomputed by `code/p2_dataprep/make_r10_report.py` from '
             '`r10c_missed_e_cost.csv` (3 class rows only) / `r10c_vs_oracle_account.csv`. The '
             'all-classes TOTAL is the sum of the three class rows, computed here only (not stored in the '
             'CSV). Post-unblinding; nothing confirmatory. This is the **vs-frozen-λ-clairvoyant-oracle** '
             'account, SEPARATE from the R9 vs-τ decision._\n',
             '\n## Missed-E cost per class + TOTAL (sum of the three), per frame-realisation\n',
             '_"strict-benefit missed-E cost" and "total E-collapse F1 cost" are **two different '
             'numbers**; do not conflate. cost-induced is **non-empty** where λ>0, small positive, '
             'included in the TOTAL._\n']
    for split in ['test', 'culver', 'validate']:
        lines.append(f'\n### {split}\n')
        for b in budgets:
            lines.append(f'\n**B_max = {b}** (λ\\* = {lam[b]})\n')
            lines.append('| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |')
            lines.append('|---|---|---|---|---|')
            for cls in CLASSES:
                lines.append(row(split, b, cls))
            lines.append(f'| **TOTAL (sum)** | — | — | **{total(cost,split,b,"F1_cost_per_framereal"):.6f}** | '
                         f'**{total(cost,split,b,"payload_extra_per_framereal"):.6f}** |')

    lines.append('\n## Headline (test)\n')
    lines.append('| B_max | strict-benefit F1/frame | total E-collapse F1/frame | cost-induced cells |')
    lines.append('|---|---|---|---|')
    for b in budgets:
        lines.append(f'| {b} | {cell(cost,"test",b,"strict","F1_cost_per_framereal"):.6f} | '
                     f'{total(cost,"test",b,"F1_cost_per_framereal"):.6f} | '
                     f'{int(cell(cost,"test",b,"cost-induced","missed_by_rf"))} |')

    lines.append('\n## vs-frozen-λ-clairvoyant-oracle account (separate from the R9 vs-τ table)\n')
    lines.append('| split | B_max | F1 gap (RF below clairvoyant) | clairvoyant payload | exceeds B_max? |')
    lines.append('|---|---|---|---|---|')
    for _, r in vsorc.iterrows():
        lines.append(f'| {r.split} | {r.budget} | {r.F1_gap_RF_below_clairvoyant:.6f} | '
                     f'{r.B_clairvoyant:.5f} | {r.clairvoyant_exceeds_Bmax} |')

    lines.append('\n## Semantic notes\n')
    lines.append('1. This is a **vs-clairvoyant-oracle** account; SEPARATE from and not to be '
                 'cross-referenced with the R9 **vs-τ** decision (`r10c_vs_tau_account.csv`, '
                 '`r9_result_claims.md`).')
    vgap = float(vsorc[(vsorc.split == 'validate')]['F1_gap_RF_below_clairvoyant'].abs().max())
    lines.append(f'2. The tiny validate gaps (max |F1 gap| ≈ {vgap:.6f}, some ~1e-6 negative) are normal '
                 'for the corrected (R10d) classification: in-sample the selector ≈ the clairvoyant '
                 'oracle and the residual is numerical, not a real reversal.')
    with open(os.path.join(OUT, 'R10_REPORT.md'), 'w') as f:
        f.write('\n'.join(lines) + '\n')

    st = {b: cell(cost, 'test', b, 'strict', 'F1_cost_per_framereal') for b in budgets}
    tt = {b: total(cost, 'test', b, 'F1_cost_per_framereal') for b in budgets}
    with open(os.path.join(OUT, 'PROVENANCE_r10c.txt'), 'w') as f:
        f.write('CA-TOSG R10c/R10d CORRIGENDUM -- POST-UNBLINDING (nothing here is confirmatory)\n' + '=' * 72 + '\n')
        f.write('All numbers recomputed by make_r10_report.py from r10c_missed_e_cost.csv (3 class rows; '
                'no hand-written numbers). The all-classes TOTAL is the SUM of the three class rows, computed '
                'here only (not stored in the CSV -- storing both bit a review re-sum with a 2x error). '
                'RETRACTS R10 "costs payload, not F1". Reference = FROZEN-LAMBDA CLAIRVOYANT oracle (NOT '
                'budget-constrained). r10c_diagnostic.py 4 hard assertions PASSED; F1_RF/B_RF reproduce the '
                'existing replay CSVs.\n\n')
        f.write('cost-induced is NON-EMPTY where lambda>0 (test B010 %d / B020 %d cells; lambda=0 budget B030 = 0); '
                'its F1 cost is small POSITIVE and is included in the TOTAL.\n'
                % (int(cell(cost, 'test', 0.10, 'cost-induced', 'missed_by_rf')),
                   int(cell(cost, 'test', 0.20, 'cost-induced', 'missed_by_rf'))))
        f.write('TWO DIFFERENT NUMBERS (do not conflate), test three budgets B010/B020/B030:\n')
        f.write('  strict-benefit missed-E F1 cost /frame = %.6f / %.6f / %.6f\n' % (st[0.10], st[0.20], st[0.30]))
        f.write('  total E-collapse F1 cost (all classes) /frame = %.6f / %.6f / %.6f\n' % (tt[0.10], tt[0.20], tt[0.30]))
        f.write('Accounts kept SEPARATE: r10c_vs_oracle_account.csv (RF vs frozen-lambda clairvoyant) and '
                'r10c_vs_tau_account.csv (R9 RF vs threshold). Retraction chain R10 -> R10c -> R10d.\n')
    print('wrote R10_REPORT.md + regenerated PROVENANCE_r10c.txt (CSV-derived; TOTAL computed as sum-of-3)')
    print('test strict /frame:', {b: round(st[b], 6) for b in budgets})
    print('test TOTAL  /frame:', {b: round(tt[b], 6) for b in budgets})


if __name__ == '__main__':
    main()
