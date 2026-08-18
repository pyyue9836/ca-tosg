#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R26-2: the delivery-semantics bracket as a product of its own.

The sentence in `sec:collab_scale` that brackets the two delivery semantics -- charge for what is
DELIVERED (B) versus charge for what was REQUESTED (A) -- was bound to
`results/baselines/SCOMCP_FUSE_REPORT.md`, a narrative report about a different arm entirely, which
does not contain its numbers. The values it needs have always existed, inside
`results/sensitivity/collaborator_scale.csv`'s semantics-B rows; they simply had no product of their
own to point at, and the mis-binding went unnoticed because `p6_numbers_vs_csv` only follows
`.csv`/`.json` and skipped the row.

This is a DERIVATION of a committed product, not a new experiment: nothing is re-run, no cache is
touched, and the arithmetic is a per-budget join of the A and B rows.

    python projects/ca_tosg/evaluation/delivery_semantics_bracket.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'results/sensitivity/collaborator_scale.csv')
OUT = os.path.join(ROOT, 'results/sensitivity/delivery_semantics_bracket.csv')


def main() -> int:
    d = pd.read_csv(SRC)
    b = d[d.semantics == 'B']
    if b.empty:
        raise SystemExit('R26-2 FUSE: collaborator_scale.csv carries no semantics-B rows')
    rows = []
    for _, r in b.iterrows():
        a = d[(d.split == r.split) & (d.budget == r.budget) & (d.N == r.N) & (d.semantics == 'A')]
        if len(a) != 1:
            raise SystemExit(f'R26-2 FUSE: {r.split}/{r.budget}/N={r.N} matched {len(a)} A rows')
        a = a.iloc[0]
        rows.append(dict(
            split=r.split, budget=r.budget, N=int(r.N),
            frames_where_semantics_differ=int(r.frames_in_scope),
            F1_requested_semantics_A=float(a.F1), F1_delivered_semantics_B=float(r.F1),
            payload_msym=float(r.payload),                 # identical under A and B: charged on request
            dF_B_minus_A=float(r.dF_vs_A_mean),
            dF_lcb95=float(r.dF_vs_A_lcb95), dF_ucb95=float(r.dF_vs_A_ucb95)))
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False))
    print(f'\nwrote {OUT}')
    print('bracket width (max |dF_B_minus_A|): %.5f over %d rows'
          % (out.dF_B_minus_A.abs().max(), len(out)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
