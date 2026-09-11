#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R5 — the numbers of Amendment 1 to f_block_selection.md, derived rather than typed.

  A-1  forward-count decomposition of the LOCKED design, validated against the probe's actual counts
  A-2  what "paired" means in the evaluation code, with line references
  A-3  what is computed once per frame and reused
  A-4  the withdrawn "16 repeats clean-only" option
  B-2  the budget margin at K_F
  C-1  stage-1 design, forward count and time estimate (probe rates, bias stated)
  B-1  stage-2 formula and the pre-registered rule for the number of random masks

Reads only: round1_lock.json, the probe summary, P1's WP5 constants, the P1 grid's p_cw per cell and
scene per frame. No F1 value is read.

`--check` re-derives, compares byte for byte, and asserts that the amendment text in
f_block_selection.md carries the same numbers.

    python projects/ca_tosg_p2/protocol/amendment1.py [--check]
"""
from __future__ import annotations
import argparse, json, math, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
LOCK = os.path.join(HERE, 'round1_lock.json')
PROBE = os.path.join(P2, 'results', 'probe', 'f_block_eval_validate.json')
WP5 = os.path.join(ROOT, 'results', 'v2', 'wp5_final_validate.json')
GRID = os.path.join(ROOT, 'results', 'v2', 'v2_grid_validate_ideal.csv')
PROTOCOL = os.path.join(HERE, 'f_block_selection.md')
OUT_JSON = os.path.join(HERE, 'amendment1.json')
OUT_MD = os.path.join(HERE, 'amendment1.md')

R_RAND_LOCKED = 20
N1_RANDOM = 8                                   # C-2: stage-1 random masks
N2_CANDIDATES = (4, 8, 12, 16, 20)              # B-1: stage-2 candidates, capped at the locked 20
RHO = 0.1                                       # B-1: Monte Carlo SE <= RHO x scene-sampling half-width
SPLIT_FRAMES = 1980


def conditions(n_rates, n_reps, n_regimes, clean=1, p_one=1):
    return clean + n_rates * n_reps * n_regimes + p_one


def build():
    lock = json.load(open(LOCK))
    probe = json.load(open(PROBE))
    wp5 = json.load(open(WP5))
    rates, reps, regimes = list(wp5['rates']), int(wp5['replicates']), list(wp5['regimes'])
    nR, nr, ng = len(rates), reps, len(regimes)
    c_full = conditions(nR, nr, ng)                           # clean + damaged + p=1
    damaged = nR * nr * ng

    # ---- A-1: locked design -------------------------------------------------------------
    rows = [
        {'ranking': 'confidence', 'masks': 1, 'clean_per_mask': 1, 'damaged_per_mask': damaged, 'p1_per_mask': 1,
         'identity_control': 1},
        {'ranking': 'norm', 'masks': 1, 'clean_per_mask': 1, 'damaged_per_mask': damaged, 'p1_per_mask': 1,
         'identity_control': 0},
        {'ranking': 'random', 'masks': R_RAND_LOCKED, 'clean_per_mask': 1, 'damaged_per_mask': damaged, 'p1_per_mask': 1,
         'identity_control': 0},
    ]
    for r in rows:
        r['forwards'] = r['masks'] * (r['clean_per_mask'] + r['damaged_per_mask'] + r['p1_per_mask']) + r['identity_control']
    masked_locked = sum(r['forwards'] for r in rows)
    shared = {'full_F_recording_forward': 1, 'collaborator_single_vehicle_forward': 1}
    formula = lambda n_rand, c=c_full: (2 + n_rand) * c + 1
    if masked_locked != formula(R_RAND_LOCKED):
        raise SystemExit('AMENDMENT1: decomposition does not sum to the formula')
    # validate against what the probe actually executed (2 random repeats)
    n_var_probe = len(probe['variants_run'])
    timed_probe = n_var_probe * (1 + damaged)                  # clean + damaged are timed in the code
    untimed_probe = n_var_probe * 1 + 1                        # p = 1 per variant + identity control
    if timed_probe != probe['timing']['n_masked_fwd']['mean']:
        raise SystemExit(f'AMENDMENT1: probe timed {probe["timing"]["n_masked_fwd"]["mean"]} != derived {timed_probe}')
    if timed_probe + untimed_probe != formula(n_var_probe - 2):
        raise SystemExit('AMENDMENT1: probe total does not match the formula')

    # ---- cells -> interpolation nodes (locked 9.3) ------------------------------------------
    p_nodes = np.array((0.0,) + tuple(rates) + (1.0,))
    g = pd.read_csv(GRID, usecols=['sample_id', 'scene', 'snr_db', 'channel', 'p_cw'])
    cells = []
    need = set()
    for c in lock['D2_cells']['primary']:
        v = g[(g.channel == c['channel']) & (g.snr_db == c['snr_db'])].p_cw.unique()
        if len(v) != 1:
            raise SystemExit('AMENDMENT1: p_cw varies within a locked cell')
        p = float(v[0])
        i = int(np.clip(np.searchsorted(p_nodes, p, side='right') - 1, 0, len(p_nodes) - 2))
        w = (p - p_nodes[i]) / (p_nodes[i + 1] - p_nodes[i])
        nodes = [float(p_nodes[i])] + ([float(p_nodes[i + 1])] if w > 0 else [])
        need.update(nodes)
        cells.append({'cell': f"{c['channel'].upper()} {c['snr_db']} dB", 'p_cw': p, 'lower_node': float(p_nodes[i]),
                      'upper_node': float(p_nodes[i + 1]), 'weight_upper': w, 'nodes_used': nodes})
    need = sorted(need)
    damaged_nodes = [x for x in need if 0 < x < 1]

    # ---- C-1: stage-1 design --------------------------------------------------------------
    ids = probe['frame_ids']
    sc = g.drop_duplicates('sample_id').set_index('sample_id').scene
    per_scene = sc.loc[ids].value_counts()
    c_stage1 = 1 + len(damaged_nodes) * nr * ng               # clean + (needed damaged nodes) x reps x regimes
    masked_stage1 = (2 + N1_RANDOM) * c_stage1 + 1
    stage1_rows = [
        {'ranking': 'confidence', 'masks': 1, 'clean_per_mask': 1, 'damaged_per_mask': len(damaged_nodes) * nr * ng, 'identity_control': 1},
        {'ranking': 'norm', 'masks': 1, 'clean_per_mask': 1, 'damaged_per_mask': len(damaged_nodes) * nr * ng, 'identity_control': 0},
        {'ranking': 'random', 'masks': N1_RANDOM, 'clean_per_mask': 1, 'damaged_per_mask': len(damaged_nodes) * nr * ng, 'identity_control': 0},
    ]
    for r in stage1_rows:
        r['forwards'] = r['masks'] * (r['clean_per_mask'] + r['damaged_per_mask']) + r['identity_control']
    if sum(r['forwards'] for r in stage1_rows) != masked_stage1:
        raise SystemExit('AMENDMENT1: stage-1 decomposition does not sum')

    # ---- time model from the probe -----------------------------------------------------------
    t = probe['timing']
    def model(stat):
        load, rec, col = t['t_load_s'][stat], t['t_record_fwd_s'][stat], t['t_collab_fwd_gpu_s'][stat]
        fwd = t['t_masked_fwd_mean_s'][stat]
        total = t['t_frame_total_s'][stat]
        cpu_share = (probe['device']['cpu_frames_timed'] * t['t_collab_fwd_cpu_s']['mean'] / probe['frames']) if stat == 'mean' else 0.0
        masked_probe = timed_probe + untimed_probe
        resid = total - (load + rec + col) - cpu_share - masked_probe * fwd
        oh = resid / masked_probe
        return {'fixed_s': load + rec + col, 'forward_s': fwd, 'overhead_per_condition_s': oh,
                'per_condition_s': fwd + oh}
    up, lo = model('mean'), model('median')
    per_frame = lambda m, n_masked: m['fixed_s'] + n_masked * m['per_condition_s']
    stage1 = {'upper_s_per_frame': per_frame(up, masked_stage1), 'lower_s_per_frame': per_frame(lo, masked_stage1)}
    stage1['upper_gpu_minutes'] = len(ids) * stage1['upper_s_per_frame'] / 60
    stage1['lower_gpu_minutes'] = len(ids) * stage1['lower_s_per_frame'] / 60
    stage2 = []
    for n in N2_CANDIDATES:
        m = formula(n)
        stage2.append({'n2': n, 'masked_forwards_per_frame': m,
                       'gpu_hours_upper': SPLIT_FRAMES * per_frame(up, m) / 3600,
                       'gpu_hours_lower': SPLIT_FRAMES * per_frame(lo, m) / 3600})
    old = SPLIT_FRAMES * (up['fixed_s'] + masked_locked * up['forward_s']) / 3600

    a3 = lock['A3_budget']
    margin = a3['B_available_msym'] - a3['N_sym_at_K_F_msym']
    return {
        'schema': 'catosg-p2-amendment1/1',
        'reads': 'round1_lock.json, probe summary, P1 WP5 constants, P1 grid p_cw and scenes; no F1 value',
        'A1_locked_decomposition': {'rows': rows, 'masked_forwards_per_frame': masked_locked, 'shared_forwards_per_frame': shared,
                                    'executed_forwards_per_frame': masked_locked + sum(shared.values()),
                                    'damaged_per_mask_formula': f'{nR} rates x {nr} realisations x {ng} regimes ({", ".join(regimes)}) = {damaged}',
                                    'formula': '(2 + R_rand) x (1 clean + damaged + 1 p=1) + 1 identity control',
                                    'probe_validation': {'variants': n_var_probe, 'timed_derived': timed_probe,
                                                         'timed_recorded': probe['timing']['n_masked_fwd']['mean'],
                                                         'untimed_derived': untimed_probe, 'total': timed_probe + untimed_probe}},
        'A2_pairing': {
            'draws': 'one codeword-erasure draw per (frame, rate, realisation), computed once per frame before the variant loop '
                     '(p2_f_block_eval.py line 278, seed [20260809, 3, frame, rate, realisation]) and reused by every variant '
                     '(line 297); the packet regime is derived deterministically from the same draw',
            'same_count': f"N_cw = {a3['n_cw_at_K_F']} for every variant, because every variant sends K_F = {a3['K_F']} blocks",
            'what_pairing_does_not_mean': 'codeword k carries the k-th chunk of each variant\'s own message, so the same draw erases '
                                          'different BEV regions under different selections; the channel realisation is paired, '
                                          'the spatial loss is not',
            'random_layer': 'random masks are drawn per (frame, repeat) with seed [20260809, 2, frame, repeat] (line 274), '
                            'independently of the codeword draws; every random mask sees the same codeword draws'},
        'A3_cache': [
            {'item': 'collaborator float bottleneck (all three branches)', 'computed': 'once per frame (full-F recording forward)', 'reused_by': 'norm ranking', 'status': 'cached'},
            {'item': 'collaborator confidence map', 'computed': 'once per frame (single-vehicle forward)', 'reused_by': 'confidence ranking', 'status': 'cached'},
            {'item': 'codeword-erasure draws', 'computed': 'once per (frame, rate, realisation)', 'reused_by': 'every variant and regime', 'status': 'cached'},
            {'item': 'clean result of a variant', 'computed': 'once per variant', 'reused_by': 'every cell with p_cw = 0 (no forward)', 'status': 'by interpolation'},
            {'item': 'E branch (ego-only)', 'computed': 'P1 WP2/WP34 products', 'reused_by': 'every comparison', 'status': 'no forward'},
            {'item': 'L branch (object-level)', 'computed': 'P1 WP34 products and grid eff_L', 'reused_by': 'every comparison', 'status': 'no forward'},
            {'item': 'pre-wire features: pillar encoder, scatter, backbone blocks, AutoEncoder encoders, branch-2 block output (ego and collaborator)',
             'computed': 'currently recomputed in every masked forward', 'reused_by': 'identical across all conditions of a frame',
             'status': 'NOT cached; caching would cut time per condition, not the forward count, and needs an identity check against the full path before use'}],
        'A4_withdrawn': 'running the loss sweep on only 4 of 20 random masks and the clean condition on the other 16 is withdrawn: '
                        'it raises the precision of the random baseline under a clean channel only and does not replace '
                        'repetitions under a damaged channel',
        'B2_margin': {'B_available_msym': a3['B_available_msym'], 'N_sym_at_K_F_msym': a3['N_sym_at_K_F_msym'],
                      'margin_msym': margin, 'margin_percent': 100 * margin / a3['B_available_msym']},
        'cells_to_nodes': {'cells': cells, 'nodes_needed': need, 'damaged_nodes_needed': damaged_nodes},
        'C1_stage1': {'frames': len(ids), 'frame_ids_rule': 'the 60 probe frames (every 33rd validate frame)',
                      'frames_per_scene': {k: int(v) for k, v in per_scene.sort_index().items()},
                      'scenes': int(len(per_scene)), 'min_frames_in_a_scene': int(per_scene.min()),
                      'random_masks': N1_RANDOM, 'conditions_per_mask': c_stage1,
                      'rows': stage1_rows, 'masked_forwards_per_frame': masked_stage1,
                      'executed_forwards_per_frame': masked_stage1 + sum(shared.values()),
                      'time': stage1, 'time_model_upper': up, 'time_model_lower': lo},
        'B1_stage2': {'frames': SPLIT_FRAMES, 'formula': 'masked forwards per frame = (2 + n2) x ' + str(c_full) + ' + 1',
                      'rule': f'n2 = the smallest n in {list(N2_CANDIDATES)} with SD_mask / sqrt(n) <= {RHO} x HW_scene; '
                              f'if none, n2 = {R_RAND_LOCKED}',
                      'rule_terms': {'SD_mask': 'standard deviation (ddof = 1) across the stage-1 random masks of the '
                                                'scene-equal F1 of random ranking, averaged over the seven locked cells, all stage-1 frames',
                                     'HW_scene': 'half-width of the scene-level bootstrap 95 % interval (10,000 resamples) of the '
                                                 'scene-equal F1 of random ranking averaged over the stage-1 masks, same cells and frames',
                                     'why': f'a Monte Carlo SE at most {RHO} of the scene half-width widens the combined '
                                            f'half-width by at most {100 * (math.sqrt(1 + RHO ** 2) - 1):.1f} %; the rule '
                                            'uses the random baseline only and cannot depend on whether confidence ranking wins'},
                      'candidates': stage2},
        'estimate_correction': {'previous_validate_gpu_hours': old, 'previous_reason': 'omitted per-condition CPU work (mask '
                                'construction and F1 scoring) that the probe residual shows',
                                'corrected_validate_gpu_hours_upper_at_20': stage2[-1]['gpu_hours_upper'],
                                'corrected_validate_gpu_hours_lower_at_20': stage2[-1]['gpu_hours_lower']},
        'bias': ['upper: probe means, including CUDA warm-up and a GPU shared with a desktop session -> pushes UP',
                 'lower: component medians combined; not the median of a sum, can understate',
                 'one-time dataset build and model load are not included',
                 'stage 1 reuses frames and seeds of the probe, so its confidence, norm, random 0 and random 1 values '
                 'must reproduce the probe CSV bit for bit -- a free determinism check, run programmatically'],
        'command': 'python projects/ca_tosg_p2/protocol/amendment1.py'}


def markdown(m):
    a1, c1, b1, a3c, b2, cn, corr = (m[k] for k in ('A1_locked_decomposition', 'C1_stage1', 'B1_stage2', 'A3_cache', 'B2_margin', 'cells_to_nodes', 'estimate_correction'))
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/amendment1.py -- do not edit by hand -->',
         '# Amendment 1 — derived numbers (P2-R5)', '', f"Reads: {m['reads']}.", '',
         '## A-1 Locked design: forwards per frame', '',
         f"Damaged repetitions per mask: {a1['damaged_per_mask_formula']}.", '',
         '| ranking | masks | clean / mask | damaged / mask | p = 1 / mask | identity control | forwards |',
         '|---|---:|---:|---:|---:|---:|---:|']
    for r in a1['rows']:
        L.append(f"| {r['ranking']} | {r['masks']} | {r['clean_per_mask']} | {r['damaged_per_mask']} | {r['p1_per_mask']} | {r['identity_control']} | {r['forwards']:,} |")
    pv = a1['probe_validation']
    L += [f"| **masked total** | | | | | | **{a1['masked_forwards_per_frame']:,}** |", '',
          f"Plus shared per frame: 1 full-F recording forward, 1 collaborator single-vehicle forward → "
          f"{a1['executed_forwards_per_frame']:,} forwards executed. Formula: {a1['formula']}. "
          f"Checked against the probe ({pv['variants']} variants): timed {pv['timed_derived']} derived = {pv['timed_recorded']:.0f} recorded; "
          f"plus {pv['untimed_derived']} untimed = {pv['total']}.", '',
          '## A-2 Pairing', '']
    L += [f"* {v}." for v in m['A2_pairing'].values()]
    L += ['', '## A-3 Computed once and reused', '', '| item | computed | reused by | status |', '|---|---|---|---|']
    L += [f"| {c['item']} | {c['computed']} | {c['reused_by']} | {c['status']} |" for c in a3c]
    L += ['', f"## A-4 Withdrawn", '', m['A4_withdrawn'] + '.', '',
          '## B-2 Margin', '', f"B_available {b2['B_available_msym']:.4f} Msym − N_sym,F(K_F) {b2['N_sym_at_K_F_msym']:.4f} Msym = "
          f"**{b2['margin_msym']:.4f} Msym ({b2['margin_percent']:.1f} %)**.", '',
          '## The seven locked cells need two nodes', '', '| cell | p_cw | lower node | upper node | weight on upper | nodes used |', '|---|---:|---:|---:|---:|---|']
    L += [f"| {c['cell']} | {c['p_cw']:g} | {c['lower_node']:g} | {c['upper_node']:g} | {c['weight_upper']:.2f} | {', '.join(f'{x:g}' for x in c['nodes_used'])} |" for c in cn['cells']]
    L += ['', f"Nodes needed: {', '.join(f'{x:g}' for x in cn['nodes_needed'])}; damaged nodes: {', '.join(f'{x:g}' for x in cn['damaged_nodes_needed'])}.", '',
          '## C-1 Stage 1', '',
          f"{c1['frames']} frames ({c1['frame_ids_rule']}) in {c1['scenes']} scenes; frames per scene "
          f"{list(c1['frames_per_scene'].values())} — at least {c1['min_frames_in_a_scene']} in a scene. "
          f"Random masks n1 = {c1['random_masks']}. Conditions per mask: {c1['conditions_per_mask']} (clean + damaged nodes × realisations × regimes).", '',
          '| ranking | masks | clean / mask | damaged / mask | identity control | forwards |', '|---|---:|---:|---:|---:|---:|']
    L += [f"| {r['ranking']} | {r['masks']} | {r['clean_per_mask']} | {r['damaged_per_mask']} | {r['identity_control']} | {r['forwards']} |" for r in c1['rows']]
    tt = c1['time']
    L += [f"| **masked total** | | | | | **{c1['masked_forwards_per_frame']}** |", '',
          f"Executed per frame: {c1['executed_forwards_per_frame']}. Time: **{tt['lower_gpu_minutes']:.1f}–{tt['upper_gpu_minutes']:.1f} GPU-minutes** "
          f"({tt['lower_s_per_frame']:.2f}–{tt['upper_s_per_frame']:.2f} s/frame). Per-condition cost "
          f"{c1['time_model_lower']['per_condition_s'] * 1e3:.1f}–{c1['time_model_upper']['per_condition_s'] * 1e3:.1f} ms "
          f"(forward {c1['time_model_lower']['forward_s'] * 1e3:.1f}–{c1['time_model_upper']['forward_s'] * 1e3:.1f} ms + CPU "
          f"{c1['time_model_lower']['overhead_per_condition_s'] * 1e3:.1f}–{c1['time_model_upper']['overhead_per_condition_s'] * 1e3:.1f} ms).", '',
          '## B-1 Stage 2', '', f"{b1['frames']:,} frames; {b1['formula']}. **Rule:** {b1['rule']}.", '']
    L += [f"* **{k}**: {v}." for k, v in b1['rule_terms'].items()]
    L += ['', '| n2 | masked forwards / frame | validate GPU-hours |', '|---:|---:|---:|']
    L += [f"| {c['n2']} | {c['masked_forwards_per_frame']:,} | {c['gpu_hours_lower']:.1f}–{c['gpu_hours_upper']:.1f} |" for c in b1['candidates']]
    L += ['', '## Correction to the earlier estimate', '',
          f"The earlier figure of {corr['previous_validate_gpu_hours']:.1f} GPU-hours for the locked design {corr['previous_reason']}. "
          f"Corrected at 20 random masks: **{corr['corrected_validate_gpu_hours_lower_at_20']:.1f}–{corr['corrected_validate_gpu_hours_upper_at_20']:.1f} GPU-hours**.", '',
          '## Bias', '']
    L += [f"* {b}." for b in m['bias']]
    return '\n'.join(L) + '\n'


REQUIRED = lambda m: [
    'Amendment 1',
    f"{m['B2_margin']['margin_msym']:.4f} Msym",
    f"{m['B2_margin']['margin_percent']:.1f} %",
    f"{m['A1_locked_decomposition']['masked_forwards_per_frame']:,}",
    f"{m['C1_stage1']['masked_forwards_per_frame']} masked forwards",
    f"n1 = {m['C1_stage1']['random_masks']}",
    f"{m['A1_locked_decomposition']['rows'][0]['damaged_per_mask']} damaged",
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        txt = open(PROTOCOL).read()
        miss = [s for s in REQUIRED(m) if s not in txt]
        print('amendment1:', 'reproduced' if ok else 'FAIL -- not what the generator writes',
              '| protocol carries the numbers:', 'yes' if not miss else f'NO, missing {miss}')
        return 0 if ok and not miss else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md); print(md); return 0


if __name__ == '__main__':
    sys.exit(main())
