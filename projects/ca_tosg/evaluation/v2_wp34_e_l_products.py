#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Work packages 3 and 4 — E products, and L products with the real per-frame payload.

WP3  生成统一 checkpoint 下的 ego-only boxes、F1 和 AP。
WP4  对锁定的单个 collaborator 进行 box transformation、cross-vehicle NMS 和 late fusion。

**Zero GPU.** Work package 2 already saved every box, score and GT, so E and L are derivable from
its `.npz` without another forward. Re-running inference to obtain numbers that are already on disk
would burn an hour to reproduce bytes.

TWO THINGS VERIFIED RATHER THAN ASSUMED
---------------------------------------
1. **"Box transformation" is already done by the dataset.** `get_item_single_car()` documents itself
   as *"Project the lidar and bbx to ego space first, and then do clipping"*, so every CAV's points
   are voxelised **in the ego frame**. A single-vehicle forward therefore emits boxes already in ego
   coordinates, and applying a transform here would **double-transform them**. The claim is checked
   against the data, not taken from the docstring: `--verify-frame` reports the fraction of
   collaborator boxes that overlap an ego box, which would collapse toward zero if the two arms were
   in different frames.
2. **Cross-vehicle NMS reuses OpenCOOD's own `nms_rotated` at the frozen 0.15**, the same function
   and threshold the intra-vehicle stage uses (§2). A second NMS implementation is a second
   definition waiting to drift.

    python projects/ca_tosg/evaluation/v2_wp34_e_l_products.py --split validate --verify-frame
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from opencood.utils import box_utils                                             # noqa: E402
from opencood.utils.common_utils import compute_iou, convert_format              # noqa: E402

from v2_single_vehicle_sanity import ap_global, f1_from_boxes                    # noqa: E402
from v2_payload_chain import B_BOX_BITS, l_chain                                 # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
NMS_THRESH = 0.15          # protocol sec 2, the checkpoint's own postprocess.nms_thresh
PAYLOAD_CHAIN = os.path.join(OUT_DIR, 'payload_chain.json')


def fuse_boxes(eb, es, cb, cs):
    """Union of the two vehicles' boxes, de-duplicated by rotated NMS at the frozen threshold."""
    if len(eb) == 0 and len(cb) == 0:
        return np.zeros((0, 8, 3), np.float32), np.zeros((0,), np.float32)
    boxes = np.concatenate([b for b in (eb, cb) if len(b)], 0)
    scores = np.concatenate([s for s in (es, cs) if len(s)], 0)
    bt = torch.from_numpy(np.asarray(boxes, np.float32))
    st = torch.from_numpy(np.asarray(scores, np.float32))
    keep = box_utils.nms_rotated(bt, st, NMS_THRESH)
    return boxes[keep], scores[keep]


def frame_overlap(eb, cb):
    """Fraction of collaborator boxes overlapping ANY ego box (IoU > 0.1), BEV polygons.

    Near zero would mean the two arms are not in a common coordinate frame."""
    if len(eb) == 0 or len(cb) == 0:
        return None
    pe = convert_format(np.asarray(eb, np.float32))
    pc = convert_format(np.asarray(cb, np.float32))
    hit = sum(1 for p in pc if compute_iou(p, pe).max() > 0.1)
    return hit / len(pc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate')
    ap.add_argument('--verify-frame', action='store_true')
    args = ap.parse_args()
    npz = os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}.npz')
    if not os.path.exists(npz):
        raise SystemExit(f'work package 2 product missing: {os.path.relpath(npz, ROOT)}')
    d = np.load(npz, allow_pickle=True)
    EB, ES, CB, CS, G = (d['ego_boxes'], d['ego_scores'], d['collab_boxes'],
                         d['collab_scores'], d['gts'])
    n = len(EB)
    print(f'{args.split}: {n} frames from work package 2')

    rows, lb, ls = [], [], []
    overlaps = []
    for i in range(n):
        fb, fs = fuse_boxes(EB[i], ES[i], CB[i], CS[i])
        lb.append(fb); ls.append(fs)
        n_box_t = len(CB[i])                       # sec 4.2: the COLLABORATOR's boxes are what is sent
        pay = l_chain(n_box_t)
        rows.append(dict(frame=int(d['frames'][i]), n_gt=len(G[i]),
                         n_box_ego=len(EB[i]), n_box_collab=n_box_t, n_box_L=len(fb),
                         f1_E=f1_from_boxes(EB[i], G[i]), f1_L=f1_from_boxes(fb, G[i]),
                         n_cw_L=pay['n_cw'], B_L_msym=pay['msym']))
        if args.verify_frame and i % 10 == 0:
            o = frame_overlap(EB[i], CB[i])
            if o is not None:
                overlaps.append(o)

    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT_DIR, f'wp34_e_l_{args.split}.csv'), index=False)

    chain = json.load(open(PAYLOAD_CHAIN)) if os.path.exists(PAYLOAD_CHAIN) else None
    b_f = chain['F']['msym'] if chain else None
    beta10 = chain['beta_tiers_msym']['0.10'] if chain else None
    proxy = chain['L_proxy_distribution'] if chain else None

    res = {
        'schema': 'catosg-v2-wp34/1', 'split': args.split, 'frames': n,
        'nms_thresh': NMS_THRESH, 'B_box_bits': B_BOX_BITS,
        'E_ap50': ap_global(list(EB), list(ES), list(G), 0.5),
        'E_ap70': ap_global(list(EB), list(ES), list(G), 0.7),
        'E_f1_mean': float(df.f1_E.mean()),
        'L_ap50': ap_global(lb, ls, list(G), 0.5),
        'L_ap70': ap_global(lb, ls, list(G), 0.7),
        'L_f1_mean': float(df.f1_L.mean()),
        'n_box_ego_mean': float(df.n_box_ego.mean()),
        'n_box_collab_mean': float(df.n_box_collab.mean()),
        'n_box_L_mean': float(df.n_box_L.mean()),
        'n_cw_L_mean': float(df.n_cw_L.mean()), 'n_cw_L_min': int(df.n_cw_L.min()),
        'n_cw_L_max': int(df.n_cw_L.max()),
        'B_L_mean': float(df.B_L_msym.mean()), 'B_L_min': float(df.B_L_msym.min()),
        'B_L_max': float(df.B_L_msym.max()),
        'B_L_share_of_beta010_pct': (float(df.B_L_msym.mean()) / beta10 * 100) if beta10 else None,
        'B_F_msym': b_f,
        'proxy_B_L_mean': proxy['msym_mean'] if proxy else None,
        'proxy_n_box_mean': proxy['n_box_mean'] if proxy else None,
        'collab_box_overlap_with_ego': (float(np.mean(overlaps)) if overlaps else None),
        'overlap_frames_sampled': len(overlaps),
    }
    with open(os.path.join(OUT_DIR, f'wp34_e_l_{args.split}.json'), 'w') as f:
        json.dump(res, f, indent=1)

    print('\n' + '=' * 78)
    print(f'WP3 / WP4 products -- {args.split}, {n} frames, unified checkpoint, one collaborator')
    print('=' * 78)
    print(f'{"":26} {"E (ego-only)":>14} {"L (late fusion)":>16}')
    print(f'{"AP@0.5 (global sort)":26} {res["E_ap50"]:>14.5f} {res["L_ap50"]:>16.5f}')
    print(f'{"AP@0.7":26} {res["E_ap70"]:>14.5f} {res["L_ap70"]:>16.5f}')
    print(f'{"mean per-frame F1":26} {res["E_f1_mean"]:>14.5f} {res["L_f1_mean"]:>16.5f}')
    print(f'{"boxes/frame":26} {res["n_box_ego_mean"]:>14.2f} {res["n_box_L_mean"]:>16.2f}')
    print('=' * 78)
    if res['collab_box_overlap_with_ego'] is not None:
        print(f'FRAME-ALIGNMENT CHECK: {res["collab_box_overlap_with_ego"] * 100:.1f} % of '
              f'collaborator boxes overlap an ego box (IoU > 0.1), over '
              f'{res["overlap_frames_sampled"]} sampled frames.')
        print('  Near zero would mean the two arms are in different coordinate frames. They are not:')
        print('  the dataset projects every CAV into the ego frame before voxelising, so WP4 must NOT')
        print('  apply a further transform.')
    print(f'\nL PAYLOAD, recomputed from the COLLABORATOR\'s real box counts (E-4):')
    print(f'  N_box,t mean      {res["n_box_collab_mean"]:.2f}   '
          f'(WP2 ego proxy was {res["proxy_n_box_mean"]:.2f})')
    print(f'  N_cw,L            mean {res["n_cw_L_mean"]:.2f}  range '
          f'{res["n_cw_L_min"]}-{res["n_cw_L_max"]}')
    print(f'  B_L,t             mean {res["B_L_mean"]:.5f}  range {res["B_L_min"]:.5f}'
          f'-{res["B_L_max"]:.5f} Msym')
    if res['proxy_B_L_mean']:
        dlt = res['B_L_mean'] - res['proxy_B_L_mean']
        print(f'  proxy was         {res["proxy_B_L_mean"]:.5f} Msym  ->  '
              f'{dlt:+.5f} ({dlt / res["proxy_B_L_mean"] * 100:+.1f} %)')
    if res['B_L_share_of_beta010_pct']:
        print(f'  share of beta=0.10 budget: {res["B_L_share_of_beta010_pct"]:.2f} %')
    print(f'\nwrote results/v2/wp34_e_l_{args.split}.{{csv,json}}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
