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
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import paper_style as _ps; _ps.apply()
import pandas as pd

P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(P1, 'paper/figures')
V3 = os.path.join(P1, 'results/true_e2e_v3/true_e2e_global_v3_validate.csv')  # deployed selector rho_L per SNR


def _v3_shares(channel):
    d = pd.read_csv(V3)
    d = d[(d.policy == 'CA-TOSG') & (d.channel == channel)].copy()
    d['snr_db'] = pd.to_numeric(d['snr_db']); d = d.sort_values('snr_db')
    d['rf_frac_L'] = d['rho_L']
    d['rf_frac_C16'] = 1.0 - d['rho_L']          # feature action = C16 (selector never requests C256)
    d['rf_frac_C256'] = 0.0                       # C256 = 0 at the deployed point; assert -- premise, not comment
    assert (d['rf_frac_C256'] == 0).all(), 'C256 share must be 0 (selector never requests C256); rho_C16=1-rho_L premise'
    return d


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
    df_a = _v3_shares('awgn')                     # v3: derived from true_e2e_v3 rho_L (C256 layer drawn = zero)
    df_r = _v3_shares('rayleigh')

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
