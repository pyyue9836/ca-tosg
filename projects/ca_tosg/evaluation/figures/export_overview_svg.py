#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-B-e (B) item 5: export figs/ca_tosg_overview.svg to paper/figures/ca_tosg_method_overview.pdf.

The overview figure is hand-drawn as SVG. Batch 6 corrected its action-set label to
`S = {E, L, F}` and marked C256 a non-deployed comparator, but there was no SVG->PDF converter on
the host, so the committed PDF still carried the old labels. This is that converter, wired into
`tools/generate_figures.py` so the two can no longer drift again.

If no converter is available the script FAILS with the install command. It never falls back to
leaving the stale PDF in place quietly, and it never redraws the figure by hand.

    python projects/ca_tosg/evaluation/figures/export_overview_svg.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..', '..'))
SVG = os.path.join(ROOT, 'figs', 'ca_tosg_overview.svg')
PDF = os.path.join(ROOT, 'paper', 'archive', 'figures', 'ca_tosg_method_overview.pdf')


def main() -> int:
    if not os.path.exists(SVG):
        print(f'source SVG missing: {SVG}')
        return 1

    # 1) cairosvg (pure python, no system package needed)
    try:
        import cairosvg
        cairosvg.svg2pdf(url=SVG, write_to=PDF)
        print(f'cairosvg {cairosvg.__version__}: {SVG} -> {PDF}')
        return 0
    except Exception as exc:                      # noqa: BLE001 - fall through to the CLI converters
        first = f'cairosvg unavailable or failed: {exc}'

    # 2) rsvg-convert / inkscape, if either is installed
    for cmd in (['rsvg-convert', '-f', 'pdf', '-o', PDF, SVG],
                ['inkscape', SVG, '--export-type=pdf', f'--export-filename={PDF}']):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=True)
            print(f'{cmd[0]}: {SVG} -> {PDF}')
            return 0

    print(first)
    print('no SVG->PDF converter available. Install one:\n'
          '    pip install cairosvg          (preferred, no system packages)\n'
          '    apt-get install librsvg2-bin  (rsvg-convert)\n'
          'The stale PDF is left untouched rather than hand-traced.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
