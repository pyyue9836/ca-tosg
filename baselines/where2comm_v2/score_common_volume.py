#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R55-1: score Where2comm grid points inside the THREE-WAY common volume, with a GT assertion.

Volume: |x| <= 70.4 (the late-fusion branch's limit), |y| <= 38.4 (Where2comm's limit) -- the
intersection of all three configured ranges, so no arm is charged for ground truth it cannot reach.

The GT assertion here is stronger than R51's, and has to be: comparing against the audit's
uncropped per-frame mean would say nothing about the cropped set. It compares this arm's cropped GT
count, per split, against the MAINLINE canonical GT cropped identically. Different counts mean the
two tracks are not looking at the same objects, and no AP is reported.

    python score_common_volume.py --npz <cache> [--x 70.4] [--y 38.4]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
sys.path.insert(0, os.environ.get('OPENCOOD_ROOT',
                                  os.path.expanduser('~/cooperative_semantic_perception/OpenCOOD')))

import end_to_end_ap as E                                  # noqa: E402
import deployment as D                                     # noqa: E402
import pandas as pd                                        # noqa: E402


def crop(arr, xl, yl):
    a = E.tt(arr, (0, 8, 3))
    if a.shape[0] == 0:
        return a, np.ones(0, dtype=bool)
    keep = (np.abs(a[:, :, 0].mean(1)) <= xl) & (np.abs(a[:, :, 1].mean(1)) <= yl)
    return a[keep], keep


def mainline_gt(split, xl, yl):
    """Canonical GT count of the mainline track, cropped the same way."""
    dc = np.load(os.path.join(E.GS, f'comp_{split}.npz'), allow_pickle=True)
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
    sids = ds['sample_id'].astype(int).to_numpy()
    cg = list(dc['gts'])
    return int(sum(crop(cg[s], xl, yl)[0].shape[0] for s in sids)), len(sids)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True)
    ap.add_argument('--x', type=float, default=70.4)
    ap.add_argument('--y', type=float, default=38.4)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()

    z = np.load(a.npz, allow_pickle=True)
    boxes, scores, gts = list(z['boxes']), list(z['scores']), list(z['gts'])
    meta = json.load(open(os.path.splitext(a.npz)[0] + '.json'))
    split, thr = meta['split'], float(z['threshold'])

    ST, gtn, tot = [], [], 0
    for b, s, g in zip(boxes, scores, gts):
        canon, _ = crop(g, a.x, a.y)
        pb, kb = crop(b, a.x, a.y)
        ps = E.tt(s, (0,))
        ps = ps[kb] if ps.shape[0] == kb.shape[0] else ps[:pb.shape[0]]
        ST.append(E.frame_stats(pb, ps, canon))
        gtn.append(canon.shape[0])
        tot += canon.shape[0]

    ref, ref_frames = mainline_gt(split, a.x, a.y)
    if len(gts) != ref_frames or tot != ref:
        print(f'GT ASSERTION FAIL [{split}]: this arm {len(gts)} frames / {tot} cropped GT objects; '
              f'the mainline canonical track {ref_frames} / {ref}. Not the same object set.')
        return 1
    print(f'GT assertion PASS [{split}]: {tot} cropped GT objects, identical to the mainline track')

    ap30, ap50, ap70 = E.ap_pick([0] * len(ST), [ST], gtn)
    out = dict(schema='catosg-where2comm-v2-commonvolume/1', split=split, threshold=thr,
               volume=f'|x|<={a.x}, |y|<={a.y}', frames=len(boxes), gt_objects=tot,
               mean_comm_rate=meta['mean_comm_rate'],
               ap_30=round(float(ap30), 5), ap_50=round(float(ap50), 5), ap_70=round(float(ap70), 5))
    print(json.dumps(out, indent=2))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(out, open(a.out, 'w'), indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
