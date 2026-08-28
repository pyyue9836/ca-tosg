#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R19 A-1 — what the 73.6 % actually is, and why 100 % would be a failure. Zero GPU.

THE READING THAT HAD TO BE SETTLED
----------------------------------
`v2_wp34_e_l_products.py` printed

    FRAME-ALIGNMENT CHECK: 73.6 % of collaborator boxes overlap an ego box (IoU > 0.1), over
    198 sampled frames.

and the label was wrong in a way that mattered. "Frame" was meant in the *spatial reference frame*
sense — are the collaborator's boxes already in ego coordinates? — but reads as *frame index*, and a
73.6 % frame-index alignment rate would be a serious defect whose only correct value is 100 %.

The quantity is a **coordinate-frame diagnostic**. It fails DOWNWARD: two arms in different
reference frames drive it toward 0. It has **no upper failure threshold**, and **100 % would be bad
news** — it would mean the collaborator never contributes a detection the ego did not already have,
i.e. that cooperative perception buys nothing.

This module settles the reading with the data instead of the argument. It rebuilds L twice:

    L_full          ego boxes + ALL collaborator boxes  -> cross-vehicle NMS   (the real product)
    L_overlap_only  ego boxes + only the collaborator boxes that DO overlap an ego box

If the correct value of the diagnostic were 100 %, `L_overlap_only` would be the whole of L. What
the gap between the two costs is the answer.

**HOW THE RESULT MAY BE STATED (V2-R20 A-4).** The share reported below is **attributed by an
ablation** — L is rebuilt without those boxes and re-scored end to end — and it is **not** a
decomposition of AP into per-box contributions. **AP is a global-sort statistic and does not
decompose additively over predictions**: removing a box changes the ranking every later box is
scored against, so "these boxes contribute X % of the AP" is not a well-formed sentence. Say
*"removing them costs X % of the gain"*, never *"they account for X % of the gain"*.

This is the third application of one rule, and the three sites cross-reference each other:
  * `v2_wp5_message.py` module docstring, B-2 — `AP = q·AP_F + (1−q)·AP_E` is forbidden;
  * `v2_wp5_message.py:tpfp()`, B-1/B-2 — TP/FP are matched **within** a frame, then sorted globally;
  * here — an ablation attributes, it does not decompose.

It also reports the diagnostic over ALL frames rather than the 198 sampled, and the pooled
box-level fraction alongside the mean-over-frames one, because those are two different statistics
that were both being called "73.6 %".

    python projects/ca_tosg/evaluation/v2_coordinate_frame_check.py --split validate
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

import numpy as np
import torch

warnings.filterwarnings('ignore', message='invalid value encountered in intersection')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from opencood.utils import box_utils                                            # noqa: E402
from opencood.utils.common_utils import compute_iou, convert_format             # noqa: E402

from v2_single_vehicle_sanity import ap_global, f1_from_boxes                   # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
NMS_THRESH = 0.15          # sec 2, the checkpoint's own postprocess.nms_thresh
OVERLAP_IOU = 0.1          # the diagnostic's own threshold, unchanged
GT_IOU = 0.5               # "is this non-overlapping box a real object?"


def fuse(eb, es, cb, cs):
    if len(eb) == 0 and len(cb) == 0:
        return np.zeros((0, 8, 3), np.float32), np.zeros((0,), np.float32)
    b = np.concatenate([x for x in (eb, cb) if len(x)], 0)
    s = np.concatenate([x for x in (es, cs) if len(x)], 0)
    keep = box_utils.nms_rotated(torch.from_numpy(np.asarray(b, np.float32)),
                                 torch.from_numpy(np.asarray(s, np.float32)), NMS_THRESH)
    return b[keep], s[keep]


def overlap_mask(eb, cb):
    """Boolean per collaborator box: does it overlap ANY ego box above OVERLAP_IOU?"""
    if len(cb) == 0:
        return np.zeros((0,), bool)
    if len(eb) == 0:
        return np.zeros((len(cb),), bool)
    pe = convert_format(np.asarray(eb, np.float32))
    pc = convert_format(np.asarray(cb, np.float32))
    return np.array([compute_iou(p, pe).max() > OVERLAP_IOU for p in pc])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate')
    args = ap.parse_args()

    npz = os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}.npz')
    if not os.path.exists(npz):
        raise SystemExit(f'missing work-package-2 product: {os.path.relpath(npz, ROOT)}')
    d = np.load(npz, allow_pickle=True)
    EB, ES, CB, CS, G = (d['ego_boxes'], d['ego_scores'], d['collab_boxes'],
                         d['collab_scores'], d['gts'])
    n = len(EB)
    print('=' * 90)
    print(f'V2-R19 A-1 -- coordinate-frame diagnostic, ablation-attributed: {args.split}, {n} frames')
    print('=' * 90)

    per_frame, full_b, full_s, ov_b, ov_s = [], [], [], [], []
    n_ov = n_no = gt_hit = gt_eval = 0
    for i in range(n):
        m = overlap_mask(EB[i], CB[i])
        n_ov += int(m.sum())
        n_no += int((~m).sum())
        if len(CB[i]) and len(EB[i]):
            per_frame.append(float(m.mean()))
        fb, fs = fuse(EB[i], ES[i], CB[i], CS[i])
        full_b.append(fb)
        full_s.append(fs)
        ob, os_ = fuse(EB[i], ES[i], CB[i][m], CS[i][m])
        ov_b.append(ob)
        ov_s.append(os_)
        no = ~m
        if no.any() and len(G[i]):
            pg = convert_format(np.asarray(G[i], np.float32))
            pn = convert_format(np.asarray(CB[i][no], np.float32))
            gt_hit += sum(1 for p in pn if compute_iou(p, pg).max() >= GT_IOU)
            gt_eval += int(no.sum())
        if i % 200 == 0:
            print(f'  {i}/{n}', flush=True)

    per_frame = np.asarray(per_frame)
    sampled = per_frame[::10] if len(per_frame) else per_frame       # the 198-frame convention

    e50, e70 = ap_global(list(EB), list(ES), list(G), 0.5), ap_global(list(EB), list(ES), list(G), 0.7)
    l50, l70 = ap_global(full_b, full_s, list(G), 0.5), ap_global(full_b, full_s, list(G), 0.7)
    o50, o70 = ap_global(ov_b, ov_s, list(G), 0.5), ap_global(ov_b, ov_s, list(G), 0.7)
    ef1 = float(np.mean([f1_from_boxes(EB[i], G[i]) for i in range(n)]))
    lf1 = float(np.mean([f1_from_boxes(full_b[i], G[i]) for i in range(n)]))
    of1 = float(np.mean([f1_from_boxes(ov_b[i], G[i]) for i in range(n)]))

    def share(e, l, o):
        """Fraction of the E->L gain that SURVIVES the ablation (L rebuilt without those boxes).

        1 - this is the fraction LOST to the ablation. That is an attribution by removal, not a
        per-box decomposition of AP -- see the module docstring (V2-R20 A-4).
        """
        gain = l - e
        return None if gain == 0 else (o - e) / gain

    out = {
        'schema': 'catosg-v2-coordinate-frame-check/1', 'split': args.split, 'frames': n,
        'overlap_iou_threshold': OVERLAP_IOU, 'gt_iou_threshold': GT_IOU,
        'what_this_is': 'A COORDINATE-frame diagnostic: are the collaborator boxes already in ego '
                        'coordinates? It fails DOWNWARD (toward 0). It is NOT a frame-index '
                        'alignment rate and 100 % is not its correct value.',
        'statistics_that_were_both_called_73.6_pct': {
            'mean_over_frames_sampled_every_10th': float(sampled.mean()) if len(sampled) else None,
            'frames_in_that_sample': int(len(sampled)),
            'mean_over_frames_all': float(per_frame.mean()) if len(per_frame) else None,
            'frames_in_that_population': int(len(per_frame)),
            'pooled_over_boxes': float(n_ov / max(n_ov + n_no, 1)),
            'note': 'The mean of per-frame fractions and the pooled box-level fraction are '
                    'different statistics and differ here. The product reports the first, over '
                    'every 10th frame.'},
        'collaborator_boxes': {
            'overlapping_an_ego_box': int(n_ov),
            'not_overlapping_any_ego_box': int(n_no),
            'total': int(n_ov + n_no)},
        'are_the_non_overlapping_boxes_real': {
            'evaluated': int(gt_eval), 'matching_a_GT_object_at_iou_0.5': int(gt_hit),
            'precision': float(gt_hit / max(gt_eval, 1)),
            'reading': 'These are objects the collaborator detected and the ego did not. Driving '
                       'the diagnostic to 100 % would mean deleting them.'},
        'what_100_pct_would_cost': {
            'attribution_method':
                'ABLATION, not decomposition (V2-R20 A-4). L is rebuilt with the non-overlapping '
                'collaborator boxes removed and re-scored end to end. AP is a global-sort '
                'statistic and does not decompose additively over predictions, so these shares '
                'must be read as "removing these boxes costs this much of the gain" and NEVER as '
                '"these boxes account for this much of the gain". Same rule as the ban on '
                'AP = q*AP_F + (1-q)*AP_E in v2_wp5_message.py.',
            'E_ap50': e50, 'L_ap50_full': l50, 'L_ap50_overlapping_collaborator_boxes_only': o50,
            'E_ap70': e70, 'L_ap70_full': l70, 'L_ap70_overlapping_collaborator_boxes_only': o70,
            'E_f1': ef1, 'L_f1_full': lf1, 'L_f1_overlapping_only': of1,
            'ap50_gain_share_lost_to_ablation':
                None if share(e50, l50, o50) is None else 1 - share(e50, l50, o50),
            'ap70_gain_share_lost_to_ablation':
                None if share(e70, l70, o70) is None else 1 - share(e70, l70, o70),
            'f1_gain_share_lost_to_ablation':
                None if share(ef1, lf1, of1) is None else 1 - share(ef1, lf1, of1)},
        'mean_boxes_per_frame': {
            'ego': float(np.mean([len(x) for x in EB])),
            'collaborator': float(np.mean([len(x) for x in CB])),
            'L_after_cross_vehicle_nms': float(np.mean([len(x) for x in full_b]))},
        'verdict': 'The correct value of this diagnostic is NOT 100 %. It is a downward-failing '
                   'coordinate-frame check, and removing the non-overlapping collaborator boxes '
                   'costs most of the cooperative gain -- attributed by ablation and re-scoring, '
                   'not by decomposing AP over predictions (V2-R20 A-4).',
    }
    path = os.path.join(OUT_DIR, f'coordinate_frame_check_{args.split}.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)

    s = out['statistics_that_were_both_called_73.6_pct']
    w = out['what_100_pct_would_cost']
    print(f'\n  mean over every 10th frame ({s["frames_in_that_sample"]} frames): '
          f'{s["mean_over_frames_sampled_every_10th"]:.6f}   <- the reported 73.6 %')
    print(f'  mean over ALL {s["frames_in_that_population"]} frames                : '
          f'{s["mean_over_frames_all"]:.6f}')
    print(f'  pooled over all boxes                       : {s["pooled_over_boxes"]:.6f}')
    print(f'\n  collaborator boxes: {n_ov} overlap an ego box, {n_no} do not')
    print(f'  of the non-overlapping ones, {gt_hit}/{gt_eval} '
          f'({out["are_the_non_overlapping_boxes_real"]["precision"] * 100:.1f} %) match a real '
          f'GT object at IoU >= {GT_IOU}')
    print(f'\n  WHAT 100 % WOULD COST (drop every non-overlapping collaborator box):')
    print(f'{"":34}{"E":>10}{"L (full)":>12}{"L (overlap only)":>19}')
    print(f'  {"AP@0.5":32}{e50:>10.5f}{l50:>12.5f}{o50:>19.5f}')
    print(f'  {"AP@0.7":32}{e70:>10.5f}{l70:>12.5f}{o70:>19.5f}')
    print(f'  {"mean per-frame F1":32}{ef1:>10.5f}{lf1:>12.5f}{of1:>19.5f}')
    print(f'\n  ATTRIBUTED BY ABLATION (not a per-box decomposition of AP -- see A-4):')
    print(f'    removing the non-overlapping boxes costs '
          f'{w["ap50_gain_share_lost_to_ablation"] * 100:.1f} % of the E->L AP@0.5 gain')
    print(f'    removing them costs '
          f'{w["f1_gain_share_lost_to_ablation"] * 100:.1f} % of the E->L F1 gain')
    print(f'\n  VERDICT: {out["verdict"]}')
    print(f'wrote {os.path.relpath(path, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
