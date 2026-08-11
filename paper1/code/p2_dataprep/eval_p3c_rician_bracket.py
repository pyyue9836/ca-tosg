#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-C Rician BRACKETING variant (Change-log P3-C). DESCRIPTIVE; "bracketing variant, not deployed behavior".

Same frozen selector, same 200-realisation replay system + seed as item 5; the ONLY change is the
selector is fed channel_is_rayleigh = 0 (all other features unchanged), so it treats the Rician link as
AWGN-like and IS WILLING to request F on SNR/cue grounds. Delivery success/failure is then adjudicated by
the TRUE Rician frame-BLER (results/bler_sionna/bler_sionna_rician.csv, K in {0,3,10}). This is the
OPPORTUNISTIC bound; item 5 (channel_is_rayleigh=1, always-defer) is the CONSERVATIVE bound. Together they
bracket the potential gain of a K-aware selector. No change to frozen models / oracle / delta / tau*;
main.tex untouched; no new detection inference (cached eff + frozen predict()).

Outputs (results/p3_sensitivity/):
  item5c_rician_rayleigh0.csv  -- 200-replay aggregate (same seed), per split x budget x K: F1/std,
                                  payload, rho_feature (directly comparable to item5_rician.csv).
  item5c_rician_by_snr.csv     -- deterministic per split x budget x K x SNR sweep (analytic eff): shows
                                  the onset behaviour (F delivered above onset for K=10; failed/fallback
                                  below onset for K=0/3).
Run:  /path/to/env/python paper1/code/p2_dataprep/eval_p3c_rician_bracket.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_p2_deploy as D

P1 = D.P1
OUT = os.path.join(P1, 'results/p3_sensitivity')
RICIAN_TBL = os.path.join(P1, 'results/bler_sionna/bler_sionna_rician.csv')
PAYVEC = D.PAYVEC
SPLITS = D.SPLITS
SNR_GRID = np.array(D.SNR_GRID, dtype=float)
N_REPLAY = D.N_REPLAY
CSI_SEED = D.CSI_SEED
LABEL = 'bracketing variant / not deployed behavior'
K_EXPECTED = {0.0, 3.0, 10.0}


def rician_bF(s_tbl, snr):
    """16-QAM Rician frame-BLER interpolated at snr (dB) for one K's sorted sub-table."""
    return np.clip(np.interp(snr, s_tbl['esno_db'], s_tbl['bler_frame'],
                             left=1.0, right=float(s_tbl['bler_frame'].iloc[-1])), 0, 1)


def main():
    if not os.path.exists(RICIAN_TBL):
        raise SystemExit('P3-C FUSE: rician table absent -- run build_bler_sionna.py --rician_K 0,3,10 first.')
    os.makedirs(OUT, exist_ok=True)
    man, budgets = D.load_manifest()
    tags = sorted(budgets)
    rt = pd.read_csv(RICIAN_TBL)
    rt16 = rt[(rt['qam'] == 16) & (rt['rician_k'].isin(K_EXPECTED))]
    have = set(rt16['rician_k'].unique().tolist())
    if not K_EXPECTED.issubset(have):
        raise SystemExit(f'P3-C FUSE: rician table incomplete (have K={sorted(have)}, need {sorted(K_EXPECTED)})')
    datasets = {sp: pd.read_csv(os.path.join(D.DATA, D.DATASET[sp])) for sp in SPLITS}

    agg_rows, snr_rows = [], []
    for sp in SPLITS:
        ds = datasets[sp]
        ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
        n = len(ds)
        cue_cols = None
        for K in sorted(K_EXPECTED):
            s = rt16[rt16['rician_k'] == K].sort_values('esno_db')
            for tag in tags:
                bd = budgets[tag]
                if cue_cols is None:
                    cue_cols = [c for c in bd['feat'] if c not in ('est_snr_db', 'channel_is_rayleigh')]

                # --- (A) 200-replay aggregate, SAME seed as item5, but fed channel_is_rayleigh=0 ---
                rng = np.random.default_rng(CSI_SEED)
                snr_2d = rng.uniform(0, 20, size=(N_REPLAY, n))
                _ = rng.random(size=(N_REPLAY, n))                      # keep draw order aligned w/ item5
                F1 = np.empty(N_REPLAY); B = np.empty(N_REPLAY); RHO = np.empty(N_REPLAY)
                for r in range(N_REPLAY):
                    bF = rician_bF(s, snr_2d[r])
                    big = D._feature_matrix(bd['feat'], ds, snr_2d[r], np.zeros(n, bool))   # rayleigh=0
                    act = np.asarray(bd['model'].predict(big), dtype=int)
                    E = np.stack([ego, late, comp * (1 - bF) + ego * bF], axis=1)
                    F1[r] = E[np.arange(n), act].mean(); B[r] = PAYVEC[act].mean(); RHO[r] = float((act == 2).mean())
                agg_rows.append(dict(split=sp, budget=float(tag), rician_K=float(K), feed='rayleigh=0',
                                     policy='RF', F1=round(float(F1.mean()), 5), F1_std=round(float(F1.std()), 5),
                                     payload=round(float(B.mean()), 5), rho_feature=round(float(RHO.mean()), 4),
                                     note=LABEL))

                # --- (B) deterministic per-SNR sweep (analytic eff), fed channel_is_rayleigh=0 ---
                base = ds[cue_cols].to_numpy()
                for snr in SNR_GRID:
                    bF = float(rician_bF(s, np.array([snr]))[0])
                    big = np.empty((n, len(bd['feat'])))
                    big[:, [bd['feat'].index(c) for c in cue_cols]] = base
                    big[:, bd['feat'].index('est_snr_db')] = snr
                    big[:, bd['feat'].index('channel_is_rayleigh')] = 0
                    act = np.asarray(bd['model'].predict(big), dtype=int)
                    E = np.stack([ego, late, comp * (1 - bF) + ego * bF], axis=1)
                    rho_req = float((act == 2).mean())                  # F REQUEST rate (pre-delivery)
                    snr_rows.append(dict(split=sp, budget=float(tag), rician_K=float(K), snr_db=float(snr),
                                         feed='rayleigh=0', bler_F=round(bF, 4),
                                         F1=round(float(E[np.arange(n), act].mean()), 5),
                                         payload=round(float(PAYVEC[act].mean()), 5),
                                         rho_feature_request=round(rho_req, 4), note=LABEL))
        print(f'[{sp}] done', flush=True)

    pd.DataFrame(agg_rows).to_csv(os.path.join(OUT, 'item5c_rician_rayleigh0.csv'), index=False)
    pd.DataFrame(snr_rows).to_csv(os.path.join(OUT, 'item5c_rician_by_snr.csv'), index=False)

    # append a note to the P3 provenance (do not clobber the existing item1-5 provenance)
    with open(os.path.join(OUT, 'PROVENANCE_p3.txt'), 'a') as f:
        f.write('\n[P3-C, 2026-08-11] Rician BRACKETING variant (eval_p3c_rician_bracket.py). '
                f'"{LABEL}".\n')
        f.write('  Same frozen selectors + 200-replay seed as item5; ONLY change = selector fed '
                'channel_is_rayleigh=0 (opportunistic bound). Delivery adjudicated by the TRUE Rician '
                'frame-BLER (K in {0,3,10}); item5 (rayleigh=1) = conservative bound. The two bracket a '
                'K-aware selector.\n')
        f.write('  item5c_rician_rayleigh0.csv = 200-replay aggregate; item5c_rician_by_snr.csv = '
                'deterministic per-(K,SNR) sweep (rho_feature_request = pre-delivery F request rate; '
                'bler_F = true Rician frame-BLER). No frozen model/oracle/delta/tau* change; main.tex untouched.\n')
    print('wrote results/p3_sensitivity/{item5c_rician_rayleigh0.csv, item5c_rician_by_snr.csv} + PROVENANCE note')


if __name__ == '__main__':
    main()
