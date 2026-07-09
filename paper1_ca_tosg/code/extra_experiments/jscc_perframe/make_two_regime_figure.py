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
BLER = pd.read_csv(os.path.join(C.REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv'))


def bler16(snr):
    sub = BLER[BLER['qam'] == 16].sort_values('snr_db')
    return np.clip(np.interp(snr, sub['snr_db'], sub['bler'], left=1.0, right=0.0), 0, 1)


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
    df = pd.read_csv(C.VAL_CSV)
    jf = pd.read_csv(os.path.join(HERE, 'out', 'jscc_perframe_jscc_awgn.csv'))
    frames = np.sort(jf['sample_id'].unique())
    df = df[df['sample_id'].isin(frames)].sort_values('sample_id').reset_index(drop=True)
    cue_cols = [c for c in C.feat_cols(df, 'full') if c not in ('est_snr_db', 'channel_is_rayleigh')]
    cues = df[cue_cols].to_numpy(); late_f1 = df['late_f1'].to_numpy()
    comp_f1 = df['compressed_f1'].to_numpy()

    # JSCC per-frame interpolator
    grid = np.sort(jf['snr_db'].unique())
    piv = jf.pivot_table(index='sample_id', columns='snr_db', values='jscc_f1_05').sort_index()[grid].to_numpy()

    def eff_C_ldpc(snr):
        return comp_f1 * (1 - bler16(snr))

    def eff_C_jscc(snr):
        return np.array([np.interp(snr[k], grid, piv[k]) for k in range(len(snr))])

    bars_csv = os.path.join(HERE, 'out', 'two_regime_bars.csv')
    if '--replot' in sys.argv and os.path.exists(bars_csv):
        print('[replot] loading cached bars (skip 400 RF fits)')
        bars = pd.read_csv(bars_csv).to_dict('records')
    else:
        print('computing LDPC regime (same frames)...')
        R_ldpc = eval_regime(df, cues, late_f1, eff_C_ldpc, 1000)
        print('computing JSCC regime (same frames)...')
        R_jscc = eval_regime(df, cues, late_f1, eff_C_jscc, 2000)
        bars = []
        for reg, R in [('LDPC+QAM\n(cliff)', R_ldpc), ('Importance-map JSCC\n(graceful)', R_jscc)]:
            for k in ['L', 'thr', 'RF', 'oracle']:
                m, lo, hi = ci(R[k]); bars.append(dict(regime=reg, policy=k, mean=m, lo=lo, hi=hi))
        em, elo, ehi = ci(R_ldpc['edge']); ej, ejlo, ejhi = ci(R_jscc['edge'])
        print(f'LDPC edge = {em:+.4f} [{elo:+.4f},{ehi:+.4f}]   JSCC edge = {ej:+.4f} [{ejlo:+.4f},{ejhi:+.4f}]')
        pd.DataFrame(bars).to_csv(bars_csv, index=False)

    # ---------- figure ----------
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(7.2, 3.0))
    cL = getattr(PS, 'C_L', '#1f77b4'); cThr = '0.55'
    cRF = getattr(PS, 'C_OURS', '#7b3294'); cOr = getattr(PS, 'C_ORACLE', '#2ca02c')

    # (a) feature F1 vs SNR
    sw = np.linspace(0, 20, 81)
    ax = axA
    ax.plot(sw, comp_f1.mean() * (1 - bler16(sw)), '-', color=cThr, lw=2,
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
    ax.set_ylim(0.83, 0.905); ax.set_ylabel('realised F1')
    ax.set_title('(b) selector vs threshold', fontsize=9)
    ax.legend(fontsize=6.3, ncol=2, loc='upper left'); ax.grid(alpha=0.3, axis='y')

    fig.tight_layout()
    out = os.path.join(C.FIGDIR, 'fig_two_regime.pdf')
    fig.savefig(out, bbox_inches='tight'); fig.savefig(out.replace('.pdf', '_preview.png'), dpi=150, bbox_inches='tight')
    print('wrote', out)


if __name__ == '__main__':
    main()
