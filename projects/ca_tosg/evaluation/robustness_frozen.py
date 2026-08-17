#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R18-final rule (c): tab:robustness ported to the frozen selectors and the corrected grid.

The three rows of `tab:robustness` came from the retired v3 ablation harness
(`ablations/robustness.py` via `_common.py`), and they did not reproduce even from that harness's own
committed CSVs. The R18 ruling says: if a row is not covered by the P3 suite but *is* re-derivable at
grid/cache level, port it. All three are — every one perturbs the **selector's inputs** and replays,
with no perception-level inference:

  1. SNR-estimation noise      est_snr = true_snr + N(0, sigma), sigma in {0, 0.5, 1, 2, 5} dB
  2. CSI aging (Jakes, 60 km/h) sigma = sqrt(1 - J0(2*pi*f_d*tau)^2) * 6 dB, tau in {0,10,20,50} ms
  3. Decision staleness         the decision taken on frame t-d applied at frame t, d in {0,1,2,5}

Models (1) and (2) are the retired harness's own formulae, carried over verbatim so the physics is
unchanged and only the selector, grid and utilities are the corrected ones. What P3 already covers and
this does NOT duplicate: channel mix ratio, SNR distribution, c_t misclassification, BLER_L, Rician K.

Every draw reuses `deployment.py` -- same CSI_SEED, same call order, same eff_matrix/PAYVEC.

    python projects/ca_tosg/evaluation/robustness_frozen.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.special import j0

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils', 'projects/ca_tosg/models'):
    sys.path.insert(0, os.path.join(ROOT, _d))
sys.path.insert(0, ROOT)

import deployment as D  # noqa: E402

OUT = os.path.join(ROOT, 'results/sensitivity/robustness_frozen.csv')
PROV = os.path.join(ROOT, 'results/provenance/PROVENANCE_robustness_frozen.txt')
SPLIT = 'test'                      # the table is on OPV2V test
SIGMAS = (0.0, 0.5, 1.0, 2.0, 5.0)
DELAYS_MS = (0, 10, 20, 50)
STALE = (0, 1, 2, 5)
FD_HZ = 327.0                       # 60 km/h at 5.9 GHz, the retired harness's value
NOISE_SEED = 20260817               # separate stream: the CSI draw order must stay byte-identical


def setup():
    tbl = pd.read_csv(D.BLER_CSV)
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[SPLIT]))
    n = len(ds)
    ego, late, comp = (ds[c].to_numpy() for c in ('ego_f1', 'late_f1', 'compressed_f1'))
    rng = np.random.default_rng(D.CSI_SEED)
    snr_2d = rng.uniform(0, 20, size=(D.N_REPLAY, n))
    is_ray_2d = rng.random(size=(D.N_REPLAY, n)) < 0.5
    bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(D.N_REPLAY)])
    E = [D.eff_matrix(ego, late, comp, bF_2d[r]) for r in range(D.N_REPLAY)]
    return ds, n, E, snr_2d, is_ray_2d


def score(idx, E, n):
    f1 = np.array([E[r][np.arange(n), idx[r]].mean() for r in range(len(E))])
    pay = np.array([D.PAYVEC[idx[r]].mean() for r in range(len(E))])
    return float(f1.mean()), float(pay.mean())


def actions(bd, ds, snr_2d, is_ray_2d, sigma=0.0):
    """Selector actions, optionally with a noisy SNR estimate. The channel and the utilities are
    unchanged -- only what the SELECTOR is told about the SNR moves, which is the point."""
    if sigma > 0:
        rng = np.random.default_rng(NOISE_SEED)
        seen = snr_2d + rng.normal(0.0, sigma, size=snr_2d.shape)
    else:
        seen = snr_2d
    return D.rf_actions_stacked(bd['model'], bd['feat'], ds, seen, is_ray_2d)


def main() -> int:
    ds, n, E, snr_2d, is_ray_2d = setup()
    _man, budgets = D.load_manifest()   # (manifest, {budget_tag: {model, tau, feat, ...}})
    rows = []
    for tag in sorted(budgets):
        bd = budgets[tag]
        base_idx = actions(bd, ds, snr_2d, is_ray_2d, 0.0)
        f1_0, pay_0 = score(base_idx, E, n)
        rows.append(dict(budget=float(tag), experiment='baseline', setting='0',
                         f1=round(f1_0, 5), payload=round(pay_0, 5), dF1=0.0))
        for sg in SIGMAS[1:]:                                        # (1) SNR-estimation noise
            f1, pay = score(actions(bd, ds, snr_2d, is_ray_2d, sg), E, n)
            rows.append(dict(budget=float(tag), experiment='snr_noise', setting=f'sigma={sg}dB',
                             f1=round(f1, 5), payload=round(pay, 5), dF1=round(f1 - f1_0, 5)))
        for tau in DELAYS_MS[1:]:                                    # (2) CSI aging, Jakes
            rho = float(j0(2 * np.pi * FD_HZ * tau * 1e-3))
            sg = float(np.sqrt(max(0.0, 1 - rho ** 2)) * 6.0)
            f1, pay = score(actions(bd, ds, snr_2d, is_ray_2d, sg), E, n)
            rows.append(dict(budget=float(tag), experiment='csi_aging',
                             setting=f'{tau}ms (rho={rho:.3f}, sigma={sg:.2f}dB)',
                             f1=round(f1, 5), payload=round(pay, 5), dF1=round(f1 - f1_0, 5)))
        for d in STALE[1:]:                                          # (3) decision staleness
            stale = np.roll(base_idx, d, axis=1)                     # frame t-d's decision at frame t
            stale[:, :d] = base_idx[:, :d]                           # no history for the first d frames
            f1, pay = score(stale, E, n)
            rate = float((stale != base_idx).mean())
            rows.append(dict(budget=float(tag), experiment='decision_staleness',
                             setting=f'{d} frame(s) stale (changed {100 * rate:.1f}% of decisions)',
                             f1=round(f1, 5), payload=round(pay, 5), dF1=round(f1 - f1_0, 5)))
        print(f'[B={tag}] baseline {f1_0:.5f}; '
              f'sigma<=1dB {[r["dF1"] for r in rows if r["budget"]==float(tag) and r["setting"]=="sigma=1.0dB"]}; '
              f'aging 10ms {[r["dF1"] for r in rows if r["budget"]==float(tag) and r["setting"].startswith("10ms")]}; '
              f'1-frame stale {[r["dF1"] for r in rows if r["budget"]==float(tag) and r["setting"].startswith("1 frame")]}')
    pd.DataFrame(rows).to_csv(OUT, index=False)
    with open(PROV, 'w') as f:
        f.write('CA-TOSG R18-final rule (c) -- tab:robustness ported to the frozen selectors.\n')
        f.write(f'generated: {datetime.now(timezone.utc).isoformat()}\n')
        f.write(f'split: {SPLIT}; N_REPLAY={D.N_REPLAY}; CSI_SEED={D.CSI_SEED} (deployed draw, reused '
                f'from deployment.py); SNR-noise stream seed {NOISE_SEED}, separate so the CSI draw '
                f'order stays byte-identical.\n')
        f.write('models carried over VERBATIM from the retired harness: Jakes f_d=327 Hz at 60 km/h, '
                'sigma = sqrt(1-J0(2*pi*f_d*tau)^2)*6 dB; CSI noise est_snr = true + N(0,sigma).\n')
        f.write('the perturbation touches only what the SELECTOR is told; the channel, the BLER and '
                'the per-frame utilities are the deployed ones.\n')
        f.write('NOT duplicated here (already covered by the P3 suite): channel mix ratio, SNR '
                'distribution, c_t misclassification, BLER_L, Rician K.\n')
    print(f'wrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
