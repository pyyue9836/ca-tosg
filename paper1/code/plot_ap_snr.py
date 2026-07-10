#self+ CA-TOSG: AP-vs-SNR figure (fig:ap_snr), unified GLOBAL-sort.
# -*- coding: utf-8 -*-
"""Regenerate the four AP-vs-SNR panels (fig_ap50/70_{awgn,rayleigh}.pdf).

Every curve is drawn from a single, documented source and every quantity is
scored under the same global-sort AP protocol as the paper's tables:

  CA-TOSG (proposed)      true_e2e_global_validate.csv, policy=CA-TOSG.
                          The deployed selector: object-level L, or the
                          attentive-compression feature branch gated by the
                          LDPC+16-QAM BLER at the estimated SNR. 1980 frames.
  Fixed L                 true_e2e_global_validate.csv, policy=Fixed-L.
                          Channel-invariant object-level baseline (horizontal).
  Feature ceiling         true_e2e_global_validate.csv, policy=Feature-ceiling.
   (perfect channel)      Perfect-channel attentive-compression AP (horizontal).
  ImportanceMapJSCC       {ch}_jscc_summary.csv  (learned reproduction).
  LDPC + 16-QAM (Fixed C16)  {ch}_ldpc16_summary.csv.
  LDPC + 256-QAM (Fixed C256){ch}_ldpc256_summary.csv.

The CA-TOSG / Fixed-L / ceiling curves are guaranteed point-for-point identical
to true_e2e_global_validate.csv (they are read from it, not recomputed). The
JSCC / LDPC baselines use the learned-codec global-sort sweep on the paper's
1000-frame-per-SNR protocol. There is no fabricated "oracle" curve: the only
perfect-channel reference shown is the measured attentive-compression ceiling.

Inputs (read-only, no GPU):
  gs_rerun/true_e2e_global_validate.csv
  gs_rerun/figure_rebuild/jscc_global/{ch}_{jscc,ldpc16,ldpc256}_summary.csv
Output: paper/figures/fig_ap{50,70}_{awgn,rayleigh}.{pdf,png,svg}
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_style as _ps; _ps.apply()
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
OUT_DIR = os.path.join(P1, 'paper/figures')


def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return paths[0]


# Data lives in results/ in the clean ca-tosg repo, and in gs_rerun/ in the OpenCOOD
# working tree. Resolve whichever exists so one script serves both layouts.
TRUE_E2E = _first_existing(
    os.path.join(P1, 'results/true_e2e_global_validate.csv'),
    os.path.join(P1, 'gs_rerun/true_e2e_global_validate.csv'))
JSCC_DIR = _first_existing(
    os.path.join(P1, 'results/ap_vs_snr'),
    os.path.join(P1, 'gs_rerun/figure_rebuild/jscc_global'))

METRICS = {'ap50': ('ap_05', 'ap50', 'AP@0.5'),   # (jscc col, true_e2e col, label)
           'ap70': ('ap_07', 'ap70', 'AP@0.7')}


def jscc_csv(channel, scheme):
    p = os.path.join(JSCC_DIR, '%s_%s_summary.csv' % (channel, scheme))
    return pd.read_csv(p).sort_values('snr_db')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    te = pd.read_csv(TRUE_E2E)

    # snr_db is object-typed in the CSV (Fixed-L / ceiling rows carry '-'); coerce the
    # CA-TOSG rows to float so the x-axis is numeric, not lexicographic/categorical.
    for channel in ('awgn', 'rayleigh'):
        cat = te[(te['policy'] == 'CA-TOSG') & (te['channel'] == channel)].copy()
        cat['snr_db'] = pd.to_numeric(cat['snr_db'])
        cat = cat.sort_values('snr_db')
        fixed_L = te[te['policy'] == 'Fixed-L'].iloc[0]
        ceiling = te[te['policy'] == 'Feature-ceiling'].iloc[0]

        for metric, (jcol, tcol, mlabel) in METRICS.items():
            fig, ax = plt.subplots(figsize=(3.5, 3.0))

            # --- feature-transmission baselines (learned JSCC / digital LDPC) ---
            for scheme, st in [
                ('jscc',    dict(color='#56B4E9', ls='-',  marker='o', label='ImportanceMapJSCC')),
                ('ldpc16',  dict(color=_ps.C_C16, ls=':',  marker='^', label='LDPC + 16-QAM (Fixed $C_{16}$)')),
                ('ldpc256', dict(color=_ps.C_C256,ls=':',  marker='v', label='LDPC + 256-QAM (Fixed $C_{256}$)')),
            ]:
                df = jscc_csv(channel, scheme)
                ax.plot(df['snr_db'], df[jcol], linewidth=1.4, markersize=3.5,
                        **{k: v for k, v in st.items() if k != 'label'}, label=st['label'])

            # --- horizontal references from the true-e2e table ---
            ax.axhline(float(ceiling[tcol]), color=_ps.C_REF, ls='--', linewidth=1.1,
                       label='Feature ceiling (perfect ch.)')
            ax.axhline(float(fixed_L[tcol]), color=_ps.C_L, ls='-.', linewidth=1.3,
                       label='Fixed $L$ (object-level)')

            # --- proposed selector ---
            ax.plot(cat['snr_db'], cat[tcol], color=_ps.C_OURS, marker='*',
                    linewidth=2.0, markersize=9, label='CA-TOSG (proposed)', zorder=5)

            ax.set_xlabel('Estimated SNR (dB)')
            ax.set_ylabel(mlabel)
            ax.set_title('%s — %s' % (mlabel, channel.upper()))
            ax.set_xlim(-1, 21)
            ax.set_xticks([0, 4, 8, 12, 16, 20])
            ax.set_ylim(0.58 if metric == 'ap70' else 0.60, 0.94)
            ax.legend(fontsize=5.9, loc='upper center', bbox_to_anchor=(0.5, -0.20),
                      ncol=3, framealpha=0.92, columnspacing=1.0, handlelength=1.6)

            fig.tight_layout()
            stem = os.path.join(OUT_DIR, 'fig_%s_%s' % (metric, channel))
            for ext in ('pdf', 'png', 'svg'):
                fig.savefig('%s.%s' % (stem, ext))
            plt.close(fig)
            print('wrote', stem + '.{pdf,png,svg}')


if __name__ == '__main__':
    main()
