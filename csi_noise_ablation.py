#self+ CA-TOSG paper2: CSI estimation noise robustness (sigma sweep + figure)
# -*- coding: utf-8 -*-
"""CSI noise robustness: inject Gaussian SNR-estimation error and re-evaluate.

Loads the deployed rf_full.pkl, perturbs est_snr_db by N(0, sigma^2) for
sigma in {0, 0.5, 1, 2, 3, 5} dB, and reports the resulting (payload, F1)
at fixed SNR=10 dB across AWGN and Rayleigh.

This addresses the standard reviewer comment "what if the SNR estimator is
noisy?" without retraining the selector.

Output:
  runs/v4_csi_noise/results.csv  — per-(sigma, channel) row
  runs/v4_csi_noise/fig_csi_noise.png + pdf
"""
import os
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/dataset.csv')
RF_PATH = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/rf_full.pkl')
BLER_CSV = os.path.join(REPO, 'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_csi_noise')

SNR_NOMINAL = 10.0  # fix operating point
SIGMAS = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]  # SNR estimation noise std (dB)
N_REPEAT = 10  # average over 10 noise draws per sigma to stabilise
SEED = 0
PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}


def bler_awgn(snr_db, bler_df, qam):
    sub = bler_df[bler_df['qam'] == qam].sort_values('snr_db')
    return float(np.clip(np.interp(snr_db, sub['snr_db'], sub['bler'],
                                   left=1.0, right=0.0), 0.0, 1.0))


def bler_rayleigh(snr_db_mean, bler_df, qam):
    sub = bler_df[bler_df['qam'] == qam].sort_values('snr_db')
    xs = sub['snr_db'].to_numpy(); ys = sub['bler'].to_numpy()
    gb = 10.0 ** (snr_db_mean / 10.0)
    g_db = np.linspace(-15.0, 40.0, 400)
    g_lin = 10.0 ** (g_db / 10.0)
    bler_g = np.clip(np.interp(g_db, xs, ys, left=1.0, right=0.0), 0.0, 1.0)
    pdf = (1.0 / gb) * np.exp(-g_lin / gb)
    jac = g_lin * np.log(10) / 10.0
    return float(np.clip(np.trapz(bler_g * pdf * jac, g_db), 0.0, 1.0))


def realised(df, actions):
    actions = np.asarray(actions)
    f1 = np.choose(
        (actions == 'C256').astype(int) * 2 + (actions == 'C16').astype(int),
        [df['eff_f1_L'].to_numpy(), df['eff_f1_C16'].to_numpy(),
         df['eff_f1_C256'].to_numpy()])
    pay = np.zeros_like(f1)
    for a in PAYLOAD:
        pay[actions == a] = PAYLOAD[a]
    return float(pay.mean()), float(f1.mean())


def evaluate_at_noise(df, rf, feat_cols, channel, sigma, rng, bler_df):
    """Run RF with noisy est_snr_db, average across N_REPEAT noise draws."""
    f1s = []; pays = []
    for _ in range(N_REPEAT):
        d = df.copy()
        true_snr = SNR_NOMINAL
        noisy_snr = true_snr + rng.normal(0.0, sigma, size=len(d))
        d['est_snr_db'] = noisy_snr
        d['channel_is_rayleigh'] = int(channel == 'rayleigh')
        # Effective F1 uses TRUE SNR (channel doesn't lie); only the selector
        # sees the noisy estimate. This isolates estimator-noise impact.
        bler_fn = bler_rayleigh if channel == 'rayleigh' else bler_awgn
        b16 = bler_fn(true_snr, bler_df, 16)
        b256 = bler_fn(true_snr, bler_df, 256)
        d['eff_f1_C16'] = d['compressed_f1'] * (1.0 - b16)
        d['eff_f1_C256'] = d['compressed_f1'] * (1.0 - b256)
        d['eff_f1_L'] = d['late_f1']
        pred = rf.predict(d[feat_cols])
        pay, f1 = realised(d, pred)
        f1s.append(f1); pays.append(pay)
    return float(np.mean(f1s)), float(np.std(f1s)), float(np.mean(pays))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATASET)
    bler_df = pd.read_csv(BLER_CSV)
    with open(RF_PATH, 'rb') as f: rf = pickle.load(f)
    feat_cols = list(rf.feature_names_in_)
    rng = np.random.default_rng(SEED)

    rows = []
    for channel in ('awgn', 'rayleigh'):
        for sigma in SIGMAS:
            f1_m, f1_s, pay = evaluate_at_noise(df, rf, feat_cols, channel,
                                                 sigma, rng, bler_df)
            rows.append(dict(channel=channel, sigma_db=sigma,
                             mean_f1=f1_m, std_f1=f1_s, mean_payload=pay))
            print(f'  {channel:8s} sigma={sigma:.1f} dB: F1={f1_m:.4f} ± {f1_s:.4f}  payload={pay:.4f}')

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT_DIR, 'results.csv'), index=False)

    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    for ch, c in (('awgn', 'tab:blue'), ('rayleigh', 'tab:orange')):
        sub = out[out['channel'] == ch].sort_values('sigma_db')
        ax.errorbar(sub['sigma_db'], sub['mean_f1'], yerr=sub['std_f1'],
                    marker='o', linewidth=2, capsize=4, label=ch.upper(),
                    color=c)
    ax.set_xlabel(r'SNR-estimation noise $\sigma$ (dB)')
    ax.set_ylabel(r'Mean realised frame F1 at $\gamma=10$ dB')
    ax.set_title('CSI-noise robustness of the deployed selector')
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'fig_csi_noise.png'), dpi=140)
    fig.savefig(os.path.join(OUT_DIR, 'fig_csi_noise.pdf'))
    print('wrote', OUT_DIR)


if __name__ == '__main__':
    main()
