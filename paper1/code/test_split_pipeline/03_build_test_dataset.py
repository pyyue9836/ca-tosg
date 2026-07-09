#self+ Test-split pipeline 03: build the channel-aware oracle dataset on test split (random SNR + channel assignments + BLER-degraded effective F1 + 3-way oracle labels); mirrors make_dataset_v2.py but reads test cues
"""
Adds est_snr_db, channel_is_rayleigh, BLER-based effective F1 columns and
the 3-way oracle label to test_frame_features.csv. Same logic as
make_dataset_v2.py but operating on the test split.

Output: runs/test_dataset.csv
"""
import os
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

RUNS = 'runs' if 'culver' not in os.environ.get('CATOSG_SPLIT', 'test') else 'runs_culver'
IN_CSV = os.path.join(REPO,
    f'peiyi_work/01_paper_ca_tosg/test_split_pipeline/{RUNS}/test_frame_features.csv')
BLER_CSV = os.path.join(REPO,
    'peiyi_work/04_experiment_logs/baseline_csvs/'
    '..')  # placeholder; corrected below
BLER_CSV = os.path.join(REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT_CSV = os.path.join(REPO,
    f'peiyi_work/01_paper_ca_tosg/test_split_pipeline/{RUNS}/test_dataset.csv')

SEED = 0


def bler_awgn(snr_db, df, qam):
    sub = df[df['qam'] == qam].sort_values('snr_db')
    return np.clip(np.interp(snr_db, sub['snr_db'], sub['bler'],
                              left=1.0, right=0.0), 0.0, 1.0)


def bler_rayleigh(snr_db_mean, df, qam, n_grid=400):
    snr_db_mean = np.atleast_1d(snr_db_mean).astype(float)
    out = np.zeros_like(snr_db_mean)
    sub = df[df['qam'] == qam].sort_values('snr_db')
    xs = sub['snr_db'].to_numpy(); ys = sub['bler'].to_numpy()
    for i, gb_db in enumerate(snr_db_mean):
        gb = 10.0 ** (gb_db / 10.0)
        g_db = np.linspace(-15.0, 40.0, n_grid)
        g_lin = 10.0 ** (g_db / 10.0)
        bler_g = np.clip(np.interp(g_db, xs, ys, left=1.0, right=0.0), 0.0, 1.0)
        pdf = (1.0 / gb) * np.exp(-g_lin / gb)
        jac = g_lin * np.log(10) / 10.0
        out[i] = np.trapz(bler_g * pdf * jac, g_db)
    return np.clip(out, 0.0, 1.0)


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(IN_CSV)
    bler = pd.read_csv(BLER_CSV)
    print(f'test cue CSV: {df.shape}')

    snr_db = rng.uniform(0.0, 20.0, size=len(df))
    channel = rng.choice(['awgn', 'rayleigh'], size=len(df))
    df['est_snr_db'] = snr_db
    df['channel_type'] = channel
    df['channel_is_rayleigh'] = (channel == 'rayleigh').astype(int)

    b16_a = bler_awgn(snr_db, bler, 16)
    b256_a = bler_awgn(snr_db, bler, 256)
    b16_r = bler_rayleigh(snr_db, bler, 16)
    b256_r = bler_rayleigh(snr_db, bler, 256)

    is_r = (channel == 'rayleigh')
    df['bler_C16'] = np.where(is_r, b16_r, b16_a)
    df['bler_C256'] = np.where(is_r, b256_r, b256_a)
    df['eff_f1_L'] = df['late_f1']
    df['eff_f1_C16'] = df['compressed_f1'] * (1.0 - df['bler_C16'])
    df['eff_f1_C256'] = df['compressed_f1'] * (1.0 - df['bler_C256'])

    f1_stack = df[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy()
    actions = np.array(['L', 'C16', 'C256'])
    df['oracle_3way'] = actions[np.argmax(f1_stack, axis=1)]

    print('per-action oracle win rates on TEST split:')
    for a in actions:
        print(f'  {a:5s}  {(df["oracle_3way"] == a).mean():.3f}')

    df.to_csv(OUT_CSV, index=False)
    print(f'wrote {OUT_CSV}')


if __name__ == '__main__':
    main()
