#self+ CA-TOSG: frame-level BLER figure (4 curves) from Sionna bler_sionna.csv.
# -*- coding: utf-8 -*-
"""Regenerate fig_channel_bler_frame.{pdf,png} from results/channel/bler_sionna.csv.

Four curves = {16,256}-QAM x {AWGN,Rayleigh}, plotted from the FRAME-level column
(bler_frame), not the codeword column. Frame BLER runs 1.0 -> 0, so the y-axis is LINEAR
[0,1] (a log axis cannot show the exact 0 of the delivered regime). AWGN gives two steep
cliffs (onset where frame BLER first drops below 0.999: 8.0 dB for 16-QAM, 16.5 dB for
256-QAM); under Rayleigh both curves stay flat at 1.0 across the range. The grey band marks
the MEASURED selector knee at 10 dB (P5-7 item 12: the frozen selectors' rho_F steps from 0
to its plateau there on all three splits), not the 12--14 dB band an earlier version drew.
"""
import os
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
CSV = os.path.join(P1, 'results/channel/bler_sionna.csv')
FIG = os.path.join(P1, 'paper/figures')

ROWS = list(csv.DictReader(open(CSV)))


def series(qam, ch):
    s = sorted((float(r['esno_db']), float(r['bler_frame']))
               for r in ROWS if r['qam'] == qam and r['channel'] == ch)
    return [x for x, _ in s], [b for _, b in s]


def main():
    os.makedirs(FIG, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.5, 3.6))

    # selector-knee marker at the MEASURED knee (10 dB), behind the curves. The band is drawn
    # narrow around the single grid point rather than spanning 12-14 dB, which was never measured.
    ax.axvspan(9.5, 10.5, color='0.85', alpha=0.7, zorder=0,
               label='selector knee (10 dB)')

    styles = [
        ('16',  'awgn',     dict(color='tab:blue', ls='-',  marker='o', label='LDPC + 16-QAM, AWGN')),
        ('256', 'awgn',     dict(color='tab:red',  ls='-',  marker='s', label='LDPC + 256-QAM, AWGN')),
        ('16',  'rayleigh', dict(color='tab:blue', ls='--', marker='^', label='LDPC + 16-QAM, Rayleigh')),
        ('256', 'rayleigh', dict(color='tab:red',  ls='--', marker='v', label='LDPC + 256-QAM, Rayleigh')),
    ]
    for qam, ch, st in styles:
        xs, ys = series(qam, ch)
        ax.plot(xs, ys, linewidth=1.8, markersize=4, **st)

    ax.set_xlabel(r'$E_s/N_0$ (dB)')
    ax.set_ylabel('Frame-level BLER')
    ax.set_xlim(0, 24)
    ax.set_ylim(-0.02, 1.03)
    ax.set_xticks([0, 4, 8, 12, 16, 20, 24])
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc='center right', framealpha=0.92)
    ax.set_title('Frame-level BLER: LDPC + QAM over AWGN and Rayleigh', fontsize=9)

    fig.tight_layout()
    stem = os.path.join(FIG, 'fig_channel_bler_frame')
    for ext in ('pdf', 'png'):
        fig.savefig(f'{stem}.{ext}', dpi=150)
    print('wrote fig_channel_bler_frame.{pdf,png}')
    # sanity echo
    for qam, ch, _ in styles:
        xs, ys = series(qam, ch)
        onset = next((x for x, b in zip(xs, ys) if b < 0.999), None)
        print(f'  {qam}-QAM {ch}: onset(<0.999)={onset}  last_bler={ys[-1]:.3g}')


if __name__ == '__main__':
    main()
