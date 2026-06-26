#self+ CA-TOSG paper2 v2: dual-channel SNR sweep + 6 figs
# -*- coding: utf-8 -*-
"""V2 figures: 3-way (L/C16/C256) decision behaviour over AWGN + Rayleigh.

For the trained CSI+channel-aware RF, override est_snr_db and channel_type
to fixed values per sweep point and plot:
  * Fig 6 equiv:  fraction of frames per action vs SNR, AWGN
  * Fig 7 equiv:  same under Rayleigh
  * Realised F1 vs SNR for all policies (fixed L/C16/C256, oracle, RF)
  * Bandwidth (channel-use Mbit eq.) vs SNR
"""
import os
import pickle

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import paper_style as _ps; _ps.apply()
import numpy as np
import pandas as pd


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2')
DATASET = os.path.join(RUN_DIR, 'dataset.csv')
BLER_CSV = os.path.join(REPO,
                       'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')

PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}
SNR_GRID = np.array([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20], dtype=float)
ACTIONS = ['L', 'C16', 'C256']
COLOURS = {'L': 'tab:green', 'C16': 'tab:blue', 'C256': 'tab:orange'}


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


def override_channel(df, snr_db, channel, bler_df):
    df = df.copy()
    df['est_snr_db'] = float(snr_db)
    df['channel_is_rayleigh'] = int(channel == 'rayleigh')
    bler_fn = bler_rayleigh if channel == 'rayleigh' else bler_awgn
    b16 = bler_fn(snr_db, bler_df, 16)
    b256 = bler_fn(snr_db, bler_df, 256)
    df['bler_C16'] = b16
    df['bler_C256'] = b256
    df['eff_f1_C16'] = df['compressed_f1'] * (1.0 - b16)
    df['eff_f1_C256'] = df['compressed_f1'] * (1.0 - b256)
    df['eff_f1_L'] = df['late_f1']
    return df


def sweep(df, rf, feat_cols, bler_df, channel):
    rows = []
    for snr in SNR_GRID:
        d = override_channel(df, snr, channel, bler_df)
        pred = rf.predict(d[feat_cols])
        oracle = np.array(ACTIONS)[np.argmax(
            d[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy(), axis=1)]
        rf_pay, rf_f1 = realised(d, pred)
        or_pay, or_f1 = realised(d, oracle)
        row = dict(snr_db=float(snr), channel=channel,
                   rf_pay=rf_pay, rf_f1=rf_f1,
                   oracle_pay=or_pay, oracle_f1=or_f1)
        for a in ACTIONS:
            row['rf_frac_' + a] = float((pred == a).mean())
            row['oracle_frac_' + a] = float((oracle == a).mean())
        # Fixed-policy realised F1 at this SNR.
        for a in ACTIONS:
            fa = np.array([a] * len(d))
            _, f1a = realised(d, fa)
            row['fixed_' + a + '_f1'] = f1a
        rows.append(row)
    return pd.DataFrame(rows)


def plot_decisions(df_sw, channel, save_path):
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    for a in ACTIONS:
        ax.plot(df_sw['snr_db'], df_sw['rf_frac_' + a], 'o-',
                color=COLOURS[a], label='RF %s' % a, linewidth=2)
        ax.plot(df_sw['snr_db'], df_sw['oracle_frac_' + a], 's--',
                color=COLOURS[a], alpha=0.5, linewidth=1.2,
                label='Oracle %s' % a)
    ax.set_xlabel('Estimated SNR (dB)')
    ax.set_ylabel('Fraction of frames')
    ax.set_title('3-way selector behaviour — %s' % channel.upper())
    ax.set_ylim(-0.02, 1.02)
    ax.grid(alpha=0.3); ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=140)
    fig.savefig(save_path.replace('.png', '.pdf'))


def plot_f1(df_sw, channel, save_path):
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    ax.plot(df_sw['snr_db'], df_sw['rf_f1'], 'o-', linewidth=2,
            label='CSI+channel-aware RF', color='tab:red')
    ax.plot(df_sw['snr_db'], df_sw['oracle_f1'], 's--', linewidth=2,
            alpha=0.7, label='Channel-aware oracle (3-way)', color='black')
    ax.plot(df_sw['snr_db'], df_sw['fixed_C16_f1'], '^:', linewidth=1.6,
            label='Fixed C-16', color=COLOURS['C16'])
    ax.plot(df_sw['snr_db'], df_sw['fixed_C256_f1'], 'v:', linewidth=1.6,
            label='Fixed C-256', color=COLOURS['C256'])
    ax.axhline(df_sw['fixed_L_f1'].mean(), color=COLOURS['L'],
               linestyle=':', label='Fixed L')
    ax.set_xlabel('Estimated SNR (dB)')
    ax.set_ylabel('Mean realised frame F1')
    ax.set_title('F1 vs SNR — %s' % channel.upper())
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=140)
    fig.savefig(save_path.replace('.png', '.pdf'))


def plot_payload(df_sw, channel, save_path):
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    ax.plot(df_sw['snr_db'], df_sw['rf_pay'], 'o-', linewidth=2,
            label='RF policy', color='tab:red')
    ax.plot(df_sw['snr_db'], df_sw['oracle_pay'], 's--', linewidth=2,
            alpha=0.7, label='Channel-aware oracle', color='black')
    for a in ACTIONS:
        ax.axhline(PAYLOAD[a], color=COLOURS[a], linestyle=':',
                   label='Fixed %s = %.3f' % (a, PAYLOAD[a]))
    ax.set_yscale('log')
    ax.set_xlabel('Estimated SNR (dB)')
    ax.set_ylabel('Mean payload (Mbit channel-use eq., log)')
    ax.set_title('Bandwidth vs SNR — %s' % channel.upper())
    ax.grid(alpha=0.3, which='both'); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=140)
    fig.savefig(save_path.replace('.png', '.pdf'))


def main():
    df = pd.read_csv(DATASET)
    bler_df = pd.read_csv(BLER_CSV)
    with open(os.path.join(RUN_DIR, 'rf_full.pkl'), 'rb') as f:
        rf = pickle.load(f)
    feat_cols = list(rf.feature_names_in_)
    print('feature cols (%d):' % len(feat_cols))
    for c in feat_cols: print(' ', c)

    for ch in ('awgn', 'rayleigh'):
        sw = sweep(df, rf, feat_cols, bler_df, ch)
        sw.to_csv(os.path.join(RUN_DIR, 'snr_sweep_%s.csv' % ch), index=False)
        print('\n%s sweep:' % ch.upper())
        cols = ['snr_db'] + ['rf_frac_' + a for a in ACTIONS] + \
               ['rf_f1', 'oracle_f1', 'rf_pay']
        print(sw[cols].round(3).to_string(index=False))
        plot_decisions(sw, ch,
                       os.path.join(RUN_DIR, 'fig_decisions_%s.png' % ch))
        plot_f1(sw, ch, os.path.join(RUN_DIR, 'fig_f1_%s.png' % ch))
        plot_payload(sw, ch, os.path.join(RUN_DIR, 'fig_payload_%s.png' % ch))

    print('\nwrote 6 figures to', RUN_DIR)


if __name__ == '__main__':
    main()
