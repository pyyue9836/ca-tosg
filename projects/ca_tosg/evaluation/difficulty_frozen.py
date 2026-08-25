#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-5 item 7: difficulty stratification under the FROZEN protocol (reliable-channel view only).

The retired v3 difficulty ablation (`ablations/a2_difficulty.py`, deleted with its two CSVs in
R67(c)) produced the published `+0.090`: it loaded `data/selector_rf.pkl` (the v3 deployed selector,
per `ablations/_common.py`) and scored through `v3_eval`'s 200-realisation machinery. Neither is the
frozen P2 product, so its numbers may not be mixed with anything in the P2 tables.

Only ONE of that script's two views is recoverable here, and the distinction is the point:

  reliable-channel conditional   RECOVERED. Difficulty is tertiles of the frame's own object-level
                                 effective F1; conditioning on a single (channel, SNR) grid point
                                 makes the whole stratification a function of the frozen grid
                                 `data/p2/p2_grid_{split}.csv` plus the frozen selector. No new
                                 inference, no CSI draw, nothing stochastic except the bootstrap.
  all-channel 200-realisation    NOT RECOVERED, deliberately. That is the retired engine's own
                                 quantity (its selector, its CSI draw). Recomputing "the same"
                                 number under the frozen replay would be a different quantity
                                 wearing the old one's clothes, so it is deleted, not reproduced.

This file computes the CSV and needs the ARTEFACT tier (`data/p2/p2_grid_*.csv`, the frozen
`selector_B0XX.pkl`, `FROZEN_MANIFEST.json`). R69-1 moved the drawing out to
`figures/plot_difficulty_frozen.py`, which reads only the committed CSV, so the delivered figure can
be redrawn on a clean clone. Do not draw here again: re-adding a savefig re-couples the figure to
artefacts a clean clone does not have.

    python projects/ca_tosg/evaluation/difficulty_frozen.py      # CSV only
    python tools/generate_figures.py difficulty                  # the figure, from that CSV
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import os as _o, sys as _s                                                       # noqa: E401
_CT_ROOT = _o.path.abspath(_o.path.join(HERE, '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))

import deployment as D                                                           # noqa: E402

OUT_CSV = os.path.join(D.P1, 'results/sensitivity/difficulty_frozen.csv')
PROV = os.path.join(D.PROV_DIR, 'PROVENANCE_difficulty_frozen.txt')
STRATA = ('easy', 'medium', 'hard')


def strata_of(eff_L):
    """Tertiles of the frame's own object-level effective F1; LOW F1 = HARD (the retired v3
    ablation's rule, carried over verbatim)."""
    q1, q2 = np.quantile(eff_L, [1 / 3, 2 / 3])
    lab = np.full(len(eff_L), 'medium', dtype=object)
    lab[eff_L <= q1] = 'hard'
    lab[eff_L > q2] = 'easy'
    return lab, float(q1), float(q2)


def run(split, budget_tag, snr_db, channel, budgets, n_boot, seed):
    grid = pd.read_csv(os.path.join(D.GRID_DIR, f'p2_grid_{split}.csv'))
    is_ray = channel == 'rayleigh'
    sel = grid[(grid.snr_db == snr_db) & (grid.channel == channel)].sort_values('sample_id')
    assert len(sel), f'{split}: no grid rows at {channel} {snr_db} dB'

    cues = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
    assert len(cues) == len(sel), (
        f'{split}: {len(cues)} cue rows vs {len(sel)} grid rows at this condition'
    )
    # the grid is sorted by sample_id; align the cue frame the same way rather than assuming
    cues = cues.sort_values('sample_id').reset_index(drop=True)
    assert (cues['sample_id'].to_numpy() == sel['sample_id'].to_numpy()).all(), \
        f'{split}: cue/grid sample_id order differs'

    bd = budgets[budget_tag]
    n = len(sel)
    snr_2d = np.full((1, n), float(snr_db))
    ray_2d = np.full((1, n), is_ray)
    act = D.rf_actions_stacked(bd['model'], bd['feat'], cues, snr_2d, ray_2d)[0]   # 0/1/2 = E/L/F

    eff = D.eff_matrix(sel['eff_E'].to_numpy(), sel['eff_L'].to_numpy(),
                       sel['eff_F'].to_numpy(), sel['bler_F'].to_numpy())
    f1_sel = eff[np.arange(n), act]
    f1_fixedL = eff[:, D.ACTIONS.index('L')]
    f1_oracle = eff.max(1)

    lab, q1, q2 = strata_of(sel['eff_L'].to_numpy())
    rows = []
    for s in STRATA:
        m = lab == s
        delta = f1_sel[m] - f1_fixedL[m]
        mean, lo, hi = D.paired_bootstrap(delta, n_boot, seed)
        rows.append(dict(
            split=split, budget=float(budget_tag), channel=channel, snr_db=snr_db,
            view=f'reliable_{channel}_{int(snr_db)}dB', stratum=s, n=int(m.sum()),
            f1_fixedL=float(f1_fixedL[m].mean()), f1_catosg=float(f1_sel[m].mean()),
            f1_oracle=float(f1_oracle[m].mean()),
            gain_catosg_minus_L=mean, ci_lo=lo, ci_hi=hi,
            rho_E=float((act[m] == 0).mean()), rho_L=float((act[m] == 1).mean()),
            rho_F=float((act[m] == 2).mean()),
            tercile_q1=q1, tercile_q2=q2,
        ))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snr', type=float, default=16.0)
    ap.add_argument('--channel', default='awgn')
    ap.add_argument('--budget', default='0.20', help='budget tag for the console preview')
    ap.add_argument('--fig-split', default='test', help='split for the console preview')
    args = ap.parse_args()

    man, budgets = D.load_manifest()
    out = []
    for split in D.SPLITS:
        for tag in sorted(budgets):
            out.append(run(split, tag, args.snr, args.channel, budgets, D.N_BOOT, D.BOOT_SEED))
    df = pd.concat(out, ignore_index=True)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    with open(PROV, 'w') as f:
        f.write('CA-TOSG P5-5 item 7 -- difficulty stratification, FROZEN protocol.\n' + '=' * 78 + '\n')
        f.write(f'manifest: results/manifests/FROZEN_MANIFEST.json (freeze {man["freeze_timestamp"]})\n')
        f.write(f'condition: {args.channel} @ {args.snr} dB, one grid point (NOT a CSI draw)\n')
        f.write('difficulty: tertiles of the frame\'s own eff_L (low = hard), computed per split '
                'at this condition\n')
        f.write(f'selector: frozen data/p2/selector_B0XX.pkl applied via deployment.rf_actions_stacked '
                f'(imported, not re-implemented)\n')
        f.write(f'bootstrap: paired frame-level, n_boot={D.N_BOOT}, seed={D.BOOT_SEED} '
                f'(deployment.paired_bootstrap)\n')
        f.write('NOT PRODUCED: the all-channel 200-realisation view. That is the retired v3 engine\'s\n'
                '  own quantity (v3 selector data/selector_rf.pkl + v3_eval CSI machinery) and is\n'
                '  deleted rather than reproduced -- the two engines may not be blended.\n')

    show = df[(df.split == args.fig_split) & (df.budget == float(args.budget))]
    print(show[['split', 'budget', 'stratum', 'n', 'f1_fixedL', 'f1_catosg', 'f1_oracle',
                'gain_catosg_minus_L', 'ci_lo', 'ci_hi', 'rho_F']].to_string(index=False))
    print(f'\nwrote {OUT_CSV}\n      {PROV}')
    print('the figure is NOT drawn here (R69-1): run '
          'python tools/generate_figures.py difficulty, which calls '
          'projects/ca_tosg/evaluation/figures/plot_difficulty_frozen.py on the CSV above.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
