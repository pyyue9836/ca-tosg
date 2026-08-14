#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-7 (D): ONE frozen source for every SNR-indexed figure.

Fig.4 (AP/F1 vs SNR), Fig.5 (payload vs SNR), Fig.6 (decision ratios) and Fig.8 (Pareto) were each
drawn from a different, mostly retired, product. This module emits a single CSV covering all of
them, computed on the deterministic frozen grid `data/p2/p2_grid_{split}.csv` with the frozen
selectors applied through `deployment.rf_actions_stacked` -- imported, never re-implemented.

Per (split, budget, channel, SNR) it records, for each policy:
    f1        mean realised effective F1 (the analytic eff of PROTOCOL sec 4)
    payload   mean per-frame channel use in Msym
    rho_E/L/F action shares

Policies: `fixed_L`, `fixed_F`, `feature_ceiling` (F always delivered -- the perfect-channel
reference), `oracle_masked` (argmax over the feasibility-masked [E,L,F], the same rule as
`grid_builder`), `oracle_lambda` (the same masked argmax with that budget's frozen `lambda_star`
payload penalty -- the correct companion for a budgeted selector, and NOT clairvoyant: it sees the
BLER, not the block outcome), and `catosg` (the frozen selector at that budget).

This is a deterministic grid product. It is a DIFFERENT quantity from the 200-realisation replay of
`replay_summary.csv`, which marginalises SNR and channel away; the two must not be mixed in one
sentence. Figures that show a curve versus SNR use this file; tables that quote a channel-averaged
operating point use the replay.

    python projects/ca_tosg/evaluation/frozen_curves.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import os as _o, sys as _s                                                        # noqa: E401
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils'):
    _s.path.insert(0, _o.path.join(_o.path.abspath(_o.path.join(HERE, '..', '..', '..')), _d))

import deployment as D                                                            # noqa: E402

OUT_CSV = os.path.join(D.OUT, 'frozen_curves.csv')
PROV = os.path.join(D.PROV_DIR, 'PROVENANCE_frozen_curves.txt')
BLER_INFEASIBLE = 0.999


def shares(idx):
    return {f'rho_{a}': float((idx == k).mean()) for k, a in enumerate(D.ACTIONS)}


def main() -> int:
    man, budgets = D.load_manifest()
    # lambda_star is on the manifest, not on deployment.load_manifest's reduced budget dict
    lam_of = {b: float(bd['lambda_star']) for b, bd in man['budgets'].items()}
    rows = []
    for split in D.SPLITS:
        grid = pd.read_csv(os.path.join(D.GRID_DIR, f'p2_grid_{split}.csv'))
        cues = pd.read_csv(os.path.join(D.DATA, D.DATASET[split])).sort_values('sample_id')
        for tag in sorted(budgets):
            bd = budgets[tag]
            lam = lam_of[tag]
            for ch in ('awgn', 'rayleigh'):
                for snr in D.SNR_GRID:
                    g = grid[(grid.channel == ch) & (grid.snr_db == snr)].sort_values('sample_id')
                    assert len(g) == len(cues), f'{split} {ch} {snr}: grid/cue length mismatch'
                    assert (g['sample_id'].to_numpy() == cues['sample_id'].to_numpy()).all()
                    n = len(g)
                    bF = g['bler_F'].to_numpy()
                    eff = D.eff_matrix(g['eff_E'].to_numpy(), g['eff_L'].to_numpy(),
                                       g['eff_F'].to_numpy(), bF)
                    masked = eff.copy()
                    masked[bF >= BLER_INFEASIBLE, 2] = -np.inf

                    act = D.rf_actions_stacked(bd['model'], bd['feat'], cues,
                                               np.full((1, n), float(snr)),
                                               np.full((1, n), ch == 'rayleigh'))[0]
                    or_idx = masked.argmax(1)
                    lam_idx = (masked - lam * D.PAYVEC[None, :]).argmax(1)

                    entries = {
                        'fixed_L': (eff[:, 1], np.full(n, D.PAY['L']), None),
                        'fixed_F': (eff[:, 2], np.full(n, D.PAY['F']), None),
                        'feature_ceiling': (g['eff_F'].to_numpy() * 0 + g['eff_F'].to_numpy(),
                                            np.full(n, D.PAY['F']), None),
                        'oracle_masked': (eff[np.arange(n), or_idx], D.PAYVEC[or_idx], or_idx),
                        'oracle_lambda': (eff[np.arange(n), lam_idx], D.PAYVEC[lam_idx], lam_idx),
                        'catosg': (eff[np.arange(n), act], D.PAYVEC[act], act),
                    }
                    # feature_ceiling = the compressed branch with NO channel loss. Read it
                    # straight from the cue dataset rather than inverting eff_F: below the cliff
                    # bF = 1 and the inversion divides by zero.
                    entries['feature_ceiling'] = (cues['compressed_f1'].to_numpy(),
                                                  np.full(n, D.PAY['F']), None)

                    for pol, (f1, pay, idx) in entries.items():
                        r = dict(split=split, budget=float(tag), channel=ch, snr_db=float(snr),
                                 policy=pol, f1=float(np.nanmean(f1)),
                                 payload_msym=float(np.mean(pay)), n_frames=n,
                                 bler_F=float(bF[0]), lambda_star=lam)
                        r.update(shares(idx) if idx is not None
                                 else {f'rho_{a}': float('nan') for a in D.ACTIONS})
                        rows.append(r)
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    with open(PROV, 'w') as f:
        f.write('CA-TOSG P5-7 (D) -- frozen SNR-indexed curves, ONE source for Figs. 4/5/6/8.\n'
                + '=' * 78 + '\n')
        f.write(f'manifest: results/manifests/FROZEN_MANIFEST.json (freeze {man["freeze_timestamp"]})\n')
        f.write('substrate: data/p2/p2_grid_{split}.csv -- the DETERMINISTIC frame x 11 SNR x 2 '
                'channel grid.\n')
        f.write('selector: frozen data/p2/selector_B0XX.pkl via deployment.rf_actions_stacked '
                '(imported).\n')
        f.write(f'oracle_masked: argmax over eff with BLER_F >= {BLER_INFEASIBLE} removing F '
                '(PROTOCOL sec 4), ties -> E then L.\n')
        f.write('oracle_lambda: the same masked argmax minus lambda_star * payload, lambda_star '
                'read per budget from the manifest. It sees the BLER, NOT the per-frame block '
                'outcome -- it is not clairvoyant.\n')
        f.write('DIFFERENT QUANTITY from results/main/replay_summary.csv (200-realisation replay, '
                'SNR and channel marginalised away). Do not mix the two in one sentence.\n')
    print(df.groupby(['split', 'policy']).size().to_string())
    print(f'\nwrote {OUT_CSV}  ({len(df)} rows)\n      {PROV}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
