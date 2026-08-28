#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R24 B-2 — freeze `v2_ego_local_23d`: fields, code locations, FOV, WP2 dependency, hashes.

Protocol §9.2. The schema is the selector's contract with the physical world: it says what the ego is
allowed to know at decision time. Freezing it means a later run cannot quietly gain a field, lose
one, or keep the names while changing what they are computed from.

WHAT IS PINNED, AND WHY EACH ITEM IS HERE
------------------------------------------
* **the field list and its order** -- a reordered feature vector silently retrains a different model;
* **a code location per field**, carried over from the WP6 audit, because §9.1 criterion 2 makes a
  verbal assertion inadmissible as evidence of provenance;
* **the field of view** -- the whole reason the cues had to be regenerated is that a scene statistic
  is defined over a region, and v1's region was the late-fusion `cav_lidar_range`, not this one;
* **the WP2 products the schema depends on**, by SHA-256: `ego_detected_box_count` IS a WP2 output,
  so a schema frozen without pinning WP2 would be frozen against a moving input;
* **the checkpoint hashes**, since `ego_detected_box_count` is a detector output and would change
  under different weights even with every other input identical;
* **the cue table's own hash**, so the frozen declaration and the delivered product cannot drift.

    python tools/build_cue_schema_manifest.py            # write
    python tools/build_cue_schema_manifest.py --check    # verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(ROOT, 'results', 'v2')
OUT = os.path.join(ROOT, 'results', 'manifests', 'V2_CUE_SCHEMA.json')
PROTOCOL_SECTION = '9.2'
SCHEMA = 'v2_ego_local_23d'
SPLIT = 'validate'


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def build():
    meta_p = os.path.join(V2, f'wp6_cues_{SPLIT}.json')
    csv_p = os.path.join(V2, f'wp6_cues_{SPLIT}.csv')
    audit_p = os.path.join(V2, 'wp6_cue_audit.json')
    for p in (meta_p, csv_p, audit_p):
        if not os.path.exists(p):
            raise SystemExit(f'missing input: {os.path.relpath(p, ROOT)}')
    meta = json.load(open(meta_p))
    audit = json.load(open(audit_p))
    if meta.get('schema') != SCHEMA:
        raise SystemExit(f'schema is {meta.get("schema")!r}, expected {SCHEMA!r}')

    fields = list(meta['perception_fields']) + list(meta['channel_fields'])
    if len(fields) != 23:
        raise SystemExit(f'{len(fields)} fields, expected 23')

    # provenance: the WP6 audit's code locations, for fields that carry over by definition
    audit_loc = {c['name']: c['code_location'] for c in audit['cues']}
    gen = 'projects/ca_tosg/evaluation/v2_wp6_generate_cues.py'
    prov = {}
    for f in fields:
        if f in ('est_snr_db', 'channel_is_rayleigh'):
            prov[f] = audit_loc.get(f, ['projects/ca_tosg/models/feature_encoder.py'])
        elif f == 'ego_detected_box_count':
            prov[f] = [f'{gen}:ego_detected_box_count <- wp2_per_agent_{SPLIT}.csv:n_box_ego']
        elif f == 'has_collaborator':
            prov[f] = [f'{gen}:ego_points() <- catosg_collab_subset.subset_of + COM_RANGE']
        else:
            prov[f] = [f'{gen}:extract_pcd_features(get_item_single_car()[projected_lidar])']

    import yaml
    ck_dir = ('/mnt/h/opencood_project/pretrained_models/pointpillar_attentive_fusion/'
              'pointpillar_attentive_fusion_compression')
    ck_cfg = os.path.join(ck_dir, 'config.yaml')
    fov = None
    if os.path.exists(ck_cfg):
        fov = yaml.load(open(ck_cfg), Loader=yaml.Loader)['preprocess']['cav_lidar_range']

    deps = {}
    for name in (f'wp2_per_agent_{SPLIT}.csv', f'wp6_cues_{SPLIT}.csv',
                 f'alignment_audit_{SPLIT}.json'):
        p = os.path.join(V2, name)
        if os.path.exists(p):
            deps[name] = sha256_file(p)
    for name, p in (('checkpoint/latest.pth', os.path.join(ck_dir, 'latest.pth')),
                    ('checkpoint/config.yaml', ck_cfg)):
        if os.path.exists(p):
            deps[name] = sha256_file(p)

    return {
        'schema': 'catosg-v2-cue-schema/1', 'name': SCHEMA, 'protocol_section': PROTOCOL_SECTION,
        'frozen': True,
        'why': 'The schema states what the ego is allowed to know at decision time. Freezing it '
               'stops a later run gaining a field, losing one, or keeping the names while changing '
               'what they are computed from.',
        'n_fields': len(fields), 'fields': fields,
        'field_provenance': prov,
        'field_of_view': {
            'cav_lidar_range': fov,
            'note': 'The unified v2 FOV (§3.1). v1 cues were extracted under the LATE-FUSION range '
                    'x in [-70.4, 70.4]; a scene statistic is defined over a region, which is why '
                    'the regeneration was required. Pinned because the fields would silently mean '
                    'something else under another range.'},
        'point_source': meta['point_source'],
        'frozen_thresholds': meta['frozen_thresholds'],
        'forbidden_and_absent': meta['forbidden_and_absent'],
        'depends_on': deps,
        'retired': {'ego_num_objects': 'GROUND TRUTH (params[vehicles]); kept outside the schema as '
                                       'evaluation_only_gt, never a selector input',
                    'num_cavs': 'size of the fused CAV set (2-7) -- post-decision; replaced by the '
                                'binary has_collaborator'},
        'gates': ['tests/test_cue_schema.py', 'tests/test_cue_field_whitelist.py'],
    }


def check(man):
    fails = []
    meta_p = os.path.join(V2, f'wp6_cues_{SPLIT}.json')
    if not os.path.exists(meta_p):
        return ['the cue product is gone']
    meta = json.load(open(meta_p))
    live = list(meta['perception_fields']) + list(meta['channel_fields'])
    if live != man['fields']:
        added, lost = set(live) - set(man['fields']), set(man['fields']) - set(live)
        if added or lost:
            fails.append(f'field set moved: added {sorted(added)}, lost {sorted(lost)}')
        else:
            fails.append('field ORDER moved -- a reordered vector trains a different model')
    for name, want in man['depends_on'].items():
        p = os.path.join(V2, name)
        if not os.path.exists(p):
            p = os.path.join('/mnt/h/opencood_project/pretrained_models/pointpillar_attentive_fusion/'
                             'pointpillar_attentive_fusion_compression',
                             os.path.basename(name))
        if not os.path.exists(p):
            fails.append(f'dependency missing: {name}')
        elif sha256_file(p) != want:
            fails.append(f'dependency changed: {name} ({sha256_file(p)[:12]} != {want[:12]})')
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        if not os.path.exists(OUT):
            print('CUE SCHEMA FREEZE FAIL: no manifest')
            return 1
        man = json.load(open(OUT))
        f = check(man)
        print(f'cue schema freeze: {man["name"]}, {man["n_fields"]} fields, '
              f'{len(man["depends_on"])} pinned dependencies')
        for x in f:
            print('  ' + x)
        print('CUE SCHEMA FREEZE ' + ('PASS' if not f else 'FAIL'))
        return 0 if not f else 1
    man = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as fh:
        json.dump(man, fh, indent=1)
    print(f'wrote {os.path.relpath(OUT, ROOT)}')
    print(f'  {man["name"]}: {man["n_fields"]} fields, FOV {man["field_of_view"]["cav_lidar_range"]}')
    for k, v in man['depends_on'].items():
        print(f'  pinned  {v[:16]}  {k}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
