#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-B-g item 4: the mainline pipeline, parameterised, for the SECOND arm.

The four remaining stages -- grid expansion, scene-level 9-fold LOSO, the budget walk freeze, and
the 200-CSI paired replay -- exist only as mainline scripts with module-level paths baked in. This
driver runs those SAME modules against different inputs by overriding their path constants; it does
not re-implement any of them and it does not edit them, so the generators of the frozen products
stay byte-identical.

**The gate (pre-registered E-Lg2).** Overriding a module's constants is only safe if it changes
nothing else, and that is checked rather than assumed: `--verify` points every stage back at the
MAINLINE inputs, writes to a scratch directory, and bit-compares the result against the committed
mainline product. A stage that does not reproduce its own committed output exactly is wrong, and no
SECOND number is produced from it.

Nothing here writes to `data/p2/`, `FROZEN_MANIFEST.json`, or any deployed artefact: the SECOND arm
writes to `data/p4b/` and `P4B_FROZEN_MANIFEST.json` throughout.

    python projects/ca_tosg/evaluation/second_arm_pipeline.py --verify        # E-Lg2 gate
    python projects/ca_tosg/evaluation/second_arm_pipeline.py --build-dataset
    python projects/ca_tosg/evaluation/second_arm_pipeline.py --stage grid
"""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets',
           'projects/ca_tosg/models'):
    sys.path.insert(0, os.path.join(ROOT, _d))
sys.path.insert(0, ROOT)

MAIN_DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
SECOND_CACHE = os.path.join(OPENCOOD, 'peiyi_work/paper1/gs_rerun_second')
ARM_DATA = os.path.join(ROOT, 'data/p4b')                       # git-excluded, like data/p2
# The arm gets its OWN provenance directory. Pointing it at results/manifests/ made selector.main()
# write candidate_walk_B0XX.csv straight over the DEPLOYED frozen products -- caught by the manifest
# and leakage gates, restored from git. The arm must never share an output directory with the freeze.
ARM_PROV = os.path.join(ROOT, 'results/p4b/manifests')
ARM_OUT = os.path.join(ROOT, 'results/p4b')
ARM_MANIFEST = os.path.join(ARM_PROV, 'P4B_FROZEN_MANIFEST.json')
assert 'p4b' in ARM_PROV, 'arm provenance dir must be arm-private'
SPLITS = ('validate', 'test', 'culver')
MAIN_DATASET = {'validate': 'dataset_validate.csv', 'test': 'dataset_test_v3.csv',
                'culver': 'dataset_culver_v3.csv'}
ARM_DATASET = {s: f'dataset_{s}_second.csv' for s in SPLITS}


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


# ------------------------------------------------------------------ dataset assembly
def build_dataset():
    """SECOND per-frame dataset = mainline cues + SECOND's own F1s and ego object count.

    Of the 21 task cues, 20 are LiDAR geometry / scene metadata and are detector-independent, so
    they are reused verbatim. `ego_num_objects` is the one detector-dependent cue and is taken from
    the SECOND ego cache. The three F1 columns come from the SECOND caches.
    """
    os.makedirs(ARM_DATA, exist_ok=True)
    rows = []
    for split in SPLITS:
        base = pd.read_csv(os.path.join(MAIN_DATA, MAIN_DATASET[split]))
        ego = np.load(os.path.join(SECOND_CACHE, f'ego_{split}.npz'), allow_pickle=True)
        comp = np.load(os.path.join(SECOND_CACHE, f'comp_{split}.npz'), allow_pickle=True)
        late = np.load(os.path.join(SECOND_CACHE, f'late_{split}.npz'), allow_pickle=True)
        n = len(base)
        for name, arr in (('ego', ego['f1']), ('comp', comp['f1']), ('late', late['f1'])):
            assert len(arr) == n, f'{split}: {name} cache has {len(arr)} frames, dataset has {n}'
        out = base.copy()
        out['ego_f1'] = np.asarray(ego['f1'], dtype=float)
        out['compressed_f1'] = np.asarray(comp['f1'], dtype=float)
        out['late_f1'] = np.asarray(late['f1'], dtype=float)
        out['ego_num_objects'] = np.asarray(ego['num_objects'], dtype=float)
        p = os.path.join(ARM_DATA, ARM_DATASET[split])
        out.to_csv(p, index=False)
        rows.append(dict(split=split, frames=n, path=p, md5=md5(p),
                         ego_f1=round(float(out.ego_f1.mean()), 5),
                         late_f1=round(float(out.late_f1.mean()), 5),
                         compressed_f1=round(float(out.compressed_f1.mean()), 5),
                         ego_num_objects=round(float(out.ego_num_objects.mean()), 3)))
        print(f'[{split}] n={n}  ego={out.ego_f1.mean():.5f}  late={out.late_f1.mean():.5f}  '
              f'comp={out.compressed_f1.mean():.5f}  ego_objs={out.ego_num_objects.mean():.2f}')
    return rows


# ------------------------------------------------------------------ stage runners
def run_grid(dataset_dir, dataset_names, out_data, splits):
    import grid_builder as G
    old = (G.DATA, dict(G.DATASET_NAME), G.OUT_DATA)
    G.DATA, G.OUT_DATA = dataset_dir, out_data
    G.DATASET_NAME = dict(dataset_names)
    os.makedirs(out_data, exist_ok=True)
    tbl = pd.read_csv(G.BLER_CSV)
    try:
        return {s: G.expand_split(s, tbl) for s in splits}
    finally:
        G.DATA, G.DATASET_NAME, G.OUT_DATA = old[0], old[1], old[2]


def verify_grid():
    """E-Lg2 stage 1: re-expand the MAINLINE grid into scratch and bit-compare."""
    tmp = tempfile.mkdtemp(prefix='p4b_verify_grid_')
    try:
        run_grid(MAIN_DATA, MAIN_DATASET, tmp, SPLITS)
        ok = True
        for s in SPLITS:
            a = os.path.join(ROOT, 'data/p2', f'p2_grid_{s}.csv')
            b = os.path.join(tmp, f'p2_grid_{s}.csv')
            if not os.path.exists(a):
                print(f'  grid {s}: committed product absent ({a}) -- cannot verify')
                ok = False
                continue
            same = filecmp.cmp(a, b, shallow=False)
            print(f'  grid {s}: {"BIT-IDENTICAL" if same else "**DIFFERS**"}  '
                  f'({md5(a)[:8]} vs {md5(b)[:8]})')
            ok &= same
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _patch(mod, **kw):
    old = {k: getattr(mod, k) for k in kw}
    for k, v in kw.items():
        setattr(mod, k, v)
    return old


def _aliases(basename):
    """Every module object in sys.modules that IS this source file.

    A module reachable by two import paths exists TWICE in sys.modules -- `feature_encoder` and
    `projects.ca_tosg.models.feature_encoder` are different objects. Patching one leaves the other
    untouched, which is how the first version of this driver silently ran the SECOND arm on the
    MAINLINE inputs and still reported a PASS. Patch every alias, always.
    """
    out = []
    for name, m in list(sys.modules.items()):
        if m is None or not hasattr(m, '__file__') or not m.__file__:
            continue
        if os.path.basename(m.__file__) == basename + '.py':
            out.append(m)
    return out


def _patch_all(basename, **kw):
    mods = _aliases(basename)
    assert mods, f'{basename} is not imported yet -- nothing to patch'
    return [(m, _patch(m, **kw)) for m in mods]


def run_selector(cues_csv, grid_csv, out_model, out_prov, manifest, folds_csv, prov_dir,
                 force_fresh_loso=False):
    """selector.main() with its paths redirected. The module itself is never edited."""
    import feature_encoder  # noqa: F401  (ensures at least one alias exists)
    import selector  # noqa: F401
    from projects.ca_tosg.models import feature_encoder as _fe2  # noqa: F401
    from projects.ca_tosg.models import selector as _sel2  # noqa: F401

    fe = _patch_all('feature_encoder', CUES_CSV=cues_csv, GRID_CSV=grid_csv)
    sel = _patch_all('selector', OUT_MODEL=out_model, OUT_PROV=out_prov, MANIFEST=manifest,
                     FOLDS_CSV=(folds_csv if not force_fresh_loso
                                else folds_csv + '.forced-fresh'), PROV_DIR=prov_dir)
    # POSITIVE CONTROL: every alias must now report the intended inputs, or the redirect is inert
    for m in _aliases('feature_encoder'):
        assert m.GRID_CSV == grid_csv and m.CUES_CSV == cues_csv, \
            f'redirect did not take on {m.__name__} -- refusing to run'
    os.makedirs(out_model, exist_ok=True)
    os.makedirs(out_prov, exist_ok=True)
    os.makedirs(prov_dir, exist_ok=True)
    try:
        for m in _aliases('selector'):
            m.main()
            break
    finally:
        for m, old in fe + sel:
            _patch(m, **old)


def verify_selector(force_fresh_loso):
    """E-Lg2 stage 2: re-run LOSO/walk/freeze on MAINLINE inputs into scratch and compare.

    `force_fresh_loso` points FOLDS_CSV at a path that does not exist, so the 1,008 fits are
    actually recomputed instead of reused -- otherwise the check would only exercise the walk and
    the manifest writer, not the cross-validation itself.
    """
    tmp = tempfile.mkdtemp(prefix='p4b_verify_sel_')
    try:
        run_selector(os.path.join(MAIN_DATA, 'dataset_validate.csv'),
                     os.path.join(ROOT, 'data/p2/p2_grid_validate.csv'),
                     os.path.join(tmp, 'model'), tmp,
                     os.path.join(tmp, 'FROZEN_MANIFEST.json'),
                     os.path.join(tmp, 'validate_loso_folds.csv'),
                     os.path.join(tmp, 'prov'), force_fresh_loso=force_fresh_loso)
        ok = True
        a = os.path.join(ROOT, 'results/manifests/validate_loso_folds.csv')
        b = os.path.join(tmp, 'validate_loso_folds.csv' + ('.forced-fresh' if force_fresh_loso
                                                           else ''))
        if os.path.exists(b):
            same = filecmp.cmp(a, b, shallow=False)
            print(f'  LOSO folds CSV: {"BIT-IDENTICAL" if same else "**DIFFERS**"}')
            ok &= same
        for name in ('candidate_walk_B010.csv', 'candidate_walk_B020.csv',
                     'candidate_walk_B030.csv'):
            a = os.path.join(ROOT, 'results/manifests', name)
            b = os.path.join(tmp, name)
            if os.path.exists(b) and os.path.exists(a):
                same = filecmp.cmp(a, b, shallow=False)
                print(f'  {name}: {"BIT-IDENTICAL" if same else "**DIFFERS**"}')
                ok &= same
        am = json.load(open(os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')))
        bm = json.load(open(os.path.join(tmp, 'FROZEN_MANIFEST.json')))
        for b_tag in sorted(am['budgets']):
            fields = ('candidate_index', 'lambda_star', 'tau_star', 'walk_depth',
                      'frozen_validate_f1', 'frozen_validate_payload', 'class_weight')
            same = all(am['budgets'][b_tag][f] == bm['budgets'][b_tag][f] for f in fields)
            print(f'  manifest budget {b_tag}: {"MATCH" if same else "**DIFFERS**"} '
                  f'(cand/lambda/tau/depth/f1/payload/cw)')
            ok &= same
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_replay(data_dir, dataset_names, grid_dir, manifest, out_dir, prov_dir):
    """deployment.main() with its paths redirected -- the 200-CSI paired replay, unmodified."""
    import deployment as D
    old = _patch(D, DATA=data_dir, DATASET=dict(dataset_names), GRID_DIR=grid_dir,
                 MANIFEST=manifest, OUT=out_dir, PROV_DIR=prov_dir)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(prov_dir, exist_ok=True)
    try:
        D.main()
        # deployment.py always writes r9_decision.csv. For THIS arm that file is a side effect of
        # reusing the mainline script unmodified, not a decision: the arm is descriptive with
        # paired CIs and delta is neither used nor changed here. Publishing it would leave a second
        # file that reads like an R9 adjudication, so it is removed on every run rather than
        # explained away in a footnote nobody reads next to the CSV.
        stray = os.path.join(out_dir, 'r9_decision.csv')
        if os.path.exists(stray):
            os.remove(stray)
            print(f'removed {stray} -- this arm takes no decision (P4-B-f)')
    finally:
        _patch(D, **old)


def verify_replay():
    """E-Lg2 stage 3: re-run the MAINLINE replay into scratch and compare replay_summary.csv."""
    tmp = tempfile.mkdtemp(prefix='p4b_verify_rep_')
    try:
        run_replay(MAIN_DATA, MAIN_DATASET, os.path.join(ROOT, 'data/p2'),
                   os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json'),
                   tmp, os.path.join(tmp, 'prov'))
        a = os.path.join(ROOT, 'results/main/replay_summary.csv')
        b = os.path.join(tmp, 'replay_summary.csv')
        if not os.path.exists(b):
            print('  replay: no output produced')
            return False
        da = pd.read_csv(a)
        da = da[da['split'] != 'split']
        db = pd.read_csv(b)
        key = ['split', 'budget']
        cols = [c for c in db.columns if c not in key]
        da[key[1]] = da[key[1]].astype(float)
        db[key[1]] = db[key[1]].astype(float)
        m = da.merge(db, on=key, suffixes=('_ref', '_new'))
        ok = len(m) == len(db)
        bad = []
        for c in cols:
            if f'{c}_ref' not in m:
                continue
            for i in m.index:
                x, y = m.loc[i, f'{c}_ref'], m.loc[i, f'{c}_new']
                if str(x) != str(y):
                    bad.append((m.loc[i, 'split'], m.loc[i, 'budget'], c, x, y))
        print(f'  replay_summary.csv: {len(m)} rows compared, '
              f'{"IDENTICAL" if not bad else str(len(bad)) + " cell(s) DIFFER"}')
        for r in bad[:12]:
            print(f'    {r}')
        return ok and not bad
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true', help='E-Lg2: reproduce the mainline products')
    ap.add_argument('--build-dataset', action='store_true')
    ap.add_argument('--stage', choices=['grid', 'selector', 'replay'],
                    help='run a stage for the SECOND arm')
    ap.add_argument('--verify-stage', choices=['grid', 'selector', 'replay'],
                    default=None)
    ap.add_argument('--fresh-loso', action='store_true',
                    help='force the LOSO fits to be recomputed during --verify')
    args = ap.parse_args()

    if args.verify:
        print('=== E-Lg2: parameterised stages must reproduce the committed mainline products ===')
        want = args.verify_stage
        ok = True
        if want in (None, 'grid'):
            ok &= verify_grid()
            print(f'E-Lg2 stage "grid": {"PASS" if ok else "FAIL"}')
        if want in (None, 'replay'):
            o = verify_replay()
            print(f'E-Lg2 stage "replay": {"PASS" if o else "FAIL"}')
            ok &= o
        if want in (None, 'selector'):
            o = verify_selector(args.fresh_loso)
            print(f'E-Lg2 stage "selector": {"PASS" if o else "FAIL"}'
                  f'{" (LOSO fits recomputed)" if args.fresh_loso else " (folds reused)"}')
            ok &= o
        return 0 if ok else 1

    if args.build_dataset:
        rows = build_dataset()
        out = os.path.join(ARM_PROV, 'P4B_DATASET_MANIFEST.json')
        with open(out, 'w') as f:
            json.dump({'schema': 'catosg-p4b-dataset/1',
                       'label': 'second-backbone arm, not deployed',
                       'generated_by': 'python projects/ca_tosg/evaluation/'
                                       'second_arm_pipeline.py --build-dataset',
                       'cues': '20 of 21 task cues are detector-independent (LiDAR geometry / scene '
                               'metadata) and are reused verbatim from the mainline dataset; '
                               'ego_num_objects is the one detector-dependent cue and comes from '
                               "SECOND's own ego cache",
                       'splits': rows}, f, indent=1)
            f.write('\n')
        print(f'\nwrote {out}')
        return 0

    if args.stage == 'replay':
        run_replay(ARM_DATA, ARM_DATASET, ARM_DATA, ARM_MANIFEST, ARM_OUT,
                   os.path.join(ROOT, 'results/provenance'))
        return 0

    if args.stage == 'selector':
        assert os.path.abspath(ARM_PROV) != os.path.abspath(os.path.join(ROOT, 'results/manifests')), \
            'the arm may not write into the deployed manifests directory'
        run_selector(os.path.join(ARM_DATA, ARM_DATASET['validate']),
                     os.path.join(ARM_DATA, 'p2_grid_validate.csv'),
                     ARM_DATA, ARM_PROV, ARM_MANIFEST,
                     os.path.join(ARM_PROV, 'P4B_validate_loso_folds.csv'),
                     os.path.join(ARM_OUT, 'provenance'))
        return 0

    if args.stage == 'grid':
        res = run_grid(ARM_DATA, ARM_DATASET, ARM_DATA, SPLITS)
        for s, r in res.items():
            print(f'[{s}] rows={r["rows"]} scenes={r["n_scenes"]} md5={r["md5"][:8]} '
                  f'base_rate={ {k: round(v, 4) for k, v in r["base_rate"].items()} }')
        return 0

    ap.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
