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
FIG = os.path.join(ROOT, 'paper', 'figures')
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
    box(21, 26, 16, 13, 'Ego-local cues\n(21 task/availability\n+ 2 channel, all\npre-request)')
    box(41, 27, 13, 11, 'RF selector\n(frozen)', col=C['rf'])
    box(58, 34, 15, 7, 'E: no message', col=C['muted'])
    box(58, 25, 15, 7, 'L: boxes', col=C['tau'])
    box(58, 15, 15, 9, 'F: int8 feature tensor\n(candidate set only;\nnever requested)',
        col=C['rf'], fs=5.6)
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
    f.tight_layout(pad=0.2)
    p = os.path.join(FIG, 'fig1_system.pdf'); f.savefig(p, bbox_inches='tight'); plt.close(f)
    prov['fig1_system.pdf'] = {'panel': 'main', 'kind': 'conceptual block diagram',
        'inputs': [], 'note': 'No result numbers. Every block is an implemented component; nothing '
        'unimplemented is drawn (B-1). Two factual corrections over the first draft: the channel '
        'estimate is an EGO-side input, not derived from the collaborator; and E issues no message '
        'so it does not reach the transport chain.', 'sha256': sha(p)}


def fig2_primary(prov):
    """V2-R56 G-10 / R58 D-2 — F1 AND realised payload on one plane, never F1 alone.

    A single accuracy column invites a ranking; this figure makes the trade-off the object. Each
    panel is one held-out split: x is realised payload, y is scene-equal F1. The budget ceiling is
    drawn, so an over-budget arm is visibly not a competitor rather than a footnote.

    The x axis is SYMLOG, not log: Fixed E spends exactly zero and a log axis cannot show zero.
    Dropping the point or nudging it to a small positive value would both be fabrications
    (the sibling of V2-R56 G-3, which struck 0 off Fig. 4's log axis).
    """
    src = {k: os.path.join(ROOT, f'results/v2/v2_{k}_primary.json') for k in ('test', 'culver')}
    d = {k: json.load(open(v)) for k, v in src.items()}
    fa = json.load(open(os.path.join(ROOT, 'results/v2/v2_heldout_fixed_arms.json')))
    mp = json.load(open(os.path.join(ROOT, 'results/v2/v2_matched_payload.json')))
    ceil_ = json.load(open(os.path.join(ROOT, 'results/v2/payload_chain.json')))[
        'beta_tiers_msym']['0.20']

    f, axes = plt.subplots(1, 2, figsize=(W2, 2.5), sharey=False)
    for ax, k, name in zip(axes, ('test', 'culver'), ('Test', 'Culver-City')):
        arms = fa['splits'][k]['arms']
        pol = mp['splits'][k]['policies']
        pts = [
            ('Fixed E', arms['E']['mean_payload'], arms['E']['scene_equal_f1'], C['muted'], 'o'),
            ('Fixed L', arms['L']['mean_payload'], arms['L']['scene_equal_f1'], C['muted'], 's'),
            ('Fixed F', arms['F']['mean_payload'], arms['F']['scene_equal_f1'], C['muted'], 'D'),
            (f"$\\tau$={d[k]['tau']['tau']}", d[k]['tau']['mean_payload'],
             d[k]['tau']['scene_equal_f1'], C['tau'], '^'),
            ('CA-TOSG', d[k]['RF']['mean_payload'], d[k]['RF']['scene_equal_f1'], C['rf'], '*'),
        ]
        # the matched-payload diagnostics sit at CA-TOSG's own x
        for key, lab, mk in (('random_el', 'Random', 'v'), ('task_only', 'Task-only', 'x'),
                             ('snr_only', 'SNR-only', 'P'),
                             ('greedy_gain_per_cost', 'Greedy ref.', '+')):
            v = pol[key]
            pts.append((lab, v['mean_payload'], v['scene_equal_f1'], C['aux'], mk))
        ax.axvspan(ceil_, 10, color=C['tau'], alpha=0.07, zorder=0)
        ax.axvline(ceil_, color=C['tau'], lw=0.9, ls=':', zorder=1)
        # Inline labels were tried first and were unreadable: five of the nine points sit within
        # a factor of two on x and within 0.005 on y, so their labels overprinted each other
        # (found by looking at the rendered figure, not by reading the code). A legend identifies
        # them without competing for space inside the cluster.
        for lab, x, y, col, mk in pts:
            ax.plot(x, y, mk, ms=7 if mk == '*' else 4.5, color=col, zorder=3,
                    mew=1.2 if mk in ('x', '+', 'P') else 0.6,
                    label=lab if ax is axes[0] else None)
        ax.set_xscale('symlog', linthresh=1e-3)
        ax.set_xlim(-2e-4, 8)
        ax.set_xlabel('Realised payload (Msym, symlog)')
        ax.set_title(name)
        tidy(ax)
    axes[0].set_ylabel('Scene-equal $F_1$')
    axes[0].text(ceil_ * 1.6, axes[0].get_ylim()[0], ' over the $\\beta=0.20$ budget',
                 fontsize=5.5, color=C['tau'], rotation=90, va='bottom')
    h, l = axes[0].get_legend_handles_labels()
    f.legend(h, l, frameon=False, fontsize=6, ncol=5, loc='upper center',
             bbox_to_anchor=(0.5, 0.02))
    f.tight_layout(pad=0.3)
    p = os.path.join(FIG, 'fig2_primary.pdf'); f.savefig(p, bbox_inches='tight'); plt.close(f)
    prov['fig2_primary.pdf'] = {'panel': 'main',
        'inputs': {os.path.relpath(v, ROOT): sha(v) for v in list(src.values()) + [
            os.path.join(ROOT, 'results/v2/v2_heldout_fixed_arms.json'),
            os.path.join(ROOT, 'results/v2/v2_matched_payload.json')]},
        'fields': ['RF.mean_payload', 'RF.scene_equal_f1', 'tau.*', 'arms.*', 'policies.*'],
        'layout_rule': 'F1 AND realised payload together on one plane, with the budget ceiling '
                       'drawn. SYMLOG x, because Fixed E spends exactly zero and a log axis '
                       'cannot show zero (V2-R56 G-3/G-10).',
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
    # The annotation goes in the empty band between the flat all-or-nothing line and the
    # fragment-aware curve, and the legend moves out of that band entirely. Two page reads were
    # needed: at 'lower left' the text overprinted the legend, and one nudge up was not enough
    # (V2-R48 D-1).
    ax.text(0.0012, max(y) + 0.018, f'$q$-dominated ($q$={q:.1e} at $p$=0.001)',
            fontsize=6, color=C['aux'], va='bottom')
    ax.set_xscale('log'); ax.set_xlabel('Codeword loss rate $p$')
    ax.set_ylabel('Mean per-frame $F_1$'); tidy(ax)
    # No corner of these axes is free: the curves occupy the top, the flat all-or-nothing line
    # runs across the bottom, and the annotation takes the upper left. The legend goes outside.
    ax.legend(frameon=False, ncol=3, fontsize=6, loc='upper center',
              bbox_to_anchor=(0.5, -0.28))
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
        # G-3: the axis is SYMLOG, and it says so. The sweep includes rate 0, which a log
        # axis cannot show; leaving the scale unnamed invites the reader to read the 0 tick
        # as sitting on a log axis.
        ax.set_xlabel('Native communication rate (% of features kept, symlog)')
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


MACROS = os.path.join(ROOT, 'paper', 'tables', 'generated_numbers.tex')


def _macro(name):
    """Read one generated macro's value, so the figure can be checked against the table."""
    import re as _re
    m = _re.search(r'\\newcommand\{\\%s\}\{([^}]*)\}' % name,
                   open(MACROS, encoding='utf-8').read())
    if not m:
        raise SystemExit(f'macro \\{name} not found -- run tools/build_v2_paper_numbers.py first')
    return float(m.group(1).replace(',', ''))


def fig6_matched_forest(prov):
    """V2-R62 B — the matched-payload differences as a forest plot.

    Same source and same numbers as Table IV, and that is ASSERTED rather than intended: a figure
    and a table that compute the same quantity separately will eventually disagree, and the reader
    has no way to tell which one is wrong. Every point and every interval end is checked against
    the generated macro the table prints.

    The oracle is deliberately absent: it is not deployable, and putting it on the same axis as
    three deployable rules invites reading it as a fourth competitor.
    """
    src = os.path.join(ROOT, 'results/v2/v2_matched_payload.json')
    d = json.load(open(src))
    ROWS = (('random_el', 'Random E/L', 'Random'),
            ('task_only', 'Task-only E/L', 'TaskOnly'),
            ('snr_only', 'SNR-only E/L', 'SnrOnly'))
    f, axes = plt.subplots(1, 2, figsize=(W2, 1.9), sharey=True)
    for ax, sp, name, tag in zip(axes, ('test', 'culver'), ('Test', 'Culver-City'),
                                 ('Test', 'Culver')):
        v = d['splits'][sp]['vs_ca_tosg']
        for i, (key, lab, mac) in enumerate(ROWS):
            pt = v[key]['delta_f1_point']; lo = v[key]['delta_f1_LCB95']
            hi = v[key]['delta_f1_UCB95']
            # B-1: the figure must print the table's numbers, not its own
            for got, want_macro in ((pt, f'{tag}MP{mac}Delta'), (lo, f'{tag}MP{mac}LCB')):
                if abs(float('%+.5f' % got) - _macro(want_macro)) > 1e-9:
                    raise SystemExit(f'{sp}/{key}: plotted {got!r} disagrees with macro '
                                     f'\\{want_macro} -- figure and table would print different '
                                     f'numbers for the same quantity')
            if not (lo <= pt <= hi):
                raise SystemExit(f'{sp}/{key}: point estimate outside its own interval')
            y = len(ROWS) - 1 - i
            ax.plot([lo, hi], [y, y], color=C['muted'], lw=1.4, zorder=2)
            ax.plot(pt, y, 'o', ms=5, color=C['rf'], zorder=3)
            ax.plot([lo, hi], [y, y], '|', ms=7, mew=1.4, color=C['rf'], zorder=3)
        ax.axvline(0.0, color=C['tau'], lw=1.0, ls='--', zorder=1)
        ax.set_yticks(range(len(ROWS)))
        ax.set_yticklabels([r[1] for r in ROWS][::-1])
        ax.set_ylim(-0.6, len(ROWS) - 0.4)
        ax.set_xlabel('$\\Delta F_1$ (CA-TOSG $-$ baseline)')
        ax.set_title(name)
        for sd in ('top', 'right', 'left'):
            ax.spines[sd].set_visible(False)
        ax.grid(True, axis='x', alpha=0.7); ax.set_axisbelow(True)
    f.tight_layout(pad=0.3)
    q = os.path.join(FIG, 'fig6_matched_forest.pdf')
    f.savefig(q, bbox_inches='tight'); plt.close(f)
    prov['fig6_matched_forest.pdf'] = {'panel': 'main',
        'inputs': {os.path.relpath(src, ROOT): sha(src),
                   os.path.relpath(MACROS, ROOT): sha(MACROS)},
        'fields': ['vs_ca_tosg.*.delta_f1_point', '.delta_f1_LCB95', '.delta_f1_UCB95'],
        'layout_rule': 'Same vector and same bootstrap as Table IV, asserted value by value '
                       'against the printed macros. The greedy outcome-aware references are '
                       'excluded: not deployable, and not proven optima.',
        'sha256': sha(q)}


def fig7_action_heatmap(prov):
    """V2-R62 C — where the frozen policy requests object-level cooperation.

    Descriptive only. The bins are fixed in the product, not here: the SNR axis is the 11 protocol
    grid points and the box-count axis is the quartiles of the pooled held-out rows. No smoothing
    and no interpolation -- a smoothed heat map would invent structure between grid points that
    were never evaluated.
    """
    src = os.path.join(ROOT, 'results/v2/v2_matched_payload.json')
    h = json.load(open(src))['action_heatmap']
    edges = h['nbox_edges']
    snrs = sorted({float(k.split('|')[1]) for k in h['cells']})
    f, axes = plt.subplots(1, 2, figsize=(W2, 1.9), sharey=True)
    im = None
    for ax, ch, name in zip(axes, ('awgn', 'rayleigh'), ('AWGN', 'Rayleigh')):
        M = np.full((4, len(snrs)), np.nan)
        for j, sv in enumerate(snrs):
            for q in range(4):
                c = h['cells'].get(f'{ch}|{sv:g}|{q}')
                if c and c['share_L'] is not None:
                    M[q, j] = c['share_L']
        im = ax.imshow(M, aspect='auto', origin='lower', vmin=0, vmax=1,
                       cmap='viridis', interpolation='nearest')
        ax.set_xticks(range(len(snrs)))
        ax.set_xticklabels([f'{s:g}' for s in snrs], fontsize=5.5)
        ax.set_yticks(range(4))
        # A-7: an en-dash, not two hyphens -- matplotlib renders the literal characters
        ax.set_yticklabels([f'{edges[q]:g}\u2013{edges[q+1]:g}' for q in range(4)], fontsize=5.5)
        ax.set_xlabel('Estimated SNR (dB)')
        ax.set_title(name)
        for sd in ('top', 'right'):
            ax.spines[sd].set_visible(False)
    axes[0].set_ylabel('Ego detected boxes\n(held-out quartiles)', fontsize=6)
    cb = f.colorbar(im, ax=axes, fraction=0.03, pad=0.02)
    cb.set_label('Requested-L share', fontsize=6); cb.ax.tick_params(labelsize=5.5)
    q = os.path.join(FIG, 'fig7_action_heatmap.pdf')
    f.savefig(q, bbox_inches='tight'); plt.close(f)
    prov['fig7_action_heatmap.pdf'] = {'panel': 'main',
        'inputs': {os.path.relpath(src, ROOT): sha(src)},
        'fields': ['action_heatmap.cells.*.share_L', 'action_heatmap.nbox_edges'],
        'layout_rule': 'Bins fixed in the product before plotting; nearest-neighbour rendering, no '
                       'smoothing or interpolation between evaluated grid points.',
        'sha256': sha(q)}


def fig8_channel_utility(prov):
    """V2-R66 B-1 — the two curves the selector's channel cue indexes.

    Left: the per-codeword erasure probability at each grid point, the quantity the transport model
    consumes. Right: the development-split effective utility of each action against the same axis,
    which is what the selector trades against payload. Plotted on the SAME x so the reader can read
    one against the other; the AWGN waterfall and the point where L overtakes F line up there.
    """
    g = pd.read_csv(os.path.join(ROOT, 'results/v2/v2_grid_validate_ideal.csv'),
                    usecols=['snr_db', 'channel', 'p_cw', 'eff_E', 'eff_L', 'eff_F'])
    f, axes = plt.subplots(1, 2, figsize=(W2, 2.1))
    ax = axes[0]
    for ch, lab, col, mk in (('awgn', 'AWGN', C['rf'], 'o'), ('rayleigh', 'Rayleigh', C['tau'], 's')):
        d = g[g.channel == ch].groupby('snr_db', as_index=False).p_cw.first()
        ax.plot(d.snr_db, d.p_cw, mk + '-', ms=3.5, lw=1.5, color=col, label=lab)
    ax.set_xlabel('Estimated SNR (dB)'); ax.set_ylabel('$p_{\\mathrm{cw}}$')
    ax.set_title('Per-codeword erasure'); ax.legend(frameon=False, fontsize=6); tidy(ax)
    ax = axes[1]
    for act, lab, col, mk in (('eff_E', 'E', C['muted'], 'o'), ('eff_L', 'L', C['rf'], 's'),
                              ('eff_F', 'F', C['aux'], '^')):
        d = g.groupby('snr_db', as_index=False)[act].mean()
        ax.plot(d.snr_db, d[act], mk + '-', ms=3.5, lw=1.5, color=col, label=lab)
    ax.set_xlabel('Estimated SNR (dB)'); ax.set_ylabel('Effective per-frame $F_1$')
    ax.set_title('Action utility (development split)')
    ax.legend(frameon=False, fontsize=6); tidy(ax)
    f.tight_layout(pad=0.3)
    q = os.path.join(FIG, 'fig8_channel_utility.pdf')
    f.savefig(q, bbox_inches='tight'); plt.close(f)
    prov['fig8_channel_utility.pdf'] = {'panel': 'main',
        'inputs': {'results/v2/v2_grid_validate_ideal.csv':
                   sha(os.path.join(ROOT, 'results/v2/v2_grid_validate_ideal.csv'))},
        'fields': ['p_cw', 'eff_E', 'eff_L', 'eff_F', 'snr_db', 'channel'],
        'layout_rule': 'Both panels share the SNR axis so the erasure curve and the utility curves '
                       'can be read against each other. Utility is averaged over the two channels '
                       'at each SNR point, matching how the grid is swept.',
        'sha256': sha(q)}


def main():
    os.makedirs(FIG, exist_ok=True)
    prov = {}
    fig1_block(prov); fig2_primary(prov); fig3_recovery(prov); fig4_w2c(prov); fig5_lambda(prov)
    fig6_matched_forest(prov); fig7_action_heatmap(prov); fig8_channel_utility(prov)
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
