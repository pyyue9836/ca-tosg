#self+ CA-TOSG paper2: top-12 feature importance horizontal bar chart (channel-side red, perception blue)
# -*- coding: utf-8 -*-
"""Feature importance bar chart for the deployed RF (rf_full).

Top-12 features by Gini importance, with the two channel-side features
highlighted in a contrasting colour. The total importance of
{est_snr_db, channel_is_rayleigh} is annotated to support the abstract
claim of "65% of importance from comm-side features".
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IN = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/feature_importance_full.csv')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_figures')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(IN).sort_values('importance', ascending=False).head(12)
    df = df.iloc[::-1]  # bar chart bottom-to-top
    comm_keys = {'est_snr_db', 'channel_is_rayleigh'}
    colours = ['tab:red' if f in comm_keys else 'tab:blue' for f in df['feature']]

    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    bars = ax.barh(range(len(df)), df['importance'].values, color=colours,
                    edgecolor='black', linewidth=0.5)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df['feature'].values, fontsize=9)
    ax.set_xlabel('Gini importance')
    ax.set_title('Top-12 features by Gini importance (deployed selector)')

    comm_total = df[df['feature'].isin(comm_keys)]['importance'].sum()
    ax.axvline(0, color='black', linewidth=0.5)
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color='tab:red', label=f'Channel-side (CSI + ch. type), $\\Sigma$={comm_total:.3f}'),
        Patch(color='tab:blue', label='Perception cues (LiDAR-derived)'),
    ], fontsize=8, loc='lower right')
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, 'fig_feature_importance.png'), dpi=140)
    fig.savefig(os.path.join(OUT_DIR, 'fig_feature_importance.pdf'))
    print('wrote', os.path.join(OUT_DIR, 'fig_feature_importance.pdf'))
    print(f'  channel-side total importance: {comm_total:.4f}')


if __name__ == '__main__':
    main()
