#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 RESIDENT LEAKAGE GATE (item 11). Exit 0 iff every invariant holds; else print the first
failing assertion and exit 1. Run on every P2 commit alongside block-exit + paragraph gate.

Enforces the two protocol bans (PROTOCOL.md sec 1-2) on the produced P2 data:

  (1) NO scene straddles the validate train/dev boundary. The split is per-scene, so all 11x2
      channel copies of a scene's frames must share one role. Verified structurally: train/dev
      scene sets are disjoint and cover exactly the scenes present in the validate grid, the grid
      is complete (every frame has all 22 copies, every frame maps to one scene), and no grid scene
      lacks a role. Together these prove no channel copy of any scene can appear on both sides.

  (2) test / Culver-City carry NO training / tuning / threshold-search fingerprint, FREEZE-AWARE
      (PROTOCOL sec 10): pre-freeze (no FROZEN_MANIFEST.json) their grids MUST be absent; post-freeze
      they must exist, contain ONLY the raw expansion columns (no role/train/dev/tau/lambda/fitted/
      selected/threshold), and be built AFTER the manifest timestamp. In both stages the validate
      split artifact must name NO test/Culver scene and results/p2_dataprep/ must hold no test/Culver
      tuning artifact.

  (3) INDEPENDENT frame->scene cross-check: scene_manifest_validate.csv (built by a different code
      path, export_scene_manifest.py) must agree with the _scene_map block-counting, AND the
      dataset's own per-frame cav_keys must be a subset of the reconstructed scene's CAV set
      (real-data correctness anchor, not just internal consistency).

Data-dependent: the validate grid lives in data/p2/ (git-excluded). If absent, the gate FAILS with
an instruction to build it first -- a leakage gate must never silently pass when it cannot verify.

Run:  python paper1/code/p2_dataprep/check_leakage.py
"""
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
MANIFEST = os.path.join(PROV, 'FROZEN_MANIFEST.json')            # P2 freeze marker (PROTOCOL sec 10)

SNR_N, CHAN_N = 11, 2
COPIES = SNR_N * CHAN_N                                           # 22 per frame
FORBIDDEN_COLS = {'role', 'train', 'dev', 'split', 'tau', 'lambda',
                  'fitted', 'selected', 'threshold'}
ALLOWED_GRID_COLS = {'sample_id', 'scene', 'snr_db', 'channel', 'bler_F',
                     'eff_E', 'eff_L', 'eff_F', 'oracle_ELF'}


class Fail(SystemExit):
    def __init__(self, msg):
        super().__init__(f'LEAKAGE GATE FAIL: {msg}')


def _grid(split):
    p = os.path.join(GRID, f'p2_grid_{split}.csv')
    if not os.path.exists(p):
        raise Fail(f'{split} grid absent ({p}); run expand_grid_clean.py first '
                   '(cannot verify leakage without the data).')
    return pd.read_csv(p)


def check_validate_scene_disjoint():
    g = _grid('validate')
    split_csv = os.path.join(PROV, 'validate_scene_split.csv')
    if not os.path.exists(split_csv):
        raise Fail(f'validate scene split absent ({split_csv}); run make_scene_split.py first.')
    sp = pd.read_csv(split_csv)
    train = set(sp.loc[sp.role == 'train', 'scene'])
    dev = set(sp.loc[sp.role == 'dev', 'scene'])

    if train & dev:
        raise Fail(f'scenes in BOTH train and dev: {sorted(train & dev)}')
    grid_scenes = set(g['scene'].unique())
    if (train | dev) != grid_scenes:
        raise Fail(f'split scenes != grid scenes (missing role: '
                   f'{sorted(grid_scenes - (train | dev))}; extra: {sorted((train | dev) - grid_scenes)})')
    # grid completeness: every frame has exactly COPIES rows and maps to a single scene
    per_frame = g.groupby('sample_id')
    sz = per_frame.size()
    if not (sz == COPIES).all():
        bad = sz[sz != COPIES].index.tolist()[:5]
        raise Fail(f'frames without exactly {COPIES} channel copies: e.g. {bad}')
    if not (per_frame['scene'].nunique() == 1).all():
        raise Fail('a frame maps to >1 scene (frame->scene map inconsistent)')
    # each scene present in grid has a role (already covered by set-equality, but assert per-row)
    role_of = {**{s: 'train' for s in train}, **{s: 'dev' for s in dev}}
    if not g['scene'].map(role_of).notna().all():
        raise Fail('some grid rows have a scene with no train/dev role')
    print(f'  (1) validate scene-disjoint OK: {len(train)} train / {len(dev)} dev scenes, '
          f'{len(grid_scenes)} total; every scene single-role; all frames have {COPIES} copies.')


def check_scene_manifest_crosscheck():
    """Independent frame->scene manifest (different code path) must agree with _scene_map, and the
    dataset's own per-frame cav_keys must be a subset of the reconstructed scene's CAV set."""
    man_p = os.path.join(PROV, 'scene_manifest_validate.csv')
    if not os.path.exists(man_p):
        raise Fail(f'scene manifest absent ({man_p}); run export_scene_manifest.py first.')
    man = pd.read_csv(man_p).sort_values('sample_id').reset_index(drop=True)
    labels, _ = scene_labels(OPENCOOD, 'validate', len(man))    # block-counting path
    if list(man['scene']) != list(labels):                      # (a) independent-path agreement
        for i, (a, b) in enumerate(zip(man['scene'], labels)):
            if a != b:
                raise Fail(f'scene manifest vs _scene_map disagree at sample_id {i}: {a} != {b}')
        raise Fail('scene manifest length differs from _scene_map labels')
    ds_p = os.path.join(DATA, 'dataset_validate_v3.csv')         # (b) real-data cav_keys anchor
    if os.path.exists(ds_p):
        ds = pd.read_csv(ds_p)
        if 'cav_keys' in ds.columns and len(ds) == len(man):
            csv_ids = ds['cav_keys'].astype(str).str.split('|')
            scene_ids = man['scene_cav_set'].astype(str).str.split('|')
            for i in range(len(ds)):
                cids = {t for t in csv_ids.iloc[i] if t.isdigit()}
                sids = set(scene_ids.iloc[i])
                if not cids <= sids:
                    raise Fail(f'sample_id {i}: cav_keys {sorted(cids)} not subset of scene CAV set '
                               f'{sorted(sids)} (frame->scene map wrong)')
            print('  (3) manifest cross-check OK: independent frame->scene == _scene_map; '
                  'dataset cav_keys ⊆ reconstructed scene CAV set (real-data anchor).')
            return
    print('  (3) manifest cross-check OK: independent frame->scene == _scene_map '
          '(cav_keys anchor skipped: dataset absent).')


def check_finaltest_clean():
    frozen = os.path.exists(MANIFEST)
    sp = pd.read_csv(os.path.join(PROV, 'validate_scene_split.csv'))
    split_scenes = set(sp['scene'])
    for split in ('test', 'culver'):
        p = os.path.join(GRID, f'p2_grid_{split}.csv')
        if not frozen:
            # PRE-FREEZE (PROTOCOL sec 10): test/Culver grids MUST NOT exist yet.
            if os.path.exists(p):
                raise Fail(f'PRE-FREEZE (no {os.path.basename(MANIFEST)}) but {split} grid exists '
                           f'({p}); test/Culver grids are post-freeze only (PROTOCOL sec 10).')
        else:
            # POST-FREEZE: grid must exist, be column-pure, and be built after the manifest.
            if not os.path.exists(p):
                raise Fail(f'POST-FREEZE but {split} grid absent ({p}); regenerate it post-manifest.')
            cols = set(pd.read_csv(p, nrows=0).columns)
            bad = cols & FORBIDDEN_COLS
            if bad:
                raise Fail(f'{split} grid carries selection/tuning columns: {sorted(bad)}')
            extra = cols - ALLOWED_GRID_COLS
            if extra:
                raise Fail(f'{split} grid has unexpected columns (possible fitting artifact): {sorted(extra)}')
            if os.path.getmtime(p) < os.path.getmtime(MANIFEST):
                raise Fail(f'{split} grid predates {os.path.basename(MANIFEST)} (built before freeze?)')
        # validate split must never assign a role to a test/Culver scene (checked both stages)
        overlap = split_scenes & {s for s, _ in _scene_frame_counts(OPENCOOD, split)}
        if overlap:
            raise Fail(f'validate split assigns a role to {split} scene(s): {sorted(overlap)}')
    # no test/Culver-specific tuning artifact staged in results/p2_dataprep/
    for fn in os.listdir(PROV):
        low = fn.lower()
        if ('test' in low or 'culver' in low) and any(k in low for k in
                                                      ('tau', 'threshold', 'tune', 'fit', 'train')):
            raise Fail(f'test/Culver tuning artifact present in results/p2_dataprep/: {fn}')
    stage = 'POST-FREEZE (grids present, column-pure, built after manifest)' if frozen \
        else 'PRE-FREEZE (grids correctly absent per sec 10)'
    print(f'  (2) test/Culver clean OK [{stage}]; no test/Culver scene in the validate split; '
          'no test/Culver tuning artifact.')


def main():
    print('P2 leakage gate:')
    check_validate_scene_disjoint()
    check_scene_manifest_crosscheck()
    check_finaltest_clean()
    print('LEAKAGE GATE PASS: 0 violations.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
