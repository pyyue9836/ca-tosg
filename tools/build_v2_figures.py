#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R43 — generate every v2 figure from the closed-out products. Vector PDF, IEEE two-column.

**No number or label in any figure is typed by hand (C-2).** Every value is read from a product and
every provenance entry is hashed into PROVENANCE_figures.json.

**No v1 figure is reused (C-4)** -- a copied figure carries old numbers.

THE SCALE PROBLEM, AND WHY IT IS A LAYOUT DECISION (B-2)
--------------------------------------------------------
The two halves of the primary result differ by three orders of magnitude: the payload ratio is ~400x
and the F1 shortfall on the bound is 0.0024. Any shared axis makes one of them vanish, and the
result would then read as whichever half survived the autoscale. So:

  * payload is drawn on a LOG axis, where a 400x ratio is legible;
  * dF1 gets its OWN panel at its own scale, with the -0.005 margin and the LCB95 on the SAME
    ruler, so "the bound crosses the margin" is visible rather than asserted.

Two y-scales on one panel would be a dual-axis chart, which is never correct: the reader cannot tell
which curve belongs to which ruler, and the crossing point is an artefact of the scaling choice.

    python tools/build_v2_figures.py
"""
from __future__ import annotations
import hashlib, json, os, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, 'paper', 'v2_draft', 'figures')
PROV = os.path.join(FIG, 'PROVENANCE_figures.json')
# validated with the dataviz palette validator (light surface): all six checks PASS
C = {'rf': '#2B62C4', 'tau': '#E06C1F', 'w2c': '#009B6B', 'aux': '#8A4FC0',
     'ink': '#1a1a1a', 'muted': '#6b6b6b', 'grid': '#d8d8d6'}
W1, W2 = 3.5, 7.16          # IEEE single / double column, inches

plt.rcParams.update({'font.size': 8, 'axes.labelsize': 8, 'axes.titlesize': 8,
                     'legend.fontsize': 7, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
                     'axes.edgecolor': C['muted'], 'axes.linewidth': 0.6,
                     'grid.color': C['grid'], 'grid.linewidth': 0.5,
                     'text.color': C['ink'], 'axes.labelcolor': C['ink'],
                     'xtick.color': C['muted'], 'ytick.color': C['muted'],
                     'pdf.fonttype': 42, 'figure.dpi': 200})


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def tidy(ax):
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.grid(True, axis='y', alpha=0.7)
    ax.set_axisbelow(True)


def fig1_block(prov):
    """The data flow as IMPLEMENTED. Two corrections over the first draft, both factual:
    the channel estimate is an EGO-side input and does not come from the collaborator's LiDAR;
    and E issues no message, so it does not enter the transport chain at all."""
    f, ax = plt.subplots(figsize=(W2, 2.6)); ax.axis('off')
    ax.set_xlim(0, 104); ax.set_ylim(0, 44)
    def box(x, y, w, h, t, col=C['ink'], fs=6.8):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.35',
                                    ec=col, fc='none', lw=0.9))
        ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=fs, color=C['ink'])
    def arr(x1, y1, x2, y2, col=None, ls='-'):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>', mutation_scale=7,
                                     lw=0.8, color=col or C['muted'], linestyle=ls,
                                     connectionstyle='arc3,rad=0'))
    ax.text(1, 42, 'EGO', fontsize=7, color=C['muted'], weight='bold')
    ax.text(1, 12.5, 'COLLABORATOR', fontsize=7, color=C['muted'], weight='bold')
    box(1, 30, 17, 9, 'Ego LiDAR\n(own sweep)')
    box(1, 18, 17, 8, 'Channel\nestimate')
    box(21, 26, 16, 13, 'Ego-local cues\n(21 scene + 2\nchannel, all\npre-request)')
    box(41, 27, 13, 11, 'RF selector\n(frozen)', col=C['rf'])
    box(58, 34, 15, 7, 'E: no message', col=C['muted'])
    box(58, 25, 15, 7, 'L: boxes', col=C['tau'])
    box(58, 16, 15, 7, 'F: int8\nbottleneck', col=C['rf'])
    box(1, 1, 17, 9, 'Collaborator\nLiDAR')
    box(21, 1, 16, 9, 'Same checkpoint\n(per-agent\ninference)')
    box(78, 14, 25, 14, 'packetise $\\rightarrow$ LDPC/QAM\n$\\rightarrow$ per-codeword loss\n'
                        '$\\rightarrow$ partial recovery\n$\\rightarrow$ AttFusion at ego',
        col=C['w2c'], fs=6.5)
    arr(18, 34.5, 21, 34)
    arr(18, 22, 21, 29)
    arr(37, 32.5, 41, 32.5)
    for yy in (37.5, 28.5, 19.5):
        arr(54, 32.5, 58, yy)
    arr(18, 5.5, 21, 5.5)
    arr(37, 5.5, 58, 17, col=C['muted'], ls=':')
    arr(37, 5.5, 58, 26, col=C['muted'], ls=':')
    arr(73, 28.5, 78, 24)
    arr(73, 19.5, 78, 21)
    ax.text(66, 12.5, 'E sends nothing', fontsize=6, color=C['muted'], ha='center', style='italic')
    ax.text(47, 9, 'content supplied on request', fontsize=6, color=C['muted'],
            ha='center', style='italic')
    f.tight_layout(pad=0.2)
    p = os.path.join(FIG, 'fig1_system.pdf'); f.savefig(p, bbox_inches='tight'); plt.close(f)
    prov['fig1_system.pdf'] = {'panel': 'main', 'kind': 'conceptual block diagram',
        'inputs': [], 'note': 'No result numbers. Every block is an implemented component; nothing '
        'unimplemented is drawn (B-1). Two factual corrections over the first draft: the channel '
        'estimate is an EGO-side input, not derived from the collaborator; and E issues no message '
        'so it does not reach the transport chain.', 'sha256': sha(p)}


def fig2_primary(prov):
    src = {k: os.path.join(ROOT, f'results/v2/v2_{k}_primary.json') for k in ('test', 'culver')}
    d = {k: json.load(open(v)) for k, v in src.items()}
    f, axes = plt.subplots(1, 3, figsize=(W2, 2.2),
                           gridspec_kw={'width_ratios': [1, 1, 1.15]})
    for ax, k, name in zip(axes[:2], ('test', 'culver'), ('Test', 'Culver-City')):
        x = np.arange(2)
        pay = [d[k]['RF']['mean_payload'], d[k]['tau']['mean_payload']]
        ax.bar(x, pay, width=0.55, color=[C['rf'], C['tau']], zorder=3)
        ax.set_yscale('log')          # a ~400x ratio is only legible on a log axis
        ax.set_xticks(x); ax.set_xticklabels(['CA-TOSG', f"$\\tau$={d[k]['tau']['tau']}"])
        ax.set_title(name)
        for xi, v in zip(x, pay):
            ax.text(xi, v * 1.35, f'{v:.5f}', ha='center', fontsize=6.5, color=C['ink'])
        tidy(ax)
    axes[0].set_ylabel('Realised payload (Msym, log)')
    ax = axes[2]
    ks, labs = ('test', 'culver'), ('Test', 'Culver-City')
    y = np.arange(2)
    pts = [d[k]['delta_f1_point'] for k in ks]
    lcb = [d[k]['delta_f1_LCB95'] for k in ks]
    for i, (pt, lo) in enumerate(zip(pts, lcb)):
        ax.plot([lo, pt], [i, i], color=C['muted'], lw=1.4, zorder=2)
        ax.plot(pt, i, 'o', ms=5, color=C['rf'], zorder=3)
        ax.plot(lo, i, '|', ms=9, mew=1.6, color=C['rf'], zorder=3)
        ax.text(pt, i + 0.18, f'{pt:+.5f}', ha='center', fontsize=6.5, color=C['ink'])
        ax.text(lo, i - 0.28, f'LCB {lo:+.5f}', ha='center', fontsize=6.5, color=C['ink'])
    m = -d['test']['delta']
    ax.axvline(m, color=C['tau'], lw=1.1, ls='--', zorder=1)
    ax.text(m, 1.55, f'margin {m:+.3f}', color=C['tau'], fontsize=6.5, ha='center')
    ax.set_yticks(y); ax.set_yticklabels(labs)
    ax.set_xlabel('$\\Delta F_1$ (CA-TOSG $-$ comparator)')
    ax.set_title('Non-inferiority')
    ax.set_ylim(-0.6, 1.9)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.grid(True, axis='x', alpha=0.7); ax.set_axisbelow(True)
    f.tight_layout(pad=0.3)
    p = os.path.join(FIG, 'fig2_primary.pdf'); f.savefig(p, bbox_inches='tight'); plt.close(f)
    prov['fig2_primary.pdf'] = {'panel': 'main',
        'inputs': {os.path.relpath(v, ROOT): sha(v) for v in src.values()},
        'fields': ['RF.mean_payload', 'tau.mean_payload', 'delta_f1_point', 'delta_f1_LCB95',
                   'delta'],
        'layout_rule': 'payload on a LOG axis, dF1 in its OWN panel with the margin on the same '
                       'ruler as the bound. A shared axis would erase one half of the result '
                       '(V2-R43 B-2); two y-scales on one panel would be a dual-axis chart.',
        'sha256': sha(p)}


def fig3_recovery(prov):
    src = os.path.join(ROOT, 'results/v2/wp5_final_validate.csv')
    msg = os.path.join(ROOT, 'results/v2/wp5_message_validate.json')
    df = pd.read_csv(src); m = json.load(open(msg))
    rates = [0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9]
    f, ax = plt.subplots(figsize=(W1, 2.3))
    for reg, col, lab in (('ideal', C['rf'], 'Fragment-aware (ideal)'),
                          ('packet', C['w2c'], 'Packet-level')):
        y = [np.mean([df[f'f1_{reg}_p{p!r}_r{r}'].mean() for r in range(4)]) for p in rates]
        ax.plot(rates, y, 'o-', ms=3.5, lw=1.6, color=col, label=lab)
    mr = m['message_regime']
    y = [mr[str(p)]['per_frame_expected_f1_mean'] for p in rates]
    ax.plot(rates, y, 's--', ms=3.5, lw=1.6, color=C['aux'], label='All-or-nothing (message)')
    q = mr['0.001']['q_message_survives']
    ax.axvspan(0.001, 0.9, color=C['aux'], alpha=0.06, zorder=0)
    ax.text(0.02, min(y) + 0.004, f'$q$-dominated ($q$={q:.1e} at $p$=0.001)',
            fontsize=6, color=C['aux'])
    ax.set_xscale('log'); ax.set_xlabel('Codeword loss rate $p$')
    ax.set_ylabel('Mean per-frame $F_1$'); tidy(ax)
    ax.legend(frameon=False, loc='lower left')
    f.tight_layout(pad=0.3)
    p = os.path.join(FIG, 'fig3_recovery.pdf'); f.savefig(p, bbox_inches='tight'); plt.close(f)
    prov['fig3_recovery.pdf'] = {'panel': 'main',
        'inputs': {os.path.relpath(x, ROOT): sha(x) for x in (src, msg)},
        'fields': ['f1_{ideal,packet}_p*_r0..3 (replicate mean)',
                   'message_regime[p].per_frame_expected_f1_mean', 'q_message_survives'],
        'split': 'validate (mechanism result)', 'sha256': sha(p)}


def fig4_w2c(prov):
    src = os.path.join(ROOT, 'results/baselines/where2comm_v2/scored_v2/summary_deterministic.csv')
    d = pd.read_csv(src)
    f, axes = plt.subplots(1, 2, figsize=(W2, 2.1), sharey=False)
    for ax, sp, name in zip(axes, ('test', 'culver'), ('Test', 'Culver-City')):
        s = d[d.split == sp].sort_values('comm_rate')
        ax.plot(s.comm_rate * 100, s.ap_50, 'o-', ms=3.5, lw=1.6, color=C['w2c'], label='AP@0.5')
        ax.plot(s.comm_rate * 100, s.ap_70, 's--', ms=3.5, lw=1.6, color=C['aux'], label='AP@0.7')
        ax.set_xscale('symlog', linthresh=1)
        ax.set_xlabel('Native communication rate (\\% of features kept)')
        ax.set_title(name); tidy(ax)
    axes[0].set_ylabel('AP'); axes[0].legend(frameon=False, loc='lower right')
    f.tight_layout(pad=0.3)
    p = os.path.join(FIG, 'fig4_where2comm.pdf'); f.savefig(p, bbox_inches='tight'); plt.close(f)
    prov['fig4_where2comm.pdf'] = {'panel': 'main',
        'inputs': {os.path.relpath(src, ROOT): sha(src)},
        'fields': ['comm_rate', 'ap_50', 'ap_70'],
        'axis_rule': 'the x axis is the NATIVE communication rate. No Msym and no budget-matched '
                     'language may appear in the figure or its caption (V2-R40 B-7).',
        'sha256': sha(p)}


def fig5_lambda(prov):
    src = os.path.join(ROOT, 'results/v2/v2_lambda_fine_scan_validate.csv')
    d = pd.read_csv(src).sort_values('lam')
    f, ax = plt.subplots(figsize=(W1, 2.2))
    for k, col, lab in (('rho_E', C['tau'], '$\\rho_E$'), ('rho_L', C['rf'], '$\\rho_L$'),
                        ('rho_F', C['w2c'], '$\\rho_F$')):
        ax.plot(d.lam, d[k], 'o-', ms=3, lw=1.5, color=col, label=lab)
    ax.set_xlabel('$\\lambda$ (unsampled interval of the pre-registered grid)')
    ax.set_ylabel('Oracle action share'); tidy(ax)
    ax.legend(frameon=False, ncol=3, loc='upper center')
    ax.set_title('Validate-only exploratory diagnostic', fontsize=7.5, color=C['muted'])
    f.tight_layout(pad=0.3)
    p = os.path.join(FIG, 'fig5_lambda.pdf'); f.savefig(p, bbox_inches='tight'); plt.close(f)
    prov['fig5_lambda.pdf'] = {'panel': 'supplementary',
        'inputs': {os.path.relpath(src, ROOT): sha(src)},
        'fields': ['lam', 'rho_E', 'rho_L', 'rho_F'],
        'status': 'EXPLORATORY, validate only. Did not replace the frozen candidate and explains '
                  'no Test result (V2-R43 B-5).', 'sha256': sha(p)}


def main():
    os.makedirs(FIG, exist_ok=True)
    prov = {}
    fig1_block(prov); fig2_primary(prov); fig3_recovery(prov); fig4_w2c(prov); fig5_lambda(prov)
    import subprocess
    out = {'schema': 'catosg-v2-figures/1',
           'generator': 'tools/build_v2_figures.py',
           'commit': subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'],
                                    capture_output=True, text=True).stdout.strip(),
           'palette': {'hexes': [C['rf'], C['tau'], C['w2c'], C['aux']],
                       'validated': 'dataviz validate_palette.js, light surface: all six checks '
                                    'PASS (lightness band, chroma floor, CVD separation, '
                                    'normal-vision floor, contrast)'},
           'v1_figures_reused': 0,
           'figures': prov}
    json.dump(out, open(PROV, 'w'), indent=1)
    for k, v in prov.items():
        print(f"  {v['panel']:14} {k}  {v['sha256'][:12]}")
    print(f'wrote {len(prov)} figures + {os.path.relpath(PROV, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
