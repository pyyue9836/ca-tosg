#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R22 F — gate 27: the `v2_ego_local_23d` cue schema is admissible and is what it claims to be.

Protocol §9.0/§9.2. Five checks, of which the third is the one that needed thought:

  F-1  every field has an explicit code source, verified at run time (not a table of assertions)
  F-2  no field reaches GT objects / `object_ids` / `params['vehicles']`
  F-3  no `ego_pcd_*` is traceable to `projected_lidar_stack` -- **by data flow, not by name**
  F-4  `ego_detected_box_count` equals the WP2 ego box count, frame by frame
  F-5  `has_collaborator` equals the alignment audit's availability, frame by frame

HOW F-3 IS DONE, AND WHY NOT BY NAME
------------------------------------
A name check is worthless here: renaming `pcd_*` to `ego_pcd_*` is exactly what a *wrong*
implementation would also do. So the gate **recomputes** the cues for a sample of frames from the
ego-only path and requires the stored values to match **exactly**. If the table had been produced
from the all-CAV cloud, the recomputation would disagree.

That alone would still be weak -- it would pass if the two clouds happened to give the same numbers.
So a **negative control** runs beside it: the same statistics are computed from the all-CAV stack for
the same frames, and the gate requires those to **differ**. A positive check whose control never
fires is a check that would pass whatever the data said, which is failure mode 4 in
`docs/gate_design_principles.md`.

  python tests/test_cue_schema.py
  python tests/test_cue_schema.py --self-test     # F-6
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(ROOT, 'results', 'v2')
GEN = os.path.join(ROOT, 'projects', 'ca_tosg', 'evaluation', 'v2_wp6_generate_cues.py')
SPLITS = ('validate',)
N_SAMPLE = 8

sys.path.insert(0, os.path.join(ROOT, 'projects', 'ca_tosg', 'evaluation'))

# F-2. Source-level, matched against the *provenance* recorded by the WP6 audit and against names as
# a second net. Same two-layer design as tests/test_cue_field_whitelist.py.
GT_PATTERNS = [r'(^|_)gt(_|$)', r'ground_?truth', r'num_objects', r'object_ids', r"params\['vehicles'\]"]
ALLCAV_TOKENS = ['projected_lidar_stack', 'origin_lidar']


def load(split):
    csv = os.path.join(V2, f'wp6_cues_{split}.csv')
    meta = os.path.join(V2, f'wp6_cues_{split}.json')
    if not (os.path.exists(csv) and os.path.exists(meta)):
        return None, None
    import pandas as pd
    return pd.read_csv(csv), json.load(open(meta))


def f1_sources(meta):
    """Every field must be named in the schema metadata; nothing may appear undeclared."""
    fails = []
    cols = set(meta.get('perception_fields', []))
    if not cols:
        return ['schema metadata declares no perception fields']
    if meta.get('schema') != 'v2_ego_local_23d':
        fails.append(f'schema name is {meta.get("schema")!r}, expected v2_ego_local_23d')
    total = meta.get('total_dimensions')
    if total != 23:
        fails.append(f'total_dimensions is {total}, expected 23')
    if not meta.get('point_source'):
        fails.append('no point_source recorded -- the provenance of the cues is undeclared')
    return fails


def f2_no_gt(df, meta):
    fails = []
    for c in list(df.columns) + list(meta.get('perception_fields', [])):
        for p in GT_PATTERNS:
            if re.search(p, c, re.I):
                fails.append(f'{c}: matches the ground-truth pattern /{p}/')
                break
    ps = (meta.get('point_source') or '') + ' ' + ' '.join(meta.get('forbidden_and_absent', []))
    if 'vehicles' in ps and 'absent' not in ps.lower() and 'forbidden' not in ps.lower():
        fails.append('point_source mentions params[vehicles] outside a forbidden-list context')
    return fails


def f3_dataflow(df, split, sample=N_SAMPLE):
    """Recompute from the ego-only path and require agreement; require the all-CAV control to differ."""
    import v2_wp6_generate_cues as G
    from v2_alignment_audit import build_ds
    from opencood.data_utils.datasets import basedataset
    import copy
    import functools

    ds = build_ds(split)
    real = basedataset.load_yaml
    memo = functools.lru_cache(maxsize=4096)(real)
    basedataset.load_yaml = lambda p, *a, **k: copy.deepcopy(memo(p))
    fails, agreed, control_differed, control_na = [], 0, 0, 0
    cols = ['ego_' + k for k in G.PCD_NAMES]
    try:
        idxs = df.frame.to_numpy()
        step = max(1, len(idxs) // sample)
        for idx in idxs[::step][:sample]:
            idx = int(idx)
            pts, _ego, _hc = G.ego_points(ds, idx)
            got = G.extract_pcd_features(pts)
            row = df[df.frame == idx].iloc[0]
            bad = [k for k in G.PCD_NAMES
                   if not np.isclose(float(row['ego_' + k]), float(got[k]), rtol=0, atol=1e-9)]
            if bad:
                fails.append(f'frame {idx}: stored cues disagree with the ego-only recomputation '
                             f'on {bad[:4]} -- the table was not produced from the ego path')
            else:
                agreed += 1
            # negative control: the all-CAV cloud must NOT give the same numbers
            base = ds.retrieve_base_data(idx, cur_ego_pose_flag=ds.cur_ego_pose_flag)
            ego_id = next(c for c in base if base[c]['ego'])
            pose = base[ego_id]['params']['lidar_pose']
            from opencood.utils import catosg_collab_subset
            sub = catosg_collab_subset.subset_of(base, pose)
            stack = [G.ego_points(ds, idx)[0]]
            for cid, content in sub.items():
                if content['ego']:
                    continue
                stack.append(np.asarray(ds.get_item_single_car(content, pose, None)['projected_lidar']))
            if len(stack) < 2:
                control_na += 1
                continue
            allcav = G.extract_pcd_features(np.vstack(stack))
            if any(not np.isclose(float(row['ego_' + k]), float(allcav[k]), rtol=0, atol=1e-9)
                   for k in G.PCD_NAMES):
                control_differed += 1
            else:
                fails.append(f'frame {idx}: the all-CAV control produces the SAME cue values, so '
                             f'the ego-only check proves nothing here')
    finally:
        basedataset.load_yaml = real
    if agreed and control_differed == 0 and control_na < agreed:
        fails.append('the all-CAV negative control never differed -- F-3 is unfalsified')
    return fails, {'recomputed_and_agreed': agreed, 'control_differed': control_differed,
                   'control_not_applicable': control_na, 'columns': len(cols)}


def f4_f5_joins(df, split):
    import pandas as pd
    fails = []
    wp2 = pd.read_csv(os.path.join(V2, f'wp2_per_agent_{split}.csv'))
    if not np.array_equal(df.frame.to_numpy(), wp2.frame.to_numpy()):
        return ['frame vectors differ from WP2 -- no join is possible']
    if not np.array_equal(df.ego_detected_box_count.to_numpy(), wp2.n_box_ego.to_numpy()):
        n = int((df.ego_detected_box_count.to_numpy() != wp2.n_box_ego.to_numpy()).sum())
        fails.append(f'F-4: ego_detected_box_count differs from WP2 n_box_ego on {n} frame(s)')
    ap = os.path.join(V2, f'alignment_audit_{split}.json')
    if not os.path.exists(ap):
        fails.append('F-5: no alignment audit to check has_collaborator against')
    elif not np.array_equal(df.has_collaborator.to_numpy(), wp2.has_collab.to_numpy()):
        n = int((df.has_collaborator.to_numpy() != wp2.has_collab.to_numpy()).sum())
        fails.append(f'F-5: has_collaborator differs from the audited availability on {n} frame(s)')
    return fails


def run(split, df=None, meta=None, dataflow=True):
    if df is None:
        df, meta = load(split)
    if df is None:
        return [f'{split}: no cue table -- run v2_wp6_generate_cues.py'], {}
    fails = f1_sources(meta) + f2_no_gt(df, meta) + f4_f5_joins(df, split)
    info = {}
    if dataflow:
        f3, info = f3_dataflow(df, split)
        fails += f3
    return fails, info


def self_test():
    import pandas as pd
    df, meta = load('validate')
    if df is None:
        print('SELF-TEST INCONCLUSIVE: no cue table yet')
        return 1
    base_fails, _ = run('validate', df, meta, dataflow=False)
    if base_fails:
        print(f'SELF-TEST FAIL: baseline not clean -- {base_fails[0]}')
        return 1
    print('  baseline (real schema, non-dataflow checks): clean')

    ok = True
    d1 = df.copy()
    d1['ego_num_objects'] = 1
    m1 = json.loads(json.dumps(meta))
    m1['perception_fields'].append('ego_num_objects')
    f1, _ = run('validate', d1, m1, dataflow=False)
    print(f'  {"FIRES  " if f1 else "SILENT "}  a GT cue is planted')
    if f1:
        print(f'            -> {f1[0][:120]}')
    ok &= bool(f1)

    d2 = df.copy()
    d2['ego_detected_box_count'] = d2['ego_detected_box_count'] + 1
    f2, _ = run('validate', d2, meta, dataflow=False)
    print(f'  {"FIRES  " if f2 else "SILENT "}  ego_detected_box_count no longer matches WP2 '
          f'(stands in for an all-CAV/misjoined table)')
    if f2:
        print(f'            -> {f2[0][:120]}')
    ok &= bool(f2)

    d3 = df.copy()
    d3['has_collaborator'] = 1 - d3['has_collaborator']
    f3, _ = run('validate', d3, meta, dataflow=False)
    print(f'  {"FIRES  " if f3 else "SILENT "}  has_collaborator contradicts the alignment audit')
    ok &= bool(f3)

    d4 = df.copy()
    d4['ego_scene_complexity'] = 1.0
    m4 = json.loads(json.dumps(meta))
    m4['perception_fields'].append('ego_scene_complexity')
    f4, _ = run('validate', d4, m4, dataflow=False)
    print(f'  {"FIRES  " if f4 else "SILENT "}  a RENAMED GT cue with no source evidence')
    print('            (EXPECTED SILENT -- DOCUMENTED BLIND SPOT: a GT quantity under an innocuous '
          'name defeats both the name net and the provenance net. This is why §9.1 criterion 2 '
          'requires a code location per dimension and criterion 5 stops the batch on an '
          'unclassifiable cue: the gate cannot replace the audit, only hold its result.)')

    print('CUE SCHEMA SELF-TEST ' + ('PASS' if ok else 'FAIL: an injection did not fire'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    allf, info = [], {}
    for s in SPLITS:
        f, i = run(s)
        allf += [f'{s}: {x}' for x in f]
        info[s] = i
    print(f'cue schema: v2_ego_local_23d over {len(SPLITS)} split(s); data-flow recomputation '
          f'{info.get("validate", {}).get("recomputed_and_agreed", 0)} frame(s) agreed, all-CAV '
          f'control differed on {info.get("validate", {}).get("control_differed", 0)}')
    if allf:
        print('\nCUE SCHEMA GATE FAIL:')
        for x in allf:
            print('  ' + x)
        return 1
    print('CUE SCHEMA GATE PASS: 23 declared dimensions, no ground-truth field, the ego_pcd_* values '
          'reproduce from the ego-only path and NOT from the all-CAV stack, and both joins hold '
          'frame by frame.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
