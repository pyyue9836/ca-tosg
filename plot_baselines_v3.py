#self+ CA-TOSG paper2 v3: read user jscc_eval CSVs and plot empirical baseline AP-vs-SNR curves
# -*- coding: utf-8 -*-
"""V3 figures: pull the user's existing JSCC eval summaries into AP-vs-SNR
comparison plots for Paper #2.

Data sources (no GPU needed — these are evals you already ran):
  peiyi_work/04_experiment_logs/importance_map_jscc/jscc_eval/{awgn,rayleigh}_{jscc,ldpc16,ldpc256,upper}_summary.csv

Schemes plotted per channel:
  Upper bound  — perfect channel, AP ceiling (~0.87 / 0.86)
  ImportanceMapJSCC — analog JSCC, graceful degradation across SNR
  LDPC-16QAM    — separate coding with 16-QAM, cliff effect
  LDPC-256QAM   — separate coding with 256-QAM, steeper cliff
  Fixed L       — PointPillar_Late from baseline_results_5070.csv, channel-invariant

Outputs peiyi_work/01_paper_ca_tosg/runs/v3/{fig_ap50_awgn,fig_ap50_rayleigh,fig_ap70_awgn,fig_ap70_rayleigh}.png+pdf
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSCC = os.path.join(REPO, 'peiyi_work/04_experiment_logs/importance_map_jscc/jscc_eval')
RUN_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v3')

# Channel-invariant L baseline (PointPillar_Late on validate, no channel).
FIXED_L_AP50 = 0.84
FIXED_L_AP70 = 0.76

STYLE = {
    'upper':  dict(color='black',     ls='--', marker='s', label='Upper bound (perfect)'),
    'jscc':   dict(color='tab:red',   ls='-',  marker='o', label='ImportanceMapJSCC'),
    'ldpc16': dict(color='tab:blue',  ls=':',  marker='^', label='LDPC + 16-QAM'),
    'ldpc256':dict(color='tab:orange',ls=':',  marker='v', label='LDPC + 256-QAM'),
}


def load(channel, scheme):
    p = os.path.join(JSCC, '%s_%s_summary.csv' % (channel, scheme))
    if not os.path.exists(p):
        return None
    return pd.read_csv(p).sort_values('snr_db')


def make_fig(channel, metric, save_path):
    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    ap_col = {'ap50': 'ap_05', 'ap70': 'ap_07'}[metric]
    fixed_L = {'ap50': FIXED_L_AP50, 'ap70': FIXED_L_AP70}[metric]

    for scheme in ('upper', 'jscc', 'ldpc16', 'ldpc256'):
        df = load(channel, scheme)
        if df is None or len(df) == 0:
            continue
        st = STYLE[scheme]
        if scheme == 'upper':
            # Single point at SNR=60; draw it as a horizontal line for clarity.
            y = float(df[ap_col].iloc[0])
            ax.axhline(y, color=st['color'], ls=st['ls'], label=st['label'])
        else:
            ax.plot(df['snr_db'], df[ap_col], color=st['color'], ls=st['ls'],
                    marker=st['marker'], linewidth=2, label=st['label'])

    ax.axhline(fixed_L, color='tab:green', ls='-.', linewidth=1.6,
               label='Fixed L (channel-invariant)')

    ax.set_xlabel('SNR (dB)')
    metric_name = {'ap50': 'AP@0.5', 'ap70': 'AP@0.7'}[metric]
    ax.set_ylabel(metric_name)
    ax.set_title('%s vs SNR — %s' % (metric_name, channel.upper()))
    ax.set_xlim(-1, 21)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc='lower right')
    fig.tight_layout()
    fig.savefig(save_path, dpi=140)
    fig.savefig(save_path.replace('.png', '.pdf'))


def main():
    os.makedirs(RUN_DIR, exist_ok=True)
    for ch in ('awgn', 'rayleigh'):
        for metric in ('ap50', 'ap70'):
            out = os.path.join(RUN_DIR, 'fig_%s_%s.png' % (metric, ch))
            make_fig(ch, metric, out)
            print('wrote', out)


if __name__ == '__main__':
    main()
