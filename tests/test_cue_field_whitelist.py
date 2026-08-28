#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R21 C-5 — the cue-vector field ban, as a gate rather than a documentation clause.

Forbidden as a selector input, by source rather than by name (a rename must not defeat it):

    ground truth . task metric . oracle action . delivery outcome . actual erasure mask . future info

**This gate is expected to FAIL until the §9 amendment lands.** `ego_num_objects` is currently in the
23-dimension cue set and is a ground-truth object count -- `len(ego['object_ids'])`, built by
`generate_object_center()` from `cav_content['params']['vehicles']`. That is what work package 6
found, and the gate reporting it is the gate working. It is deliberately **not registered in
`tools/verify_results.py`** yet: committing a knowingly-red gate is the thing that teaches people to
ignore the suite. It goes into the suite in the same batch as the amendment that removes the field.

Two layers, because a name-based check alone is defeated by a rename:

  1. **name patterns** over whatever cue columns are live, and
  2. **the WP6 audit's per-dimension classification**, which was established by reading the
     provenance chain to its source and cites a code location for each row.

  python tests/test_cue_field_whitelist.py
  python tests/test_cue_field_whitelist.py --self-test
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, 'results', 'v2', 'wp6_cue_audit.json')

# Source-based, and matched against the column name only as a second net.
BANNED_PATTERNS = [
    (r'(^|_)gt(_|$)|ground_?truth|num_objects|object_ids', 'ground_truth'),
    (r'(^|_)(f1|ap|precision|recall|tp|fp|fn)(_|$)', 'task_metric'),
    (r'oracle|best_(method|level|f1|payload)', 'oracle_action'),
    (r'eff_f1|delivered|erasure|realised|realized', 'delivery_outcome'),
    (r'future|next_frame|lookahead', 'future_information'),
]


def active_schema(split='validate'):
    """The cue set actually in force, not the retired one the audit describes."""
    p = os.path.join(ROOT, 'results', 'v2', f'wp6_cues_{split}.json')
    if not os.path.exists(p):
        return None
    m = json.load(open(p))
    return {'name': m.get('schema'),
            'fields': list(m.get('perception_fields', [])) + list(m.get('channel_fields', []))}


def check(schema=None, audit=None, extra_names=None):
    """Fail if any BANNED source reaches the ACTIVE cue schema.

    Two nets, and note which set each is applied to:

      * the WP6 audit says which *v1* dimensions were forbidden. A forbidden dimension is a failure
        only when it is still IN the active schema -- the audit is a record of what was found, not a
        standing accusation against a field that has since been removed.
      * the name patterns are applied to the active schema's own field list, so a newly added field
        is caught even though the audit never classified it.
    """
    fails = []
    if schema is None:
        schema = active_schema()
    if schema is None:
        return ['no active cue schema -- run projects/ca_tosg/evaluation/v2_wp6_generate_cues.py']
    if audit is None:
        if not os.path.exists(AUDIT):
            return ['no WP6 cue audit -- run projects/ca_tosg/evaluation/v2_wp6_cue_audit.py']
        audit = json.load(open(AUDIT))

    live = set(schema['fields'])
    for c in audit['cues']:
        if c['classification'] == 'forbidden' and c['name'] in live:
            fails.append(f'{c["name"]}: classified FORBIDDEN by the WP6 audit '
                         f'[{c.get("forbidden_source")}] and STILL IN the active schema '
                         f'({c["code_location"][0]})')

    for n in list(schema['fields']) + list(extra_names or []):
        for pat, src in BANNED_PATTERNS:
            if re.search(pat, n, re.I):
                fails.append(f'{n}: name matches the {src} ban pattern /{pat}/')
                break
    return fails


def self_test():
    schema = active_schema()
    audit = json.load(open(AUDIT)) if os.path.exists(AUDIT) else None
    if schema is None or audit is None:
        print('SELF-TEST INCONCLUSIVE: no active schema or no audit')
        return 1
    if check(schema, audit):
        print('SELF-TEST FAIL: the live schema must be clean or the injections prove nothing')
        return 1
    print(f'  baseline ({schema["name"]}, {len(schema["fields"])} fields): clean')

    def with_field(name):
        s2 = json.loads(json.dumps(schema))
        s2['fields'].append(name)
        return s2

    cases = [
        ('the retired GT field is put back in the schema', with_field('ego_num_objects'), None),
        ('an outcome column reaches the schema', with_field('compressed_f1'), None),
        ('an oracle label reaches the schema', with_field('oracle_3way'), None),
        ('a delivery outcome reaches the schema', with_field('eff_f1_L'), None),
    ]
    ok = True
    for name, sc, extra in cases:
        f = check(sc, audit, extra)
        print(f'  {"FIRES  " if f else "SILENT "}  {name}')
        if f:
            print(f'            -> {f[0][:130]}')
        ok &= bool(f)

    f = check(with_field('ego_scene_complexity'), audit)
    print(f'  {"FIRES  " if f else "SILENT "}  a RENAMED GT cue with no source evidence')
    print('            (EXPECTED SILENT -- DOCUMENTED BLIND SPOT: a GT quantity under an innocuous '
          'name defeats both the name net and the provenance net. This is why §9.1 criterion 2 '
          'requires a code location per dimension and criterion 5 stops the batch on an '
          'unclassifiable cue: this gate holds the audit result, it cannot replace the audit.)')

    print('CUE WHITELIST SELF-TEST ' + ('PASS' if ok else 'FAIL: an injection did not fire'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    fails = check()
    sc = active_schema()
    print(f'cue field whitelist: source-based ban over the ACTIVE schema '
          f'{sc["name"] if sc else "?"} ({len(sc["fields"]) if sc else 0} fields)')
    if fails:
        print('\nCUE WHITELIST GATE FAIL:')
        for f in fails:
            print('  ' + f)
        return 1
    print('CUE WHITELIST GATE PASS: no ground truth, task metric, oracle label, delivery outcome '
          'or future information in the cue vector.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
