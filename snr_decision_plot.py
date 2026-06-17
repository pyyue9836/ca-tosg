#self+ CA-TOSG paper2 v1: AWGN-only SNR sweep + 3 figs (decisions/F1/payload)
# -*- coding: utf-8 -*-
"""Killer figure for Paper #2: RF decision behaviour vs SNR.

For the trained CSI-aware RF, override the est_snr_db column to a constant
across all 1980 frames, sweep it from 0 to 20 dB, and plot:
  (a) fraction of frames where the RF picks LATE  (should rise as SNR drops)
  (b) mean realised F1 + mean payload (efficient-frontier curve)

This is the channel-adaptive story the comm-side reviewers want to see.

Run:
  /home/josh/miniconda3/envs/sionna310/bin/python peiyi_work/01_paper_ca_tosg/snr_decision_plot.py
"""
import os
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v1')
DATASET = os.path.join(RUN_DIR, 'dataset.csv')
BLER_CSV = os.path.join(
    REPO, 'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')

PAYLOAD_LATE = 0.024
PAYLOAD_COMP = 1.98
SNR_GRID = np.array([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20], dtype=float)


def bler_lookup(snr_db, bler_df, qam=16):
    sub = bler_df[bler_df['qam'] == qam].sort_values('snr_db')
    xs = sub['snr_db'].to_numpy(); ys = sub['bler'].to_numpy()
    return np.clip(np.interp(snr_db, xs, ys, left=1.0, right=0.0), 0.0, 1.0)


def evaluate_at_snr(df, rf, feat_cols, snr_db, bler_df):
    """Override CSI cue to snr_db, override effective_C_f1 too, run RF."""
    df = df.copy()
    df['est_snr_db'] = float(snr_db)
    bler = bler_lookup(float(snr_db), bler_df, qam=16)
    df['effective_compressed_f1'] = df['compressed_f1'] * (1.0 - bler)
    X = df[feat_cols]
    pred = rf.predict(X)
    frac_L = float((pred == 'late').mean())
    f1 = np.where(pred == 'compressed',
                  df['effective_compressed_f1'].to_numpy(),
                  df['late_f1'].to_numpy())
    payload = np.where(pred == 'compressed', PAYLOAD_COMP, PAYLOAD_LATE)

    # Reference oracle at this fixed SNR (channel-aware).
    oracle = np.where(df['effective_compressed_f1'] > df['late_f1'],
                      'compressed', 'late')
    frac_L_oracle = float((oracle == 'late').mean())
    f1_oracle = np.where(oracle == 'compressed',
                         df['effective_compressed_f1'].to_numpy(),
                         df['late_f1'].to_numpy())
    payload_oracle = np.where(oracle == 'compressed', PAYLOAD_COMP, PAYLOAD_LATE)

    return dict(
        snr_db=float(snr_db),
        rf_frac_L=frac_L, rf_mean_payload=float(payload.mean()),
        rf_mean_f1=float(f1.mean()),
        oracle_frac_L=frac_L_oracle, oracle_mean_payload=float(payload_oracle.mean()),
        oracle_mean_f1=float(f1_oracle.mean()),
        # fixed-C realised performance at this SNR (degrades with BLER):
        fixedC_mean_f1=float((df['compressed_f1'] * (1.0 - bler)).mean()),
        bler_16qam=float(bler),
    )


def main():
    df = pd.read_csv(DATASET)
    bler_df = pd.read_csv(BLER_CSV)

    with open(os.path.join(RUN_DIR, 'rf_csi.pkl'), 'rb') as f:
        rf = pickle.load(f)
    # Recover the exact feature columns the RF was trained on.
    feat_cols = list(rf.feature_names_in_) if hasattr(rf, 'feature_names_in_') \
        else None
    if feat_cols is None:
        raise RuntimeError('RF has no feature_names_in_ — retrain with sklearn'
                           ' >= 1.0 to get column names embedded.')

    rows = [evaluate_at_snr(df, rf, feat_cols, s, bler_df) for s in SNR_GRID]
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RUN_DIR, 'snr_sweep.csv'), index=False)
    print(out.to_string(index=False))

    # ---- Figure 1: P(pick LATE) vs SNR ----
    plt.figure(figsize=(5.5, 3.6))
    plt.plot(out['snr_db'], out['rf_frac_L'], 'o-', label='CSI-aware RF',
             linewidth=2)
    plt.plot(out['snr_db'], out['oracle_frac_L'], 's--', label='Channel-aware oracle',
             linewidth=2, alpha=0.7)
    plt.axhline(0.0, color='gray', linewidth=0.5)
    plt.axhline(1.0, color='gray', linewidth=0.5)
    plt.xlabel('Estimated SNR (dB)')
    plt.ylabel('Fraction of frames selecting L (object-level)')
    plt.title('Channel-adaptive selector behaviour')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RUN_DIR, 'fig_snr_vs_decisions.png'), dpi=140)
    plt.savefig(os.path.join(RUN_DIR, 'fig_snr_vs_decisions.pdf'))

    # ---- Figure 2: realised F1 vs SNR ----
    plt.figure(figsize=(5.5, 3.6))
    plt.plot(out['snr_db'], out['rf_mean_f1'], 'o-', label='CSI-aware RF',
             linewidth=2)
    plt.plot(out['snr_db'], out['oracle_mean_f1'], 's--',
             label='Channel-aware oracle', linewidth=2, alpha=0.7)
    plt.plot(out['snr_db'], out['fixedC_mean_f1'], '^:',
             label='Fixed C (no adapt)', linewidth=2, alpha=0.7)
    plt.axhline(df['late_f1'].mean(), color='black', linestyle=':',
                label='Fixed L (channel-invariant)')
    plt.xlabel('Estimated SNR (dB)')
    plt.ylabel('Mean realised frame F1')
    plt.title('Receiver-side F1 vs channel quality')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RUN_DIR, 'fig_snr_vs_f1.png'), dpi=140)
    plt.savefig(os.path.join(RUN_DIR, 'fig_snr_vs_f1.pdf'))

    # ---- Figure 3: payload vs SNR ----
    plt.figure(figsize=(5.5, 3.6))
    plt.plot(out['snr_db'], out['rf_mean_payload'], 'o-', label='CSI-aware RF',
             linewidth=2)
    plt.plot(out['snr_db'], out['oracle_mean_payload'], 's--',
             label='Channel-aware oracle', linewidth=2, alpha=0.7)
    plt.axhline(PAYLOAD_COMP, color='red', linestyle=':', label='Fixed C')
    plt.axhline(PAYLOAD_LATE, color='green', linestyle=':', label='Fixed L')
    plt.xlabel('Estimated SNR (dB)')
    plt.ylabel('Mean payload (Mbit / frame)')
    plt.title('Bandwidth consumption vs channel quality')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RUN_DIR, 'fig_snr_vs_payload.png'), dpi=140)
    plt.savefig(os.path.join(RUN_DIR, 'fig_snr_vs_payload.pdf'))

    print('\nwrote 3 figures to', RUN_DIR)


if __name__ == '__main__':
    main()
