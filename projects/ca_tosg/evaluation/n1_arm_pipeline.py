#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 corrigendum: re-run the mainline pipeline under the N=1 collaborator convention.

Change-log P0 ruling (a): the main experiment is the **nearest single collaborator**, so that one
message is paid for and one collaborator's information is received. The committed mainline fused
every collaborator in the frame while charging a single message.

No new perception inference is needed — P4-C already built the N=1 caches
(`gs_rerun/p4c_N1/{late,intermediate}_{split}.npz`). This driver reuses the SECOND arm's stage
runners verbatim (`second_arm_pipeline.run_grid` / `run_selector` / `run_replay`), which redirect
the mainline modules' path constants without editing them, so the generators of the frozen products
stay byte-identical.

**Self-check before every stage.** `--verify` points each stage back at the MAINLINE inputs, writes
to scratch, and bit-compares against the committed mainline product. A stage that cannot reproduce
its own committed output is wrong, and no N=1 number is taken from it.

Nothing here writes to `data/p2/`, `results/manifests/`, or any deployed artefact: the arm writes to
`data/p0_n1/` and `results/p0_n1/` throughout, behind an assertion.

    python projects/ca_tosg/evaluation/n1_arm_pipeline.py --verify
    python projects/ca_tosg/evaluation/n1_arm_pipeline.py --build-dataset
    python projects/ca_tosg/evaluation/n1_arm_pipeline.py --stage grid
    python projects/ca_tosg/evaluation/n1_arm_pipeline.py --stage selector   # STOP POINT after this
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets',
           'projects/ca_tosg/models'):
    sys.path.insert(0, os.path.join(ROOT, _d))
sys.path.insert(0, ROOT)

import second_arm_pipeline as S  # noqa: E402  (stage runners + E-Lg2 verifiers, reused as-is)

GS = os.path.join(OPENCOOD, 'peiyi_work/paper1/gs_rerun')
N1_CACHE = os.path.join(GS, 'p4c_N1')
ARM_DATA = os.path.join(ROOT, 'data/p0_n1')                 # git-excluded, like data/p2
ARM_PROV = os.path.join(ROOT, 'results/p0_n1/manifests')    # arm-private: never results/manifests/
ARM_OUT = os.path.join(ROOT, 'results/p0_n1')
ARM_MANIFEST = os.path.join(ARM_PROV, 'N1_FROZEN_MANIFEST.json')
assert 'p0_n1' in ARM_PROV and 'p0_n1' in ARM_DATA, 'arm directories must be arm-private'
SPLITS = ('validate', 'test', 'culver')
ARM_DATASET = {s: f'dataset_{s}_n1.csv' for s in SPLITS}


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def f1_from_boxes(pred, gt, iou=0.5):
    """The shared scorer: IoU 0.5, unit scores, canonical union GT."""
    import torch

    from opencood.utils import eval_utils
    pred = np.asarray(pred, np.float32)
    gt = np.asarray(gt, np.float32)
    pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
    gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
    rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, iou)
    tp, fp, g = float(sum(rs[iou]['tp'])), float(sum(rs[iou]['fp'])), float(rs[iou]['gt'])
    p = tp / (tp + fp) if tp + fp > 0 else 0.0
    r = tp / g if g > 0 else 0.0
    return 2 * p * r / (p + r) if p + r > 0 else 0.0


def build_dataset():
    """N=1 dataset = mainline cues, mainline ego column, N=1 late/compressed utilities.

    Scored against the SAME canonical union GT as every other arm (P4-C ruling 1): restricting the
    CAV set also shrinks the post-processor's union GT, and per-N GT would put each arm on a
    different ruler. `ego_f1` and the 21 cues are N-independent and are reused verbatim.
    """
    sys.path.insert(0, OPENCOOD)
    os.makedirs(ARM_DATA, exist_ok=True)
    rows = []
    for split in SPLITS:
        base = pd.read_csv(os.path.join(S.MAIN_DATA, S.MAIN_DATASET[split]))
        gts = np.load(os.path.join(GS, f'comp_{split}.npz'), allow_pickle=True)['gts']
        assert len(gts) == len(base), f'{split}: GT {len(gts)} vs dataset {len(base)}'
        out = base.copy()
        for branch, col in (('late', 'late_f1'), ('intermediate', 'compressed_f1')):
            z = np.load(os.path.join(GS, f'p4c_N1/{branch}_{split}.npz'), allow_pickle=True)
            assert len(z['boxes']) == len(base), f'{split}/{branch}: cache/dataset frame mismatch'
            new = np.array([f1_from_boxes(z['boxes'][i], gts[i]) for i in range(len(gts))])
            print(f'  [{split}] {col}: full-set {base[col].mean():.5f} -> N=1 {new.mean():.5f} '
                  f'({new.mean() - base[col].mean():+.5f})')
            out[col] = new
        p = os.path.join(ARM_DATA, ARM_DATASET[split])
        out.to_csv(p, index=False)
        rows.append(dict(split=split, frames=len(out), path=os.path.relpath(p, ROOT), md5=md5(p),
                         ego_f1=round(float(out.ego_f1.mean()), 5),
                         late_f1=round(float(out.late_f1.mean()), 5),
                         compressed_f1=round(float(out.compressed_f1.mean()), 5)))
    os.makedirs(ARM_PROV, exist_ok=True)
    with open(os.path.join(ARM_PROV, 'N1_DATASET_MANIFEST.json'), 'w') as f:
        json.dump(dict(schema='catosg-n1-dataset/1', generated=datetime.now(timezone.utc).isoformat(),
                       convention='N=1 nearest collaborator (Change-log P0 ruling (a))',
                       gt='canonical union GT of the FULL collaborator set (P4-C ruling 1)',
                       source_cache=os.path.relpath(N1_CACHE, OPENCOOD), splits=rows), f, indent=2)
    return rows


def stage_grid():
    print('N=1 grid expansion ->', os.path.relpath(ARM_DATA, ROOT))
    S.run_grid(ARM_DATA, ARM_DATASET, ARM_DATA, SPLITS)
    for s in SPLITS:
        p = os.path.join(ARM_DATA, f'p2_grid_{s}.csv')
        d = pd.read_csv(p)
        print(f'  p2_grid_{s}.csv: {len(d)} rows, md5 {md5(p)[:8]}, '
              f'oracle mix {dict(d.oracle_ELF.value_counts())}')


def stage_selector():
    print('N=1 LOSO + candidate walk + freeze ->', os.path.relpath(ARM_PROV, ROOT))
    S.run_selector(os.path.join(ARM_DATA, ARM_DATASET['validate']),
                   os.path.join(ARM_DATA, 'p2_grid_validate.csv'),
                   os.path.join(ARM_DATA, 'model'), ARM_PROV, ARM_MANIFEST,
                   os.path.join(ARM_PROV, 'validate_loso_folds.csv'), ARM_PROV)


def report_stop_point():
    """The pre-registered stop point: lambda*, tau* and payload, before any replay."""
    m = json.load(open(ARM_MANIFEST))
    print('\n' + '=' * 78)
    print('P0-2 STOP POINT -- frozen N=1 selectors (no replay has run)')
    print('=' * 78)
    print(f'{"budget":8s} {"cand":>5s} {"lambda*":>10s} {"tau*":>8s} {"depth":>6s} '
          f'{"val F1":>9s} {"val payload":>12s} {"class_weight":>13s}')
    for tag in sorted(m['budgets']):
        b = m['budgets'][tag]
        print(f'{tag:8s} {b["candidate_index"]:5d} {b["lambda_star"]:10.5f} {b["tau_star"]:8.3f} '
              f'{b["walk_depth"]:6d} {b["frozen_validate_f1"]:9.5f} '
              f'{b["frozen_validate_payload"]:12.5f} {str(b["class_weight"]):>13s}')
    dep = os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')
    if os.path.exists(dep):
        d = json.load(open(dep))
        print('\nagainst the DEPLOYED (full-collaborator) freeze, for comparison only:')
        for tag in sorted(d['budgets']):
            a, b = d['budgets'][tag], m['budgets'].get(tag)
            if not b:
                continue
            print(f'  {tag}: cand {a["candidate_index"]}->{b["candidate_index"]}  '
                  f'lambda* {a["lambda_star"]:.5f}->{b["lambda_star"]:.5f}  '
                  f'tau* {a["tau_star"]:.3f}->{b["tau_star"]:.3f}  '
                  f'F1 {a["frozen_validate_f1"]:.5f}->{b["frozen_validate_f1"]:.5f}  '
                  f'payload {a["frozen_validate_payload"]:.5f}->'
                  f'{b["frozen_validate_payload"]:.5f}')
    print('\nSTOP: the 200-CSI replay and R9 are NOT run until these are cleared.')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true',
                    help='bit-reproduce the committed MAINLINE products (self-check)')
    ap.add_argument('--fresh-loso', action='store_true',
                    help='with --verify: recompute the 1,008 LOSO fits instead of reusing them')
    ap.add_argument('--build-dataset', action='store_true')
    ap.add_argument('--stage', choices=('grid', 'selector', 'report'))
    a = ap.parse_args()
    if a.verify:
        print('E-Lg2 self-check, stage 1 (grid): re-expanding the MAINLINE grid into scratch')
        ok = S.verify_grid()
        print('E-Lg2 self-check, stage 2 (selector): re-running LOSO/walk/freeze on MAINLINE inputs')
        ok &= S.verify_selector(a.fresh_loso)
        print('SELF-CHECK ' + ('PASS -- stages reproduce their committed products bit-for-bit'
                               if ok else 'FAIL -- no N=1 number may be taken from these stages'))
        return 0 if ok else 1
    if a.build_dataset:
        build_dataset()
        return 0
    if a.stage == 'grid':
        stage_grid()
    elif a.stage == 'selector':
        stage_selector()
        report_stop_point()
    elif a.stage == 'report':
        report_stop_point()
    return 0


if __name__ == '__main__':
    sys.exit(main())
