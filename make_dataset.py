#self+ CA-TOSG paper2 v1: build channel-aware oracle dataset (AWGN only, 2-way L/C)
# -*- coding: utf-8 -*-
"""Build the channel-aware oracle dataset for Paper #2.

Loads the existing 1980-frame cue CSV (60+ hand-crafted cues + late_f1 +
compressed_f1), samples a per-frame SNR (uniform over the training range),
looks up 16-QAM LDPC BLER at that SNR, computes
    effective_compressed_f1 = compressed_f1 * (1 - BLER(SNR))
and writes the channel-aware oracle label
    channel_oracle = 'compressed' if effective_compressed_f1 > late_f1 else 'late'

Output: peiyi_work/01_paper_ca_tosg/runs/v1/dataset.csv  (one row per frame, with extra SNR
and oracle columns appended).

Run:
  /home/josh/miniconda3/envs/sionna310/bin/python peiyi_work/01_paper_ca_tosg/make_dataset.py
"""
import os
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARCHIVE = '/home/josh/cooperative_semantic_perception/OpenCOOD_cleanup_archive_20260604'

CUE_CSV = os.path.join(
    ARCHIVE, 'peiyi_work/04_experiment_logs/experiment_logs/semantic_value',
    'frame_level_semantic_value_with_dataloader_pcd.csv')
BLER_CSV = os.path.join(
    REPO, 'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v1')
SEED = 0


def bler_lookup(snr_db, bler_df, qam=16):
    """Piecewise-linear interpolation of BLER vs SNR at a fixed QAM order."""
    sub = bler_df[bler_df['qam'] == qam].sort_values('snr_db')
    xs = sub['snr_db'].to_numpy()
    ys = sub['bler'].to_numpy()
    return np.clip(np.interp(snr_db, xs, ys, left=1.0, right=0.0), 0.0, 1.0)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = np.random.default_rng(SEED)

    df = pd.read_csv(CUE_CSV)
    bler = pd.read_csv(BLER_CSV)
    print('cue CSV   :', df.shape, '(frames x cols)')
    print('BLER table:', bler.shape)

    # Per-frame estimated SNR (uniform 0-20 dB, matching SComCP training range).
    snr_db = rng.uniform(0.0, 20.0, size=len(df))
    df['est_snr_db'] = snr_db
    df['bler_16qam'] = bler_lookup(snr_db, bler, qam=16)

    # Channel-aware effective C F1 and oracle label.
    df['effective_compressed_f1'] = df['compressed_f1'] * (1.0 - df['bler_16qam'])
    df['channel_oracle'] = np.where(
        df['effective_compressed_f1'] > df['late_f1'], 'compressed', 'late')

    # Sanity report.
    p_C = (df['channel_oracle'] == 'compressed').mean()
    p_C_no_ch = (df['compressed_f1'] > df['late_f1']).mean()
    mean_bler = df['bler_16qam'].mean()
    print('p(oracle = C) without channel  = %.3f' % p_C_no_ch)
    print('p(oracle = C) with channel     = %.3f  (mean BLER = %.3f)'
          % (p_C, mean_bler))

    out_path = os.path.join(OUT_DIR, 'dataset.csv')
    df.to_csv(out_path, index=False)
    print('wrote', out_path, '(%d rows x %d cols)' % df.shape)


if __name__ == '__main__':
    main()
