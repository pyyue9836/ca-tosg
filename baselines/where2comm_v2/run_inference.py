#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R51: Where2comm budget-matched arm — inference at one communication threshold.

Per `docs/where2comm_rerun_plan_v2.md` §b, inference is cached PER GRID POINT and every later
question (which point meets which budget under which payload convention) is a table join over these
caches. Nothing about payload accounting happens here.

Three plan amendments are implemented here rather than the plan's original text, each recorded in
the change-log (R51):

  * **The grid is over the communication THRESHOLD, not over a sparsity `s`.** Reading
    `opencood/models/fuse_modules/where2comm_fuse.py`, `Communication.forward` at eval time builds
    `mask = confidence > threshold` and *measures* `communication_rate = mask.sum() / (L*H*W)`. The
    rate is an output, not a control. A plan that asks for `s = 0.05` cannot be executed as written.
  * **No retraining.** `CATOSG_MAX_COLLAB=1` is an inference-time hook
    (`opencood/utils/catosg_collab_subset.py`), and every mainline arm uses public pretrained
    checkpoints under it. Retraining Where2comm at N=1 would treat it *differently* from the arms it
    is compared against.
  * **The achieved rate is recorded per frame**, because the threshold-to-rate map is scene
    dependent and the budget match is done on the realised mean.

    PYTHONPATH=<OpenCOOD> python run_inference.py --model_dir <ckpt dir> --split validate \
        --threshold 0.01 --out <npz> [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch
from torch.utils.data import DataLoader

REPO = os.environ.get('OPENCOOD_ROOT',
                      os.path.expanduser('~/cooperative_semantic_perception/OpenCOOD'))
sys.path.insert(0, REPO)

from opencood.hypes_yaml import yaml_utils          # noqa: E402
from opencood.tools import train_utils, inference_utils  # noqa: E402
from opencood.data_utils.datasets import build_dataset   # noqa: E402

SPLIT_DIR = {
    'validate': 'validate',
    'test': 'test',
    'culver': 'test_culver_city',
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', required=True)
    ap.add_argument('--split', required=True, choices=sorted(SPLIT_DIR))
    ap.add_argument('--threshold', type=float, required=True,
                    help='Where2comm communication threshold (the grid axis; the achieved '
                         'sparsity is an OUTPUT, recorded per frame)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--data_root', default=None,
                    help='override the split directory (default: the checkpoint config)')
    a = ap.parse_args()

    # N = 1: the nearest single collaborator, the mainline convention (plan v2 §a).
    os.environ['CATOSG_MAX_COLLAB'] = '1'

    class O:
        model_dir = a.model_dir
    hypes = yaml_utils.load_yaml(None, O)

    # the grid axis
    fusion = hypes['model']['args']['where2comm_fusion']
    fusion['communication']['threshold'] = float(a.threshold)
    fusion['fully'] = False

    root = a.data_root or os.path.join(os.path.dirname(hypes['validate_dir'].rstrip('/')),
                                       SPLIT_DIR[a.split])
    hypes['validate_dir'] = root
    if not os.path.isdir(root):
        print(f'FAIL: split directory does not exist: {root}')
        return 1

    ds = build_dataset(hypes, visualize=False, train=False)
    n = len(ds)
    print(f'{a.split}: {n} frames | threshold={a.threshold} | N=1 | {root}', flush=True)
    loader = DataLoader(ds, batch_size=1, num_workers=4, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False)

    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(a.model_dir, model)
    model.eval()

    # the achieved communication rate is a model-internal quantity; capture it per frame
    rates = []
    fuse_mod = model.fusion_net.naive_communication
    orig_forward = fuse_mod.forward

    def capture(batch_confidence_maps, B):
        masks, rate = orig_forward(batch_confidence_maps, B)
        rates.append(float(rate.detach().cpu()) if torch.is_tensor(rate) else float(rate))
        return masks, rate
    fuse_mod.forward = capture

    boxes_all, scores_all, gts_all = [], [], []
    t0 = time.time()
    with torch.no_grad():
        for i, batch in enumerate(loader):
            if a.limit and i >= a.limit:
                break
            batch = train_utils.to_device(batch, device)
            pred_box, pred_score, gt_box = inference_utils.inference_intermediate_fusion(
                batch, model, ds)
            boxes_all.append(pred_box.cpu().numpy() if torch.is_tensor(pred_box) else pred_box)
            scores_all.append(pred_score.cpu().numpy() if torch.is_tensor(pred_score) else pred_score)
            gts_all.append(gt_box.cpu().numpy() if torch.is_tensor(gt_box) else gt_box)
            if (i + 1) % 100 == 0:
                el = time.time() - t0
                print(f'  {i + 1}/{n} frames, {el:.1f}s ({el / (i + 1):.3f} s/frame)', flush=True)
    elapsed = time.time() - t0

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    np.savez_compressed(
        a.out,
        boxes=np.array(boxes_all, dtype=object), scores=np.array(scores_all, dtype=object),
        gts=np.array(gts_all, dtype=object), comm_rate=np.array(rates, dtype=np.float64),
        threshold=np.float64(a.threshold))
    meta = {
        'schema': 'catosg-where2comm-v2/1',
        'split': a.split, 'frames': len(boxes_all), 'threshold': a.threshold,
        'collaborators': 'N=1 (CATOSG_MAX_COLLAB=1, nearest)',
        'model_dir': a.model_dir, 'data_root': root,
        'mean_comm_rate': float(np.mean(rates)) if rates else None,
        'gt_objects_total': int(sum(len(g) for g in gts_all)),
        'seconds': round(elapsed, 1), 'seconds_per_frame': round(elapsed / max(1, len(boxes_all)), 4),
    }
    with open(os.path.splitext(a.out)[0] + '.json', 'w') as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
