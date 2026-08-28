#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R25 F-1 — build the v2 oracle/feasibility grid. Zero GPU.

Protocol §9.3. One row per (frame, SNR, channel): the realised utility of each action and the payload
it costs. This is the layer the selector is fitted against, so every column below traces to a locked
clause rather than to a convenience.

    p          = bler_cw(16-QAM, channel, SNR) from the Sionna table -- per-CODEWORD loss probability
    eff_E      = the ego-only F1 (WP3). No message, so the channel cannot touch it.
    eff_L      = q_L * f1_L + (1 - q_L) * f1_E,   q_L = (1 - p)^{N_cw,L,t}
    eff_F      = the §9.3(b) interpolation of WP5's `ideal` partial-recovery F1 at p
    B_{t,E}    = 0
    B_{t,L}    = B_{L,t}   (per frame, §4.2)
    B_{t,F}    = 3.14175 Msym (§3.2)

WHY L AND F ARE TREATED DIFFERENTLY, WITH THE PROTOCOL'S OWN WORDS
-------------------------------------------------------------------
F is **partial recovery**: WP5 already simulated fragment-aware reconstruction at each p, so the
interpolated F1 *is* the realised utility -- multiplying it by a delivery probability would charge
the loss twice.

L is **message-level**. §4.3: *"L has a genuine physical-layer delivery probability, and a failed
delivery falls back to ego-only exactly as F's does."* A box list is not fragment-recoverable the way
a feature tensor is, so L is delivered or it is not. **This is a reading of §4.3 and it is flagged as
one**: it is the one place in this module where the protocol admits more than one implementation, and
it is recorded here rather than settled silently.

PAYLOAD IS CHARGED FOR THE ATTEMPT (§9.3(j))
---------------------------------------------
`B_{t,a}` is NOT multiplied by the success probability. A failed delivery does not refund the symbols
already spent. This module and §9.3(j) are a reconciliation pair.

    python projects/ca_tosg/evaluation/v2_build_grid.py --split validate
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
V2 = os.path.join(ROOT, 'results', 'v2')

from projects.ca_tosg.models.v2_eff_f import eff_f, load_nodes, self_check   # noqa: E402

QAM = 16
N_CW_F = 12567          # §3.2
B_F = 3.14175           # Msym, §3.2
BLER_INFEASIBLE = 0.999


def bler_lookup(bler, channels, snrs):
    """Per-codeword BLER at (16-QAM, channel, SNR), EXACT points only, with one narrow exception.

    The Sionna sweep does not carry AWGN at 14 and 18 dB. Those two are bracketed by entries that are
    **exactly equal** (10/12/16/20 dB all read 0.00000), so filling them is arithmetic, not a model:
    a value bracketed by two identical values can only be that value.

    Anything else raises. In particular a point in the steep part of the curve is NEVER interpolated
    -- AWGN 16-QAM falls from 0.7465 to 0.0410 between 6 and 7 dB, and a linear fill there would
    invent a number that looks plausible and is not measured. **The rule is "fill only where the fill
    is forced", not "interpolate where convenient".**
    """
    out = np.empty(len(channels), float)
    for ch in np.unique(channels):
        t = bler[(bler.qam == QAM) & (bler.channel == ch)].sort_values('esno_db')
        x, y = t.esno_db.to_numpy(float), t.bler_cw.to_numpy(float)
        m = channels == ch
        for s in np.unique(snrs[m]):
            hit = np.isclose(x, s)
            if hit.any():
                v = float(y[hit][0])
            else:
                j = np.searchsorted(x, s)
                if j == 0 or j >= len(x):
                    raise SystemExit(f'BLER: {ch} {s} dB is outside the swept range')
                lo, hi = y[j - 1], y[j]
                if lo != hi:
                    raise SystemExit(
                        f'BLER: {ch} {s} dB is not measured and its neighbours differ '
                        f'({x[j-1]} dB -> {lo}, {x[j]} dB -> {hi}); refusing to interpolate in a '
                        f'region where the fill would not be forced')
                v = float(lo)
            out[m & (snrs == s)] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate')
    ap.add_argument('--regime', default='ideal', choices=['ideal', 'packet'])
    args = ap.parse_args()

    wp34 = pd.read_csv(os.path.join(V2, f'wp34_e_l_{args.split}.csv'))
    wp2 = pd.read_csv(os.path.join(V2, f'wp2_per_agent_{args.split}.csv'))
    cues = pd.read_csv(os.path.join(V2, f'wp6_cues_{args.split}.csv'))
    bler = pd.read_csv(os.path.join(ROOT, 'results/channel/bler_sionna.csv'))
    old_grid = pd.read_csv(os.path.join(ROOT, 'data/p2/p2_grid_validate.csv'))

    frames, p_nodes, F = load_nodes(args.split, args.regime)
    sc = self_check(p_nodes, F)
    if sc:
        raise SystemExit('§9.3 interpolation self-check FAILED -- refusing to build:\n  '
                         + '\n  '.join(sc))
    print(f'§9.3 interpolation self-check: PASS ({len(p_nodes)} nodes, {F.shape[0]} frames)')

    for name, df in (('wp34', wp34), ('wp2', wp2), ('cues', cues)):
        if not np.array_equal(df.frame.to_numpy(), frames):
            raise SystemExit(f'{name} frame vector differs from WP5 -- refusing to join by row')

    # the SNR x channel support is carried over from v1 unchanged (11 SNR x 2 channels)
    pts = old_grid[['sample_id', 'scene', 'snr_db', 'channel']].copy()
    p = bler_lookup(bler, pts.channel.to_numpy(), pts.snr_db.to_numpy().astype(float))
    pts['bler_cw'] = p

    # per-frame quantities, expanded onto the grid rows
    fi = pts.sample_id.to_numpy()
    f1_E = wp34.f1_E.to_numpy()[fi]
    f1_L = wp34.f1_L.to_numpy()[fi]
    n_cw_L = wp34.n_cw_L.to_numpy()[fi]
    B_L_t = wp34.B_L_msym.to_numpy()[fi]
    has_collab = cues.has_collaborator.to_numpy()[fi]

    q_L = (1.0 - p) ** n_cw_L                      # §4.3, message-level for L
    eff_E = f1_E
    eff_L = q_L * f1_L + (1.0 - q_L) * f1_E
    eff_F = eff_f(p, p_nodes, F[fi])               # §9.3(b), partial recovery already in the nodes
    bler_F = 1.0 - (1.0 - p) ** N_CW_F

    # §9.3(k): with no collaborator nothing is received and nothing is charged
    no = has_collab == 0
    eff_L = np.where(no, f1_E, eff_L)
    eff_F = np.where(no, f1_E, eff_F)
    B_L_row = np.where(no, 0.0, B_L_t)
    B_F_row = np.where(no, 0.0, B_F)

    out = pd.DataFrame({
        'sample_id': fi, 'scene': pts.scene.to_numpy(),
        'snr_db': pts.snr_db.to_numpy(), 'channel': pts.channel.to_numpy(),
        'p_cw': p, 'bler_F': bler_F, 'q_L': q_L, 'has_collaborator': has_collab,
        'eff_E': eff_E, 'eff_L': eff_L, 'eff_F': eff_F,
        'B_E': 0.0, 'B_L': B_L_row, 'B_F': B_F_row,
    })
    csv = os.path.join(V2, f'v2_grid_{args.split}_{args.regime}.csv')
    out.to_csv(csv, index=False)

    meta = {
        'schema': 'catosg-v2-grid/1', 'split': args.split, 'regime': args.regime,
        'rows': int(len(out)), 'frames': int(out.sample_id.nunique()),
        'snr_points': sorted(int(x) for x in out.snr_db.unique()),
        'channels': sorted(out.channel.unique()),
        'protocol': '§9.3 (a)-(n)',
        'eff_F': 'piecewise-linear in RAW p over the replicate means of WP5 `%s`; endpoints are the '
                 'clean and all-lost measurements; no monotone correction' % args.regime,
        'eff_L': 'q_L*f1_L + (1-q_L)*f1_E with q_L = (1-p)^N_cw,L -- message level, per §4.3 '
                 '"a failed delivery falls back to ego-only". FLAGGED as a reading: it is the one '
                 'place this module resolves an ambiguity in the protocol text.',
        'payload': 'charged for the ATTEMPT, never multiplied by the success probability (§9.3(j))',
        'B_F_msym': B_F, 'N_cw_F': N_CW_F, 'bler_infeasible': BLER_INFEASIBLE,
        'no_collaborator_rows': int(no.sum()),
        'mainline': args.regime == 'ideal',
    }
    with open(os.path.join(V2, f'v2_grid_{args.split}_{args.regime}.json'), 'w') as f:
        json.dump(meta, f, indent=1)

    print(f'\nv2 grid [{args.regime}]: {len(out)} rows = {out.sample_id.nunique()} frames x '
          f'{len(meta["snr_points"])} SNR x {len(meta["channels"])} channels')
    print(f'  p_cw            {p.min():.3e} .. {p.max():.3e}')
    print(f'  bler_F          {bler_F.min():.3e} .. {bler_F.max():.3e}   '
          f'infeasible (>= {BLER_INFEASIBLE}) on {(bler_F >= BLER_INFEASIBLE).sum()} rows '
          f'({(bler_F >= BLER_INFEASIBLE).mean() * 100:.1f} %)')
    print(f'  eff_E mean      {eff_E.mean():.5f}')
    print(f'  eff_L mean      {eff_L.mean():.5f}')
    print(f'  eff_F mean      {eff_F.mean():.5f}')
    print(f'  B_L mean        {B_L_row.mean():.5f} Msym   B_F {B_F} Msym')
    print(f'wrote {os.path.relpath(csv, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
