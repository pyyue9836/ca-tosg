#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R58-2: the Where2comm arm under the modelled transport, not under ideal delivery.

R58-1 corrected the record: the earlier comparison applied no channel model to either arm. This
script supplies the missing half. Four things must match the mainline exactly or the comparison is
not a comparison, and each is spelled out because getting one of them wrong is invisible in the
output:

  1. **Draw order.** `rng = default_rng(CSI_SEED)`, then `uniform(0, 20, (R, n))`, then
     `random((R, n)) < 0.5`, in that order -- the same sequence `end_to_end_ap.main()` uses, so the
     two arms see the same channel realisations frame by frame.
  2. **The arm's own codeword count.** The frame BLER of the mainline table is computed at
     `N_cw = 3960`, which belongs to the mainline's payload. Where2comm's payload differs per grid
     point, so its frame BLER is re-derived from the `bler_cw` column at its own
     `N_cw(s) = info_bits(s) / K`, `K = 500` -- never read off the `bler_frame` column.
  3. **A separate, shared delivery coin.** `default_rng(BLER_COIN_SEED)`, so the CSI draws stay
     byte-identical to deployment and both arms are paired on the same coin.
  4. **The fallback is this arm's own ego-only forward**, cached at threshold 1.1 (mask empty, the
     module forces the ego row), not the mainline's ego branch.

Invariant checked before anything is reported: at `bF = 0` the replay must reproduce the
ideal-delivery AP of the same grid point exactly.

    python baselines/where2comm_v2/transport_replay.py --point test:0.015 --budget 0.10
"""
from __future__ import annotations

import argparse
import json
import math
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
from intersection_gt_track import match, crop, EPS          # noqa: E402

OUT = os.path.join(ROOT, 'results', 'diagnostics')
REF = 256 * 48 * 176
BPE = 1.98e6 / REF
HW = 48 * 176
IDX = math.ceil(math.log2(HW))
K_INFO = 500                      # LDPC information bits per codeword, as in the mainline chain


def w2c_info_bits(s):
    return s * REF * BPE + min(s * HW * IDX, HW)


def w2c_n_cw(s):
    return max(1, int(round(w2c_info_bits(s) / K_INFO)))


def frame_bler_at(bler_cw, n_cw):
    return 1.0 - np.power(1.0 - np.asarray(bler_cw, dtype=float), n_cw)


def arm_bler(tbl, n_cw, snr, is_ray):
    """Frame BLER for THIS arm's codeword count, interpolated on the committed table."""
    out = np.empty_like(snr, dtype=float)
    for chan, mask in (('awgn', ~is_ray), ('rayleigh', is_ray)):
        t = tbl[(tbl.qam == 16) & (tbl.channel == chan)].sort_values('esno_db')
        fb = frame_bler_at(t.bler_cw.to_numpy(), n_cw)
        out[mask] = np.interp(snr[mask], t.esno_db.to_numpy(), fb, left=1.0, right=fb[-1])
    return np.clip(out, 0.0, 1.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--point', required=True, help='split:threshold, e.g. test:0.015')
    ap.add_argument('--budget', required=True, choices=['0.10', '0.20', '0.30'])
    ap.add_argument('--realisations', type=int, default=E.N_REPLAY)
    ap.add_argument('--x', type=float, default=70.4)
    ap.add_argument('--y', type=float, default=38.4)
    ap.add_argument('--mix', default=None,
                    help='amendment A2: mix a second threshold per frame, "thr:p" -- p is the '
                         'probability of using THIS point, chosen so the mean fraction hits the cap')
    ap.add_argument('--mix_seed', type=int, default=20260822)
    a = ap.parse_args()
    split, thr = a.point.split(':')

    zc = np.load(os.path.join(ROOT, f'data/where2comm_v2/{split}_thr{thr}.npz'), allow_pickle=True)
    zm, mix_p, mix_thr = None, 0.0, None
    if a.mix:                                   # A2: a per-frame mixture of two grid points
        mix_thr, mix_p = a.mix.split(':')[0], float(a.mix.split(':')[1])
        zm = np.load(os.path.join(ROOT, f'data/where2comm_v2/{split}_thr{mix_thr}.npz'),
                     allow_pickle=True)
    ze = np.load(os.path.join(ROOT, f'data/where2comm_v2/{split}_thr1.1.npz'), allow_pickle=True)
    meta = json.load(open(os.path.join(ROOT, f'data/where2comm_v2/{split}_thr{thr}.json')))
    rate = float(meta['mean_comm_rate'])
    n_cw = w2c_n_cw(rate)
    if zm is not None:
        meta_m = json.load(open(os.path.join(ROOT,
                                             f'data/where2comm_v2/{split}_thr{mix_thr}.json')))
        rate_m = float(meta_m['mean_comm_rate'])
        n_cw_m = w2c_n_cw(rate_m)
        rate = mix_p * rate + (1 - mix_p) * rate_m          # the realised mean fraction
        print(f'A2 mixture: p={mix_p:.4f} of thr={thr} (rate {meta["mean_comm_rate"]:.4f}, '
              f'N_cw={n_cw}) with thr={mix_thr} (rate {rate_m:.4f}, N_cw={n_cw_m}); '
              f'mean fraction {rate:.4f}', flush=True)

    dl = np.load(os.path.join(E.GS, f'late_{split}.npz'), allow_pickle=True)
    dc = np.load(os.path.join(E.GS, f'comp_{split}.npz'), allow_pickle=True)
    de = np.load(os.path.join(E.GS, f'ego_{split}.npz'), allow_pickle=True)
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
    sids = ds['sample_id'].astype(int).to_numpy()
    n = len(sids)

    WD, WE, LST, CST, EST, WM, gtn = [], [], [], [], [], [], []
    print(f'[{split} thr={thr}] rate={rate:.4f}  N_cw={n_cw} (mainline 3960)  frames={n}', flush=True)
    for k, s in enumerate(sids):
        gw = E.tt(list(zc['gts'])[k], (0, 8, 3))
        gm = E.tt(list(dc['gts'])[s], (0, 8, 3))
        iw, im = match(gw, gm, EPS)
        canon, _ = crop(gm[im], a.x, a.y)
        gtn.append(canon.shape[0])
        srcs = [(zc, k, WD), (ze, k, WE), (dl, s, LST), (dc, s, CST), (de, s, EST)]
        if zm is not None:
            srcs.append((zm, k, WM))
        for src, idx, store in srcs:
            # R58-2: a frame with no detections at all comes back 0-d from `tt`, and `crop` then
            # raises IndexError on `.shape[0]`. The ego-only forward produces such frames on test
            # (it detects nothing in a few), which is why this only appeared once that cache joined
            # the inputs. Normalise to an empty (0, 8, 3) rather than special-casing downstream.
            raw = E.tt(list(src['boxes'])[idx], (0, 8, 3))
            if raw.ndim != 3:
                raw = np.zeros((0, 8, 3), dtype=float)
            b, kb = crop(raw, a.x, a.y)
            sc = E.tt(list(src['scores'])[idx], (0,))
            sc = sc if sc.ndim == 1 else np.zeros((0,), dtype=float)
            sc = sc[kb] if sc.shape[0] == kb.shape[0] else sc[:b.shape[0]]
            store.append(E.frame_stats(b, sc, canon))
        if k % 500 == 0:
            print(f'  {k}/{n}', flush=True)

    ST = [WD, WE, LST, CST, EST] + ([WM] if zm is not None else [])
    # 0 delivered(main point), 1 ego, 2 L, 3 F, 4 ego(mainline), 5 delivered(mixed-in point)

    # invariant: with no losses the replay must reproduce the ideal-delivery AP exactly
    ideal = E.ap_pick([0] * n, ST, gtn)
    print(f'invariant: ideal-delivery AP@0.5 = {ideal[1]:.5f}', flush=True)

    tbl = pd.read_csv(D.BLER_CSV)
    rng = np.random.default_rng(E.CSI_SEED)                 # order fixed: uniform, then random
    snr = rng.uniform(0, 20, size=(E.N_REPLAY, n))
    ray = rng.random(size=(E.N_REPLAY, n)) < 0.5
    coin = np.random.default_rng(E.BLER_COIN_SEED).random(size=(E.N_REPLAY, n))

    man, budgets = D.load_manifest()
    bd = budgets[a.budget]
    rf = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr, ray)
    bF_main = np.stack([D.bler16(tbl, snr[r], ray[r]) for r in range(E.N_REPLAY)])

    R = min(a.realisations, E.N_REPLAY)
    w50, w70, c50, c70, deliv = [], [], [], [], []
    for r in range(R):
        if zm is None:
            bF_w2c = arm_bler(tbl, n_cw, snr[r], ray[r])
            surv_w = coin[r] > bF_w2c
            src_pick = np.zeros(n, dtype=int)
        else:
            use_main = np.random.default_rng(a.mix_seed + r).random(n) < mix_p
            bF_w2c = np.where(use_main, arm_bler(tbl, n_cw, snr[r], ray[r]),
                              arm_bler(tbl, n_cw_m, snr[r], ray[r]))
            surv_w = coin[r] > bF_w2c
            src_pick = np.where(use_main, 0, 5)
        deliv.append(float(surv_w.mean()))
        v = E.ap_pick(np.where(surv_w, src_pick, 1).tolist(), ST, gtn)
        w50.append(v[1]); w70.append(v[2])
        surv_m = coin[r] > bF_main[r]
        picks = [2 if p == E.LATE else 3 if p == E.COMP else 4
                 for p in E.branch_of(rf[r], surv_m).tolist()]
        v = E.ap_pick(picks, ST, gtn)
        c50.append(v[1]); c70.append(v[2])
        if (r + 1) % 25 == 0:
            print(f'  replay {r + 1}/{R}: W2C {np.mean(w50):.5f} | CA-TOSG {np.mean(c50):.5f}',
                  flush=True)

    row = dict(split=split, threshold=float(thr), budget=a.budget, rate=round(rate, 4), n_cw=n_cw,
               realisations=R, mean_delivery_rate=round(float(np.mean(deliv)), 4),
               w2c_ap50=round(float(np.mean(w50)), 5), w2c_ap50_std=round(float(np.std(w50)), 5),
               w2c_ap70=round(float(np.mean(w70)), 5),
               catosg_ap50=round(float(np.mean(c50)), 5), catosg_ap50_std=round(float(np.std(c50)), 5),
               catosg_ap70=round(float(np.mean(c70)), 5),
               d_ap50=round(float(np.mean(w50) - np.mean(c50)), 5),
               w2c_ideal_ap50=round(float(ideal[1]), 5))
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f'transport_replay_{split}_thr{thr}_B{a.budget}.json')
    json.dump(row, open(p, 'w'), indent=2)
    print(json.dumps(row, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
