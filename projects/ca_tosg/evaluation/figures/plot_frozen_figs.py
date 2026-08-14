#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-7 (D): Figs. 4, 5, 6 and 8, all drawn from `results/main/frozen_curves.csv`.

Each figure writes a PROVENANCE file listing **every number it actually drew** that also appears in
a caption or in the body text. `tools/check_figure_consistency.py` then compares those against
`paper/main.tex`, so "the figure, its caption and the text agree" is checked rather than asserted.

Figures produced (all at the pre-registered confirmatory budget B_max = 0.20 unless stated):
  fig_ap50_{awgn,rayleigh}.pdf   F1 vs SNR: CA-TOSG, Fixed L, Fixed F, ceiling, masked oracle
  fig_payload_awgn.pdf           channel use vs SNR
  fig_decisions_{awgn,rayleigh}.pdf   rho_F / rho_L overlay vs that budget's lambda-penalised oracle
  fig_stacked_area.pdf           rho_E / rho_L / rho_F stacked, AWGN + Rayleigh panels
  fig_decisions_budgets.pdf      the three budgets side by side (appendix)
  fig_pareto_test.pdf            payload-F1 plane, x-axis reaching past Fixed F (0.99)

    python projects/ca_tosg/evaluation/figures/plot_frozen_figs.py
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                                    # noqa: E402
import numpy as np                                                 # noqa: E402
import pandas as pd                                                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
CURVES = os.path.join(ROOT, 'results/main/frozen_curves.csv')
REPLAY = os.path.join(ROOT, 'results/main/replay_summary.csv')
FIXED = os.path.join(ROOT, 'results/main/fixed_references.csv')
FIGDIR = os.path.join(ROOT, 'paper/figures')
PROVDIR = os.path.join(ROOT, 'results/provenance')

MAIN_BUDGET = 0.20
MAIN_SPLIT = 'validate'
KNEE_DB = 10.0
drawn: dict[str, float] = {}          # every number this module puts on paper


def note(key, value):
    drawn[key] = round(float(value), 4)
    return value


def _style(ax, xlabel, ylabel, title=None):
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    if title:
        ax.set_title(title, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.25, lw=0.4)


def fig_f1_vs_snr(cv):
    for ch in ('awgn', 'rayleigh'):
        d = cv[(cv.channel == ch) & (cv.split == MAIN_SPLIT) & (cv.budget == MAIN_BUDGET)]
        fig, ax = plt.subplots(figsize=(3.4, 2.5))
        for pol, lab, kw in (('fixed_L', r'Fixed $L$', dict(ls='--', c='tab:green')),
                             ('fixed_F', r'Fixed $F$', dict(ls='--', c='tab:red')),
                             ('feature_ceiling', 'Perfect-channel ceiling',
                              dict(ls=':', c='0.35')),
                             ('oracle_masked', 'Masked oracle', dict(ls='-.', c='tab:purple')),
                             ('catosg', r'\textsc{CA-TOSG}'.replace('\\textsc{', '').replace('}', ''),
                              dict(ls='-', c='tab:blue', lw=2))):
            g = d[d.policy == pol].sort_values('snr_db')
            ax.plot(g.snr_db, g.f1, label=lab, **kw)
        if ch == 'awgn':
            ax.axvline(KNEE_DB, c='0.6', lw=0.8, ls=':')
            ax.annotate(f'policy knee {KNEE_DB:.0f} dB', (KNEE_DB, ax.get_ylim()[0]),
                        xytext=(2, 4), textcoords='offset points', fontsize=6, color='0.35')
        _style(ax, 'Es/N0 (dB)', 'Realised effective F1',
               f'{ch.upper()}, {MAIN_SPLIT}, $B_{{\\max}}={MAIN_BUDGET:.2f}$')
        ax.legend(fontsize=6, frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(FIGDIR, f'fig_ap50_{ch}.pdf'))
        plt.close(fig)
        c = d[d.policy == 'catosg'].sort_values('snr_db')
        note(f'f1_catosg_{ch}_low', c[c.snr_db < KNEE_DB].f1.iloc[0])
        note(f'f1_catosg_{ch}_high', c[c.snr_db >= KNEE_DB].f1.iloc[-1])
    d = cv[(cv.channel == 'awgn') & (cv.split == MAIN_SPLIT) & (cv.budget == MAIN_BUDGET)]
    note('f1_fixedL_validate', d[d.policy == 'fixed_L'].f1.iloc[0])
    note('f1_ceiling_validate', d[d.policy == 'feature_ceiling'].f1.iloc[0])
    note('f1_oracle_masked_validate_high',
         d[(d.policy == 'oracle_masked') & (d.snr_db >= KNEE_DB)].f1.iloc[-1])


def fig_payload_vs_snr(cv):
    d = cv[(cv.channel == 'awgn') & (cv.split == MAIN_SPLIT) & (cv.budget == MAIN_BUDGET)]
    fig, ax = plt.subplots(figsize=(4.2, 2.5))
    for pol, lab, kw in (('fixed_F', r'Fixed $F$ (0.99)', dict(ls='--', c='tab:red')),
                         ('fixed_L', r'Fixed $L$ (0.024)', dict(ls='--', c='tab:green')),
                         ('oracle_lambda', r'$\lambda$-penalised oracle',
                          dict(ls='-.', c='tab:purple')),
                         ('catosg', 'CA-TOSG', dict(ls='-', c='tab:blue', lw=2))):
        g = d[d.policy == pol].sort_values('snr_db')
        ax.plot(g.snr_db, g.payload_msym, label=lab, **kw)
    ax.axvline(KNEE_DB, c='0.6', lw=0.8, ls=':')
    _style(ax, 'Es/N0 (dB)', 'Channel use (Msym/frame)',
           f'AWGN, {MAIN_SPLIT}, $B_{{\\max}}={MAIN_BUDGET:.2f}$')
    ax.legend(fontsize=6, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGDIR, 'fig_payload_awgn.pdf'))
    plt.close(fig)
    c = d[d.policy == 'catosg'].sort_values('snr_db')
    note('payload_catosg_awgn_low', c[c.snr_db < KNEE_DB].payload_msym.iloc[0])
    note('payload_catosg_awgn_high', c[c.snr_db >= KNEE_DB].payload_msym.iloc[0])


def fig_decisions(cv):
    for ch in ('awgn', 'rayleigh'):
        d = cv[(cv.channel == ch) & (cv.split == MAIN_SPLIT) & (cv.budget == MAIN_BUDGET)]
        fig, ax = plt.subplots(figsize=(3.4, 2.4))
        for pol, ls, lab in (('catosg', '-', 'selector'), ('oracle_lambda', '--',
                                                           r'$\lambda$-penalised oracle')):
            g = d[d.policy == pol].sort_values('snr_db')
            ax.plot(g.snr_db, g.rho_L, ls, c='tab:green', lw=1.6 if pol == 'catosg' else 1.0,
                    label=rf'$\rho_L$ {lab}')
            ax.plot(g.snr_db, g.rho_F, ls, c='tab:blue', lw=1.6 if pol == 'catosg' else 1.0,
                    label=rf'$\rho_F$ {lab}')
        if ch == 'awgn':
            ax.axvline(KNEE_DB, c='0.6', lw=0.8, ls=':')
        ax.set_ylim(-0.03, 1.03)
        _style(ax, 'Es/N0 (dB)', 'Selection ratio',
               f'{ch.upper()}, {MAIN_SPLIT}, $B_{{\\max}}={MAIN_BUDGET:.2f}$')
        ax.legend(fontsize=5.5, frameon=False, ncol=2)
        fig.tight_layout()
        fig.savefig(os.path.join(FIGDIR, f'fig_decisions_{ch}.pdf'))
        plt.close(fig)


def fig_stacked(cv):
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.4), sharey=True)
    for ax, ch in zip(axes, ('awgn', 'rayleigh')):
        d = cv[(cv.channel == ch) & (cv.split == MAIN_SPLIT) &
               (cv.budget == MAIN_BUDGET) & (cv.policy == 'catosg')].sort_values('snr_db')
        ax.stackplot(d.snr_db, d.rho_E, d.rho_L, d.rho_F,
                     labels=[r'$\rho_E$', r'$\rho_L$', r'$\rho_F$'],
                     colors=['tab:orange', 'tab:green', 'tab:blue'], alpha=0.85)
        if ch == 'awgn':
            ax.axvline(KNEE_DB, c='k', lw=0.9, ls=':')
            ax.annotate(f'{KNEE_DB:.0f} dB', (KNEE_DB, 1.02), fontsize=6, ha='center')
        ax.set_ylim(0, 1)
        _style(ax, 'Es/N0 (dB)', 'Action share' if ch == 'awgn' else '',
               f'{ch.upper()}, $B_{{\\max}}={MAIN_BUDGET:.2f}$')
    axes[0].legend(fontsize=6, frameon=False, loc='center left')
    fig.tight_layout()
    fig.savefig(os.path.join(FIGDIR, 'fig_stacked_area.pdf'))
    plt.close(fig)
    for sp in ('test', 'culver'):
        r = cv[(cv.split == sp) & (cv.budget == MAIN_BUDGET) & (cv.channel == 'rayleigh') &
               (cv.snr_db == KNEE_DB)]
        note(f'rho_E_oracle_rayleigh_{sp}', r[r.policy == 'oracle_masked'].rho_E.iloc[0])
        note(f'rho_E_catosg_rayleigh_{sp}', r[r.policy == 'catosg'].rho_E.iloc[0])
    for sp in ('validate', 'test', 'culver'):
        g = cv[(cv.split == sp) & (cv.budget == MAIN_BUDGET) & (cv.channel == 'awgn') &
               (cv.policy == 'catosg') & (cv.snr_db == KNEE_DB)]
        note(f'rho_F_at_knee_{sp}', g.rho_F.iloc[0])


def fig_budgets_appendix(cv):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.3), sharey=True)
    for ax, b in zip(axes, sorted(cv.budget.unique())):
        d = cv[(cv.channel == 'awgn') & (cv.split == MAIN_SPLIT) & (cv.budget == b) &
               (cv.policy == 'catosg')].sort_values('snr_db')
        ax.stackplot(d.snr_db, d.rho_E, d.rho_L, d.rho_F,
                     colors=['tab:orange', 'tab:green', 'tab:blue'], alpha=0.85,
                     labels=[r'$\rho_E$', r'$\rho_L$', r'$\rho_F$'])
        ax.axvline(KNEE_DB, c='k', lw=0.9, ls=':')
        ax.set_ylim(0, 1)
        _style(ax, 'Es/N0 (dB)', 'Action share' if b == min(cv.budget) else '',
               f'$B_{{\\max}}={b:.2f}$')
    axes[0].legend(fontsize=6, frameon=False, loc='center left')
    fig.tight_layout()
    fig.savefig(os.path.join(FIGDIR, 'fig_decisions_budgets.pdf'))
    plt.close(fig)


def fig_pareto():
    rep = pd.read_csv(REPLAY)
    rep = rep[rep['split'] == 'test'].copy()
    for c in ('budget', 'F1_RF', 'F1_tau', 'B_RF', 'B_tau'):
        rep[c] = rep[c].astype(float)
    fx = pd.read_csv(FIXED)
    fx = fx[fx.split == 'test'].set_index('policy')

    fig, ax = plt.subplots(figsize=(4.0, 2.9))
    for pol, lab, m, c in (('Fixed-L', r'Fixed $L$', 's', 'tab:green'),
                           ('Fixed-C256', r'Fixed $C_{256}$', 'v', 'tab:brown'),
                           ('Fixed-F', r'Fixed $F$', 'D', 'tab:red')):
        ax.scatter(fx.loc[pol].payload_msym, fx.loc[pol].F1, marker=m, c=c, s=42, label=lab,
                   zorder=3)
        note(f'pareto_{pol}_payload', fx.loc[pol].payload_msym)
        note(f'pareto_{pol}_f1', fx.loc[pol].F1)
    ax.scatter(fx.loc['oracle'].payload_msym, fx.loc['oracle'].F1, marker='*', s=130,
               c='tab:purple', label='Masked oracle', zorder=4)
    note('pareto_oracle_payload', fx.loc['oracle'].payload_msym)
    note('pareto_oracle_f1', fx.loc['oracle'].F1)
    ax.scatter(rep.B_RF, rep.F1_RF, marker='o', s=48, c='tab:blue', label='CA-TOSG (frozen)',
               zorder=5)
    ax.scatter(rep.B_tau, rep.F1_tau, marker='^', s=44, facecolors='none',
               edgecolors='tab:orange', label=r'budget-matched $\tau^\star$', zorder=5)
    for _, r in rep.iterrows():
        ax.annotate(f'{r.budget:.2f}', (r.B_RF, r.F1_RF), xytext=(3, 4),
                    textcoords='offset points', fontsize=6, color='tab:blue')
        note(f'pareto_catosg_B{int(r.budget*100):03d}_payload', r.B_RF)
        note(f'pareto_catosg_B{int(r.budget*100):03d}_f1', r.F1_RF)
    ax.set_xlim(0, 1.08)                      # Fixed F at 0.99 MUST be inside the axes
    _style(ax, 'Channel use (Msym/frame)', 'Mean realised F1',
           'OPV2V test, frozen replay (200 realisations)')
    ax.legend(fontsize=6, frameon=False, loc='lower right')
    fig.tight_layout()
    fig.savefig(os.path.join(FIGDIR, 'fig_pareto_test.pdf'))
    plt.close(fig)


def main():
    os.makedirs(FIGDIR, exist_ok=True)
    os.makedirs(PROVDIR, exist_ok=True)
    cv = pd.read_csv(CURVES)
    fig_f1_vs_snr(cv)
    fig_payload_vs_snr(cv)
    fig_decisions(cv)
    fig_stacked(cv)
    fig_budgets_appendix(cv)
    fig_pareto()
    drawn['knee_db'] = KNEE_DB
    drawn['_source'] = 0                                    # placeholder, kept numeric-free below
    prov = {k: v for k, v in drawn.items() if not k.startswith('_')}
    with open(os.path.join(PROVDIR, 'PROVENANCE_figures.json'), 'w') as f:
        json.dump({'schema': 'catosg-figure-provenance/1',
                   'generated_by': 'python projects/ca_tosg/evaluation/figures/plot_frozen_figs.py',
                   'sources': ['results/main/frozen_curves.csv',
                               'results/main/replay_summary.csv',
                               'results/main/fixed_references.csv'],
                   'budget': MAIN_BUDGET, 'split_for_snr_figures': MAIN_SPLIT,
                   'numbers_drawn': prov}, f, indent=1)
        f.write('\n')
    for k, v in sorted(prov.items()):
        print(f'  {k:38s} {v}')
    print(f'\nwrote {len(prov)} drawn numbers -> results/provenance/PROVENANCE_figures.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
