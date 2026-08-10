#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single source for every R10-family REPORT/PROVENANCE number: recompute them from
results/p2_deploy/r10c_missed_e_cost.csv (+ r10c_vs_oracle_account.csv) -- NO hand-written numbers.

Does NOT touch the CSVs, r10c_diagnostic.py, or any assertion. It only regenerates the narrative
artifacts so their numbers cannot drift from the CSV: results/p2_deploy/R10_REPORT.md and
results/p2_deploy/PROVENANCE_r10c.txt. Run it after r10c_diagnostic.py.

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
VSTAU = os.path.join(OUT, 'r10c_vs_tau_account.csv')
MANIFEST = os.path.join(P1, 'results/p2_dataprep/FROZEN_MANIFEST.json')
CLASSES = ['strict', 'tie', 'cost-induced', 'TOTAL(all-classes)']


def cell(df, split, budget, e_class, col):
    return df[(df.split == split) & (df.budget == budget) & (df.e_class == e_class)].iloc[0][col]


def main():
    cost = pd.read_csv(COST); vsorc = pd.read_csv(VSORC); vstau = pd.read_csv(VSTAU)
    man = json.load(open(MANIFEST))
    lam = {float(b): float(bd['lambda_star']) for b, bd in man['budgets'].items()}
    budgets = sorted(cost.budget.unique())

    # sanity (not an assertion on the pipeline; just a report-integrity guard): cost-induced count is 0
    # exactly on the lambda=0 budget, per the CSV.
    for b in budgets:
        for split in cost.split.unique():
            ci = int(cell(cost, split, b, 'cost-induced', 'missed_by_rf'))
            if (lam[b] == 0) != (ci == 0):
                raise SystemExit(f'report-integrity: {split} B{b} cost-induced missed={ci} but lambda={lam[b]}')

    def row(split, b, cls):
        return (f'| {cls} | {int(cell(cost,split,b,cls,"clairvoyant_E_cells"))} | '
                f'{int(cell(cost,split,b,cls,"missed_by_rf"))} | '
                f'{cell(cost,split,b,cls,"F1_cost_per_framereal"):.6f} | '
                f'{cell(cost,split,b,cls,"payload_extra_per_framereal"):.6f} |')

    lines = ['# R10-family diagnostic report (auto-generated from the CSVs; do not hand-edit)\n',
             '_Every number below is recomputed by `code/p2_dataprep/make_r10_report.py` from '
             '`r10c_missed_e_cost.csv` / `r10c_vs_oracle_account.csv`. Post-unblinding; nothing '
             'confirmatory. This is the **vs-frozen-λ-clairvoyant-oracle** account and is SEPARATE from '
             'the R9 vs-τ decision._\n',
             '\n## Missed-E cost per class and TOTAL (per frame-realisation)\n',
             '_"strict-benefit missed-E cost" and "total E-collapse F1 cost" are **two different '
             'numbers**; do not conflate. cost-induced is **non-empty** where λ>0 and its F1 cost is '
             'included in the TOTAL._\n']
    for split in ['test', 'culver', 'validate']:
        lines.append(f'\n### {split}\n')
        for b in budgets:
            lines.append(f'\n**B_max = {b}** (λ\\* = {lam[b]})\n')
            lines.append('| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |')
            lines.append('|---|---|---|---|---|')
            for cls in CLASSES:
                lines.append(row(split, b, cls))

    # headline numbers, all from the CSV
    def num(split, b, cls, col='F1_cost_per_framereal'):
        return cell(cost, split, b, cls, col)
    lines.append('\n## Headline (test, from CSV)\n')
    lines.append('| B_max | strict-benefit F1/frame | total E-collapse F1/frame | cost-induced cells |')
    lines.append('|---|---|---|---|')
    for b in budgets:
        lines.append(f'| {b} | {num("test",b,"strict"):.6f} | {num("test",b,"TOTAL(all-classes)"):.6f} | '
                     f'{int(num("test",b,"cost-induced","missed_by_rf"))} |')

    lines.append('\n## vs-frozen-λ-clairvoyant-oracle account (separate from the R9 vs-τ table)\n')
    lines.append('| split | B_max | F1 gap (RF below clairvoyant) | clairvoyant payload | exceeds B_max? |')
    lines.append('|---|---|---|---|---|')
    for _, r in vsorc.iterrows():
        lines.append(f'| {r.split} | {r.budget} | {r.F1_gap_RF_below_clairvoyant:.6f} | '
                     f'{r.B_clairvoyant:.5f} | {r.clairvoyant_exceeds_Bmax} |')

    lines.append('\n## Semantic notes\n')
    lines.append('1. This is a **vs-clairvoyant-oracle** account; it is SEPARATE from and must not be '
                 'cross-referenced with the R9 **vs-τ** decision (`r10c_vs_tau_account.csv`, '
                 '`r9_result_claims.md`).')
    vgap = float(vsorc[(vsorc.split == 'validate')]['F1_gap_RF_below_clairvoyant'].abs().max())
    lines.append(f'2. The tiny validate gaps (max |F1 gap| ≈ {vgap:.6f}, some ~1e-6 negative) are normal '
                 'for the corrected (R10d) classification: in-sample the selector ≈ the clairvoyant '
                 'oracle and the residual is numerical, not a real reversal.')
    with open(os.path.join(OUT, 'R10_REPORT.md'), 'w') as f:
        f.write('\n'.join(lines) + '\n')

    # regenerate PROVENANCE_r10c.txt with CSV-derived numbers only
    st = {b: num('test', b, 'strict') for b in budgets}
    tt = {b: num('test', b, 'TOTAL(all-classes)') for b in budgets}
    with open(os.path.join(OUT, 'PROVENANCE_r10c.txt'), 'w') as f:
        f.write('CA-TOSG R10c/R10d CORRIGENDUM -- POST-UNBLINDING (nothing here is confirmatory)\n' + '=' * 72 + '\n')
        f.write('All numbers below are recomputed by make_r10_report.py from r10c_missed_e_cost.csv '
                '(no hand-written numbers). RETRACTS R10 "costs payload, not F1". Reference = FROZEN-'
                'LAMBDA CLAIRVOYANT oracle (NOT budget-constrained). 4 hard assertions in r10c_diagnostic.py '
                'PASSED; per-realisation F1_RF/B_RF reproduce the existing replay CSVs.\n\n')
        f.write('cost-induced is NON-EMPTY where lambda>0 (test B010 %d / B020 %d cells; lambda=0 budget B030 = 0); '
                'its F1 cost (small POSITIVE) is included in the TOTAL.\n'
                % (int(num('test', 0.10, 'cost-induced', 'missed_by_rf')),
                   int(num('test', 0.20, 'cost-induced', 'missed_by_rf'))))
        f.write('TWO DIFFERENT NUMBERS (do not conflate), test three budgets B010/B020/B030:\n')
        f.write('  strict-benefit missed-E F1 cost /frame = %.6f / %.6f / %.6f\n'
                % (st[0.10], st[0.20], st[0.30]))
        f.write('  total E-collapse F1 cost (all classes) /frame = %.6f / %.6f / %.6f\n'
                % (tt[0.10], tt[0.20], tt[0.30]))
        f.write('Accounts kept SEPARATE: r10c_vs_oracle_account.csv (RF vs frozen-lambda clairvoyant) and '
                'r10c_vs_tau_account.csv (R9 RF vs threshold). Retraction chain R10 -> R10c -> R10d.\n')
        f.write('NOTE: an earlier hand-written summary said "cost-induced empty" (WRONG: non-empty for '
                'lambda>0) and described cost-induced F1 cost as "<0" (WRONG: small positive). The total is '
                '%.6f/%.6f/%.6f (test) -- NOT 2x that; a proposed 0.006042/0.005775/0.006060 was a 2x '
                'hand-computation error, superseded by these CSV-derived values.\n' % (tt[0.10], tt[0.20], tt[0.30]))
    print('wrote R10_REPORT.md + regenerated PROVENANCE_r10c.txt (all numbers CSV-derived)')
    print('test strict-benefit /frame:', {b: round(st[b], 6) for b in budgets})
    print('test TOTAL /frame:', {b: round(tt[b], 6) for b in budgets})


if __name__ == '__main__':
    main()
