#self+ A2 v3 (200-realisation, PUBLICATION): difficulty-stratified analysis -- where CA-TOSG wins.
"""
Stratify frames into Easy/Medium/Hard by the ego's own object-level detection quality (late_f1
terciles: low late_f1 = Hard = ego's compact message weak = feature-level help most valuable). Two
views, both under the v3 canonical protocol:
  (1) ALL-CHANNEL: 200-realisation (random SNR+channel), per stratum Fixed-L / CA-TOSG(deployed RF) /
      Oracle realised F1 + the CA-TOSG-over-L gain with a FRAME-level paired 95% CI on the Hard stratum
      (the 4.4.2 published hard-frame gain).
  (2) RELIABLE-CHANNEL conditional (AWGN, 16 dB, C deliverable): isolates the frame-difficulty axis from
      the channel axis -- the per-frame gain the channel-averaged view dilutes. Deterministic condition
      (NOT a single random draw): every frame at est_snr=16, awgn.
Outputs: out/a2_difficulty_v3.csv, out/a2_difficulty_reliable_v3.csv, paper/figures/fig_difficulty.pdf
"""
import os
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import _common as C
import v3_eval as V

STRATA = ['Easy', 'Medium', 'Hard']


def stratify(df):
    q = df['late_f1'].quantile([1 / 3, 2 / 3]).to_numpy()
    return np.where(df['late_f1'] <= q[0], 'Hard', np.where(df['late_f1'] <= q[1], 'Medium', 'Easy'))


def all_channel(name, df, rf, feat):
    lab = stratify(df); rows = []
    fm_rf = V.frame_means(df, 'rf', feat=feat, model=rf)
    fm_L = V.frame_means(df, 'fixedL')
    for s in STRATA:
        m = lab == s
        f1r, payr = V.eval_series(df, 'rf', feat=feat, model=rf, mask=m)
        f1L, _ = V.eval_series(df, 'fixedL', mask=m)
        f1o, _ = V.eval_series(df, 'oracle', mask=m)
        d, lo, hi = V.paired_ci_frames_from(fm_rf[m], fm_L[m])
        rows.append(dict(split=name, view='all_channel_200real', stratum=s, n=int(m.sum()),
                         late_f1_mean=round(df['late_f1'].to_numpy()[m].mean(), 3),
                         fixedL_f1=round(float(f1L.mean()), 4), catosg_f1=round(float(f1r.mean()), 4),
                         oracle_f1=round(float(f1o.mean()), 4),
                         gain_catosg_minus_L=round(d, 4), gain_ci_lo=round(lo, 4), gain_ci_hi=round(hi, 4),
                         gain_significant=bool(lo > 0 or hi < 0), catosg_payload=round(float(payr.mean()), 4)))
    return rows


def reliable_channel(name, df, rf, feat, snr=16.0):
    """Reliable-channel conditional: every frame at AWGN, snr dB (C reliably deliverable).

    CONDITION-DEFINITION CHANGE v2->v3 (declare, do NOT silently substitute -- part of the v2->v3 diff):
    v2 defined the 'good channel' subset by the FROZEN SAMPLED est_snr_db >= 14 dB. Under v3 the channel
    is a per-realisation random draw, not a frozen frame property, so that subset no longer maps to
    fixed frames. v3 replaces it with a DETERMINISTIC channel condition (AWGN, 16 dB) applied to every
    frame -- a conditional expectation given a reliable channel, which cleanly isolates the
    frame-difficulty axis from the channel axis. The threshold moved 14->16 dB because the frame cliff
    moved to ~8 dB (16 dB sits safely above it, b16~0). This is NOT single-frozen-draw eval: the channel
    state is fixed by construction, not sampled once."""
    lab = stratify(df)
    b16 = float(V._bler(np.array([snr]), 16, 'awgn')[0]); b256 = float(V._bler(np.array([snr]), 256, 'awgn')[0])
    eff = V.eff_of(df, np.full(len(df), b16), np.full(len(df), b256))
    d = df.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = 0
    rf_i = np.array([V.ACTIONS.index(a) for a in np.asarray(rf.predict(d[feat]))])
    per_gain = eff[np.arange(len(df)), rf_i] - eff[:, 0]   # deterministic per-frame gain
    rows = []
    for s in STRATA:
        m = lab == s
        f1L = eff[m, 0].mean(); f1r = eff[np.arange(len(df))[m], rf_i[m]].mean()
        f1o = eff[m].max(1).mean(); payr = V.PAYVEC[rf_i[m]].mean()
        g, lo, hi = V.paired_ci_frames_from(eff[np.arange(len(df))[m], rf_i[m]], eff[m, 0])
        rows.append(dict(split=name, view=f'reliable_awgn_{int(snr)}dB', stratum=s, n=int(m.sum()),
                         fixedL_f1=round(float(f1L), 4), catosg_f1=round(float(f1r), 4),
                         oracle_f1=round(float(f1o), 4), gain_catosg_minus_L=round(float(f1r - f1L), 4),
                         gain_ci_lo=round(lo, 4), gain_ci_hi=round(hi, 4),
                         gain_significant=bool(lo > 0 or hi < 0), catosg_payload=round(float(payr), 4)))
    return rows


def _panel(ax, rs, title):
    x = np.arange(len(STRATA)); w = 0.26
    g = lambda k: [next(r[k] for r in rs if r['stratum'] == s) for s in STRATA]
    ax.bar(x - w, g('fixedL_f1'), w, label='Fixed $L$', color=C.PS.C_L)
    ax.bar(x, g('catosg_f1'), w, label='CA-TOSG', color=C.PS.C_OURS)
    ax.bar(x + w, g('oracle_f1'), w, label='Oracle', color=C.PS.C_ORACLE)
    for i, s in enumerate(STRATA):
        gg = next(r['gain_catosg_minus_L'] for r in rs if r['stratum'] == s)
        ax.text(i, 0.05, f'{gg:+.3f}', ha='center', fontsize=6.5, color=C.PS.C_OURS)
    ax.set_xticks(x); ax.set_xticklabels(STRATA, fontsize=8); ax.set_title(title, fontsize=9)
    ax.set_ylim(0, 1.05); ax.grid(True, axis='y', alpha=0.3)


def main():
    rf = C.load_rf(); feat = list(rf.feature_names_in_)
    allc, rel = [], []
    for name, csv in [('validate', C.VAL_CSV), ('test', C.TEST_CSV), ('culver', C.CULVER_CSV)]:
        df = pd.read_csv(csv)
        allc += all_channel(name, df, rf, feat)
        rel += reliable_channel(name, df, rf, feat)
    ac = pd.DataFrame(allc); rc = pd.DataFrame(rel)
    ac.to_csv(os.path.join(C.OUTDIR, 'a2_difficulty_v3.csv'), index=False)
    rc.to_csv(os.path.join(C.OUTDIR, 'a2_difficulty_reliable_v3.csv'), index=False)
    print('=== A2 v3 all-channel (200-realisation) ==='); print(ac.to_string())
    print('\n=== A2 v3 reliable-channel conditional (AWGN 16 dB) ==='); print(rc.to_string())
    try:
        fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), sharey=True)
        _panel(axes[0], [r for r in allc if r['split'] == 'test'], 'OPV2V test: all channels (200 real.)')
        _panel(axes[1], [r for r in rel if r['split'] == 'test'], r'OPV2V test: AWGN 16 dB (C reliable)')
        axes[0].set_ylabel('Mean realised F1'); axes[0].legend(fontsize=7, loc='lower left')
        fig.tight_layout()
        out = os.path.join(C.FIGDIR, 'fig_difficulty.pdf')
        fig.savefig(out, bbox_inches='tight'); fig.savefig(out.replace('.pdf', '_preview.png'), dpi=140, bbox_inches='tight')
        print('wrote', out)
    except Exception as e:
        print('plot skipped:', e)


if __name__ == '__main__':
    main()
