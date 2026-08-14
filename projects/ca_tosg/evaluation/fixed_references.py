#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-7 (A): the fixed-policy reference rows, under the FROZEN replay's own CSI draw.

`replay_summary.csv` carries only the two learned policies (RF and tau). The reference rows that
sit beside them in Tables IV and VIII -- Fixed L, Fixed F, Fixed C256 and the channel-aware oracle
-- came from the retired engine, so a table containing both was mixing engines.

Everything here is computed with the SAME machinery as `deployment.py`: the same generator, the
same seed, the same call order, the same `eff_matrix`, the same feasibility mask. Nothing is
re-implemented except one thing, and that one thing is asserted:

  `bler_q` generalises `deployment.bler16` to an arbitrary QAM order (C256 needs qam=256, which the
  deployed helper hard-codes away). It must return values IDENTICAL to `deployment.bler16` at
  qam=16, or the C256 row would not be comparable to the F row -- checked at run time, and the run
  stops if it ever differs.

The clairvoyant upper bound is deliberately NOT produced: the legacy one sampled the per-frame
block outcome post hoc under the retired engine, and there is no frozen definition of it. Inventing
one here would be exactly the substitution this batch exists to remove.

    python projects/ca_tosg/evaluation/fixed_references.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import os as _o, sys as _s                                                        # noqa: E401
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils'):
    _s.path.insert(0, _o.path.join(_o.path.abspath(_o.path.join(HERE, '..', '..', '..')), _d))

import deployment as D                                                            # noqa: E402

OUT_CSV = os.path.join(D.OUT, 'fixed_references.csv')
PROV = os.path.join(D.PROV_DIR, 'PROVENANCE_fixed_references.txt')
BLER_INFEASIBLE = 0.999          # PROTOCOL sec 4, same constant as grid_builder
PAY_C256 = 0.495                 # Eq.(7): 3.96 Mbit coded / 8 bit-per-symbol


def bler_q(tbl, snr, channel, qam):
    """deployment.bler16, generalised over the QAM order. Same interpolation, same edge rules."""
    out = np.empty_like(snr, dtype=float)
    for ch, name in ((True, 'rayleigh'), (False, 'awgn')):
        m = channel == ch
        if m.any():
            s = tbl[(tbl['qam'] == qam) & (tbl['channel'] == name)].sort_values('esno_db')
            out[m] = np.clip(np.interp(snr[m], s['esno_db'], s['bler_frame'],
                                       left=1.0, right=float(s['bler_frame'].iloc[-1])), 0, 1)
    return out


def main() -> int:
    tbl = pd.read_csv(D.BLER_CSV)
    rows, prov = [], []
    for split in D.SPLITS:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        ego = ds['ego_f1'].to_numpy()
        late = ds['late_f1'].to_numpy()
        comp = ds['compressed_f1'].to_numpy()

        # the frozen draw: same generator, same seed, same order as deployment.main()
        rng = np.random.default_rng(D.CSI_SEED)
        snr_2d = rng.uniform(0, 20, size=(D.N_REPLAY, n))
        is_ray_2d = rng.random(size=(D.N_REPLAY, n)) < 0.5

        f1 = {k: np.empty(D.N_REPLAY) for k in ('L', 'F', 'C256', 'oracle')}
        pay = {k: np.empty(D.N_REPLAY) for k in ('oracle',)}
        for r in range(D.N_REPLAY):
            bF = D.bler16(tbl, snr_2d[r], is_ray_2d[r])
            b16_check = bler_q(tbl, snr_2d[r], is_ray_2d[r], 16)
            assert np.array_equal(bF, b16_check), (
                'bler_q(qam=16) does not reproduce deployment.bler16 -- the C256 row would not be '
                'comparable to the F row; refusing to continue'
            )
            b256 = bler_q(tbl, snr_2d[r], is_ray_2d[r], 256)

            eff = D.eff_matrix(ego, late, comp, bF)            # (n,3) for [E, L, F]
            f1['L'][r] = eff[:, 1].mean()
            f1['F'][r] = eff[:, 2].mean()
            f1['C256'][r] = (comp * (1 - b256) + ego * b256).mean()

            masked = eff.copy()
            masked[bF >= BLER_INFEASIBLE, 2] = -np.inf         # PROTOCOL sec 4, as in grid_builder
            idx = masked.argmax(1)                             # ties -> E, then L
            f1['oracle'][r] = eff[np.arange(n), idx].mean()
            pay['oracle'][r] = D.PAYVEC[idx].mean()

        for policy, payload in (('Fixed-L', D.PAY['L']), ('Fixed-F', D.PAY['F']),
                                ('Fixed-C256', PAY_C256), ('oracle', None)):
            key = {'Fixed-L': 'L', 'Fixed-F': 'F', 'Fixed-C256': 'C256', 'oracle': 'oracle'}[policy]
            p = pay['oracle'].mean() if payload is None else payload
            rows.append(dict(split=split, policy=policy,
                             F1=round(float(f1[key].mean()), 5),
                             F1_std=round(float(f1[key].std()), 5),
                             payload_msym=round(float(p), 5),
                             n_realisations=D.N_REPLAY))
        prov.append((split, n))

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    with open(PROV, 'w') as f:
        f.write('CA-TOSG P5-7 (A) -- fixed-policy references under the FROZEN replay draw.\n'
                + '=' * 78 + '\n')
        f.write(f'CSI: {D.N_REPLAY} samplings/split, seed={D.CSI_SEED}, SNR~U[0,20], '
                f'channel~Bernoulli(0.5 Rayleigh) -- the SAME generator/seed/order as deployment.py\n')
        f.write(f'eff: deployment.eff_matrix (imported). Mask: BLER_F >= {BLER_INFEASIBLE} removes F '
                f'from the oracle argmax (PROTOCOL sec 4), ties -> E then L.\n')
        f.write('C256: bler_q(qam=256) on the same committed BLER table; bler_q(qam=16) asserted '
                'equal to deployment.bler16 on every realisation.\n')
        f.write('NOT PRODUCED: the clairvoyant upper bound. Its legacy definition sampled the '
                'per-frame block outcome post hoc under the retired engine; there is no frozen\n'
                '  definition, and inventing one here is exactly the substitution this batch '
                'removes.\n')
        for split, n in prov:
            f.write(f'  {split}: {n} frames\n')
    print(df.to_string(index=False))
    print(f'\nwrote {OUT_CSV}\n      {PROV}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
