#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Work package 5, final — three delivery regimes, R=4 replicates, endpoints, identity check.

Supersedes the replicate=0 sweep in `v2_wp5_f_products.py`, which is kept (V2-R11 A-1) as the R=0
product and is not deleted or re-run.

THREE DELIVERY REGIMES, reported side by side from optimistic to pessimistic (V2-R9 B-4)
---------------------------------------------------------------------------------------
* **`ideal`** — *ideal fragment-aware partial recovery with known fragment positions*. The receiver
  knows the fragment mapping, so when a header-carrying codeword fails the rest of that packet's
  payload is still locatable and recoverable. This is the **main** regime, and the name is the point:
  it is an upper bound that assumes a mapping a real stack would have to signal.
* **`packet`** — packet-drop sensitivity. If the codeword carrying a packet's header fails, **the
  whole packet is unusable** and all of its payload is zeroed. Otherwise per-codeword as in `ideal`.
* **`message`** — all-or-nothing, at the **message** level: the message survives only if *every* one
  of the 12,567 codewords does, otherwise the receiver falls back to ego-only. Computed
  analytically from the clean and ego-only outputs; it needs no forward, because the outcome is one
  of exactly two things.

`packet` and `message` are different layers and neither substitutes for the other.

ELEMENT ZEROING (V2-R9 C-3): an int8 element whose 8 bits straddle two codewords is zeroed if
**either** fails. Partial zeroing would produce a value that is neither the original nor the zero
code point, which the dequantiser has no way to interpret. 5,914 of 739,200 elements (0.80 %)
straddle; 8 per packet, 2 in the tail.

IDENTITY CHECK (V2-R9 C-1): `clean` (masking skipped) and `all codewords succeed` (an all-False mask
applied) must agree **frame by frame on the predicted boxes and scores** — not on a rounded AP.
Tolerance is exact equality of shapes plus max |Δ| = 0 on both arrays; anything else stops the run.

    python projects/ca_tosg/evaluation/v2_wp5_final.py --split validate
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
# V2-R16: deterministic per-sample point shuffle on the evaluation path
os.environ.setdefault('CATOSG_EVAL_RNG', '1')

from torch.utils.data import DataLoader, Subset                                  # noqa: E402

from opencood.data_utils.datasets import build_dataset                           # noqa: E402
from opencood.hypes_yaml import yaml_utils                                       # noqa: E402
from opencood.tools import inference_utils, train_utils                          # noqa: E402

from v2_single_vehicle_sanity import CKPT, DATA_ROOT, ap_global, f1_from_boxes   # noqa: E402
from v2_wp1_invariants import assert_invariants                                  # noqa: E402
from v2_wp2_per_agent import SPLIT_DIR                                           # noqa: E402
from v2_wp5_f_products import BRANCH_ELEMS, QMAX, element_to_codeword            # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
SCALES_JSON = os.path.join(ROOT, 'results', 'manifests', 'V2_INT8_SCALES.json')
CHAIN_JSON = os.path.join(OUT_DIR, 'payload_chain.json')
BASE_SEED = 20260809
SEED_K = 1000003                 # A-5: fixed large prime, recorded in the protocol and manifest
CW_PER_PACKET = 17               # (8000 + 320 + 499) // 500
RATES = (0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90)
R_REPS = 4
REGIMES = ('ideal', 'packet')    # 'message' is analytic


def seed_of(frame, rate_idx, rep):
    return BASE_SEED + frame * 131 + rate_idx + rep * SEED_K


class Transport:
    def __init__(self, backbone, scales, cw_lo, cw_hi):
        self.bb, self.scales = backbone, scales
        self.cw_lo, self.cw_hi = cw_lo, cw_hi
        self.n_cw = int(max(cw_hi.max(), cw_lo.max())) + 1
        off = np.cumsum((0,) + BRANCH_ELEMS)
        self.slices = [(off[i], off[i + 1]) for i in range(3)]
        self.masks = [None, None, None]
        self.n_lost_cw = 0
        self.lost_frac = 0.0
        self._saved = []

    def to_device(self, dev):
        """Move the element->codeword mapping to the GPU once.

        The alternative -- expanding the mask on the CPU and shipping 739,200 booleans per condition
        -- moves ~93 GB across the bus over a full run, which is most of the wall clock. Only 12,567
        booleans per condition need to cross; the expansion is an indexing op the GPU does for free.
        The numpy RNG and the seed schedule are untouched, so the masks are bit-identical either way.
        """
        self.dev = dev
        self.t_lo = torch.from_numpy(self.cw_lo).to(dev)
        self.t_hi = torch.from_numpy(self.cw_hi).to(dev)
        return self

    def set_dead(self, dead, regime):
        """dead: bool[n_cw]. In `packet` regime a failed header codeword kills its whole packet."""
        if regime == 'packet':
            dead = dead.copy()
            hdr = np.arange(0, self.n_cw, CW_PER_PACKET)           # codeword 0 of each packet
            for h in hdr[dead[hdr]]:
                dead[h:min(h + CW_PER_PACKET, self.n_cw)] = True
        self.n_lost_cw = int(dead.sum())
        d = torch.from_numpy(dead).to(self.dev)                    # 12,567 bools, not 739,200
        keep = ~(d[self.t_lo] | d[self.t_hi])                      # C-3: either half -> element gone
        self.lost_frac = float(1.0 - keep.float().mean().item())
        self.masks = [keep[a:b].float() for a, b in self.slices]
        return dead

    def set_clean(self, apply_empty_mask=False):
        """apply_empty_mask=True runs the masking path with nothing erased -- the C-1 control."""
        self.n_lost_cw = 0
        self.lost_frac = 0.0
        if apply_empty_mask:
            self.masks = [torch.ones(b - a, device=self.dev) for a, b in self.slices]
        else:
            self.masks = [None, None, None]

    def _apply(self, x, b):
        if x.shape[0] < 2:
            return x
        s = self.scales[b]
        collab = x[1:]
        deq = torch.clamp(torch.round(collab / s), -QMAX, QMAX) * s
        m = self.masks[b]
        if m is not None:
            # multiply by a keep-mask rather than boolean-index-assign: same result, no gather
            deq = (deq.reshape(deq.shape[0], -1) * m).reshape(deq.shape)
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
        raise SystemExit('WP5 is authorised for validate only (V2-R11 F-3).')

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
    if n_elem != chain['elements'] or n_cw != chain['n_cw']:
        raise SystemExit('WP5: mapping disagrees with the payload chain -- stop.')

    # A-5 control: no two replicates of the same (frame, rate) may draw the same mask
    coll = 0
    for f in (0, 991, 1979):
        for ri, p in enumerate(RATES):
            ms = [np.random.default_rng(seed_of(f, ri, r)).random(n_cw) < p for r in range(R_REPS)]
            for a in range(R_REPS):
                for b in range(a + 1, R_REPS):
                    coll += int(np.array_equal(ms[a], ms[b]))
    print(f'A-5 mask-collision control: {coll} identical pairs across '
          f'{3 * len(RATES) * R_REPS * (R_REPS - 1) // 2} comparisons (expected 0)')
    if coll:
        raise SystemExit('A-5: replicate masks collide -- the seed schedule is broken.')

    ds = build_dataset(hypes, visualize=False, train=False)

    ds.catosg_split = args.split   # V2-R16 B-3: part of the seed identity
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

    n_cond = 2 + len(RATES) * R_REPS * len(REGIMES) + 1
    print(f'{args.split}: {len(idx)} frames x {n_cond} conditions '
          f'(clean, C-1 control, {len(RATES)}x{R_REPS}x{len(REGIMES)}, p=1.0)', flush=True)

    tp = Transport(model.backbone, scales, cw_lo, cw_hi).to_device(dev)
    ego = np.load(os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}.npz'), allow_pickle=True)
    ego_map = {int(f): i for i, f in enumerate(ego['frames'])}

    acc = {}          # (regime, p, rep) -> (boxes, scores)
    gts, rows = [], []
    identity_fail = []
    t0 = time.time()

    def run(pack):
        pb, ps, g = inference_utils.inference_intermediate_fusion(pack, model, ds)

        def np_(t, shp):
            return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
        return np_(pb, (0, 8, 3)), np_(ps, (0,)), np_(g, (0, 8, 3))

    for i, batch in enumerate(loader):
        b = train_utils.to_device(batch, dev)
        cav = b['ego']
        pack = {'ego': cav}
        rec = {'frame': idx[i], 'n_cav': int(cav['record_len'].sum().item())}
        with torch.no_grad():
            tp.set_clean(False)
            with tp.patched():
                Bc, Sc, G = run(pack)
            gts.append(G)
            acc.setdefault(('clean', 0.0, 0), ([], []))
            acc[('clean', 0.0, 0)][0].append(Bc); acc[('clean', 0.0, 0)][1].append(Sc)
            rec['n_box_clean'] = len(Bc); rec['f1_clean'] = f1_from_boxes(Bc, G)

            # C-1: the same thing with an all-False mask applied
            tp.set_clean(True)
            with tp.patched():
                Bi, Si, _ = run(pack)
            same = (Bi.shape == Bc.shape and Si.shape == Sc.shape
                    and (Bi.size == 0 or np.abs(Bi - Bc).max() == 0)
                    and (Si.size == 0 or np.abs(Si - Sc).max() == 0))
            if not same:
                identity_fail.append(idx[i])

            for ri, p in enumerate(RATES):
                for rep in range(R_REPS):
                    draw = np.random.default_rng(seed_of(idx[i], ri, rep)).random(n_cw) < p
                    for reg in REGIMES:
                        tp.set_dead(draw, reg)
                        with tp.patched():
                            B, S, _ = run(pack)
                        k = (reg, p, rep)
                        acc.setdefault(k, ([], []))
                        acc[k][0].append(B); acc[k][1].append(S)
                        rec[f'f1_{reg}_p{p}_r{rep}'] = f1_from_boxes(B, G)
                        rec[f'cw_{reg}_p{p}_r{rep}'] = tp.n_lost_cw
            # p = 1.00: every codeword fails, identical in both regimes
            tp.set_dead(np.ones(n_cw, bool), 'ideal')
            with tp.patched():
                B1, S1, _ = run(pack)
            acc.setdefault(('ideal', 1.0, 0), ([], []))
            acc[('ideal', 1.0, 0)][0].append(B1); acc[('ideal', 1.0, 0)][1].append(S1)
            rec['f1_p1.0'] = f1_from_boxes(B1, G)
            rec['n_box_p1.0'] = len(B1)
        j = ego_map.get(idx[i])
        rec['f1_ego'] = f1_from_boxes(ego['ego_boxes'][j], G) if j is not None else np.nan
        rows.append(rec)
        if i % 50 == 0:
            el = time.time() - t0
            print(f'  {i}/{len(idx)} frame={idx[i]}  clean={rec["n_box_clean"]} '
                  f'p1.0={rec["n_box_p1.0"]}  {el / max(i, 1):.2f}s/frame '
                  f'eta {(len(idx) - i) * el / max(i, 1) / 60:.0f}min', flush=True)
    dt = time.time() - t0

    import pandas as pd
    df = pd.DataFrame(rows)
    tag = f'_{args.tag}' if args.tag else ''
    df.to_csv(os.path.join(OUT_DIR, f'wp5_final_{args.split}{tag}.csv'), index=False)

    out = {'schema': 'catosg-v2-wp5-final/1', 'split': args.split, 'frames': len(df),
           'rates': list(RATES), 'replicates': R_REPS, 'regimes': list(REGIMES),
           'base_seed': BASE_SEED, 'seed_K': SEED_K, 'n_cw': n_cw, 'elements': n_elem,
           'seconds': round(dt, 1), 'sec_per_frame': round(dt / max(len(df), 1), 3),
           'identity_check': {'failures': identity_fail, 'n_failures': len(identity_fail),
                              'criterion': 'exact equality of boxes and scores, max|delta| = 0'},
           'conditions': {}}
    for (reg, p, rep), (B, S) in acc.items():
        out['conditions'][f'{reg}|{p}|{rep}'] = {
            'ap50': ap_global(B, S, gts, 0.5), 'ap70': ap_global(B, S, gts, 0.7),
            'boxes_mean': float(np.mean([len(x) for x in B]))}
    # message-level regime: analytic, P(success) = (1-p)^n_cw -- no forward needed
    out['message_regime'] = {
        str(p): {'p_message_survives': float((1 - p) ** n_cw)} for p in (0.0,) + RATES + (1.0,)}
    # V2-R9 C-3: the boundary-element record, derived here rather than quoted
    straddle = cw_lo != cw_hi
    off = np.cumsum((0,) + BRANCH_ELEMS)
    out['boundary_elements'] = {
        'rule': 'an int8 element is zeroed if EITHER covering codeword fails; partial zeroing '
                'would yield a value that is neither the original nor the zero code point',
        'n_straddling': int(straddle.sum()),
        'pct_of_elements': float(straddle.mean() * 100),
        'per_branch': {str(b): int(straddle[off[b]:off[b + 1]].sum()) for b in range(3)},
        'per_packet': '8 in each full packet, 2 in the tail',
        'first_examples': [{'element': int(e), 'codewords': [int(cw_lo[e]), int(cw_hi[e])]}
                           for e in np.flatnonzero(straddle)[:8]],
    }
    with open(os.path.join(OUT_DIR, f'wp5_final_{args.split}{tag}.json'), 'w') as f:
        json.dump(out, f, indent=1)

    print(f'\nidentity check (C-1): {len(identity_fail)} frame(s) differ '
          f'(criterion: exact equality of boxes and scores)')
    print(f'{dt / 60:.1f} min total, {out["sec_per_frame"]:.3f} s/frame')
    print(f'wrote results/v2/wp5_final_{args.split}{tag}.{{csv,json}}')
    return 1 if identity_fail else 0


if __name__ == '__main__':
    sys.exit(main())
