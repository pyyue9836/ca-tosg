#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R4 step 4: calibrate the int8 transmit scales on validate, freeze them, and measure the cost.

WHAT THE PROTOCOL REQUIRES (§2 F, §3.3, B-4). The F branch must actually execute
`F_float -> Q_int8 -> F_hat_float -> fusion/detection`, quantising **only the bottleneck that
travels from the collaborator to the ego**. The ego's own features never cross a link and are not
quantised; E and L transmit no tensor at all.

WHERE THE TRANSMITTED TENSOR ACTUALLY IS. `AttBEVBackbone` calls `compression_modules[i]`, which is
an `AutoEncoder` whose `forward` runs encoder *and* decoder in one call — so the thing that would go
on the wire, the bottleneck, is never exposed. This module therefore wraps the AutoEncoder to split
that call: encode, quantise the collaborator's slice, decode. Branch 2 has no AutoEncoder (it is
transmitted uncompressed), so its collaborator slice is quantised in place before fusion.

**This implements the protocol; it does not repair a forward path.** No weight, no module and no
fusion rule is altered — a quantise/dequantise pair is inserted exactly where the protocol says the
channel is.

SCALE DEFINITION (§2, "per-branch scale"): three symmetric scalars, `s_b = max|x_b| / 127`, one per
backbone branch, computed over the transmitted bottleneck across the calibration set. Not per frame,
not per channel, not per element.

CALIBRATION SET: validate only, every 9th frame so all nine scenes contribute. The maximum is taken
over **every non-ego CAV's** bottleneck, which is at least as large as any single collaborator's --
so the frozen scale is conservative and does not depend on which collaborator the selection rule
picks.

    python projects/ca_tosg/evaluation/v2_int8_calibrate.py --calib 220 --eval 220
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

from torch.utils.data import DataLoader                                          # noqa: E402

from opencood.data_utils.datasets import build_dataset                           # noqa: E402
from opencood.hypes_yaml import yaml_utils                                       # noqa: E402
from opencood.tools import inference_utils, train_utils                          # noqa: E402

from v2_single_vehicle_sanity import (CKPT, DATA_ROOT, ap_global,                 # noqa: E402
                                      f1_from_boxes)

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
MANIFEST = os.path.join(ROOT, 'results', 'manifests', 'V2_INT8_SCALES.json')
N_BRANCH = 3
QMAX = 127


class TransmitQuant:
    """Splits each AutoEncoder into encode / [channel] / decode and quantises the collaborator slice.

    mode 'calibrate' records max|x| per branch and passes the tensor through untouched.
    mode 'quantise' applies the frozen symmetric int8 scale to the collaborator rows only.
    """

    def __init__(self, backbone, mode='calibrate', scales=None):
        self.bb = backbone
        self.mode = mode
        self.scales = scales
        self.maxima = [0.0] * N_BRANCH
        self.err = [[] for _ in range(N_BRANCH)]
        self._saved = []

    def _apply(self, x, b):
        """x: (n_cav, C, H, W) stacked; row 0 is the ego and is never quantised (B-4)."""
        if x.shape[0] < 2:
            return x                     # no collaborator in this frame: nothing crosses a link
        collab = x[1:]
        if self.mode == 'calibrate':
            self.maxima[b] = max(self.maxima[b], float(collab.abs().max().item()))
            return x
        s = self.scales[b]
        q = torch.clamp(torch.round(collab / s), -QMAX, QMAX)
        deq = q * s
        self.err[b].append(float((deq - collab).abs().mean().item()))
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
                    x = self._apply(x, b)                 # <-- the wire
                    for j in range(len(ae.decoder) - 1, -1, -1):
                        x = ae.decoder[j](x)
                    return x
                return fwd
            ae.forward = make()
        # branch 2 carries no AutoEncoder: it is transmitted uncompressed, so quantise it where the
        # fusion consumes it
        fm = bb.fuse_modules[2]
        saved_fuse = fm.forward

        def fuse_fwd(x, record_len, _f=saved_fuse):
            return _f(self._apply(x, 2), record_len)
        fm.forward = fuse_fwd
        try:
            yield self
        finally:
            for ae, f in self._saved:
                ae.forward = f
            fm.forward = saved_fuse


def two_cav(cav):
    """Restrict the batch to ego + ONE collaborator (B-2). Returns None if the frame has no
    collaborator. CAV index 1 stands in for the nearest-by-distance rule, which work package 2
    supplies; the int8-vs-float DELTA is what this script measures and it does not depend on which
    collaborator is chosen."""
    import copy
    n = int(cav['record_len'].sum().item())
    if n < 2:
        return None
    out = copy.copy(cav)
    pl = cav['processed_lidar']
    keep = pl['voxel_coords'][:, 0] < 2
    out['processed_lidar'] = {k: pl[k][keep] for k in
                              ('voxel_features', 'voxel_coords', 'voxel_num_points')}
    out['record_len'] = torch.tensor([2], dtype=cav['record_len'].dtype,
                                     device=cav['record_len'].device)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', default=CKPT)
    ap.add_argument('--data_root', default=DATA_ROOT)
    ap.add_argument('--calib', type=int, default=220)
    ap.add_argument('--eval', type=int, default=220)
    ap.add_argument('--every', type=int, default=9)
    args = ap.parse_args()

    class O:
        model_dir = args.model_dir
    hypes = yaml_utils.load_yaml(None, O)
    split_dir = os.path.join(args.data_root, 'validate')
    hypes['root_dir'] = hypes['validate_dir'] = split_dir
    ds = build_dataset(hypes, visualize=False, train=False)
    # Subset, not skip-in-the-loop: the workload is I/O-bound (~1.7 s to load a frame, ~0.05 s to
    # run one), so iterating the full 1980-frame loader and discarding 8 of every 9 frames costs
    # nine times the wall clock for the same result. Indices are strided so all nine scenes appear.
    from torch.utils.data import Subset
    idx = list(range(0, len(ds), args.every))
    sub_ds = Subset(ds, idx)
    loader = DataLoader(sub_ds, batch_size=1, num_workers=4, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False)
    print(f'dataset {len(ds)} frames; sampling every {args.every}th -> {len(idx)} loaded')
    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(args.model_dir, model)
    model.eval()

    # ---------------- pass 1: calibrate ----------------
    t0 = time.time()
    cal = TransmitQuant(model.backbone, mode='calibrate')
    taken = 0
    with cal.patched():
        for i, batch in enumerate(loader):
            if taken >= args.calib:
                break
            b = train_utils.to_device(batch, dev)
            sub = two_cav(b['ego'])
            if sub is None:
                continue
            taken += 1
            with torch.no_grad():
                model(sub)
    scales = [m / QMAX for m in cal.maxima]
    print(f'calibration: {taken} validate frames (every {args.every}th, ego + 1 collaborator)')
    for b in range(N_BRANCH):
        print(f'  branch {b}:  max|x| = {cal.maxima[b]:.6f}   s_{b} = max/127 = {scales[b]:.8f}')

    # ---------------- pass 2: float vs int8, same frames ----------------
    q = TransmitQuant(model.backbone, mode='quantise', scales=scales)
    rows, fb, fs, fg, qb, qs = [], [], [], [], [], []
    taken = 0
    for i, batch in enumerate(loader):
        if taken >= args.eval:
            break
        b = train_utils.to_device(batch, dev)
        sub = two_cav(b['ego'])
        if sub is None:
            continue
        taken += 1
        pack = {'ego': sub}
        sub['anchor_box'] = b['ego']['anchor_box']
        sub['transformation_matrix'] = b['ego']['transformation_matrix']
        with torch.no_grad():
            p1, s1, g1 = inference_utils.inference_intermediate_fusion(pack, model, ds)
            with q.patched():
                p2, s2, _ = inference_utils.inference_intermediate_fusion(pack, model, ds)

        def np_(t, shp):
            return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
        B1, S1, G = np_(p1, (0, 8, 3)), np_(s1, (0,)), np_(g1, (0, 8, 3))
        B2, S2 = np_(p2, (0, 8, 3)), np_(s2, (0,))
        fb.append(B1); fs.append(S1); fg.append(G); qb.append(B2); qs.append(S2)
        rows.append(dict(frame=idx[i], n_gt=len(G), n_box_float=len(B1), n_box_int8=len(B2),
                         f1_float=f1_from_boxes(B1, G), f1_int8=f1_from_boxes(B2, G)))
        if taken % 50 == 1:
            print(f'  eval {taken}/{args.eval} (frame {idx[i]})', flush=True)
    dt = time.time() - t0

    import pandas as pd
    df = pd.DataFrame(rows)
    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_csv(os.path.join(OUT_DIR, 'int8_clean_delivery_validate.csv'), index=False)
    res = {
        'schema': 'catosg-v2-int8-scales/1',
        'protocol': 'docs/unified_branch_protocol_v2.md sec 2 (F), sec 3.3 (C-2), B-4',
        'checkpoint': args.model_dir,
        'calibration_split': 'validate', 'calibration_every': args.every,
        'calibration_frames': int(taken), 'config': 'ego + 1 collaborator (B-2)',
        'quantiser': 'symmetric int8, per branch, s_b = max|x_b| / 127',
        'branch_max_abs': cal.maxima, 'scales': scales,
        'mean_abs_dequant_error': [float(np.mean(e)) if e else None for e in q.err],
        'frames_evaluated': len(df), 'seconds': round(dt, 1),
        'ap50_float': ap_global(fb, fs, fg, 0.5), 'ap50_int8': ap_global(qb, qs, fg, 0.5),
        'ap70_float': ap_global(fb, fs, fg, 0.7), 'ap70_int8': ap_global(qb, qs, fg, 0.7),
        'f1_float': float(df.f1_float.mean()), 'f1_int8': float(df.f1_int8.mean()),
        'boxes_float_mean': float(df.n_box_float.mean()),
        'boxes_int8_mean': float(df.n_box_int8.mean()),
    }
    for k in ('ap50', 'ap70', 'f1'):
        a, b_ = res[f'{k}_float'], res[f'{k}_int8']
        res[f'{k}_quantisation_loss'] = a - b_
    with open(MANIFEST, 'w') as f:
        json.dump(res, f, indent=1)

    print('\n' + '=' * 78)
    print(f'INT8 CLEAN DELIVERY vs FLOAT -- same {len(df)} frames, ego + 1 collaborator')
    print('=' * 78)
    print(f'{"":24} {"float":>12} {"int8":>12} {"quantisation loss":>20}')
    for k, lab in (('ap50', 'AP@0.5'), ('ap70', 'AP@0.7'), ('f1', 'mean per-frame F1')):
        print(f'{lab:24} {res[f"{k}_float"]:>12.5f} {res[f"{k}_int8"]:>12.5f} '
              f'{res[f"{k}_quantisation_loss"]:>+20.5f}')
    print(f'{"boxes/frame mean":24} {res["boxes_float_mean"]:>12.2f} '
          f'{res["boxes_int8_mean"]:>12.2f}')
    print('=' * 78)
    print('scales frozen ->', os.path.relpath(MANIFEST, ROOT))
    print('THE LOSS IS REPORTED AS MEASURED. It is not grounds for changing w (B-4).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
