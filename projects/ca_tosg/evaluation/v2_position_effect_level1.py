#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R19 B — the level-1 position effect, with the amount of loss held exactly fixed. Zero GPU.

THE QUESTION
------------
WP5 established level 1 loosely: sigma_mask > 0 everywhere, i.e. replicates of the same frame at the
same loss rate give different task outcomes. That is compatible with a purely *quantity* explanation
— replicate A lost 12 codewords, replicate B lost 15, so of course they differ.

This module removes that explanation by conditioning on it. Among the R = 4 replicates of a given
(frame, rate, regime) it keeps only the pairs whose **codeword-loss counts are exactly equal**, and
asks whether F1 still differs. Same frame. Same number of lost codewords. Only the *positions*
differ.

THE SUFFICIENCY CRITERION IS PRE-REGISTERED, AND IT IS WRITTEN HERE BEFORE THE SCRIPT WAS RUN
---------------------------------------------------------------------------------------------
Under independent per-codeword erasure the number lost is Binomial(N_cw = 12567, p), so exact ties
between two replicates are common at small p (std 3.54 at p = 0.001) and rare at mid p (std 56.05 at
p = 0.5). Whether the strict conclusion is reportable therefore depends on a count nobody has looked
at yet. It is fixed now:

    SUFFICIENT  <=>  at least 100 equal-loss pairs, spanning at least 30 distinct frames,
                     within a single regime, AND the Wilson 95 % lower bound on the
                     proportion of pairs with dF1 != 0 is strictly above 0.

The frame-count clause is there so a result cannot rest on one pathological frame paired with
itself six ways. This is a distributional argument about Binomial tie frequency, not a look at the
outcome column.

  * SUFFICIENT   -> the strict sentence is reportable:
        "At a fixed frame and an identical number of lost codewords, different loss locations can
         produce different task outcomes."
  * NOT SUFFICIENT -> level 1 only, and the |dN_cw| <= 1 stratum may be reported as a SEPARATE,
        clearly-labelled layer. It may NOT be merged with the equal-loss stratum into an
        "approximately equal amount" conclusion, and the write-up must state plainly that the
        equal-codeword sample is too small to exclude the quantity explanation.

Level 3 — "position matters MORE than amount" — is **not adjudicated here** and no threshold for it
is set: V2-R11 B-2 required that threshold to be pre-registered and it never was, so choosing one now
would be choosing it with the numbers already on screen (V2-R19 B-4).

    python projects/ca_tosg/evaluation/v2_position_effect_level1.py --split validate
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, 'results', 'v2')

RATES = (0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90)
REGIMES = ('ideal', 'packet')
R = 4

MIN_PAIRS, MIN_FRAMES = 100, 30          # pre-registered above; not revisited after the run


def col(kind, regime, p, r):
    """WP5 writes the rate into the column name with Python float repr: 0.10 -> '0.1'."""
    return f'{kind}_{regime}_p{p!r}_r{r}'


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def dist(v):
    v = np.asarray(v, float)
    if v.size == 0:
        return {'n': 0}
    return {'n': int(v.size), 'mean': float(v.mean()), 'median': float(np.median(v)),
            'p90': float(np.quantile(v, 0.90)), 'p99': float(np.quantile(v, 0.99)),
            'max': float(v.max()), 'min': float(v.min())}


def collect(df, regime, max_dcw):
    """All replicate pairs of every (frame, rate) whose |dN_cw| <= max_dcw."""
    out = []
    for p in RATES:
        f = np.column_stack([df[col('f1', regime, p, r)].to_numpy() for r in range(R)])
        c = np.column_stack([df[col('cw', regime, p, r)].to_numpy() for r in range(R)])
        for i, j in itertools.combinations(range(R), 2):
            dcw = np.abs(c[:, i] - c[:, j])
            m = dcw <= max_dcw
            if not m.any():
                continue
            out.append(pd.DataFrame({
                'rate': p, 'frame': df.frame.to_numpy()[m],
                'ri': i, 'rj': j,
                'cw_i': c[m, i], 'cw_j': c[m, j], 'dcw': dcw[m],
                'f1_i': f[m, i], 'f1_j': f[m, j],
                'df1': f[m, i] - f[m, j]}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(
        columns=['rate', 'frame', 'ri', 'rj', 'cw_i', 'cw_j', 'dcw', 'f1_i', 'f1_j', 'df1'])


def summarise(t, label):
    n = len(t)
    nz = t[t.df1 != 0] if n else t
    lo, hi = wilson(len(nz), n)
    s = {
        'label': label, 'pairs': int(n), 'frames_involved': int(t.frame.nunique()) if n else 0,
        'pairs_with_df1_nonzero': int(len(nz)),
        'proportion_df1_nonzero': float(len(nz) / n) if n else None,
        'wilson95_lo': lo, 'wilson95_hi': hi,
        'abs_df1_distribution_over_nonzero': dist(np.abs(nz.df1.to_numpy())) if n else {'n': 0},
        'abs_df1_distribution_over_all_pairs': dist(np.abs(t.df1.to_numpy())) if n else {'n': 0},
        'by_rate': {},
    }
    for p in RATES:
        sub = t[t.rate == p]
        if not len(sub):
            s['by_rate'][str(p)] = {'pairs': 0}
            continue
        subnz = sub[sub.df1 != 0]
        l2, h2 = wilson(len(subnz), len(sub))
        s['by_rate'][str(p)] = {
            'pairs': int(len(sub)), 'frames': int(sub.frame.nunique()),
            'df1_nonzero': int(len(subnz)),
            'proportion': float(len(subnz) / len(sub)),
            'wilson95_lo': l2, 'wilson95_hi': h2,
            'max_abs_df1': float(np.abs(sub.df1).max()),
        }
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate')
    args = ap.parse_args()

    src = os.path.join(OUT_DIR, f'wp5_final_{args.split}.csv')
    if not os.path.exists(src):
        raise SystemExit(f'missing WP5 product: {os.path.relpath(src, ROOT)}')
    df = pd.read_csv(src)
    print('=' * 96)
    print(f'V2-R19 B -- level-1 position effect at EXACTLY equal codeword loss: {args.split}, '
          f'{len(df)} frames, R = {R}')
    print(f'pre-registered sufficiency: >= {MIN_PAIRS} pairs, >= {MIN_FRAMES} frames, '
          f'Wilson95 lower bound > 0')
    print('=' * 96)

    res, tables = {}, {}
    for regime in REGIMES:
        eq = collect(df, regime, 0)                 # STRATUM 1 -- dN_cw == 0, the strict one
        near = collect(df, regime, 1)
        near = near[near.dcw == 1]                  # STRATUM 2 -- |dN_cw| == 1, reported SEPARATELY
        s_eq = summarise(eq, f'{regime}: dN_cw == 0')
        s_near = summarise(near, f'{regime}: |dN_cw| == 1  (SEPARATE STRATUM, never merged)')
        suff = bool(s_eq['pairs'] >= MIN_PAIRS and s_eq['frames_involved'] >= MIN_FRAMES
                    and (s_eq['wilson95_lo'] or 0) > 0)
        res[regime] = {'equal_loss': s_eq, 'near_equal_loss_separate': s_near,
                       'sufficient_by_preregistered_criterion': suff}
        tables[regime] = eq

        print(f'\n--- regime: {regime} ---')
        for s in (s_eq, s_near):
            print(f'  {s["label"]}')
            print(f'    pairs {s["pairs"]},  distinct frames {s["frames_involved"]},  '
                  f'dF1 != 0 on {s["pairs_with_df1_nonzero"]} '
                  f'({(s["proportion_df1_nonzero"] or 0) * 100:.2f} %, '
                  f'Wilson95 [{s["wilson95_lo"]:.4f}, {s["wilson95_hi"]:.4f}])')
            d = s['abs_df1_distribution_over_nonzero']
            if d['n']:
                print(f'    |dF1| over the non-zero pairs: mean {d["mean"]:.5f}  '
                      f'median {d["median"]:.5f}  p90 {d["p90"]:.5f}  max {d["max"]:.5f}')
        print(f'  PRE-REGISTERED VERDICT: '
              f'{"SUFFICIENT" if suff else "NOT SUFFICIENT"}')

    any_suff = any(v['sufficient_by_preregistered_criterion'] for v in res.values())
    strict = ('At a fixed frame and an identical number of lost codewords, different loss locations '
              'can produce different task outcomes.')
    weak = ('The equal-codeword-count sample is too small to support strictly excluding the '
            'quantity explanation. Level 1 stands as reported; the |dN_cw| <= 1 stratum is given '
            'separately and is NOT combined with it.')
    out = {
        'schema': 'catosg-v2-position-level1/1', 'split': args.split,
        'frames': int(len(df)), 'replicates': R, 'rates': list(RATES),
        'preregistered_criterion': {
            'min_pairs': MIN_PAIRS, 'min_frames': MIN_FRAMES,
            'rule': 'wilson95 lower bound on P(dF1 != 0) strictly above 0',
            'written_before_the_run': True,
            'basis': 'Binomial(N_cw, p) tie frequency -- a distributional argument, not a look at '
                     'the outcome column.'},
        'level_2_position_vs_amount': 'NOT ADJUDICATED (V2-R19 B-4). V2-R11 B-2 required a '
                                      'proportion threshold to be pre-registered and it never was; '
                                      'setting one now would be setting it with the data on screen.',
        'regimes': res,
        'verdict': 'SUFFICIENT' if any_suff else 'NOT SUFFICIENT',
        'reportable_sentence': strict if any_suff else weak,
    }
    path = os.path.join(OUT_DIR, f'position_effect_level1_{args.split}.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    for regime, t in tables.items():
        if len(t):
            t.to_csv(os.path.join(OUT_DIR,
                                  f'position_equal_loss_pairs_{regime}_{args.split}.csv'),
                     index=False)
    print('\n' + '=' * 96)
    print(f'VERDICT: {out["verdict"]}')
    print(f'REPORTABLE: {out["reportable_sentence"]}')
    print(f'wrote {os.path.relpath(path, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
