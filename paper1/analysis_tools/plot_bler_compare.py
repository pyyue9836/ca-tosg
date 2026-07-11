#self+ P1 Step 1 acceptance figure: old (40-block, codeword-used-as-frame) vs new Sionna
# (codeword-level and frame-level) LDPC+QAM BLER.
import os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys as _s; _s.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'code'))
import paper_style as PS; PS.apply()
import pandas as pd, numpy as np

P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
old = pd.read_csv(os.path.join(P1, 'results/ldpc_qam_bler_table.csv'))     # AWGN codeword, N=40
new = pd.read_csv(os.path.join(P1, 'results/bler_sionna/bler_sionna.csv'))
COL = {16: PS.C_C16, 256: PS.C_C256}

fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4), sharey=True)
for ax, ch in zip(axes, ('awgn', 'rayleigh')):
    for q in (16, 256):
        d = new[(new.channel == ch) & (new.qam == q)].sort_values('esno_db')
        ax.plot(d.esno_db, d.bler_cw.clip(1e-5), '-', color=COL[q], lw=1.2, alpha=0.6,
                label=f'{q}-QAM new codeword')
        ax.plot(d.esno_db, d.bler_frame.clip(1e-5), '-', color=COL[q], lw=2.4,
                label=f'{q}-QAM new frame')
    if ch == 'awgn':                                    # old table is AWGN codeword, used as frame
        for q in (16, 256):
            o = old[old.qam == q].sort_values('snr_db')
            ax.plot(o.snr_db, o.bler.clip(1e-5), '--o', color='0.4', lw=1.1, ms=3,
                    label=f'{q}-QAM OLD (N=40, used as frame)' if q == 16 else None)
        ax.axhline(1/40, color='r', ls=':', lw=1.0, alpha=0.7)
        ax.annotate('old 1/40 sampling floor', xy=(13, 1/40), xytext=(9, 0.09),
                    fontsize=6.5, color='r', arrowprops=dict(arrowstyle='->', color='r', lw=0.7))
    ax.set_yscale('log'); ax.set_ylim(8e-5, 1.4); ax.set_xlim(0, 25)
    ax.set_xlabel('Es/N0 (dB)  [old table: its snr_db axis]')
    ax.set_title(ch.upper(), fontsize=9); ax.grid(alpha=0.3, which='both')
axes[0].set_ylabel('BLER'); axes[0].legend(fontsize=5.6, loc='lower left', ncol=1, framealpha=0.92)
fig.tight_layout()
for ext in ('pdf', 'png', 'svg'):
    fig.savefig(os.path.join(P1, 'results/bler_sionna/bler_old_vs_new.' + ext))
print('wrote results/bler_sionna/bler_old_vs_new.{pdf,png,svg}')
