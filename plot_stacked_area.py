#self+ CA-TOSG paper2: stacked-area rho_s vs SNR (AWGN + Rayleigh side-by-side)
# -*- coding: utf-8 -*-
"""Stacked-area selection ratio versus SNR, AWGN + Rayleigh side-by-side.

Visualises rho_L, rho_C16, rho_C256 as a stacked area chart, the canonical
"channel-adaptive policy" diagnostic.
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_figures')


def plot_side(ax, df, title):
    ax.stackplot(df['snr_db'],
                  df['rf_frac_L'], df['rf_frac_C16'], df['rf_frac_C256'],
                  labels=['L  (object-level)', 'C$_{16}$  (16-QAM feature)',
                          'C$_{256}$  (256-QAM feature)'],
                  colors=['#82B366', '#6C8EBF', '#D79B00'],
                  alpha=0.85, edgecolor='black', linewidth=0.4)
    ax.set_xlim(df['snr_db'].min(), df['snr_db'].max())
    ax.set_ylim(0, 1)
    ax.set_xlabel('SNR (dB)')
    ax.set_ylabel(r'Selection ratio $\rho_s$')
    ax.set_title(title)
    ax.grid(alpha=0.3)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df_a = pd.read_csv(os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/snr_sweep_awgn.csv'))
    df_r = pd.read_csv(os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/snr_sweep_rayleigh.csv'))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    plot_side(ax1, df_a, 'AWGN')
    plot_side(ax2, df_r, 'Rayleigh')
    ax2.legend(loc='lower right', fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'fig_stacked_area.png'), dpi=140)
    fig.savefig(os.path.join(OUT_DIR, 'fig_stacked_area.pdf'))
    print('wrote', os.path.join(OUT_DIR, 'fig_stacked_area.pdf'))


if __name__ == '__main__':
    main()
