#self+ CA-TOSG paper2 v3_with_rf: overlay RF policy + L-vs-JSCC oracle on empirical AP curves (final figs)
# -*- coding: utf-8 -*-
"""Final Paper #2 figure set: empirical baselines (v3) + RF policy overlay.

For each (channel, AP threshold) we plot:
  Upper bound      — perfect channel ceiling (from upper_summary.csv)
  ImportanceMapJSCC— Sheng et al. 2024 JSCC, graceful degradation
  LDPC + 16-QAM    — separate-coding baseline, cliff
  LDPC + 256-QAM   — separate-coding baseline, higher-order cliff
  Fixed L          — PointPillar_Late, channel-invariant
  Channel-aware oracle (L vs JSCC) — max(Fixed_L_AP, JSCC_AP) per SNR;
                     the achievable upper bound of any binary L/C selector
                     when JSCC is the C scheme
  CSI-aware RF policy — the v2 RF selector. AP estimated as the per-SNR
                     weighted average of Fixed_L_AP and JSCC_AP, weighted
                     by the RF's per-frame L vs C selection fractions.

Notes / caveats (kept honest):
  * The v2 RF was trained against an LDPC-QAM channel model, NOT against
    JSCC. Plotting its decisions against the JSCC baseline overstates how
    aggressively it would pick L if it knew the C scheme was the more
    graceful JSCC. The plotted RF curve is therefore a CONSERVATIVE
    lower bound on the achievable; a JSCC-aware retrained RF would sit
    closer to the oracle.
  * Bandwidth (payload) is plotted separately so the L vs C trade is
    visible. RF policy saves bandwidth in proportion to its L-selection
    rate.

Inputs (read-only, no GPU):
  v2:  peiyi_work/01_paper_ca_tosg/runs/v2/snr_sweep_{awgn,rayleigh}.csv         (RF decisions)
  v3:  peiyi_work/04_experiment_logs/importance_map_jscc/jscc_eval/*.csv       (real AP)
  ref: peiyi_work/04_experiment_logs/baseline_results_5070.csv                 (Fixed L AP)

Output: peiyi_work/01_paper_ca_tosg/runs/v3_with_rf/
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import paper_style as _ps; _ps.apply()
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2')
JSCC = os.path.join(REPO, 'peiyi_work/04_experiment_logs/importance_map_jscc/jscc_eval')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v3_with_rf')

# Per-frame Fixed L AP (PointPillar_Late on OPV2V validate, from baseline_results_5070.csv)
FIXED_L = {'ap50': 0.84, 'ap70': 0.76}

# Payload constants (Mbit information per frame; comparable across schemes).
PAYLOAD = {'L': 0.024, 'C16': 1.98, 'C256': 1.98, 'JSCC': 1.98}


def load_csv(channel, scheme):
    p = os.path.join(JSCC, '%s_%s_summary.csv' % (channel, scheme))
    if not os.path.exists(p):
        return None
    return pd.read_csv(p).sort_values('snr_db')


def interp_ap(df, snr_grid, col):
    """Piecewise-linear interpolation of df[col] vs df['snr_db'] at snr_grid."""
    xs = df['snr_db'].to_numpy(); ys = df[col].to_numpy()
    return np.interp(snr_grid, xs, ys, left=ys[0], right=ys[-1])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for channel in ('awgn', 'rayleigh'):
        v2_sweep = pd.read_csv(os.path.join(V2_DIR, 'snr_sweep_%s.csv' % channel))
        # v2 sweep has rf_frac_L / rf_frac_C16 / rf_frac_C256 per SNR.
        snr_grid = v2_sweep['snr_db'].to_numpy()
        p_L = v2_sweep['rf_frac_L'].to_numpy()
        p_C = 1.0 - p_L  # treat C16 and C256 jointly as "C"

        jscc_df = load_csv(channel, 'jscc')

        for metric in ('ap50', 'ap70'):
            ap_col = {'ap50': 'ap_05', 'ap70': 'ap_07'}[metric]
            metric_name = {'ap50': 'AP@0.5', 'ap70': 'AP@0.7'}[metric]
            L_AP = FIXED_L[metric]

            # JSCC AP at our v2 SNR grid via interpolation.
            jscc_at_grid = interp_ap(jscc_df, snr_grid, ap_col)

            # Channel-aware oracle (L vs JSCC) and RF policy AP estimates.
            oracle_AP = np.maximum(L_AP, jscc_at_grid)
            rf_AP = p_L * L_AP + p_C * jscc_at_grid
            rf_payload = p_L * PAYLOAD['L'] + p_C * PAYLOAD['JSCC']

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.0),
                                            gridspec_kw=dict(width_ratios=[1.6, 1.0]))

            # ---- Left panel: AP vs SNR with all baselines + RF + oracle ----
            for scheme, st in [
                ('upper',   dict(color=_ps.C_REF,   ls='--', marker='s', label='Upper bound (perfect)')),
                ('jscc',    dict(color='#56B4E9',   ls='-',  marker='o', label='ImportanceMapJSCC')),
                ('ldpc16',  dict(color=_ps.C_C16,   ls=':',  marker='^', label='LDPC + 16-QAM')),
                ('ldpc256', dict(color=_ps.C_C256,  ls=':',  marker='v', label='LDPC + 256-QAM')),
            ]:
                df = load_csv(channel, scheme)
                if df is None: continue
                if scheme == 'upper':
                    ax1.axhline(float(df[ap_col].iloc[0]), color=st['color'],
                                ls=st['ls'], label=st['label'])
                else:
                    ax1.plot(df['snr_db'], df[ap_col], **{k: v for k, v in st.items() if k != 'label'},
                             linewidth=2, label=st['label'])

            ax1.axhline(L_AP, color=_ps.C_L, ls='-.', linewidth=1.6,
                        label='Fixed L (channel-invariant)')
            ax1.plot(snr_grid, oracle_AP, color=_ps.C_ORACLE, ls='--',
                     marker='D', linewidth=2, label='Oracle (L vs JSCC)')
            ax1.plot(snr_grid, rf_AP, color=_ps.C_OURS, marker='*',
                     linewidth=2.4, markersize=9,
                     label='CSI-aware RF policy (proposed)')

            ax1.set_xlabel('SNR (dB)')
            ax1.set_ylabel(metric_name)
            ax1.set_title('%s vs SNR — %s' % (metric_name, channel.upper()))
            ax1.set_xlim(-1, 21)
            ax1.grid(alpha=0.3)
            ax1.legend(fontsize=7.5, loc='lower right', ncol=1)

            # ---- Right panel: payload vs SNR for RF / oracle / fixed ----
            ax2.plot(snr_grid, rf_payload, color=_ps.C_OURS, marker='*',
                     linewidth=2.4, markersize=9, label='RF policy')
            ax2.axhline(PAYLOAD['L'], color=_ps.C_L, ls='-.',
                        label='Fixed L = %.3f' % PAYLOAD['L'])
            ax2.axhline(PAYLOAD['JSCC'], color=_ps.C_C16, ls='-',
                        label='Fixed C / JSCC = %.2f' % PAYLOAD['JSCC'])
            ax2.set_yscale('log')
            ax2.set_xlabel('SNR (dB)')
            ax2.set_ylabel('Payload (Mbit information / frame, log)')
            ax2.set_title('Bandwidth — %s' % channel.upper())
            ax2.set_xlim(-1, 21)
            ax2.grid(alpha=0.3, which='both')
            ax2.legend(fontsize=8, loc='center right')

            fig.tight_layout()
            out = os.path.join(OUT_DIR, 'fig_%s_%s.png' % (metric, channel))
            fig.savefig(out, dpi=140)
            fig.savefig(out.replace('.png', '.pdf'))
            print('wrote', out)

            # Tabular dump for the paper.
            tab = pd.DataFrame({
                'snr_db': snr_grid,
                'rf_frac_L': p_L,
                'rf_AP': rf_AP,
                'oracle_AP': oracle_AP,
                'jscc_AP': jscc_at_grid,
                'fixed_L_AP': L_AP,
                'rf_payload_Mbit': rf_payload,
            })
            tab.to_csv(os.path.join(OUT_DIR, 'tab_%s_%s.csv' % (metric, channel)),
                       index=False)


if __name__ == '__main__':
    main()
