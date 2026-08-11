#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-A evaluation: external RL bandit baseline vs RF and vs tau (Change-log P4-A (c)). DESCRIPTIVE + CI ONLY.

"external baseline, not deployed". Same 200-realisation paired replay + CSI_SEED as eval_p2_deploy (the
RL, RF, and tau policies see the IDENTICAL per-frame SNR/channel draws), same eff definition, same paired
bootstrap CI machinery as R9. Reports RL-vs-RF and RL-vs-tau as CIs only -- NO new decision (the
confirmatory primary was spent once at R9). Frozen CA-TOSG models / delta / tau* / oracle unchanged;
main.tex untouched; no new perception inference.

Outputs (results/p4a/): p4a_replay_{split}_B0XX.csv (200 rows) + p4a_summary.csv + PROVENANCE_p4a.txt.
Run:  /path/to/env/python paper1/code/p2_dataprep/eval_p4a_deploy.py
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_p2_deploy as D
import train_p4a_bandit as T

P1 = D.P1
OUT = os.path.join(P1, 'results/p4a')
P4A_MANIFEST = os.path.join(OUT, 'P4A_MANIFEST.json')
PAYVEC = D.PAYVEC
SPLITS = D.SPLITS
N_REPLAY = D.N_REPLAY
CSI_SEED = D.CSI_SEED
N_BOOT = D.N_BOOT
BOOT_SEED = D.BOOT_SEED
DEV = T.DEV


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load_bandits():
    if not os.path.exists(P4A_MANIFEST):
        raise SystemExit('P4-A eval FUSE: P4A_MANIFEST.json absent -- run train_p4a_bandit.py first.')
    man = json.load(open(P4A_MANIFEST))
    out = {}
    for tag, bd in man['budgets'].items():
        mp = os.path.join(P1, bd['model'])
        if _sha256(mp) != bd['model_sha256']:
            raise SystemExit(f'P4-A eval FUSE: {tag} bandit sha mismatch (not the frozen product)')
        ck = torch.load(mp, map_location=DEV, weights_only=False)
        net = T.QNet(len(ck['feat']), ck['hidden']).to(DEV)
        net.load_state_dict(ck['state_dict']); net.eval()
        out[tag] = dict(net=net, mu=ck['mu'], sd=ck['sd'], feat=ck['feat'], lam=bd['lam'])
    return man, out


def bandit_actions(bd, ds, snr_2d, is_ray_2d):
    """Greedy bandit action for all 200 realisations at once. Returns (R,n) int idx."""
    R, n = snr_2d.shape
    big = D._feature_matrix(bd['feat'], ds, snr_2d.reshape(-1), is_ray_2d.reshape(-1))
    z = ((big - bd['mu']) / bd['sd']).astype(np.float32)
    with torch.no_grad():
        a = bd['net'](torch.from_numpy(z).to(DEV)).argmax(1).cpu().numpy()
    return a.reshape(R, n)


def paired_bootstrap(delta, n_boot, seed):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    means = delta[idx].mean(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(delta.mean()), float(lo), float(hi)


def main():
    os.makedirs(OUT, exist_ok=True)
    p4man, bandits = load_bandits()
    rfman, rfbud = D.load_manifest()
    tbl = pd.read_csv(D.BLER_CSV)
    tags = sorted(bandits)                                            # ['0.10','0.20','0.30']
    summ = []
    for split in SPLITS:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
        rng = np.random.default_rng(CSI_SEED)                         # SAME draws as eval_p2_deploy
        snr_2d = rng.uniform(0, 20, size=(N_REPLAY, n))
        is_ray_2d = rng.random(size=(N_REPLAY, n)) < 0.5
        bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(N_REPLAY)])
        for tag in tags:
            bmax = float(tag)
            rl_idx = bandit_actions(bandits[tag], ds, snr_2d, is_ray_2d)
            rf_idx = D.rf_actions_stacked(rfbud[tag]['model'], rfbud[tag]['feat'], ds, snr_2d, is_ray_2d)
            ta_idx = D.tau_actions(snr_2d, is_ray_2d, rfbud[tag]['tau'])
            F = {k: np.empty(N_REPLAY) for k in ('RL', 'RF', 'TA')}
            B = {k: np.empty(N_REPLAY) for k in ('RL', 'RF', 'TA')}
            for r in range(N_REPLAY):
                E = D.eff_matrix(ego, late, comp, bF_2d[r])              # (n,3)
                for k, idx in (('RL', rl_idx), ('RF', rf_idx), ('TA', ta_idx)):
                    F[k][r] = E[np.arange(n), idx[r]].mean(); B[k][r] = PAYVEC[idx[r]].mean()
            dF_rf = F['RL'] - F['RF']; dB_rf = B['RL'] - B['RF']
            dF_ta = F['RL'] - F['TA']; dB_ta = B['RL'] - B['TA']
            pd.DataFrame(dict(realisation=np.arange(N_REPLAY), F1_RL=F['RL'], F1_RF=F['RF'], F1_tau=F['TA'],
                              B_RL=B['RL'], B_RF=B['RF'], B_tau=B['TA'],
                              dF_RL_RF=dF_rf, dB_RL_RF=dB_rf, dF_RL_tau=dF_ta, dB_RL_tau=dB_ta)).to_csv(
                os.path.join(OUT, f'p4a_replay_{split}_B{int(round(bmax*100)):03d}.csv'), index=False)
            row = dict(split=split, budget=bmax,
                       F1_RL=round(F['RL'].mean(), 5), F1_RF=round(F['RF'].mean(), 5), F1_tau=round(F['TA'].mean(), 5),
                       B_RL=round(B['RL'].mean(), 5), B_RF=round(B['RF'].mean(), 5), B_tau=round(B['TA'].mean(), 5))
            for name, d in (('RL_vs_RF_dF', dF_rf), ('RL_vs_RF_dB', dB_rf),
                            ('RL_vs_tau_dF', dF_ta), ('RL_vs_tau_dB', dB_ta)):
                m, lo, hi = paired_bootstrap(d, N_BOOT, BOOT_SEED)
                row[name + '_mean'] = round(m, 5); row[name + '_lcb95'] = round(lo, 5); row[name + '_ucb95'] = round(hi, 5)
            summ.append(row)
            print(f'[{split} B{int(bmax*100):03d}] F1 RL={F["RL"].mean():.4f} RF={F["RF"].mean():.4f} '
                  f'tau={F["TA"].mean():.4f} | B RL={B["RL"].mean():.4f} RF={B["RF"].mean():.4f} | '
                  f'dF(RL-RF)=[{row["RL_vs_RF_dF_lcb95"]:.4f},{row["RL_vs_RF_dF_ucb95"]:.4f}]', flush=True)
    pd.DataFrame(summ).to_csv(os.path.join(OUT, 'p4a_summary.csv'), index=False)

    with open(os.path.join(OUT, 'PROVENANCE_p4a.txt'), 'w') as f:
        f.write('CA-TOSG P4-A -- external RL bandit baseline vs RF and tau (eval_p4a_deploy.py). '
                'DESCRIPTIVE + CI ONLY; "external baseline, not deployed".\n' + '=' * 90 + '\n')
        f.write(f'P4A manifest: results/p4a/P4A_MANIFEST.json ({p4man["schema"]}, algo {p4man["algorithm"]}, '
                f'problem_form {p4man["problem_form"]}); 3 bandits sha256-verified.\n')
        f.write(f'Same 200 paired CSI samplings/split, seed={CSI_SEED} (identical draws to eval_p2_deploy); '
                'RL, RF and tau replay the SAME draws. eff identical to the mainline (F1_RF here == replay_summary).\n')
        f.write(f'Paired bootstrap CI, {N_BOOT} resamples, seed={BOOT_SEED}, percentile. '
                'RL-vs-RF and RL-vs-tau reported as CIs ONLY -- NO new decision (R9 primary already spent).\n')
        f.write('Frozen CA-TOSG models / delta / tau* / oracle unchanged; main.tex untouched; no new '
                'perception inference (cached eff + frozen predict()).\n')
    print('wrote results/p4a/{p4a_replay_*, p4a_summary.csv, PROVENANCE_p4a.txt}')


if __name__ == '__main__':
    main()
