#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 item-3 LABELLED comparison variants (validate-only; NOT deployed; Change-log P3).

Trains two feature-set probes and one full-feature control, ALL on the validate grid oracle_ELF label,
with the deployed RF family's hyper-parameters (400 trees, depth 10, leaf 4, class_weight=None,
random_state=0). They are **labeled variants, not deployed**: they do NOT touch FROZEN_MANIFEST.json,
are trained + evaluated on validate ONLY, and answer the feature-sufficiency question behind item 3
(does the selector need the ego cues / a continuous channel observable vs the binary channel bit?).

  * full_ref     : the 23 deployed features (21 ego cues + est_snr_db + channel_is_rayleigh).
  * snr_only     : est_snr_db alone.
  * cont_obs     : 21 ego cues + est_snr_db + delay_spread_ns + doppler_hz, where the binary
                   channel_is_rayleigh is REPLACED by a frozen deterministic map (Change-log P3):
                   delay_spread_ns = {awgn:30, rayleigh:300}, doppler_hz = {awgn:20, rayleigh:600}.

Evaluation: realised validate F1 / payload / feature-selection rate under the baseline replay (uniform
SNR, 50/50 channel, BLER_L=0), reusing eval_p3_sensitivity's draws/metrics. Reported next to the deployed
selectors' validate numbers (baseline_sanity.csv) for context. Descriptive only.

Output: results/sensitivity/item3_variants.csv  (+ notes in PROVENANCE_p3.txt).
Run:  /path/to/env/python projects/ca_tosg/evaluation/p3_variants.py
"""
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# --- ca-tosg layout bootstrap (restructure commit 2/4) ---
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/evaluation/ablations', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
# --- end bootstrap ---
import deployment as D
import eval_p3_sensitivity as P3

P1 = D.P1
OUT = os.path.join(P1, 'results/sensitivity')
GRID = os.path.join(D.GRID_DIR, 'p2_grid_validate.csv')
ACT2I = {'E': 0, 'L': 1, 'F': 2}
DELAY = {'awgn': 30.0, 'rayleigh': 300.0}      # ns  (frozen map, Change-log P3)
DOPP = {'awgn': 20.0, 'rayleigh': 600.0}       # Hz
RF_KW = dict(n_estimators=400, max_depth=10, min_samples_leaf=4, class_weight=None, random_state=0, n_jobs=-1)


def cue_cols(feat):
    return [c for c in feat if c not in ('est_snr_db', 'channel_is_rayleigh')]


def build_X(variant, cues_block, snr, is_ray, cols):
    """Build a variant feature matrix. cues_block=(m,21) ego cues; snr,is_ray=(m,); cols=ego cue names."""
    m = len(snr)
    ray = is_ray.astype(bool)
    if variant == 'snr_only':
        return snr.reshape(-1, 1)
    if variant == 'full_ref':
        X = np.empty((m, len(cols) + 2))
        X[:, :len(cols)] = cues_block
        X[:, len(cols)] = snr
        X[:, len(cols) + 1] = ray.astype(int)
        return X
    if variant == 'cont_obs':
        X = np.empty((m, len(cols) + 3))
        X[:, :len(cols)] = cues_block
        X[:, len(cols)] = snr
        X[:, len(cols) + 1] = np.where(ray, DELAY['rayleigh'], DELAY['awgn'])
        X[:, len(cols) + 2] = np.where(ray, DOPP['rayleigh'], DOPP['awgn'])
        return X
    raise ValueError(variant)


def eval_variant(model, variant, ds, cols):
    """Realised validate F1/payload/rho under the baseline replay (uniform SNR, 50/50, BLER_L=0)."""
    tbl = pd.read_csv(D.BLER_CSV)
    snr_2d, is_ray_2d = P3._draws(ds, 'uniform', 0.5)
    cues_block = ds[cols].to_numpy()
    F1 = np.empty(P3.N_REPLAY); B = np.empty(P3.N_REPLAY); RHO = np.empty(P3.N_REPLAY)
    ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
    n = len(ds)
    for r in range(P3.N_REPLAY):
        X = build_X(variant, cues_block, snr_2d[r], is_ray_2d[r], cols)
        act = np.asarray(model.predict(X), dtype=int)
        bF = D.bler16(tbl, snr_2d[r], is_ray_2d[r])
        E = np.stack([ego, late, comp * (1 - bF) + ego * bF], axis=1)
        F1[r] = E[np.arange(n), act].mean(); B[r] = P3.PAYVEC[act].mean(); RHO[r] = float((act == 2).mean())
    return float(F1.mean()), float(F1.std()), float(B.mean()), float(RHO.mean())


def main():
    os.makedirs(OUT, exist_ok=True)
    man, budgets = D.load_manifest()
    feat = man['feature_names']
    cols = cue_cols(feat)
    grid = pd.read_csv(GRID)
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET['validate']))

    # training matrices from the validate grid (frame x snr x channel), target = oracle_ELF
    gcue = grid.merge(ds[['sample_id'] + cols], on='sample_id', how='left')[cols].to_numpy()
    gsnr = grid['snr_db'].to_numpy(float)
    gray = (grid['channel'] == 'rayleigh').to_numpy()
    y = grid['oracle_ELF'].map(ACT2I).to_numpy()

    rows = []
    for variant in ('full_ref', 'snr_only', 'cont_obs'):
        Xtr = build_X(variant, gcue, gsnr, gray, cols)
        m = RandomForestClassifier(**RF_KW).fit(Xtr, y)
        train_acc = float((m.predict(Xtr) == y).mean())
        f1, f1s, pay, rho = eval_variant(m, variant, ds, cols)
        rows.append(dict(variant=variant, status='labeled variant / not deployed', split='validate',
                         n_features=Xtr.shape[1], train_oracle_acc=round(train_acc, 4),
                         F1=round(f1, 5), F1_std=round(f1s, 5), payload=round(pay, 5),
                         rho_feature=round(rho, 4)))
        print(f'  {variant:9s} nfeat={Xtr.shape[1]:2d} train_acc={train_acc:.4f} '
              f'validate F1={f1:.5f} payload={pay:.5f} rho_F={rho:.4f}', flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, 'item3_variants.csv'), index=False)
    print('wrote results/sensitivity/item3_variants.csv (labeled variants, not deployed; validate-only)')


if __name__ == '__main__':
    main()
