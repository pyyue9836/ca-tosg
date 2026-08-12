#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 descriptive sensitivity batch -- re-weighted 200-realisation replay of the cached eff (Change-log P3).

DESCRIPTIVE ONLY. No change to the frozen selectors / delta / tau* / oracle / mainline replay; main.tex
untouched. Every item RE-RUNS the mainline deployment replay (eval_p2_deploy machinery, imported) under a
modified channel/SNR/BLER_L distribution, reusing the cached per-frame eff (ego_f1/late_f1/compressed_f1
in dataset_{split}.csv) and the frozen predict() -- NO new detection inference. The frozen selectors +
tau* come from FROZEN_MANIFEST.json (sha256-verified). §8 anti-forcing clause applies: expected
behaviours are checks, not targets; a miss is reported, not fixed.

Baseline path (uniform SNR, 50/50 channel, BLER_L=0) draws from rng(CSI_SEED) in the SAME order as
eval_p2_deploy, so it reproduces the mainline replay_summary EXACTLY (sanity, baseline_sanity.csv).

Items (per split x budget; F1 = mean realised eff at the selector action, payload = mean channel use;
mean +/- std over N_REPLAY realisations):
  1. channel ratio     : channel ~ Bernoulli(p_rayleigh), p_rayleigh in {0.75,0.50,0.25} (SNR uniform).
  2. non-uniform SNR    : SNR ~ {uniform, Beta(2,5)x20 low-skew, N(10,5) trunc[0,20]} (channel 50/50).
  3. channel-type flip  : the selector's channel_is_rayleigh flipped w.p. p in {0,.05,.10,.20}; the TRUE
                          channel used for BLER is unchanged. Same-seed replay.
  4. BLER_L grid        : eff_L' = eff_L*(1-BLER_L)+eff_E*BLER_L, BLER_L in {0,.01,.05,.10}; frozen
                          actions + oracle unchanged (BLER_L is not a selector input); mainline BLER_L=0.
  5. Rician (if table)  : K in {0,3,10} from results/channel/bler_sionna_rician.csv; selector fed
                          channel_is_rayleigh=1 (fading); eff_F recomputed under the Rician frame-BLER.

Outputs (results/p3_sensitivity/): item{1..5}_*.csv + baseline_sanity.csv + PROVENANCE_p3.txt.
Run:  /path/to/env/python projects/ca_tosg/evaluation/sensitivity.py
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# --- ca-tosg layout bootstrap (restructure commit 2/4) ---
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/evaluation/ablations', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
# --- end bootstrap ---
import deployment as D

P1 = D.P1
OUT = os.path.join(P1, 'results/sensitivity')
PROV_DIR = os.path.join(P1, 'results/provenance')
RICIAN_TBL = os.path.join(P1, 'results/channel/bler_sionna_rician.csv')
PAYVEC = D.PAYVEC
SPLITS = D.SPLITS
SNR_GRID = np.array(D.SNR_GRID, dtype=float)
N_REPLAY = D.N_REPLAY
CSI_SEED = D.CSI_SEED
FLIP_SEED = 20260811            # item-3 flip mask (separate, recorded); base draws stay byte-identical


def draw_snr(rng, shape, dist):
    if dist == 'uniform':
        return rng.uniform(0, 20, size=shape)
    if dist == 'beta25_lowskew':
        return rng.beta(2, 5, size=shape) * 20.0
    if dist == 'truncgauss_10_5':
        a, b = (0 - 10) / 5.0, (20 - 10) / 5.0
        return stats.truncnorm.ppf(rng.random(size=shape), a, b, loc=10, scale=5)
    raise ValueError(dist)


def eff_matrix_blerL(ego, late, comp, bF, bler_L=0.0):
    """(n,3) eff for [E,L,F]; eff_L' = late*(1-bler_L)+ego*bler_L (item 4)."""
    effL = late * (1 - bler_L) + ego * bler_L
    return np.stack([ego, effL, comp * (1 - bF) + ego * bF], axis=1)


def _draws(ds, dist, p_ray):
    """Baseline-aligned draws: rng(CSI_SEED) -> snr_2d then is_ray_2d, SAME order as eval_p2_deploy."""
    n = len(ds)
    rng = np.random.default_rng(CSI_SEED)
    snr_2d = draw_snr(rng, (N_REPLAY, n), dist)
    is_ray_2d = rng.random(size=(N_REPLAY, n)) < p_ray
    return snr_2d, is_ray_2d


def _metrics(ds, tbl, act_2d, snr_2d, is_ray_2d, bler_L):
    """Vectorised F1/payload/rho over realisations given per-cell actions (R,n)."""
    ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
    n = len(ds)
    F1 = np.empty(N_REPLAY); B = np.empty(N_REPLAY); RHO = np.empty(N_REPLAY)
    for r in range(N_REPLAY):
        bF = D.bler16(tbl, snr_2d[r], is_ray_2d[r])           # true-channel frame BLER
        E = eff_matrix_blerL(ego, late, comp, bF, bler_L)
        a = act_2d[r]
        F1[r] = E[np.arange(n), a].mean(); B[r] = PAYVEC[a].mean(); RHO[r] = float((a == 2).mean())
    return F1.mean(), F1.std(), B.mean(), B.std(), RHO.mean()


def replay(bd, ds, tbl, dist='uniform', p_ray=0.5, bler_L=0.0, flip_p=0.0):
    """RF replay under a modified distribution. One stacked predict (200 x n). bF uses the TRUE channel;
    the selector sees channel_is_rayleigh possibly flipped w.p. flip_p (true channel for BLER unchanged)."""
    snr_2d, is_ray_2d = _draws(ds, dist, p_ray)
    feat_ray = is_ray_2d
    if flip_p > 0:
        flip_2d = np.random.default_rng(FLIP_SEED).random(size=is_ray_2d.shape) < flip_p
        feat_ray = is_ray_2d ^ flip_2d
    act_2d = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr_2d, feat_ray)
    return _metrics(ds, tbl, act_2d, snr_2d, is_ray_2d, bler_L)


def replay_tau(bd, ds, tbl, dist='uniform', p_ray=0.5, bler_L=0.0):
    """SNR-threshold baseline under the same modified distribution (tau is channel-aware by rule; no flip)."""
    snr_2d, is_ray_2d = _draws(ds, dist, p_ray)
    act_2d = D.tau_actions(snr_2d, is_ray_2d, bd['tau'])
    f, fs, b, bs, _ = _metrics(ds, tbl, act_2d, snr_2d, is_ray_2d, bler_L)
    return f, fs, b, bs


def main():
    os.makedirs(OUT, exist_ok=True)
    man, budgets = D.load_manifest()
    tags = sorted(budgets)
    tbl = pd.read_csv(D.BLER_CSV)
    datasets = {sp: pd.read_csv(os.path.join(D.DATA, D.DATASET[sp])) for sp in SPLITS}

    sanity, rows1, rows2, rows3, rows4 = [], [], [], [], []
    for sp in SPLITS:
        ds = datasets[sp]
        for tag in tags:
            bd = budgets[tag]; bmax = float(tag)

            # sanity (baseline) -- must match mainline replay_summary
            f, fs, b, bs, rho = replay(bd, ds, tbl)
            tf, tfs, tb, tbs = replay_tau(bd, ds, tbl)
            sanity.append(dict(split=sp, budget=bmax, policy='RF', F1=round(f, 5), payload=round(b, 5)))
            sanity.append(dict(split=sp, budget=bmax, policy='tau', F1=round(tf, 5), payload=round(tb, 5)))

            # item 1: channel ratio
            for pr in (0.75, 0.50, 0.25):
                f, fs, b, bs, rho = replay(bd, ds, tbl, p_ray=pr)
                tf, tfs, tb, tbs = replay_tau(bd, ds, tbl, p_ray=pr)
                lbl = f'{int(round((1-pr)*100))}/{int(round(pr*100))}'
                rows1.append(dict(split=sp, budget=bmax, awgn_rayleigh=lbl, p_rayleigh=pr, policy='RF',
                                  F1=round(f, 5), F1_std=round(fs, 5), payload=round(b, 5), rho_feature=round(rho, 4)))
                rows1.append(dict(split=sp, budget=bmax, awgn_rayleigh=lbl, p_rayleigh=pr, policy='tau',
                                  F1=round(tf, 5), F1_std=round(tfs, 5), payload=round(tb, 5), rho_feature=''))

            # item 2: non-uniform SNR (channel 50/50)
            for dist in ('uniform', 'beta25_lowskew', 'truncgauss_10_5'):
                f, fs, b, bs, rho = replay(bd, ds, tbl, dist=dist)
                tf, tfs, tb, tbs = replay_tau(bd, ds, tbl, dist=dist)
                rows2.append(dict(split=sp, budget=bmax, snr_dist=dist, policy='RF',
                                  F1=round(f, 5), F1_std=round(fs, 5), payload=round(b, 5), rho_feature=round(rho, 4)))
                rows2.append(dict(split=sp, budget=bmax, snr_dist=dist, policy='tau',
                                  F1=round(tf, 5), F1_std=round(tfs, 5), payload=round(tb, 5), rho_feature=''))

            # item 3: channel-type flip (true channel unchanged)
            for p in (0.0, 0.05, 0.10, 0.20):
                f, fs, b, bs, rho = replay(bd, ds, tbl, flip_p=p)
                rows3.append(dict(split=sp, budget=bmax, flip_p=p, policy='RF',
                                  F1=round(f, 5), F1_std=round(fs, 5), payload=round(b, 5), rho_feature=round(rho, 4)))

            # item 4: BLER_L grid (frozen actions; realised eff_L only)
            for bl in (0.0, 0.01, 0.05, 0.10):
                f, fs, b, bs, rho = replay(bd, ds, tbl, bler_L=bl)
                rows4.append(dict(split=sp, budget=bmax, bler_L=bl, policy='RF',
                                  F1=round(f, 5), F1_std=round(fs, 5), payload=round(b, 5), rho_feature=round(rho, 4)))
            print(f'[{sp} B{int(bmax*100):03d}] done', flush=True)

    pd.DataFrame(sanity).to_csv(os.path.join(OUT, 'baseline_sanity.csv'), index=False)
    pd.DataFrame(rows1).to_csv(os.path.join(OUT, 'channel_ratio.csv'), index=False)
    pd.DataFrame(rows2).to_csv(os.path.join(OUT, 'nonuniform_snr.csv'), index=False)
    pd.DataFrame(rows3).to_csv(os.path.join(OUT, 'channel_misclassification.csv'), index=False)
    pd.DataFrame(rows4).to_csv(os.path.join(OUT, 'object_message_bler.csv'), index=False)

    # item 5: Rician (only if the Sionna table is present AND complete -- all pre-registered K present).
    RICIAN_K_EXPECTED = {0.0, 3.0, 10.0}
    rician_done = False
    rt_ready = False
    if os.path.exists(RICIAN_TBL):
        _rt = pd.read_csv(RICIAN_TBL)
        have = set(_rt[_rt['qam'] == 16]['rician_k'].unique().tolist())
        rt_ready = RICIAN_K_EXPECTED.issubset(have)
        if not rt_ready:
            print(f'item5 SKIP: rician table incomplete (have K={sorted(have)}, need {sorted(RICIAN_K_EXPECTED)})', flush=True)
    if rt_ready:
        rt16 = pd.read_csv(RICIAN_TBL)
        rt16 = rt16[(rt16['qam'] == 16) & (rt16['rician_k'].isin(RICIAN_K_EXPECTED))]
        rows5 = []
        for sp in SPLITS:
            ds = datasets[sp]
            ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
            n = len(ds)
            for K in sorted(rt16['rician_k'].unique()):
                s = rt16[rt16['rician_k'] == K].sort_values('esno_db')
                for tag in tags:
                    bd = budgets[tag]
                    rng = np.random.default_rng(CSI_SEED)
                    snr_2d = rng.uniform(0, 20, size=(N_REPLAY, n))
                    _ = rng.random(size=(N_REPLAY, n))                 # keep draw order aligned; channel unused
                    F1 = np.empty(N_REPLAY); B = np.empty(N_REPLAY); RHO = np.empty(N_REPLAY)
                    for r in range(N_REPLAY):
                        bF = np.clip(np.interp(snr_2d[r], s['esno_db'], s['bler_frame'],
                                               left=1.0, right=float(s['bler_frame'].iloc[-1])), 0, 1)
                        big = D._feature_matrix(bd['feat'], ds, snr_2d[r], np.ones(n, bool))   # rayleigh=1
                        act = np.asarray(bd['model'].predict(big), dtype=int)
                        E = np.stack([ego, late, comp * (1 - bF) + ego * bF], axis=1)
                        F1[r] = E[np.arange(n), act].mean(); B[r] = PAYVEC[act].mean(); RHO[r] = float((act == 2).mean())
                    rows5.append(dict(split=sp, budget=float(tag), rician_K=float(K), policy='RF',
                                      F1=round(float(F1.mean()), 5), F1_std=round(float(F1.std()), 5),
                                      payload=round(float(B.mean()), 5), rho_feature=round(float(RHO.mean()), 4)))
                print(f'[rician {sp}] done', flush=True)
        pd.DataFrame(rows5).to_csv(os.path.join(OUT, 'rician_proxy.csv'), index=False)
        rician_done = True

    with open(os.path.join(PROV_DIR, 'PROVENANCE_p3.txt'), 'w') as f:
        f.write('CA-TOSG P3 -- descriptive sensitivity batch (sensitivity.py). DESCRIPTIVE ONLY.\n' + '=' * 80 + '\n')
        f.write(f'manifest: results/manifests/FROZEN_MANIFEST.json ({man["schema"]}, freeze {man["freeze_timestamp"]})\n')
        f.write('Each item = the mainline 200-realisation replay (eval_p2_deploy machinery) under a modified\n'
                'channel/SNR/BLER_L distribution, reusing cached per-frame eff + frozen predict(); no new\n'
                'detection inference. Frozen selectors/delta/tau*/oracle unchanged; main.tex untouched.\n')
        f.write(f'Baseline (uniform SNR, 50/50, BLER_L=0) uses rng(CSI_SEED={CSI_SEED}) in eval_p2_deploy order\n'
                '-> reproduces replay_summary.csv EXACTLY (baseline_sanity.csv).\n')
        f.write('item1 p_rayleigh in {0.75,0.50,0.25}; item2 SNR {uniform, beta25_lowskew=Beta(2,5)x20, '
                'truncgauss_10_5=N(10,5) trunc[0,20]}; item3 flip p in {0,.05,.10,.20} (true channel unchanged, '
                f'flip mask seed={FLIP_SEED}); item4 BLER_L in {{0,.01,.05,.10}} (eff_L only, actions/oracle fixed).\n')
        f.write(f'item5 Rician: {"present -> rician_proxy.csv" if rician_done else "table ABSENT -> SKIPPED"} '
                '(K from table; selector fed channel_is_rayleigh=1; eff_F recomputed under Rician frame-BLER).\n')
        f.write('§8 anti-forcing: expected behaviours are checks, not targets; a miss is reported, not fixed.\n')
    print(f'wrote results/p3_sensitivity/ item1-4 + sanity{"+item5" if rician_done else " (item5 skipped)"} + PROVENANCE_p3.txt')


if __name__ == '__main__':
    main()
