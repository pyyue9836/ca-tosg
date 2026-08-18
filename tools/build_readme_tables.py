#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R24-3: the README's model-zoo table, written from FROZEN_MANIFEST.json.

R20 rebuilt the README's *results* section from the registry sources and left this table alone, so
it still carried the pre-corrigendum LOSO F1 / payload pairs (0.9070/0.0679, 0.9087/0.0992,
0.9094/0.1570) against the frozen manifest's 0.8555/0.080803, 0.8606/0.150158, 0.8622/0.201607.
Nothing caught it: no claim row covers the README, and the fingerprint sweep only greps values that
were already known to be retired.

Every cell here is read from the manifest at build time. The splice fails loudly if the table shape
changes, because a generator that silently rewrites nothing is how the last one went stale
(R23-8).

    python tools/build_readme_tables.py [--check]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, 'README.md')
MANIFEST = os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')
HEADER = ('| B_max (mean Msym/frame) | model | λ\\* | τ\\* | LOSO OOF F1 | '
          'frozen validate payload |')


def body(man):
    rows = []
    for tag in sorted(man['budgets']):
        b = man['budgets'][tag]
        rows.append(f'| {float(tag):.2f} | `{b["selector"]}` | {float(b["lambda_star"]):.2f} | '
                    f'{float(b["tau_star"]):.1f} dB | {b["loso_frame_weighted_f1"]} | '
                    f'{b["frozen_validate_payload"]} |')
    return '\n'.join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='print the body, write nothing')
    a = ap.parse_args()
    man = json.load(open(MANIFEST))
    new = body(man)
    if a.check:
        print(new)
        return 0
    text = open(README, encoding='utf-8').read()
    pat = re.compile(re.escape(HEADER) + r'\n\|[-| ]+\|\n((?:\|.*\n)+)')
    out, n = pat.subn(lambda m: m.group(0)[:m.start(1) - m.start(0)] + new + '\n', text)
    if n != 1:
        raise SystemExit(f'README model-zoo table: matched {n} times, expected exactly 1 -- '
                         'the generator is not writing what it claims to write')
    open(README, 'w', encoding='utf-8').write(out)
    print('README model-zoo table written from results/manifests/FROZEN_MANIFEST.json:')
    print(new)
    return 0


if __name__ == '__main__':
    sys.exit(main())
