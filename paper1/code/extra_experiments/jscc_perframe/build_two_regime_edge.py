#self+ CA-TOSG P1 Step-5 Track A: two-regime task-cue EDGE (JSCC graceful vs LDPC cliff), v3 GT,
# 200-realisation, board-3 frame-level paired CI. "Edge" = RF realised F1 - best-threshold realised F1
# on the SAME channel regime; the currency question (accuracy vs bandwidth) is read from F1 + payload.
"""
For a (channel, split): the regime fixes the channel; per realisation draw snr~U[0,20]; the selector
chooses between L (late) and C (feature-level).
  JSCC regime : eff_C(frame, snr) = per-frame JSCC F1 interpolated over the 6-pt SNR grid (graceful,
                no cliff). JSCC delivers a graded feature message -- no BLER/ego fallback (that is the
                point of the digital-vs-analog contrast).
  LDPC regime : eff_C(frame, snr) = comp*(1-BLER_sionna(snr)) + ego*BLER  (cliff + ego fallback, v3).
2-way oracle (per regime) is trained ONCE on the frozen est_snr labels (labels fixed); EVAL is
200-realisation. Reports RF F1 / best-tau-threshold F1 / their frame-level paired 95% CI, + payloads.
Interpolation systematic term (JSCC side only): aggregate bias <=0.0012 (mid-grid probe), attached here.
Outputs: results/jscc_v3/two_regime_edge_v3.csv (appends per channel,split,regime).
"""
import os, sys
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, *(['..'] * 5)))
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, 'peiyi_work/paper1/code/extra_experiments'))
sys.path.insert(0, HERE)
import v3_eval as V
import score_jscc_v3 as SC

P1 = os.path.join(REPO, 'peiyi_work/paper1'); DATA = os.path.join(P1, 'data')
JSCC_DIR = os.path.join(P1, 'gs_rerun/jscc_v3'); OUT = os.path.join(P1, 'results/jscc_v3')
SNR_GRID = np.array([0, 4, 8, 12, 16, 20], float)
PAY_L, PAY_C = 0.024, 1.98 / 4.0   # L vs one feature-level message (C16-equivalent channel use)
TAU_GRID = np.round(np.arange(0.0, 20.0001, 0.5), 3)
INTERP_BIAS = 0.0012
CUES = None  # set from dataset feature columns


def jscc_grid(channel, split):
    canon = SC.canon_of(split); n = None; cols = []
    for snr in SNR_GRID:
        p = os.path.join(JSCC_DIR, f'jscc_{channel}_{split}_snr{int(snr):02d}.npz')
        pf, m = SC.perframe_f1(p, canon); cols.append(pf); n = m if n is None else min(n, m)
    return np.stack([c[:n] for c in cols], axis=1), n     # (n, 6) per-frame JSCC F1 over the grid


def interp_rows(grid, snr):
    """Per-frame linear interp of the JSCC F1 curve at each frame's drawn snr. grid (n,6), snr (n,)."""
    return np.array([np.interp(snr[i], SNR_GRID, grid[i]) for i in range(len(snr))])


def eff_C_of(regime, df, grid, snr, b16=None):
    late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy(); ego = df['ego_f1'].to_numpy()
    if regime == 'jscc':
        return interp_rows(grid, snr)
    return comp * (1 - b16) + ego * b16                    # ldpc, v3 ego fallback


def edge(channel, split, regime, feat):
    df = pd.read_csv(os.path.join(DATA, f'dataset_{split}_v3.csv'))
    grid, n = (jscc_grid(channel, split) if regime == 'jscc' else (None, len(df)))
    df = df.iloc[:n].reset_index(drop=True)
    late = df['late_f1'].to_numpy()
    # frozen 2-way oracle labels (at the dataset's frozen est_snr, this channel)
    fsnr = df['est_snr_db'].to_numpy()
    b16f = V._bler(fsnr, 16, channel)
    effC_f = eff_C_of(regime, df, grid, fsnr, b16f)
    y = np.where(effC_f > late, 'C', 'L')
    rf = RandomForestClassifier(n_estimators=400, max_depth=10, min_samples_leaf=4,
                                class_weight='balanced', random_state=0, n_jobs=-1).fit(df[feat], y)
    # 200-realisation eval on this fixed-channel regime
    rf_fm = np.zeros(n); tau_fm = {t: np.zeros(n) for t in TAU_GRID}
    rf_pay = np.zeros(n)
    for s in range(V.N_SEED):
        rng = np.random.default_rng(s); snr = rng.uniform(0, 20, n)
        b16 = V._bler(snr, 16, channel)
        effC = eff_C_of(regime, df, grid, snr, b16)
        eff = np.stack([late, effC], 1)
        d = df.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = int(channel == 'rayleigh')
        ai = (np.asarray(rf.predict(d[feat])) == 'C').astype(int)
        rf_fm += eff[np.arange(n), ai]; rf_pay += np.where(ai == 1, PAY_C, PAY_L)
        for t in TAU_GRID:
            ti = ((snr > t) if channel == 'awgn' else np.zeros(n, bool)).astype(int)
            tau_fm[t] += eff[np.arange(n), ti]
    rf_fm /= V.N_SEED; rf_pay /= V.N_SEED
    tau_mean = {t: tau_fm[t].mean() / V.N_SEED for t in TAU_GRID}
    best_tau = max(tau_mean, key=tau_mean.get); tau_best_fm = tau_fm[best_tau] / V.N_SEED
    d_edge, lo, hi = V.paired_ci_frames_from(rf_fm, tau_best_fm)
    return dict(channel=channel, split=split, regime=regime, n=n,
                rf_f1=round(float(rf_fm.mean()), 4), best_tau=float(best_tau),
                threshold_f1=round(float(tau_best_fm.mean()), 4),
                edge_rf_minus_threshold=round(d_edge, 5), edge_ci_lo=round(lo, 5), edge_ci_hi=round(hi, 5),
                edge_significant=bool(lo > 0 or hi < 0), rf_payload=round(float(rf_pay.mean()), 4),
                interp_bias=(INTERP_BIAS if regime == 'jscc' else 0.0))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--channels', default='awgn'); ap.add_argument('--splits', default='validate,test')
    o = ap.parse_args()
    sample = pd.read_csv(os.path.join(DATA, 'dataset_validate_v3.csv'))
    import _common as C
    feat = C.feat_cols(sample, 'full')
    rows = []
    for ch in o.channels.split(','):
        for sp in o.splits.split(','):
            for regime in ('ldpc', 'jscc'):
                try:
                    r = edge(ch, sp, regime, feat); rows.append(r)
                    print(f"[{ch} {sp} {regime}] RF {r['rf_f1']}@{r['rf_payload']} vs tau{r['best_tau']} "
                          f"{r['threshold_f1']} | edge {r['edge_rf_minus_threshold']:+.5f} "
                          f"CI[{r['edge_ci_lo']:+.5f},{r['edge_ci_hi']:+.5f}] {'SIG' if r['edge_significant'] else 'ns'}", flush=True)
                except Exception as e:
                    print(f"[{ch} {sp} {regime}] SKIP: {e}", flush=True)
    out = pd.DataFrame(rows)
    path = os.path.join(OUT, 'two_regime_edge_v3.csv')
    if os.path.exists(path):
        out = pd.concat([pd.read_csv(path), out]).drop_duplicates(['channel', 'split', 'regime'], keep='last')
    out.to_csv(path, index=False)
    print('\nwrote', path); print(out.to_string(index=False))


if __name__ == '__main__':
    main()
