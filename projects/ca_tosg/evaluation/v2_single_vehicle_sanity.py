#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R1 item 1: does the attentive-compression checkpoint still detect with NO feature fusion?

WHY THIS RUNS FIRST. Paper v2 (plan A) removes the confound that four things differ at once between
the L and F branches -- trained weights, fusion architecture, feature codec and field of view -- by
driving ALL THREE actions from ONE checkpoint. That only works if this checkpoint, which was trained
with attentive fusion in the loop, still produces usable boxes when a vehicle runs alone. If it does
not, plan A is dead on arrival and nothing downstream is worth pre-registering.

WHAT "NO FUSION" MEANS HERE, EXACTLY, AND WHY NO FORWARD CODE IS TOUCHED.
`AttFusion.forward` regroups the stacked CAV features by `record_len` and self-attends within each
group. With `record_len = [1]` the softmax is over a single element, so `attn == 1.0` and
`context == value`: the fusion is an EXACT identity, not an approximation. So a single-vehicle
forward is obtained purely by feeding the model one CAV -- slice the collated voxels to
`voxel_coords[:, 0] == 0` (the ego; the intermediate dataset orders ego first) and set
`record_len = [1]`. The model file, the fusion module and the post-processor are untouched, which is
the standing instruction: diagnose the forward path, do not edit it.

WHAT IS DELIBERATELY *NOT* CHANGED, and is a pre-registration question rather than a code question:
the compression AutoEncoder stays IN the path in single-vehicle mode. Physically a vehicle does not
encode a message to itself, so action E arguably should bypass it -- but bypassing it changes the
network the weights were trained for. This script reports the as-is number; the protocol decides.

BOTH ARMS SEE THE SAME FRAMES AND THE SAME GT. `post_process` derives GT from
`object_bbx_center`/`object_bbx_mask`, which the slicing does not touch, so the cooperative and
single-vehicle arms are scored against one identical cooperative GT -- the same convention the v1
ego-only fallback used, and the only one under which the two arms are comparable frame by frame.

    python projects/ca_tosg/evaluation/v2_single_vehicle_sanity.py --limit 200
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, REPO)

os.environ.setdefault('CATOSG_EVAL_RNG', '1')  # V2-R16

from torch.utils.data import DataLoader                                          # noqa: E402

from opencood.data_utils.datasets import build_dataset                           # noqa: E402
from opencood.hypes_yaml import yaml_utils                                       # noqa: E402
from opencood.tools import inference_utils, train_utils                          # noqa: E402
from opencood.utils import eval_utils                                            # noqa: E402

CKPT = ('/mnt/h/opencood_project/pretrained_models/pointpillar_attentive_fusion/'
        'pointpillar_attentive_fusion_compression')
OUT_DIR = os.path.join(ROOT, 'results', 'v2')
# The checkpoint config stores `root_dir: "opv2v_data_dumping/validate"` -- relative to whatever
# directory the original training run used. Resolved here to an absolute path instead of relying on
# cwd, which is how v1's drivers had to be launched. This repoints an INPUT, not the forward path.
DATA_ROOT = '/mnt/h/opencood_project/datasets/opv2v_data_dumping'
# The fuse, from the FROZEN v1 product -- read, never typed. results/main/ego_only_acceptance.csv
# carries the v1 ego-only AP@0.5 per split; the sanity check stops if the single-vehicle arm of this
# checkpoint falls below half of it.
EGO_ACCEPT = os.path.join(ROOT, 'results', 'main', 'ego_only_acceptance.csv')


def frozen_ego_ap(split):
    import pandas as pd
    d = pd.read_csv(EGO_ACCEPT)
    row = d[d.split == split]
    if row.empty:
        raise SystemExit(f'no frozen ego-only row for split={split} in {EGO_ACCEPT}')
    return float(row.ego_ap50.iloc[0]), float(row.ego_f1.iloc[0])


def f1_from_boxes(pred, gt, iou=0.5):
    """Per-frame F1 at a fixed IoU, scores ignored -- the v1 convention (run_ego_only.py)."""
    pred = np.asarray(pred, np.float32)
    gt = np.asarray(gt, np.float32)
    pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
    gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
    rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, iou)
    tp = sum(rs[iou]['tp'])
    fp = sum(rs[iou]['fp'])
    g = rs[iou]['gt']
    p = tp / (tp + fp) if tp + fp > 0 else 0.
    r = tp / g if g > 0 else 0.
    return (2 * p * r / (p + r)) if p + r > 0 else 0.


def ap_global(boxes, scores, gts, thr=0.5):
    """Global-sort AP: one score ranking over ALL frames, the v1 convention."""
    tot = int(sum(len(np.asarray(g)) for g in gts))
    rs = {thr: {'tp': [], 'fp': [], 'gt': tot, 'score': []}}
    for i in range(len(boxes)):
        pb = np.asarray(boxes[i], np.float32)
        ps = np.asarray(scores[i], np.float32)
        g = np.asarray(gts[i], np.float32)
        pt = torch.from_numpy(pb) if pb.size else torch.zeros((0, 8, 3))
        gt_t = torch.from_numpy(g) if g.size else torch.zeros((0, 8, 3))
        st = torch.from_numpy(ps) if ps.size else torch.zeros((0,))
        r1 = {thr: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
        eval_utils.caluclate_tp_fp(pt, st, gt_t, r1, thr)
        for k in ('tp', 'fp', 'score'):
            rs[thr][k] += r1[thr][k]
    return float(eval_utils.calculate_ap(rs, thr, True)[0])


def ego_only_batch(cav):
    """Return a copy of the ego cav_content restricted to the ego vehicle's own voxels.

    `voxel_coords[:, 0]` is the index of the CAV inside the stacked sample (see
    SpVoxelPreprocessor.collate_batch_*), and the intermediate dataset puts the ego at 0.
    """
    out = copy.copy(cav)
    pl = cav['processed_lidar']
    keep = pl['voxel_coords'][:, 0] == 0
    out['processed_lidar'] = {
        'voxel_features': pl['voxel_features'][keep],
        'voxel_coords': pl['voxel_coords'][keep],
        'voxel_num_points': pl['voxel_num_points'][keep],
    }
    out['record_len'] = torch.tensor([1], dtype=cav['record_len'].dtype,
                                     device=cav['record_len'].device)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', default=CKPT)
    ap.add_argument('--split', default='validate')
    ap.add_argument('--limit', type=int, default=200)
    ap.add_argument('--tag', default='')
    ap.add_argument('--data_root', default=DATA_ROOT)
    ap.add_argument('--every', type=int, default=9,
                    help='take every Nth frame. validate is 1980 frames over 9 scenes in index '
                         'order, so the first 200 consecutive frames are ONE scene -- a biased '
                         'sample for a check whose whole job is to be representative. Default 9 '
                         'spreads the sample over all nine.')
    args = ap.parse_args()

    class O:
        model_dir = args.model_dir
    hypes = yaml_utils.load_yaml(None, O)
    split_dir = os.path.join(args.data_root, args.split)
    if not os.path.isdir(split_dir):
        raise SystemExit(f'split directory not found: {split_dir}')
    hypes['root_dir'] = split_dir
    hypes['validate_dir'] = split_dir
    ds = build_dataset(hypes, visualize=False, train=False)
    ds.catosg_split = args.split   # V2-R16 B-3: part of the seed identity
    loader = DataLoader(ds, batch_size=1, num_workers=4, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False)
    n_total = len(ds)
    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(args.model_dir, model)
    model.eval()
    print(f'dataset: {n_total} frames ({args.split}); scoring the first {args.limit}', flush=True)
    print(f'device: {device}; score_threshold from the checkpoint config: '
          f'{hypes["postprocess"]["target_args"]["score_threshold"]}', flush=True)

    # scene boundaries, so the report can state the coverage instead of asserting it
    len_record = list(getattr(ds, 'len_record', []) or [])
    def scene_of(idx):
        for s, end in enumerate(len_record):
            if idx < end:
                return s
        return -1

    rows = []
    co_b, co_s, co_g = [], [], []
    sv_b, sv_s, sv_g = [], [], []
    t0 = time.time()
    taken = 0
    for i, batch in enumerate(loader):
        if taken >= args.limit:
            break
        if i % args.every:
            continue
        taken += 1
        batch = train_utils.to_device(batch, device)
        cav = batch['ego']
        n_cav = int(cav['record_len'].sum().item())
        with torch.no_grad():
            pb, ps, gt = inference_utils.inference_intermediate_fusion(batch, model, ds)
            solo = {'ego': ego_only_batch(cav)}
            # GT and anchors come from the untouched ego dict, so both arms share one GT
            solo['ego']['anchor_box'] = cav['anchor_box']
            solo['ego']['transformation_matrix'] = cav['transformation_matrix']
            pb2, ps2, gt2 = inference_utils.inference_intermediate_fusion(solo, model, ds)

        def np_(t, shp):
            return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
        b1, s1, g1 = np_(pb, (0, 8, 3)), np_(ps, (0,)), np_(gt, (0, 8, 3))
        b2, s2, g2 = np_(pb2, (0, 8, 3)), np_(ps2, (0,)), np_(gt2, (0, 8, 3))
        assert len(g1) == len(g2), f'frame {i}: GT differs between arms ({len(g1)} vs {len(g2)})'
        co_b.append(b1); co_s.append(s1); co_g.append(g1)
        sv_b.append(b2); sv_s.append(s2); sv_g.append(g2)
        rows.append(dict(frame=i, scene=scene_of(i), n_cav=n_cav, n_gt=len(g1),
                         n_box_coop=len(b1), n_box_single=len(b2),
                         f1_coop=f1_from_boxes(b1, g1), f1_single=f1_from_boxes(b2, g1)))
        if taken % 25 == 1:
            print(f'  {taken}/{args.limit} (frame {i}, scene {scene_of(i)})  cav={n_cav} '
                  f'gt={len(g1)} coop={len(b1)} single={len(b2)}', flush=True)
    dt = time.time() - t0

    import pandas as pd
    df = pd.DataFrame(rows)
    os.makedirs(OUT_DIR, exist_ok=True)
    tag = f'_{args.tag}' if args.tag else ''
    csv_path = os.path.join(OUT_DIR, f'sanity_single_vehicle_{args.split}{tag}.csv')
    df.to_csv(csv_path, index=False)

    res = {
        'split': args.split, 'frames': len(df), 'dataset_frames': n_total,
        'model_dir': args.model_dir,
        'score_threshold': float(hypes['postprocess']['target_args']['score_threshold']),
        'seconds': round(dt, 1), 'sec_per_frame': round(dt / max(len(df), 1), 3),
        'ap50_coop': ap_global(co_b, co_s, co_g, 0.5),
        'ap70_coop': ap_global(co_b, co_s, co_g, 0.7),
        'ap50_single': ap_global(sv_b, sv_s, co_g, 0.5),
        'ap70_single': ap_global(sv_b, sv_s, co_g, 0.7),
        'f1_coop_mean': float(df.f1_coop.mean()), 'f1_single_mean': float(df.f1_single.mean()),
        'n_cav_mean': float(df.n_cav.mean()), 'n_cav_max': int(df.n_cav.max()),
        'every': args.every, 'scenes_covered': int(df.scene.nunique()),
        'scenes_total': len(len_record) or None,
        'frames_per_scene': {str(k): int(v) for k, v in df.scene.value_counts().sort_index().items()},
        'n_gt_mean': float(df.n_gt.mean()),
        'boxes_coop': {k: float(v) for k, v in df.n_box_coop.describe().items()},
        'boxes_single': {k: float(v) for k, v in df.n_box_single.describe().items()},
    }
    ap_ref, f1_ref = frozen_ego_ap(args.split)
    res['frozen_v1_ego_ap50'] = ap_ref
    res['frozen_v1_ego_f1'] = f1_ref
    res['fuse_threshold_ap50'] = ap_ref / 2.0
    res['fuse_blown'] = bool(res['ap50_single'] < ap_ref / 2.0)
    json_path = os.path.join(OUT_DIR, f'sanity_single_vehicle_{args.split}{tag}.json')
    with open(json_path, 'w') as f:
        json.dump(res, f, indent=1)

    print('\n' + '=' * 78)
    print(f'{"":22} {"cooperative":>12} {"single-vehicle":>15}')
    print(f'{"AP@0.5 (global sort)":22} {res["ap50_coop"]:>12.5f} {res["ap50_single"]:>15.5f}')
    print(f'{"AP@0.7 (global sort)":22} {res["ap70_coop"]:>12.5f} {res["ap70_single"]:>15.5f}')
    print(f'{"mean per-frame F1":22} {res["f1_coop_mean"]:>12.5f} {res["f1_single_mean"]:>15.5f}')
    print(f'{"boxes/frame mean":22} {res["boxes_coop"]["mean"]:>12.2f} '
          f'{res["boxes_single"]["mean"]:>15.2f}')
    print(f'{"boxes/frame median":22} {res["boxes_coop"]["50%"]:>12.1f} '
          f'{res["boxes_single"]["50%"]:>15.1f}')
    print(f'{"boxes/frame max":22} {res["boxes_coop"]["max"]:>12.0f} '
          f'{res["boxes_single"]["max"]:>15.0f}')
    print('=' * 78)
    print(f'GT/frame mean {res["n_gt_mean"]:.2f} | CAVs/frame mean {res["n_cav_mean"]:.2f} '
          f'(max {res["n_cav_max"]}) | {res["sec_per_frame"]:.3f} s/frame')
    print(f'sample: every {args.every}th frame, {res["scenes_covered"]}/'
          f'{res["scenes_total"]} scenes covered')
    print(f'FUSE: v1 frozen ego-only AP@0.5 = {ap_ref:.5f} -> stop below {ap_ref / 2:.5f}. '
          f'single-vehicle = {res["ap50_single"]:.5f} -> '
          f'{"BLOWN -- STOP" if res["fuse_blown"] else "intact"}')
    print(f'wrote {os.path.relpath(csv_path, ROOT)}\n      {os.path.relpath(json_path, ROOT)}')
    return 1 if res['fuse_blown'] else 0


if __name__ == '__main__':
    sys.exit(main())
