#self+ CA-TOSG P1 DIAGNOSTIC (not for the paper table): leakage-free IN-DISTRIBUTION k-fold two-regime
# edge. Answers whether the +0.03 test-JSCC oracle headroom is capturable by cues WITHIN the split
# (no validate->test shift). Protocol per fold: RF fit + tau* tuned on the K-1 training folds only,
# evaluated on the held-out fold (200-realisation). Held-out per-frame realised F1 is concatenated
# across folds -> every frame scored by a model that never saw it. Reports kfold RF F1 / threshold F1 /
# paired 95% CI + all-L + clairvoyant-oracle headroom, next to the leaky in-sample and clean cross-split.
import os, sys
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *(['..'] * 5)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'peiyi_work/paper1/code/extra_experiments'))
sys.path.insert(0, HERE)
import v3_eval as V
import build_two_regime_edge_clean as B   # _load, _realise, eff_C_of, jscc_grid(cached), TAU_GRID, PAY_*
import _common as C

DATA = B.DATA
K = 5


def kfold_edge(channel, regime, split, feat):
    df, grid, n, late = B._load(channel, split, regime)
    fsnr = df['est_snr_db'].to_numpy()
    b16f = V._bler(fsnr, 16, channel) if regime == 'ldpc' else None
    effC_f = B.eff_C_of(regime, df, grid, fsnr, b16f)
    y = np.where(effC_f > late, 'C', 'L')
    skf = StratifiedKFold(n_splits=K, shuffle=True, random_state=0)
    rf_fm = np.zeros(n); tau_fm = np.zeros(n); rf_pay = np.zeros(n)
    for tr, te in skf.split(df, y):
        dtr = df.iloc[tr].reset_index(drop=True); gtr = grid[tr] if grid is not None else None
        ltr = late[tr]; ntr = len(tr)
        rf = RandomForestClassifier(n_estimators=400, max_depth=10, min_samples_leaf=4,
                                    class_weight='balanced', random_state=0, n_jobs=-1).fit(dtr[feat], y[tr])
        # tune tau* on TRAIN folds only (200-realisation)
        tau_tr = {t: 0.0 for t in B.TAU_GRID}
        for s in range(V.N_SEED):
            snr = np.random.default_rng(s).uniform(0, 20, ntr)
            eff = B._realise(dtr, gtr, ntr, ltr, regime, channel, snr)
            for t in B.TAU_GRID:
                ti = ((snr > t) if channel == 'awgn' else np.zeros(ntr, bool)).astype(int)
                tau_tr[t] += eff[np.arange(ntr), ti].mean()
        best_tau = float(max(tau_tr, key=tau_tr.get))
        # eval on HELD-OUT fold (200-realisation), frozen rf + best_tau
        dte = df.iloc[te].reset_index(drop=True); gte = grid[te] if grid is not None else None
        lte = late[te]; nte = len(te)
        for s in range(V.N_SEED):
            snr = np.random.default_rng(s).uniform(0, 20, nte)
            eff = B._realise(dte, gte, nte, lte, regime, channel, snr)
            d = dte.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = int(channel == 'rayleigh')
            ai = (np.asarray(rf.predict(d[feat])) == 'C').astype(int)
            rf_fm[te] += eff[np.arange(nte), ai]; rf_pay[te] += np.where(ai == 1, B.PAY_C, B.PAY_L)
            ti = ((snr > best_tau) if channel == 'awgn' else np.zeros(nte, bool)).astype(int)
            tau_fm[te] += eff[np.arange(nte), ti]
    rf_fm /= V.N_SEED; tau_fm /= V.N_SEED; rf_pay /= V.N_SEED
    # clairvoyant oracle + all-L headroom (over the same 200 realisations, whole split)
    orc = np.zeros(n)
    for s in range(V.N_SEED):
        snr = np.random.default_rng(s).uniform(0, 20, n)
        eff = B._realise(df, grid, n, late, regime, channel, snr)
        orc += np.maximum(eff[:, 0], eff[:, 1])
    orc /= V.N_SEED
    d_edge, lo, hi = V.paired_ci_frames_from(rf_fm, tau_fm)
    return dict(channel=channel, regime=regime, split=split, n=n,
                all_L=round(float(late.mean()), 4), oracle=round(float(orc.mean()), 4),
                oracle_headroom=round(float(orc.mean() - late.mean()), 4),
                kfold_rf_f1=round(float(rf_fm.mean()), 4),
                kfold_threshold_f1=round(float(tau_fm.mean()), 4),
                kfold_edge=round(d_edge, 5), edge_ci_lo=round(lo, 5), edge_ci_hi=round(hi, 5),
                edge_significant=bool(lo > 0 or hi < 0), kfold_rf_payload=round(float(rf_pay.mean()), 4))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--channels', default='awgn,rayleigh,ofdm')
    ap.add_argument('--regimes', default='ldpc,jscc')
    ap.add_argument('--splits', default='test')
    ap.add_argument('--out', default=os.path.join(B.OUT, 'two_regime_kfold_diag.csv'))
    o = ap.parse_args()
    feat = C.feat_cols(pd.read_csv(os.path.join(DATA, 'dataset_validate_v3.csv')), 'full')
    rows = []
    for ch in o.channels.split(','):
        for regime in o.regimes.split(','):
            for sp in o.splits.split(','):
                try:
                    r = kfold_edge(ch, regime, sp, feat); rows.append(r)
                    print(f"[{ch} {regime} {sp}] kfoldRF {r['kfold_rf_f1']} vs allL {r['all_L']} "
                          f"(oracle {r['oracle']}, headroom {r['oracle_headroom']:+.4f}) | "
                          f"edge {r['kfold_edge']:+.5f} CI[{r['edge_ci_lo']:+.5f},{r['edge_ci_hi']:+.5f}] "
                          f"{'SIG' if r['edge_significant'] else 'ns'}", flush=True)
                except Exception as e:
                    import traceback; print(f"[{ch} {regime} {sp}] SKIP: {e}"); traceback.print_exc()
    out = pd.DataFrame(rows)
    out.to_csv(o.out, index=False)
    print('\nwrote', o.out); print(out.to_string(index=False))


if __name__ == '__main__':
    main()
