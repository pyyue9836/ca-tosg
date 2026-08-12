#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard for erratum P3-1: every P3 sensitivity draw must live on the pre-registered SNR grid.

The defect this exists to prevent: declaring the 11-point grid {0,2,...,20} dB in the protocol and
then sampling the sensitivity items from the continuum, so the distribution that reached the
selector was never the one the protocol declared.

Checks:
  1. GRID       the grid the sampler uses IS the protocol's grid (parsed out of
                docs/experiment_protocol.md, not taken on trust from the code).
  2. MASS       each declared distribution's probabilities sum to 1 and are non-negative;
                `uniform` is exactly 1/11 per point.
  3. SUPPORT    a large draw from each distribution lands only on grid points, and covers every
                point that carries mass (so a sampler that silently collapsed to one value fails).
  4. MAINLINE   the continuous path is still continuous -- baseline_sanity must keep reproducing
                the mainline replay, so this erratum must not have moved it onto the grid.
  5. BITES      a continuous draw is fed through the same support assertion and must FAIL it.

  python tests/test_p3_snr_support.py
"""
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))

import sensitivity as P3  # noqa: E402

PROTOCOL = os.path.join(ROOT, 'docs/experiment_protocol.md')
DISTS = ('uniform', 'beta25_lowskew', 'truncgauss_10_5')
N_DRAW = (200, 300)


def protocol_grid():
    """The 11 SNR points as the protocol states them -- derived, never hardcoded here."""
    txt = open(PROTOCOL, encoding='utf-8').read()
    m = re.search(r'\*\*SNR grid:\*\*\s*\{([0-9,\s]+)\}\s*dB', txt)
    if not m:
        raise SystemExit('SNR grid not found in docs/experiment_protocol.md')
    return np.array([int(x) for x in m.group(1).replace(' ', '').split(',')], dtype=float)


def on_grid(x, grid):
    return set(np.unique(np.asarray(x)).tolist()).issubset(set(grid.tolist()))


def main():
    grid = protocol_grid()
    fails = []
    print('P3 SNR support:')

    if not np.array_equal(np.asarray(P3.SNR_GRID, dtype=float), grid):
        fails.append('sensitivity.SNR_GRID %s != the protocol grid %s'
                     % (list(P3.SNR_GRID), list(grid)))
    print('  1. grid          %d points, matches docs/experiment_protocol.md sec 3' % len(grid))

    for d in DISTS:
        p = np.asarray(P3.grid_probs(d), dtype=float)
        if p.shape != grid.shape:
            fails.append('%s: %d probabilities for %d grid points' % (d, p.size, grid.size))
            continue
        if (p < 0).any():
            fails.append('%s: negative probability' % d)
        if abs(p.sum() - 1.0) > 1e-12:
            fails.append('%s: probabilities sum to %.15f, not 1' % (d, p.sum()))
        if d == 'uniform' and not np.allclose(p, 1.0 / len(grid), atol=0, rtol=1e-12):
            fails.append('uniform is not equal-probability 1/%d per point' % len(grid))
        print('  2. mass          %-16s sum=%.12f  min=%.5f max=%.5f' % (d, p.sum(), p.min(), p.max()))

    for d in DISTS:
        x = P3.draw_snr(np.random.default_rng(20260812), N_DRAW, d, grid=True)
        if not on_grid(x, grid):
            off = sorted(set(np.unique(x).tolist()) - set(grid.tolist()))[:5]
            fails.append('%s: drew off-grid values %s' % (d, off))
        p = np.asarray(P3.grid_probs(d))
        want = set(grid[p > 1e-4].tolist())
        got = set(np.unique(x).tolist())
        if not want.issubset(got):
            fails.append('%s: points with mass never drawn: %s' % (d, sorted(want - got)))
        print('  3. support       %-16s %d distinct values, all on the grid' % (d, len(got)))

    cont = P3.draw_snr(np.random.default_rng(0), (50, 50), 'uniform', grid=False)
    if on_grid(cont, grid):
        fails.append('the grid=False (mainline) path is on the grid -- baseline_sanity would stop '
                     'reproducing the mainline replay')
    print('  4. mainline      grid=False stays continuous (baseline_sanity keeps the mainline protocol)')

    if on_grid(cont, grid):
        fails.append('check 5 cannot bite: the continuous draw passed the support assertion')
    print('  5. bites         a continuous draw fails the support assertion, as it must')

    if fails:
        print('\nP3 SNR SUPPORT GATE FAIL:')
        for f in fails:
            print('  ' + f)
        return 1
    print('P3 SNR SUPPORT GATE PASS: %d distributions, all on the %d-point grid, all sum to 1.'
          % (len(DISTS), len(grid)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
