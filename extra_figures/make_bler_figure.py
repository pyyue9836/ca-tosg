#self+ Peiyi: channel-model figure — LDPC+QAM BLER vs SNR (AWGN solid, Rayleigh dashed)
"""
Plots the BLER cliffs that drive the selector: 16-QAM vs 256-QAM under LDPC 1/2,
AWGN (solid, from the empirical table) and Rayleigh (dashed, fading-averaged with
the same integral used in test_split_pipeline/03_build_test_dataset.py).
Shows (i) the AWGN knee that the selector tracks, (ii) the 256-QAM cliff sitting
far to the right of 16-QAM (the dominance argument), (iii) Rayleigh degrading so
badly that feature-level transmission is never worthwhile -> selector stays at L.
Output: paper/figures/fig_channel_bler.pdf
"""
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paper_style as PS; PS.apply()
BLER_CSV = os.path.join(REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/paper/figures/fig_channel_bler.pdf')


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
    df = pd.read_csv(BLER_CSV)
    snr = np.linspace(0, 20, 201)

    fig, ax = plt.subplots(figsize=(PS.COL, 2.7))
    ax.plot(snr, bler_awgn(snr, df, 16),  '-',  color=PS.C_C16, lw=1.6,
            label='16-QAM, AWGN')
    ax.plot(snr, bler_awgn(snr, df, 256), '-',  color=PS.C_C256, lw=1.6,
            label='256-QAM, AWGN')
    ax.plot(snr, bler_rayleigh(snr, df, 16),  '--', color=PS.C_C16, lw=1.6,
            label='16-QAM, Rayleigh')
    ax.plot(snr, bler_rayleigh(snr, df, 256), '--', color=PS.C_C256, lw=1.6,
            label='256-QAM, Rayleigh')

    # mark the AWGN 16-QAM knee region the selector tracks (~12-14 dB)
    ax.axvspan(12, 14, color='0.85', zorder=0)
    ax.text(13, 0.55, 'selector\nknee', ha='center', va='center', fontsize=7,
            color='0.35')

    ax.set_xlabel('SNR (dB)')
    ax.set_ylabel('Block error rate (BLER)')
    ax.set_xlim(0, 20)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc='center right', framealpha=0.9)
    fig.tight_layout()
    fig.savefig(OUT, bbox_inches='tight')
    fig.savefig(OUT.replace('.pdf', '_preview.png'), bbox_inches='tight', dpi=140)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
