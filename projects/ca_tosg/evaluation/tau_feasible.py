#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R18-3: the strictly-matched SNR-threshold comparator, τ_feasible.

Pre-registered in `docs/experiment_protocol.md`, Change-log R18-3, before this file existed.

`pick_tau` selects τ* on the deterministic grid subject to `pay <= B_max`, but the deployed
comparison reports the mean payload over the 200-realisation replay -- and there τ* is **over
budget** at B_max = 0.20 and 0.30 on every split, so every payload reduction quoted against it is
flattered by the overspend.

τ_feasible is the **F1-maximising** τ on the same grid whose **replay-mean** payload fits the budget.
Fitted on **validate only**, applied unchanged to test and Culver-City.

AMENDMENT, and when it was made. The pre-registration said "the largest feasible τ", on the reasoning
that the largest is the cheapest admissible comparator. That rule is **degenerate**: payload falls
monotonically in τ, so the largest τ always fits and spends nothing -- it selected τ = 20.5 (above the
20 dB draw range) at all three budgets, reproducing Fixed-L exactly (payload 0.024 = B_L, F1 = Fixed-L
F1) and yielding "reductions" like -489%. The amendment was written **after seeing that**, and keeps
`pick_tau`'s own objective (maximise F1) while moving only the CONSTRAINT from the deterministic grid
to the replay distribution -- which is the defect being fixed. It does not tune toward any outcome:
the objective is the incumbent one and the constraint is the stricter one. The degenerate choice is
recorded per budget in the manifest rather than discarded.

Secondary by construction: R9 is not re-taken against it, and nominal τ* stays in every table.

Every draw reuses `deployment.py` -- the same `CSI_SEED`, the same `rng` call order, the same
`eff_matrix`, `tau_actions`, `bler16` and `PAYVEC`. Re-implementing the replay here would let the
two drift apart, which is the whole reason the deployed comparison is trusted.

    python projects/ca_tosg/evaluation/tau_feasible.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils', 'projects/ca_tosg/models'):
    sys.path.insert(0, os.path.join(ROOT, _d))
sys.path.insert(0, ROOT)

import deployment as D  # noqa: E402

OUT = os.path.join(ROOT, 'results/main/tau_feasible.csv')
PROV = os.path.join(ROOT, 'results/provenance/PROVENANCE_tau_feasible.txt')
MANIFEST = os.path.join(ROOT, 'results/manifests/TAU_FEASIBLE_MANIFEST.json')
TAU_GRID = np.round(np.arange(0.0, 20.0 + 1e-9, 0.5), 3)   # capped at the SNR range:
#   tau=20.5 is unreachable by a U[0,20] draw, so it silently means 'never send F'


def replay_for_split(split, tbl):
    """The deployed draw for one split: (ds, eff-per-realisation, snr_2d, is_ray_2d)."""
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
    n = len(ds)
    ego = ds['ego_f1'].to_numpy()
    late = ds['late_f1'].to_numpy()
    comp = ds['compressed_f1'].to_numpy()
    rng = np.random.default_rng(D.CSI_SEED)                 # identical seed and call order
    snr_2d = rng.uniform(0, 20, size=(D.N_REPLAY, n))
    is_ray_2d = rng.random(size=(D.N_REPLAY, n)) < 0.5
    bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(D.N_REPLAY)])
    E = [D.eff_matrix(ego, late, comp, bF_2d[r]) for r in range(D.N_REPLAY)]
    return ds, E, snr_2d, is_ray_2d


def score_tau(ds, E, snr_2d, is_ray_2d, tau):
    """Mean F1 and mean payload of `F if (AWGN and snr>tau) else L`, over the 200 draws."""
    n = len(ds)
    idx = D.tau_actions(snr_2d, is_ray_2d, float(tau))
    f1 = np.array([E[r][np.arange(n), idx[r]].mean() for r in range(D.N_REPLAY)])
    pay = np.array([D.PAYVEC[idx[r]].mean() for r in range(D.N_REPLAY)])
    return float(f1.mean()), float(pay.mean())


def main() -> int:
    tbl = pd.read_csv(D.BLER_CSV)
    frozen = json.load(open(os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')))['budgets']
    print('fitting tau_feasible on validate over the 200-replay distribution')
    ds_v, E_v, snr_v, ray_v = replay_for_split('validate', tbl)
    curve = [(float(t), *score_tau(ds_v, E_v, snr_v, ray_v, t)) for t in TAU_GRID]

    chosen = {}
    for tag in sorted(frozen):
        bmax = float(tag)
        feasible = [(t, f1, pay) for t, f1, pay in curve if pay <= bmax]
        nom = frozen[tag]['tau_star']
        if not feasible:
            print(f'  B_max={bmax:.2f}: no grid tau fits the replay-mean budget')
            chosen[tag] = None
            continue
        t_cheap, f1_cheap, pay_cheap = max(feasible, key=lambda x: x[0])
        t, f1, pay = max(feasible, key=lambda x: x[1])        # AMENDED: F1-maximising, budget-feasible
        chosen[tag] = dict(tau_feasible=t, validate_f1=round(f1, 5), validate_payload=round(pay, 5),
                           tau_nominal=nom,
                           degenerate_largest_tau=t_cheap,
                           degenerate_payload=round(pay_cheap, 5),
                           degenerate_note=('the pre-registered "largest feasible tau" rule is '
                                            'degenerate: payload is monotone decreasing in tau, so '
                                            'the largest tau always fits and reproduces Fixed-L '
                                            '(payload = B_L, F1 = Fixed-L F1)'))
        print(f'  B_max={bmax:.2f}: nominal tau*={nom} -> tau_feasible={t} '
              f'(validate F1 {f1:.5f}, payload {pay:.5f} <= {bmax})')

    rows = []
    for split in D.SPLITS:
        ds, E, snr, ray = replay_for_split(split, tbl)
        rep = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
        for tag in sorted(frozen):
            if chosen[tag] is None:
                continue
            bmax = float(tag)
            tf = chosen[tag]['tau_feasible']
            f1_f, pay_f = score_tau(ds, E, snr, ray, tf)
            f1_n, pay_n = score_tau(ds, E, snr, ray, chosen[tag]['tau_nominal'])
            r = rep[(rep.split == split) & (rep.budget == bmax)].iloc[0]
            rows.append(dict(
                split=split, budget=bmax,
                tau_nominal=chosen[tag]['tau_nominal'], tau_feasible=tf,
                F1_RF=round(float(r.F1_RF), 5),
                F1_tau_nominal=round(f1_n, 5), F1_tau_feasible=round(f1_f, 5),
                B_RF=round(float(r.B_RF), 5),
                B_tau_nominal=round(pay_n, 5), B_tau_feasible=round(pay_f, 5),
                nominal_over_budget=round(pay_n - bmax, 5),
                feasible_over_budget=round(pay_f - bmax, 5),
                dF_vs_feasible=round(float(r.F1_RF) - f1_f, 5),
                dB_vs_feasible=round(float(r.B_RF) - pay_f, 5),
                payload_reduction_vs_nominal=round(1 - float(r.B_RF) / pay_n, 5),
                payload_reduction_vs_feasible=round(1 - float(r.B_RF) / pay_f, 5)))
            print(f'  [{split} B{bmax:.2f}] RF F1 {r.F1_RF:.5f} pay {r.B_RF:.5f} | '
                  f'tau_nom F1 {f1_n:.5f} pay {pay_n:.5f} (over {pay_n - bmax:+.5f}) | '
                  f'tau_feas F1 {f1_f:.5f} pay {pay_f:.5f} | '
                  f'reduction {100 * (1 - float(r.B_RF) / pay_n):.1f}% -> '
                  f'{100 * (1 - float(r.B_RF) / pay_f):.1f}%')
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    with open(PROV, 'w') as f:
        f.write('CA-TOSG R18-3 -- tau_feasible, strictly-matched SECONDARY comparator.\n')
        f.write(f'generated: {datetime.now(timezone.utc).isoformat()}\n')
        f.write('rule (AMENDED after the pre-registered one proved degenerate): the F1-MAXIMISING '
                'grid tau whose 200-replay MEAN payload <= B_max, fitted on validate only, applied '
                'unchanged to test/culver.\n')
        f.write('the pre-registered "largest feasible tau" selected tau=20.5 (above the 20 dB draw '
                'range) at every budget, i.e. never send F -- it reproduced Fixed-L. Recorded per '
                'budget in TAU_FEASIBLE_MANIFEST.json under degenerate_largest_tau.\n')
        f.write(f'tau grid: {TAU_GRID[0]}..{TAU_GRID[-1]} step 0.5; CSI_SEED={D.CSI_SEED}, '
                f'N_REPLAY={D.N_REPLAY} -- the deployed draw, reused from deployment.py.\n')
        f.write('SECONDARY: R9 is NOT re-taken against this comparator. Nominal tau* stays in every '
                'table beside it, because that is what the pre-registered decision used.\n')
        f.write('DISCLOSURE REQUIRED: any payload reduction quoted against nominal tau* must state '
                'in the same sentence that nominal tau* is over budget where it is.\n')
    json.dump(dict(schema='catosg-tau-feasible/1', fitted_on='validate',
                   applied_to=['test', 'culver'], tau_grid=[float(TAU_GRID[0]), float(TAU_GRID[-1]),
                                                            0.5],
                   csi_seed=D.CSI_SEED, n_replay=D.N_REPLAY, chosen=chosen,
                   rows=rows), open(MANIFEST, 'w'), indent=2)
    print(f'\nwrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
