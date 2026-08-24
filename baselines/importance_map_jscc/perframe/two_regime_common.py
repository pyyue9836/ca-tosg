#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R67-a: the shared two-regime constants and helpers, in one module.

`build_two_regime_edge_clean.py` imported its grid, payloads and interpolation helper *from the
leaky script it exists to replace* -- so the clean arm could not be run, or reasoned about, without
the arm that leaks. The shared pieces live here; the leaky script is deleted.

Nothing is recomputed: these are the same definitions, moved.
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PAY_L, PAY_C = 0.024, 0.99   # channel uses (Msym) at rate-1/2: L=0.024, C=C16=1.98/0.5/4=0.99

SNR_GRID = np.array([0, 4, 8, 12, 16, 20], float)


TAU_GRID = np.round(np.arange(0.0, 20.0001, 0.5), 3)


INTERP_BIAS = 0.0012


def eff_C_of(regime, df, grid, snr, b16=None):
    late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy(); ego = df['ego_f1'].to_numpy()
    if regime == 'jscc':
        return interp_rows(grid, snr)
    return comp * (1 - b16) + ego * b16                    # ldpc, v3 ego fallback


def jscc_grid(channel, split):
    canon = SC.canon_of(split); n = None; cols = []
    for snr in SNR_GRID:
        p = os.path.join(JSCC_DIR, f'jscc_{channel}_{split}_snr{int(snr):02d}.npz')
        pf, m = SC.perframe_f1(p, canon); cols.append(pf); n = m if n is None else min(n, m)
    return np.stack([c[:n] for c in cols], axis=1), n     # (n, 6) per-frame JSCC F1 over the grid
