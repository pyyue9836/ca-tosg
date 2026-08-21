#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R56: the intersection-GT track — both arms scored against provably identical objects.

Third labelled track, beside the frozen one and the R53 common-volume diagnostic. It exists because
two in-dataset GT filters disagreed near the $|y|$ boundary (Where2comm's config filters at 38.4 m,
the mainline's at 40 m), and no post-hoc geometric crop reconciles two different filters — R55-1
measured the residue at 2.4 / 0.6 / 1.4 % of objects, one-sided.

Construction, pre-registered before running:

  * per frame, match ground-truth boxes between the two canonical sets by **box-centre distance**,
    one-to-one, greedy mutual nearest neighbour, with tolerance **eps = 0.5 m**; a many-to-one match
    is refused rather than resolved;
  * the intersection is the set of matched objects, and it is used as the GT for **both** arms;
  * **assertion**: the two sides' intersection counts are strictly equal per split — that equality
    is the entire reason this track exists, so it is checked, not assumed.

The tolerance is generous by design and the result does not depend on it: measured over 300 validate
frames, matched centres are bit-identical (median, p95, p99 and max nearest-neighbour distance all
0.000 m), because both sets come from the same simulator annotations. The script reports the match
count at eps = 0.01 m as well, so a future reader can see the insensitivity rather than trust this
sentence.

    python baselines/where2comm_v2/intersection_gt_track.py --point validate:0.02 --point test:0.015 \
        --point culver:0.02 [--x 70.4] [--y 38.4] [--realisations 20]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
sys.path.insert(0, os.environ.get('OPENCOOD_ROOT',
                                  os.path.expanduser('~/cooperative_semantic_perception/OpenCOOD')))

import end_to_end_ap as E                                   # noqa: E402
import deployment as D                                      # noqa: E402

OUT = os.path.join(ROOT, 'results', 'diagnostics')
EPS = 0.5                     # metres, pre-registered
EPS_TIGHT = 0.01              # the insensitivity probe


def centres(t):
    return t[:, :, :2].mean(axis=1) if t.shape[0] else np.zeros((0, 2))


def match(a, b, eps):
    """Greedy mutual-nearest one-to-one matching. Returns index pairs within eps."""
    if a.shape[0] == 0 or b.shape[0] == 0:
        return [], []
    ca, cb = centres(a), centres(b)
    dm = np.linalg.norm(ca[:, None, :] - cb[None, :, :], axis=2)
    ia, ib = [], []
    used_b = set()
    order = np.dstack(np.unravel_index(np.argsort(dm, axis=None), dm.shape))[0]
    used_a = set()
    for i, j in order:
        if dm[i, j] > eps:
            break
        if i in used_a or j in used_b:
            continue                      # one-to-one: a second claim on either side is refused
        used_a.add(int(i)); used_b.add(int(j)); ia.append(int(i)); ib.append(int(j))
    return ia, ib


def crop(t, xl, yl):
    if t.shape[0] == 0:
        return t, np.ones(0, dtype=bool)
    c = centres(t)
    k = (np.abs(c[:, 0]) <= xl) & (np.abs(c[:, 1]) <= yl)
    return t[k], k


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--point', action='append', required=True,
                    help='split:threshold of a Where2comm cache, e.g. validate:0.02')
    ap.add_argument('--x', type=float, default=70.4)
    ap.add_argument('--y', type=float, default=38.4)
    ap.add_argument('--realisations', type=int, default=20)
    ap.add_argument('--budget', default='0.10', choices=['0.10', '0.20', '0.30'],
                    help='which frozen selector the CA-TOSG row uses; must be the budget the '
                         'Where2comm point is matched to (R56)')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rows = []

    for spec in a.point:
        split, thr = spec.split(':')
        npz = os.path.join(ROOT, f'data/where2comm_v2/{split}_thr{thr}.npz')
        z = np.load(npz, allow_pickle=True)
        meta = json.load(open(os.path.splitext(npz)[0] + '.json'))
        dl = np.load(os.path.join(E.GS, f'late_{split}.npz'), allow_pickle=True)
        dc = np.load(os.path.join(E.GS, f'comp_{split}.npz'), allow_pickle=True)
        de = np.load(os.path.join(E.GS, f'ego_{split}.npz'), allow_pickle=True)
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        sids = ds['sample_id'].astype(int).to_numpy()
        n = len(sids)

        WST, LST, CST, EST, gtn = [], [], [], [], []
        tot_w = tot_m = tot_tight = 0
        print(f'[{split} thr={thr}] building the intersection GT over {n} frames', flush=True)
        for k, s in enumerate(sids):
            gw = E.tt(list(z['gts'])[k], (0, 8, 3))
            gm = E.tt(list(dc['gts'])[s], (0, 8, 3))
            iw, im = match(gw, gm, EPS)
            tot_tight += len(match(gw, gm, EPS_TIGHT)[0])
            canon_w, canon_m = gw[iw], gm[im]
            tot_w += canon_w.shape[0]; tot_m += canon_m.shape[0]
            canon, _ = crop(canon_m, a.x, a.y)               # one GT for both sides, then cropped
            gtn.append(canon.shape[0])
            for src, store in ((z, WST),):
                b, kb = crop(E.tt(list(src['boxes'])[k], (0, 8, 3)), a.x, a.y)
                sc = E.tt(list(src['scores'])[k], (0,))
                sc = sc[kb] if sc.shape[0] == kb.shape[0] else sc[:b.shape[0]]
                store.append(E.frame_stats(b, sc, canon))
            for src, store in ((dl, LST), (dc, CST), (de, EST)):
                b, kb = crop(E.tt(list(src['boxes'])[s], (0, 8, 3)), a.x, a.y)
                sc = E.tt(list(src['scores'])[s], (0,))
                sc = sc[kb] if sc.shape[0] == kb.shape[0] else sc[:b.shape[0]]
                store.append(E.frame_stats(b, sc, canon))
            if k % 500 == 0:
                print(f'  {k}/{n}', flush=True)

        if tot_w != tot_m:
            print(f'INTERSECTION ASSERTION FAIL [{split}]: {tot_w} vs {tot_m} matched objects -- '
                  f'the matching is not one-to-one and the track is invalid')
            return 1
        print(f'INTERSECTION ASSERTION PASS [{split}]: {tot_w} objects on both sides '
              f'(eps={EPS} m; at eps={EPS_TIGHT} m the same matching gives {tot_tight}), '
              f'{sum(gtn)} of them inside the volume', flush=True)

        ST = [WST, LST, CST, EST]
        for name, idx in (('Where2comm', 0), ('Fixed-L', 1), ('Feature-ceiling', 2),
                          ('ego-only', 3)):
            ap30, ap50, ap70 = E.ap_pick([idx] * n, ST, gtn)
            rows.append(dict(split=split, track='intersection-GT', policy=name,
                             w2c_threshold=float(thr) if name == 'Where2comm' else None,
                             w2c_rate=meta['mean_comm_rate'] if name == 'Where2comm' else None,
                             ap50=round(float(ap50), 5), ap70=round(float(ap70), 5),
                             gt_objects=sum(gtn)))
            print(f'  {name:16s} AP@.5={ap50:.5f} AP@.7={ap70:.5f}', flush=True)

        # CA-TOSG at B_max = 0.10, the budget the Where2comm point is matched to
        man, budgets = D.load_manifest()
        tbl = pd.read_csv(D.BLER_CSV)
        bd = budgets[a.budget]
        rng = np.random.default_rng(E.CSI_SEED)
        snr = rng.uniform(0, 20, size=(E.N_REPLAY, n))
        ray = rng.random(size=(E.N_REPLAY, n)) < 0.5
        bF = np.stack([D.bler16(tbl, snr[r], ray[r]) for r in range(E.N_REPLAY)])
        coin = np.random.default_rng(E.BLER_COIN_SEED).random(size=(E.N_REPLAY, n))
        surv = coin > bF
        rf = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr, ray)
        a50, a70 = [], []
        for r in range(min(a.realisations, E.N_REPLAY)):
            picks = [1 if p == E.LATE else 2 if p == E.COMP else 3
                     for p in E.branch_of(rf[r], surv[r]).tolist()]
            v = E.ap_pick(picks, ST, gtn)
            a50.append(v[1]); a70.append(v[2])
        rows.append(dict(split=split, track='intersection-GT', policy=f'CA-TOSG-RF @ B{a.budget}',
                         w2c_threshold=None, w2c_rate=None,
                         ap50=round(float(np.mean(a50)), 5), ap70=round(float(np.mean(a70)), 5),
                         gt_objects=sum(gtn)))
        print(f'  CA-TOSG-RF@B0.10 AP@.5={np.mean(a50):.5f} AP@.7={np.mean(a70):.5f}', flush=True)

    df = pd.DataFrame(rows)
    p = os.path.join(OUT, f'intersection_gt_track_B{a.budget}.csv')
    df.to_csv(p, index=False)
    print('\n' + df.to_string(index=False))
    print(f'\nwrote {os.path.relpath(p, ROOT)} (DESCRIPTIVE; third track, nothing frozen touched)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
