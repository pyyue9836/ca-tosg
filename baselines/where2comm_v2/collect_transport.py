#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R60-3: the deterministic collector for the transport-replay cells.

`transport_replay.csv` was assembled by an ad-hoc snippet typed at a prompt, which is how a summary
product ends up with nobody able to say what wrote it. This reads the seven per-cell JSONs and
writes the CSV, dropping the per-realisation arrays (they belong to the JSONs and to the bootstrap,
not to a summary table).

    python baselines/where2comm_v2/collect_transport.py [--check]
"""
from __future__ import annotations

import glob
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'results', 'diagnostics', 'transport_replay.csv')
DROP = ('w2c_ap50_per_realisation', 'catosg_ap50_per_realisation')
# R61-4: the seven cells this summary is defined over, named. A glob silently absorbs an eighth file
# and silently tolerates a missing one; either way the CSV stops describing what it claims to.
EXPECTED = (
    'transport_replay_culver_thr0.02_B0.10.json',
    'transport_replay_test_thr0.015_B0.10.json',
    'transport_replay_validate_thr0.02_B0.10.json',
    'transport_replay_test_thr0.013_B0.20.json',
    'transport_replay_culver_thr0.013_B0.30.json',
    'transport_replay_test_thr0.013_B0.30.json',
    'transport_replay_validate_thr0.013_B0.30.json',
)


def build() -> pd.DataFrame:
    found = {os.path.basename(f) for f in
             glob.glob(os.path.join(ROOT, 'results/diagnostics/transport_replay_*.json'))}
    missing, extra = set(EXPECTED) - found, found - set(EXPECTED)
    if missing or extra:
        raise SystemExit(
            'collect_transport FAIL: the cell set does not match the manifest -- '
            + (f'missing {sorted(missing)} ' if missing else '')
            + (f'unexpected {sorted(extra)}' if extra else ''))
    rows = []
    for name in EXPECTED:
        d = json.load(open(os.path.join(ROOT, 'results/diagnostics', name)))
        rows.append({k: v for k, v in d.items() if k not in DROP})
    return pd.DataFrame(rows).sort_values(['budget', 'split']).reset_index(drop=True)


def main() -> int:
    df = build()
    text = df.to_csv(index=False)
    if '--check' in sys.argv:
        cur = open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''
        if cur != text:
            print('TRANSPORT COLLECTOR CHECK FAIL: results/diagnostics/transport_replay.csv is not '
                  'what the per-cell JSONs produce -- re-run: '
                  'python baselines/where2comm_v2/collect_transport.py')
            return 1
        print(f'TRANSPORT COLLECTOR CHECK PASS: {len(df)} cells, summary matches the per-cell JSONs.')
        return 0
    open(OUT, 'w', encoding='utf-8').write(text)
    print(f'wrote {os.path.relpath(OUT, ROOT)} ({len(df)} cells)')
    return 0


def self_test() -> int:
    """An eighth cell must break the collector, not be quietly averaged in."""
    fake = os.path.join(ROOT, 'results/diagnostics/transport_replay_ghost_thr0.99_B0.10.json')
    json.dump({'split': 'ghost', 'budget': '0.10'}, open(fake, 'w'))
    try:
        try:
            build()
            fired = False
        except SystemExit:
            fired = True
    finally:
        os.remove(fake)
    print('SELF-TEST: an eighth JSON -> %s' % ('FIRES' if fired else 'DOES NOT FIRE'))
    clean = True
    try:
        build()
    except SystemExit:
        clean = False
    print('SELF-TEST: manifest restored -> %s' % ('silent' if clean else 'FALSE POSITIVE'))
    return 0 if (fired and clean) else 1


if __name__ == '__main__':
    sys.exit(self_test() if '--self-test' in sys.argv else main())
