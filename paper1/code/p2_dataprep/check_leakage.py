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
import itertools
import json
import os
import re
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
PROTOCOL = os.path.join(P1, 'PROTOCOL.md')
CUES_CSV = os.path.join(DATA, 'dataset_validate.csv')
GRID_CSV = os.path.join(GRID, 'p2_grid_validate.csv')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
SCHEMA = 'catosg-frozen-manifest/1'


def protocol_candidate_block():
    """Return (md5, n_candidates) for PROTOCOL.md's CATOSG-CANDIDATES block (single source of truth)."""
    txt = open(PROTOCOL, encoding='utf-8').read()
    m = re.search(r'```json CATOSG-CANDIDATES\s*(\{.*?\})\s*```', txt, re.S)
    if not m:
        raise Fail('CATOSG-CANDIDATES block not found in PROTOCOL.md')
    spec = json.loads(m.group(1))
    hp = spec['hyperparameters']
    combos = list(itertools.product(hp['n_estimators'], hp['max_depth'], hp['min_samples_leaf'],
                                    hp['max_features'], spec['class_weight'], spec['lambda_grid']))
    return hashlib.md5(m.group(1).encode()).hexdigest(), len(combos), spec, combos


def _norm_mf(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return str(v)


def _row_sig(row):
    md = None if pd.isna(row['max_depth']) else int(row['max_depth'])
    cw = None if (pd.isna(row['class_weight']) or row['class_weight'] == '') else row['class_weight']
    return (int(row['n_estimators']), md, int(row['min_samples_leaf']),
            _norm_mf(row['max_features']), cw, round(float(row['lambda']), 6))


def _combo_sig(combo):
    ne, md, ml, mf, cw, lam = combo
    return (ne, md, ml, _norm_mf(mf), cw, round(float(lam), 6))

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
        # R7: assert 112 x 9 = 1008 rows AND per-row candidate params match the PROTOCOL block
        # (enforced EVEN with no manifest, so the LOSO record can never silently drift).
        _, n_cand, _, combos = protocol_candidate_block()
        if len(folds) != n_cand * len(grid_scenes):
            raise Fail(f'validate_loso_folds.csv has {len(folds)} rows, expected {n_cand}x{len(grid_scenes)}')
        want = {i: _combo_sig(c) for i, c in enumerate(combos)}
        have = {}
        for _, r in folds.iterrows():
            have.setdefault(int(r['candidate_index']), _row_sig(r))
        if set(have) != set(want) or any(have[i] != want[i] for i in want):
            bad = [i for i in want if have.get(i) != want[i]][:5]
            raise Fail(f'folds candidate params do not match PROTOCOL block (e.g. index {bad})')
        n = folds['fold_scene'].nunique()
        print(f'  (1) validate grid + LOSO {n}-fold OK: {len(folds)} rows = {n_cand}x{len(grid_scenes)}, '
              f'params match block, each scene held out once; every frame has {COPIES} copies.')
    elif frozen:
        raise Fail('manifest present but validate_loso_folds.csv absent (LOSO record required post-freeze).')
    else:
        print(f'  (1) validate grid complete OK ({len(grid_scenes)} scenes); LOSO folds not yet built '
              '(pre-freeze).')


def check_manifest():
    """Seven frozen-state checks (PROTOCOL sec 6, R6). All FAIL, never skip."""
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
    # check 5: schema exactly the expected version
    if man.get('schema') != SCHEMA:
        raise Fail(f'manifest schema {man.get("schema")!r} != {SCHEMA!r}')
    # check 6: candidate_block_md5 == the current PROTOCOL block
    blk_md5, n_cand, _, _ = protocol_candidate_block()
    if man.get('candidate_block_md5') != blk_md5:
        raise Fail(f'manifest candidate_block_md5 != current PROTOCOL block ({man.get("candidate_block_md5")} '
                   f'!= {blk_md5}) -- candidates changed without a re-freeze.')
    # check 4: declared inputs + grid/cues/folds must all exist (missing = FAIL, no skip)
    for f in (GRID_CSV, CUES_CSV, FOLDS):
        if not os.path.exists(f):
            raise Fail(f'required input absent (no-skip): {os.path.relpath(f, P1)}')
    for key, meta in man['inputs'].items():
        fp = os.path.join(P1, meta['file'])                       # check 10: cue relpath (../OpenCOOD/..) resolves
        if not os.path.exists(fp):
            raise Fail(f'manifest input {key} path does not resolve: {meta["file"]}')
        if 'sha256' in meta:                                     # check 8: folds_csv sha256
            if hashlib.sha256(open(fp, 'rb').read()).hexdigest() != meta['sha256']:
                raise Fail(f'input {key} ({meta["file"]}) sha256 mismatch vs manifest')
        elif hashlib.md5(open(fp, 'rb').read()).hexdigest() != meta['md5']:
            raise Fail(f'input {key} ({meta["file"]}) md5 mismatch vs manifest')
    # check 7: folds CSV exactly n_candidates x folds rows
    folds = pd.read_csv(FOLDS)
    expect = n_cand * man['loso']['folds']
    if len(folds) != expect:
        raise Fail(f'validate_loso_folds.csv has {len(folds)} rows, expected {n_cand}x{man["loso"]["folds"]}={expect}')
    if 'n_frames' not in folds.columns:
        raise Fail('validate_loso_folds.csv missing n_frames column (R6: weighted payload must be recomputable)')
    # per-budget: fields, model file+hash (check 3), frozen payload (check 1), OOF payload (check 2)
    for b, bd in man['budgets'].items():
        bmiss = BUDGET_FIELDS - set(bd)
        if bmiss:
            raise Fail(f'manifest budget {b} missing fields: {sorted(bmiss)}')
        bmax = float(b)
        mp = os.path.join(P1, bd['model'])
        if not os.path.exists(mp):                               # check 3: model file missing = FAIL
            raise Fail(f'budget {b} model file absent (frozen-state, no-skip): {bd["model"]}')
        if hashlib.sha256(open(mp, 'rb').read()).hexdigest() != bd['model_sha256']:
            raise Fail(f'budget {b} model sha256 mismatch (file != manifest)')
        if 'frozen_validate_payload' not in bd or bd['frozen_validate_payload'] > bmax:  # check 1
            raise Fail(f'budget {b} frozen_validate_payload {bd.get("frozen_validate_payload")} > B_max {bmax}')
        if 'loso_frame_weighted_payload' not in bd or bd['loso_frame_weighted_payload'] > bmax:  # check 2
            raise Fail(f'budget {b} frame-weighted OOF payload {bd.get("loso_frame_weighted_payload")} > B_max {bmax}')
        if not bd.get('budget_satisfied', False):
            raise Fail(f'budget {b} budget_satisfied is not True')
        # check 9 (R7): recompute OOF metrics from the folds for this budget's candidate and cross-check
        gc = folds[folds['candidate_index'] == bd['candidate_index']]
        w = gc['n_frames'].to_numpy(dtype=float); W = w.sum()
        oof_pay = float((w * gc['realised_payload'].to_numpy()).sum() / W)
        oof_f1 = float((w * gc['realised_f1'].to_numpy()).sum() / W)
        if abs(oof_pay - bd['loso_frame_weighted_payload']) > 1e-4:
            raise Fail(f'budget {b} OOF payload recomputed {oof_pay:.6f} != manifest {bd["loso_frame_weighted_payload"]}')
        if abs(oof_f1 - bd['loso_frame_weighted_f1']) > 1e-3:
            raise Fail(f'budget {b} OOF F1 recomputed {oof_f1:.4f} != manifest {bd["loso_frame_weighted_f1"]}')
    print(f'  (2) manifest OK [10 checks]: schema+block_md5 match, {len(man["budgets"])} budgets '
          f'frozen_pay+OOF<=B_max, model+folds hashes verified, OOF recomputed from folds, folds={len(folds)} rows.')


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
