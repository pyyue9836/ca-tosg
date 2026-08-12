#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command 6/6: regenerate every figure main.tex includes from the committed result CSVs.

  python tools/generate_figures.py            # all
  python tools/generate_figures.py bler ap    # a subset
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


import runpy

FIGDIR = os.path.join(ROOT, 'projects/ca_tosg/evaluation/figures')
GENERATORS = [
    ('bler',      'plot_bler_frame.py',        'fig_channel_bler_frame.pdf'),
    ('ap',        'plot_ap_snr.py',            'fig_ap50_{awgn,rayleigh}.pdf'),
    ('payload',   'plot_pareto_payload.py',    'fig_payload_awgn.pdf + fig_pareto_test.pdf'),
    ('decisions', 'snr_decision_plot.py',      'fig_decisions_{awgn,rayleigh}.pdf'),
    ('stacked',   'plot_stacked_area.py',      'fig_stacked_area.pdf'),
    ('features',  'plot_feature_importance.py','fig_feature_importance.pdf'),
]

if __name__ == '__main__':
    want = set(sys.argv[1:])
    sys.path.insert(0, FIGDIR)
    sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/utils'))
    for key, script, out in GENERATORS:
        if want and key not in want:
            continue
        print('=== %-10s %-28s -> %s' % (key, script, out), flush=True)
        sys.argv = [os.path.join(FIGDIR, script)]
        runpy.run_path(os.path.join(FIGDIR, script), run_name='__main__')
    print('\nfig:overview and fig:qualitative are MANUAL (figs/ca_tosg_overview.svg, BEV render);'
          ' fig:difficulty and fig:two_regime come from the ablation / JSCC baselines.')
