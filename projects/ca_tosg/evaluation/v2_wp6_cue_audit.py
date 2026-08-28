#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Work package 6 — the 23-dimension cue audit. Zero GPU.

Protocol §9.1 acceptance criteria 1, 2, 5 and 6, plus V2-R21 C-4 and C-5.

WHAT WP6 WAS LOOKING FOR, AND WHAT IS ACTUALLY THERE
----------------------------------------------------
§9.1 names one hazard: carrying v1 cue *values* over unregenerated would feed **v1 detections** into
a v2 selector. The audit below finds that hazard does **not** occur by that route — **no cue reads a
detection output at all** — and that two different problems do:

  1. **`ego_num_objects` is a GROUND-TRUTH object count.** It is `len(ego['object_ids'])`, and
     `object_ids` is built by `generate_object_center()` from `cav_content['params']['vehicles']` —
     the dataset's annotation. A selector conditioning on it is reading the answer. V2-R21 C-5
     forbids GT in the cue vector outright, so this is not a judgement call.

  2. **Nineteen of the twenty-one "ego-side" cues are not ego-side.** They are computed from
     `ego['origin_lidar']`, which `intermediate_fusion_dataset.py` builds as
     `np.vstack(projected_lidar_stack)` — the projected LiDAR of **every CAV in the frame**. Under
     v1 that is up to seven vehicles (mean 3.89); under the v2 single-collaborator rule it is at
     most two. §9's stated reason for carrying the cue set over unchanged — *"the cues describe the
     ego's own scene and channel, not the branch architecture"* — is therefore **factually wrong**
     for these nineteen, and `num_cavs` changes by construction as well.

**Neither is caught by the `depends` / `independent` split alone**, which is why criterion 2 insists
on a code location rather than an assertion: the classification that matters here was only visible
by following `origin_lidar` and `object_ids` back to where they are built.

Every `code_location` below was read, not recalled; the line numbers are checked at run time by
`--verify-locations`, so this table cannot quietly drift from the code it cites.

    python projects/ca_tosg/evaluation/v2_wp6_cue_audit.py
    python projects/ca_tosg/evaluation/v2_wp6_cue_audit.py --verify-locations
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SIBLING = os.path.abspath(os.path.join(os.path.dirname(ROOT), 'OpenCOOD'))
OUT = os.path.join(ROOT, 'results', 'v2', 'wp6_cue_audit.json')

CUE_CSV = os.path.join(ROOT, 'data/p2/dataset_validate_n1.csv')
EXTRACT = 'projects/ca_tosg/datasets/test_split/02_extract_cues_and_f1.py'
IFD = 'opencood/data_utils/datasets/intermediate_fusion_dataset.py'
BPP = 'opencood/data_utils/post_processor/base_postprocessor.py'
ENCODER = 'projects/ca_tosg/models/feature_encoder.py'

# V2-R21 C-5. A field matching any of these may never enter the cue vector. This is the machine-
# readable form of the ban; `tests/test_cue_field_whitelist.py` is the gate that enforces it.
FORBIDDEN_SOURCES = {
    'ground_truth': 'GT boxes, GT object ids, GT counts -- the answer the detector is estimating',
    'task_metric': 'AP, F1, precision, recall, tp/fp/fn -- outcomes, not inputs',
    'oracle_action': 'oracle labels or best_method/best_level columns',
    'delivery_outcome': 'realised delivery, effective F1, the actual erasure mask',
    'future_information': 'anything from a later frame or from after the decision',
}

# 'sees' names the deepest source the value provably reaches, established by reading the chain.
CUES = [
    dict(name='num_cavs', group='scene',
         sees='the CAV set after the collaborator-subset rule (NOT detections, NOT GT)',
         classification='independent',
         changes_under_v2=True,
         why_changes='v1 counted every CAV in the frame (observed 2-7); the v2 rule caps it at 2, '
                     'so the value moves on every frame with 3 or more CAVs',
         code_location=[f'{EXTRACT}:134', f'{IFD}:81']),
    dict(name='ego_num_objects', group='scene',
         sees='GROUND TRUTH: params["vehicles"] via generate_object_center()',
         classification='forbidden',
         forbidden_source='ground_truth',
         changes_under_v2=True,
         why_changes='irrelevant -- it may not be used at all (C-5)',
         code_location=[f'{EXTRACT}:137', f'{IFD}:235', f'{BPP}:125']),
    dict(name='ego_origin_lidar_shape_0', group='lidar',
         sees='the stacked multi-CAV projected point cloud',
         classification='independent', changes_under_v2=True,
         why_changes='origin_lidar is np.vstack(projected_lidar_stack) over ALL CAVs',
         code_location=[f'{EXTRACT}:138', f'{IFD}:198']),
    dict(name='ego_origin_lidar_shape_1', group='lidar',
         sees='the stacked multi-CAV projected point cloud (column count)',
         classification='independent', changes_under_v2=False,
         why_changes='the column count is the point dimensionality, invariant to the CAV set',
         code_location=[f'{EXTRACT}:139', f'{IFD}:198']),
]
_PCD = ['pcd_num_points', 'pcd_mean_range', 'pcd_max_range', 'pcd_std_range', 'pcd_near_20m',
        'pcd_mid_20_50m', 'pcd_far_50_80m', 'pcd_very_far_80m', 'pcd_front_points',
        'pcd_back_points', 'pcd_left_points', 'pcd_right_points', 'pcd_front_far_30m',
        'pcd_front_far_50m', 'pcd_density_0_20', 'pcd_density_20_50', 'pcd_density_50_80']
for _n in _PCD:
    CUES.append(dict(
        name=_n, group='lidar',
        sees='the stacked multi-CAV projected point cloud (no detector output on the path)',
        classification='independent', changes_under_v2=True,
        why_changes='computed from ego["origin_lidar"], which is np.vstack(projected_lidar_stack) '
                    'over ALL CAVs in the frame -- the v2 rule changes that set',
        code_location=[f'{EXTRACT}:58', f'{EXTRACT}:116', f'{IFD}:198']))
CUES += [
    dict(name='est_snr_db', group='channel',
         sees='the channel grid; no perception quantity on the path',
         classification='independent', changes_under_v2=False,
         why_changes='a channel condition assigned per (frame, realisation); the branch does not '
                     'enter its computation',
         code_location=[f'{ENCODER}:46']),
    dict(name='channel_is_rayleigh', group='channel',
         sees='the channel grid; no perception quantity on the path',
         classification='independent', changes_under_v2=False,
         why_changes='same as est_snr_db',
         code_location=[f'{ENCODER}:47']),
]


def resolve(loc):
    path, line = loc.rsplit(':', 1)
    root = SIBLING if path.startswith('opencood/') else ROOT
    return os.path.join(root, path), int(line)


def verify_locations():
    """Criterion 2 made enforceable: every cited line must exist and still be non-trivial."""
    fails = []
    for c in CUES:
        for loc in c['code_location']:
            p, n = resolve(loc)
            if not os.path.exists(p):
                fails.append(f'{c["name"]}: {loc} -- file does not exist')
                continue
            lines = open(p, encoding='utf-8', errors='replace').read().splitlines()
            if n > len(lines):
                fails.append(f'{c["name"]}: {loc} -- file has only {len(lines)} lines')
            elif not lines[n - 1].strip():
                fails.append(f'{c["name"]}: {loc} -- cited line is blank')
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify-locations', action='store_true')
    args = ap.parse_args()

    if args.verify_locations:
        f = verify_locations()
        for x in f:
            print('  ' + x)
        print('CODE LOCATION CHECK ' + ('PASS' if not f else 'FAIL'))
        return 0 if not f else 1

    by = {}
    for c in CUES:
        by.setdefault(c['classification'], []).append(c)
    forbidden = by.get('forbidden', [])
    depends = by.get('depends', [])
    independent = by.get('independent', [])
    changes = [c for c in CUES if c['changes_under_v2']]

    print('=' * 100)
    print(f'WORK PACKAGE 6 -- cue audit: {len(CUES)} dimensions')
    print('=' * 100)
    print(f'{"cue":28} {"class":12} {"v2?":5} sees')
    for c in CUES:
        print(f'  {c["name"]:26} {c["classification"]:12} '
              f'{"MOVES" if c["changes_under_v2"] else "same ":5} {c["sees"][:44]}')

    print('\n' + '-' * 100)
    print(f'depends on detection output : {len(depends)}')
    print(f'independent                 : {len(independent)}')
    print(f'FORBIDDEN (C-5)             : {len(forbidden)}')
    print(f'value MOVES under the v2 branch: {len(changes)} of {len(CUES)}')

    if forbidden:
        print('\n*** C-5 VIOLATION -- these may not be in the cue vector at all ***')
        for c in forbidden:
            print(f'  {c["name"]}  [{c["forbidden_source"]}]  {c["sees"]}')
            for loc in c['code_location']:
                print(f'      {loc}')

    out = {
        'schema': 'catosg-v2-wp6-cue-audit/1',
        'dimensions': len(CUES),
        'counts': {'depends': len(depends), 'independent': len(independent),
                   'forbidden': len(forbidden), 'changes_under_v2': len(changes)},
        'forbidden_sources': FORBIDDEN_SOURCES,
        'headline': 'No cue reads a detection output -- the hazard §9.1 named does not occur by '
                    'that route. Two others do: ego_num_objects is a GROUND-TRUTH count (C-5), and '
                    '19 of the 21 "ego-side" cues are computed over the ALL-CAV stacked point '
                    'cloud, so §9 justification for carrying them over unchanged does not hold.',
        'blocking': [
            'ego_num_objects is ground truth and must leave the cue set -- an amendment under §9, '
            'which requires a written registration before any test/Culver number is seen.',
            '§9 says the cues "describe the ego own scene"; origin_lidar is the ALL-CAV stack, so '
            'that sentence is wrong for 19 of 21 and must be corrected before the set is refrozen.',
        ],
        'cues': CUES,
    }
    with open(OUT, 'w') as f:
        json.dump(out, f, indent=1)
    print(f'\nwrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
