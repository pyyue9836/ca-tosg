#self+ A2: difficulty-stratified analysis (easy/medium/hard) -- where CA-TOSG actually wins
"""
Average F1 hides CA-TOSG's value. We stratify frames into easy/medium/hard by the
ego's own object-level detection quality (late_f1 terciles: low late_f1 = hard, i.e.
the ego's compact message is weak and feature-level help is most valuable). For each
stratum we report Fixed-L, CA-TOSG (deployed RF), and Oracle realised F1, the
CA-TOSG-over-L gain, CA-TOSG payload, and the selector's action mix.
Outputs: out/a2_difficulty.csv + paper/figures/fig_difficulty.pdf
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import _common as C


def stratify(df):
    q = df['late_f1'].quantile([1/3, 2/3]).to_numpy()
    lab = np.where(df['late_f1'] <= q[0], 'Hard',
                   np.where(df['late_f1'] <= q[1], 'Medium', 'Easy'))
    return lab


def analyse(name, csv, rf):
    df = pd.read_csv(csv)
    df['stratum'] = stratify(df)
    rf_act = C.rf_predict(rf, df)
    rows = []
    for s in ['Easy', 'Medium', 'Hard']:
        m = df['stratum'].to_numpy() == s
        sub = df[m]
        _, f1_L = C.realised(sub, np.array(['L'] * len(sub)))
        pay_rf, f1_rf = C.realised(sub, rf_act[m])
        _, f1_or = C.realised(sub, sub['oracle_3way'].to_numpy())
        ar = C.action_ratios(rf_act[m])
        rows.append(dict(split=name, stratum=s, n=int(m.sum()),
                         late_f1_mean=round(sub['late_f1'].mean(), 3),
                         fixedL_f1=round(f1_L, 4), catosg_f1=round(f1_rf, 4),
                         oracle_f1=round(f1_or, 4),
                         gain_catosg_minus_L=round(f1_rf - f1_L, 4),
                         catosg_payload=round(pay_rf, 4),
                         act_L=round(ar['L'], 3), act_C16=round(ar['C16'], 3),
                         act_C256=round(ar['C256'], 3)))
    return rows


def _panel(ax, rs, title):
    strata = [r['stratum'] for r in rs]
    x = np.arange(len(strata)); w = 0.26
    ax.bar(x - w, [r['fixedL_f1'] for r in rs], w, label='Fixed $L$', color='#1f77b4')
    ax.bar(x, [r['catosg_f1'] for r in rs], w, label='CA-TOSG', color='#9467bd')
    ax.bar(x + w, [r['oracle_f1'] for r in rs], w, label='Oracle', color='#2ca02c')
    for i, r in enumerate(rs):
        g = r['gain_catosg_minus_L']
        ax.text(i, max(r['catosg_f1'], r['fixedL_f1']) + 0.015,
                f'{g:+.3f}', ha='center', fontsize=7, color='#5b2a86')
    ax.set_xticks(x); ax.set_xticklabels(strata, fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.set_ylim(0, 1.05); ax.grid(True, axis='y', alpha=0.3)


def plot(rows, gc_rows):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), sharey=True)
    _panel(axes[0], [r for r in rows if r['split'] == 'test'],
           'OPV2V test: all channels')
    _panel(axes[1], [r for r in gc_rows if r['split'] == 'test'],
           r'OPV2V test: AWGN, SNR $\geq$ 14 dB')
    axes[0].set_ylabel('Mean realised F1')
    axes[0].legend(fontsize=7, loc='lower left')
    fig.text(0.5, -0.02, 'frame difficulty (by ego object-level F1 tercile)',
             ha='center', fontsize=8)
    fig.tight_layout()
    out = os.path.join(C.FIGDIR, 'fig_difficulty.pdf')
    fig.savefig(out, bbox_inches='tight')
    fig.savefig(out.replace('.pdf', '_preview.png'), bbox_inches='tight', dpi=140)
    print('wrote', out)


def analyse_goodchannel(name, csv, rf):
    """Difficulty strata restricted to channel realisations that can actually
    support feature-level transmission (AWGN, SNR >= 14 dB). This separates the
    'frame difficulty' axis from the 'channel' axis: the per-frame gain the
    channel-averaged view dilutes shows up here."""
    df = pd.read_csv(csv)
    good = df[(df['channel_type'] == 'awgn') & (df['est_snr_db'] >= 14.0)].copy()
    good['stratum'] = stratify(good)
    rf_act = C.rf_predict(rf, good)
    rows = []
    for s in ['Easy', 'Medium', 'Hard']:
        m = good['stratum'].to_numpy() == s
        sub = good[m]
        if len(sub) == 0:
            continue
        _, f1_L = C.realised(sub, np.array(['L'] * len(sub)))
        pay_rf, f1_rf = C.realised(sub, rf_act[m])
        _, f1_or = C.realised(sub, sub['oracle_3way'].to_numpy())
        rows.append(dict(split=name, subset='AWGN_SNR>=14', stratum=s, n=int(m.sum()),
                         fixedL_f1=round(f1_L, 4), catosg_f1=round(f1_rf, 4),
                         oracle_f1=round(f1_or, 4),
                         gain_catosg_minus_L=round(f1_rf - f1_L, 4),
                         catosg_payload=round(pay_rf, 4)))
    return rows


def main():
    rf = C.load_rf()
    rows = []
    for name, csv in [('validate', C.VAL_CSV), ('test', C.TEST_CSV)]:
        rows += analyse(name, csv, rf)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(C.OUTDIR, 'a2_difficulty.csv'), index=False)
    print('=== all-channel (channel-averaged) ===')
    print(out.to_string())

    gc = []
    for name, csv in [('validate', C.VAL_CSV), ('test', C.TEST_CSV)]:
        gc += analyse_goodchannel(name, csv, rf)
    gcdf = pd.DataFrame(gc)
    gcdf.to_csv(os.path.join(C.OUTDIR, 'a2_difficulty_goodchannel.csv'), index=False)
    plot(rows, gc)
    print('\n=== good-channel subset (AWGN, SNR>=14 dB): difficulty x reliable channel ===')
    print(gcdf.to_string())


if __name__ == '__main__':
    main()
