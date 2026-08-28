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


def cue_names_from_audit(audit):
    return [c['name'] for c in audit['cues']]


def check(audit=None, extra_names=None):
    fails = []
    if audit is None:
        if not os.path.exists(AUDIT):
            return ['no WP6 cue audit -- run projects/ca_tosg/evaluation/v2_wp6_cue_audit.py']
        audit = json.load(open(AUDIT))

    for c in audit['cues']:
        if c['classification'] == 'forbidden':
            fails.append(f'{c["name"]}: classified FORBIDDEN by the WP6 audit '
                         f'[{c.get("forbidden_source")}] -- {c["sees"]} '
                         f'({c["code_location"][0]})')

    names = cue_names_from_audit(audit) + list(extra_names or [])
    for n in names:
        for pat, src in BANNED_PATTERNS:
            if re.search(pat, n, re.I):
                msg = f'{n}: name matches the {src} ban pattern /{pat}/'
                if not any(msg.startswith(f.split(':')[0] + ':') for f in fails):
                    fails.append(msg)
                break
    return fails


def self_test():
    audit = json.load(open(AUDIT)) if os.path.exists(AUDIT) else None
    if audit is None:
        print('SELF-TEST INCONCLUSIVE: no audit')
        return 1
    clean = json.loads(json.dumps(audit))
    clean['cues'] = [c for c in clean['cues'] if c['classification'] != 'forbidden'
                     and not any(re.search(p, c['name'], re.I) for p, _ in BANNED_PATTERNS)]
    if check(clean):
        print('SELF-TEST FAIL: the cleaned baseline must be clean')
        return 1
    print(f'  baseline (audit with the forbidden row removed, {len(clean["cues"])} cues): clean')

    cases = []
    a1 = json.loads(json.dumps(clean))
    a1['cues'].append(dict(name='ego_num_objects', classification='forbidden',
                           forbidden_source='ground_truth', sees='GT', code_location=['x.py:1']))
    cases.append(('a GT-derived cue is added back', a1, None))

    a2 = json.loads(json.dumps(clean))
    a2['cues'].append(dict(name='scene_complexity_index', classification='independent',
                           sees='?', code_location=['x.py:1']))
    cases.append(('a renamed GT cue slips past the name net but the audit marks it independent',
                  a2, None))

    a3 = json.loads(json.dumps(clean))
    cases.append(('an outcome column reaches the feature list under its own name',
                  a3, ['compressed_f1']))

    a4 = json.loads(json.dumps(clean))
    cases.append(('an oracle label reaches the feature list', a4, ['oracle_3way']))

    ok = True
    for name, a, extra in cases:
        f = check(a, extra)
        expected_fire = 'renamed' not in name
        fired = bool(f)
        verdict = 'FIRES  ' if fired else 'SILENT '
        print(f'  {verdict}  {name}')
        if fired:
            print(f'            -> {f[0][:130]}')
        if expected_fire:
            ok &= fired
        else:
            # documented limitation, asserted so it cannot be mistaken for coverage
            print('            (EXPECTED SILENT: a rename with no source evidence is invisible to '
                  'both nets -- this is why criterion 2 requires a code location per dimension, '
                  'and why an unclassifiable cue must STOP the batch rather than default in)')
    print('CUE WHITELIST SELF-TEST ' + ('PASS' if ok else 'FAIL: an injection did not fire'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    fails = check()
    print('cue field whitelist: source-based ban over the WP6-audited cue set')
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
