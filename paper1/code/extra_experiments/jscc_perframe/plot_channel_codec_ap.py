#self+ Figure A: channel x codec AP@0.5 vs SNR (9 panels), test split. Supervisor plotting disciplines:
# shared y-axis across all 9 panels; 6 measured SNR points as MARKERS with straight guide lines (NO spline);
# row/col titles once each; single figure-level legend. Three reference lines (byte-consistent with
# tab:headline true-e2e): upper (identity comp) 0.9216, Fixed-L (late) 0.9189, ego floor 0.7350 -- distinct
# line styles, values in the legend. Fixed-L is labelled as "the object-level alternative available to an
# adaptive selector" (a codec-response figure, NOT a selector-performance figure).
import os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
POL = os.path.join(P1, 'results/jscc_v3'); FIGDIR = os.path.join(P1, 'paper/figures')
os.makedirs(FIGDIR, exist_ok=True)
try:
    sys.path.insert(0, os.path.join(P1, 'code')); import paper_style as PS; PS.apply()
except Exception:
    pass

UPPER, FIXEDL, EGO = 0.9216, 0.9189, 0.7350         # byte-consistent with tab:headline true-e2e (test)
CHANNELS = ['awgn', 'rayleigh', 'ofdm']; CH_LABEL = {'awgn': 'AWGN', 'rayleigh': 'Rayleigh', 'ofdm': 'OFDM'}
CODECS = ['LDPC-16', 'LDPC-256', 'JSCC']
CODEC_LABEL = {'LDPC-16': 'LDPC + 16-QAM', 'LDPC-256': 'LDPC + 256-QAM', 'JSCC': 'JSCC'}
CODEC_COL = {'LDPC-16': '#0072B2', 'LDPC-256': '#D55E00', 'JSCC': '#009E73'}


def main(split='test'):
    d = pd.read_csv(os.path.join(POL, f'channel_codec_ap_v3_{split}.csv'))
    fig, axes = plt.subplots(3, 3, figsize=(8.4, 7.2), sharex=True, sharey=True)
    for i, ch in enumerate(CHANNELS):
        for j, cd in enumerate(CODECS):
            ax = axes[i, j]
            s = d[(d.channel == ch) & (d.codec == cd)].sort_values('snr_db')
            ax.plot(s.snr_db, s.ap50, marker='o', ms=4, lw=1.2, color=CODEC_COL[cd],
                    label=f'{CODEC_LABEL[cd]} codec' if (i == 0 and j == 0) else None)  # markers + straight guides
            ax.axhline(UPPER, ls='--', lw=0.9, color='0.30',
                       label=f'delivery ceiling (error-free, AP $=0.922$)' if (i == 0 and j == 0) else None)
            ax.axhline(FIXEDL, ls='-.', lw=0.9, color='0.55',
                       label=f'object-level $L$ alternative (AP $=0.919$)' if (i == 0 and j == 0) else None)
            ax.axhline(EGO, ls=':', lw=1.0, color='#7B3FA0',
                       label=f'ego-only failure floor (AP $=0.735$)' if (i == 0 and j == 0) else None)
            ax.set_ylim(0.70, 0.95); ax.grid(True, alpha=0.3)
            if i == 0:
                ax.set_title(CODEC_LABEL[cd], fontsize=10)
            if j == 0:
                ax.set_ylabel(f'{CH_LABEL[ch]}\nAP@0.5', fontsize=9)
            if i == 2:
                ax.set_xlabel('Es/N0 (dB)', fontsize=9)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=7.5, loc='upper center', ncol=2, bbox_to_anchor=(0.5, 1.005))
    fig.suptitle('Channel $\\times$ codec delivery AP (OPV2V test)', fontsize=11, y=1.06)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(FIGDIR, f'fig_channel_codec_ap_{split}.pdf')
    fig.savefig(out, bbox_inches='tight'); fig.savefig(out.replace('.pdf', '_preview.png'), dpi=150, bbox_inches='tight')
    print('wrote', out)


if __name__ == '__main__':
    main()
