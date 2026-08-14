#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-C: build the per-frame caches for a collaborator-scale arm (Change-log P4-C).

For an arm N, a frame only needs a new forward when its collaborator count EXCEEDS N -- otherwise
the N-subset IS the full set and the committed full-set cache already answers it. This driver
therefore re-runs only those frames and splices them into a copy of the existing cache, which is
what makes the sweep ~54 GPU-min instead of ~3 GPU-hours.

The subset itself is applied inside OpenCOOD by opencood/utils/catosg_collab_subset.py (#self+),
driven by CATOSG_MAX_COLLAB, which this script sets. Verified before use: with the variable unset
the loader is bit-identical to the pre-patch code, and with it set the outputs differ on exactly
the frames whose collaborator count exceeds N.

  python p4c_infer.py --split validate --fusion late --n 2 --model_dir <dir> --out <npz>

Run from the OpenCOOD checkout with PYTHONPATH=. (it needs the opencood package and the dataset).
"""
import argparse
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

OPENCOOD = os.environ.get('CATOSG_OPENCOOD', os.getcwd())
sys.path.insert(0, OPENCOOD)
from opencood.hypes_yaml import yaml_utils                      # noqa: E402
from opencood.tools import train_utils, inference_utils         # noqa: E402
from opencood.data_utils.datasets import build_dataset          # noqa: E402

DATASET = {'validate': 'dataset_validate.csv', 'test': 'dataset_test_v3.csv',
           'culver': 'dataset_culver_v3.csv'}
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')


def frames_needing_forward(split, n):
    """Indices whose collaborator count exceeds n (num_cavs counts the ego)."""
    ds = pd.read_csv(os.path.join(DATA, DATASET[split]))
    k = ds['num_cavs'].to_numpy() - 1
    return np.nonzero(k > n)[0], len(ds), k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', required=True, choices=sorted(DATASET))
    ap.add_argument('--fusion', required=True, choices=['late', 'intermediate'])
    ap.add_argument('--n', type=int, required=True)
    ap.add_argument('--model_dir', required=True)
    ap.add_argument('--base_cache', required=True, help='full-set cache to splice into')
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0, help='debug: only the first K needed frames')
    ap.add_argument('--frames_npy', default='', help='explicit frame indices (semantics-B bracket)')
    ap.add_argument('--nth', type=int, default=0, help='keep EXACTLY the j-th nearest collaborator')
    opt = ap.parse_args()

    todo, n_frames, kcol = frames_needing_forward(opt.split, opt.n)
    if opt.frames_npy:
        todo = np.load(opt.frames_npy)
        print('explicit frame list: %d frames' % len(todo), flush=True)
    if opt.limit:
        todo = todo[:opt.limit]
    base = np.load(opt.base_cache, allow_pickle=True)
    boxes = list(base['boxes']); scores = list(base['scores']); gts = list(base['gts'])
    assert len(boxes) == n_frames, 'base cache has %d frames, dataset has %d' % (len(boxes), n_frames)
    print('[%s N=%d %s] %d/%d frames need a forward (%d reuse the full-set cache)'
          % (opt.split, opt.n, opt.fusion, len(todo), n_frames, n_frames - len(todo)), flush=True)
    if len(todo) == 0:
        np.savez(opt.out, boxes=np.array(boxes, dtype=object), scores=np.array(scores, dtype=object),
                 gts=np.array(gts, dtype=object), n_new=0, arm_n=opt.n)
        print('  nothing to run -- the arm equals the full set on this split; wrote a copy', flush=True)
        return 0

    if opt.nth:
        os.environ['CATOSG_NTH_COLLAB'] = str(opt.nth)           # exactly the j-th nearest collaborator
        os.environ.pop('CATOSG_MAX_COLLAB', None)
    else:
        os.environ['CATOSG_MAX_COLLAB'] = str(opt.n)             # the subset mask, on for this run

    class O:
        model_dir = opt.model_dir
    hypes = yaml_utils.load_yaml(None, O)
    ds = build_dataset(hypes, visualize=False, train=False)
    assert len(ds) == n_frames, 'loader has %d frames, dataset csv has %d' % (len(ds), n_frames)
    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(opt.model_dir, model)
    model.eval()
    inf = {'late': inference_utils.inference_late_fusion,
           'intermediate': inference_utils.inference_intermediate_fusion}[opt.fusion]

    sub = torch.utils.data.Subset(ds, todo.tolist())
    loader = DataLoader(sub, batch_size=1, num_workers=8, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False)
    t0 = time.time()
    with torch.no_grad():
        for j, batch in enumerate(loader):
            batch = train_utils.to_device(batch, dev)
            pb, ps, gb = inf(batch, model, ds)
            i = int(todo[j])
            boxes[i] = pb.cpu().numpy() if pb is not None else np.zeros((0, 8, 3), np.float32)
            scores[i] = ps.cpu().numpy() if ps is not None else np.zeros((0,), np.float32)
            gts[i] = gb.cpu().numpy() if gb is not None else np.zeros((0, 8, 3), np.float32)
            if (j + 1) % 200 == 0:
                el = time.time() - t0
                print('  %d/%d  %.3f s/frame  eta %.1f min'
                      % (j + 1, len(todo), el / (j + 1), (len(todo) - j - 1) * el / (j + 1) / 60),
                      flush=True)
    el = time.time() - t0
    np.savez(opt.out, boxes=np.array(boxes, dtype=object), scores=np.array(scores, dtype=object),
             gts=np.array(gts, dtype=object), n_new=len(todo), arm_n=opt.n,
             sec_per_frame=el / max(1, len(todo)))
    print('  wrote %s  (%d new forwards, %.3f s/frame, %.1f min)'
          % (opt.out, len(todo), el / len(todo), el / 60), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
