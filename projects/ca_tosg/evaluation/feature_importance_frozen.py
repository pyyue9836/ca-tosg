#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R17-C: Gini feature importances read from the FROZEN B_max=0.20 selector.

Section VI's feature-importance numbers (34.9 / 27.5 / 62.4 %) had no committed CSV behind them.
This reads them straight out of `data/p2/selector_B020.pkl` -- the deployed model whose sha256 is
recorded in FROZEN_MANIFEST.json -- so the claim is bound to the artefact rather than to a figure.

    python projects/ca_tosg/evaluation/feature_importance_frozen.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils'):
    sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(HERE, '..', '..', '..')), _d))
import deployment as D  # noqa: E402

OUT = os.path.join(D.OUT, 'feature_importance_frozen.csv')
CHANNEL_FEATURES = {'est_snr_db', 'channel_is_rayleigh'}


def main() -> int:
    man, budgets = D.load_manifest()
    bd = budgets['0.20']
    model, feat = bd['model'], bd['feat']
    imp = getattr(model, 'feature_importances_', None)
    if imp is None:
        print('the frozen B020 model exposes no feature_importances_')
        return 1
    df = pd.DataFrame({'feature': feat, 'gini_importance': imp})
    df['percent'] = (df.gini_importance / df.gini_importance.sum() * 100).round(4)
    df['side'] = ['channel' if f in CHANNEL_FEATURES else 'perception' for f in df.feature]
    df = df.sort_values('percent', ascending=False).reset_index(drop=True)
    df.insert(0, 'rank', df.index + 1)
    df['selector'] = 'data/p2/selector_B020.pkl'
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    ch = df[df.side == 'channel']
    print(df.head(12).to_string(index=False))
    print(f'\nchannel-side total: {ch.percent.sum():.4f}%  '
          f'({", ".join(f"{r.feature} {r.percent:.4f}%" for _, r in ch.iterrows())})')
    print(f'top perception-side: {df[df.side == "perception"].iloc[0].feature} '
          f'{df[df.side == "perception"].iloc[0].percent:.4f}%')
    print(f'wrote {OUT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
