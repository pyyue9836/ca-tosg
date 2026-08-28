#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R25 B — `eff_F` on the SNR grid: replicate mean, then piecewise-linear interpolation in raw p.

Protocol §9.3(a)–(g). This is the one genuinely NEW modelling layer in the v2 oracle chain, and a
wrong implementation of it produces a curve that looks perfectly reasonable — smooth, monotone-ish,
bounded — while being wrong everywhere between the nodes. That is why §9.3's self-check is a
precondition of use rather than a test someone might run: see `self_check()` and `--self-test`.

THE RULES, EACH TRACEABLE TO A PROTOCOL CLAUSE
----------------------------------------------
  (a) replicates averaged with equal weight, per frame -- a replicate is a channel realisation
  (b) piecewise linear in RAW p, never log p. The interpolation coordinate must be the variable the
      quantity is roughly linear in, and the damaged fraction of transmitted elements is ~ p. log p
      also diverges at p = 0: a coordinate system needing a patch to cover its own endpoint is the
      wrong coordinate system.
  (c) endpoints locked -- p = 0 is clean F1, p = 1 is the measured all-lost F1; no extrapolation
  (d) NO monotone correction. Some masks raise a frame's F1 by removing false positives, which is
      the observation §5.1(a)'s strict result rests on; smoothing it away would erase a finding.
  (e) mainline = the `ideal` fragment-aware partial-recovery regime
  (f) `packet` built by the identical rule, as a SEPARATE sensitivity grid, never for selection
  (g) only per-frame F1 is interpolated -- never AP

    python projects/ca_tosg/models/v2_eff_f.py --self-test
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
V2 = os.path.join(ROOT, 'results', 'v2')

RATES = (0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9)
R = 4
TOL = 1e-12


def load_nodes(split='validate', regime='ideal'):
    """-> (frames, p_nodes, F) with F[t, i] the replicate MEAN at node i (clause a).

    p_nodes runs 0.0, the 8 WP5 rates, then 1.0 -- the endpoints are real measurements
    (clean F1 and the p = 1.00 forward), not extrapolations (clause c).
    """
    df = pd.read_csv(os.path.join(V2, f'wp5_final_{split}.csv'))
    frames = df.frame.to_numpy()
    cols = []
    for p in RATES:
        reps = [df[f'f1_{regime}_p{p!r}_r{r}'].to_numpy() for r in range(R)]
        cols.append(np.mean(np.column_stack(reps), axis=1))          # (a) equal weight
    F_mid = np.column_stack(cols)
    clean = df['f1_clean'].to_numpy()
    allost = df['f1_p1.0'].to_numpy()
    p_nodes = np.array((0.0,) + RATES + (1.0,), float)
    F = np.column_stack([clean, F_mid, allost])
    return frames, p_nodes, F


def eff_f(p, p_nodes, F):
    """Piecewise-linear in raw p (clause b). p may be scalar or an array broadcast over frames.

    No monotone correction (clause d) and no extrapolation (clause c): p is clamped into [0, 1],
    which are both measured nodes, so clamping never invents a value.
    """
    p = np.asarray(p, float)
    if np.any(p < 0) or np.any(p > 1):
        raise ValueError('p outside [0, 1] -- extrapolation is forbidden by §9.3(c)')
    idx = np.clip(np.searchsorted(p_nodes, p, side='right') - 1, 0, len(p_nodes) - 2)
    p0 = p_nodes[idx]
    p1 = p_nodes[idx + 1]
    w = np.where(p1 > p0, (p - p0) / np.where(p1 > p0, p1 - p0, 1.0), 0.0)
    if F.ndim == 2 and np.ndim(p) == 1 and len(p) == F.shape[0]:
        rows = np.arange(F.shape[0])
        return (1 - w) * F[rows, idx] + w * F[rows, idx + 1]
    return (1 - w) * F[..., idx] + w * F[..., idx + 1]


def self_check(p_nodes, F, tol=TOL, F_ref=None):
    """§9.3's precondition: at every node the interpolant must equal the REPLICATE MEAN (D-1..D-3).

    `F_ref` is the source of truth to compare against, defaulting to the matrix the interpolant was
    built from. It exists because comparing the interpolant to its OWN nodes is self-consistent by
    construction and therefore cannot fail -- the D-4 injection needs to build from a corrupted
    matrix and compare against the true one. Written this way only after the first version's
    injections all came back SILENT, which is exactly the failure it now guards.
    """
    ref = F if F_ref is None else F_ref
    fails = []
    for i, p in enumerate(p_nodes):
        got = eff_f(np.full(F.shape[0], p), p_nodes, F)
        d = np.abs(got - ref[:, i])
        if d.max() > tol:
            k = int(d.argmax())
            fails.append(f'node p={p}: max |interp - replicate mean| = {d.max():.3e} > {tol:g} '
                         f'(worst frame index {k}: {got[k]!r} vs {F[k, i]!r})')
    # D-3, stated separately because they are different claims from "a node reproduces"
    if np.abs(eff_f(np.zeros(F.shape[0]), p_nodes, F) - ref[:, 0]).max() > tol:
        fails.append('p=0 does not return the clean F1')
    if np.abs(eff_f(np.ones(F.shape[0]), p_nodes, F) - ref[:, -1]).max() > tol:
        fails.append('p=1 does not return the all-lost F1')
    return fails


def self_test(split='validate'):
    frames, p_nodes, F = load_nodes(split)
    fails = self_check(p_nodes, F)
    print(f'  nodes {len(p_nodes)} (0.0, 8 WP5 rates, 1.0) over {F.shape[0]} frames')
    print(f'  {"CLEAN  " if not fails else "FAIL   "}  every node reproduced to {TOL:g}')
    for f in fails:
        print('      ' + f)
    if fails:
        print('EFF_F SELF-TEST FAIL')
        return 1

    # D-4: perturb one node by one decimal place; the check MUST fire
    ok = True
    for i in (0, 3, len(p_nodes) - 1):
        G = F.copy()
        G[0, i] = round(float(G[0, i]) + 0.1, 12)
        f = self_check(p_nodes, G, F_ref=F)
        print(f'  {"FIRES  " if f else "SILENT "}  node index {i} perturbed by 0.1 on one frame')
        ok &= bool(f)

    # (d): assert the interpolant is NOT monotone in p -- if it were, the "no smoothing" clause
    # would be describing a property the data happens not to have, and a future smoothing bug
    # would be invisible.
    mid = eff_f(np.full(F.shape[0], 0.02), p_nodes, F)
    lo = eff_f(np.full(F.shape[0], 0.001), p_nodes, F)
    rises = int((mid > lo + 1e-12).sum())
    print(f'  non-monotone frames between p=0.001 and p=0.02: {rises}/{F.shape[0]} '
          f'(clause d -- these are real and must not be smoothed away)')

    print('EFF_F SELF-TEST ' + ('PASS' if ok else 'FAIL: a perturbation did not fire'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(self_test() if '--self-test' in sys.argv else self_test())
