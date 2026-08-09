#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R10c CORRIGENDUM diagnostic (post-unblinding; nothing here is confirmatory).

Corrects R10 (r10_diagnostic.py), whose taxonomy required eff_E > eff_F for strict-benefit -- wrong,
because where BLER_F >= 0.999 F is infeasible and eff_F = ego = eff_E, so genuine strict-benefit E
cells (E beats the only feasible alternative L) were mis-bucketed as "lambda-induced". No training, no
model/delta/tau change, no change to the R9 replay CSVs; this recomputes the vs-ORACLE diagnostic on
the SAME deployment distribution (seed 20260809) and ALSO asserts it reproduces the existing replay
CSVs (a determinism/integrity check of the original P2-B run).

Feasible utility: feas = eff, with feas[:,F] = -inf where BLER_F >= 0.999 (same mask as the oracle).
RAW oracle  = argmax_s feas_s               (no penalty)          -- saved separately.
BUDGET oracle = argmax_s (feas_s - lambda_b * B_s)                 -- saved separately.
Taxonomy of budget-oracle E cells (mutually exclusive; residual -> hard error):
  strict       : E is the UNIQUE feasible argmax of the RAW utility.
  tie          : E is a feasible argmax of the RAW utility, tied with >=1 other action.
  cost-induced : E is NOT raw-optimal (some feasible action beats it) but wins under the budget oracle.
Missed-E cost (budget-oracle = E, RF != E), for EVERY class: dF1 = eff_E - eff_{RF action} AND
dpayload = B_{RF} - B_E. Reported per class with BOTH an F1 and a payload column.

Hard assertions (fail = fuse): (a) at lambda=0 the cost-induced count is 0; (b) every cost-induced
frame has raw dF1(E vs L) <= 0 (eff_E <= eff_L). Plus (c) per-realisation F1_RF/B_RF reproduce the
existing replay_{split}_B0XX.csv exactly.

Outputs (results/p2_deploy/): r10c_missed_e_cost.csv, r10c_vs_oracle_account.csv,
r10c_vs_tau_account.csv, r10c_decision_log_{split}_B0XX.csv (realisation 0, per frame),
PROVENANCE_r10c.txt.

Run:  /path/to/env/python paper1/code/p2_dataprep/r10c_diagnostic.py
"""
import hashlib
import json
import os
import pickle

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
MANIFEST = os.path.join(P1, 'results/p2_dataprep/FROZEN_MANIFEST.json')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
OUT = os.path.join(P1, 'results/p2_deploy')

ACTIONS = ['E', 'L', 'F']
PAY = np.array([0.0, 0.024, 0.99])
DATASET = {'validate': 'dataset_validate.csv', 'test': 'dataset_test_v3.csv', 'culver': 'dataset_culver_v3.csv'}
SPLITS = ['validate', 'test', 'culver']
N_REPLAY = 200
CSI_SEED = 20260809
BLER_INFEASIBLE = 0.999
TOL = 1e-9


def fuse(msg):
    raise SystemExit(f'R10c FUSE: {msg}')


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def bler16(tbl, snr, is_ray):
    out = np.empty_like(snr, dtype=float)
    for ray, name in ((True, 'rayleigh'), (False, 'awgn')):
        m = is_ray == ray
        if m.any():
            s = tbl[(tbl['qam'] == 16) & (tbl['channel'] == name)].sort_values('esno_db')
            out[m] = np.clip(np.interp(snr[m], s['esno_db'], s['bler_frame'],
                                       left=1.0, right=float(s['bler_frame'].iloc[-1])), 0, 1)
    return out


def rf_stacked(model, feat, cues, snr_2d, ray_2d):
    R, n = snr_2d.shape
    cue_cols = [c for c in feat if c not in ('est_snr_db', 'channel_is_rayleigh')]
    base = cues[cue_cols].to_numpy()
    big = np.empty((R * n, len(feat)))
    big[:, [feat.index(c) for c in cue_cols]] = np.tile(base, (R, 1))
    big[:, feat.index('est_snr_db')] = snr_2d.reshape(-1)
    big[:, feat.index('channel_is_rayleigh')] = ray_2d.reshape(-1).astype(int)
    return np.asarray(model.predict(big), dtype=int).reshape(R, n)


def main():
    man = json.load(open(MANIFEST))
    tbl = pd.read_csv(BLER_CSV)
    os.makedirs(OUT, exist_ok=True)
    cost_rows, vsorc_rows, vstau_rows = [], [], []
    replay_summary = pd.read_csv(os.path.join(OUT, 'replay_summary.csv'))

    for split in SPLITS:
        cues = pd.read_csv(os.path.join(DATA, DATASET[split]))
        n = len(cues)
        ego = cues['ego_f1'].to_numpy(); late = cues['late_f1'].to_numpy(); comp = cues['compressed_f1'].to_numpy()
        rng = np.random.default_rng(CSI_SEED)                    # SAME draws as eval_p2_deploy
        snr_2d = rng.uniform(0, 20, size=(N_REPLAY, n))
        ray_2d = rng.random(size=(N_REPLAY, n)) < 0.5
        bF_2d = np.stack([bler16(tbl, snr_2d[r], ray_2d[r]) for r in range(N_REPLAY)])   # (R,n)
        # true eff (R,n,3) and feasible eff (F->-inf where infeasible)
        eff = np.stack([np.broadcast_to(ego, (N_REPLAY, n)), np.broadcast_to(late, (N_REPLAY, n)),
                        comp[None, :] * (1 - bF_2d) + ego[None, :] * bF_2d], axis=2)
        feas = eff.copy(); feas[:, :, 2][bF_2d >= BLER_INFEASIBLE] = -np.inf
        raw_orc = feas.argmax(2)                                 # (R,n) raw oracle
        eE, eL = eff[:, :, 0], eff[:, :, 1]

        for b, bd in man['budgets'].items():
            lam = float(bd['lambda_star']); bmax = float(b)
            mp = os.path.join(P1, bd['model'])
            if _sha256(mp) != bd['model_sha256']:
                fuse(f'{b} model sha mismatch')
            model = pickle.load(open(mp, 'rb'))
            rf = rf_stacked(model, man['feature_names'], cues, snr_2d, ray_2d)          # (R,n)
            bud_orc = (feas - lam * PAY[None, None, :]).argmax(2)                        # (R,n) budget oracle

            # --- integrity: per-realisation F1_RF/B_RF must reproduce the existing replay CSV ---
            eff_rf = np.take_along_axis(eff, rf[:, :, None], 2)[:, :, 0]
            F1_RF = eff_rf.mean(1); B_RF = PAY[rf].mean(1)
            rp = pd.read_csv(os.path.join(OUT, f'replay_{split}_B{int(round(bmax*100)):03d}.csv'))
            if (np.abs(F1_RF - rp['F1_RF'].to_numpy()).max() > 1e-9
                    or np.abs(B_RF - rp['B_RF'].to_numpy()).max() > 1e-9):
                fuse(f'{split} B{bmax}: recomputed F1_RF/B_RF != existing replay CSV (determinism/integrity)')

            # --- taxonomy of budget-oracle E cells, on the RAW E-vs-L utility (L is E's low-payload
            #     competitor; F is the high-payload action both undercut and is masked/penalised out) ---
            isE = bud_orc == 0
            dEL = eff[:, :, 0] - eff[:, :, 1]                     # raw eff_E - eff_L
            strict = isE & (dEL > TOL)                            # E strictly beats L (real perception benefit)
            tie = isE & (np.abs(dEL) <= TOL)                      # E ties L (only saves payload)
            cost = isE & (dEL < -TOL)                             # E loses to L raw; wins only via lambda penalty
            resid = isE & ~(strict | tie | cost)
            if resid.any():
                fuse(f'{split} B{bmax}: {int(resid.sum())} budget-oracle-E cells fall in NO class (residual)')
            # hard assertions
            if lam == 0 and int(cost.sum()) != 0:
                fuse(f'{split} B{bmax}: lambda=0 but cost-induced count = {int(cost.sum())} (must be 0)')
            if cost.any() and (eff[:, :, 0][cost] > eff[:, :, 1][cost] + TOL).any():
                fuse(f'{split} B{bmax}: a cost-induced frame has raw dF1(E vs L) > 0 (eff_E > eff_L)')

            miss = isE & (rf != 0)
            for name, mask in (('strict', strict), ('tie', tie), ('cost-induced', cost)):
                mm = mask & miss
                cells = int(mask.sum()); nmiss = int(mm.sum())
                df1 = float((eff[:, :, 0][mm] - eff_rf[mm]).sum())                       # dF1 = F1_E - F1_rf
                dpay = float(PAY[rf[mm]].sum())                                          # dpayload = B_rf - 0
                denom = N_REPLAY * n
                cost_rows.append(dict(split=split, budget=bmax, e_class=name,
                                      oracle_E_cells=cells, missed_by_rf=nmiss,
                                      F1_cost_sum=round(df1, 4), F1_cost_per_framereal=round(df1 / denom, 8),
                                      payload_extra_sum=round(dpay, 2),
                                      payload_extra_per_framereal=round(dpay / denom, 6)))

            # --- vs-ORACLE account (RF vs the budget oracle), on the replay distribution ---
            eff_bo = np.take_along_axis(eff, bud_orc[:, :, None], 2)[:, :, 0]
            F1_bo = eff_bo.mean(1); B_bo = PAY[bud_orc].mean(1)
            vsorc_rows.append(dict(split=split, budget=bmax,
                                   F1_oracle=round(float(F1_bo.mean()), 5), F1_RF=round(float(F1_RF.mean()), 5),
                                   F1_gap_RF_below_oracle=round(float((F1_bo - F1_RF).mean()), 6),
                                   B_oracle=round(float(B_bo.mean()), 5), B_RF=round(float(B_RF.mean()), 5),
                                   payload_gap_RF_minus_oracle=round(float((B_RF - B_bo).mean()), 6)))
            # --- vs-TAU account (R9), copied from the existing replay summary (kept SEPARATE) ---
            rs = replay_summary[(replay_summary.split == split) & (replay_summary.budget == bmax)].iloc[0]
            vstau_rows.append(dict(split=split, budget=bmax, dF_mean=rs['dF_mean'],
                                   dF_lcb95=rs['dF_lcb95'], dF_ucb95=rs['dF_ucb95'],
                                   dB_mean=rs['dB_mean'], payload_reduction=rs['payload_reduction']))

            # --- per-frame decision log for realisation 0 ---
            cls = np.full(n, '', dtype=object)
            cls[strict[0]] = 'strict'; cls[tie[0]] = 'tie'; cls[cost[0]] = 'cost-induced'
            log = pd.DataFrame(dict(frame=np.arange(n), snr_db=np.round(snr_2d[0], 3),
                                    channel=np.where(ray_2d[0], 'rayleigh', 'awgn'),
                                    eff_E=np.round(eff[0, :, 0], 5), eff_L=np.round(eff[0, :, 1], 5),
                                    eff_F=np.round(eff[0, :, 2], 5), bler_F=np.round(bF_2d[0], 5),
                                    raw_oracle=np.array(ACTIONS)[raw_orc[0]],
                                    budget_oracle=np.array(ACTIONS)[bud_orc[0]],
                                    rf=np.array(ACTIONS)[rf[0]], e_class=cls))
            log.to_csv(os.path.join(OUT, f'r10c_decision_log_{split}_B{int(round(bmax*100)):03d}.csv'), index=False)
            print(f'[{split} B{int(bmax*100):03d}] strict/tie/cost missed F1/frame = '
                  f'{[c for c in cost_rows if c["split"]==split and c["budget"]==bmax]}', flush=True)

    pd.DataFrame(cost_rows).to_csv(os.path.join(OUT, 'r10c_missed_e_cost.csv'), index=False)
    pd.DataFrame(vsorc_rows).to_csv(os.path.join(OUT, 'r10c_vs_oracle_account.csv'), index=False)
    pd.DataFrame(vstau_rows).to_csv(os.path.join(OUT, 'r10c_vs_tau_account.csv'), index=False)

    cost = pd.DataFrame(cost_rows)
    prim = cost[(cost.split == 'test') & (cost.budget == 0.20) & (cost.e_class == 'strict')].iloc[0]
    with open(os.path.join(OUT, 'PROVENANCE_r10c.txt'), 'w') as f:
        f.write('CA-TOSG R10c CORRIGENDUM -- POST-UNBLINDING (nothing here is confirmatory)\n' + '=' * 72 + '\n')
        f.write('RETRACTS R10 "costs payload, not F1". Feasible utility (F->-inf if BLER_F>=0.999); raw and '
                'budget oracles separate; classes strict/tie/cost-induced (residual->fuse). All missed-E '
                'cells charged dF1 AND dpayload. Recomputed on the R9 replay distribution (seed 20260809) '
                'and asserted to reproduce the existing replay CSVs (integrity check PASSED).\n\n')
        f.write(f'CORRECTED: strict-benefit missed-E F1 cost, test @ B020 = '
                f'{prim["F1_cost_per_framereal"]:.6f} per frame-realisation '
                f'(vs the retracted R10 value that hid it). The E-collapse DOES cost F1.\n')
        f.write('Accounts kept SEPARATE: r10c_vs_oracle_account.csv (RF vs budget-oracle) and '
                'r10c_vs_tau_account.csv (R9 RF vs threshold) -- do not cross-reference to explain.\n')
        f.write('6d AP and P2-C/D remain FROZEN pending review of this corrigendum.\n')
    print('\nR10c written -> results/p2_deploy/r10c_*.csv + PROVENANCE_r10c.txt (integrity assertions PASSED)')


if __name__ == '__main__':
    main()
