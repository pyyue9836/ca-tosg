#self+ CA-TOSG paper2: deployment-mode verification with empirical ego floor (table in §VI.9)
# -*- coding: utf-8 -*-
"""End-to-end deployment-mode verification.

Mirrors the at-deployment pipeline:
  for each frame (without train/test leakage of selector cues):
    rf decides s_t in {L, C16, C256} from (cues_t, snr_t, channel_t)
    if s_t == L:    realised F1 = late_f1
    if s_t == C16:  realised F1 = compressed_f1 with prob (1-BLER16);
                                  ego-only floor with prob BLER16
    if s_t == C256: same with BLER256

This differs from the training-time analytical model in TWO ways:
  1. Channel is sampled stochastically per frame from a Bernoulli(BLER)
     rather than collapsed into the expectation, mirroring deployment.
  2. The block-loss outcome falls back to a configurable floor F_floor
     (default = empirical ego-only AP@0.5 of 0.63 from baseline_results_5070.csv)
     rather than to F1=0, which is a more realistic receiver behaviour.

The output (mean F1) should sit between the analytical model and Fixed L
because the floor is non-zero. This serves as the deployment-mode sanity
check requested by reviewers.

Output: runs/v4_e2e/results.csv (one row per (channel, snr) operating point).
"""
import os
import pickle

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/dataset.csv')
RF_PATH = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/rf_full.pkl')
BLER_CSV = os.path.join(REPO, 'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_e2e')

# Single operating points reviewers typically ask about: 10 dB on both channels.
OPS = [
    ('awgn', 0.0), ('awgn', 10.0), ('awgn', 12.0),
    ('awgn', 14.0), ('awgn', 16.0), ('awgn', 20.0),
    ('rayleigh', 0.0), ('rayleigh', 10.0), ('rayleigh', 20.0),
]
N_REPEAT = 50  # stochastic channel realisations averaged
SEED = 0
F_FLOOR = 0.63  # ego-only F1 floor on OPV2V (empirically observed)
PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}


def bler_awgn(snr, df, qam):
    s = df[df['qam'] == qam].sort_values('snr_db')
    return float(np.clip(np.interp(snr, s['snr_db'], s['bler'],
                                   left=1.0, right=0.0), 0.0, 1.0))


def bler_rayleigh(snr_mean, df, qam):
    s = df[df['qam'] == qam].sort_values('snr_db')
    xs = s['snr_db'].to_numpy(); ys = s['bler'].to_numpy()
    gb = 10.0 ** (snr_mean / 10.0)
    g_db = np.linspace(-15.0, 40.0, 400)
    g_lin = 10.0 ** (g_db / 10.0)
    bler_g = np.clip(np.interp(g_db, xs, ys, left=1.0, right=0.0), 0.0, 1.0)
    pdf = (1.0 / gb) * np.exp(-g_lin / gb)
    jac = g_lin * np.log(10) / 10.0
    return float(np.clip(np.trapz(bler_g * pdf * jac, g_db), 0.0, 1.0))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATASET)
    bler_df = pd.read_csv(BLER_CSV)
    with open(RF_PATH, 'rb') as f: rf = pickle.load(f)
    feat_cols = list(rf.feature_names_in_)
    rng = np.random.default_rng(SEED)

    rows = []
    for channel, snr in OPS:
        d = df.copy()
        d['est_snr_db'] = snr
        d['channel_is_rayleigh'] = int(channel == 'rayleigh')
        # Selector observes the operating point and predicts per-frame actions.
        actions = rf.predict(d[feat_cols])

        # BLER at this operating point
        bler_fn = bler_rayleigh if channel == 'rayleigh' else bler_awgn
        b16 = bler_fn(snr, bler_df, 16)
        b256 = bler_fn(snr, bler_df, 256)

        f1_runs = []; pay_runs = []
        for _ in range(N_REPEAT):
            f1 = np.zeros(len(d)); pay = np.zeros(len(d))
            # L: no channel loss
            mask_L = actions == 'L'
            f1[mask_L] = d.loc[mask_L, 'late_f1'].to_numpy()
            pay[mask_L] = PAYLOAD['L']
            # C16: Bernoulli(BLER16) drop -> floor
            mask_C16 = actions == 'C16'
            n16 = mask_C16.sum()
            survives16 = rng.random(n16) > b16
            f1_C16_clean = d.loc[mask_C16, 'compressed_f1'].to_numpy()
            f1_C16 = np.where(survives16, f1_C16_clean, F_FLOOR)
            f1[mask_C16] = f1_C16
            pay[mask_C16] = PAYLOAD['C16']
            # C256
            mask_C256 = actions == 'C256'
            n256 = mask_C256.sum()
            survives256 = rng.random(n256) > b256
            f1_C256_clean = d.loc[mask_C256, 'compressed_f1'].to_numpy()
            f1_C256 = np.where(survives256, f1_C256_clean, F_FLOOR)
            f1[mask_C256] = f1_C256
            pay[mask_C256] = PAYLOAD['C256']
            f1_runs.append(f1.mean()); pay_runs.append(pay.mean())

        # Reference: analytical-model F1 (block-loss with floor=0).
        f1_analytic = np.where(actions == 'L', d['late_f1'].to_numpy(),
            np.where(actions == 'C16',
                     d['compressed_f1'].to_numpy() * (1.0 - b16),
                     d['compressed_f1'].to_numpy() * (1.0 - b256))).mean()

        # Also: deterministic e2e F1 with floor (no Bernoulli sampling).
        f1_e2e_det = np.where(actions == 'L', d['late_f1'].to_numpy(),
            np.where(actions == 'C16',
                     (1 - b16) * d['compressed_f1'].to_numpy() + b16 * F_FLOOR,
                     (1 - b256) * d['compressed_f1'].to_numpy() + b256 * F_FLOOR
                    )).mean()

        rows.append(dict(
            channel=channel, snr_db=snr,
            frac_L=float((actions == 'L').mean()),
            frac_C16=float((actions == 'C16').mean()),
            frac_C256=float((actions == 'C256').mean()),
            f1_analytic_model=float(f1_analytic),
            f1_e2e_with_floor_det=float(f1_e2e_det),
            f1_e2e_with_floor_stochastic=float(np.mean(f1_runs)),
            f1_e2e_std=float(np.std(f1_runs)),
            payload=float(np.mean(pay_runs)),
            bler_16=b16, bler_256=b256,
        ))
        print(f'  {channel:8s} SNR={snr:5.1f} dB: '
              f'F1_analytic={f1_analytic:.4f}  F1_e2e(floor)={np.mean(f1_runs):.4f}±{np.std(f1_runs):.4f}  '
              f'payload={np.mean(pay_runs):.4f}  rho_L={float((actions=="L").mean()):.3f}')

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT_DIR, 'results.csv'), index=False)
    print('wrote', os.path.join(OUT_DIR, 'results.csv'))


if __name__ == '__main__':
    main()
