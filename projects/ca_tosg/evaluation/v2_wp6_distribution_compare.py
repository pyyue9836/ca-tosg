#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R22 D-1 — measure before retraining. Zero GPU.

**Nothing is refitted until this has been produced and read.** The input point set for the nineteen
perception cues changes from the fused multi-CAV cloud to the ego's own sweep. That is a change of
*statistical object*, not a tuning adjustment, and if the selector later behaves differently there
would be no way to tell "the leak was removed" from "there is less information" without this table.

TWO FACTORS MOVE, NOT ONE — AND THEY OPPOSE EACH OTHER
-------------------------------------------------------
The v1 cue table was extracted under the **late-fusion** config, `cav_lidar_range` x ∈ [−70.4, 70.4].
The v2 unified FOV (§3.1) is x ∈ [−140.8, 140.8]. So "v1 cue vs v2 cue" moves

    (P) the point set   all-CAV stack  ->  ego only          (fewer points)
    (R) the x-range     ±70.4 m        ->  ±140.8 m          (more points)

at the same time, in opposite directions. A single old/new column would net them into one number and
read as "barely changed", which would be the wrong conclusion drawn from the right arithmetic. The
generator therefore also emits the SAME ego points masked to the v1 range, giving a third arm that
isolates (P):

    v1        all-CAV @ ±70.4     the retired cue values
    ego@70    ego-only @ ±70.4    <- differs from v1 only by (P)
    v2        ego-only @ ±140.8   the new schema; differs from ego@70 only by (R)

**Correlation structure is reported as well as marginals**, because the selector consumes the joint
distribution: two feature sets can have similar per-column means and quite different geometry.

    python projects/ca_tosg/evaluation/v2_wp6_distribution_compare.py --split validate
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, 'results', 'v2')

PCD = ['pcd_num_points', 'pcd_mean_range', 'pcd_max_range', 'pcd_std_range', 'pcd_near_20m',
       'pcd_mid_20_50m', 'pcd_far_50_80m', 'pcd_very_far_80m', 'pcd_front_points',
       'pcd_back_points', 'pcd_left_points', 'pcd_right_points', 'pcd_front_far_30m',
       'pcd_front_far_50m', 'pcd_density_0_20', 'pcd_density_20_50', 'pcd_density_50_80']


def stats(s):
    s = pd.to_numeric(s, errors='coerce').dropna()
    return {'mean': float(s.mean()), 'median': float(s.median()),
            'p10': float(s.quantile(0.10)), 'p90': float(s.quantile(0.90)),
            'std': float(s.std()), 'min': float(s.min()), 'max': float(s.max())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate')
    args = ap.parse_args()

    v1 = pd.read_csv(os.path.join(ROOT, 'data/p2', f'dataset_{args.split}_n1.csv'))
    new = pd.read_csv(os.path.join(OUT_DIR, f'wp6_cues_{args.split}.csv'))
    dec_p = os.path.join(OUT_DIR, f'wp6_range_decomposition_{args.split}.csv')
    dec = pd.read_csv(dec_p) if os.path.exists(dec_p) else None
    if len(v1) != len(new):
        raise SystemExit(f'row counts differ: v1 {len(v1)} vs new {len(new)}')
    if dec is not None and not np.array_equal(dec.frame.to_numpy(), new.frame.to_numpy()):
        raise SystemExit('decomposition frame vector differs from the cue table')

    print('=' * 108)
    print(f'V2-R22 D-1 -- cue distribution comparison BEFORE any refit: {args.split}, {len(new)} frames')
    print('=' * 108)
    print('v1 = all-CAV @ +-70.4   |   ego@70 = ego-only @ +-70.4   |   v2 = ego-only @ +-140.8')
    print(f'{"cue":22}{"v1 mean":>13}{"ego@70 mean":>14}{"v2 mean":>13}'
          f'{"(P) ego/v1":>12}{"(R) v2/ego70":>14}{"net v2/v1":>11}')

    rows = {}
    for k in PCD:
        a, b = stats(v1[k]), stats(new['ego_' + k])
        c = stats(dec['ego70_' + k]) if dec is not None else None
        fP = (c['mean'] / a['mean']) if c and a['mean'] else None
        fR = (b['mean'] / c['mean']) if c and c['mean'] else None
        fN = (b['mean'] / a['mean']) if a['mean'] else None
        rows[k] = {'v1': a, 'ego_at_v1_range': c, 'v2': b,
                   'factor_point_set_P': fP, 'factor_range_R': fR, 'factor_net': fN}
        print(f'  {k:20}{a["mean"]:>13.3f}{(c["mean"] if c else float("nan")):>14.3f}'
              f'{b["mean"]:>13.3f}'
              f'{(fP if fP is not None else float("nan")):>12.3f}'
              f'{(fR if fR is not None else float("nan")):>14.3f}'
              f'{(fN if fN is not None else float("nan")):>11.3f}')

    # the two replaced fields, reported as replacements rather than as a like-for-like delta
    repl = {
        'ego_num_objects -> ego_detected_box_count': {
            'retired_v1_GT_field': stats(v1['ego_num_objects']),
            'new_detector_field': stats(new['ego_detected_box_count']),
            'note': 'NOT a like-for-like change: GT object count -> ego-only detected box count at '
                    'the frozen 0.20/0.15 thresholds. Comparable in scale, different in kind.'},
        'num_cavs -> has_collaborator': {
            'retired_v1_field': stats(v1['num_cavs']),
            'new_field': stats(new['has_collaborator']),
            'note': 'v1 encoded the size of the fused set (2-7), which is post-decision; the '
                    'replacement is a binary pre-decision availability flag.'},
    }
    print('\n  replaced fields (not like-for-like):')
    print(f'    ego_num_objects  mean {repl["ego_num_objects -> ego_detected_box_count"]["retired_v1_GT_field"]["mean"]:.3f} (GT)'
          f'   ->  ego_detected_box_count mean '
          f'{repl["ego_num_objects -> ego_detected_box_count"]["new_detector_field"]["mean"]:.3f} (detector)')
    print(f'    num_cavs         mean {repl["num_cavs -> has_collaborator"]["retired_v1_field"]["mean"]:.3f}'
          f'   ->  has_collaborator       mean '
          f'{repl["num_cavs -> has_collaborator"]["new_field"]["mean"]:.3f}')

    # correlation geometry: the selector consumes the joint distribution, not 19 marginals
    old_cols = PCD + ['ego_num_objects', 'num_cavs']
    new_cols = ['ego_' + k for k in PCD] + ['ego_detected_box_count', 'has_collaborator']
    Co = v1[old_cols].corr().to_numpy()
    Cn = new[new_cols].corr().to_numpy()
    iu = np.triu_indices_from(Co, k=1)
    do, dn = Co[iu], Cn[iu]
    ok = np.isfinite(do) & np.isfinite(dn)
    corr = {
        'mean_abs_offdiag_v1': float(np.nanmean(np.abs(do))),
        'mean_abs_offdiag_v2': float(np.nanmean(np.abs(dn))),
        'mean_abs_change': float(np.nanmean(np.abs(dn[ok] - do[ok]))),
        'max_abs_change': float(np.nanmax(np.abs(dn[ok] - do[ok]))),
        'pairs_compared': int(ok.sum()),
        'note': 'positions matched by the replacement mapping, so the last two entries compare '
                'ego_num_objects->ego_detected_box_count and num_cavs->has_collaborator, which are '
                'replacements rather than the same quantity recomputed.',
    }
    print(f'\n  correlation geometry over {corr["pairs_compared"]} off-diagonal pairs:')
    print(f'    mean |r|  v1 {corr["mean_abs_offdiag_v1"]:.4f}  ->  v2 {corr["mean_abs_offdiag_v2"]:.4f}')
    print(f'    mean |change| {corr["mean_abs_change"]:.4f}   max |change| {corr["max_abs_change"]:.4f}')

    out = {'schema': 'catosg-v2-wp6-distribution-compare/1', 'split': args.split,
           'frames': int(len(new)),
           'why': 'D-1: measured BEFORE any refit, so a later change in selector behaviour can be '
                  'attributed. Two factors move and oppose each other -- point set (all-CAV -> '
                  'ego-only) and x-range (+-70.4 -> +-140.8) -- so a single old/new column would '
                  'net them into a misleadingly small number.',
           'arms': {'v1': 'all-CAV @ +-70.4 (retired)',
                    'ego_at_v1_range': 'ego-only @ +-70.4 (isolates the point-set factor)',
                    'v2': 'ego-only @ +-140.8 (the new schema)'},
           'per_cue': rows, 'replaced_fields': repl, 'correlation': corr}
    p = os.path.join(OUT_DIR, f'wp6_distribution_compare_{args.split}.json')
    with open(p, 'w') as f:
        json.dump(out, f, indent=1)
    print(f'\nwrote {os.path.relpath(p, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
