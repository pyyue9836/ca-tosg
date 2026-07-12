#self+ CA-TOSG P1 Step-4: SNR curve of the feasibility-masked oracle action distribution.
# -*- coding: utf-8 -*-
"""Reads results/step4_oracle_action_dist_v3.csv and plots the oracle action mix vs Es/N0 for each
split x channel (3 splits rows x 2 channels cols). Shows the ~8 dB AWGN cliff and the Rayleigh
all-L collapse after the feasibility mask. Outputs results/step4_oracle_action_dist_v3.{pdf,png}.
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(HERE)
RESULTS = os.path.join(P1, 'results')
CSV = os.path.join(RESULTS, 'step4_oracle_action_dist_v3.csv')
SPLITS = ('validate', 'test', 'culver')
CHANNELS = ('awgn', 'rayleigh')

# fixed palette (mirror paper_style: L blue, C16 vermillion, C256 orange)
COL = {'frac_L': ('#0072B2', 'L (late)'), 'frac_C16': ('#D55E00', 'C16'),
       'frac_C256': ('#E69F00', 'C256')}


def main():
    df = pd.read_csv(CSV)
    fig, axes = plt.subplots(len(SPLITS), len(CHANNELS), figsize=(8.2, 8.4),
                             sharex=True, sharey=True)
    for i, sp in enumerate(SPLITS):
        for j, ch in enumerate(CHANNELS):
            ax = axes[i, j]
            s = df[(df.split == sp) & (df.channel == ch)].sort_values('snr_db')
            x = s['snr_db'].to_numpy()
            for col, (c, lab) in COL.items():
                ax.plot(x, s[col].to_numpy(), '-o', ms=3, lw=1.4, color=c, label=lab)
            ax.axvline(8, color='0.6', ls=':', lw=0.9)
            ax.set_ylim(-0.03, 1.03); ax.grid(True, alpha=0.3)
            if i == 0:
                ax.set_title(ch.upper(), fontsize=11)
            if j == 0:
                ax.set_ylabel(f'{sp}\naction fraction', fontsize=9)
            if i == len(SPLITS) - 1:
                ax.set_xlabel('Es/N0 (dB)', fontsize=9)
    axes[0, 0].legend(fontsize=8, loc='center left')
    fig.suptitle('Feasibility-masked oracle action distribution vs SNR '
                 '(dotted = 8 dB AWGN cliff)', fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    for ext in ('pdf', 'png'):
        out = os.path.join(RESULTS, f'step4_oracle_action_dist_v3.{ext}')
        fig.savefig(out, bbox_inches='tight', dpi=140 if ext == 'png' else None)
        print('wrote', out)


if __name__ == '__main__':
    main()
