#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Work package 5 — F products: int8 transport, clean and partial delivery.

生成 int8 quantise/dequantise、完整投递和部分投递条件下的 feature fusion 结果。

SCOPE, and why it stops where it does. WP5 produces F's output **as a function of codeword loss**.
Mapping SNR and channel onto a loss rate is work package 8's job, and keeping the two apart means the
expensive part (inference) is computed once against a loss axis rather than re-computed per channel
model.

§5's six rules, implemented literally
-------------------------------------
1. **Fixed flatten order.** branch 0, then 1, then 2, each C-H-W — the natural `reshape(-1)` of a
   (C, H, W) tensor. 35,200 + 140,800 + 563,200 = 739,200 elements.
2. **Contiguous packetisation.** payload bit `p` sits in packet `p // 8000` at offset `p % 8000`;
   inside the packet the first 320 bits are header, so the local bit index is `320 + offset`. No
   interleaving.
3. **A failed information block zero-fills the positions it carried.** Codeword `c` of a packet
   carries local bits `[500c, 500c+500)`; whichever payload bits those are, their elements go to
   zero. An element straddling two codewords is lost if **either** fails — a byte with a corrupted
   half is not a usable byte.
4. **CRC identifies the failed block**, so the receiver knows *which* positions to zero.
5. **Delivered blocks dequantise normally**, at the frozen per-branch scale.
6. **No reordering.** The mapping is computed once, from the flatten order above, and is identical
   for every frame and every loss rate.

A MODELLING CHOICE THAT MUST BE VISIBLE. Codeword 0 of each packet carries the 320 header bits plus
180 payload bits. Rule 3 says a failed block zero-fills *the positions it carried*, so losing it
zeroes those 180 payload bits and nothing more — the rest of the packet still decodes. A real stack
would usually drop the whole packet with its header. **The literal rule is implemented; the more
pessimistic reading belongs to the all-or-nothing sensitivity arm, not here.**

    python projects/ca_tosg/evaluation/v2_wp5_f_products.py --split validate
"""
from __future__ import annotations

import argparse
import contextlib
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

os.environ.setdefault('CATOSG_MAX_COLLAB', '1')

from torch.utils.data import DataLoader, Subset                                  # noqa: E402

from opencood.data_utils.datasets import build_dataset                           # noqa: E402
from opencood.hypes_yaml import yaml_utils                                       # noqa: E402
from opencood.tools import inference_utils, train_utils                          # noqa: E402

from v2_single_vehicle_sanity import CKPT, DATA_ROOT, ap_global, f1_from_boxes   # noqa: E402
from v2_wp1_invariants import assert_invariants                                  # noqa: E402
from v2_wp2_per_agent import SPLIT_DIR                                           # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
SCALES_JSON = os.path.join(ROOT, 'results', 'manifests', 'V2_INT8_SCALES.json')
CHAIN_JSON = os.path.join(OUT_DIR, 'payload_chain.json')
BRANCH_ELEMS = (35200, 140800, 563200)
W_BITS, P_BITS, H_BITS, K = 8, 8000, 320, 500
QMAX = 127
BASE_SEED = 20260809                                   # the protocol's CSI_SEED, reused for erasures
LOSS_RATES = (0.0, 0.001, 0.01, 0.05, 0.10, 0.25, 0.50)


def element_to_codeword():
    """Per element, the (first, last) codeword ids carrying its 8 bits. §5 rules 1, 2, 6.

    Computed once and reused for every frame and loss rate, which is what rule 6 requires: a mapping
    recomputed per frame could differ per frame, and then 'no reordering' would be unverifiable.
    """
    n_elem = sum(BRANCH_ELEMS)
    e = np.arange(n_elem, dtype=np.int64)

    def cw_of(bit):
        j = bit // P_BITS                                   # packet index
        local = H_BITS + (bit - j * P_BITS)                 # header sits first inside the packet
        return j * ((P_BITS + H_BITS + K - 1) // K) + local // K
    lo = cw_of(e * W_BITS)
    hi = cw_of(e * W_BITS + (W_BITS - 1))
    return lo, hi, n_elem


class Transport:
    """Quantise the collaborator's bottleneck, then erase whatever the failed codewords carried."""

    def __init__(self, backbone, scales, cw_lo, cw_hi):
        self.bb, self.scales = backbone, scales
        self.cw_lo, self.cw_hi = cw_lo, cw_hi
        self.n_cw = int(max(cw_hi.max(), cw_lo.max())) + 1
        off = np.cumsum((0,) + BRANCH_ELEMS)
        self.slices = [(off[i], off[i + 1]) for i in range(3)]
        self.masks = [None, None, None]                     # per-branch bool: element is lost
        self._saved = []

    def set_loss(self, p, seed):
        if p <= 0:
            self.masks = [None, None, None]
            self.n_lost_cw = 0
            return 0.0
        rng = np.random.default_rng(seed)
        dead = rng.random(self.n_cw) < p
        self.n_lost_cw = int(dead.sum())
        lost = dead[self.cw_lo] | dead[self.cw_hi]          # rule 3: either half corrupt -> lost
        self.masks = [lost[a:b] for a, b in self.slices]
        return float(lost.mean())

    def _apply(self, x, b):
        if x.shape[0] < 2:
            return x                                        # no collaborator: nothing transmitted
        s = self.scales[b]
        collab = x[1:]
        deq = torch.clamp(torch.round(collab / s), -QMAX, QMAX) * s   # rules 5 + B-4
        m = self.masks[b]
        if m is not None:
            flat = deq.reshape(deq.shape[0], -1)
            flat[:, torch.from_numpy(m).to(flat.device)] = 0.0        # rule 3: zero-fill
            deq = flat.reshape(deq.shape)
        out = x.clone()
        out[1:] = deq
        return out

    @contextlib.contextmanager
    def patched(self):
        bb = self.bb
        for i, ae in enumerate(bb.compression_modules):
            self._saved.append((ae, ae.forward))

            def make(ae=ae, b=i):
                def fwd(x):
                    for enc in ae.encoder:
                        x = enc(x)
                    x = self._apply(x, b)
                    for j in range(len(ae.decoder) - 1, -1, -1):
                        x = ae.decoder[j](x)
                    return x
                return fwd
            ae.forward = make()
        fm = bb.fuse_modules[2]
        saved = fm.forward

        def fuse_fwd(x, record_len, _f=saved):
            return _f(self._apply(x, 2), record_len)
        fm.forward = fuse_fwd
        try:
            yield self
        finally:
            for ae, f in self._saved:
                ae.forward = f
            self._saved.clear()
            fm.forward = saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', default=CKPT)
    ap.add_argument('--data_root', default=DATA_ROOT)
    ap.add_argument('--split', default='validate', choices=list(SPLIT_DIR))
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--tag', default='')
    args = ap.parse_args()
    if args.split != 'validate':
        raise SystemExit('WP5 is authorised for validate only in this batch (V2-R6 / user ruling). '
                         'Held-out splits wait for an explicit go.')

    class O:
        model_dir = args.model_dir
    hypes = yaml_utils.load_yaml(None, O)
    dd = os.path.join(args.data_root, SPLIT_DIR[args.split])
    hypes['root_dir'] = hypes['validate_dir'] = dd
    assert_invariants(args.model_dir, hypes)

    scales = json.load(open(SCALES_JSON))['scales']
    chain = json.load(open(CHAIN_JSON))['F']
    cw_lo, cw_hi, n_elem = element_to_codeword()
    n_cw = int(max(cw_lo.max(), cw_hi.max())) + 1
    print(f'WP1 invariants PASS | CATOSG_MAX_COLLAB={os.environ["CATOSG_MAX_COLLAB"]}')
    print(f'elements {n_elem:,}  (protocol {chain["elements"]:,})   '
          f'N_cw {n_cw:,}  (protocol {chain["n_cw"]:,})')
    if n_elem != chain['elements'] or n_cw != chain['n_cw']:
        raise SystemExit('WP5: the element/codeword mapping disagrees with the payload chain -- '
                         'stop. One of them is wrong and it is not safe to guess which.')
    print(f'scales {["%.8f" % s for s in scales]}')

    ds = build_dataset(hypes, visualize=False, train=False)
    idx = list(range(0, len(ds), args.every))
    if args.limit:
        idx = idx[:args.limit]
    loader = DataLoader(Subset(ds, idx), batch_size=1, num_workers=4,
                        collate_fn=ds.collate_batch_test, shuffle=False, pin_memory=False)
    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(args.model_dir, model)
    model.eval()
    print(f'{args.split}: {len(ds)} frames, running {len(idx)}, '
          f'{len(LOSS_RATES)} delivery conditions', flush=True)

    tp = Transport(model.backbone, scales, cw_lo, cw_hi)
    boxes = {p: [] for p in LOSS_RATES}
    scores = {p: [] for p in LOSS_RATES}
    gts, rows = [], []
    t0 = time.time()
    for i, batch in enumerate(loader):
        b = train_utils.to_device(batch, dev)
        cav = b['ego']
        n_cav = int(cav['record_len'].sum().item())
        rec = {'frame': idx[i], 'n_cav': n_cav, 'has_collab': int(n_cav >= 2)}
        G = None
        for pi, p in enumerate(LOSS_RATES):
            frac = tp.set_loss(p, BASE_SEED + idx[i] * 131 + pi)
            with torch.no_grad(), tp.patched():
                pb, ps, g = inference_utils.inference_intermediate_fusion({'ego': cav}, model, ds)

            def np_(t, shp):
                return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
            B, S = np_(pb, (0, 8, 3)), np_(ps, (0,))
            if G is None:
                G = np_(g, (0, 8, 3))
                gts.append(G)
            boxes[p].append(B); scores[p].append(S)
            rec[f'n_box_p{p}'] = len(B)
            rec[f'f1_p{p}'] = f1_from_boxes(B, G)
            if pi:
                rec[f'lost_elem_frac_p{p}'] = round(frac, 6)
                rec[f'lost_cw_p{p}'] = tp.n_lost_cw
        rows.append(rec)
        if i % 100 == 0:
            print(f'  {i}/{len(idx)} frame={idx[i]} cav={n_cav} gt={len(G)} '
                  f'clean={rec["n_box_p0.0"]} p50={rec["n_box_p0.5"]}', flush=True)
    dt = time.time() - t0

    import pandas as pd
    df = pd.DataFrame(rows)
    tag = f'_{args.tag}' if args.tag else ''
    df.to_csv(os.path.join(OUT_DIR, f'wp5_f_products_{args.split}{tag}.csv'), index=False)
    res = {'schema': 'catosg-v2-wp5/1', 'split': args.split, 'frames': len(df),
           'loss_rates': list(LOSS_RATES), 'n_cw': n_cw, 'elements': n_elem,
           'scales': scales, 'base_seed': BASE_SEED,
           'seconds': round(dt, 1), 'sec_per_frame': round(dt / max(len(df), 1), 3),
           'conditions': {}}
    for p in LOSS_RATES:
        res['conditions'][str(p)] = {
            'ap50': ap_global(boxes[p], scores[p], gts, 0.5),
            'ap70': ap_global(boxes[p], scores[p], gts, 0.7),
            'f1_mean': float(df[f'f1_p{p}'].mean()),
            'boxes_mean': float(df[f'n_box_p{p}'].mean()),
            'lost_elem_frac_mean': (float(df[f'lost_elem_frac_p{p}'].mean()) if p else 0.0),
            'lost_cw_mean': (float(df[f'lost_cw_p{p}'].mean()) if p else 0.0),
        }
    with open(os.path.join(OUT_DIR, f'wp5_f_products_{args.split}{tag}.json'), 'w') as f:
        json.dump(res, f, indent=1)

    print('\n' + '=' * 82)
    print(f'WP5 F products -- {args.split}, {len(df)} frames, int8, one collaborator')
    print('=' * 82)
    print(f'{"codeword loss":>14} {"lost cw":>9} {"lost elem":>10} {"AP@0.5":>9} {"AP@0.7":>9} '
          f'{"F1":>9} {"boxes":>7}')
    for p in LOSS_RATES:
        c = res['conditions'][str(p)]
        lab = 'clean' if p == 0 else f'{p:.3f}'
        print(f'{lab:>14} {c["lost_cw_mean"]:>9.0f} {c["lost_elem_frac_mean"]:>9.2%} '
              f'{c["ap50"]:>9.5f} {c["ap70"]:>9.5f} {c["f1_mean"]:>9.5f} {c["boxes_mean"]:>7.2f}')
    print('=' * 82)
    print(f'{res["sec_per_frame"]:.3f} s/frame over {len(LOSS_RATES)} conditions')
    return 0


if __name__ == '__main__':
    sys.exit(main())
