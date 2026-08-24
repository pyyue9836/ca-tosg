#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R59-1: paired bootstrap intervals for the external-arm cells, at the pre-registered settings.

The R58 tables reported an across-realisation standard deviation. That is a dispersion, not an
interval, and the protocol's own comparison discipline asks for a paired bootstrap: `N_BOOT = 10000`,
`BOOT_SEED = 12345`, percentile method, resampling the unit the two arms are paired on.

Here the pairing unit is the **CSI realisation**: both arms see the same 200 draws, frame by frame,
through the same delivery coin, so a realisation index selects the same channel conditions for both.
Resampling realisations with replacement and taking the difference of means inside each resample is
the paired construction that the stored per-realisation arrays support.

What this is NOT, said plainly: the mainline's R9 interval resamples **frames** and is computed on
frame F1. This one resamples realisations and is computed on AP@0.5, because AP is not a per-frame
quantity — it is defined over a whole split through a global sort. The interval quantifies stability
over channel realisations, conditional on the fixed evaluation set, and does not cover
scene-sampling variability; it must not be cited as the same construction as the frame-level R9
interval.

    python baselines/where2comm_v2/paired_bootstrap.py
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'results', 'diagnostics')
N_BOOT = 10000
BOOT_SEED = 12345


def main() -> int:
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT, 'transport_replay_*.json'))):
        d = json.load(open(f))
        w = np.asarray(d.get('w2c_ap50_per_realisation', []), dtype=float)
        c = np.asarray(d.get('catosg_ap50_per_realisation', []), dtype=float)
        if w.size == 0 or w.size != c.size:
            print(f'SKIP {os.path.basename(f)}: no paired per-realisation arrays '
                  f'(re-run transport_replay.py -- storing only mean and std makes a paired '
                  f'interval impossible after the fact)')
            continue
        diff = w - c
        rng = np.random.default_rng(BOOT_SEED)
        idx = rng.integers(0, diff.size, size=(N_BOOT, diff.size))
        boot = diff[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        rows.append(dict(split=d['split'], budget=d['budget'], mixture=bool(d.get('mixture', False)),
                         realisations=int(d['realisations']),
                         w2c_ap50=round(float(w.mean()), 5), catosg_ap50=round(float(c.mean()), 5),
                         d_ap50=round(float(diff.mean()), 5),
                         ci_lo=round(float(lo), 5), ci_hi=round(float(hi), 5),
                         # R61-3: no `beyond_delta` column. The margin was pre-registered for a
                         # frame-F1 confirmatory comparison; this is a post-hoc AP analysis, and a
                         # column comparing it to delta invites exactly the reading the wording was
                         # corrected to remove.
                         excludes_zero=bool(lo * hi > 0)))
    if not rows:
        print('PAIRED BOOTSTRAP: nothing to do')
        return 1
    df = pd.DataFrame(rows).sort_values(['budget', 'split'])
    p = os.path.join(OUT, 'transport_replay_ci.csv')
    df.to_csv(p, index=False)
    print(df.to_string(index=False))
    print(f'\nN_BOOT={N_BOOT}, BOOT_SEED={BOOT_SEED}, percentile, paired on the CSI realisation.')
    print(f'wrote {os.path.relpath(p, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
