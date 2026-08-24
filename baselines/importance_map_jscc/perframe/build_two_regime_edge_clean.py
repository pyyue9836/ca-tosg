#self+ CA-TOSG P1 v3 CLEAN PROTOCOL two-regime edge (supervisor fix: no train/tune-on-eval leakage).
# Difference vs build_two_regime_edge.py: there the RF was fit AND best_tau chosen on the SAME split
# it evaluated (test/culver rows self-trained + threshold self-tuned -> optimistic edge). Here the
# selector is DOUBLE-FROZEN on validate:
#   (1) oracle labels built at validate's frozen est_snr; RF fit on validate features,
#   (2) tau* chosen on validate 200-realisation realised F1,
# then BOTH the frozen RF and frozen tau* are applied UNCHANGED to test + culver (out-of-sample).
# Eval = 200-realisation; reports RF F1 / frozen-tau-threshold F1 / frame-level paired 95% CI + payload.
# validate rows are reported too (in-sample, marked eval_split=validate) as the sanity anchor.
"""
Regimes (identical eff_C model to build_two_regime_edge.py -- only the train/eval separation changed):
  jscc : eff_C(frame,snr) = per-frame JSCC F1 linearly interpolated over the 6-pt SNR grid (graceful,
         no cliff, no ego fallback -- the analog-vs-digital contrast).
  ldpc : eff_C(frame,snr) = comp*(1-BLER16(snr)) + ego*BLER16(snr)  (cliff + ego fallback, v3).
The threshold baseline is AWGN-only by construction (an instantaneous-SNR gate has no CSI under
fading) -> for rayleigh/ofdm the threshold policy degenerates to all-L; tau* is then a no-op. This
matches build_two_regime_edge.py exactly; only the leakage is removed.
Output: results/baselines/importance_map_jscc/two_regime_edge_clean.csv (one row per channel,regime,eval_split).
"""
import os, sys
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *(['..'] * 5)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'peiyi_work/paper1/code/extra_experiments'))
sys.path.insert(0, HERE)
# --- ca-tosg layout bootstrap (restructure commit 2/4) ---
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/evaluation/ablations', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
# --- end bootstrap ---
import v3_eval as V
import score_jscc as SC
# reuse the EXACT eff_C model + constants from the leaky script (single source of truth). jscc_grid
# is overridden below to read the cached per-frame F1 npz (score_jscc.py output) instead of
# re-scoring from the decode npz -- same values, ~100x faster.
# R67-a: the shared pieces come from the common module, not from the leaky script this file
# replaces -- importing them from there made the clean arm depend on the arm that leaks.
from two_regime_common import (jscc_grid as _jscc_grid_rescore, eff_C_of, SNR_GRID,
                               PAY_L, PAY_C, TAU_GRID, INTERP_BIAS)

P1 = os.path.join(REPO, 'peiyi_work/paper1'); DATA = os.path.join(P1, 'data')
OUT = os.path.join(P1, 'results/baselines/importance_map_jscc')
TRAIN_SPLIT = 'validate'


def jscc_grid(channel, split):
    """(n,6) per-frame JSCC F1 over the SNR grid, from cached jscc_perframe_f1_*.npz if present
    (identical to score_jscc.perframe_f1), else fall back to re-scoring the decode npz."""
    cols, n = [], None
    for snr in SNR_GRID:
        cache = os.path.join(OUT, f'jscc_perframe_f1_{channel}_{split}_snr{int(snr):02d}.npz')
        if os.path.exists(cache):
            pf = np.load(cache)['f1']
        else:
            return _jscc_grid_rescore(channel, split)   # any cache missing -> rescore whole grid
        cols.append(pf); n = len(pf) if n is None else min(n, len(pf))
    return np.stack([c[:n] for c in cols], axis=1), n


def _load(channel, split, regime):
    """Return (df, grid, n, late) for a (channel, split, regime); grid is None for ldpc."""
    df = pd.read_csv(os.path.join(DATA, f'dataset_{split}_v3.csv'))
    grid, n = (jscc_grid(channel, split) if regime == 'jscc' else (None, len(df)))
    df = df.iloc[:n].reset_index(drop=True)
    return df, grid, n, df['late_f1'].to_numpy()


def _realise(df, grid, n, late, regime, channel, snr):
    """eff array (n,2) = [late, eff_C] at a drawn per-frame snr vector."""
    b16 = V._bler(snr, 16, channel) if regime == 'ldpc' else None
    effC = eff_C_of(regime, df, grid, snr, b16)
    return np.stack([late, effC], axis=1)


def train_frozen(channel, regime, feat):
    """Fit RF on validate oracle labels (frozen est_snr) + pick tau* on validate 200-realisation F1."""
    df, grid, n, late = _load(channel, TRAIN_SPLIT, regime)
    fsnr = df['est_snr_db'].to_numpy()
    b16f = V._bler(fsnr, 16, channel) if regime == 'ldpc' else None
    effC_f = eff_C_of(regime, df, grid, fsnr, b16f)
    y = np.where(effC_f > late, 'C', 'L')
    rf = RandomForestClassifier(n_estimators=400, max_depth=10, min_samples_leaf=4,
                                class_weight='balanced', random_state=0, n_jobs=-1).fit(df[feat], y)
    # tau* by validate 200-realisation realised F1 (threshold gate: awgn only, else all-L)
    tau_fm = {t: np.zeros(n) for t in TAU_GRID}
    for s in range(V.N_SEED):
        rng = np.random.default_rng(s); snr = rng.uniform(0, 20, n)
        eff = _realise(df, grid, n, late, regime, channel, snr)
        for t in TAU_GRID:
            ti = ((snr > t) if channel == 'awgn' else np.zeros(n, bool)).astype(int)
            tau_fm[t] += eff[np.arange(n), ti]
    tau_mean = {t: tau_fm[t].mean() / V.N_SEED for t in TAU_GRID}
    best_tau = float(max(tau_mean, key=tau_mean.get))
    return rf, best_tau


def eval_frozen(channel, regime, eval_split, feat, rf, best_tau):
    """Apply frozen RF + frozen tau* to eval_split; 200-realisation, frame-level paired CI."""
    df, grid, n, late = _load(channel, eval_split, regime)
    rf_fm = np.zeros(n); tau_fm = np.zeros(n); rf_pay = np.zeros(n)
    for s in range(V.N_SEED):
        rng = np.random.default_rng(s); snr = rng.uniform(0, 20, n)
        eff = _realise(df, grid, n, late, regime, channel, snr)
        d = df.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = int(channel == 'rayleigh')
        ai = (np.asarray(rf.predict(d[feat])) == 'C').astype(int)
        rf_fm += eff[np.arange(n), ai]; rf_pay += np.where(ai == 1, PAY_C, PAY_L)
        ti = ((snr > best_tau) if channel == 'awgn' else np.zeros(n, bool)).astype(int)
        tau_fm += eff[np.arange(n), ti]
    rf_fm /= V.N_SEED; tau_fm /= V.N_SEED; rf_pay /= V.N_SEED
    d_edge, lo, hi = V.paired_ci_frames_from(rf_fm, tau_fm)
    return dict(channel=channel, regime=regime, eval_split=eval_split, train_split=TRAIN_SPLIT, n=n,
                rf_f1=round(float(rf_fm.mean()), 4), frozen_tau=best_tau,
                threshold_f1=round(float(tau_fm.mean()), 4),
                edge_rf_minus_threshold=round(d_edge, 5), edge_ci_lo=round(lo, 5), edge_ci_hi=round(hi, 5),
                edge_significant=bool(lo > 0 or hi < 0), rf_payload=round(float(rf_pay.mean()), 4),
                interp_bias=(INTERP_BIAS if regime == 'jscc' else 0.0))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--channels', default='awgn,rayleigh,ofdm')
    ap.add_argument('--regimes', default='ldpc,jscc')
    ap.add_argument('--eval_splits', default='validate,test,culver')
    ap.add_argument('--out', default=os.path.join(OUT, 'two_regime_edge_clean.csv'))
    o = ap.parse_args()
    import _common as C
    feat = C.feat_cols(pd.read_csv(os.path.join(DATA, 'dataset_validate_v3.csv')), 'full')
    rows = []
    for ch in o.channels.split(','):
        for regime in o.regimes.split(','):
            try:
                rf, tau = train_frozen(ch, regime, feat)
                print(f"[FROZEN {ch} {regime}] tau*={tau} on {TRAIN_SPLIT}", flush=True)
            except Exception as e:
                print(f"[FROZEN {ch} {regime}] SKIP train: {e}", flush=True); continue
            for sp in o.eval_splits.split(','):
                try:
                    r = eval_frozen(ch, regime, sp, feat, rf, tau); rows.append(r)
                    print(f"  [{ch} {regime} -> {sp}] RF {r['rf_f1']}@{r['rf_payload']} vs tau{r['frozen_tau']} "
                          f"{r['threshold_f1']} | edge {r['edge_rf_minus_threshold']:+.5f} "
                          f"CI[{r['edge_ci_lo']:+.5f},{r['edge_ci_hi']:+.5f}] "
                          f"{'SIG' if r['edge_significant'] else 'ns'}", flush=True)
                except Exception as e:
                    print(f"  [{ch} {regime} -> {sp}] SKIP eval: {e}", flush=True)
    out = pd.DataFrame(rows)
    if os.path.exists(o.out):
        out = pd.concat([pd.read_csv(o.out), out]).drop_duplicates(
            ['channel', 'regime', 'eval_split'], keep='last')
    order = ['channel', 'regime', 'eval_split', 'train_split', 'n', 'rf_f1', 'frozen_tau',
             'threshold_f1', 'edge_rf_minus_threshold', 'edge_ci_lo', 'edge_ci_hi',
             'edge_significant', 'rf_payload', 'interp_bias']
    out = out[[c for c in order if c in out.columns]]
    out.to_csv(o.out, index=False)
    print('\nwrote', o.out); print(out.to_string(index=False))


if __name__ == '__main__':
    main()
