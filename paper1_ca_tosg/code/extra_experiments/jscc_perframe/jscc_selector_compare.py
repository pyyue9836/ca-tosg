#self+ The payoff experiment: under graceful JSCC (no SNR cliff), does a learned
# selector using perception cues beat a pure SNR-threshold rule?
"""
Thesis: with LDPC+QAM the channel has a sharp cliff, so the estimated SNR is a
near-sufficient statistic and an SNR threshold matches the RF (a9). With JSCC the
feature F1 degrades gracefully, so whether a feature message beats the object-level
message on a given frame depends on the FRAME CONTENT (its late_f1), not only on SNR.
A pure SNR threshold ignores content; the RF, via its perception cues, should sit
ABOVE the threshold's realised-F1 vs feature-rate frontier.

Inputs (all per-frame, validate split, frames 0..N-1):
  - runs/v2/dataset.csv ............ cues + late_f1 (= F1 of object-level L)
  - out/jscc_perframe_jscc_awgn.csv  per-frame JSCC feature F1 at an SNR grid

Protocol mirrors a9: N_SEED Monte-Carlo draws of per-frame SNR ~ U[0,20] (AWGN).
For each seed: eff_L = late_f1 (channel-invariant); eff_C = jscc_f1(snr) interpolated
per frame; oracle = argmax. 70/30 frame split, RF trained on oracle labels with
[cues, est_snr]; evaluate realised F1 and feature-send rate on the held-out frames.
Threshold rule 'C if snr>tau' swept over tau on the same held-out frames.

Verdict = RF realised F1 minus the best threshold F1 achievable at <= RF's feature
rate (matched payload). Positive and CI-excluding-0 => perception cues help under JSCC.

Run: PYTHONPATH=. <sionna310 python> jscc_selector_compare.py   (after the sweep)
"""
import os
import sys
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))     # 01_paper_ca_tosg
sys.path.insert(0, os.path.join(ROOT, 'extra_experiments'))
import _common as C  # noqa: E402

N_SEED = 200
TAUS = np.arange(0, 21, 1.0)
IOU = '05'   # use jscc_f1_05


def build_interp(jscc_csv):
    """per-frame callable jscc_f1(snr) via linear interp over the SNR grid."""
    j = pd.read_csv(jscc_csv)
    grid = np.sort(j['snr_db'].unique())
    piv = j.pivot_table(index='sample_id', columns='snr_db',
                        values=f'jscc_f1_{IOU}').sort_index()
    piv = piv[grid]                       # columns in SNR order
    frames = piv.index.to_numpy()
    M = piv.to_numpy()                    # (frame, snr_grid)
    def interp(snr_per_frame):
        out = np.empty(len(frames))
        for k in range(len(frames)):
            out[k] = np.interp(snr_per_frame[k], grid, M[k])
        return out
    return frames, grid, interp


def eval_seed(df, late_f1, cues, interp, rng):
    n = len(df)
    snr = rng.uniform(0, 20, n)
    eff_C = interp(snr)
    eff_L = late_f1
    oracle = np.where(eff_C > eff_L, 'C', 'L')
    eff = np.stack([eff_L, eff_C], 1)            # cols: L, C
    ai = {'L': 0, 'C': 1}
    oi = np.array([ai[a] for a in oracle])

    X = np.column_stack([cues, snr])
    # 70/30 split
    idx = rng.permutation(n); cut = int(0.7 * n)
    tr, te = idx[:cut], idx[cut:]
    rf = RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=4,
                                class_weight='balanced', random_state=0, n_jobs=-1)
    rf.fit(X[tr], oracle[tr])
    pred = rf.predict(X[te])
    pi = np.array([ai[a] for a in pred])

    def realised(action_idx, rows):
        return eff[rows, action_idx].mean()
    rf_f1 = realised(pi, te); rf_rho = (pred == 'C').mean()
    or_f1 = realised(oi[te], te)
    L_f1 = eff_L[te].mean()
    # threshold frontier on the same held-out frames
    thr = []
    for t in TAUS:
        ti = (snr[te] > t).astype(int)
        thr.append((t, eff[te, ti].mean(), ti.mean()))
    thr = np.array(thr)   # (tau, f1, rho)
    # best threshold F1 at feature-rate <= rf_rho (matched-or-cheaper payload)
    elig = thr[thr[:, 2] <= rf_rho + 1e-9]
    best_thr_f1 = elig[:, 1].max() if len(elig) else thr[:, 1].min()
    return dict(rf_f1=rf_f1, rf_rho=rf_rho, or_f1=or_f1, L_f1=L_f1,
                best_thr_f1=best_thr_f1, edge=rf_f1 - best_thr_f1), thr


def ci(x):
    return float(np.mean(x)), float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--channel', default='awgn', choices=['awgn', 'rayleigh', 'ofdm'])
    args = ap.parse_args()
    jscc_csv = os.path.join(HERE, 'out', f'jscc_perframe_jscc_{args.channel}.csv')
    if not os.path.exists(jscc_csv):
        sys.exit(f'[WAIT] {jscc_csv} not ready yet (sweep still running).')
    print(f'### channel = {args.channel} ###')
    frames, grid, interp = build_interp(jscc_csv)

    df = pd.read_csv(C.VAL_CSV)
    df = df[df['sample_id'].isin(frames)].sort_values('sample_id').reset_index(drop=True)
    assert np.array_equal(df['sample_id'].to_numpy(), frames), 'frame misalignment'
    cue_cols = [c for c in C.feat_cols(df, 'full') if c not in ('est_snr_db', 'channel_is_rayleigh')]
    print(f'frames={len(df)}  cues={len(cue_cols)}  snr grid={list(grid)}')
    late_f1 = df['late_f1'].to_numpy()
    cues = df[cue_cols].to_numpy()

    recs, thr_all = [], []
    for s in range(N_SEED):
        r, thr = eval_seed(df, late_f1, cues, interp, np.random.default_rng(s))
        recs.append(r); thr_all.append(thr)
    R = pd.DataFrame(recs)

    print('\n=== JSCC selector vs SNR-threshold (AWGN, %d seeds, 95%% CI) ===' % N_SEED)
    for k in ['rf_f1', 'rf_rho', 'or_f1', 'L_f1', 'best_thr_f1', 'edge']:
        m, lo, hi = ci(R[k])
        print(f'  {k:12s} {m:.4f}  [{lo:.4f}, {hi:.4f}]')
    m, lo, hi = ci(R['edge'])
    verdict = 'SIGNIFICANT: cues beat threshold under JSCC' if lo > 0 else \
              ('threshold still matches RF' if hi > 0 else 'threshold BEATS RF')
    print(f'\n  VERDICT (edge = RF F1 - best threshold F1 at matched feature-rate): {verdict}')

    out = os.path.join(HERE, 'out', f'jscc_selector_compare_{args.channel}.csv')
    rows = [dict(metric=k, mean=ci(R[k])[0], ci_lo=ci(R[k])[1], ci_hi=ci(R[k])[2])
            for k in ['rf_f1', 'rf_rho', 'or_f1', 'L_f1', 'best_thr_f1', 'edge']]
    pd.DataFrame(rows).to_csv(out, index=False)
    # seed-averaged threshold frontier for plotting
    T = np.array(thr_all).mean(0)
    pd.DataFrame(dict(tau=T[:, 0], thr_f1=T[:, 1], thr_rho=T[:, 2])).to_csv(
        os.path.join(HERE, 'out', f'jscc_threshold_frontier_{args.channel}.csv'), index=False)
    print('[DONE] wrote', out)


if __name__ == '__main__':
    main()
