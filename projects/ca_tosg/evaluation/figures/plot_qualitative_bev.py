#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-B-e (B) item 6: a real generator for fig:qualitative, whose generator was never checked in.

The frame was recovered from the figure's own printed numbers rather than guessed: the caption
states frame F1 $=0.67$ for the object-level branch and $=0.95$ for the feature branch, and exactly
one frame in the three committed per-frame datasets matches both at 2 dp --

    split=test, sample_id=1436, late_f1=0.666667, compressed_f1=0.952381   (unique)

so the figure is reproducible from the committed caches after all. Panels are drawn from
`gs_rerun/{late,comp}_test.npz` against the canonical union GT in the comp cache, and the panel
titles use the deployed action names ($L$ and $F$), not the retired $C_{16}$.

    python projects/ca_tosg/evaluation/figures/plot_qualitative_bev.py
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                                     # noqa: E402
import numpy as np                                                  # noqa: E402
import pandas as pd                                                 # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
GS = os.path.join(OPENCOOD, 'peiyi_work/paper1/gs_rerun')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
OUT = os.path.join(ROOT, 'paper/archive/figures/fig_qualitative_bev.pdf')
PROV = os.path.join(ROOT, 'results/provenance/PROVENANCE_qualitative.json')

SPLIT, SAMPLE_ID = 'test', 1436
DATASET = {'validate': 'dataset_validate.csv', 'test': 'dataset_test_v3.csv',
           'culver': 'dataset_culver_v3.csv'}


def recover_frame():
    """Re-derive the frame from the caption's own numbers; fail loudly if it stops being unique."""
    hits = []
    for sp, fn in DATASET.items():
        p = os.path.join(DATA, fn)
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p)
        m = (d.late_f1.round(2) == 0.67) & (d.compressed_f1.round(2) == 0.95)
        hits += [(sp, int(s)) for s in d.loc[m, 'sample_id']]
    return hits


def corners_to_xy(box):
    """An OPV2V box is (8,3) corners; the BEV footprint is the convex order of the top 4."""
    b = np.asarray(box, dtype=float)
    return b[:4, 0], b[:4, 1]


def panel(ax, boxes, gts, title, f1):
    for g in gts:
        x, y = corners_to_xy(g)
        ax.fill(np.append(x, x[0]), np.append(y, y[0]), color='tab:green', alpha=0.28, lw=0)
    for b in boxes:
        x, y = corners_to_xy(b)
        ax.plot(np.append(x, x[0]), np.append(y, y[0]), c='tab:blue', lw=1.0)
    ax.set_title(f'{title}   (frame F1 = {f1:.2f})', fontsize=9)
    ax.set_xlabel('x (m)', fontsize=8)
    ax.set_ylabel('y (m)', fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_aspect('equal')
    ax.grid(alpha=0.2, lw=0.4)


def main() -> int:
    hits = recover_frame()
    if hits != [(SPLIT, SAMPLE_ID)]:
        print(f'frame recovery is no longer unique: {hits} (expected [({SPLIT!r}, {SAMPLE_ID})]). '
              'Refusing to draw a frame the caption does not pin down.')
        return 1

    late = np.load(os.path.join(GS, f'late_{SPLIT}.npz'), allow_pickle=True)
    comp = np.load(os.path.join(GS, f'comp_{SPLIT}.npz'), allow_pickle=True)
    lb = list(late['boxes'])[SAMPLE_ID]
    cb = list(comp['boxes'])[SAMPLE_ID]
    gt = list(comp['gts'])[SAMPLE_ID]

    d = pd.read_csv(os.path.join(DATA, DATASET[SPLIT])).set_index('sample_id')
    f1_l = float(d.loc[SAMPLE_ID, 'late_f1'])
    f1_f = float(d.loc[SAMPLE_ID, 'compressed_f1'])

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4), sharex=True, sharey=True)
    panel(axes[0], lb, gt, r'Object-level message $L$', f1_l)
    panel(axes[1], cb, gt, r'Feature-level message $F$', f1_f)
    fig.tight_layout()
    fig.savefig(OUT)
    plt.close(fig)

    with open(PROV, 'w') as f:
        json.dump({'schema': 'catosg-qualitative-provenance/1',
                   'generated_by': 'python projects/ca_tosg/evaluation/figures/'
                                   'plot_qualitative_bev.py',
                   'frame': {'split': SPLIT, 'sample_id': SAMPLE_ID},
                   'recovered_how': "unique match of the caption's printed F1 pair (0.67, 0.95) "
                                    'against the committed per-frame datasets',
                   'sources': [f'gs_rerun/late_{SPLIT}.npz', f'gs_rerun/comp_{SPLIT}.npz',
                               f'data/{DATASET[SPLIT]}'],
                   'numbers_drawn': {'qualitative_f1_L': round(f1_l, 4),
                                     'qualitative_f1_F': round(f1_f, 4)},
                   'panel_titles': ['Object-level message L', 'Feature-level message F'],
                   'note': 'panel titles use the deployed action names; the retired C_16 label is '
                           'gone. GT boxes shaded, predictions outlined.'}, f, indent=1)
        f.write('\n')
    print(f'{SPLIT}/sample {SAMPLE_ID}: L F1={f1_l:.4f} ({len(lb)} boxes), '
          f'F F1={f1_f:.4f} ({len(cb)} boxes), {len(gt)} GT')
    print(f'wrote {OUT}\n      {PROV}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
