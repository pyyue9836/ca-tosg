#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fig_difficulty.pdf <- results/sensitivity/difficulty_frozen.csv. CSV in, PDF out. Nothing else.

R69-1: this drawing code lived inside `projects/ca_tosg/evaluation/difficulty_frozen.py`, which is
the *computation* -- it opens `data/p2/p2_grid_{split}.csv`, the frozen `selector_B0XX.pkl` and
`FROZEN_MANIFEST.json`, all of them git-excluded. Redrawing the delivered figure therefore required
the artefact tier, so `python tools/generate_figures.py difficulty` could not run on a clean clone at
all: a figure whose data is committed was not reproducible from the committed tree.

The split is the fix. `difficulty_frozen.py` still owns the CSV and needs its artefacts; this file
owns the PDF and needs only the committed CSV. It imports nothing from the evaluation package -- not
`deployment`, not the manifest loader -- because importing the compute side back in would quietly
restore the dependency this split exists to remove.

    python projects/ca_tosg/evaluation/figures/plot_difficulty_frozen.py
    python tools/generate_figures.py difficulty          # the driver's own entry
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..', '..'))
IN_CSV = os.path.join(ROOT, 'results/sensitivity/difficulty_frozen.csv')
OUT_FIG = os.path.join(ROOT, 'paper/archive/figures/fig_difficulty.pdf')
STRATA = ('easy', 'medium', 'hard')


def figure(df, path, split, budget):
    """Draw the three-stratum bar chart. The condition in the title is READ FROM THE CSV, never
    passed in: a caption that says 'AWGN 16 dB' while the rows were computed at another condition is
    exactly the class of error the figure-consistency gate exists for."""
    d = df[(df.split == split) & (df.budget == budget)]
    if d.empty:
        raise SystemExit(f'no rows for split={split} budget={budget} in {IN_CSV}')
    channel = str(d.channel.iloc[0])
    snr_db = float(d.snr_db.iloc[0])
    if d.channel.nunique() != 1 or d.snr_db.nunique() != 1:
        raise SystemExit(f'{split} B={budget}: rows span more than one (channel, SNR) condition')
    d = d.set_index('stratum').loc[list(STRATA)]

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    x = np.arange(len(STRATA))
    w = 0.27
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    ax.bar(x - w, d.f1_fixedL, w, label=r'Fixed $L$')
    ax.bar(x, d.f1_catosg, w, label='CA-TOSG')
    ax.bar(x + w, d.f1_oracle, w, label='Oracle')
    for i, g in enumerate(d.gain_catosg_minus_L):
        ax.text(i, max(d.f1_catosg.iloc[i], d.f1_fixedL.iloc[i]) + 0.004,
                f'{g:+.4f}', ha='center', fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([s.capitalize() for s in STRATA])
    ax.set_xlabel('Frame difficulty (ego object-level F1 tercile)')
    ax.set_ylabel('Realised F1')
    ax.set_title(f'{channel.upper()} {int(snr_db)} dB, {split}, '
                 rf'$B_{{\max}}={budget:.2f}$', fontsize=8)
    ax.legend(fontsize=7, frameon=False)
    lo = min(d.f1_fixedL.min(), d.f1_catosg.min())
    ax.set_ylim(lo - 0.02, d.f1_oracle.max() + 0.02)
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return channel, snr_db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='test')
    ap.add_argument('--budget', type=float, default=0.20)
    args = ap.parse_args()
    if not os.path.exists(IN_CSV):
        raise SystemExit(f'{os.path.relpath(IN_CSV, ROOT)} is missing -- run '
                         'projects/ca_tosg/evaluation/difficulty_frozen.py (artefact tier) first')
    df = pd.read_csv(IN_CSV)
    channel, snr_db = figure(df, OUT_FIG, args.split, args.budget)
    print(f'wrote {os.path.relpath(OUT_FIG, ROOT)} '
          f'({args.split}, B_max={args.budget:.2f}, {channel} {int(snr_db)} dB) '
          f'<- {os.path.relpath(IN_CSV, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
