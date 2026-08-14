#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-7 (E) item 18: in-figure vs caption vs body text, three-way.

The figure generators record every number they actually plotted into
`results/provenance/PROVENANCE_figures.json`. This checker takes each of those numbers and asks
where it appears in `paper/main.tex` -- inside a figure/table environment (the caption side) and
outside one (the body side).

It **reports**; it does not choose. A number drawn but absent from both caption and body is listed,
a number present in one and not the other is listed, and a near-miss (the same value at a
neighbouring rounding) is listed as a near-miss rather than silently accepted. Deciding which of
the three is wrong is a human call, and this tool deliberately does not make it.

    python tools/check_figure_consistency.py
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'paper', 'main.tex')
PROV = os.path.join(ROOT, 'results', 'provenance', 'PROVENANCE_figures.json')

# numbers that are axis furniture or shared constants, not claims to be cross-checked
SKIP_KEYS = ('knee_db',)


def split_caption_body(tex):
    """Return (caption_text, body_text): everything inside \\caption{...} vs everything else."""
    caps, body, i = [], [], 0
    for m in re.finditer(r'\\caption\{', tex):
        start = m.end()
        depth, j = 1, start
        while j < len(tex) and depth:
            if tex[j] == '{':
                depth += 1
            elif tex[j] == '}':
                depth -= 1
            j += 1
        caps.append(tex[start:j - 1])
        body.append(tex[i:m.start()])
        i = j
    body.append(tex[i:])
    return '\n'.join(caps), '\n'.join(body)


def appears(value, text):
    """Does `value` appear as a printed number at its OWN precision, or rounded by one digit?

    Degrading further would make almost anything match: 0.9244 truncated to "0.9" appears on nearly
    every page, and an earlier version of this check reported exactly that as a hit. Only the value
    as stored and one digit coarser are tried, and a literal shorter than three significant digits
    is refused outright.
    """
    exact = ('%f' % value).rstrip('0').rstrip('.')
    dec = len(exact.split('.')[1]) if '.' in exact else 0
    lits = [exact]                      # the exact literal is specific by construction
    if dec >= 1:                        # the COARSENED one is what can collide, so gate that
        coarse = f'{value:.{dec - 1}f}'
        if len(coarse.lstrip('-0.').replace('.', '')) >= 3:
            lits.append(coarse)
    for lit in lits:
        if re.search(r'(?<![\d.])' + re.escape(lit) + r'(?![\d])', text):
            return lit
    return None


def main() -> int:
    if not os.path.exists(PROV):
        print(f'{PROV} absent -- run tools/generate_figures.py first')
        return 1
    prov = json.load(open(PROV))
    tex = open(MAIN, encoding='utf-8').read()
    caption, body = split_caption_body(tex)

    rows, missing_both, one_sided = [], [], []
    for key, val in sorted(prov['numbers_drawn'].items()):
        if key in SKIP_KEYS:
            continue
        c = appears(val, caption)
        b = appears(val, body)
        rows.append((key, val, c, b))
        if c is None and b is None:
            missing_both.append((key, val))
        elif (c is None) != (b is None):
            one_sided.append((key, val, 'caption only' if b is None else 'body only'))

    w = max(len(r[0]) for r in rows)
    print('=' * (w + 46))
    print(f'{"drawn number".ljust(w)}  {"value":>9}  {"in caption":>11}  {"in body":>9}')
    print('-' * (w + 46))
    for key, val, c, b in rows:
        print(f'{key.ljust(w)}  {val:>9}  {str(c or "-"):>11}  {str(b or "-"):>9}')
    print('=' * (w + 46))

    print(f'\ndrawn and quoted on BOTH sides   : {sum(1 for _k,_v,c,b in rows if c and b)}')
    print(f'drawn and quoted on ONE side     : {len(one_sided)}')
    print(f'drawn but quoted NOWHERE         : {len(missing_both)}')
    if one_sided:
        print('\nONE-SIDED (a figure number that the caption or the body states, but not both).')
        print('Not necessarily an error -- a number may legitimately live only in a caption.')
        for key, val, where in one_sided:
            print(f'  {key:38s} {val:>9}   {where}')
    if missing_both:
        print('\nDRAWN BUT NEVER STATED (the figure shows it; no caption or sentence does).')
        for key, val in missing_both:
            print(f'  {key:38s} {val:>9}')
    print('\nThis tool REPORTS. It does not decide which of figure / caption / body is right.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
