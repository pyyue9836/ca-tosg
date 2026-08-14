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
# P5-7 (D): Figs. 4/5/6/8 are now ONE generator reading ONE frozen source
# (results/main/frozen_curves.csv + the frozen replay), which also writes
# results/provenance/PROVENANCE_figures.json -- the input to
# tools/check_figure_consistency.py. The retired per-figure scripts
# (plot_ap_snr.py, plot_pareto_payload.py, snr_decision_plot.py, plot_stacked_area.py)
# drew from the v3 products and are no longer invoked.
GENERATORS = [
    ('bler',      'plot_bler_frame.py',        'fig_channel_bler_frame.pdf'),
    ('frozen',    'plot_frozen_figs.py',       'fig_ap50_*, fig_payload_awgn, '
                                               'fig_decisions_*, fig_stacked_area, '
                                               'fig_decisions_budgets, fig_pareto_test'),
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
    print('\nNOT regenerated here, and each is a KNOWN GAP rather than an omission:')
    print('  fig:overview     figs/ca_tosg_overview.svg -> PDF by hand; no SVG->PDF tool on this')
    print('                   host, so its action-set label is edited in the SVG only.')
    print('  fig:qualitative  a BEV render with no generator in the repository at all.')
    print('  fig:difficulty   projects/ca_tosg/evaluation/difficulty_frozen.py (frozen, P5-5).')
    print('  fig:two_regime   the JSCC prior-protocol arm (Appendix).')
