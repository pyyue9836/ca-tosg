#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R21-A evaluation: the frozen two-gate heuristic on the 200-realisation paired replay.

DESCRIPTIVE + CI ONLY. R9's confirmatory primary is spent; nothing here is a decision, in either
direction (Change-log R21-A, "How it is reported").

Same machinery as `deployment.py` and the P4-A bandit: the SAME 200 paired CSI draws per split
(`CSI_SEED`), the same `eff_matrix`, the same paired bootstrap (`N_BOOT`, `BOOT_SEED`). The two-gate
policy, RF and tau therefore see identical per-frame SNR/channel draws, so `F1_RF` printed here must
reproduce `replay_summary.csv` exactly -- asserted at run time.

The frozen thresholds transfer as ABSOLUTE cue values; they are NOT re-quantiled per split.

Outputs (results/baselines/): two_gate.csv, two_gate_actions.csv,
two_gate_runs/r21a_replay_{split}_B0XX.csv, + results/provenance/PROVENANCE_r21a.txt

    python tools/run_baselines.py two_gate --evaluate
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
_CT_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils'):
    sys.path.insert(0, os.path.join(_CT_ROOT, _d))

import deployment as D                                                            # noqa: E402
import train as T                                                                 # noqa: E402

P1 = D.P1
OUT_RUNS = os.path.join(P1, 'results/baselines/two_gate_runs')
OUT_SUMM = os.path.join(P1, 'results/baselines/two_gate.csv')
OUT_ACT = os.path.join(P1, 'results/baselines/two_gate_actions.csv')
PROV = os.path.join(P1, 'results/provenance/PROVENANCE_r21a.txt')
REPLAY_SUMM = os.path.join(P1, 'results/main/replay_summary.csv')


def load_manifest():
    if not os.path.exists(T.MANIFEST):
        raise SystemExit('R21-A eval FUSE: R21A_MANIFEST.json absent -- run --train first.')
    man = json.load(open(T.MANIFEST))
    if man.get('schema') != 'catosg-r21a-manifest/1':
        raise SystemExit(f'R21-A eval FUSE: unexpected schema {man.get("schema")!r}')
    for key, spec in man['inputs'].items():
        p = os.path.join(P1, spec['file'])
        got = T._md5(p) if 'md5' in spec else T._sha256(p)
        if got != spec.get('md5', spec.get('sha256')):
            raise SystemExit(f'R21-A eval FUSE: {key} changed since the freeze ({spec["file"]})')
    return man


def main():
    os.makedirs(OUT_RUNS, exist_ok=True)
    man = load_manifest()
    rfman, rfbud = D.load_manifest()
    tbl = pd.read_csv(D.BLER_CSV)
    ref = pd.read_csv(REPLAY_SUMM)
    tags = sorted(man['budgets'])

    summ, act_rows = [], []
    for split in D.SPLITS:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
        rng = np.random.default_rng(D.CSI_SEED)                       # SAME draws as deployment.py
        snr_2d = rng.uniform(0, 20, size=(D.N_REPLAY, n))
        is_ray_2d = rng.random(size=(D.N_REPLAY, n)) < 0.5
        bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(D.N_REPLAY)])
        r_2d = 1.0 - bF_2d

        for tag in tags:
            bd = man['budgets'][tag]
            bmax = float(tag)
            if not bd.get('feasible', False):
                summ.append(dict(split=split, budget=bmax, feasible=False))
                continue
            d = bd['sign'] * ds[bd['cue']].to_numpy(float)
            tE = -np.inf if bd['tau_E_is_never_E'] else float(bd['tau_E'])
            tF = np.inf if bd['tau_F_is_never_F'] else float(bd['tau_F'])
            tg_idx = np.where(d[None, :] <= tE, 0, np.where(r_2d >= tF, 2, 1))       # (R,n)
            rf_idx = D.rf_actions_stacked(rfbud[tag]['model'], rfbud[tag]['feat'], ds, snr_2d, is_ray_2d)
            ta_idx = D.tau_actions(snr_2d, is_ray_2d, rfbud[tag]['tau'])

            F = {k: np.empty(D.N_REPLAY) for k in ('TG', 'RF', 'TA')}
            B = {k: np.empty(D.N_REPLAY) for k in ('TG', 'RF', 'TA')}
            for r in range(D.N_REPLAY):
                E = D.eff_matrix(ego, late, comp, bF_2d[r])
                for k, idx in (('TG', tg_idx), ('RF', rf_idx), ('TA', ta_idx)):
                    F[k][r] = E[np.arange(n), idx[r]].mean()
                    B[k][r] = D.PAYVEC[idx[r]].mean()

            # the paired-draw check: RF here must reproduce the mainline replay exactly
            m = ref[(ref['split'] == split) & (np.isclose(ref['budget'], bmax))]
            if len(m) == 1 and abs(round(F['RF'].mean(), 5) - float(m['F1_RF'].iloc[0])) > 1e-5:
                raise SystemExit(f'R21-A eval FUSE: F1_RF {F["RF"].mean():.5f} != replay_summary '
                                 f'{float(m["F1_RF"].iloc[0]):.5f} -- the draws are not paired')

            dF_rf = F['TG'] - F['RF']; dB_rf = B['TG'] - B['RF']
            dF_ta = F['TG'] - F['TA']; dB_ta = B['TG'] - B['TA']
            pd.DataFrame(dict(realisation=np.arange(D.N_REPLAY), F1_2G=F['TG'], F1_RF=F['RF'],
                              F1_tau=F['TA'], B_2G=B['TG'], B_RF=B['RF'], B_tau=B['TA'],
                              dF_2G_RF=dF_rf, dB_2G_RF=dB_rf, dF_2G_tau=dF_ta, dB_2G_tau=dB_ta)).to_csv(
                os.path.join(OUT_RUNS, f'r21a_replay_{split}_B{int(round(bmax*100)):03d}.csv'), index=False)

            row = dict(split=split, budget=bmax, feasible=True, cue=bd['cue'], sign=bd['sign'],
                       tau_E=bd['tau_E'], tau_F=bd['tau_F'],
                       F1_2G=round(F['TG'].mean(), 5), F1_RF=round(F['RF'].mean(), 5),
                       F1_tau=round(F['TA'].mean(), 5), B_2G=round(B['TG'].mean(), 5),
                       B_RF=round(B['RF'].mean(), 5), B_tau=round(B['TA'].mean(), 5),
                       over_budget_2G=round(float(B['TG'].mean() - bmax), 5))
            for name, dd in (('2G_vs_RF_dF', dF_rf), ('2G_vs_RF_dB', dB_rf),
                             ('2G_vs_tau_dF', dF_ta), ('2G_vs_tau_dB', dB_ta)):
                mm, lo, hi = D.paired_bootstrap(dd, D.N_BOOT, D.BOOT_SEED)
                row[name + '_mean'] = round(mm, 5)
                row[name + '_lcb95'] = round(lo, 5)
                row[name + '_ucb95'] = round(hi, 5)
            summ.append(row)

            for k, idx in (('two_gate', tg_idx), ('RF', rf_idx), ('tau', ta_idx)):
                act_rows.append(dict(split=split, budget=bmax, policy=k,
                                     rho_E=round(float((idx == 0).mean()), 5),
                                     rho_L=round(float((idx == 1).mean()), 5),
                                     rho_F=round(float((idx == 2).mean()), 5)))
            print(f'[{split} B{int(bmax*100):03d}] F1 2G={F["TG"].mean():.5f} RF={F["RF"].mean():.5f} '
                  f'tau={F["TA"].mean():.5f} | B 2G={B["TG"].mean():.5f} RF={B["RF"].mean():.5f} | '
                  f'dF(2G-RF)=[{row["2G_vs_RF_dF_lcb95"]:.5f},{row["2G_vs_RF_dF_ucb95"]:.5f}] '
                  f'rho_E={act_rows[-3]["rho_E"]:.4f}', flush=True)

    pd.DataFrame(summ).to_csv(OUT_SUMM, index=False)
    pd.DataFrame(act_rows).to_csv(OUT_ACT, index=False)

    with open(PROV, 'w') as f:
        f.write('CA-TOSG R21-A -- two-gate heuristic (difficulty gate + link-reliability gate).\n'
                'DESCRIPTIVE + CI ONLY; not deployed; no decision in either direction.\n' + '=' * 88 + '\n')
        f.write(f'manifest: results/manifests/R21A_MANIFEST.json (schema {man["schema"]}); all four '
                'frozen inputs md5/sha256-verified before the replay.\n')
        f.write('policy: ' + man['policy'] + '\n')
        for tag in tags:
            bd = man['budgets'][tag]
            if bd.get('feasible'):
                f.write(f'  B={tag}: candidate {bd["candidate_index"]} {bd["cue"]}/{bd["sign"]:+d}, '
                        f'tau_E={bd["tau_E"]} (q={bd["tau_E_quantile"]}), tau_F={bd["tau_F"]}, '
                        f'OOF f1={bd["loso_frame_weighted_f1"]} pay={bd["loso_frame_weighted_payload"]}\n')
            else:
                f.write(f'  B={tag}: INFEASIBLE -- {bd.get("note")}\n')
        f.write(f'CSI: {D.N_REPLAY} paired samplings/split, seed={D.CSI_SEED} -- the IDENTICAL draws to '
                'deployment.py; RF reproduced from the frozen selectors and asserted equal to '
                'replay_summary.csv.\n')
        f.write(f'CI: paired bootstrap, {D.N_BOOT} resamples, percentile, seed={D.BOOT_SEED}.\n')
        f.write('Thresholds transfer as ABSOLUTE cue values (validate quantile, NOT re-quantiled per '
                'split). test/Culver labels used for SCORING ONLY.\n')
        f.write('Zero GPU: cached eff + the committed BLER table + frozen predict().\n')
    print('\nwrote results/baselines/{two_gate.csv, two_gate_actions.csv, two_gate_runs/r21a_replay_*}'
          '\n      results/provenance/PROVENANCE_r21a.txt')
    return 0


if __name__ == '__main__':
    sys.exit(main())
