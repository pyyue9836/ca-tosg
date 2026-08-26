#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Hash every section of docs/unified_branch_protocol_v2.md into a manifest (V2-R1 item 3).

A protocol that can be edited silently is not a pre-specification. This walks the `## ` sections,
records a sha256 per section, and reads the lock table in section 16 so a section that is NOT LOCKED
is recorded as `PENDING` rather than as a satisfied hash.

`--check` fails when a LOCKED section's hash has moved, and when a section recorded as PENDING is
still PENDING at a moment the caller declares it must not be (that second half is deliberately not
automated: whether an open item is allowed to stay open is Josh's call, so the tool reports and the
human decides).

Not registered in `tools/verify_results.py`. `docs/STOP_WORK_v1_freeze.md` forbids adding gates while
the v1 manuscript is frozen, and this governs a v2 document; it becomes a gate when the v2 products
land and their gates are decided together.

    python tools/build_v2_protocol_manifest.py [--check]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTOCOL = os.path.join(ROOT, 'docs', 'unified_branch_protocol_v2.md')
STOPWORK = os.path.join(ROOT, 'docs', 'STOP_WORK_v1_freeze.md')
OUT = os.path.join(ROOT, 'results', 'manifests', 'V2_PROTOCOL_MANIFEST.json')
SCHEMA = 'catosg-v2-protocol-manifest/1'


def sections(text):
    """[(heading, body)] for every '## ' heading, body running to the next one."""
    parts = re.split(r'(?m)^(## .+)$', text)
    out = []
    for i in range(1, len(parts), 2):
        out.append((parts[i].strip(), parts[i + 1]))
    return out


def lock_table(text):
    """{section-number: 'LOCKED' | 'NOT LOCKED' | 'PARTIAL'} read from section 16's own table.

    The lock state is read from the document rather than passed in, so the manifest cannot claim a
    section is locked while the document says it is not.
    """
    m = re.search(r'(?ms)^## 16\. Lock status(.*)$', text)
    if not m:
        raise SystemExit('section 16 (Lock status) not found -- the manifest needs it')
    states = {}
    for line in m.group(1).splitlines():
        row = re.match(r'^\|\s*(\d+)\s+([^|]+?)\s*\|\s*([^|]+?)\s*\|', line)
        if not row:
            continue
        num, _name, state = row.group(1), row.group(2), row.group(3)
        s = state.replace('*', '').strip()
        if s.upper().startswith('NOT LOCKED'):
            states[num] = 'NOT LOCKED'
        elif 'except' in s.lower():
            states[num] = 'PARTIAL'
        elif s.upper().startswith('LOCKED'):
            states[num] = 'LOCKED'
        else:
            states[num] = s
    return states


def build():
    text = open(PROTOCOL, encoding='utf-8').read()
    locks = lock_table(text)
    entries = []
    for heading, body in sections(text):
        num = re.match(r'## (\d+)', heading)
        key = num.group(1) if num else heading[3:].strip()
        state = locks.get(key, 'UNDECLARED')
        digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
        entries.append({
            'section': heading[3:].strip(),
            'number': key,
            'lock_state': state,
            'sha256': 'PENDING' if state == 'NOT LOCKED' else digest,
            'sha256_observed': digest,
            'bytes': len(body.encode('utf-8')),
        })
    man = {
        'schema': SCHEMA,
        'protocol': os.path.relpath(PROTOCOL, ROOT),
        'protocol_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'stop_work_order': os.path.relpath(STOPWORK, ROOT),
        'stop_work_sha256': (hashlib.sha256(open(STOPWORK, 'rb').read()).hexdigest()
                             if os.path.exists(STOPWORK) else None),
        'sections': entries,
        'locked': sum(1 for e in entries if e['lock_state'] == 'LOCKED'),
        'partial': sum(1 for e in entries if e['lock_state'] == 'PARTIAL'),
        'not_locked': sum(1 for e in entries if e['lock_state'] == 'NOT LOCKED'),
    }
    return man


def main() -> int:
    man = build()
    if '--check' in sys.argv:
        if not os.path.exists(OUT):
            print(f'V2 PROTOCOL MANIFEST CHECK FAIL: {os.path.relpath(OUT, ROOT)} is missing')
            return 1
        old = json.load(open(OUT))
        oldmap = {e['number']: e for e in old['sections']}
        moved = []
        for e in man['sections']:
            o = oldmap.get(e['number'])
            if o is None:
                moved.append(f"{e['number']}: new section")
            elif o['lock_state'] == 'LOCKED' and o['sha256'] != e['sha256_observed']:
                moved.append(f"{e['number']} ({e['section'][:40]}): LOCKED section changed")
        if moved:
            print('V2 PROTOCOL MANIFEST CHECK FAIL:')
            for m in moved:
                print('  ' + m)
            print('A locked section may only change through a written amendment.')
            return 1
        print(f'V2 PROTOCOL MANIFEST CHECK PASS: {man["locked"]} locked, {man["partial"]} partial, '
              f'{man["not_locked"]} not locked; no locked section has moved.')
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(man, f, indent=1)
    print(f'wrote {os.path.relpath(OUT, ROOT)}')
    print(f'  protocol sha256 {man["protocol_sha256"]}')
    for e in man['sections']:
        print(f'  {e["number"]:>3}  {e["lock_state"]:<10}  {e["sha256"][:16]}  {e["section"][:52]}')
    print(f'  {man["locked"]} LOCKED | {man["partial"]} PARTIAL | {man["not_locked"]} NOT LOCKED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
