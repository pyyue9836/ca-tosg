#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate (R63-3): the transport cells must carry the values the simulation actually used.

Three checks, each guarding a defect that has already occurred in this arm:

  1. **Schema.** Every one of the seven cells carries all five `realised_*` fields. A cell written
     by an older version of the replay looks fine in a table and silently describes a design value
     instead of a draw.
  2. **Single-threshold cells are consistent.** For a non-mixture cell the realised fraction is the
     point's own mean, so it must equal the stored `rate` to rounding. This is what catches a cell
     whose realised fields were copied from the wrong point.
  3. **The mixture cell's realised fraction sits between its components and near the design value.**
     It is a draw, so it is not required to equal 0.1978 -- it is required to be a plausible draw
     around it, and to lie inside the two component fractions.

    python tests/test_transport_products.py [--self-test]
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'baselines', 'where2comm_v2'))

from collect_transport import EXPECTED                       # noqa: E402
DIAG = os.path.join(ROOT, 'results', 'diagnostics')
FIELDS = ('realised_mean_fraction', 'realised_fraction_deviation', 'realised_ncw_mean',
          'realised_ncw_min', 'realised_ncw_max')
COMPONENTS = (0.3130, 0.0802)         # the mixture's two component fractions, test split
DESIGN = 0.1978


def check(cells):
    bad = []
    for name, d in cells.items():
        missing = [f for f in FIELDS if f not in d]
        if missing:
            bad.append(f'{name}: missing {missing}')
            continue
        if not d.get('mixture'):
            if abs(float(d['realised_mean_fraction']) - float(d['rate'])) > 5e-4:
                bad.append(f"{name}: realised fraction {d['realised_mean_fraction']} != stored rate "
                           f"{d['rate']} -- a single-threshold cell transmits the same payload every "
                           f"realisation, so these cannot differ")
        else:
            r = float(d['realised_mean_fraction'])
            lo, hi = min(COMPONENTS), max(COMPONENTS)
            if not lo <= r <= hi:
                bad.append(f'{name}: mixture fraction {r} outside its components [{lo}, {hi}]')
            if abs(r - DESIGN) > 0.02:
                bad.append(f'{name}: mixture fraction {r} is not a plausible draw around the design '
                           f'value {DESIGN}')
            if int(d['realised_ncw_max']) <= int(d['realised_ncw_min']):
                bad.append(f'{name}: mixture codeword span is degenerate')
    return bad


def load():
    out = {}
    for name in EXPECTED:
        p = os.path.join(DIAG, name)
        if os.path.exists(p):
            out[name] = json.load(open(p))
    return out


def main():
    cells = load()
    if len(cells) != len(EXPECTED):
        print(f'TRANSPORT PRODUCT GATE FAIL: {len(cells)} of {len(EXPECTED)} cells present')
        return 1
    if '--self-test' in sys.argv:
        probe = {k: dict(v) for k, v in cells.items()}
        first = sorted(probe)[0]
        probe[first].pop('realised_mean_fraction', None)
        fired_schema = bool(check(probe))
        probe2 = {k: dict(v) for k, v in cells.items()}
        single = next(k for k, v in probe2.items() if not v.get('mixture'))
        probe2[single]['realised_mean_fraction'] = float(probe2[single]['rate']) + 0.05
        fired_value = bool(check(probe2))
        print('SELF-TEST: a missing realised_* field -> %s'
              % ('FIRES' if fired_schema else 'DOES NOT FIRE'))
        print('SELF-TEST: a single-threshold cell whose realised fraction drifts -> %s'
              % ('FIRES' if fired_value else 'DOES NOT FIRE'))
        live = check(cells)
        print(f'SELF-TEST: the live cells -> {len(live)} failure(s) (expected 0)')
        return 0 if (fired_schema and fired_value and not live) else 1
    bad = check(cells)
    print(f'transport products: {len(cells)} cells, {len(FIELDS)} realised fields each')
    for b in bad:
        print(f'  {b}')
    if bad:
        print(f'TRANSPORT PRODUCT GATE FAIL: {len(bad)} problem(s) (R63-3)')
        return 1
    print('TRANSPORT PRODUCT GATE PASS: every cell reports what the simulation used.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
