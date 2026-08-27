#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Work package 2 — per-agent single-vehicle inference under the locked single-collaborator rule.

为 Validate、Test、Culver 生成每辆车的独立检测和中间 bottleneck。

THE COLLABORATOR RULE IS NOT RE-IMPLEMENTED HERE. `§2` of the protocol quotes the v1 P4-C subset
rule verbatim, and that rule already exists as executable code in the sibling checkout —
`opencood/utils/catosg_collab_subset.py`, applied inside `IntermediateFusionDataset.__getitem__`
before the pairwise transformation is built. Setting `CATOSG_MAX_COLLAB=1` selects **ego + the single
nearest collaborator by Euclidean distance on `lidar_pose[0:2]`, ties broken by ascending CAV id**.

Writing a second implementation of a rule the protocol quotes is how two definitions drift apart, so
this module sets the environment variable and asserts the effect, rather than re-deriving distances.

SINGLE-VEHICLE FORWARD is the exact identity established in the sanity check: `AttFusion` with
`record_len=[1]` self-attends over one element, so `attn == 1.0` and `context == value`.

VALIDATE-ONLY DISCIPLINE (E-2): this module *generates* test and Culver-City products, and nothing
here reads them back. They are written and left alone until the manifest freeze.

    python projects/ca_tosg/evaluation/v2_wp2_per_agent.py --split validate            # full
    python projects/ca_tosg/evaluation/v2_wp2_per_agent.py --split validate --every 9  # health check
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# set BEFORE the dataset module is imported/used, so the subset rule is active for every __getitem__
os.environ.setdefault('CATOSG_MAX_COLLAB', '1')
# V2-R16: deterministic per-sample point shuffle on the evaluation path
os.environ.setdefault('CATOSG_EVAL_RNG', '1')

from torch.utils.data import DataLoader, Subset                                  # noqa: E402

from opencood.data_utils.datasets import build_dataset                           # noqa: E402
from opencood.hypes_yaml import yaml_utils                                       # noqa: E402
from opencood.tools import inference_utils, train_utils                          # noqa: E402

from v2_single_vehicle_sanity import CKPT, DATA_ROOT, ap_global, f1_from_boxes   # noqa: E402
from v2_wp1_invariants import assert_invariants                                  # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
SPLIT_DIR = {'validate': 'validate', 'test': 'test', 'culver': 'test_culver_city'}


def one_cav(cav, row):
    """The batch restricted to a single stacked CAV row (0 = ego, 1 = the nearest collaborator)."""
    out = copy.copy(cav)
    pl = cav['processed_lidar']
    keep = pl['voxel_coords'][:, 0] == row
    if not bool(keep.any()):
        return None
    vc = pl['voxel_coords'][keep].clone()
    vc[:, 0] = 0                                     # renumber to a single-CAV batch
    out['processed_lidar'] = {'voxel_features': pl['voxel_features'][keep],
                              'voxel_coords': vc,
                              'voxel_num_points': pl['voxel_num_points'][keep]}
    out['record_len'] = torch.tensor([1], dtype=cav['record_len'].dtype,
                                     device=cav['record_len'].device)
    out['anchor_box'] = cav['anchor_box']
    out['transformation_matrix'] = cav['transformation_matrix']
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', default=CKPT)
    ap.add_argument('--data_root', default=DATA_ROOT)
    ap.add_argument('--split', default='validate', choices=list(SPLIT_DIR))
    ap.add_argument('--every', type=int, default=1, help='1 = every frame (the real product run)')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--tag', default='')
    ap.add_argument('--held-out-eval', action='store_true',
                    help='compute accuracy on a held-out split. Work package 11 only.')
    args = ap.parse_args()

    class O:
        model_dir = args.model_dir
    hypes = yaml_utils.load_yaml(None, O)
    d = os.path.join(args.data_root, SPLIT_DIR[args.split])
    if not os.path.isdir(d):
        raise SystemExit(f'split directory not found: {d}')
    hypes['root_dir'] = hypes['validate_dir'] = d

    # WP1 is a PRECONDITION, not a separate chore: nothing is written if an invariant moved.
    assert_invariants(args.model_dir, hypes)
    print(f'WP1 invariants: PASS  |  CATOSG_MAX_COLLAB={os.environ["CATOSG_MAX_COLLAB"]}')

    ds = build_dataset(hypes, visualize=False, train=False)

    ds.catosg_split = args.split   # V2-R16 B-3: part of the seed identity
    idx = list(range(0, len(ds), args.every))
    if args.limit:
        idx = idx[:args.limit]
    loader = DataLoader(Subset(ds, idx), batch_size=1, num_workers=4,
                        collate_fn=ds.collate_batch_test, shuffle=False, pin_memory=False)
    print(f'{args.split}: {len(ds)} frames, running {len(idx)}', flush=True)

    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(args.model_dir, model)
    model.eval()

    rows, eb, es, gts, cb, cs = [], [], [], [], [], []
    n_no_collab = 0
    t0 = time.time()
    for i, batch in enumerate(loader):
        b = train_utils.to_device(batch, dev)
        cav = b['ego']
        n_cav = int(cav['record_len'].sum().item())

        def np_(t, shp):
            return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)

        with torch.no_grad():
            solo = one_cav(cav, 0)
            p, s, g = inference_utils.inference_intermediate_fusion({'ego': solo}, model, ds)
            E_b, E_s, G = np_(p, (0, 8, 3)), np_(s, (0,)), np_(g, (0, 8, 3))
            C_b, C_s = np.zeros((0, 8, 3), np.float32), np.zeros((0,), np.float32)
            if n_cav >= 2:
                col = one_cav(cav, 1)
                if col is not None:
                    p2, s2, _ = inference_utils.inference_intermediate_fusion({'ego': col},
                                                                             model, ds)
                    C_b, C_s = np_(p2, (0, 8, 3)), np_(s2, (0,))
            else:
                n_no_collab += 1
        eb.append(E_b); es.append(E_s); gts.append(G); cb.append(C_b); cs.append(C_s)
        r = dict(frame=idx[i], n_cav=n_cav, has_collab=int(n_cav >= 2), n_gt=len(G),
                 n_box_ego=len(E_b), n_box_collab=len(C_b))
        # A per-frame F1 on a held-out split is MORE informative than the aggregate, not less, so
        # it is sealed at the same standard (E-2). Box counts stay: they feed payload accounting,
        # which is not accuracy.
        if args.split == 'validate' or args.held_out_eval:
            r['f1_ego'] = f1_from_boxes(E_b, G)
        rows.append(r)
        if i % 100 == 0:
            print(f'  {i}/{len(idx)} frame={idx[i]} cav={n_cav} gt={len(G)} '
                  f'ego={len(E_b)} collab={len(C_b)}', flush=True)
    dt = time.time() - t0

    import pandas as pd
    df = pd.DataFrame(rows)
    os.makedirs(OUT_DIR, exist_ok=True)
    tag = f'_{args.tag}' if args.tag else ''
    csv = os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}{tag}.csv')
    df.to_csv(csv, index=False)
    npz = os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}{tag}.npz')
    np.savez(npz, ego_boxes=np.array(eb, dtype=object), ego_scores=np.array(es, dtype=object),
             collab_boxes=np.array(cb, dtype=object), collab_scores=np.array(cs, dtype=object),
             gts=np.array(gts, dtype=object), frames=np.array(df.frame.to_numpy()))
    summary = {
        'schema': 'catosg-v2-wp2/1', 'split': args.split, 'frames': len(df),
        'dataset_frames': len(ds), 'every': args.every,
        'collaborator_rule': 'CATOSG_MAX_COLLAB=1 -- opencood/utils/catosg_collab_subset.py, '
                             'the v1 P4-C rule the protocol quotes verbatim in sec 2',
        'frames_with_collaborator': int(df.has_collab.sum()),
        'frames_without_collaborator': int(n_no_collab),
        'n_cav_max': int(df.n_cav.max()), 'n_cav_mean': float(df.n_cav.mean()),
        'n_gt_mean': float(df.n_gt.mean()),
        'n_box_ego_mean': float(df.n_box_ego.mean()),
        'n_box_collab_mean': float(df[df.has_collab == 1].n_box_collab.mean())
        if df.has_collab.any() else None,
        # E-2: on a held-out split this is accuracy computed before the selector freeze. It is not
        # written into the ordinary summary, because a number that sits in a file people read is a
        # number that informs decisions whether or not anyone meant it to. WP11 passes
        # --held-out-eval when it is time.
        **({'ego_ap50': ap_global(eb, es, gts, 0.5), 'ego_f1_mean': float(df.f1_ego.mean())}
           if (args.split == 'validate' or args.held_out_eval) else
           {'held_out_accuracy': 'NOT COMPUTED -- sealed until work package 11 (E-2)'}),
        'seconds': round(dt, 1), 'sec_per_frame': round(dt / max(len(df), 1), 3),
    }
    with open(os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}{tag}.json'), 'w') as f:
        json.dump(summary, f, indent=1)

    print('\n' + '=' * 78)
    print(f'WP2 {args.split}: {len(df)} frames')
    print('=' * 78)
    print(f'  n_cav after the rule      max {summary["n_cav_max"]}  mean '
          f'{summary["n_cav_mean"]:.3f}   <- must be <= 2')
    print(f'  frames with a collaborator {summary["frames_with_collaborator"]} / {len(df)}')
    print(f'  GT/frame mean              {summary["n_gt_mean"]:.2f}')
    print(f'  ego boxes/frame mean       {summary["n_box_ego_mean"]:.2f}')
    print(f'  collaborator boxes/frame   {summary["n_box_collab_mean"]}')
    if 'ego_ap50' in summary:
        print(f'  ego AP@0.5 / mean F1       {summary["ego_ap50"]:.5f} / '
              f'{summary["ego_f1_mean"]:.5f}')
    else:
        print('  ego AP@0.5 / mean F1       sealed (held-out split, E-2)')
    print(f'  {summary["sec_per_frame"]:.3f} s/frame')
    if summary['n_cav_max'] > 2:
        print('  FAIL: the single-collaborator rule did not take effect')
        return 1
    print(f'wrote {os.path.relpath(csv, ROOT)}\n      {os.path.relpath(npz, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
