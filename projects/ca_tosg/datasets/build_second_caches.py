#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-B-e: the SECOND per-frame caches (E and F branches) for all three splits.

Runs the **verified** converted SECOND checkpoint (P4-B-c: reproduces the model zoo's own AP to
+0.0008 / +0.0019) over each split twice:

  comp_{split}.npz   intermediate fusion  -> the F branch, and the canonical union GT
  ego_{split}.npz    the same model with every collaborator removed -> the E branch

and scores per frame with the mainline scorer and the mainline canonical union GT convention
(`canonical_rescore.py` / `run_ego_only.py`): F1 at IoU 0.5 against the comp cache's union GT, no
crop, no visibility filter.

The `L` branch is NOT built here and is not faked: it needs the SECOND *late-fusion* checkpoint,
which is not on disk and cannot be fetched (see the P4-B-e change-log entry). Without `eff_L` there
is no eff matrix, so nothing downstream of this script is run either.

Ego-only is produced by the same collaborator-subsetting hook the P4-C arm uses
(`CATOSG_MAX_COLLAB=0` -> ego alone), so "ego" means the identical model on the identical frame with
no collaborator, not a different network.

    python projects/ca_tosg/datasets/build_second_caches.py [--splits validate test culver]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
CKPT = ('/mnt/h/opencood_project/pretrained_models/second_attentive_fusion_spconv2/'
        'second_attentive_fusion_compression')
CKPT_LATE = '/mnt/h/opencood_project/pretrained_models/second_late_fusion_spconv2'
DATA_ROOT = '/mnt/h/opencood_project/datasets/opv2v_data_dumping'
OUT_DIR = os.path.join(OPENCOOD, 'peiyi_work/paper1/gs_rerun_second')
SPLIT_DIR = {'validate': 'validate', 'test': 'test', 'culver': 'test_culver_city'}


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def f1_per_frame(boxes, gts, iou=0.5):
    """Mainline convention: F1 at IoU 0.5, unit scores, canonical union GT, no crop/visibility."""
    import torch

    from opencood.utils import eval_utils
    out = []
    for pred, gt in zip(boxes, gts):
        pred = np.asarray(pred, np.float32)
        gt = np.asarray(gt, np.float32)
        pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
        gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
        rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
        eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, iou)
        tp, fp, g = sum(rs[iou]['tp']), sum(rs[iou]['fp']), rs[iou]['gt']
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / g if g else 0.0
        out.append((2 * p * r / (p + r)) if p + r else 0.0)
    return np.asarray(out, dtype=np.float32)


def run_late(split):
    """The L branch: SECOND late fusion, its own checkpoint and its own LateFusionDataset.

    Scored later against the SAME canonical union GT as E and F (the comp cache's `gts`), so the
    three branches sit on one ruler exactly as the mainline's do.
    """
    import copy

    import torch
    from torch.utils.data import DataLoader
    from tqdm import tqdm

    import opencood.hypes_yaml.yaml_utils as yaml_utils
    from opencood.data_utils.datasets import build_dataset
    from opencood.tools import inference_utils, train_utils

    os.environ.pop('CATOSG_MAX_COLLAB', None)
    hypes = copy.deepcopy(yaml_utils.load_yaml(os.path.join(CKPT_LATE, 'config.yaml'), None))
    hypes['validate_dir'] = os.path.join(DATA_ROOT, SPLIT_DIR[split])
    ds = build_dataset(hypes, visualize=False, train=False)
    loader = DataLoader(ds, batch_size=1, num_workers=8, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False, drop_last=False)
    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(dev)
    _, model = train_utils.load_saved_model(CKPT_LATE, model)
    model.eval()

    boxes, scores = [], []
    with torch.no_grad():
        for batch in tqdm(loader, desc=f'{split}/late'):
            batch = train_utils.to_device(batch, dev)
            pb, ps, _ = inference_utils.inference_late_fusion(batch, model, ds)
            boxes.append(pb.cpu().numpy() if pb is not None else np.zeros((0, 8, 3), np.float32))
            scores.append(ps.cpu().numpy() if ps is not None else np.zeros((0,), np.float32))
    return boxes, scores


def run_branch(split, ego_only):
    import copy

    import torch
    from torch.utils.data import DataLoader
    from tqdm import tqdm

    import opencood.hypes_yaml.yaml_utils as yaml_utils
    from opencood.data_utils.datasets import build_dataset
    from opencood.tools import inference_utils, train_utils

    if ego_only:
        os.environ['CATOSG_MAX_COLLAB'] = '0'          # the P4-C hook: ego alone
    else:
        os.environ.pop('CATOSG_MAX_COLLAB', None)

    hypes = copy.deepcopy(yaml_utils.load_yaml(os.path.join(CKPT, 'config.yaml'), None))
    hypes['validate_dir'] = os.path.join(DATA_ROOT, SPLIT_DIR[split])
    ds = build_dataset(hypes, visualize=False, train=False)
    loader = DataLoader(ds, batch_size=1, num_workers=8, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False, drop_last=False)
    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(dev)
    _, model = train_utils.load_saved_model(CKPT, model)
    model.eval()

    boxes, scores, gts = [], [], []
    with torch.no_grad():
        for batch in tqdm(loader, desc=f'{split}/{"ego" if ego_only else "comp"}'):
            batch = train_utils.to_device(batch, dev)
            pb, ps, gt = inference_utils.inference_intermediate_fusion(batch, model, ds)
            boxes.append(pb.cpu().numpy() if pb is not None else np.zeros((0, 8, 3), np.float32))
            scores.append(ps.cpu().numpy() if ps is not None else np.zeros((0,), np.float32))
            gts.append(gt.cpu().numpy() if gt is not None else np.zeros((0, 8, 3), np.float32))
    os.environ.pop('CATOSG_MAX_COLLAB', None)
    return boxes, scores, gts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--splits', nargs='+', default=['validate', 'test', 'culver'])
    ap.add_argument('--branches', nargs='+', default=['ego', 'comp'],
                    choices=['ego', 'comp', 'late'])
    args = ap.parse_args()
    sys.path.insert(0, OPENCOOD)
    os.makedirs(OUT_DIR, exist_ok=True)

    record = {
        'schema': 'catosg-p4b-cache-manifest/1',
        'protocol': 'CA-TOSG P4-B-e (docs/experiment_protocol.md)',
        'generated_by': 'python projects/ca_tosg/datasets/build_second_caches.py',
        'generated': datetime.now(timezone.utc).isoformat(),
        'checkpoint': CKPT,
        'checkpoint_sha256': sha256(os.path.join(CKPT, 'latest.pth')),
        'checkpoint_status': 'converted + verified against the model zoo AP (P4-B-c)',
        'payload_convention': {
            'B_F_SECOND_msym': 0.99,
            'N_cw': 3960,
            'bler_table': 'results/channel/bler_sionna.csv (mainline, unchanged)',
            'note': 'EQUAL-BUDGET CONTROLLED comparison: the SECOND F message is charged the '
                    'mainline per-frame channel budget so the two backbones are compared at the '
                    'same channel cost. This does NOT claim the SECOND feature tensor compresses '
                    'to that size, and it declares NO codec. Measured sizes (P4-B-d, recorded only, '
                    'not the operative payload): pre-compression 6,758,400 elements/CAV, '
                    'bottleneck 352,000 elements/CAV.',
        },
        'branches_built': ['E (ego-only)', 'F (intermediate/compressed)'],
        'branch_L': 'NOT BUILT -- the SECOND late-fusion checkpoint is absent and the zoo Box '
                    'direct link returns HTTP 403. eff_L is therefore unavailable and no grid '
                    'expansion, LOSO, budget walk or replay was run. The mainline PointPillar L '
                    'branch was deliberately NOT substituted.',
        'frozen_manifest_sha256': sha256(os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')),
        'frozen_manifest_note': 'recorded as evidence that the deployed freeze was not touched',
        'splits': {},
    }

    if args.branches == ['late']:
        # L-only pass: reuse the committed canonical GT from the existing comp cache so the three
        # branches are scored on one ruler; nothing already built is recomputed or overwritten.
        record['branches_built'] = ['L (late fusion)']
        record['branch_L'] = 'BUILT'
        record['checkpoint_late'] = CKPT_LATE
        record['checkpoint_late_sha256'] = sha256(os.path.join(CKPT_LATE, 'latest.pth'))
        for split in args.splits:
            comp = np.load(os.path.join(OUT_DIR, f'comp_{split}.npz'), allow_pickle=True)
            cg = list(comp['gts'])
            lb, ls = run_late(split)
            assert len(lb) == len(cg), f'{split}: late {len(lb)} vs canonical GT {len(cg)} frames'
            late_f1 = f1_per_frame(lb, cg)
            np.savez_compressed(os.path.join(OUT_DIR, f'late_{split}.npz'),
                                boxes=np.array(lb, dtype=object),
                                scores=np.array(ls, dtype=object), f1=late_f1)
            record['splits'][split] = {
                'frames': len(lb),
                'late_f1_mean': round(float(late_f1.mean()), 5),
                'late_npz_sha256': sha256(os.path.join(OUT_DIR, f'late_{split}.npz')),
            }
            print(f'[{split}] frames={len(lb)}  late_f1={late_f1.mean():.5f}', flush=True)
        record['zoo_bandwidth_crosscheck'] = (
            'the zoo row for this model lists bandwidth 0.024/0.024 Mbit, identical to the '
            'mainline B_L = 0.024 Mbit used throughout. Recorded as independent corroboration of '
            'the object-level payload convention; reported, not adjudicated.')
        out = os.path.join(ROOT, 'results/manifests/P4B_CACHE_LATE_MANIFEST.json')
        with open(out, 'w') as f:
            json.dump(record, f, indent=1)
            f.write('\n')
        print(f'\nwrote {out}')
        return 0

    for split in args.splits:
        cb, cs, cg = run_branch(split, ego_only=False)
        eb, es, _ = run_branch(split, ego_only=True)
        assert len(cb) == len(eb), f'{split}: comp {len(cb)} vs ego {len(eb)} frames'

        comp_f1 = f1_per_frame(cb, cg)
        ego_f1 = f1_per_frame(eb, cg)                  # ego scored on the SAME canonical union GT
        ego_num_objects = np.asarray([len(b) for b in eb], dtype=np.int32)

        np.savez_compressed(os.path.join(OUT_DIR, f'comp_{split}.npz'),
                            boxes=np.array(cb, dtype=object), scores=np.array(cs, dtype=object),
                            gts=np.array(cg, dtype=object), f1=comp_f1)
        np.savez_compressed(os.path.join(OUT_DIR, f'ego_{split}.npz'),
                            boxes=np.array(eb, dtype=object), scores=np.array(es, dtype=object),
                            f1=ego_f1, num_objects=ego_num_objects)
        record['splits'][split] = {
            'frames': len(cb),
            'gt_boxes_total': int(sum(len(g) for g in cg)),
            'compressed_f1_mean': round(float(comp_f1.mean()), 5),
            'ego_f1_mean': round(float(ego_f1.mean()), 5),
            'ego_num_objects_mean': round(float(ego_num_objects.mean()), 3),
            'comp_npz_sha256': sha256(os.path.join(OUT_DIR, f'comp_{split}.npz')),
            'ego_npz_sha256': sha256(os.path.join(OUT_DIR, f'ego_{split}.npz')),
        }
        print(f'[{split}] frames={len(cb)}  compressed_f1={comp_f1.mean():.5f}  '
              f'ego_f1={ego_f1.mean():.5f}  ego_objs={ego_num_objects.mean():.2f}', flush=True)

    # ---- pre-registered fuse conditions (E-P4Be) ----
    fuses = []
    for sp, r in record['splits'].items():
        if not 0.5 <= r['compressed_f1_mean'] <= 1.0:
            fuses.append(f'{sp}: compressed_f1 {r["compressed_f1_mean"]} outside [0.5, 1.0]')
    if record['splits'] and all(r['ego_f1_mean'] > r['compressed_f1_mean']
                                for r in record['splits'].values()):
        fuses.append('ego_f1 > compressed_f1 on EVERY split')
    record['fuse_conditions_E_P4Be'] = fuses or 'none triggered'

    out = os.path.join(ROOT, 'results/manifests/P4B_CACHE_MANIFEST.json')
    with open(out, 'w') as f:
        json.dump(record, f, indent=1)
        f.write('\n')
    print('\nFUSE:', record['fuse_conditions_E_P4Be'])
    print(f'wrote {out}')
    return 1 if fuses else 0


if __name__ == '__main__':
    sys.exit(main())
