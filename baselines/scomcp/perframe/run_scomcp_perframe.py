#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SC-2: SComCP per-frame sweep, isomorphic to the Appendix-A ImportanceMapJSCC arm.

For each (channel, SNR, split) the trained SComCP net is re-configured at eval time and run over
the whole split; per-frame F1 is scored with the **same** helper, the **same** canonical union GT
and the **same** IoU-0.5 unit-score convention as `late_f1` / `compressed_f1` / `jscc_f1`, so the
`scomcp_f1` column drops straight into the same table and figure as the other arms.

Payload: the ImportanceMapJSCC arm registers **no** codec-level payload convention
(`jscc_ap_f1.csv` has no payload column; `rf_payload` elsewhere is the *selector's* L/feature mix).
Per the SC-2 ruling this arm therefore reports F1 and AP plus the codec's own `com_rate` as a
standalone column, and invents **no** Msym/Mbit conversion.

    python baselines/scomcp/perframe/run_scomcp_perframe.py --ckpt <net_final.pth> \
        --config <stage3.yaml> --out results/baselines/scomcp.csv
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
DATA_ROOT = '/mnt/h/opencood_project/datasets/opv2v_data_dumping'
SPLIT_DIR = {'validate': 'validate', 'test': 'test', 'culver': 'test_culver_city'}
SNR_GRID = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]      # the pre-registered 11-point grid


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def f1_per_frame(boxes, gts, iou=0.5):
    """The shared convention: IoU 0.5, unit scores, canonical union GT, no crop/visibility."""
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


def build(config, ckpt, split):
    import torch
    from torch.utils.data import DataLoader

    import opencood.hypes_yaml.yaml_utils as yaml_utils
    from opencood.data_utils.datasets import build_dataset
    from opencood.tools import train_utils

    hypes = copy.deepcopy(yaml_utils.load_yaml(config, None))
    hypes['validate_dir'] = os.path.join(DATA_ROOT, SPLIT_DIR[split])
    ds = build_dataset(hypes, visualize=False, train=False)
    loader = DataLoader(ds, batch_size=1, num_workers=8, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False, drop_last=False)
    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(dev)
    sd = torch.load(ckpt, map_location=dev)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    print(f'  loaded {os.path.basename(ckpt)}: {len(missing)} missing, {len(unexpected)} unexpected')
    model.eval()
    return model, ds, loader, dev


def fusion_of(model):
    for name in ('fusion_net', 'fusion', 'semantic_fusion'):
        if hasattr(model, name):
            return getattr(model, name)
    raise SystemExit('cannot locate the fusion module on the model')


def sweep_one(model, ds, loader, dev, channel, snr):
    import torch
    from tqdm import tqdm

    from opencood.models.fuse_modules.importance_map_jscc_fuse import build_channel
    from opencood.tools import inference_utils, train_utils

    fn = fusion_of(model)
    fn.channel_type = channel
    fn.perfect_comm_control = False
    fn.remote_zero_control = False
    fn.ldpc_baseline_control = False
    if hasattr(fn, 'semantic_codec'):
        fn.semantic_codec.channel = build_channel(channel, snr)
        fn.semantic_codec.channel.to(next(model.parameters()).device)
    if hasattr(fn, 'set_snr'):
        fn.set_snr(float(snr))

    boxes, gts, coms = [], [], []
    with torch.no_grad():
        for batch in tqdm(loader, desc=f'{channel} {snr}dB', leave=False):
            batch = train_utils.to_device(batch, dev)
            pb, ps, gt = inference_utils.inference_intermediate_fusion(batch, model, ds)
            boxes.append(pb.cpu().numpy() if pb is not None else np.zeros((0, 8, 3), np.float32))
            gts.append(gt.cpu().numpy() if gt is not None else np.zeros((0, 8, 3), np.float32))
            cr = getattr(fn, 'last_remote_payload_cr_actual', None)
            if cr is None:
                cr = getattr(fn, 'last_paper_cr_actual', None)
            if cr is not None:
                coms.append(float(cr))
    return boxes, gts, (float(np.mean(coms)) if coms else float('nan'))


def ap_of(boxes, gts):
    """AP@.3/.5/.7, no global sort (this arm's own convention), on a fresh result_stat each time."""
    import torch

    from opencood.utils import eval_utils
    rs = {t: {'tp': [], 'fp': [], 'gt': 0, 'score': []} for t in (0.3, 0.5, 0.7)}
    for pred, gt in zip(boxes, gts):
        pred = np.asarray(pred, np.float32)
        gt = np.asarray(gt, np.float32)
        pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
        gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
        for t in (0.3, 0.5, 0.7):
            eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, t)
    # calculate_ap cumsums its input IN PLACE, so每 call gets its own copy
    return tuple(float(eval_utils.calculate_ap(copy.deepcopy(rs), t, False)[0])
                 for t in (0.3, 0.5, 0.7))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--splits', nargs='+', default=['validate', 'test'])
    ap.add_argument('--channels', nargs='+', default=['awgn', 'rayleigh'])
    ap.add_argument('--snrs', nargs='+', type=float, default=SNR_GRID)
    ap.add_argument('--out', default=os.path.join(ROOT, 'results/baselines/scomcp.csv'))
    args = ap.parse_args()
    sys.path.insert(0, OPENCOOD)
    import pandas as pd

    rows = []
    for split in args.splits:
        model, ds, loader, dev = build(args.config, args.ckpt, split)
        for ch in args.channels:
            for snr in args.snrs:
                boxes, gts, com = sweep_one(model, ds, loader, dev, ch, snr)
                f1 = f1_per_frame(boxes, gts)
                a30, a50, a70 = ap_of(boxes, gts)
                rows.append(dict(channel=ch, split=split, snr_db=snr, n=len(f1),
                                 scomcp_f1=round(float(f1.mean()), 4),
                                 ap30=round(a30, 4), ap50=round(a50, 4), ap70=round(a70, 4),
                                 com_rate=(round(com, 6) if com == com else None)))
                print(f'[{split} {ch} {snr:>4.1f} dB] n={len(f1)} f1={f1.mean():.4f} '
                      f'ap50={a50:.4f} ap70={a70:.4f} com_rate={com:.6f}', flush=True)
                pd.DataFrame(rows).to_csv(args.out, index=False)   # checkpoint after every run

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    prov = os.path.join(ROOT, 'results/provenance/PROVENANCE_scomcp.txt')
    with open(prov, 'w') as f:
        f.write('CA-TOSG SC-2 -- SComCP baseline, DESCRIPTIVE, no decision.\n' + '=' * 78 + '\n')
        f.write(f'generated: {datetime.now(timezone.utc).isoformat()}\n')
        f.write(f'checkpoint: {args.ckpt}\n  sha256 {sha256(args.ckpt)}\n')
        f.write(f'config: {args.config}\n')
        f.write('training split: VALIDATE (1,980 frames), NOT the 6,764-frame train split the '
                'source paper uses -- absolute AP is therefore not comparable to the published '
                'figures.\n')
        f.write('warm start: importance_map_jscc/stage2_rayleigh_learned_v3/'
                'stage2_whole_map_4000steps.pth (md5 c5a02fd77154), itself trained on the OPV2V '
                'train split -- consistent with this paper\'s discipline: train is where every\n'
                '  representation here is learned (frozen PointPillars backbone included), while '
                'the validate-only rule governs arm-specific learning so test and Culver stay '
                'held out. No held-out split was read during training.\n')
        f.write('step budget (pre-registered SC-2): 4000 / 4000 / 2000 for stages 1 / 2 / 3.\n')
        f.write(f'coverage: channels={args.channels} snr={args.snrs} splits={args.splits} '
                '(option B). Culver-City is NOT covered.\n')
        f.write('per-frame F1: same helper, same canonical union GT, same IoU-0.5 unit-score '
                'convention as late_f1 / compressed_f1 / jscc_f1.\n')
        f.write('AP: no global sort (this arm\'s own convention), fresh result_stat per call.\n')
        f.write('PAYLOAD: the ImportanceMapJSCC arm registers no codec-level payload convention, so '
                'com_rate is reported as a STANDALONE column and NO Msym/Mbit conversion is '
                'invented (SC-2 ruling).\n')
    print(f'\nwrote {args.out}\n      {prov}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
