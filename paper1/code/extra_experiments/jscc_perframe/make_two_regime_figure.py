#self+ Two-regime figure: WHEN do task-oriented perception cues matter?
# (a) feature F1 vs SNR -- LDPC cliff (SNR informative) vs JSCC flat (SNR uninformative)
# (b) realised F1 of {Fixed-L, best SNR-threshold, RF (ours), oracle} per regime, same
#     validate frames 0..999, same 200-seed AWGN protocol. Threshold ~= RF under LDPC
#     (cues redundant); threshold ~= Fixed-L < RF under JSCC (only cues win).
"""
Run: PYTHONPATH=. <sionna310 py> make_two_regime_figure.py
Outputs: paper/figures/fig_two_regime.pdf (+ _preview.png) and
         out/two_regime_bars.csv (the plotted numbers).
"""
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'extra_experiments'))
import _common as C  # noqa: E402
PS = C.PS

N_SEED = 200
TAUS = np.arange(0, 21, 1.0)
# panel-(a) cliff uses BE.V._bler (Sionna v3), not the old v2 ldpc_qam_bler_table.csv;
# the module-level table load + bler16 helper are retired with the v3 rewire.


def ci(x):
    return np.mean(x), np.percentile(x, 2.5), np.percentile(x, 97.5)


def eval_regime(df, cues, late_f1, eff_C_fn, rng_seed):
    """One 200-seed AWGN comparison; eff_C_fn(snr)->per-frame feature F1."""
    n = len(df)
    recs = []
    for s in range(N_SEED):
        rng = np.random.default_rng(rng_seed + s)
        snr = rng.uniform(0, 20, n)
        eff_C = eff_C_fn(snr)
        eff = np.stack([late_f1, eff_C], 1)
        oracle = np.where(eff_C > late_f1, 'C', 'L')
        X = np.column_stack([cues, snr])
        idx = rng.permutation(n); cut = int(0.7 * n); tr, te = idx[:cut], idx[cut:]
        rf = RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=4,
                                    class_weight='balanced', random_state=0, n_jobs=-1)
        rf.fit(X[tr], oracle[tr])
        pred = rf.predict(X[te]); pi = (pred == 'C').astype(int)
        rf_f1 = eff[te, pi].mean(); rf_rho = pi.mean()
        oi = (oracle[te] == 'C').astype(int)
        thr = np.array([[t, eff[te, (snr[te] > t).astype(int)].mean(),
                         (snr[te] > t).mean()] for t in TAUS])
        elig = thr[thr[:, 2] <= rf_rho + 1e-9]
        best_thr = elig[:, 1].max() if len(elig) else thr[:, 1].min()
        recs.append(dict(L=late_f1[te].mean(), thr=best_thr, RF=rf_f1,
                         oracle=eff[te, oi].mean(), edge=rf_f1 - best_thr))
    return pd.DataFrame(recs)


def main():
    # v3 rewire: TEST split, reusing build_two_regime_edge's EXACT mechanism so the figure's edges bit-
    # reproduce two_regime_edge_v3 (RF random_state=0, TAU_GRID, 200-seed, PAY 0.024/0.99 -- all in BE).
    import build_two_regime_edge as BE
    SPLIT, CH = 'test', 'awgn'
    df = pd.read_csv(os.path.join(BE.DATA, f'dataset_{SPLIT}_v3.csv')).reset_index(drop=True)
    feat = C.feat_cols(df, 'full')
    late_f1 = df['late_f1'].to_numpy(); comp_f1 = df['compressed_f1'].to_numpy()
    piv, njscc = BE.jscc_grid(CH, SPLIT)            # (n x 6) per-frame JSCC F1 at BE.SNR_GRID (test npz)
    grid = BE.SNR_GRID

    # --- aggregates via the SAME function as two_regime_edge_v3 (spec 1: bit-reproduce; spec 2: same seed/protocol) ---
    r_ldpc = BE.edge(CH, SPLIT, 'ldpc', feat)
    r_jscc = BE.edge(CH, SPLIT, 'jscc', feat)
    ref = pd.read_csv(os.path.join(BE.OUT, 'two_regime_edge_v3.csv'))
    for reg, r in (('ldpc', r_ldpc), ('jscc', r_jscc)):
        want = float(ref[(ref.channel == CH) & (ref.split == SPLIT) & (ref.regime == reg)].edge_rf_minus_threshold.iloc[0])
        assert abs(r['edge_rf_minus_threshold'] - want) < 1e-9, (reg, r['edge_rf_minus_threshold'], want)
        print(f"[bit-match {reg}] figure edge {r['edge_rf_minus_threshold']:+.5f} == two_regime_edge_v3 {want:+.5f}")

    def oracle_mean(regime):                        # per-frame max(eff_L, eff_C), 200-seed -- context bar
        gr, n = (piv, njscc) if regime == 'jscc' else (None, len(df))
        d = df.iloc[:n]; lt = d['late_f1'].to_numpy(); acc = 0.0
        for s in range(BE.V.N_SEED):
            rng = np.random.default_rng(s); snr = rng.uniform(0, 20, n)
            b16 = BE.V._bler(snr, 16, CH); effC = BE.eff_C_of(regime, d, gr, snr, b16)
            acc += np.maximum(lt, effC).mean()
        return acc / BE.V.N_SEED

    bars = []
    for reg_label, reg, r in (('LDPC+QAM\n(cliff)', 'ldpc', r_ldpc), ('Importance-map JSCC\n(graceful)', 'jscc', r_jscc)):
        vals = {'L': float(df.iloc[:r['n']]['late_f1'].mean()), 'thr': r['threshold_f1'],
                'RF': r['rf_f1'], 'oracle': oracle_mean(reg)}
        for k, v in vals.items():
            bars.append(dict(regime=reg_label, policy=k, mean=v, lo=v, hi=v))   # point bars (edge CI is in the table)

    # ---------- figure ----------
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(7.2, 3.0))
    cL = getattr(PS, 'C_L', '#1f77b4'); cThr = '0.55'
    cRF = getattr(PS, 'C_OURS', '#7b3294'); cOr = getattr(PS, 'C_ORACLE', '#2ca02c')

    # (a) feature F1 vs SNR
    sw = np.linspace(0, 20, 81)
    ax = axA
    ax.plot(sw, comp_f1.mean() * (1 - BE.V._bler(sw, 16, CH)), '-', color=cThr, lw=2,
            label='LDPC+QAM feature (cliff)')
    ax.plot(grid, piv.mean(0), 'o-', color=cRF, lw=2, ms=4,
            label='JSCC feature (graceful)')
    ax.axhline(late_f1.mean(), ls='-.', color=cL, lw=1.4, label='Fixed $L$ (object-level)')
    ax.set_xlabel('SNR (dB, AWGN)'); ax.set_ylabel('mean feature F1')
    ax.set_title('(a) channel response', fontsize=9)
    ax.annotate('SNR informative', (10, 0.30), fontsize=7, color=cThr)
    ax.annotate('SNR uninformative', (6, 0.872), fontsize=7, color=cRF)
    ax.legend(fontsize=6.3, loc='center right'); ax.grid(alpha=0.3)

    # (b) grouped bars
    ax = axB
    B = pd.DataFrame(bars)
    regimes = list(dict.fromkeys(B['regime'])); pols = ['L', 'thr', 'RF', 'oracle']
    labels = {'L': 'Fixed $L$', 'thr': 'best SNR-thr', 'RF': 'CA-TOSG (ours)', 'oracle': 'oracle'}
    cols = {'L': cL, 'thr': cThr, 'RF': cRF, 'oracle': cOr}
    w = 0.19
    for j, pol in enumerate(pols):
        xs = np.arange(len(regimes)) + (j - 1.5) * w
        sub = B[B['policy'] == pol].set_index('regime').loc[regimes]
        yerr = np.vstack([sub['mean'] - sub['lo'], sub['hi'] - sub['mean']])
        ax.bar(xs, sub['mean'], w, yerr=yerr, capsize=2, color=cols[pol], label=labels[pol])
    ax.set_xticks(np.arange(len(regimes))); ax.set_xticklabels(regimes, fontsize=7.5)
    # data-driven y-range (test bars sit higher than the retired validate render): floor a hair below the
    # shortest bar, headroom above the tallest for the legend strip. Range shift vs validate is expected.
    ymean = B['mean']
    ax.set_ylim(ymean.min() - 0.012, ymean.max() + 0.030); ax.set_ylabel('realised F1')
    ax.set_title('(b) selector vs threshold', fontsize=9)
    ax.legend(fontsize=6.3, ncol=4, loc='upper center', columnspacing=1.0,
              handlelength=1.3); ax.grid(alpha=0.3, axis='y')
    print('[bars]\n' + B.to_string(index=False))

    fig.tight_layout()
    out = os.path.join(C.FIGDIR, 'fig_two_regime.pdf')
    fig.savefig(out, bbox_inches='tight'); fig.savefig(out.replace('.pdf', '_preview.png'), dpi=150, bbox_inches='tight')
    print('wrote', out)


if __name__ == '__main__':
    main()
