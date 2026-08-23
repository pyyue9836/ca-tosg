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


def build() -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'results/diagnostics/transport_replay_*.json'))):
        d = json.load(open(f))
        rows.append({k: v for k, v in d.items() if k not in DROP})
    if not rows:
        raise SystemExit('collect_transport: no per-cell JSON found')
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


if __name__ == '__main__':
    sys.exit(main())
