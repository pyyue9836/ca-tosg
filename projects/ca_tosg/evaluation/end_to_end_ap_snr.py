#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-5 item 8: true end-to-end AP at a PINNED SNR, under the frozen protocol.

`end_to_end_ap.py` draws `snr ~ U[0,20]` and `channel ~ Bernoulli(0.5)` and therefore marginalises
the channel away: it can only produce `split x budget x policy`. The paper's §generalisation
per-SNR AP knee has no frozen-protocol source at all -- the published curve came from the retired v3
global-sort scorer.

This module is that engine with **one** difference: where the SNR/channel draw happens, a pinned
(snr, channel) pair is substituted. Everything else -- the caches, the canonical union GT, the
per-frame stat precomputation, `ap_pick`, `branch_of`, the frozen selector application, the
BLER-coin seed and its pairing between RF and tau -- is *imported from* `end_to_end_ap` rather than
re-implemented, so the two cannot drift apart.

That claim is not asserted, it is gated. `--mode uniform` restores the original draw and the result
must reproduce every committed row of `results/main/true_e2e_ap.csv` exactly:

    python projects/ca_tosg/evaluation/end_to_end_ap_snr.py --verify      # the E-8 gate
    python projects/ca_tosg/evaluation/end_to_end_ap_snr.py --pinned ...  # only after it passes

Per the pre-registration, no pinned-SNR number may be produced or quoted until `--verify` passes.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import end_to_end_ap as E                                  # noqa: E402  (path set above)
import deployment as D                                     # noqa: E402

OUT_CSV = os.path.join(E.OUT, 'true_e2e_ap_by_snr.csv')
VERIFY_CSV = os.path.join(E.OUT, 'true_e2e_ap.csv')


def load_split(split):
    """Caches + per-frame stats vs the canonical union GT -- lifted verbatim from end_to_end_ap."""
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
    n = len(ds)
    sids = ds['sample_id'].astype(int).to_numpy()

    dl = np.load(os.path.join(E.GS, f'late_{split}.npz'), allow_pickle=True)
    dc = np.load(os.path.join(E.GS, f'comp_{split}.npz'), allow_pickle=True)
    de = np.load(os.path.join(E.GS, f'ego_{split}.npz'), allow_pickle=True)
    lb, ls = list(dl['boxes']), list(dl['scores'])
    cb, cs, cg = list(dc['boxes']), list(dc['scores']), list(dc['gts'])
    eb, es = list(de['boxes']), list(de['scores'])

    print(f'[{split}] precomputing per-frame stats for {n} frames...', flush=True)
    LST, CST, EST, gtn = [], [], [], []
    for k, s in enumerate(sids):
        canon = E.tt(cg[s], (0, 8, 3))
        gtn.append(canon.shape[0])
        LST.append(E.frame_stats(lb[s], ls[s], canon))
        CST.append(E.frame_stats(cb[s], cs[s], canon))
        EST.append(E.frame_stats(eb[s], es[s], canon))
        if k % 500 == 0:
            print(f'  {k}/{n}', flush=True)
    return ds, n, [LST, CST, EST], gtn


def draws(n, mode, snr_db, is_rayleigh):
    """The ONLY difference from end_to_end_ap: how (snr, channel) are obtained.

    `uniform` reproduces the committed draw bit-for-bit -- same generator, same seed, same call
    order. `pinned` replaces both with constants and touches nothing else.
    """
    rng = np.random.default_rng(E.CSI_SEED)
    if mode == 'uniform':
        snr_2d = rng.uniform(0, 20, size=(E.N_REPLAY, n))
        is_ray_2d = rng.random(size=(E.N_REPLAY, n)) < 0.5
    elif mode == 'pinned':
        snr_2d = np.full((E.N_REPLAY, n), float(snr_db))
        is_ray_2d = np.full((E.N_REPLAY, n), bool(is_rayleigh))
    else:
        raise ValueError(mode)
    return snr_2d, is_ray_2d


def evaluate(split, ds, n, ST, gtn, tbl, budgets, tags, mode, snr_db=None, is_ray=None):
    snr_2d, is_ray_2d = draws(n, mode, snr_db, is_ray)
    bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(E.N_REPLAY)])
    coin_2d = np.random.default_rng(E.BLER_COIN_SEED).random(size=(E.N_REPLAY, n))
    survive_2d = coin_2d > bF_2d

    # Exact memo, pinned mode only. `E.ap_pick` is a pure function of `picks` (ST and gtn are
    # fixed for the split), so caching on the picks vector changes no value. It matters here
    # because at a pinned SNR the feature vector is identical across all 200 replays, so the
    # action vector is too, and under AWGN the BLER is ~0 or ~1 at almost every grid point --
    # the coin is then degenerate and all 200 replays share one picks vector. The `uniform`
    # path deliberately keeps the un-memoised call, so the E-8 gate still exercises the
    # original code path byte for byte.
    memo = {}

    def ap_of(picks):
        if mode != 'pinned':
            return E.ap_pick(picks, ST, gtn)
        key = hash(tuple(picks))
        if key not in memo:
            memo[key] = E.ap_pick(picks, ST, gtn)
        return memo[key]

    rows = []
    if mode == 'uniform':
        # the deterministic references are budget- and channel-independent; only the uniform run
        # emits them, because that is what the committed table contains
        for pol, picks in (('Fixed-L', [E.LATE] * n), ('Feature-ceiling', [E.COMP] * n),
                           ('ego-only', [E.EGO] * n)):
            ap = E.ap_pick(picks, ST, gtn)
            rows.append(dict(split=split, budget='-', policy=pol,
                             ap30_mean=round(ap[0], 4), ap30_std=0.0,
                             ap50_mean=round(ap[1], 4), ap50_std=0.0,
                             ap70_mean=round(ap[2], 4), ap70_std=0.0, n_realisations=1))

    for tag in tags:
        bd = budgets[tag]
        bmax = float(tag)
        rf_idx = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr_2d, is_ray_2d)
        ta_idx = D.tau_actions(snr_2d, is_ray_2d, bd['tau'])
        for pol, act_2d in (('CA-TOSG-RF', rf_idx), ('SNR-threshold', ta_idx)):
            a30, a50, a70 = [], [], []
            for r in range(E.N_REPLAY):
                picks = E.branch_of(act_2d[r], survive_2d[r]).tolist()
                v = ap_of(picks)
                a30.append(v[0]); a50.append(v[1]); a70.append(v[2])
            row = dict(split=split, budget=bmax, policy=pol,
                       ap30_mean=round(float(np.mean(a30)), 4), ap30_std=round(float(np.std(a30)), 4),
                       ap50_mean=round(float(np.mean(a50)), 4), ap50_std=round(float(np.std(a50)), 4),
                       ap70_mean=round(float(np.mean(a70)), 4), ap70_std=round(float(np.std(a70)), 4),
                       n_realisations=E.N_REPLAY)
            if mode == 'pinned':
                row.update(snr_db=float(snr_db), channel='rayleigh' if is_ray else 'awgn',
                           rho_E=float((act_2d[0] == 0).mean()),
                           rho_L=float((act_2d[0] == 1).mean()),
                           rho_F=float((act_2d[0] == 2).mean()),
                           bler_F=float(bF_2d[0, 0]))
            rows.append(row)
            tail = f' [snr={snr_db} {"rayleigh" if is_ray else "awgn"}]' if mode == 'pinned' else ''
            print(f'[{split} B{int(bmax * 100):03d}]{tail} {pol:14s} '
                  f'AP@.5={np.mean(a50):.4f} AP@.7={np.mean(a70):.4f}', flush=True)
    return rows


def verify():
    """E-8: uniform mode must reproduce every committed row of true_e2e_ap.csv exactly."""
    man, budgets = D.load_manifest()
    tbl = pd.read_csv(D.BLER_CSV)
    tags = sorted(budgets)
    got = []
    for split in E.SPLITS:
        ds, n, ST, gtn = load_split(split)
        got += evaluate(split, ds, n, ST, gtn, tbl, budgets, tags, 'uniform')
    new = pd.DataFrame(got)
    ref = pd.read_csv(VERIFY_CSV)

    key = ['split', 'budget', 'policy']
    new['budget'] = new['budget'].astype(str)
    ref['budget'] = ref['budget'].astype(str)
    merged = ref.merge(new, on=key, how='outer', suffixes=('_ref', '_new'), indicator=True)
    cols = [c for c in ref.columns if c not in key]

    bad = merged[merged['_merge'] != 'both']
    diffs = []
    for c in cols:
        a, b = merged[f'{c}_ref'], merged[f'{c}_new']
        neq = ~(a.astype(str) == b.astype(str))
        for i in merged.index[neq]:
            diffs.append((merged.loc[i, key].tolist(), c, a[i], b[i]))

    print('\n' + '=' * 78)
    print(f'E-8 REPRODUCTION GATE: {len(ref)} committed rows, {len(new)} produced')
    if len(bad):
        print(f'** {len(bad)} row(s) present on only one side:')
        print(bad[key + ['_merge']].to_string(index=False))
    if diffs:
        print(f'** {len(diffs)} cell mismatch(es):')
        for k, c, a, b in diffs[:40]:
            print(f'   {k} {c}: committed={a} produced={b}')
    ok = not len(bad) and not diffs
    print('E-8 PASS -- uniform mode reproduces the committed table exactly' if ok else
          'E-8 FAIL -- no pinned-SNR number may be produced (pre-registered stop)')
    print('=' * 78)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true', help='run the E-8 reproduction gate and exit')
    ap.add_argument('--splits', nargs='+', default=['test', 'culver'])
    ap.add_argument('--channels', nargs='+', default=['awgn'], choices=['awgn', 'rayleigh'])
    ap.add_argument('--snr', nargs='+', type=float,
                    default=[0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
    ap.add_argument('--budgets', nargs='+', default=None, help='default: every frozen budget')
    ap.add_argument('--out', default=OUT_CSV)
    args = ap.parse_args()

    if args.verify:
        return verify()

    if not os.path.exists(VERIFY_CSV):
        print('refusing to run: the reference table is missing, so the E-8 gate cannot have passed')
        return 1

    man, budgets = D.load_manifest()
    tbl = pd.read_csv(D.BLER_CSV)
    tags = sorted(args.budgets or budgets)

    rows = []
    for split in args.splits:
        ds, n, ST, gtn = load_split(split)
        for ch in args.channels:
            for snr in args.snr:
                rows += evaluate(split, ds, n, ST, gtn, tbl, budgets, tags,
                                 'pinned', snr_db=snr, is_ray=(ch == 'rayleigh'))
    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f'\nwrote {args.out}  ({len(df)} rows; splits={args.splits} channels={args.channels} '
          f'snr={args.snr} budgets={tags})')
    print('COVERAGE NOTE: any split/channel/budget not listed above is NOT covered by this file.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
