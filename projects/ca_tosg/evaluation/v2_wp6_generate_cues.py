#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Work package 6 — generate the `v2_ego_local_23d` cue set. Zero GPU.

Protocol §9.0/§9.2 (V2-R22). Every field must be computable by the ego BEFORE it requests anything,
from its own sensor and its own channel estimate. Two v1 defects are removed by construction:

  * `ego_num_objects` was GROUND TRUTH (`params['vehicles']`) -> replaced by
    `ego_detected_box_count`, the ego-only detector's own output from the deterministic WP2 run at
    the frozen 0.20 / 0.15 thresholds;
  * the 17 `pcd_*` and 2 shape cues were computed over `np.vstack(projected_lidar_stack)`, the
    ALL-CAV cloud -- decision-after-information -> recomputed from the ego CAV's own sweep only.

ONE CONFIGURATION SOURCE, NOT TWO (D-3)
---------------------------------------
The points these cues describe are the *same array* the ego-only forward voxelises.
`get_item_single_car()` builds `projected_lidar` -- ego points, self-hits removed, range-filtered by
`params['preprocess']['cav_lidar_range']` -- and passes that identical `lidar_np` to
`pre_processor.preprocess()`. This module reads `projected_lidar` from that same call, so the scene
the cue describes is the scene action E actually sees. Nothing here re-declares a range constant; a
second hand-maintained copy is exactly the mismatch the rule exists to prevent.

THE STATISTIC DEFINITIONS ARE UNCHANGED, ON PURPOSE
---------------------------------------------------
`extract_pcd_features()` is imported from the v1 extractor rather than re-implemented, so the ONLY
thing that differs between the old and new columns is the point set. That is what makes the D-1
distribution comparison interpretable: a difference is attributable to the input, not to a quietly
rewritten formula.

    python projects/ca_tosg/evaluation/v2_wp6_generate_cues.py --split validate
"""
from __future__ import annotations

import argparse
import copy
import functools
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'projects', 'ca_tosg', 'datasets', 'test_split'))

os.environ.setdefault('CATOSG_MAX_COLLAB', '1')
os.environ.setdefault('CATOSG_EVAL_RNG', '1')

from opencood.data_utils import datasets as ocd                                 # noqa: E402
from opencood.data_utils.datasets import basedataset                            # noqa: E402
from opencood.utils import catosg_collab_subset, catosg_eval_rng                # noqa: E402

from v2_alignment_audit import build_ds, sha256_file                            # noqa: E402

# The v1 statistic definitions, imported verbatim. Only the point set changes.
import importlib.util                                                           # noqa: E402
_spec = importlib.util.spec_from_file_location(
    'v1_cue_extract',
    os.path.join(ROOT, 'projects/ca_tosg/datasets/test_split/02_extract_cues_and_f1.py'))
_mod = importlib.util.module_from_spec(_spec)
_src = open(_spec.origin, encoding='utf-8').read()
# execute only the pure helper; the module's top level opens dataset paths we do not want here
_ns = {'np': np}
exec(compile(_src[_src.index('def extract_pcd_features'):_src.index('def load_boxes')],
             _spec.origin, 'exec'), _ns)
extract_pcd_features = _ns['extract_pcd_features']

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
SEALED = os.path.join(OUT_DIR, 'sealed')
HELD_OUT = ('test', 'culver')
SCHEMA = 'v2_ego_local_23d'

# D-1 DECOMPOSITION. The v1 cue table was extracted under the LATE-FUSION config, whose
# cav_lidar_range is x in [-70.4, 70.4]; the v2 unified FOV is x in [-140.8, 140.8] (sec 3.1). So a
# bare "v1 cue vs v2 cue" table moves TWO things at once -- the point set (all-CAV -> ego-only) and
# the range (halved -> full) -- and the two push the point count in OPPOSITE directions, which is
# why the ego-only cloud is not obviously smaller. A two-factor change reported as one number is
# exactly what D-1 exists to prevent, so the SAME ego points are additionally masked to the v1
# x-range, isolating the point-set factor at no extra I/O.
V1_EXTRACT_X_ABS = 70.4

PCD_NAMES = ['pcd_num_points', 'pcd_mean_range', 'pcd_max_range', 'pcd_std_range', 'pcd_near_20m',
             'pcd_mid_20_50m', 'pcd_far_50_80m', 'pcd_very_far_80m', 'pcd_front_points',
             'pcd_back_points', 'pcd_left_points', 'pcd_right_points', 'pcd_front_far_30m',
             'pcd_front_far_50m', 'pcd_density_0_20', 'pcd_density_20_50', 'pcd_density_50_80']


def ego_points(ds, idx):
    """The ego CAV's own filtered point cloud -- the SAME array the ego-only forward voxelises.

    Returns (points, ego_id, has_collaborator). Nothing from any collaborator is touched: the
    per-CAV call is made for the ego alone, so `projected_lidar_stack` is never built.
    """
    base = ds.retrieve_base_data(idx, cur_ego_pose_flag=ds.cur_ego_pose_flag)
    ego_id = next((c for c in base if base[c]['ego']), None)
    if ego_id is None:
        raise SystemExit(f'frame {idx}: no ego in the base data')
    ego_pose = base[ego_id]['params']['lidar_pose']
    sub = catosg_collab_subset.subset_of(base, ego_pose)
    # availability is decided by the SAME rule the forward uses, including the COM_RANGE filter
    n_in_range = 0
    for cav_id, content in sub.items():
        if content['ego']:
            continue
        p = content['params']['lidar_pose']
        if ((p[0] - ego_pose[0]) ** 2 + (p[1] - ego_pose[1]) ** 2) ** 0.5 <= ocd.COM_RANGE:
            n_in_range += 1
    rng = catosg_eval_rng.sample_rng(getattr(ds, 'catosg_split', 'unknown'),
                                     ds._catosg_scene_of(idx), int(idx), str(ego_id)) \
        if catosg_eval_rng.enabled() else None
    proc = ds.get_item_single_car(base[ego_id], ego_pose, rng)
    return np.asarray(proc['projected_lidar']), str(ego_id), int(n_in_range >= 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate')
    ap.add_argument('--held-out-eval', action='store_true')
    args = ap.parse_args()
    # V2-R30 B-3: a held-out cue table is created IN sealed/, never written openly and moved.
    if args.split in HELD_OUT:
        if not args.held_out_eval:
            raise SystemExit(f'{args.split} is held out: pass --held-out-eval')
        os.makedirs(SEALED, exist_ok=True)
    dest = SEALED if args.split in HELD_OUT else OUT_DIR

    import pandas as pd
    wp2 = pd.read_csv(os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}.csv'))
    align = os.path.join(OUT_DIR, f'alignment_audit_{args.split}.json')
    if not os.path.exists(align):
        raise SystemExit('run v2_alignment_audit.py first -- the identity join is its guarantee')

    ds = build_ds(args.split)
    n = len(wp2)
    if len(ds) != n:
        raise SystemExit(f'dataset has {len(ds)} frames, WP2 has {n} -- refusing to align by row')

    # the yaml memo, with the deepcopy that makes it safe (see v2_alignment_audit for why)
    real_yaml = basedataset.load_yaml
    _memo = functools.lru_cache(maxsize=8192)(real_yaml)
    basedataset.load_yaml = lambda p, *_a, **_k: copy.deepcopy(_memo(p))

    rows, decomp = [], []
    t0 = time.time()
    try:
        for i in range(n):
            idx = int(wp2.frame.iloc[i])
            pts, ego_id, has_collab = ego_points(ds, idx)
            feats = extract_pcd_features(pts)
            row = {'frame': idx, 'ego_id': ego_id,
                   'ego_detected_box_count': int(wp2.n_box_ego.iloc[i]),
                   'has_collaborator': has_collab,
                   'ego_origin_lidar_shape_0': int(pts.shape[0]),
                   'ego_origin_lidar_shape_1': int(pts.shape[1]) if pts.ndim == 2 else -1}
            for k in PCD_NAMES:
                row['ego_' + k] = feats[k]
            rows.append(row)
            if pts.ndim == 2 and pts.shape[0]:
                d70 = extract_pcd_features(pts[np.abs(pts[:, 0]) <= V1_EXTRACT_X_ABS])
            else:
                d70 = extract_pcd_features(pts)
            decomp.append({'frame': idx, **{'ego70_' + k: d70[k] for k in PCD_NAMES}})
            if i % 200 == 0:
                print(f'  {i}/{n} frame={idx} ego={ego_id} pts={pts.shape[0]} '
                      f'collab={has_collab}', flush=True)
    finally:
        basedataset.load_yaml = real_yaml
    dt = time.time() - t0

    df = pd.DataFrame(rows)
    # C-7 / F-5: the identity join is checked, never assumed
    if not np.array_equal(df.frame.to_numpy(), wp2.frame.to_numpy()):
        raise SystemExit('frame vectors differ from WP2 -- refusing to write')
    if not np.array_equal(df.has_collaborator.to_numpy(), wp2.has_collab.to_numpy()):
        raise SystemExit('has_collaborator disagrees with WP2 has_collab -- stop')
    if not np.array_equal(df.ego_detected_box_count.to_numpy(), wp2.n_box_ego.to_numpy()):
        raise SystemExit('ego_detected_box_count disagrees with WP2 n_box_ego -- stop')

    csv = os.path.join(dest, f'wp6_cues_{args.split}.csv')
    df.to_csv(csv, index=False)
    pd.DataFrame(decomp).to_csv(
        os.path.join(dest, f'wp6_range_decomposition_{args.split}.csv'), index=False)
    fields = [c for c in df.columns if c not in ('frame', 'ego_id')]
    meta = {
        'schema': SCHEMA, 'split': args.split, 'frames': int(len(df)),
        'perception_fields': fields, 'n_perception_fields': len(fields),
        'channel_fields': ['est_snr_db', 'channel_is_rayleigh'],
        'total_dimensions': len(fields) + 2,
        'protocol': '§9.0 / §9.2 amendment, V2-R22',
        'point_source': "get_item_single_car()['projected_lidar'] for the EGO CAV ONLY -- the same "
                        "array pre_processor.preprocess() receives, so the cue describes exactly "
                        "the scene action E sees. projected_lidar_stack is never built.",
        'forbidden_and_absent': ['ground truth / object_ids / params[vehicles]',
                                 'collaborator point clouds', 'fused tensors',
                                 'task metrics', 'oracle labels', 'delivery outcomes'],
        'frozen_thresholds': {'score_threshold': 0.20, 'nms_iou': 0.15},
        'inputs': {f'wp2_per_agent_{args.split}.csv':
                   sha256_file(os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}.csv'))},
        'seconds': round(dt, 1),
    }
    with open(os.path.join(dest, f'wp6_cues_{args.split}.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    print(f'\n{SCHEMA}: {len(df)} frames, {len(fields)} perception + 2 channel = '
          f'{len(fields) + 2} dimensions')
    print(f'  ego points/frame  mean {df.ego_pcd_num_points.mean():.0f}  '
          f'range {df.ego_pcd_num_points.min()}-{df.ego_pcd_num_points.max()}')
    print(f'  ego_detected_box_count mean {df.ego_detected_box_count.mean():.2f}')
    print(f'  has_collaborator  {int(df.has_collaborator.sum())}/{len(df)}')
    print(f'wrote {os.path.relpath(csv, ROOT)}  ({dt:.0f} s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
