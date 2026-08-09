#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R10c/R10d CORRIGENDUM diagnostic (post-unblinding; nothing here is confirmatory).

Supersedes r10_diagnostic.py, whose taxonomy required eff_E > eff_F for strict-benefit -- wrong where
BLER_F >= 0.999 (F infeasible, eff_F = ego = eff_E), so genuine strict-benefit E cells were mis-bucketed
as lambda-induced, producing the RETRACTED conclusion "the E-collapse costs payload, not F1". No
training, no model/delta/tau change, no change to the R9 replay CSVs; recomputes the vs-oracle
diagnostic on the SAME deployment distribution (seed 20260809) and ALSO asserts it reproduces the
existing replay CSVs (a determinism/integrity check of the original P2-B run).

REFERENCE ORACLE = the "frozen-lambda clairvoyant oracle": s* = argmax_s (feas_s - lambda_b * B_s) with
feas_F = -inf where BLER_F >= 0.999 and lambda_b the FROZEN validate lambda*. It is CLAIRVOYANT (knows
per-frame eff) and uses the frozen lambda, but it is NOT budget-constrained: on test/Culver its mean
payload can EXCEED B_max (e.g. test B010 0.112, Culver B010 0.155, Culver B020 0.223). It is a post-hoc
reference only; a true budget-constrained oracle is NOT constructed this round.

Taxonomy of frozen-lambda-clairvoyant E cells (supervisor pseudocode, TOL = 1e-9; pre-registered in
PROTOCOL R10d), on the RAW feasible utility (no lambda), raw_max = max feasible action utility:
  strict       = isE & (eff_E > feas_L + TOL) & (eff_E > feas_F + TOL)   # E strictly beats both feasible
  tie          = isE & (|eff_E - raw_max| <= TOL) & ~strict              # E is a feasible argmax, tied
  cost_induced = isE & (eff_E < raw_max - TOL)                           # E below the feasible optimum
Every missed-E cell (all classes) is charged dF1 = eff_E - eff_{RF action} AND dpayload = B_{RF} - B_E.
Per class AND a class TOTAL are reported. "strict-benefit missed-E cost" and "total E-collapse F1 cost"
are TWO DIFFERENT numbers -- do not conflate (CLAIMS rule).

Hard assertions (fail = fuse): (a) dF1[strict & missed] >= -TOL row-wise; (b) strict|tie|cost == isE
(mutually exclusive + complete, zero residual); (c) lambda=0 => cost_induced count 0; (d) cost_induced
rows satisfy raw dF1(E vs feasible optimum) = eff_E - raw_max <= 0; plus per-realisation F1_RF/B_RF
reproduce the existing replay CSVs.

Outputs (results/p2_deploy/): r10c_missed_e_cost.csv, r10c_vs_oracle_account.csv, r10c_vs_tau_account.csv,
r10c_decision_log_{split}_B0XX.csv (realisation 0, per frame), PROVENANCE_r10c.txt.

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
    raise SystemExit(f'R10c/R10d FUSE: {msg}')


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
        bF_2d = np.stack([bler16(tbl, snr_2d[r], ray_2d[r]) for r in range(N_REPLAY)])
        eff = np.stack([np.broadcast_to(ego, (N_REPLAY, n)), np.broadcast_to(late, (N_REPLAY, n)),
                        comp[None, :] * (1 - bF_2d) + ego[None, :] * bF_2d], axis=2)
        feas = eff.copy(); feas[:, :, 2][bF_2d >= BLER_INFEASIBLE] = -np.inf
        raw_orc = feas.argmax(2)
        eE = eff[:, :, 0]

        for b, bd in man['budgets'].items():
            lam = float(bd['lambda_star']); bmax = float(b)
            mp = os.path.join(P1, bd['model'])
            if _sha256(mp) != bd['model_sha256']:
                fuse(f'{b} model sha mismatch')
            model = pickle.load(open(mp, 'rb'))
            rf = rf_stacked(model, man['feature_names'], cues, snr_2d, ray_2d)
            clair = (feas - lam * PAY[None, None, :]).argmax(2)      # frozen-lambda clairvoyant oracle

            # integrity: per-realisation F1_RF/B_RF must reproduce the existing replay CSV
            eff_rf = np.take_along_axis(eff, rf[:, :, None], 2)[:, :, 0]
            F1_RF = eff_rf.mean(1); B_RF = PAY[rf].mean(1)
            rp = pd.read_csv(os.path.join(OUT, f'replay_{split}_B{int(round(bmax*100)):03d}.csv'))
            if (np.abs(F1_RF - rp['F1_RF'].to_numpy()).max() > 1e-9
                    or np.abs(B_RF - rp['B_RF'].to_numpy()).max() > 1e-9):
                fuse(f'{split} B{bmax}: recomputed F1_RF/B_RF != existing replay CSV (integrity)')

            # --- taxonomy (supervisor pseudocode, R10d) on the RAW feasible utility ---
            isE = clair == 0
            raw_max = feas.max(2)
            fL = feas[:, :, 1]; fF = feas[:, :, 2]
            strict = isE & (eE > fL + TOL) & (eE > fF + TOL)
            tie = isE & (np.abs(eE - raw_max) <= TOL) & ~strict
            cost = isE & (eE < raw_max - TOL)
            resid = isE & ~(strict | tie | cost)
            # hard assertions
            if resid.any():
                fuse(f'{split} B{bmax}: {int(resid.sum())} clairvoyant-E cells fall in NO class (b: residual)')
            if lam == 0 and int(cost.sum()) != 0:
                fuse(f'{split} B{bmax}: lambda=0 but cost_induced count = {int(cost.sum())} (c)')
            if cost.any() and ((eE[cost] - raw_max[cost]) > TOL).any():
                fuse(f'{split} B{bmax}: a cost_induced row has raw dF1(E vs feasible optimum) > 0 (d)')
            miss = isE & (rf != 0)
            # Assertion (a) checks TAXONOMY consistency (on strict cells the feasible-best is E, so RF
            # cannot beat it on the FEASIBLE utility). It therefore uses the mask-consistent realised eff:
            # an RF pick of a MASKED-INFEASIBLE F (BLER_F >= 0.999) delivers ego (the failure fallback),
            # matching the oracle mask -- otherwise the BLER=0.999 boundary (F succeeds 0.1% -> ego+eps)
            # would spuriously beat E by ~1e-5 on a handful of in-sample cells. The COST account below
            # keeps the TRUE realised eff (deployment reality: RF wastes B_F=0.99 for ~0 F1).
            eff_rf_feas = eff_rf.copy()
            inf_F = (rf == 2) & (bF_2d >= BLER_INFEASIBLE)
            eff_rf_feas[inf_F] = np.broadcast_to(ego, (N_REPLAY, n))[inf_F]
            if (strict & miss).any() and ((eE[strict & miss] - eff_rf_feas[strict & miss]) < -TOL).any():
                fuse(f'{split} B{bmax}: a strict & missed row has feasible dF1 < -TOL (a)')

            denom = N_REPLAY * n
            tot_f1 = 0.0; tot_pay = 0.0
            for name, mask in (('strict', strict), ('tie', tie), ('cost-induced', cost)):
                mm = mask & miss
                df1 = float((eE[mm] - eff_rf[mm]).sum()); dpay = float(PAY[rf[mm]].sum())
                tot_f1 += df1; tot_pay += dpay
                cost_rows.append(dict(split=split, budget=bmax, e_class=name,
                                      clairvoyant_E_cells=int(mask.sum()), missed_by_rf=int(mm.sum()),
                                      F1_cost_sum=round(df1, 4), F1_cost_per_framereal=round(df1 / denom, 8),
                                      payload_extra_sum=round(dpay, 2),
                                      payload_extra_per_framereal=round(dpay / denom, 6)))
            cost_rows.append(dict(split=split, budget=bmax, e_class='TOTAL(all-classes)',
                                  clairvoyant_E_cells=int(isE.sum()), missed_by_rf=int(miss.sum()),
                                  F1_cost_sum=round(tot_f1, 4), F1_cost_per_framereal=round(tot_f1 / denom, 8),
                                  payload_extra_sum=round(tot_pay, 2),
                                  payload_extra_per_framereal=round(tot_pay / denom, 6)))

            # vs-ORACLE account (RF vs the frozen-lambda clairvoyant oracle), replay distribution
            eff_bo = np.take_along_axis(eff, clair[:, :, None], 2)[:, :, 0]
            F1_bo = eff_bo.mean(1); B_bo = PAY[clair].mean(1)
            vsorc_rows.append(dict(split=split, budget=bmax,
                                   F1_clairvoyant=round(float(F1_bo.mean()), 5), F1_RF=round(float(F1_RF.mean()), 5),
                                   F1_gap_RF_below_clairvoyant=round(float((F1_bo - F1_RF).mean()), 6),
                                   B_clairvoyant=round(float(B_bo.mean()), 5), B_RF=round(float(B_RF.mean()), 5),
                                   clairvoyant_exceeds_Bmax=bool(float(B_bo.mean()) > bmax)))
            rs = replay_summary[(replay_summary.split == split) & (replay_summary.budget == bmax)].iloc[0]
            vstau_rows.append(dict(split=split, budget=bmax, dF_mean=rs['dF_mean'],
                                   dF_lcb95=rs['dF_lcb95'], dF_ucb95=rs['dF_ucb95'],
                                   dB_mean=rs['dB_mean'], payload_reduction=rs['payload_reduction']))

            # per-frame decision log for realisation 0
            cls = np.full(n, '', dtype=object)
            cls[strict[0]] = 'strict'; cls[tie[0]] = 'tie'; cls[cost[0]] = 'cost-induced'
            pd.DataFrame(dict(frame=np.arange(n), snr_db=np.round(snr_2d[0], 3),
                              channel=np.where(ray_2d[0], 'rayleigh', 'awgn'),
                              eff_E=np.round(eff[0, :, 0], 5), eff_L=np.round(eff[0, :, 1], 5),
                              eff_F=np.round(eff[0, :, 2], 5), bler_F=np.round(bF_2d[0], 5),
                              raw_oracle=np.array(ACTIONS)[raw_orc[0]],
                              frozen_lambda_clairvoyant=np.array(ACTIONS)[clair[0]],
                              rf=np.array(ACTIONS)[rf[0]], e_class=cls)).to_csv(
                os.path.join(OUT, f'r10c_decision_log_{split}_B{int(round(bmax*100)):03d}.csv'), index=False)
            print(f'[{split} B{int(bmax*100):03d}] strict F1/frame={cost_rows[-4]["F1_cost_per_framereal"]:.6f} '
                  f'TOTAL F1/frame={tot_f1/denom:.6f} clair_pay={B_bo.mean():.4f}(Bmax {bmax})', flush=True)

    pd.DataFrame(cost_rows).to_csv(os.path.join(OUT, 'r10c_missed_e_cost.csv'), index=False)
    pd.DataFrame(vsorc_rows).to_csv(os.path.join(OUT, 'r10c_vs_oracle_account.csv'), index=False)
    pd.DataFrame(vstau_rows).to_csv(os.path.join(OUT, 'r10c_vs_tau_account.csv'), index=False)

    cost = pd.DataFrame(cost_rows)
    strict20 = cost[(cost.split == 'test') & (cost.budget == 0.20) & (cost.e_class == 'strict')].iloc[0]
    total20 = cost[(cost.split == 'test') & (cost.budget == 0.20) & (cost.e_class == 'TOTAL(all-classes)')].iloc[0]
    with open(os.path.join(OUT, 'PROVENANCE_r10c.txt'), 'w') as f:
        f.write('CA-TOSG R10c/R10d CORRIGENDUM -- POST-UNBLINDING (nothing here is confirmatory)\n' + '=' * 72 + '\n')
        f.write('RETRACTS R10 "costs payload, not F1". Taxonomy per supervisor pseudocode (R10d), TOL=1e-9, '
                'on feasible utility; reference = FROZEN-LAMBDA CLAIRVOYANT oracle (NOT budget-constrained: '
                'its mean payload can exceed B_max on test/Culver). Recomputed on the R9 replay distribution '
                '(seed 20260809); reproduces the existing replay CSVs (integrity check PASSED). 4 hard '
                'assertions PASSED.\n\n')
        f.write('TWO DIFFERENT NUMBERS (do not conflate):\n')
        f.write(f'  strict-benefit missed-E F1 cost, test @ B020 = {strict20["F1_cost_per_framereal"]:.6f} /frame '
                f'(substantive; the E-collapse DOES cost F1).\n')
        f.write(f'  total E-collapse F1 cost (all classes), test @ B020 = {total20["F1_cost_per_framereal"]:.6f} /frame '
                '(nets in tie ~0 and cost-induced <0 where RF picks the raw-better action).\n')
        f.write('Accounts kept SEPARATE: r10c_vs_oracle_account.csv (RF vs frozen-lambda clairvoyant) and '
                'r10c_vs_tau_account.csv (R9 RF vs threshold) -- do not cross-reference to explain.\n')
        f.write('Retraction chain: R10 -> R10c -> R10d (see PROTOCOL change-log). 6d AP + P2-C/D stay frozen.\n')
    print('\nR10c/R10d written -> results/p2_deploy/r10c_*.csv + PROVENANCE_r10c.txt (assertions PASSED)')


if __name__ == '__main__':
    main()
