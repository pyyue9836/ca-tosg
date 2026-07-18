#self+ CA-TOSG: regenerate fig_pareto_test + fig_payload_awgn from the CURRENT committed CSVs.
# -*- coding: utf-8 -*-
"""Two test-split figures, each read straight from a committed results CSV.

fig_pareto_test.pdf  <- results/policy_v3/pareto_points.csv (test rows, corrected rate-1/2 payloads)
    Payload--F1 plane. Fixed L / C16 / C256, channel-blind EU policy (collapses to Fixed-L),
    channel-state-conditioned oracle, and CA-TOSG (RF, deployed). 200-realisation protocol,
    selector md5 eb9358e9 (see results/policy_recompute_PROVENANCE.txt).

fig_payload_awgn.pdf <- results/true_e2e_v3/true_e2e_global_v3_validate.csv (AWGN CA-TOSG rows; matches the validate AP/payload section)
    Average channel-use-equivalent payload vs SNR under AWGN, from the deployed selector's
    per-SNR rho_L: payload = rho_L*B_L + (1-rho_L)*B_C, B_L=0.024, B_C=0.99 (Fixed C16, rate-1/2).
    Global-sort true-e2e protocol, same selector md5 eb9358e9.

Provenance is recorded in paper/figures/README.md (Figure provenance section).
Outputs {pdf,svg} into paper/figures/. Pure plotting, no GPU / no inference.
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_style as PS; PS.apply()
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(HERE)
RES = os.path.join(P1, 'results'); FIG = os.path.join(P1, 'paper/figures')
B_L, B_C = 0.024, 0.99                   # object-level; Fixed C16 channel-use payload (rate-1/2: 1.98/(0.5*4))


def save(fig, stem):
    for ext in ('pdf', 'svg'):
        fig.savefig(os.path.join(FIG, f'{stem}.{ext}'))
    plt.close(fig); print('wrote', stem + '.{pdf,svg}')


def pareto_test():
    df = pd.read_csv(os.path.join(RES, 'policy_v3', 'pareto_points.csv'))  # corrected rate-1/2 payloads
    d = df[df.split == 'test']
    style = {
        'Fixed L': ('s', PS.C_L), 'Fixed C16': ('^', PS.C_C16),
        'Fixed C256': ('v', PS.C_C256),
        'Channel-blind EU (->Fixed-L)': ('P', '0.45'),
        'Oracle': ('*', PS.C_ORACLE), 'CA-TOSG (RF, deployed)': ('D', PS.C_OURS)}
    label = {'Channel-blind EU (->Fixed-L)': r'Channel-blind EU ($\to$Fixed $L$)',
             'Oracle': 'Channel-aware oracle'}
    fig, ax = plt.subplots(figsize=(5.6, 3.3))
    for _, r in d.iterrows():
        m, c = style.get(r.policy, ('o', 'k'))
        ax.scatter([r.payload], [r.f1], marker=m, c=c, s=110 if m == '*' else 60,
                   zorder=4, edgecolors='k', linewidths=0.5,
                   label=label.get(r.policy, r.policy))
    ax.set_xscale('log'); ax.set_xlim(0.018, 0.65); ax.set_ylim(0.05, 0.95)
    ax.set_xlabel('Average payload (Mbit/frame, log scale)')
    ax.set_ylabel('Mean realised F1'); ax.set_title('OPV2V test', fontsize=9)
    ax.grid(True, alpha=0.3, which='both')
    ax.annotate('fixed feature-level\npolicies are dominated', xy=(0.495, 0.826),
                xytext=(0.11, 0.30), fontsize=7, color='0.3',
                arrowprops=dict(arrowstyle='->', color='0.5', lw=0.8))
    ax.legend(fontsize=6.8, loc='center left', bbox_to_anchor=(1.01, 0.5), framealpha=0.95)
    fig.tight_layout(); save(fig, 'fig_pareto_test')


def payload_awgn():
    df = pd.read_csv(os.path.join(RES, 'true_e2e_v3', 'true_e2e_global_v3_validate.csv'))  # validate: matches item-7 payload section (0.633/0.990)
    d = df[(df.policy == 'CA-TOSG') & (df.channel == 'awgn')].copy()
    d['snr_db'] = pd.to_numeric(d['snr_db']); d = d.sort_values('snr_db')
    pay = d['rho_L'] * B_L + (1 - d['rho_L']) * B_C
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.plot(d['snr_db'], pay, 'o-', color=PS.C_OURS, lw=2, ms=6, label='CA-TOSG (deployed)')
    ax.axhline(B_L, color=PS.C_L, ls='-.', lw=1.3, label='Fixed $L$ = %.3f' % B_L)
    ax.axhline(B_C, color=PS.C_C16, ls=':', lw=1.3, label='Fixed $C_{16}$ = %.3f' % B_C)
    ax.axhline(0.495, color=PS.C_C256, ls=':', lw=1.1, label='Fixed $C_{256}$ = %.3f' % 0.495)
    ax.set_yscale('log'); ax.set_xlim(-1, 21); ax.set_xticks([0, 4, 8, 12, 16, 20])
    ax.set_xlabel('Estimated SNR (dB)')
    ax.set_ylabel('Mean payload (Mbit channel-use eq., log)')
    ax.set_title('Bandwidth vs SNR — AWGN', fontsize=9)
    ax.grid(alpha=0.3, which='both'); ax.legend(fontsize=7.5, loc='center right')
    fig.tight_layout(); save(fig, 'fig_payload_awgn')


if __name__ == '__main__':
    pareto_test(); payload_awgn()
