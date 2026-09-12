#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R8 B — stage 2, clean condition only, on all 1,980 validate frames: read and reported.

Order, and it stops at a failure:
  0. determinism: the 60 frames stage 2 shares with stage 1 must give bit-identical clean F1 for
     every variant. A mismatch stops the tool.
  B-1  scene-equal F1 overall and on the locked hard subset; per-scene differences; descriptive
       paired intervals. The 8 dB cell is NOT computed in this round and is not substituted, so
       there is no seven-cell average here.
  B-2  per-frame win / tie / loss of confidence F against L, and the size distribution of both signs
  B-3  recall, misses recovered and false positives introduced, F against L, from box counts
  B-4  the measured SD_mask against the planning value, and the measured run time
  B-5  the exploratory subsets, reported, never confirmatory
  B-6  frames where sparse F scores above full F: the change in false positives and in misses,
       reported separately and not attributed

L's fused boxes are not a P1 product; they are rebuilt with P1's own `fuse_boxes` from the WP2 boxes
(CPU, rotated NMS at 0.15, no network) and the rebuild is verified against P1's recorded `f1_L`
before it is used. No extra inference is run.

    python projects/ca_tosg_p2/evaluation/p2_stage2_report.py [--check]
"""
from __future__ import annotations
import argparse, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
sys.path.insert(0, os.path.join(P2, 'protocol'))
sys.path.insert(0, os.path.join(ROOT, 'projects', 'ca_tosg', 'evaluation'))
sys.path.insert(0, HERE)

from p2_stage1_report import scene_equal, boot_ci, MISS_LADDER                    # noqa: E402

STAGE2 = os.path.join(P2, 'results', 'stage2_clean')
STAGE1 = os.path.join(P2, 'results', 'stage1')
GRID = os.path.join(ROOT, 'results', 'v2', 'v2_grid_validate_ideal.csv')
WP34 = os.path.join(ROOT, 'results', 'v2', 'wp34_e_l_validate.csv')
WP2 = os.path.join(ROOT, 'results', 'v2', 'wp2_per_agent_validate.npz')
WP5 = os.path.join(ROOT, 'results', 'v2', 'wp5_final_validate.csv')
AM2 = os.path.join(P2, 'protocol', 'amendment2.json')
OUT_JSON = os.path.join(STAGE2, 'stage2_report.json')
OUT_MD = os.path.join(STAGE2, 'stage2_report.md')
IOU = 0.5


def l_counts(frames):
    """L's boxes, rebuilt with P1's fuse_boxes and verified against P1's f1_L before use."""
    import torch
    from opencood.utils import eval_utils
    from v2_wp34_e_l_products import fuse_boxes
    from v2_single_vehicle_sanity import f1_from_boxes
    z = np.load(WP2, allow_pickle=True)
    w = pd.read_csv(WP34, usecols=['frame', 'f1_E', 'f1_L', 'n_box_L'])
    if not np.array_equal(w.frame.to_numpy(), z['frames']):
        raise SystemExit('B-3: WP2 and WP34 frame vectors differ')
    pos = {int(f): i for i, f in enumerate(z['frames'])}

    def cnt(pred, gt):
        pred = np.asarray(pred, np.float32); gt = np.asarray(gt, np.float32)
        pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
        gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
        rs = {IOU: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
        eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, IOU)
        return int(sum(rs[IOU]['tp'])), int(sum(rs[IOU]['fp'])), int(rs[IOU]['gt'])

    out, dl, de, nbox = {'tp_L': [], 'fp_L': [], 'tp_E': [], 'fp_E': [], 'n_gt': []}, [], [], []
    for f in frames:
        i = pos[int(f)]
        fb, fs = fuse_boxes(z['ego_boxes'][i], z['ego_scores'][i], z['collab_boxes'][i], z['collab_scores'][i])
        dl.append(abs(f1_from_boxes(fb, z['gts'][i]) - w.f1_L.to_numpy()[i]))
        de.append(abs(f1_from_boxes(z['ego_boxes'][i], z['gts'][i]) - w.f1_E.to_numpy()[i]))
        nbox.append(len(fb))
        tp, fp, g = cnt(fb, z['gts'][i]); out['tp_L'].append(tp); out['fp_L'].append(fp); out['n_gt'].append(g)
        tp, fp, _ = cnt(z['ego_boxes'][i], z['gts'][i]); out['tp_E'].append(tp); out['fp_E'].append(fp)
    # Two criteria, and they are different in kind. The BOX SET must reproduce exactly -- that is what the
    # counts are built from, and it admits no tolerance. The F1 comparison has one side that has been
    # through a CSV text round trip, so it is held to float64 round-trip precision rather than to bit
    # equality; the observed difference is one unit in the last place at ~1.0 and no box differs.
    F1_ROUND_TRIP_TOL = 1e-12
    n_box_mismatch = int((np.array(nbox) != w.n_box_L.to_numpy()[[pos[int(f)] for f in frames]]).sum())
    rebuild = {'max_abs_f1_L_diff': float(np.max(dl)), 'max_abs_f1_E_diff': float(np.max(de)),
               'n_box_L_mismatches': n_box_mismatch, 'f1_round_trip_tolerance': F1_ROUND_TRIP_TOL,
               'criterion': 'box counts must match exactly; F1 to float64 CSV round-trip precision'}
    if n_box_mismatch:
        raise SystemExit(f'B-3: the rebuilt L boxes differ from P1 in {n_box_mismatch} frames -- refusing to use them')
    if rebuild['max_abs_f1_L_diff'] > F1_ROUND_TRIP_TOL or rebuild['max_abs_f1_E_diff'] > F1_ROUND_TRIP_TOL:
        raise SystemExit(f'B-3: the rebuilt L/E boxes do not reproduce P1 ({rebuild}) -- refusing to use them')
    return {k: np.array(v) for k, v in out.items()}, rebuild


def determinism(s2, frames_s2):
    s1 = pd.read_csv(os.path.join(STAGE1, 'f_block_rows_validate.csv'))
    cols = [c for c in s1.columns if c.endswith('_clean') and c.startswith('f1_') and c in s2.columns]
    cols += [c for c in ('blocks_conf', 'blocks_norm', 'overlap_conf_norm') if c in s1.columns and c in s2.columns]
    pos = {int(f): i for i, f in enumerate(frames_s2)}
    take = [pos[int(f)] for f in s1.frame]
    bad = []
    for c in cols:
        a, b = s2[c].to_numpy()[take], s1[c].to_numpy()
        if a.dtype.kind in 'fi' and b.dtype.kind in 'fi':
            d = np.abs(a.astype(float) - b.astype(float))
            if d.max() > 0:
                bad.append({'column': c, 'max_abs_diff': float(d.max())})
        elif not (a == b).all():
            bad.append({'column': c, 'max_abs_diff': None})
    if bad:
        raise SystemExit('DETERMINISM FAILED against stage 1:\n' + '\n'.join(f'  {x}' for x in bad))
    return {'frames_compared': int(len(s1)), 'columns_compared': len(cols),
            'values_compared': int(len(s1) * len(cols)), 'all_identical': True}


def build():
    s2 = pd.read_csv(os.path.join(STAGE2, 'f_block_rows_validate.csv'))
    meta = json.load(open(os.path.join(STAGE2, 'f_block_eval_validate.json')))
    am2 = json.load(open(AM2))
    frames = s2.frame.to_numpy()
    det = determinism(s2, frames)

    g = pd.read_csv(GRID, usecols=['sample_id', 'scene']).drop_duplicates('sample_id').set_index('sample_id')
    scenes = g.scene.loc[frames].to_numpy()
    w34 = pd.read_csv(WP34, usecols=['frame', 'f1_E', 'f1_L']).set_index('frame').loc[frames]
    w5 = pd.read_csv(WP5, usecols=['frame', 'f1_clean']).set_index('frame').loc[frames]
    if np.abs(s2.f1_full_clean.to_numpy() - w5.f1_clean.to_numpy()).max() > 0:
        raise SystemExit('the full-F forward does not reproduce P1 f1_clean -- refusing to report')

    n_rand = meta['rand_reps_run']
    arms = {'E': w34.f1_E.to_numpy(), 'L': w34.f1_L.to_numpy(), 'full_F_P1': w5.f1_clean.to_numpy(),
            'sparse_F_confidence': s2.f1_conf_clean.to_numpy(), 'sparse_F_norm': s2.f1_norm_clean.to_numpy(),
            'sparse_F_random_mean': np.mean([s2[f'f1_rand{r}_clean'].to_numpy() for r in range(n_rand)], axis=0)}
    diffs = {'confidence_minus_L': arms['sparse_F_confidence'] - arms['L'],
             'norm_minus_L': arms['sparse_F_norm'] - arms['L'],
             'random_minus_L': arms['sparse_F_random_mean'] - arms['L'],
             'confidence_minus_random': arms['sparse_F_confidence'] - arms['sparse_F_random_mean'],
             'confidence_minus_norm': arms['sparse_F_confidence'] - arms['sparse_F_norm'],
             'norm_minus_random': arms['sparse_F_norm'] - arms['sparse_F_random_mean'],
             'full_F_minus_L': arms['full_F_P1'] - arms['L']}

    from round1_lock import hard_frames
    missed_all, _ = hard_frames()
    missed = missed_all[frames]

    def block(sel, label, locked):
        sc = scenes[sel]
        inc = np.unique(sc)
        return {'label': label, 'locked_rule': locked, 'frames': int(sel.sum()),
                'share': float(sel.mean()), 'scenes_included': int(len(inc)),
                'scenes_total': int(len(np.unique(scenes))),
                'scenes_dropped': [str(x) for x in np.unique(scenes) if x not in inc],
                'scene_equal_f1': {a: scene_equal(v[sel], sc) for a, v in arms.items()},
                'differences': {k: boot_ci(v[sel], sc) for k, v in diffs.items()},
                'per_scene': [{'scene': str(x), 'frames': int((sc == x).sum()),
                               **{k: float(v[sel][sc == x].mean()) for k, v in diffs.items()}} for x in inc]}

    all_sel = np.ones(len(frames), bool)
    b1 = {'overall': block(all_sel, 'all validate frames', False),
          'hard_locked': block(missed >= 1, 'locked hard subset (E misses >= 1)', True),
          'cell_note': 'clean condition only. The six locked cells with p_cw exactly 0 equal this value; '
                       'AWGN 8 dB is NOT computed this round and is not substituted, so no seven-cell average '
                       'is formed'}

    # B-2
    d = diffs['confidence_minus_L']
    pos_, neg_, tie_ = d > 0, d < 0, d == 0
    b2 = {'frames': int(len(d)), 'win': int(pos_.sum()), 'tie': int(tie_.sum()), 'loss': int(neg_.sum()),
          'win_share': float(pos_.mean()), 'tie_share': float(tie_.mean()), 'loss_share': float(neg_.mean()),
          'win_magnitude_quantiles_p25_p50_p75_p90_max': [float(x) for x in np.percentile(d[pos_], [25, 50, 75, 90, 100])] if pos_.any() else [],
          'loss_magnitude_quantiles_p25_p50_p75_p90_max': [float(x) for x in np.percentile(-d[neg_], [25, 50, 75, 90, 100])] if neg_.any() else [],
          'mean_over_wins': float(d[pos_].mean()) if pos_.any() else 0.0,
          'mean_over_losses': float(d[neg_].mean()) if neg_.any() else 0.0,
          'hard_subset': {'win': int((d[missed >= 1] > 0).sum()), 'tie': int((d[missed >= 1] == 0).sum()),
                          'loss': int((d[missed >= 1] < 0).sum())},
          'caveat': 'this describes the spread of per-frame outcomes only. It is NOT evidence that a selector '
                    'could identify the winning frames in advance: the split is made with the realised outcome'}

    # B-3
    c, rebuild = l_counts(frames)
    tp_f, fp_f = s2.tp_conf.to_numpy(), s2.fp_conf.to_numpy()
    n_gt = c['n_gt']
    if not np.array_equal(n_gt, s2.n_gt.to_numpy()):
        raise SystemExit('B-3: ground-truth counts disagree between the run and the WP2 product')
    fn = {'E': n_gt - c['tp_E'], 'L': n_gt - c['tp_L'], 'F_conf': n_gt - tp_f}
    b3 = {'rebuild_check': rebuild, 'total_gt': int(n_gt.sum()),
          'recall': {k: float((n_gt.sum() - v.sum()) / n_gt.sum()) for k, v in fn.items()},
          'false_positives': {'E': int(c['fp_E'].sum()), 'L': int(c['fp_L'].sum()), 'F_conf': int(fp_f.sum())},
          'F_vs_L': {'misses_recovered_net': int((fn['L'] - fn['F_conf']).sum()),
                     'misses_recovered_on_frames_where_positive': int(np.maximum(fn['L'] - fn['F_conf'], 0).sum()),
                     'misses_introduced_on_frames_where_negative': int(np.maximum(fn['F_conf'] - fn['L'], 0).sum()),
                     'false_positives_net': int((fp_f - c['fp_L']).sum()),
                     'false_positives_added_where_positive': int(np.maximum(fp_f - c['fp_L'], 0).sum()),
                     'false_positives_removed_where_negative': int(np.maximum(c['fp_L'] - fp_f, 0).sum()),
                     'frames_with_fewer_misses': int((fn['F_conf'] < fn['L']).sum()),
                     'frames_with_more_misses': int((fn['F_conf'] > fn['L']).sum()),
                     'frames_with_fewer_fp': int((fp_f < c['fp_L']).sum()),
                     'frames_with_more_fp': int((fp_f > c['fp_L']).sum())},
          'note': 'counts at IoU 0.5 against the canonical union ground truth, the same matching the F1 uses'}

    # B-4
    per_mask = [scene_equal(s2[f'f1_rand{r}_clean'].to_numpy(), scenes) for r in range(n_rand)]
    per_mask_hard = [scene_equal(s2[f'f1_rand{r}_clean'].to_numpy()[missed >= 1], scenes[missed >= 1]) for r in range(n_rand)]
    hw = b1['overall']['differences']['confidence_minus_random']['half_width']
    sd = float(np.std(per_mask, ddof=1))
    b4 = {'masks': n_rand, 'per_mask_scene_equal_f1': per_mask, 'sd_mask_measured': sd,
          'sd_mask_planned': am2['B2_basis']['sd_mask'],
          'ratio_measured_over_planned': sd / am2['B2_basis']['sd_mask'],
          'sd_mask_measured_hard_subset': float(np.std(per_mask_hard, ddof=1)),
          'mc_se_at_8_measured': sd / np.sqrt(n_rand),
          'threshold_now': 0.1 * hw, 'meets_threshold_at_8': bool(sd / np.sqrt(n_rand) <= 0.1 * hw),
          'half_width_confidence_minus_random': hw,
          'runtime': {'frames': meta['frames'], 'seconds': meta['seconds'], 'sec_per_frame': meta['sec_per_frame'],
                      'gpu_hours': meta['seconds'] / 3600,
                      'planned_gpu_hours': am2['C_clean_only_stage2']['gpu_hours'],
                      'planned_sec_per_frame': am2['C_clean_only_stage2']['sec_per_frame']}}

    # B-5
    b5 = [block(missed >= k, f'exploratory subset (E misses >= {k})', False) for k in MISS_LADDER if k > 1]

    # B-6
    over = arms['sparse_F_confidence'] > arms['full_F_P1']
    d_fp = s2.fp_conf.to_numpy() - s2.fp_full.to_numpy()
    d_fn = (n_gt - tp_f) - (n_gt - s2.tp_full.to_numpy())
    b6 = {'frames_sparse_above_full': int(over.sum()), 'share': float(over.mean()),
          'on_those_frames': {'delta_false_positives_total': int(d_fp[over].sum()),
                              'delta_misses_total': int(d_fn[over].sum()),
                              'frames_with_fewer_fp': int((d_fp[over] < 0).sum()),
                              'frames_with_more_fp': int((d_fp[over] > 0).sum()),
                              'frames_with_fewer_misses': int((d_fn[over] < 0).sum()),
                              'frames_with_more_misses': int((d_fn[over] > 0).sum()),
                              'mean_delta_fp': float(d_fp[over].mean()) if over.any() else 0.0,
                              'mean_delta_misses': float(d_fn[over].mean()) if over.any() else 0.0},
          'all_frames': {'delta_false_positives_total': int(d_fp.sum()), 'delta_misses_total': int(d_fn.sum())},
          'no_attribution': 'the two changes are reported as measured. Nothing here establishes WHY sparse F '
                            'scores above full F on these frames, and "it removes false positives" is not '
                            'claimed'}

    return {'schema': 'catosg-p2-stage2-report/1',
            'scope': 'validate, all frames, CLEAN condition only; no loss sweep; no selector trained',
            'determinism_vs_stage1': det, 'design': {'frames': int(len(frames)), 'scenes': int(len(np.unique(scenes))),
                                                     'random_masks': n_rand, 'K_F': meta['K_F'], 'n_blocks': meta['n_blocks']},
            'B1': b1, 'B2_per_frame': b2, 'B3_counts': b3, 'B4_masks_and_time': b4, 'B5_exploratory': b5,
            'B6_sparse_above_full': b6,
            'not_computed': 'AWGN 8 dB: it needs the p = 0.001 node, which this run does not produce; it is '
                            'reported as not computed and no clean value is substituted for it',
            'command': 'python projects/ca_tosg_p2/evaluation/p2_stage2_report.py'}


def fmt_block(b, L):
    L += ['', f"### {b['label']}: {b['frames']:,} frames, {b['scenes_included']} of {b['scenes_total']} scenes"
          + ('' if not b['scenes_dropped'] else f" — dropped: {', '.join(b['scenes_dropped'])}"), '',
          '| ' + ' | '.join(b['scene_equal_f1']) + ' |', '|---:' * len(b['scene_equal_f1']) + '|',
          '| ' + ' | '.join(f'{v:.5f}' for v in b['scene_equal_f1'].values()) + ' |', '',
          '| difference | mean | 95 % interval |', '|---|---:|---|']
    L += [f"| {k} | {v['mean']:+.5f} | [{v['lcb95']:+.5f}, {v['ucb95']:+.5f}] |" for k, v in b['differences'].items()]
    return L


def markdown(m):
    b1, b2, b3, b4, b6 = m['B1'], m['B2_per_frame'], m['B3_counts'], m['B4_masks_and_time'], m['B6_sparse_above_full']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/evaluation/p2_stage2_report.py -- do not edit by hand -->',
         '# Stage 2, clean condition only (P2-R8)', '', f"**Scope:** {m['scope']}.", '',
         f"Determinism against stage 1: {m['determinism_vs_stage1']['values_compared']:,} values over "
         f"{m['determinism_vs_stage1']['columns_compared']} columns on the {m['determinism_vs_stage1']['frames_compared']} "
         f"shared frames, all identical.", '', f"**Not computed:** {m['not_computed']}.", '',
         '## B-1 Scene-equal F1 and differences', '', b1['cell_note'] + '.']
    L = fmt_block(b1['overall'], L)
    L = fmt_block(b1['hard_locked'], L)
    L += ['', '#### Per scene, locked hard subset (confidence − L, norm − L, random − L, confidence − random)', '',
          '| scene | frames | conf − L | norm − L | random − L | conf − random |', '|---|---:|---:|---:|---:|---:|']
    for r in b1['hard_locked']['per_scene']:
        L.append(f"| {r['scene']} | {r['frames']} | {r['confidence_minus_L']:+.5f} | {r['norm_minus_L']:+.5f} | "
                 f"{r['random_minus_L']:+.5f} | {r['confidence_minus_random']:+.5f} |")
    L += ['', '## B-2 Per-frame outcome, confidence F against L', '',
          f"All frames: **{b2['win']:,} win / {b2['tie']:,} tie / {b2['loss']:,} loss** "
          f"({b2['win_share'] * 100:.1f} % / {b2['tie_share'] * 100:.1f} % / {b2['loss_share'] * 100:.1f} %). "
          f"Hard subset: {b2['hard_subset']['win']:,} / {b2['hard_subset']['tie']:,} / {b2['hard_subset']['loss']:,}.", '',
          f"Win sizes (p25/p50/p75/p90/max): {', '.join(f'{x:+.4f}' for x in b2['win_magnitude_quantiles_p25_p50_p75_p90_max'])}; "
          f"mean over wins {b2['mean_over_wins']:+.4f}.", '',
          f"Loss sizes (p25/p50/p75/p90/max, as magnitudes): {', '.join(f'{x:.4f}' for x in b2['loss_magnitude_quantiles_p25_p50_p75_p90_max'])}; "
          f"mean over losses {b2['mean_over_losses']:+.4f}.", '', f"*{b2['caveat']}.*", '',
          '## B-3 Recall, misses and false positives (IoU 0.5)', '',
          f"L's boxes rebuilt with P1's `fuse_boxes` and verified: **{b3['rebuild_check']['n_box_L_mismatches']} box-count "
          f"mismatches** over all frames, max |Δf1_L| = {b3['rebuild_check']['max_abs_f1_L_diff']:g}, "
          f"max |Δf1_E| = {b3['rebuild_check']['max_abs_f1_E_diff']:g} (one unit in the last place; P1's value comes "
          f"from a CSV, so F1 is held to float64 round-trip precision while the box set must match exactly). "
          f"Total ground-truth objects: {b3['total_gt']:,}.", '',
          '| arm | recall | false positives |', '|---|---:|---:|']
    for k in ('E', 'L', 'F_conf'):
        L.append(f"| {k} | {b3['recall'][k] * 100:.2f} % | {b3['false_positives'][k]:,} |")
    v = b3['F_vs_L']
    L += ['', 'Confidence F against L:', '',
          f"* misses recovered, net: **{v['misses_recovered_net']:+,}** "
          f"(recovered where positive {v['misses_recovered_on_frames_where_positive']:,}; "
          f"introduced where negative {v['misses_introduced_on_frames_where_negative']:,})",
          f"* false positives, net: **{v['false_positives_net']:+,}** "
          f"(added {v['false_positives_added_where_positive']:,}; removed {v['false_positives_removed_where_negative']:,})",
          f"* frames with fewer / more misses: {v['frames_with_fewer_misses']:,} / {v['frames_with_more_misses']:,}; "
          f"with fewer / more false positives: {v['frames_with_fewer_fp']:,} / {v['frames_with_more_fp']:,}", '',
          '## B-4 Mask spread and run time', '',
          f"SD_mask measured over {b4['masks']} masks: **{b4['sd_mask_measured']:.5f}** against the planning value "
          f"{b4['sd_mask_planned']:.5f} (ratio {b4['ratio_measured_over_planned']:.2f}); on the hard subset "
          f"{b4['sd_mask_measured_hard_subset']:.5f}. Monte Carlo SE at 8 masks {b4['mc_se_at_8_measured']:.5f} "
          f"against the threshold {b4['threshold_now']:.5f} (0.1 × the confidence − random half-width "
          f"{b4['half_width_confidence_minus_random']:.5f}): "
          f"**{'meets it' if b4['meets_threshold_at_8'] else 'does NOT meet it'}**.", '',
          f"Run time: {b4['runtime']['frames']:,} frames in {b4['runtime']['seconds']:.0f} s = "
          f"{b4['runtime']['gpu_hours']:.2f} GPU-hours ({b4['runtime']['sec_per_frame']:.2f} s/frame), against the "
          f"plan of {b4['runtime']['planned_gpu_hours']:.1f} GPU-hours ({b4['runtime']['planned_sec_per_frame']:.2f} s/frame).", '',
          '## B-5 Exploratory subsets (never confirmatory)']
    for b in m['B5_exploratory']:
        L = fmt_block(b, L)
    o = b6['on_those_frames']
    L += ['', '## B-6 Frames where sparse F scores above full F', '',
          f"**{b6['frames_sparse_above_full']:,} frames ({b6['share'] * 100:.1f} %)**. On those frames, against full F: "
          f"false positives change by {o['delta_false_positives_total']:+,} in total "
          f"({o['frames_with_fewer_fp']:,} frames fewer, {o['frames_with_more_fp']:,} more; mean {o['mean_delta_fp']:+.2f}); "
          f"misses change by {o['delta_misses_total']:+,} "
          f"({o['frames_with_fewer_misses']:,} fewer, {o['frames_with_more_misses']:,} more; mean {o['mean_delta_misses']:+.2f}). "
          f"Across all frames: false positives {b6['all_frames']['delta_false_positives_total']:+,}, "
          f"misses {b6['all_frames']['delta_misses_total']:+,}.", '', f"*{b6['no_attribution']}.*"]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('stage2 report:', 'reproduced' if ok else 'FAIL -- not what the generator writes'); return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md); print(md); return 0


if __name__ == '__main__':
    sys.exit(main())
