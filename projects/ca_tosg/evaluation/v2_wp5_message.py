#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""WP5 addendum — the message-level regime, and the p = 1.00 vs ego-only comparison.

TWO ASSERTIONS THIS FILE EXISTS TO HONOUR
-----------------------------------------
**B-2: AP may not be linearly mixed.** `AP = q·AP_F + (1−q)·AP_E` is **forbidden**. AP is computed
from a *global* score ranking over the whole prediction set (the v1 "global sort" convention), so
substituting a different subset of frames changes the ranking structure. The mixture of two APs is
not the AP of the mixture, except by coincidence.

The correct treatment, and the one implemented here:

* **F1 is a per-frame quantity**, so its expectation is exact and analytic:
  `E[F1] = q·F1_clean + (1−q)·F1_ego`, frame by frame.
* **AP is not.** It is estimated by **Monte Carlo**: draw each frame's message-survival with a fixed
  seed, assemble the *whole* prediction set from the surviving-F and fallen-back-to-E frames, and
  compute the global-sort AP over that assembly. Repeat, and report mean and standard deviation.

**One rule, three homes, cross-referenced (V2-R20 A-4).** Because AP does not decompose over
predictions: (i) it may not be linearly mixed over frames — this docstring; (ii) TP/FP must be
matched **within** a frame before any global sort — `tpfp()` below; (iii) the contribution of a
*subset of boxes* is established by **ablation and re-scoring**, never by attributing a share of AP
to them — `v2_coordinate_frame_check.py`, and the "AP attributed per prediction" row of
`tests/tracked_terms.md`.

**Zero neural-network forwards.** The draw only *chooses between* predictions that already exist, so
the expensive part — the per-frame true-positive/false-positive/score decomposition — is computed
once per frame per source and reused across every replay. That is what makes 200 replays × 9 loss
rates affordable at all.

**C-1/C-2: p = 1.00 is NOT assumed equal to ego-only.** With every codeword lost the collaborator's
tensor is all zeros, but a zero tensor still enters `AttFusion`, whose softmax over two elements
dilutes the ego's own features. Whether that equals an ego-only forward is a measurement, not a
definition, and this file makes it. It is the extreme point of the same phenomenon as
"0 % delivery ≠ E".

    python projects/ca_tosg/evaluation/v2_wp5_message.py --split validate
"""
from __future__ import annotations

import argparse
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
from opencood.utils import eval_utils                                            # noqa: E402

from v2_single_vehicle_sanity import (CKPT, DATA_ROOT, ap_global,                  # noqa: E402
                                      f1_from_boxes)
from v2_wp1_invariants import assert_invariants                                  # noqa: E402
from v2_wp2_per_agent import SPLIT_DIR                                           # noqa: E402
from v2_wp5_f_products import element_to_codeword                                # noqa: E402
from v2_wp5_final import RATES, SEED_K, BASE_SEED, Transport                     # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
SCALES_JSON = os.path.join(ROOT, 'results', 'manifests', 'V2_INT8_SCALES.json')
N_REPLAY = 200                       # the protocol's CSI replay count, reused (B-3)
MC_SEED = BASE_SEED + 7 * SEED_K     # distinct from every erasure seed, same schedule discipline


def tpfp(boxes, scores, gt, thr):
    """Per-frame (tp, fp, score) lists -- the only thing global-sort AP needs from a frame.

    B-1: called SEPARATELY for each IoU threshold, and the results stored separately. Matching is a
    function of the threshold -- the same box can be a TP at 0.5 and an FP at 0.7 -- so reusing one
    decomposition for both would contaminate AP@0.7 with AP@0.5's matching. It would not crash and it
    would not warn; it would just be wrong.

    B-2, in the protocol's own words: *TP/FP assignment is performed independently within each frame
    before detections from all frames are globally ranked by confidence for AP computation.*

    The risk this guards against is **not** cross-frame matching -- a correct implementation cannot do
    that, and saying so would put the danger in the wrong place. The risk is an implementation that
    **loses the frame boundary**: pooling detections and ground truth before matching, so a box in one
    frame can be assigned to an object in another. `caluclate_tp_fp` is called here once per frame,
    with that frame's own ground truth and nothing else, which is what keeps the boundary intact.

    Second of the three homes of one rule (V2-R20 A-4): AP does not decompose over predictions.
    The other two are this module's docstring (no linear mixing of APs) and
    `v2_coordinate_frame_check.py` (a subset's contribution is attributed by ablation, not by
    assigning it a share of AP).
    """
    pb = np.asarray(boxes, np.float32)
    ps = np.asarray(scores, np.float32)
    g = np.asarray(gt, np.float32)
    pt = torch.from_numpy(pb) if pb.size else torch.zeros((0, 8, 3))
    gt_t = torch.from_numpy(g) if g.size else torch.zeros((0, 8, 3))
    st = torch.from_numpy(ps) if ps.size else torch.zeros((0,))
    r = {thr: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pt, st, gt_t, r, thr)
    return r[thr]['tp'], r[thr]['fp'], r[thr]['score']


def ap_from_parts(parts, n_gt, thr):
    """Assemble a global-sort AP from per-frame parts, without recomputing any matching."""
    rs = {thr: {'tp': [], 'fp': [], 'gt': int(n_gt), 'score': []}}
    for tp, fp, sc in parts:
        rs[thr]['tp'] += tp
        rs[thr]['fp'] += fp
        rs[thr]['score'] += sc
    return float(eval_utils.calculate_ap(rs, thr, True)[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', default=CKPT)
    ap.add_argument('--data_root', default=DATA_ROOT)
    ap.add_argument('--split', default='validate', choices=list(SPLIT_DIR))
    ap.add_argument('--limit', type=int, default=0)
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
    cw_lo, cw_hi, n_elem = element_to_codeword()
    n_cw = int(max(cw_lo.max(), cw_hi.max())) + 1

    ds = build_dataset(hypes, visualize=False, train=False)

    ds.catosg_split = args.split   # V2-R16 B-3: part of the seed identity
    idx = list(range(0, len(ds), 1))
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
    tp_ = Transport(model.backbone, scales, cw_lo, cw_hi).to_device(dev)

    ego = np.load(os.path.join(OUT_DIR, f'wp2_per_agent_{args.split}.npz'), allow_pickle=True)
    emap = {int(f): i for i, f in enumerate(ego['frames'])}

    # ---- one pass: clean-F and p=1.00 predictions, plus their tp/fp/score decompositions ----
    parts = {'clean': {0.5: [], 0.7: []}, 'ego': {0.5: [], 0.7: []}, 'p1': {0.5: [], 0.7: []}}
    clean_b, clean_s, clean_g = [], [], []          # kept only for the B-3 validation
    rows, n_gt = [], 0
    t0 = time.time()
    for i, batch in enumerate(loader):
        b = train_utils.to_device(batch, dev)
        cav = b['ego']
        pack = {'ego': cav}

        def np_(t, shp):
            return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
        with torch.no_grad():
            tp_.set_clean(False)
            with tp_.patched():
                pb, ps, g = inference_utils.inference_intermediate_fusion(pack, model, ds)
            Bc, Sc, G = np_(pb, (0, 8, 3)), np_(ps, (0,)), np_(g, (0, 8, 3))
            tp_.set_dead(np.ones(n_cw, bool), 'ideal')
            with tp_.patched():
                pb1, ps1, _ = inference_utils.inference_intermediate_fusion(pack, model, ds)
            B1, S1 = np_(pb1, (0, 8, 3)), np_(ps1, (0,))
        j = emap.get(idx[i])
        Be, Se = (ego['ego_boxes'][j], ego['ego_scores'][j]) if j is not None else (Bc[:0], Sc[:0])
        n_gt += len(G)
        clean_b.append(Bc); clean_s.append(Sc); clean_g.append(G)
        for thr in (0.5, 0.7):
            parts['clean'][thr].append(tpfp(Bc, Sc, G, thr))
            parts['ego'][thr].append(tpfp(Be, Se, G, thr))
            parts['p1'][thr].append(tpfp(B1, S1, G, thr))
        same_boxes = (B1.shape == np.asarray(Be).shape
                      and (B1.size == 0 or np.abs(B1 - np.asarray(Be)).max() < 1e-6))
        rows.append(dict(frame=idx[i], n_gt=len(G),
                         f1_clean=f1_from_boxes(Bc, G), f1_ego=f1_from_boxes(Be, G),
                         f1_p1=f1_from_boxes(B1, G),
                         n_box_clean=len(Bc), n_box_ego=len(Be), n_box_p1=len(B1),
                         p1_identical_to_ego=int(same_boxes)))
        if i % 200 == 0:
            print(f'  {i}/{len(idx)}  {(time.time()-t0)/max(i,1):.2f}s/frame', flush=True)
    dt = time.time() - t0

    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT_DIR, f'wp5_message_{args.split}.csv'), index=False)

    base = {k: {thr: ap_from_parts(parts[k][thr], n_gt, thr) for thr in (0.5, 0.7)}
            for k in ('clean', 'ego', 'p1')}

    # ---------------- B: reconstruction-consistency bridge (V2-R15) ----------------
    # The clean-F predictions were REGENERATED here because the main run persisted only summary
    # statistics. Before any of them is used, they must be shown to be the same predictions the main
    # run scored. A mismatch would mean the Monte Carlo is running on a different clean-F -- and that
    # kind of divergence does not crash and does not warn. It is a precondition, not a diagnostic.
    main_csv = os.path.join(OUT_DIR, f'wp5_final_{args.split}.csv')
    main_json = os.path.join(OUT_DIR, f'wp5_final_{args.split}.json')
    bridge = {'checked': False}
    if os.path.exists(main_csv) and os.path.exists(main_json):
        mdf = pd.read_csv(main_csv).set_index('frame')
        mj = json.load(open(main_json))
        mine = df.set_index('frame')
        common = mine.index.intersection(mdf.index)
        d_box = (mine.loc[common, 'n_box_clean'] - mdf.loc[common, 'n_box_clean']).abs()
        d_f1 = (mine.loc[common, 'f1_clean'] - mdf.loc[common, 'f1_clean']).abs()
        m_ap50 = mj['conditions']['clean|0.0|0']['ap50']
        m_ap70 = mj['conditions']['clean|0.0|0']['ap70']
        d_ap50 = abs(base['clean'][0.5] - m_ap50)
        d_ap70 = abs(base['clean'][0.7] - m_ap70)
        bridge = {
            'checked': True, 'frames_compared': int(len(common)),
            'box_count_max_abs_diff': int(d_box.max()), 'box_count_tol': 0,
            'box_count_frames_differing': int((d_box > 0).sum()),
            'f1_max_abs_diff': float(d_f1.max()), 'f1_tol': 1e-12,
            'f1_frames_differing': int((d_f1 > 1e-12).sum()),
            'ap50_main': m_ap50, 'ap50_rebuilt': base['clean'][0.5], 'ap50_abs_diff': d_ap50,
            'ap70_main': m_ap70, 'ap70_rebuilt': base['clean'][0.7], 'ap70_abs_diff': d_ap70,
            'ap_tol': 1e-9,
        }
        bridge['pass'] = bool(d_box.max() == 0 and d_f1.max() <= 1e-12
                              and d_ap50 <= 1e-9 and d_ap70 <= 1e-9)
        print('\nB: reconstruction-consistency bridge vs the main run')
        print(f'  frames compared            {bridge["frames_compared"]}')
        print(f'  box count   max |diff|     {bridge["box_count_max_abs_diff"]}   '
              f'(tol 0, differing frames {bridge["box_count_frames_differing"]})')
        print(f'  per-frame F1 max |diff|    {bridge["f1_max_abs_diff"]:.3e}  '
              f'(tol 1e-12, differing frames {bridge["f1_frames_differing"]})')
        print(f'  AP@0.5      |diff|         {d_ap50:.3e}  (tol 1e-9)   '
              f'main {m_ap50:.12f}  rebuilt {base["clean"][0.5]:.12f}')
        print(f'  AP@0.7      |diff|         {d_ap70:.3e}  (tol 1e-9)   '
              f'main {m_ap70:.12f}  rebuilt {base["clean"][0.7]:.12f}')
        if not bridge['pass']:
            with open(os.path.join(OUT_DIR, f'wp5_message_{args.split}_BRIDGE_FAIL.json'), 'w') as f:
                json.dump(bridge, f, indent=1)
            raise SystemExit('B-2: the rebuilt clean-F does not match the main run. STOP. '
                             'Do not lower the tolerance and do not continue on "the difference is '
                             'small" -- it means the Monte Carlo would run on different predictions.')
        print('  -> BRIDGE PASS; the Monte Carlo may proceed')
    else:
        print('\nB: main-run products absent -- the bridge cannot be checked, so the Monte Carlo '
              'is NOT run (a check that cannot verify must not report success)')
        raise SystemExit('B-1: main run products missing; cannot establish the bridge.')

    # ---------------- C: persist the decompositions, hash them ----------------
    parts_npz = os.path.join(OUT_DIR, f'wp5_tpfp_{args.split}.npz')
    store = {}
    for k in ('clean', 'ego', 'p1'):
        for thr in (0.5, 0.7):
            tag = f'{k}_{str(thr).replace(".", "")}'
            store[f'{tag}_tp'] = np.array([np.asarray(x[0]) for x in parts[k][thr]], dtype=object)
            store[f'{tag}_fp'] = np.array([np.asarray(x[1]) for x in parts[k][thr]], dtype=object)
            store[f'{tag}_score'] = np.array([np.asarray(x[2]) for x in parts[k][thr]], dtype=object)
    store['frames'] = np.asarray(df.frame.to_numpy())
    store['n_gt_total'] = np.asarray([n_gt])
    np.savez(parts_npz, **store)
    import hashlib
    sha = hashlib.sha256(open(parts_npz, 'rb').read()).hexdigest()
    print(f'C: wrote {os.path.relpath(parts_npz, ROOT)}  sha256 {sha[:16]}...  '
          f'({os.path.getsize(parts_npz) / 1e6:.1f} MB)')

    # B-3: the decomposed path must reproduce the evaluator that every other v2 number came from.
    # This validates the reuse machinery itself, not just this file's arithmetic.
    TOL = 1e-9
    valid = {}
    for thr in (0.5, 0.7):
        direct = ap_global(clean_b, clean_s, clean_g, thr)
        viaparts = base['clean'][thr]
        valid[str(thr)] = {'ap_global_direct': direct, 'ap_from_parts': viaparts,
                           'abs_diff': abs(direct - viaparts), 'tolerance': TOL,
                           'agree': abs(direct - viaparts) <= TOL}
        print(f'B-3 validation AP@{thr}: direct {direct:.12f} vs decomposed {viaparts:.12f}  '
              f'|diff| {abs(direct - viaparts):.2e}  '
              f'{"AGREE" if abs(direct - viaparts) <= TOL else "DISAGREE"}')
    if not all(v['agree'] for v in valid.values()):
        raise SystemExit('B-3: the decomposed AP path disagrees with the evaluator -- stop.')

    # ---- B-3: Monte Carlo message-level AP; NO linear mixing of APs ----
    n = len(df)
    msg = {}
    for ri, p in enumerate((0.0,) + RATES + (1.0,)):
        q = float((1 - p) ** n_cw)
        f1_exp = float((q * df.f1_clean + (1 - q) * df.f1_ego).mean())
        aps = {0.5: [], 0.7: []}
        for r in range(N_REPLAY):
            rng = np.random.default_rng(MC_SEED + ri * 7919 + r)
            survive = rng.random(n) < q
            for thr in (0.5, 0.7):
                sel = [parts['clean'][thr][k] if survive[k] else parts['ego'][thr][k]
                       for k in range(n)]
                aps[thr].append(ap_from_parts(sel, n_gt, thr))
        msg[str(p)] = {
            'q_message_survives': q,
            'expected_frames_surviving': float(q * n),
            # A-1: this is the PER-FRAME expected F1, averaged over frames. It is NOT a pooled or
            # global F1 -- no such quantity is computed anywhere here, and naming it one would imply
            # a statistic that does not exist. Same family as B-2's AP ban: a per-frame quantity has
            # an expectation; a pooled one does not follow from it.
            'per_frame_expected_f1_mean': f1_exp,
            'ap50_mc_mean': float(np.mean(aps[0.5])), 'ap50_mc_std': float(np.std(aps[0.5])),
            'ap70_mc_mean': float(np.mean(aps[0.7])), 'ap70_mc_std': float(np.std(aps[0.7])),
            # C-4: at small p this row is set by q, not by how F performs
            'note': ('dominated by q, not a measure of F performance' if 0 < q < 0.5
                     else ('clean' if q >= 0.999 else 'mixed')),
        }
        print(f'  message p={p:<6} q={q:.3e}  E[frames surviving]={q*n:.2f}  '
              f'AP@0.5 {msg[str(p)]["ap50_mc_mean"]:.5f}+-{msg[str(p)]["ap50_mc_std"]:.5f}',
              flush=True)

    ident = int(df.p1_identical_to_ego.sum())
    out = {'schema': 'catosg-v2-wp5-message/1', 'split': args.split, 'frames': n,
           'n_cw': n_cw, 'n_replays': N_REPLAY, 'mc_seed_base': MC_SEED,
           'seconds': round(dt, 1),
           'ap_mixing': 'FORBIDDEN (B-2): AP is a global-sort statistic; the mixture of two APs is '
                        'not the AP of the mixture. F1 is analytic per frame; AP is Monte Carlo.',
           'baselines': base, 'message_regime': msg, 'b3_validation': valid,
           'reconstruction_bridge': bridge,
           'tpfp_product': {'path': f'results/v2/wp5_tpfp_{args.split}.npz', 'sha256': sha,
                            'why': 'C-2: the only forward cost that had to be paid. Any later '
                                   'recomputation reuses this and must not run inference again.'},
           'p1_vs_ego': {
               'frames_with_identical_boxes': ident,
               'frames': n,
               'pct_identical': 100.0 * ident / n,
               'ap50_p1': base['p1'][0.5], 'ap50_ego': base['ego'][0.5],
               'ap70_p1': base['p1'][0.7], 'ap70_ego': base['ego'][0.7],
               'f1_p1': float(df.f1_p1.mean()), 'f1_ego': float(df.f1_ego.mean()),
               'assertion': 'p=1.00 is NOT assumed equal to ego-only (C-1/C-2). A zero collaborator '
                            'tensor still enters AttFusion, whose softmax over two elements dilutes '
                            'the ego features. The difference is measured, not defined.'}}
    with open(os.path.join(OUT_DIR, f'wp5_message_{args.split}.json'), 'w') as f:
        json.dump(out, f, indent=1)

    print('\n' + '=' * 78)
    print('C-1/C-2  p = 1.00 (all codewords lost)  vs  ego-only forward')
    print('=' * 78)
    print(f'{"":22} {"p=1.00":>12} {"ego-only":>12} {"difference":>12}')
    print(f'{"AP@0.5":22} {base["p1"][0.5]:>12.5f} {base["ego"][0.5]:>12.5f} '
          f'{base["p1"][0.5]-base["ego"][0.5]:>+12.5f}')
    print(f'{"AP@0.7":22} {base["p1"][0.7]:>12.5f} {base["ego"][0.7]:>12.5f} '
          f'{base["p1"][0.7]-base["ego"][0.7]:>+12.5f}')
    print(f'{"mean per-frame F1":22} {df.f1_p1.mean():>12.5f} {df.f1_ego.mean():>12.5f} '
          f'{df.f1_p1.mean()-df.f1_ego.mean():>+12.5f}')
    print(f'frames with bit-identical boxes: {ident}/{n} ({100.0*ident/n:.2f} %)')
    print(f'\n{dt/60:.1f} min, {dt/max(n,1):.2f} s/frame')
    return 0


if __name__ == '__main__':
    sys.exit(main())
