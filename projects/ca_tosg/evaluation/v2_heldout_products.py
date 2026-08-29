#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R29 C-1/C-2 — held-out WP3/WP4 (+ cue) products, written STRAIGHT INTO results/v2/sealed/.

Why this exists rather than a `--split test` on the ordinary generators: those PRINT AP and F1, and
V2-R29 C-6 forbids any intermediate step from printing or reading held-out accuracy. Once WP5 runs on
test the held-out F1 exists, and a single debug line would unseal it permanently. So this module

  * writes only into `results/v2/sealed/` (gate 22's extended scope, V2-R29 A-1), and
  * prints ONLY structural counts -- never an accuracy number.

    python projects/ca_tosg/evaluation/v2_heldout_products.py --split test --stage wp34
"""
from __future__ import annotations
import argparse, json, math, os, sys
import numpy as np, torch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, REPO); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from opencood.utils import box_utils                                            # noqa: E402
from v2_single_vehicle_sanity import f1_from_boxes                              # noqa: E402
from v2_payload_chain import B_BOX_BITS, l_chain                                # noqa: E402

V2 = os.path.join(ROOT, 'results', 'v2')
SEALED = os.path.join(V2, 'sealed')
NMS = 0.15


def fuse(eb, es, cb, cs):
    if len(eb) == 0 and len(cb) == 0:
        return np.zeros((0, 8, 3), np.float32), np.zeros((0,), np.float32)
    b = np.concatenate([x for x in (eb, cb) if len(x)], 0)
    s = np.concatenate([x for x in (es, cs) if len(x)], 0)
    k = box_utils.nms_rotated(torch.from_numpy(np.asarray(b, np.float32)),
                              torch.from_numpy(np.asarray(s, np.float32)), NMS)
    return b[k], s[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', required=True, choices=['test', 'culver'])
    ap.add_argument('--stage', required=True, choices=['wp34'])
    a = ap.parse_args()
    os.makedirs(SEALED, exist_ok=True)
    import pandas as pd
    d = np.load(os.path.join(V2, f'wp2_per_agent_{a.split}.npz'), allow_pickle=True)
    EB, ES, CB, CS, G = (d['ego_boxes'], d['ego_scores'], d['collab_boxes'],
                         d['collab_scores'], d['gts'])
    rows = []
    for i in range(len(EB)):
        fb, fs = fuse(EB[i], ES[i], CB[i], CS[i])
        n_box_t = len(CB[i])
        pay = l_chain(n_box_t)
        rows.append(dict(frame=int(d['frames'][i]), n_gt=len(G[i]), n_box_ego=len(EB[i]),
                         n_box_collab=n_box_t, n_box_L=len(fb),
                         f1_E=f1_from_boxes(EB[i], G[i]), f1_L=f1_from_boxes(fb, G[i]),
                         n_cw_L=pay['n_cw'], B_L_msym=pay['msym']))
    df = pd.DataFrame(rows)
    out = os.path.join(SEALED, f'wp34_e_l_{a.split}.csv')
    df.to_csv(out, index=False)
    # STRUCTURAL COUNTS ONLY -- no accuracy is printed (C-6)
    print(f'wp34 {a.split}: {len(df)} frames written to {os.path.relpath(out, ROOT)}')
    print(f'  n_box_ego mean {df.n_box_ego.mean():.2f}   n_box_collab mean '
          f'{df.n_box_collab.mean():.2f}   B_L mean {df.B_L_msym.mean():.5f} Msym')
    print('  accuracy columns are present in the file and are NOT printed (V2-R29 C-6)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
