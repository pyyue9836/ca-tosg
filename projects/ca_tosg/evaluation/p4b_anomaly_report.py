#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-B-g item 6: the §8 anomaly checklist, run on the SECOND-backbone arm.

Every item of §8 is a falsifiable expectation. This script evaluates each one against the arm's own
committed outputs and reports PASS / **FUSE**. It never adjusts data, never retrains and never
touches delta; where an expectation and the measurement disagree, the finding is recorded as the
finding (§8 handling rule 3).

    python projects/ca_tosg/evaluation/p4b_anomaly_report.py
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
ARM = os.path.join(ROOT, 'results/p4b')
OUT = os.path.join(ARM, 'P4B_ANOMALY_REPORT.md')
MANIFEST = os.path.join(ROOT, 'results/manifests/P4B_FROZEN_MANIFEST.json')

items = []


def item(name, ok, detail):
    items.append((name, bool(ok), detail))
    return ok


def main() -> int:
    rep = pd.read_csv(os.path.join(ARM, 'replay_summary.csv'))
    rep = rep[rep['split'] != 'split'].copy()
    for c in ('budget', 'F1_RF', 'F1_tau', 'B_RF', 'B_tau', 'dF_mean', 'dF_lcb95', 'dF_ucb95'):
        rep[c] = rep[c].astype(float)
    act = pd.read_csv(os.path.join(ARM, 'action_distribution.csv'))
    per = pd.read_csv(os.path.join(ARM, 'perclass_ELF.csv'))
    man = json.load(open(MANIFEST))

    # --- §8: validate budget points ---
    v = rep[rep.split == 'validate']
    bad = v[v.B_RF > v.budget]
    item('validate mean payload <= B_max at every budget', len(bad) == 0,
         '; '.join(f'B={r.budget}: pay={r.B_RF:.5f}' for _, r in v.iterrows()))

    # --- §8: no C256 in any deployed action distribution ---
    item('no C256 in the deployed action distribution',
         not any('256' in c for c in act.columns),
         f'action columns: {[c for c in act.columns if c.startswith(("rf_", "or_"))]}')

    # --- §8: Rayleigh should show BOTH E and L (not 100% L) ---
    ray = act[act.channel == 'rayleigh']
    det = []
    ok_ray = True
    for (sp, b), g in ray.groupby(['split', 'budget']):
        e, ll = g.rf_E.mean(), g.rf_L.mean()
        det.append(f'{sp} B={b}: rf_E={e:.4f} rf_L={ll:.4f} (oracle E={g.or_E.mean():.4f})')
        ok_ray &= e > 0.0
    item('Rayleigh shows BOTH E and L for the selector (not 100% L)', ok_ray, '; '.join(det))

    # --- §8: high SNR -> F share increases ---
    aw = act[act.channel == 'awgn']
    det, ok_hi = [], True
    for (sp, b), g in aw.groupby(['split', 'budget']):
        g = g.sort_values('snr_db')
        lo = g[g.snr_db <= 6].rf_F.mean()
        hi = g[g.snr_db >= 14].rf_F.mean()
        det.append(f'{sp} B={b}: F share {lo:.4f} (<=6 dB) -> {hi:.4f} (>=14 dB)')
        ok_hi &= hi >= lo
    item('AWGN high-SNR F share does not fall', ok_hi, '; '.join(det))

    # --- §8: exactly one frozen model per budget, no per-split refit ---
    item('one frozen model + lambda*/tau* per budget, no per-split refit',
         len(man['budgets']) == 3 and all('model' in b for b in man['budgets'].values()),
         '; '.join(f'B={k}: cand#{b["candidate_index"]} cw={b["class_weight"]} '
                   f'lam*={b["lambda_star"]} tau*={b["tau_star"]}'
                   for k, b in sorted(man['budgets'].items())))

    # --- arm-specific: does the frozen selector transfer off validate? ---
    acc = per.groupby('split').rf_vs_oracle_acc.first()
    item('selector-vs-oracle agreement holds off validate (>= 0.75)',
         bool((acc.drop('validate', errors='ignore') >= 0.75).all()),
         '; '.join(f'{k}: {v:.4f}' for k, v in acc.items()))

    # --- arm-specific: paired dF sign, reported not adjudicated ---
    det = []
    for _, r in rep.iterrows():
        det.append(f'{r.split} B={r.budget}: dF={r.dF_mean:+.5f} '
                   f'[{r.dF_lcb95:+.5f},{r.dF_ucb95:+.5f}]')
    item('paired dF vs tau is non-negative off validate',
         bool((rep[rep.split != 'validate'].dF_mean >= 0).all()), '; '.join(det))

    fuses = [n for n, ok, _ in items if not ok]
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('# P4-B second-backbone arm — §8 anomaly checklist\n\n')
        f.write('**second-backbone arm, not deployed.** Descriptive with paired CIs; no decision is '
                'taken here and `delta` is untouched. §8 handling rule 3 applies throughout: where '
                'an expectation and the measurement disagree, the finding changes, not the data.\n\n')
        f.write(f'| # | expectation | result |\n|---|---|---|\n')
        for i, (n, ok, _) in enumerate(items, 1):
            f.write(f'| {i} | {n} | {"PASS" if ok else "**FUSE**"} |\n')
        f.write(f'\n**{len(fuses)} of {len(items)} expectations not met.**\n\n')
        for n, ok, d in items:
            f.write(f'\n### {"PASS" if ok else "FUSE"} — {n}\n\n{d}\n')
    for n, ok, d in items:
        print(f'{"PASS " if ok else "FUSE "} {n}\n        {d}')
    print(f'\n{len(fuses)} fuse(s). wrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
