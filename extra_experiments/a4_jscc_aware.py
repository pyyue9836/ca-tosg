#self+ A4: JSCC-aware view -- does graceful JSCC remove the need for granularity selection?
"""
A reviewer will ask: if the feature branch uses importance-map JSCC (graceful
degradation) instead of LDPC+QAM (cliff), is CA-TOSG still needed?

We plot AP@0.5 vs SNR (AWGN) from the cached ImportanceMapJSCC reproduction:
JSCC feature, LDPC+16/256-QAM feature, the perfect-channel upper bound, the
ego-only floor, and the channel-invariant Fixed-L reference. JSCC degrades
gracefully (no cliff) and stays well above the LDPC curves at low SNR.

Honest argument (stated in the paper, not fabricated): graceful JSCC weakens the
*channel-driven* case for selection, but the *task-driven* case remains -- on easy
frames object-level L already matches feature-level (A2: easy-frame gain ~= 0), so
a {L, Feature-JSCC} selector still saves bandwidth by not sending features when the
frame does not need them. The per-frame {L, Feature-JSCC} selector requires
per-frame JSCC F1, which the cached JSCC sweep only provides in aggregate; we
specify it as immediate future work (re-cache per-frame JSCC predictions, relabel
the oracle, retrain the selector -- no backbone change).

Output: paper/figures/fig_jscc_aware.pdf
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import _common as C

JDIR = os.path.join(C.REPO, 'peiyi_work/04_experiment_logs/importance_map_jscc/jscc_eval')
FIXED_L_AP05 = 0.840  # channel-invariant Fixed-L AP@0.5 (paper, sec:where2comm)


def load(name):
    p = os.path.join(JDIR, name)
    return pd.read_csv(p) if os.path.exists(p) else None


def main():
    series = {
        'ImportanceMapJSCC feature': ('awgn_jscc_summary.csv', C.PS.C_ORACLE, '-'),
        'LDPC + 16-QAM feature': ('awgn_ldpc16_summary.csv', C.PS.C_C16, '-'),
        'LDPC + 256-QAM feature': ('awgn_ldpc256_summary.csv', C.PS.C_C256, '-'),
        'Perfect-channel upper bound': ('awgn_upper_summary.csv', C.PS.C_REF, '--'),
        'Ego-only floor': ('ego_only_summary.csv', '0.65', ':'),
    }
    fig, ax = plt.subplots(figsize=(4.8, 3.3))
    for label, (fn, col, ls) in series.items():
        d = load(fn)
        if d is None:
            print('  missing', fn); continue
        ax.plot(d['snr_db'], d['ap_05'], ls, color=col, lw=1.8, label=label)
    ax.axhline(FIXED_L_AP05, color=C.PS.C_L, lw=1.4, ls='-.',
               label='Fixed $L$ (channel-invariant)')
    ax.set_xlabel('SNR (dB, AWGN)'); ax.set_ylabel('AP@0.5')
    ax.set_title('Feature-branch coding: JSCC (graceful) vs LDPC (cliff)', fontsize=8.5)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=6.5, loc='lower right')
    fig.tight_layout()
    out = os.path.join(C.FIGDIR, 'fig_jscc_aware.pdf')
    fig.savefig(out, bbox_inches='tight')
    fig.savefig(out.replace('.pdf', '_preview.png'), bbox_inches='tight', dpi=140)
    print('wrote', out)

    # quick numeric readout: JSCC vs Fixed L crossover
    j = load('awgn_jscc_summary.csv')
    if j is not None:
        lo = j[j['snr_db'] <= 4][['snr_db', 'ap_05']]
        print('JSCC AP@0.5 at low SNR vs Fixed-L=%.3f:' % FIXED_L_AP05)
        print(lo.to_string(index=False))


if __name__ == '__main__':
    main()
