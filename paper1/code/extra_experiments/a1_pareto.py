#self+ A1 v3 (PLOTTER ONLY): Pareto frontier figure from the 200-realisation engine outputs.
# -*- coding: utf-8 -*-
"""RULE (supervisor 2026-07-12): every number that appears anywhere in the paper is 200-realisation.
This script no longer COMPUTES anything from a single frozen draw -- it only PLOTS the Lagrangian
frontier + policy points already produced (200-realisation averaged) by recompute_policy_200seed.py:
  results/policy_v3/frontier_{split}.csv   (lambda, payload, f1, frac_C256/C16/L)
  results/policy_v3/pareto_points.csv      (Fixed L/C16/C256, oracle, clairvoyant, RF, tau, blind)
Outputs paper/figures/fig_pareto_{validate,test,culver}.pdf (+ _preview.png).
"""
import os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(os.path.dirname(HERE))
POL = os.path.join(P1, 'results/policy_v3'); FIGDIR = os.path.join(P1, 'paper/figures')
os.makedirs(FIGDIR, exist_ok=True)
try:
    sys.path.insert(0, os.path.join(P1, 'code')); import paper_style as PS; PS.apply()
except Exception:
    PS = None

MARK = {'Fixed L': ('s', '#0072B2'), 'Fixed C16': ('^', '#D55E00'),
        'Fixed C256': ('v', '#E69F00'), 'Oracle (ch-aware, masked)': ('*', '#009E73'),
        'CA-TOSG (RF, deployed)': ('D', '#7B3FA0'),
        'Clairvoyant (post-hoc, samples block)': ('P', '0.35'),
        'SNR-threshold (best tau)': ('X', '#CC79A7')}


def plot_split(name, front, pts):
    fig, ax = plt.subplots(figsize=(6.0, 3.5))
    ax.plot(front['payload'], front['f1'], '-', lw=1.4, color='0.4', zorder=1,
            label='Lagrangian oracle frontier (200-real.)')
    for _, row in pts.iterrows():
        pol = row['policy']
        if pol in ('Channel-blind EU (->Fixed-L)',):
            continue
        m, c = MARK.get(pol, ('o', 'k'))
        ax.scatter([row['payload']], [row['f1']], marker=m, c=c,
                   s=110 if m == '*' else 60, zorder=4, edgecolors='k', linewidths=0.5, label=pol)
    ax.set_xscale('log'); ax.set_xlabel('Average payload (Mbit/frame, log)')
    ax.set_ylabel('Mean realised F1'); ax.grid(True, alpha=0.3, which='both')
    ax.legend(fontsize=6.5, loc='center left', bbox_to_anchor=(1.01, 0.5))
    ax.set_title(f'OPV2V {name} (200 channel realisations)', fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIGDIR, f'fig_pareto_{name}.pdf')
    fig.savefig(out, bbox_inches='tight'); fig.savefig(out.replace('.pdf', '_preview.png'), dpi=140, bbox_inches='tight')
    print('wrote', out)


def main():
    pareto = pd.read_csv(os.path.join(POL, 'pareto_points.csv'))
    for name in ('validate', 'test', 'culver'):
        front = pd.read_csv(os.path.join(POL, f'frontier_{name}.csv'))
        pts = pareto[pareto.split == name]
        plot_split(name, front, pts)


if __name__ == '__main__':
    main()
