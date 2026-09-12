#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R6 B, C — the stage-1 development diagnostic, read and reported.

Order of business, and it does not proceed past a failure:
  1. determinism: every column stage 1 shares with the probe (same frames, masks, seeds, regimes)
     must be bit-identical. A mismatch stops the tool with the差 located; nothing is loosened.
  2. B-1..B-5: scene-equal F1 of E, L, full F and the three sparse F variants; differences with
     scene-level bootstrap intervals; per-scene table; per-mask spread; the two damage regimes apart.
  3. B-6: measured end-to-end time, and the stage-2 cost recomputed from it.
  4. C-1, C-2: the planning value of n2 by the pre-registered rule, and the replicate error estimated
     separately from the mask error.

This is a development diagnostic. The intervals are descriptive; nothing here is a significance test,
and no rule of the locked protocol may be changed on the strength of it (D-1).

    python projects/ca_tosg_p2/evaluation/p2_stage1_report.py [--check]
"""
from __future__ import annotations
import argparse, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
STAGE1 = os.path.join(P2, 'results', 'stage1')
PROBE = os.path.join(P2, 'results', 'probe')
LOCK = os.path.join(P2, 'protocol', 'round1_lock.json')
AM1 = os.path.join(P2, 'protocol', 'amendment1.json')
GRID = os.path.join(ROOT, 'results', 'v2', 'v2_grid_validate_ideal.csv')
OUT_JSON = os.path.join(STAGE1, 'stage1_report.json')
OUT_MD = os.path.join(STAGE1, 'stage1_report.md')

N_BOOT, BOOT_SEED = 10000, 20260809              # P1's resample count
RATE = 0.001
REGIMES = ('ideal', 'packet')
N2_CANDIDATES = (4, 8, 12, 16, 20)
RHO = 0.1
SPLIT_FRAMES = 1980
CONDITIONS_STAGE2 = 66                            # 1 clean + 8 x 4 x 2 + p = 1


def scene_equal(per_frame, scenes):
    """mean within a scene, then equal weight across scenes"""
    return float(np.mean([per_frame[scenes == s].mean() for s in np.unique(scenes)]))


def boot_ci(per_frame, scenes, seed=BOOT_SEED):
    uniq = np.unique(scenes)
    means = np.array([per_frame[scenes == s].mean() for s in uniq])
    rng = np.random.default_rng(seed)
    bs = means[rng.integers(0, len(uniq), (N_BOOT, len(uniq)))].mean(axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {'mean': float(means.mean()), 'lcb95': float(lo), 'ucb95': float(hi),
            'half_width': float((hi - lo) / 2)}


def determinism(s1, pr):
    cols = [c for c in pr.columns if c in s1.columns and (c.startswith('f1_') or c.startswith('cw_')
            or c in ('blocks_conf', 'blocks_norm', 'overlap_conf_norm', 'identity_control_ok'))]
    cols = [c for c in cols if 'p1.0' not in c and ('clean' in c or f'p{RATE}' in c or not c.startswith(('f1_', 'cw_')))]
    if not np.array_equal(s1.frame.to_numpy(), pr.frame.to_numpy()):
        raise SystemExit('DETERMINISM: frame vectors differ')
    bad, checked = [], 0
    for c in cols:
        a, b = s1[c].to_numpy(), pr[c].to_numpy()
        checked += a.size
        if a.dtype.kind in 'fi' and b.dtype.kind in 'fi':
            d = np.abs(a.astype(float) - b.astype(float))
            if d.max() > 0:
                bad.append({'column': c, 'max_abs_diff': float(d.max()),
                            'frames': [int(x) for x in s1.frame.to_numpy()[d > 0][:5]]})
        elif not (a == b).all():
            bad.append({'column': c, 'max_abs_diff': None,
                        'frames': [int(x) for x in s1.frame.to_numpy()[a != b][:5]]})
    if bad:
        raise SystemExit('DETERMINISM FAILED -- stage 1 does not reproduce the probe:\n'
                         + '\n'.join(f'  {x}' for x in bad))
    return {'columns_compared': len(cols), 'values_compared': int(checked), 'all_identical': True,
            'variants_covered': ['conf', 'norm', 'rand0', 'rand1']}


def build():
    s1 = pd.read_csv(os.path.join(STAGE1, 'f_block_rows_validate.csv'))
    pr = pd.read_csv(os.path.join(PROBE, 'f_block_rows_validate.csv'))
    meta = json.load(open(os.path.join(STAGE1, 'f_block_eval_validate.json')))
    lock, am1 = json.load(open(LOCK)), json.load(open(AM1))
    det = determinism(s1, pr)

    frames = s1.frame.to_numpy()
    g = pd.read_csv(GRID, usecols=['sample_id', 'scene', 'snr_db', 'channel', 'p_cw', 'eff_E', 'eff_L', 'eff_F'])
    g = g[g.sample_id.isin(frames)]
    scenes = g.drop_duplicates('sample_id').set_index('sample_id').scene.loc[frames].to_numpy()
    cells = [(c['channel'], c['snr_db'], c['p_cw']) for c in lock['D2_cells']['primary']]
    w = {c: cw['weight_upper'] for c, cw in zip([f'{a.upper()} {b} dB' for a, b, _ in cells],
                                                am1['cells_to_nodes']['cells'])}
    n_rand = meta['rand_reps_run']
    variants = ['conf', 'norm'] + [f'rand{r}' for r in range(n_rand)]

    def eff_sparse(v, reg):
        """per frame x cell, by the locked interpolation"""
        clean = s1[f'f1_{v}_clean'].to_numpy()
        dmg = np.mean([s1[f'f1_{v}_{reg}_p{RATE}_r{r}'].to_numpy() for r in range(4)], axis=0)
        return {f'{ch.upper()} {snr} dB': (1 - w[f'{ch.upper()} {snr} dB']) * clean
                + w[f'{ch.upper()} {snr} dB'] * dmg for ch, snr, _ in cells}

    ref = {}
    for name, col in (('E', 'eff_E'), ('L', 'eff_L'), ('full_F_P1', 'eff_F')):
        ref[name] = {f'{ch.upper()} {snr} dB':
                     g[(g.channel == ch) & (g.snr_db == snr)].set_index('sample_id')[col].loc[frames].to_numpy()
                     for ch, snr, _ in cells}
    cell_names = list(ref['E'])
    avg = lambda d: np.mean([d[c] for c in cell_names], axis=0)

    eff = {reg: {v: eff_sparse(v, reg) for v in variants} for reg in REGIMES}
    rand_mean = {reg: {c: np.mean([eff[reg][f'rand{r}'][c] for r in range(n_rand)], axis=0) for c in cell_names}
                 for reg in REGIMES}

    # B-1
    b1 = {'per_cell': {}, 'seven_cell_average': {}}
    for name in ('E', 'L', 'full_F_P1'):
        b1['per_cell'][name] = {c: scene_equal(ref[name][c], scenes) for c in cell_names}
        b1['seven_cell_average'][name] = scene_equal(avg(ref[name]), scenes)
    for reg in REGIMES:
        for v, lab in [('conf', 'sparse_F_confidence'), ('norm', 'sparse_F_norm')]:
            b1['per_cell'][f'{lab}|{reg}'] = {c: scene_equal(eff[reg][v][c], scenes) for c in cell_names}
            b1['seven_cell_average'][f'{lab}|{reg}'] = scene_equal(avg(eff[reg][v]), scenes)
        b1['per_cell'][f'sparse_F_random_mean|{reg}'] = {c: scene_equal(rand_mean[reg][c], scenes) for c in cell_names}
        b1['seven_cell_average'][f'sparse_F_random_mean|{reg}'] = scene_equal(avg(rand_mean[reg]), scenes)
    b1['full_F_note'] = ('full F is the P1 product at these cells: all 55 blocks, 3.14175 Msym. It is a '
                         'representation-quality reference, NOT a baseline at the budget of this round')

    # B-2
    b2 = {}
    for reg in REGIMES:
        for v, lab in [('conf', 'confidence'), ('norm', 'norm')]:
            b2[f'{lab}_minus_L|{reg}'] = boot_ci(avg(eff[reg][v]) - avg(ref['L']), scenes)
        b2[f'random_mean_minus_L|{reg}'] = boot_ci(avg(rand_mean[reg]) - avg(ref['L']), scenes)
        b2[f'confidence_minus_random|{reg}'] = boot_ci(avg(eff[reg]['conf']) - avg(rand_mean[reg]), scenes)
        b2[f'confidence_minus_norm|{reg}'] = boot_ci(avg(eff[reg]['conf']) - avg(eff[reg]['norm']), scenes)

    # B-3
    b3 = []
    for s in np.unique(scenes):
        m = scenes == s
        row = {'scene': str(s), 'frames': int(m.sum()), 'thin': bool(m.sum() <= 2)}
        for reg in REGIMES:
            row[f'confidence_minus_L|{reg}'] = float((avg(eff[reg]['conf']) - avg(ref['L']))[m].mean())
            row[f'norm_minus_L|{reg}'] = float((avg(eff[reg]['norm']) - avg(ref['L']))[m].mean())
            row[f'random_minus_L|{reg}'] = float((avg(rand_mean[reg]) - avg(ref['L']))[m].mean())
            row[f'confidence_minus_random|{reg}'] = float((avg(eff[reg]['conf']) - avg(rand_mean[reg]))[m].mean())
        b3.append(row)

    # B-4
    b4 = {}
    for reg in REGIMES:
        per_mask = [scene_equal(avg(eff[reg][f'rand{r}']), scenes) for r in range(n_rand)]
        b4[reg] = {'per_mask_scene_equal_f1': per_mask, 'sd_mask': float(np.std(per_mask, ddof=1)),
                   'range': [float(min(per_mask)), float(max(per_mask))],
                   'mc_se_at_n': {str(n): float(np.std(per_mask, ddof=1) / np.sqrt(n)) for n in N2_CANDIDATES}}

    # B-5: the two regimes differ only at the one damaged cell
    eight = [c for c in cell_names if c.endswith('8 dB')][0]
    b5 = {'damaged_cell': eight, 'weight_on_damaged_node': w[eight],
          'clean_cells_identical_across_regimes': True,
          'per_regime_at_damaged_cell': {reg: {'confidence': scene_equal(eff[reg]['conf'][eight], scenes),
                                               'norm': scene_equal(eff[reg]['norm'][eight], scenes),
                                               'random_mean': scene_equal(rand_mean[reg][eight], scenes),
                                               'L': scene_equal(ref['L'][eight], scenes),
                                               'full_F_P1': scene_equal(ref['full_F_P1'][eight], scenes)}
                                         for reg in REGIMES},
          'note': 'six of the seven cells have p_cw exactly 0, so their value is the clean forward and is the same '
                  'under both regimes; the regimes can differ only at the 8 dB cell, with weight '
                  f'{w[eight]:.2f} on the damaged node'}

    # B-6 and the stage-2 cost from measured time
    t = meta['timing']
    fixed = t['t_load_s']['mean'] + t['t_record_fwd_s']['mean'] + t['t_collab_fwd_gpu_s']['mean']
    masked1 = am1['C1_stage1']['masked_forwards_per_frame']
    per_cond = (t['t_frame_total_s']['mean'] - fixed) / masked1
    b6 = {'frames': meta['frames'], 'wall_clock_seconds': meta['seconds'], 'sec_per_frame': meta['sec_per_frame'],
          'estimate_was_gpu_minutes': [am1['C1_stage1']['time']['lower_gpu_minutes'],
                                       am1['C1_stage1']['time']['upper_gpu_minutes']],
          'measured_gpu_minutes': meta['seconds'] / 60,
          'per_condition_s_measured': per_cond, 'fixed_s_measured': fixed,
          'masked_forwards_per_frame': masked1,
          'stage2_cost_from_measurement': [
              {'n2': n, 'masked_forwards_per_frame': (2 + n) * CONDITIONS_STAGE2 + 1,
               'gpu_hours': SPLIT_FRAMES * (fixed + ((2 + n) * CONDITIONS_STAGE2 + 1) * per_cond) / 3600}
              for n in N2_CANDIDATES]}

    # C-1: the pre-registered rule, on the mainline regime
    reg0 = 'ideal'
    sd_mask = b4[reg0]['sd_mask']
    hw = boot_ci(avg(rand_mean[reg0]), scenes)['half_width']
    n2 = next((n for n in N2_CANDIDATES if sd_mask / np.sqrt(n) <= RHO * hw), None)
    c1 = {'regime': reg0, 'sd_mask': sd_mask, 'hw_scene': hw, 'rho': RHO,
          'threshold': RHO * hw, 'mc_se_by_n': {str(n): sd_mask / np.sqrt(n) for n in N2_CANDIDATES},
          'n2_planning_value': n2 if n2 is not None else max(N2_CANDIDATES),
          'target_precision_reached': n2 is not None,
          'label': 'planning estimate for Monte Carlo precision',
          'if_not_reached': 'reported as target precision NOT reached; it is not read as reached'}

    # C-2: replicate error, separate from mask error
    c2 = {}
    for reg in REGIMES:
        d = {}
        for v, lab in [('conf', 'confidence'), ('norm', 'norm')]:
            per_rep = [scene_equal(np.mean([(1 - w[c]) * s1[f'f1_{v}_clean'].to_numpy()
                                            + w[c] * s1[f'f1_{v}_{reg}_p{RATE}_r{r}'].to_numpy()
                                            for c in cell_names], axis=0), scenes) for r in range(4)]
            d[lab] = {'per_replicate_scene_equal_f1': per_rep, 'sd_replicate': float(np.std(per_rep, ddof=1)),
                      'mc_se_at_4': float(np.std(per_rep, ddof=1) / 2)}
        c2[reg] = d
    c2['note'] = ('the replicate error is the channel-realisation error at the one damaged node; it enters the '
                  'seven-cell average with weight ' + f'{w[eight]:.2f}/7. It is estimated here on its own and is '
                  'NOT covered by the number of random masks, which is a different source of variance')

    return {'schema': 'catosg-p2-stage1-report/1',
            'status': 'development diagnostic; intervals are descriptive; not a significance test (D-1)',
            'determinism_vs_probe': det,
            'design': {'frames': int(len(frames)), 'scenes': int(len(np.unique(scenes))),
                       'random_masks': n_rand, 'cells': cell_names, 'rate_node': RATE,
                       'regimes': list(REGIMES), 'K_F': meta['K_F'], 'n_blocks': meta['n_blocks']},
            'B1_scene_equal_f1': b1, 'B2_differences': b2, 'B3_per_scene': b3, 'B4_mask_spread': b4,
            'B5_regimes': b5, 'B6_time': b6, 'C1_n2_planning': c1, 'C2_replicate_error': c2,
            'D2_not_tested': ('this round cannot test degradation from F to L as the channel worsens: the seven '
                              'pre-registered cells are AWGN at 8 dB and above, where p_cw is 0.00013 or exactly 0'),
            'command': 'python projects/ca_tosg_p2/evaluation/p2_stage1_report.py'}


def markdown(m):
    d, b1, b2, b4, b5, b6, c1, c2 = (m[k] for k in ('design', 'B1_scene_equal_f1', 'B2_differences',
                                                    'B4_mask_spread', 'B5_regimes', 'B6_time',
                                                    'C1_n2_planning', 'C2_replicate_error'))
    L = ['<!-- GENERATED by projects/ca_tosg_p2/evaluation/p2_stage1_report.py -- do not edit by hand -->',
         '# Stage-1 development diagnostic (P2-R6)', '', f"**{m['status']}.**", '',
         f"Determinism against the probe: {m['determinism_vs_probe']['values_compared']:,} values over "
         f"{m['determinism_vs_probe']['columns_compared']} shared columns, all identical.", '',
         f"{d['frames']} frames, {d['scenes']} scenes, K_F = {d['K_F']} of {d['n_blocks']} blocks, "
         f"{d['random_masks']} random masks, damaged node p = {d['rate_node']}.", '',
         '## B-1 Scene-equal F1', '', '| arm | ' + ' | '.join(d['cells']) + ' | seven-cell average |',
         '|---' * (len(d['cells']) + 2) + '|']
    for k in b1['seven_cell_average']:
        L.append('| ' + k + ' | ' + ' | '.join(f"{b1['per_cell'][k][c]:.5f}" for c in d['cells'])
                 + f" | **{b1['seven_cell_average'][k]:.5f}** |")
    L += ['', f"*{b1['full_F_note']}.*", '', '## B-2 Differences, scene-level bootstrap (descriptive)', '',
          '| difference | mean | 95 % interval | half-width |', '|---|---:|---|---:|']
    for k, v in b2.items():
        L.append(f"| {k.replace('|', ', regime ')} | {v['mean']:+.5f} | [{v['lcb95']:+.5f}, {v['ucb95']:+.5f}] | {v['half_width']:.5f} |")
    L += ['', '## B-3 Per scene (fragment-aware regime)', '',
          '| scene | frames | conf − L | norm − L | random − L | conf − random |', '|---|---:|---:|---:|---:|---:|']
    for r in m['B3_per_scene']:
        thin = ' ⚠' if r['thin'] else ''
        L.append(f"| {r['scene']}{thin} | {r['frames']} | {r['confidence_minus_L|ideal']:+.5f} | "
                 f"{r['norm_minus_L|ideal']:+.5f} | {r['random_minus_L|ideal']:+.5f} | {r['confidence_minus_random|ideal']:+.5f} |")
    L += ['', '⚠ = 1 or 2 frames; the scene-equal mean still gives it weight 1/9.', '',
          '## B-4 Spread across the 8 random masks', '', '| regime | scene-equal F1 range | SD_mask | MC SE at n = 4 / 8 / 20 |',
          '|---|---|---:|---|']
    for reg, v in b4.items():
        L.append(f"| {reg} | [{v['range'][0]:.5f}, {v['range'][1]:.5f}] | {v['sd_mask']:.5f} | "
                 f"{v['mc_se_at_n']['4']:.5f} / {v['mc_se_at_n']['8']:.5f} / {v['mc_se_at_n']['20']:.5f} |")
    L += ['', '## B-5 The two damage regimes, kept apart', '', f"{b5['note']}.", '',
          f"At {b5['damaged_cell']}:", '', '| regime | confidence | norm | random mean | L | full F (P1) |', '|---|---:|---:|---:|---:|---:|']
    for reg, v in b5['per_regime_at_damaged_cell'].items():
        L.append(f"| {reg} | {v['confidence']:.5f} | {v['norm']:.5f} | {v['random_mean']:.5f} | {v['L']:.5f} | {v['full_F_P1']:.5f} |")
    L += ['', '## B-6 Measured time and the stage-2 cost', '',
          f"{b6['frames']} frames in {b6['wall_clock_seconds']:.0f} s = **{b6['measured_gpu_minutes']:.1f} GPU-minutes** "
          f"({b6['sec_per_frame']:.2f} s/frame); the estimate was {b6['estimate_was_gpu_minutes'][0]:.1f}–"
          f"{b6['estimate_was_gpu_minutes'][1]:.1f}. Measured per-condition cost {b6['per_condition_s_measured'] * 1e3:.1f} ms.", '',
          '| n2 | masked forwards / frame | validate GPU-hours (from measurement) |', '|---:|---:|---:|']
    for r in b6['stage2_cost_from_measurement']:
        L.append(f"| {r['n2']} | {r['masked_forwards_per_frame']:,} | {r['gpu_hours']:.1f} |")
    L += ['', '## C-1 n2, planning estimate for Monte Carlo precision', '',
          f"SD_mask = {c1['sd_mask']:.5f}, HW_scene = {c1['hw_scene']:.5f}, threshold = {RHO} × HW_scene = "
          f"{c1['threshold']:.5f} (regime {c1['regime']}).", '', '| n | MC SE | meets threshold |', '|---:|---:|:---:|']
    for n, v in c1['mc_se_by_n'].items():
        L.append(f"| {n} | {v:.5f} | {'yes' if v <= c1['threshold'] else 'no'} |")
    L += ['', (f"**n2 = {c1['n2_planning_value']}** — {c1['label']}." if c1['target_precision_reached']
               else f"**Target precision NOT reached at n = 20**; {c1['if_not_reached']}. Planning value "
                    f"{c1['n2_planning_value']} is the cap, not a value that meets the rule."), '',
          '## C-2 Replicate error, estimated separately', '', f"{c2['note']}.", '',
          '| regime | arm | SD across the 4 realisations | MC SE at 4 |', '|---|---|---:|---:|']
    for reg in ('ideal', 'packet'):
        for arm, v in c2[reg].items():
            L.append(f"| {reg} | {arm} | {v['sd_replicate']:.5f} | {v['mc_se_at_4']:.5f} |")
    L += ['', f"**Not tested this round.** {m['D2_not_tested']}."]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('stage1 report:', 'reproduced' if ok else 'FAIL -- not what the generator writes'); return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md); print(md); return 0


if __name__ == '__main__':
    sys.exit(main())
