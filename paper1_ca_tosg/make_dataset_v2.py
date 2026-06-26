#self+ CA-TOSG paper2 v2: build channel-aware oracle dataset (AWGN+Rayleigh, 3-way L/C16/C256) — main version
# -*- coding: utf-8 -*-
"""V2 dataset: 3-way action set (L / C-16 / C-256) over AWGN + Rayleigh.

Adds two upgrades over v1:
  1. THIRD ACTION 'C-256': same 1.98 Mbit information payload as C-16 but
     half the channel uses (256-QAM = 8 bits/symbol vs 16-QAM = 4 bits/sym),
     at the cost of higher BLER. Selector now picks between
        L       (0.024 Mbit eq., near-error-free)
        C-16    (1.98 Mbit eq., robust)
        C-256   (0.99 Mbit eq., fragile)
  2. RAYLEIGH CHANNEL via numerical fading-average of the AWGN BLER table.
     For each mean SNR gamma_bar, BLER_rayleigh = E_gamma[BLER_awgn(gamma)]
     with gamma ~ Exponential(gamma_bar).

Per-frame, we sample (snr_db, channel) and pre-compute the effective F1 for
every action, then label the channel-aware oracle as the argmax.

Output: peiyi_work/01_paper_ca_tosg/runs/v2/dataset.csv
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
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2')
SEED = 0

# Channel-use-equivalent payload (Mbit), accounting for QAM spectral efficiency.
# Both C variants carry the same 1.98 Mbit perception payload, but C-256 uses
# half the symbols (8 bits/sym vs 4 bits/sym). L stays at 0.024 Mbit info.
PAYLOAD_INFO = {'L': 0.024, 'C16': 1.98, 'C256': 1.98}
SPEC_EFF = {'L': 1.0, 'C16': 4.0, 'C256': 8.0}  # bits / channel use
CHANNEL_USES = {a: PAYLOAD_INFO[a] / SPEC_EFF[a] for a in PAYLOAD_INFO}  # Mbit-eq.


def bler_awgn_interp(snr_db, bler_df, qam):
    sub = bler_df[bler_df['qam'] == qam].sort_values('snr_db')
    xs = sub['snr_db'].to_numpy(); ys = sub['bler'].to_numpy()
    return np.clip(np.interp(snr_db, xs, ys, left=1.0, right=0.0), 0.0, 1.0)


def bler_rayleigh(snr_db_mean, bler_df, qam, n_grid=400):
    """Numerically average AWGN BLER over instantaneous Rayleigh SNR.

    gamma ~ Exponential(gamma_bar=10^(snr_db_mean/10)); integrate
    BLER_awgn(10*log10(gamma)) * pdf(gamma) dgamma.
    """
    snr_db_mean = np.atleast_1d(snr_db_mean).astype(float)
    out = np.zeros_like(snr_db_mean)
    sub = bler_df[bler_df['qam'] == qam].sort_values('snr_db')
    xs = sub['snr_db'].to_numpy(); ys = sub['bler'].to_numpy()
    for i, gb_db in enumerate(snr_db_mean):
        gb = 10.0 ** (gb_db / 10.0)
        # gamma grid spanning the BLER table range, with extra tails.
        g_db_grid = np.linspace(-15.0, 40.0, n_grid)
        g_lin = 10.0 ** (g_db_grid / 10.0)
        bler_g = np.clip(np.interp(g_db_grid, xs, ys, left=1.0, right=0.0),
                         0.0, 1.0)
        pdf = (1.0 / gb) * np.exp(-g_lin / gb)
        # change of variable dgamma = gamma * ln(10) / 10 * d(gamma_db)
        jac = g_lin * np.log(10) / 10.0
        out[i] = np.trapz(bler_g * pdf * jac, g_db_grid)
    return np.clip(out, 0.0, 1.0)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(CUE_CSV)
    bler = pd.read_csv(BLER_CSV)
    print('cue CSV:', df.shape)

    # Per-frame draws: SNR (0-20 dB uniform) and channel type (50/50 AWGN/Rayl).
    snr_db = rng.uniform(0.0, 20.0, size=len(df))
    channel = rng.choice(['awgn', 'rayleigh'], size=len(df))
    df['est_snr_db'] = snr_db
    df['channel_type'] = channel
    df['channel_is_rayleigh'] = (channel == 'rayleigh').astype(int)

    # Pre-compute BLER per QAM order per channel (vectorise AWGN; loop Rayleigh).
    bler_C16_awgn = bler_awgn_interp(snr_db, bler, qam=16)
    bler_C256_awgn = bler_awgn_interp(snr_db, bler, qam=256)
    bler_C16_ray = bler_rayleigh(snr_db, bler, qam=16)
    bler_C256_ray = bler_rayleigh(snr_db, bler, qam=256)

    is_ray = (channel == 'rayleigh')
    df['bler_C16'] = np.where(is_ray, bler_C16_ray, bler_C16_awgn)
    df['bler_C256'] = np.where(is_ray, bler_C256_ray, bler_C256_awgn)

    df['eff_f1_L'] = df['late_f1']
    df['eff_f1_C16'] = df['compressed_f1'] * (1.0 - df['bler_C16'])
    df['eff_f1_C256'] = df['compressed_f1'] * (1.0 - df['bler_C256'])

    f1_stack = df[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy()
    action_names = np.array(['L', 'C16', 'C256'])
    df['oracle_3way'] = action_names[np.argmax(f1_stack, axis=1)]

    # Sanity report.
    print('per-action win rates (oracle 3-way):')
    for a in action_names:
        print('  %-6s %.3f' % (a, (df['oracle_3way'] == a).mean()))
    print('mean BLER (16-QAM): AWGN=%.3f  Rayleigh=%.3f'
          % (bler_C16_awgn.mean(), bler_C16_ray.mean()))
    print('mean BLER (256-QAM): AWGN=%.3f  Rayleigh=%.3f'
          % (bler_C256_awgn.mean(), bler_C256_ray.mean()))

    out_path = os.path.join(OUT_DIR, 'dataset.csv')
    df.to_csv(out_path, index=False)
    print('wrote', out_path, df.shape)


if __name__ == '__main__':
    main()
