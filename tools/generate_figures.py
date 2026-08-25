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
# tools/check_figure_consistency.py. The retired per-figure scripts drew from the v3
# products, were never invoked from here, and were deleted in R67(c) together with the
# v3 CSVs they read.
GENERATORS = [
    ('overview',  'export_overview_svg.py',    'ca_tosg_method_overview.pdf (from figs/*.svg)'),
    ('bler',      'plot_bler_frame.py',        'fig_channel_bler_frame.pdf'),
    ('frozen',    'plot_frozen_figs.py',       'fig_ap50_*, fig_payload_awgn, '
                                               'fig_decisions_*, fig_stacked_area, '
                                               'fig_decisions_budgets, fig_pareto_test'),
    ('features',  'plot_feature_importance.py','fig_feature_importance.pdf'),
    # R66-1/2: the difficulty figure is built from the FROZEN product
    # (difficulty_frozen.py -> results/sensitivity/difficulty_frozen.csv). It used to be listed
    # below as a "known gap", which is how the retired v3 difficulty ablation stayed the only script
    # anyone associated with fig_difficulty.pdf -- and that script wrote the same filename from
    # v3-era data. It is a first-class entry here; the retired writer was disabled in R66-1 and
    # deleted with its two CSVs in R67 (c).
    # R69-1: the entry points at the PLOT script, not the compute script. difficulty_frozen.py opens
    # data/p2/ and the frozen pickle, so driving it from here made this one generator artefact-tier
    # and `generate_figures.py difficulty` impossible on a clean clone. Every entry in this list now
    # reads committed products only.
    ('difficulty', 'plot_difficulty_frozen.py', 'fig_difficulty.pdf (from difficulty_frozen.csv)'),
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
        # A generator that ends in sys.exit() would otherwise take this driver down with it: running
        # `generate_figures.py` with no arguments regenerated ONLY the overview and exited 0, which
        # looks exactly like success. Catch SystemExit per generator and keep going.
        try:
            runpy.run_path(os.path.join(FIGDIR, script), run_name='__main__')
        except SystemExit as e:
            if e.code not in (0, None):
                raise
            print('    (%s called sys.exit(%r); continuing)' % (script, e.code), flush=True)
    print('\nNOT regenerated here, and each is a KNOWN GAP rather than an omission:')
    print('  fig:qualitative  a BEV render; see projects/ca_tosg/evaluation/figures/'
          'plot_qualitative_bev.py')
    print('  fig:two_regime   the JSCC prior-protocol arm (Appendix).')
