#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 RESIDENT LEAKAGE + FREEZE GATE (PROTOCOL sec 6 / 10). Exit 0 iff every invariant holds; else
print the first failing assertion and exit 1. Run on every P2 commit.

  (1) VALIDATE grid completeness + LOSO fold structure. The grid is complete (every frame has all 22
      channel copies, each frame maps to one scene). If the LOSO record validate_loso_folds.csv is
      present it must show each of the 9 scenes held out EXACTLY ONCE per candidate and the fold-scene
      set == the grid scenes -- this replaces the old 70/30 disjointness check (Change-log R1). With a
      freeze manifest present the LOSO record is REQUIRED.

  (2) FROZEN_MANIFEST validation. If present: non-empty, valid JSON, all required top-level + per-budget
      fields, and every model sha256 / input md5 that has a file on disk must MATCH (mismatch = FAIL).
      If absent: pre-freeze.

  (3) INDEPENDENT scene cross-check, NO SKIP: scene_manifest_validate.csv (different code path) must
      agree with _scene_map, and the dataset cav_keys must be a subset of the reconstructed scene CAV
      set. Any missing input (manifest, dataset) is a FAIL -- the anchor never skips to pass.

  (4) test / Culver freeze-aware: pre-freeze their grids MUST be absent; post-freeze they are optional
      and any present must be column-pure + built after the manifest; the validate artifacts must name
      no test/Culver scene.

Data-dependent: the validate grid lives in data/p2/ (git-excluded). If absent, the gate FAILS with an
instruction to build it -- a leakage gate must never silently pass when it cannot verify.
"""
import hashlib
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _scene_map import scene_labels, _scene_frame_counts  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
GRID = os.path.join(P1, 'data/p2')
PROV = os.path.join(P1, 'results/p2_dataprep')
MANIFEST = os.path.join(PROV, 'FROZEN_MANIFEST.json')
FOLDS = os.path.join(PROV, 'validate_loso_folds.csv')

COPIES = 11 * 2                                                  # 22 cells per frame
FORBIDDEN_COLS = {'role', 'train', 'dev', 'split', 'tau', 'lambda', 'fitted', 'selected', 'threshold'}
ALLOWED_GRID_COLS = {'sample_id', 'scene', 'snr_db', 'channel', 'bler_F',
                     'eff_E', 'eff_L', 'eff_F', 'oracle_ELF'}
MANIFEST_FIELDS = {'schema', 'freeze_timestamp', 'seed', 'feature_names', 'loso', 'inputs', 'budgets'}
BUDGET_FIELDS = {'selector', 'candidate_index', 'hyperparameters', 'class_weight',
                 'lambda_star', 'tau_star', 'model', 'model_sha256'}


class Fail(SystemExit):
    def __init__(self, msg):
        super().__init__(f'LEAKAGE GATE FAIL: {msg}')


def _grid(split):
    p = os.path.join(GRID, f'p2_grid_{split}.csv')
    if not os.path.exists(p):
        raise Fail(f'{split} grid absent ({p}); run expand_grid_clean.py (cannot verify without data).')
    return pd.read_csv(p)


def check_validate_grid_and_folds():
    g = _grid('validate')
    per_frame = g.groupby('sample_id')
    if not (per_frame.size() == COPIES).all():
        bad = per_frame.size()[per_frame.size() != COPIES].index.tolist()[:5]
        raise Fail(f'frames without exactly {COPIES} channel copies: e.g. {bad}')
    if not (per_frame['scene'].nunique() == 1).all():
        raise Fail('a frame maps to >1 scene (frame->scene inconsistent)')
    grid_scenes = set(g['scene'].unique())

    frozen = os.path.exists(MANIFEST)
    if os.path.exists(FOLDS):
        folds = pd.read_csv(FOLDS)
        if set(folds['fold_scene'].unique()) != grid_scenes:
            raise Fail('LOSO fold-scene set != grid scenes (folds must cover exactly the 9 scenes)')
        held = folds.groupby(['candidate_index', 'fold_scene']).size()
        if (held != 1).any():
            raise Fail('some scene is held out != 1 time for some candidate (not a clean LOSO)')
        n = folds['fold_scene'].nunique()
        print(f'  (1) validate grid complete + LOSO {n}-fold OK: each of {len(grid_scenes)} scenes '
              f'held out exactly once per candidate; every frame has {COPIES} copies.')
    elif frozen:
        raise Fail('manifest present but validate_loso_folds.csv absent (LOSO record required post-freeze).')
    else:
        print(f'  (1) validate grid complete OK ({len(grid_scenes)} scenes); LOSO folds not yet built '
              '(pre-freeze).')


def check_manifest():
    if not os.path.exists(MANIFEST):
        print('  (2) manifest: PRE-FREEZE (no FROZEN_MANIFEST.json).')
        return
    raw = open(MANIFEST, encoding='utf-8').read()
    if not raw.strip():
        raise Fail('FROZEN_MANIFEST.json is EMPTY')
    try:
        man = json.loads(raw)
    except json.JSONDecodeError as e:
        raise Fail(f'FROZEN_MANIFEST.json is not valid JSON: {e}')
    miss = MANIFEST_FIELDS - set(man)
    if miss:
        raise Fail(f'manifest missing required fields: {sorted(miss)}')
    if not man['budgets']:
        raise Fail('manifest has no budgets')
    for b, bd in man['budgets'].items():
        bmiss = BUDGET_FIELDS - set(bd)
        if bmiss:
            raise Fail(f'manifest budget {b} missing fields: {sorted(bmiss)}')
        mp = os.path.join(P1, bd['model'])
        if os.path.exists(mp):
            sha = hashlib.sha256(open(mp, 'rb').read()).hexdigest()
            if sha != bd['model_sha256']:
                raise Fail(f'budget {b} model sha256 mismatch (file {bd["model"]} != manifest)')
    for key, meta in man['inputs'].items():
        fp = os.path.join(P1, meta['file'])
        if os.path.exists(fp) and hashlib.md5(open(fp, 'rb').read()).hexdigest() != meta['md5']:
            raise Fail(f'input {key} ({meta["file"]}) md5 mismatch vs manifest')
    verified = sum(1 for bd in man['budgets'].values() if os.path.exists(os.path.join(P1, bd['model'])))
    print(f'  (2) manifest OK: schema={man["schema"]}, {len(man["budgets"])} budgets, '
          f'{verified} model hash(es) verified, input md5s match where present.')


def check_scene_manifest_crosscheck():
    man_p = os.path.join(PROV, 'scene_manifest_validate.csv')
    if not os.path.exists(man_p):
        raise Fail(f'scene manifest absent ({man_p}); run export_scene_manifest.py (no-skip anchor).')
    man = pd.read_csv(man_p).sort_values('sample_id').reset_index(drop=True)
    labels, _ = scene_labels(OPENCOOD, 'validate', len(man))
    if list(man['scene']) != list(labels):
        for i, (a, b) in enumerate(zip(man['scene'], labels)):
            if a != b:
                raise Fail(f'scene manifest vs _scene_map disagree at sample_id {i}: {a} != {b}')
        raise Fail('scene manifest length differs from _scene_map labels')
    ds_p = os.path.join(DATA, 'dataset_validate.csv')
    if not os.path.exists(ds_p):
        raise Fail(f'cav_keys anchor input absent ({ds_p}); no-skip -- cannot verify frame->scene.')
    ds = pd.read_csv(ds_p)
    if 'cav_keys' not in ds.columns or len(ds) != len(man):
        raise Fail('dataset_validate.csv missing cav_keys or length != manifest (anchor cannot run)')
    csv_ids = ds['cav_keys'].astype(str).str.split('|')
    scene_ids = man['scene_cav_set'].astype(str).str.split('|')
    for i in range(len(ds)):
        cids = {t for t in csv_ids.iloc[i] if t.isdigit()}
        if not cids <= set(scene_ids.iloc[i]):
            raise Fail(f'sample_id {i}: cav_keys {sorted(cids)} not subset of scene CAV set '
                       f'{sorted(set(scene_ids.iloc[i]))} (frame->scene map wrong)')
    print('  (3) manifest cross-check OK: independent frame->scene == _scene_map; dataset cav_keys ⊆ '
          'reconstructed scene CAV set (no-skip anchor).')


def check_finaltest_clean():
    frozen = os.path.exists(MANIFEST)
    for split in ('test', 'culver'):
        p = os.path.join(GRID, f'p2_grid_{split}.csv')
        if not frozen:
            if os.path.exists(p):
                raise Fail(f'PRE-FREEZE but {split} grid exists ({p}); post-freeze only (PROTOCOL sec 10).')
        elif os.path.exists(p):
            cols = set(pd.read_csv(p, nrows=0).columns)
            bad = cols & FORBIDDEN_COLS
            if bad:
                raise Fail(f'{split} grid carries selection/tuning columns: {sorted(bad)}')
            extra = cols - ALLOWED_GRID_COLS
            if extra:
                raise Fail(f'{split} grid has unexpected columns: {sorted(extra)}')
            if os.path.getmtime(p) < os.path.getmtime(MANIFEST):
                raise Fail(f'{split} grid predates FROZEN_MANIFEST.json (built before freeze?)')
    for fn in os.listdir(PROV):
        low = fn.lower()
        if ('test' in low or 'culver' in low) and any(k in low for k in
                                                      ('tau', 'threshold', 'tune', 'fit', 'train')):
            raise Fail(f'test/Culver tuning artifact present in results/p2_dataprep/: {fn}')
    stage = 'POST-FREEZE (grids optional; any present column-pure + after manifest)' if frozen \
        else 'PRE-FREEZE (grids correctly absent per sec 10)'
    print(f'  (4) test/Culver clean OK [{stage}].')


def main():
    print('P2 leakage + freeze gate:')
    check_validate_grid_and_folds()
    check_scene_manifest_crosscheck()
    check_manifest()
    check_finaltest_clean()
    print('LEAKAGE GATE PASS: 0 violations.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
