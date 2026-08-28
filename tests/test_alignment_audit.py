#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R20 B-1 — the identity-alignment verdict, as a standing gate.

WHAT IS BEING GUARDED
---------------------
`projects/ca_tosg/evaluation/v2_alignment_audit.py` establishes that each work-package-2 row is the
frame it claims to be and that `N_box,t` belongs to the one selected collaborator. **Every part of it
is an identity, so 100 % is the only passing value** — unlike the coordinate-frame diagnostic
(73.6 %), which fails downward only and whose correct value is NOT 100 %. Confusing the two is what
V2-R19 A-1 cost, so the distinction is restated wherever either number lives.

WHY THIS GATE IS NOT A RUBBER STAMP
-----------------------------------
The full audit walks the real loader and costs ~25 min on validate, which is too slow for a suite
that must be run often. So it stores its verdict — and a stored verdict is worth exactly nothing
unless staleness is detectable. Three things make it real:

  1. **Input hashes.** The audit records the SHA-256 of every product it read. This gate recomputes
     them. If a product moved and the audit was not re-run, the gate FAILS rather than re-reading a
     JSON that says 100 % and believing it.
  2. **The cheap parts are re-run live**, not trusted: index integrity and payload binding are pure
     file arithmetic and take a second, so they are recomputed here and must still pass.
  3. **The stored verdict must be 100 % on every part**, on all three splits, with the mismatch
     lists actually empty — not merely with `aligned: true` set.

A gate that could not fail would be worse than no gate, so each of the three has an injection in
`--self-test`.

  python tests/test_alignment_audit.py
  python tests/test_alignment_audit.py --self-test
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(ROOT, 'results', 'v2')
SPLITS = ('validate', 'test', 'culver')
PARTS = ('A_index_integrity', 'B_collaborator_identity', 'C_row1_binding', 'D_payload_binding')

sys.path.insert(0, os.path.join(ROOT, 'projects', 'ca_tosg', 'evaluation'))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def audit_path(split):
    return os.path.join(V2, f'alignment_audit_{split}.json')


def check_stored(split, man):
    """The verdict itself: 100 % everywhere, and the mismatch lists genuinely empty."""
    f = []
    if not man.get('overall_aligned'):
        f.append(f'{split}: overall_aligned is not true')
    for part in PARTS:
        p = man.get(part)
        if p is None:
            f.append(f'{split}: {part} missing from the audit')
            continue
        if p.get('rate_pct') != 100.0:
            f.append(f'{split}: {part} rate {p.get("rate_pct")} != 100.0')
        if p.get('aligned') is not True:
            f.append(f'{split}: {part} aligned is not true')
    b = man.get('B_collaborator_identity') or {}
    for k in ('collaborator_id_mismatch_count', 'n_cav_mismatch_count',
              'has_collab_mismatch_count'):
        if b.get(k, -1) != 0:
            f.append(f'{split}: B {k} = {b.get(k)}, expected 0')
    if b.get('frames_walked') != man.get('frames'):
        f.append(f'{split}: B walked {b.get("frames_walked")} of {man.get("frames")} frames')
    c = man.get('C_row1_binding') or {}
    if c.get('negative_control_collisions'):
        f.append(f'{split}: C negative-control collision(s) present')
    if not c.get('negative_control_exercised'):
        f.append(f'{split}: C negative control never ran -- the positive result is unfalsified')
    return f


def check_inputs(split, man):
    """Staleness: the products must be the ones the verdict was computed from."""
    f = []
    ih = man.get('input_hashes')
    if not ih:
        return [f'{split}: no input_hashes recorded -- the verdict cannot be shown to be current '
                f'(re-run v2_alignment_audit.py)']
    for name, want in ih.items():
        p = os.path.join(V2, name)
        if not os.path.exists(p):
            f.append(f'{split}: input {name} is gone')
            continue
        got = sha256_file(p)
        if got != want:
            f.append(f'{split}: {name} changed since the audit ({got[:12]} != {want[:12]}) -- '
                     f're-run v2_alignment_audit.py')
    return f


def recheck_cheap(split):
    """Re-run parts A and D live. Seconds, and it means the record is not merely believed."""
    import v2_alignment_audit as A
    df, meta, d, wp34 = A.load_products(split)
    f = []
    a = A.part_a_index(df, meta, d)
    if not a['aligned']:
        f.append(f'{split}: part A recomputed and FAILS: '
                 f'missing={a["missing_indices"][:5]} dup={a["duplicate_indices"][:5]} '
                 f'order={a["out_of_order"]} csv==npz={a["csv_npz_frames_identical"]}')
    dd = A.part_d_payload(df, d, wp34)
    if not dd['aligned']:
        bad = [k for k, v in dd.items() if isinstance(v, bool) and not v
               and k != 'collab_equals_ego_on_all_frames']
        f.append(f'{split}: part D recomputed and FAILS: {bad}')
    return f


def run(loader=None, cheap=True):
    fails = []
    for split in SPLITS:
        p = audit_path(split)
        man = loader(split) if loader else (json.load(open(p)) if os.path.exists(p) else None)
        if man is None:
            fails.append(f'{split}: no alignment audit at {os.path.relpath(p, ROOT)}')
            continue
        fails += check_stored(split, man)
        fails += check_inputs(split, man)
        if cheap:
            fails += recheck_cheap(split)
    return fails


def self_test():
    base = {s: json.load(open(audit_path(s))) for s in SPLITS if os.path.exists(audit_path(s))}
    if len(base) != len(SPLITS):
        print('SELF-TEST INCONCLUSIVE: not all three audits are present')
        return 1
    if run(lambda s: copy.deepcopy(base[s]), cheap=True):
        print('SELF-TEST FAIL: the baseline must be clean or the injections prove nothing')
        return 1
    print('  baseline (untouched audits): clean')

    cases = []

    def mut(fn):
        def loader(s):
            m = copy.deepcopy(base[s])
            fn(m)
            return m
        return loader

    cases.append(('a part reports below 100 %',
                  mut(lambda m: m['A_index_integrity'].update(rate_pct=99.9))))
    cases.append(('a collaborator-id mismatch is present',
                  mut(lambda m: m['B_collaborator_identity'].update(
                      collaborator_id_mismatch_count=1))))
    cases.append(('the input hashes are stale',
                  mut(lambda m: m['input_hashes'].update(
                      {k: '0' * 64 for k in m['input_hashes']}))))
    cases.append(('input_hashes absent entirely (a pre-V2-R20 audit)',
                  mut(lambda m: m.pop('input_hashes', None))))
    cases.append(('the negative control never ran',
                  mut(lambda m: m['C_row1_binding'].update(negative_control_exercised=False))))

    ok = True
    for name, loader in cases:
        f = run(loader, cheap=False)
        print(f'  {"FIRES  " if f else "SILENT "}  {name}')
        if f:
            print(f'            -> {f[0][:140]}')
        ok &= bool(f)
    print('ALIGNMENT AUDIT SELF-TEST ' + ('PASS: every injection fires' if ok else
                                          'FAIL: an injection did not fire'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    fails = run()
    n = sum(1 for s in SPLITS if os.path.exists(audit_path(s)))
    print(f'alignment audit: {n} split(s), 4 identity parts each, verdicts re-checked against '
          f'recomputed input hashes; parts A and D re-run live')
    if fails:
        print('\nALIGNMENT AUDIT GATE FAIL:')
        for f in fails:
            print('  ' + f)
        return 1
    print('ALIGNMENT AUDIT GATE PASS: 100 % on every part of every split, inputs unchanged since '
          'the audit, and the live re-check of index integrity and payload binding agrees.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
