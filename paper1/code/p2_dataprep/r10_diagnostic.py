#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R10 POST-UNBLINDING DIAGNOSTIC. Nothing computed here is confirmatory (PROTOCOL Change-log R10).

No training, no model / delta / tau change, no replay re-run. It only swaps the REFERENCE oracle:
instead of the lambda=0 training oracle (oracle_ELF in the grid), it recomputes a BUDGET-SPECIFIC
oracle per budget using that budget's frozen lambda* (B010 -> 0.05, B020 -> 0.02, B030 -> 0):

    s*_b(cell) = argmax_s ( eff_s - lambda_b * B_s ),  F masked where bler_F >= 0.999.

Then, on the deterministic grid, it (i) classifies every budget-oracle E cell into strict-benefit /
tie-saving / lambda-induced, (ii) accounts the cost of the RF selector NOT picking E where the
budget-oracle does -- separating the ACTUAL perception F1 loss from the EXTRA payload spent -- and
(iii) re-emits the per-class table + re-adjudicates the sec-8 E check against the budget-oracle.

E-cell taxonomy (partitions the cells where the budget-oracle picks E):
  strict-benefit : eff_E > eff_L AND eff_E > eff_F              (ego genuinely best on perception)
  tie-saving     : eff_E == eff_L                               (ties L; only saves payload)
  lambda-induced : eff_E < eff_L but eff_E > eff_L - lambda_b*B_L  (E wins only via L's payload penalty)

Missed-E cost (cells where budget-oracle = E but RF != E), per (split, budget, type):
  F1 cost   = sum(eff_E - eff_rf)   (>0 = RF loses perception F1 vs the oracle's E)
  payload   = sum(B_rf - B_E)       (= sum B_rf, since B_E=0; extra channel-use RF spent)

Outputs (results/p2_deploy/): r10_missed_e_cost.csv, r10_perclass_budgetoracle.csv,
r10_anomaly_readjudication.csv, r10_decision.csv, PROVENANCE_r10.txt.

Run:  /path/to/env/python paper1/code/p2_dataprep/r10_diagnostic.py
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
MANIFEST = os.path.join(P1, 'results/p2_dataprep/FROZEN_MANIFEST.json')
GRID_DIR = os.path.join(P1, 'data/p2')
OUT = os.path.join(P1, 'results/p2_deploy')

ACTIONS = ['E', 'L', 'F']
PAY = {'E': 0.0, 'L': 0.024, 'F': 0.99}
PAYVEC = np.array([PAY[a] for a in ACTIONS])
DATASET = {'validate': 'dataset_validate.csv', 'test': 'dataset_test_v3.csv', 'culver': 'dataset_culver_v3.csv'}
SPLITS = ['validate', 'test', 'culver']
BLER_INFEASIBLE = 0.999
TOL = 1e-9


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def rf_grid_actions(model, feat, grid, cues):
    cue_cols = [c for c in feat if c not in ('est_snr_db', 'channel_is_rayleigh')]
    gcue = grid.merge(cues[['sample_id'] + cue_cols], on='sample_id', how='left')[cue_cols].to_numpy()
    big = np.empty((len(grid), len(feat)))
    big[:, [feat.index(c) for c in cue_cols]] = gcue
    big[:, feat.index('est_snr_db')] = grid['snr_db'].to_numpy(float)
    big[:, feat.index('channel_is_rayleigh')] = (grid['channel'] == 'rayleigh').astype(int).to_numpy()
    return np.asarray(model.predict(big), dtype=int)                # 0/1/2 = E/L/F


def budget_oracle(eff, bler_F, lam):
    util = eff - lam * PAYVEC[None, :]
    util[bler_F >= BLER_INFEASIBLE, 2] = -np.inf
    return util.argmax(1)


def main():
    import pickle
    man = json.load(open(MANIFEST))
    os.makedirs(OUT, exist_ok=True)
    cost_rows, perclass_rows, anom_rows, decision_rows = [], [], [], []

    for split in SPLITS:
        cues = pd.read_csv(os.path.join(DATA, DATASET[split]))
        grid = pd.read_csv(os.path.join(GRID_DIR, f'p2_grid_{split}.csv'))
        eff = grid[['eff_E', 'eff_L', 'eff_F']].to_numpy()
        bF = grid['bler_F'].to_numpy()
        is_ray = (grid['channel'] == 'rayleigh').to_numpy()
        for b, bd in man['budgets'].items():
            lam = float(bd['lambda_star']); bmax = float(b)
            mp = os.path.join(P1, bd['model'])
            if _sha256(mp) != bd['model_sha256']:
                raise SystemExit(f'model sha mismatch {b} -- not the frozen product')
            model = pickle.load(open(mp, 'rb'))
            rf = rf_grid_actions(model, man['feature_names'], grid, cues)   # 0/1/2
            orc = budget_oracle(eff, bF, lam)                              # 0/1/2 budget-specific

            eE, eL, eF = eff[:, 0], eff[:, 1], eff[:, 2]
            is_E = orc == 0
            strict = is_E & (eE > eL + TOL) & (eE > eF + TOL)
            tie = is_E & (np.abs(eE - eL) <= TOL)
            lam_ind = is_E & ~strict & ~tie                              # remaining E cells

            eff_rf = eff[np.arange(len(grid)), rf]
            miss = is_E & (rf != 0)                                       # oracle=E, RF!=E
            for name, mask in (('strict-benefit', strict), ('tie-saving', tie), ('lambda-induced', lam_ind)):
                mm = mask & miss
                n = int(mm.sum())
                f1_cost = float((eE[mm] - eff_rf[mm]).sum())             # >0 = RF loses F1
                pay_extra = float(PAYVEC[rf[mm]].sum())                  # B_rf (B_E=0)
                cost_rows.append(dict(split=split, budget=bmax, e_type=name,
                                      oracle_E_cells=int(mask.sum()), missed_by_rf=n,
                                      F1_cost_sum=round(f1_cost, 6),
                                      F1_cost_per_gridcell=round(f1_cost / len(grid), 8),
                                      payload_extra_sum=round(pay_extra, 4),
                                      payload_extra_per_gridcell=round(pay_extra / len(grid), 6)))

            # per-class RF vs BUDGET-oracle
            from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
            y = np.array(ACTIONS)[orc]; yp = np.array(ACTIONS)[rf]
            p, rc, f, sup = precision_recall_fscore_support(y, yp, labels=ACTIONS, zero_division=0)
            cm = confusion_matrix(y, yp, labels=ACTIONS)
            acc = float((y == yp).mean())
            for i, a in enumerate(ACTIONS):
                perclass_rows.append(dict(split=split, budget=bmax, cls=a, precision=round(float(p[i]), 4),
                                          recall=round(float(rc[i]), 4), f1=round(float(f[i]), 4),
                                          support=int(sup[i]), rf_vs_budgetoracle_acc=round(acc, 4),
                                          confusion_row='|'.join(str(x) for x in cm[i])))
            # sec-8 selE re-adjudication under the budget-oracle (Rayleigh only)
            ray = is_ray
            orcE_ray = float((orc[ray] == 0).mean()); rfE_ray = float((rf[ray] == 0).mean())
            met = not (orcE_ray > 0.05 and rfE_ray < 0.01)
            anom_rows.append(dict(split=split, budget=bmax, lambda_star=lam,
                                  budget_oracle_E_rayleigh=round(orcE_ray, 4),
                                  selector_E_rayleigh=round(rfE_ray, 4),
                                  sec8_selE_met=bool(met),
                                  note=('unchanged from lambda=0' if lam == 0 else 'recomputed at lambda*')))

    cost = pd.DataFrame(cost_rows); cost.to_csv(os.path.join(OUT, 'r10_missed_e_cost.csv'), index=False)
    pd.DataFrame(perclass_rows).to_csv(os.path.join(OUT, 'r10_perclass_budgetoracle.csv'), index=False)
    pd.DataFrame(anom_rows).to_csv(os.path.join(OUT, 'r10_anomaly_readjudication.csv'), index=False)

    # ---- decision draft (POST-UNBLINDING; not confirmatory) ----
    # primary lens = test @ B020: strict-benefit F1 cost per grid cell vs the R9 margin delta=0.005.
    for split in ('test', 'culver'):
        for bmax in (0.10, 0.20, 0.30):
            sub = cost[(cost.split == split) & (cost.budget == bmax)]
            strict_f1 = float(sub[sub.e_type == 'strict-benefit']['F1_cost_per_gridcell'].sum())
            tie_pay = float(sub[sub.e_type == 'tie-saving']['payload_extra_per_gridcell'].sum())
            lam_pay = float(sub[sub.e_type == 'lambda-induced']['payload_extra_per_gridcell'].sum())
            decision_rows.append(dict(split=split, budget=bmax,
                                      strict_benefit_F1_cost_per_cell=round(strict_f1, 8),
                                      tie_saving_payload_per_cell=round(tie_pay, 6),
                                      lambda_induced_payload_per_cell=round(lam_pay, 6),
                                      strict_F1_cost_vs_delta=round(strict_f1 / 0.005, 4)))
    dec = pd.DataFrame(decision_rows); dec.to_csv(os.path.join(OUT, 'r10_decision.csv'), index=False)
    prim = dec[(dec.split == 'test') & (dec.budget == 0.20)].iloc[0]
    strict_negligible = prim['strict_benefit_F1_cost_per_cell'] < 0.0005   # order below delta; a THRESHOLD PROPOSAL

    with open(os.path.join(OUT, 'PROVENANCE_r10.txt'), 'w') as f:
        f.write('CA-TOSG R10 -- POST-UNBLINDING DIAGNOSTIC (nothing here is confirmatory)\n' + '=' * 72 + '\n')
        f.write('No training / no model,delta,tau change / no replay re-run. Reference oracle swapped '
                'to the budget-specific lambda*: B010=0.05, B020=0.02, B030=0.\n')
        f.write('E-cell taxonomy: strict-benefit (eff_E>eff_L & >eff_F) / tie-saving (eff_E==eff_L) / '
                'lambda-induced (eff_E<eff_L but eff_E>eff_L-lambda*B_L).\n\n')
        f.write('PRIMARY lens test@B020: strict-benefit missed-E F1 cost per grid cell = '
                f'{prim["strict_benefit_F1_cost_per_cell"]:.6f} '
                f'(= {prim["strict_F1_cost_vs_delta"]:.3f} x delta).\n')
        f.write('DECISION DRAFT (post-unblinding; pending Peiyi Yue + supervisor confirmation):\n')
        if strict_negligible:
            f.write('  strict-benefit E F1 cost is NEGLIGIBLE (< 0.0005/cell, an order below delta) -> the '
                    'E-collapse costs mostly PAYLOAD, not F1. Proposed: keep the frozen models, run 6d as a '
                    'DESCRIPTIVE AP table, and report honestly that "E was learned mainly as a bandwidth-'
                    'saving action and is under-used by the selector" -- the R9 F1 result is unaffected.\n')
        else:
            f.write('  strict-benefit E flow-through causes a SUBSTANTIVE F1 loss -> repair route: '
                    'demote test/Culver to development-diagnostic sets and require NEW independent data for '
                    'final confirmation. (Repair itself needs a new pre-registered decision -- not taken here.)\n')
        f.write('\nsec-8 selE re-adjudication (budget-oracle): B030 unchanged (lambda=0); B010/B020 '
                'recomputed -- numbers in r10_anomaly_readjudication.csv.\n')
        f.write('ROOT-CAUSE CORRECTION: B010/B020 balanced candidates were attempted and walked past for '
                'exceeding the frozen budget; B030 balanced was NEVER tested -- its cw=None winner cand#56 '
                'passed at walk rank 0, so the walk stopped before any balanced candidate was reached.\n')

    print('R10 diagnostic written -> results/p2_deploy/r10_*.csv + PROVENANCE_r10.txt')
    print(dec.to_string(index=False))
    print('\nsec-8 selE re-adjudication:')
    print(pd.DataFrame(anom_rows).to_string(index=False))


if __name__ == '__main__':
    main()
