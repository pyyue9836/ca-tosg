#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R52-3: what the mainline headline AP looks like inside a COMMON evaluation volume.

Diagnostic only. Nothing frozen is touched: this writes to `results/diagnostic/` and the mainline
`true_e2e_ap.csv` is read, never rewritten.

The defect being measured (R51 stage 1, confirmed here from the caches themselves):

  * `end_to_end_ap.py` scores all three branches against ONE canonical GT taken from the
    attentive-compression cache (`cb, cs, cg = ...comp...; canon = tt(cg[s], ...)`, line ~148);
  * that GT extends to |x| ≈ 119 m, while the ego branch's predictions stop at |x| ≈ 70 m — the
    `pointpillar_late_fusion` config's range is x ∈ [-70.4, 70.4] against the compression config's
    x ∈ [-140.8, 140.8];
  * **12.4 % of canonical GT objects on validate lie beyond |x| > 70.4 m**, i.e. outside what the
    ego branch can ever detect. Those become structural false negatives for E, partly for L, and not
    at all for F, which flatters the L→F headroom by an amount nobody has measured.

This script measures it: every prediction and every GT box is cropped to the intersection volume
before scoring, and the resulting table is put beside the frozen one cell by cell. It reports Δ and
draws no conclusion; the ruling on whether anything in the paper changes is Josh's.

    python baselines/where2comm_v2/volume_diagnostic.py [--x 70.4] [--y 40] [--splits validate,test]
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
sys.path.insert(0, os.environ.get('OPENCOOD_ROOT',
                                  os.path.expanduser('~/cooperative_semantic_perception/OpenCOOD')))

import end_to_end_ap as E                      # noqa: E402
import deployment as D                         # noqa: E402

OUT = os.path.join(ROOT, 'results', 'diagnostic')
FROZEN = os.path.join(ROOT, 'results', 'main', 'true_e2e_ap.csv')


def crop(arr, xlim, ylim):
    """Keep boxes whose centre lies inside the volume. `arr` is (N,8,3) corner form."""
    a = E.tt(arr, (0, 8, 3))
    if a.shape[0] == 0:
        return a, np.ones(0, dtype=bool)
    cx = a[:, :, 0].mean(axis=1)
    cy = a[:, :, 1].mean(axis=1)
    keep = (np.abs(cx) <= xlim) & (np.abs(cy) <= ylim)
    return a[keep], keep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--x', type=float, default=70.4)
    ap.add_argument('--y', type=float, default=40.0)
    ap.add_argument('--splits', default='validate,test,culver')
    ap.add_argument('--realisations', type=int, default=E.N_REPLAY)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    man, budgets = D.load_manifest()
    tbl = pd.read_csv(D.BLER_CSV)
    tags = sorted(budgets)
    rows = []

    for split in [s for s in a.splits.split(',') if s]:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        sids = ds['sample_id'].astype(int).to_numpy()
        dl = np.load(os.path.join(E.GS, f'late_{split}.npz'), allow_pickle=True)
        dc = np.load(os.path.join(E.GS, f'comp_{split}.npz'), allow_pickle=True)
        de = np.load(os.path.join(E.GS, f'ego_{split}.npz'), allow_pickle=True)
        lb, ls = list(dl['boxes']), list(dl['scores'])
        cb, cs, cg = list(dc['boxes']), list(dc['scores']), list(dc['gts'])
        eb, es = list(de['boxes']), list(de['scores'])

        LST, CST, EST, gtn = [], [], [], []
        dropped_gt = kept_gt = 0
        print(f'[{split}] cropping to |x|<={a.x}, |y|<={a.y} and re-scoring {n} frames', flush=True)
        for k, s in enumerate(sids):
            canon_full = E.tt(cg[s], (0, 8, 3))
            canon, keep = crop(cg[s], a.x, a.y)
            dropped_gt += int(canon_full.shape[0] - canon.shape[0])
            kept_gt += int(canon.shape[0])
            gtn.append(canon.shape[0])
            stats = []
            for bx, sc in ((lb[s], ls[s]), (cb[s], cs[s]), (eb[s], es[s])):
                b, kb = crop(bx, a.x, a.y)
                sarr = E.tt(sc, (0,))
                sarr = sarr[kb] if sarr.shape[0] == kb.shape[0] else sarr[:b.shape[0]]
                stats.append(E.frame_stats(b, sarr, canon))
            LST.append(stats[0]); CST.append(stats[1]); EST.append(stats[2])
            if k % 500 == 0:
                print(f'  {k}/{n}', flush=True)
        ST = [LST, CST, EST]
        print(f'[{split}] GT kept {kept_gt}, dropped {dropped_gt} '
              f'({100 * dropped_gt / max(1, kept_gt + dropped_gt):.2f}% outside the volume)', flush=True)

        for pol, picks in (('Fixed-L', [E.LATE] * n), ('Feature-ceiling', [E.COMP] * n),
                           ('ego-only', [E.EGO] * n)):
            ap30, ap50, ap70 = E.ap_pick(picks, ST, gtn)
            rows.append(dict(split=split, budget='-', policy=pol, ap30_mean=round(ap30, 4),
                             ap50_mean=round(ap50, 4), ap70_mean=round(ap70, 4),
                             n_realisations=1, gt_dropped_pct=round(100 * dropped_gt /
                                                                    max(1, kept_gt + dropped_gt), 3)))
            print(f'[{split}] {pol:16s} AP@.3/.5/.7 = {ap30:.4f}/{ap50:.4f}/{ap70:.4f}', flush=True)

        rng = np.random.default_rng(E.CSI_SEED)
        snr_2d = rng.uniform(0, 20, size=(E.N_REPLAY, n))
        is_ray_2d = rng.random(size=(E.N_REPLAY, n)) < 0.5
        tbl_bF = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(E.N_REPLAY)])
        coin = np.random.default_rng(E.BLER_COIN_SEED).random(size=(E.N_REPLAY, n))
        survive = coin > tbl_bF
        R = min(a.realisations, E.N_REPLAY)
        for tag in tags:
            bd = budgets[tag]
            rf_idx = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr_2d, is_ray_2d)
            a50s, a70s, a30s = [], [], []
            for r in range(R):
                picks = E.branch_of(rf_idx[r], survive[r]).tolist()
                v = E.ap_pick(picks, ST, gtn)
                a30s.append(v[0]); a50s.append(v[1]); a70s.append(v[2])
            rows.append(dict(split=split, budget=float(tag), policy='CA-TOSG-RF',
                             ap30_mean=round(float(np.mean(a30s)), 4),
                             ap50_mean=round(float(np.mean(a50s)), 4),
                             ap70_mean=round(float(np.mean(a70s)), 4), n_realisations=R,
                             gt_dropped_pct=round(100 * dropped_gt / max(1, kept_gt + dropped_gt), 3)))
            print(f'[{split} B{tag}] CA-TOSG-RF AP@.5={np.mean(a50s):.4f} (R={R})', flush=True)

    df = pd.DataFrame(rows)
    # R52: the filename carries the SPLIT SET too. The first version keyed only on (x, y), so a
    # later run over a subset of splits silently overwrote a complete table with a partial one --
    # which is exactly what happened between the validate run and the test+culver run.
    tag = '-'.join(sorted(s for s in a.splits.split(',') if s))
    p = os.path.join(OUT, f'volume_diagnostic_x{a.x:g}_y{a.y:g}_{tag}.csv')
    df.to_csv(p, index=False)

    # side by side with the frozen table, cell by cell
    if os.path.exists(FROZEN):
        fz = pd.read_csv(FROZEN)
        fz['budget'] = fz['budget'].astype(str)
        df['budget'] = df['budget'].astype(str)
        j = df.merge(fz, on=['split', 'budget', 'policy'], suffixes=('_crop', '_frozen'), how='left')
        j['d_ap50'] = (j['ap50_mean_crop'] - j['ap50_mean_frozen']).round(4)
        j['d_ap70'] = (j['ap70_mean_crop'] - j['ap70_mean_frozen']).round(4)
        cols = ['split', 'budget', 'policy', 'ap50_mean_frozen', 'ap50_mean_crop', 'd_ap50',
                'ap70_mean_frozen', 'ap70_mean_crop', 'd_ap70', 'gt_dropped_pct']
        j[cols].to_csv(os.path.join(OUT, f'volume_delta_x{a.x:g}_y{a.y:g}_{tag}.csv'), index=False)
        print('\n=== frozen vs common-volume, per cell ===')
        print(j[cols].to_string(index=False))
    print(f'\nwrote {os.path.relpath(p, ROOT)} (DIAGNOSTIC ONLY; no frozen product was touched)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
