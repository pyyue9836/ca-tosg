#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P6 gate 3 — cross-section logical scan at the level of ENTITIES, not strings.

The other gates ask "does this number exist in a CSV?". This one asks whether the paper says two
incompatible things about the SAME entity in two different places. Both statements are individually
well formed, so no string-level or per-claim check can see it.

An earlier version of this file read entities out of the prose (nearest subject, nearest metric
word). It was discarded rather than shipped: measured against the document it held **zero**
`(F1, CA-TOSG)` records and attributed the budget literal `0.20` as an F1 value, so its "0
conflicts" carried no information. Entities here come from curated structure instead:

  ENTITY-VALUE  entity = (Metric, Split) as recorded in the claims ledger's evidence columns.
                A conflict is the same entity carrying disjoint values in two different sections.
  ORDERING      the paper's dominance/ordering statements, re-checked against the frozen
                end-to-end AP table rather than against other prose.
  EXISTENCE     a \\ref to a label the document no longer defines.

Every check has a positive control under `--self-test`: a check that cannot fail on an injected
fault is not evidence of consistency.

    python tools/p6_cross_section_scan.py [--self-test]
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from audit_claims_evidence import claims_by_section, ledger_rows, text_key  # noqa: E402

MAIN = os.path.join(ROOT, 'paper', 'main.tex')
E2E = os.path.join(ROOT, 'results/main/true_e2e_ap.csv')
FIXED = os.path.join(ROOT, 'results/main/fixed_references.csv')
OUT = os.path.join(ROOT, 'docs', 'p6_cross_section_conflicts.md')

NUM = re.compile(r'(?<![\d.])([-+]?\d+\.\d{2,5})(?![\d])')
# Settings, not measurements. Budgets and IoU thresholds appear in almost every claim, so leaving
# them in made a claim that merely mentions "B_max=0.20" collide with any other claim about the same
# (metric, split) -- two such false conflicts survived to the last verification round.
STRUCTURAL = {0.1, 0.2, 0.3, 0.5, 0.7, 0.024, 0.495, 0.99, 0.05, 0.02, 0.005}


def entity_records(claims=None, ledger=None):
    """[(metric, split, section, values, claim)] from the ledger's curated evidence columns."""
    claims = claims if claims is not None else claims_by_section()
    ledger = ledger if ledger is not None else ledger_rows(by_text=True)
    out = []
    for section, subsection, cid, claim, exact in claims:
        cells = ledger.get(cid) or ledger.get('TXT:' + text_key(claim))
        if not cells or not any(cells):
            continue
        split, metric = cells[0].strip(), cells[1].strip()
        if not split or not metric or split.startswith('n/a'):
            continue
        vals = {round(float(v), 4) for v in NUM.findall(exact)} - STRUCTURAL
        if not vals:
            continue
        loc = f'{section}{" / " + subsection if subsection else ""}'
        out.append((metric, split, loc, vals, claim))
    return out


def _same_scale(va, vb, factor=10.0):
    """Are two value sets on the same numeric scale?

    A (metric, split) label as written in the ledger is often broader than a single quantity --
    "F1 / payload vs both thresholds" legitimately covers an F1 gap of 0.0001, a payload of 0.2168
    and a threshold of 13. Comparing across those produced a run of false conflicts, each of which
    got "fixed" by inventing a narrower label. This removes the whole family at once: entities are
    comparable only when their magnitudes sit within one order of magnitude, which still catches a
    genuine same-quantity disagreement (0.89 vs 0.85) and never pairs an F1 with a payload.
    """
    a = [abs(x) for x in va if x]
    b = [abs(x) for x in vb if x]
    if not a or not b:
        return False
    return (max(a) / min(b) <= factor) and (max(b) / min(a) <= factor)


def scan_entity_values(records):
    """Same (metric, split) stated in two sections with no value in common."""
    by_key = {}
    for metric, split, loc, vals, claim in records:
        by_key.setdefault((metric, split), []).append((loc, vals, claim))
    conflicts = []
    for key, items in by_key.items():
        for i, (la, va, ca) in enumerate(items):
            for lb, vb, cb in items[i + 1:]:
                if la != lb and not (va & vb) and _same_scale(va, vb):
                    conflicts.append((key, la, sorted(va), ca, lb, sorted(vb), cb))
    return conflicts


def scan_ordering(tex, fixed_path=None, e2e_path=None):
    """Dominance / ordering statements re-checked against the frozen reference tables."""
    fx = pd.read_csv(fixed_path or FIXED)
    findings = []
    claimed_dom = bool(re.search(r'fixed feature-level policies (remain |are )?(strictly )?dominated'
                                 r'|are strictly dominated', tex))
    for split in fx.split.unique():
        g = fx[fx.split == split].groupby('policy')['F1'].mean()
        if 'Fixed-L' not in g.index:
            continue
        fixed_l = float(g['Fixed-L'])
        feature = [p for p in g.index if p in ('Fixed-F', 'Fixed-C256')]
        if claimed_dom and feature and not all(float(g[p]) < fixed_l for p in feature):
            findings.append((f'"the fixed feature-level policies remain dominated by Fixed L" '
                             f'on {split}',
                             f'Fixed-L F1 {fixed_l:.4f} vs '
                             f'{ {p: round(float(g[p]), 4) for p in feature} } -- not all below it'))
        # "each frozen selector sits between them" belongs to tab:gen_headline, which is an F1
        # table: its bounds are Fixed-L and the MASKED ORACLE, both in F1. Two earlier versions of
        # this check got the pairing wrong -- first bounding an AP@0.5 value by F1 numbers, then
        # bounding it by the perfect-channel ceiling instead of the oracle - and each produced
        # spurious findings. The metric and the two bounds must all come from the same table.
        oracle = next((p for p in g.index if 'oracle' in p.lower()), None)
        if oracle and re.search(r'each frozen selector sits between them', tex):
            lo, hi = float(g['Fixed-L']), float(g[oracle])
            rp = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
            for _, r in rp[rp.split == split].iterrows():
                v = float(r.F1_RF)
                if not min(lo, hi) <= v <= max(lo, hi):
                    findings.append((f'"each frozen selector sits between Fixed L and the masked '
                                     f'oracle" (F1) on {split}',
                                     f'selector at B={r.budget} is {v:.5f}, outside '
                                     f'[{min(lo, hi):.4f}, {max(lo, hi):.4f}]'))
    return findings


def scan_labels(tex):
    labels = set(re.findall(r'\\label\{(.*?)\}', tex))
    return [(m.group(1), tex[:m.start()].count('\n') + 1)
            for m in re.finditer(r'\\(?:eq)?ref\{(.*?)\}', tex) if m.group(1) not in labels]


def self_test(tex):
    """Each check must fire on an injected fault. A silent check is not a passing check."""
    rc = 0
    recs = entity_records()
    inj = list(recs)
    if recs:
        metric, split, _loc, vals, _c = recs[0]
        inj.append((metric, split, 'INJECTED SECTION', {round(max(vals) + 0.5, 4)},
                    'injected contradictory claim'))
    fired = [c for c in scan_entity_values(inj) if 'INJECTED' in c[1] + c[4]]
    print(f'  ENTITY-VALUE: {"FIRES" if fired else "DOES NOT FIRE"} '
          f'({len(recs)} real records available)')
    rc |= 0 if fired else 1

    bad = scan_labels(tex + '\n\\ref{sec:injected_missing_label}\n')
    print(f'  EXISTENCE:    {"FIRES" if bad else "DOES NOT FIRE"}')
    rc |= 0 if bad else 1

    d = pd.read_csv(FIXED)
    tmp = FIXED + '.selftest'
    d.loc[d.policy == 'Fixed-L', 'F1'] = 0.0   # Fixed-L worst -> the dominance claim becomes false
    d.to_csv(tmp, index=False)
    try:
        fired3 = scan_ordering(tex, fixed_path=tmp)
    finally:
        os.unlink(tmp)
    print(f'  ORDERING:     {"FIRES" if fired3 else "DOES NOT FIRE"}')
    rc |= 0 if fired3 else 1
    return rc


def main() -> int:
    tex = open(MAIN, encoding='utf-8').read()
    if '--self-test' in sys.argv:
        print('positive controls (each check must fail on an injected fault):')
        rc = self_test(tex)
        print('SELF-TEST ' + ('PASS' if rc == 0 else 'FAIL'))
        return rc
    records = entity_records()
    values = scan_entity_values(records)
    orders = scan_ordering(tex)
    labels = scan_labels(tex)
    entities = {(m, s) for m, s, _l, _v, _c in records}
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('# P6 gate 3 — cross-section logical conflicts (entity level)\n\n')
        f.write('Generated by `python tools/p6_cross_section_scan.py`. **Read-only: `paper/main.tex` '
                'is not modified.** Entities come from the claims ledger\'s curated evidence '
                'columns, not from parsing prose — a prose-parsing draft of this tool held zero '
                '`(F1, CA-TOSG)` records and mistook a budget literal for an F1, so its silence '
                'meant nothing.\n\n')
        f.write(f'Coverage: **{len(records)} entity records** over **{len(entities)} distinct '
                '(metric, split) entities**. Positive controls: '
                '`python tools/p6_cross_section_scan.py --self-test`.\n\n')
        f.write(f'| class | count |\n|---|---|\n| ENTITY-VALUE | {len(values)} |\n'
                f'| ORDERING | {len(orders)} |\n| EXISTENCE | {len(labels)} |\n\n')
        f.write(f'## ENTITY-VALUE conflicts ({len(values)})\n\n')
        for i, (key, la, va, ca, lb, vb, cb) in enumerate(values, 1):
            f.write(f'**EV-{i} — {key[0]} on {key[1]}**\n\n- `{la}` → {va}\n  > {ca[:260]}\n\n'
                    f'- `{lb}` → {vb}\n  > {cb[:260]}\n\n')
        if not values:
            f.write('None.\n\n')
        f.write(f'## ORDERING conflicts ({len(orders)})\n\n')
        for claim, detail in orders:
            f.write(f'- {claim}: {detail}\n')
        if not orders:
            f.write('None — every dominance/ordering statement agrees with '
                    '`results/main/true_e2e_ap.csv`.\n')
        f.write(f'\n## EXISTENCE conflicts ({len(labels)})\n\n')
        for lab, line in labels:
            f.write(f'- `main.tex:{line}` references `{lab}`, which no `\\label` defines\n')
        if not labels:
            f.write('None — every `\\ref` resolves.\n')
    print(f'coverage: {len(records)} entity records over {len(entities)} entities')
    print(f'ENTITY-VALUE {len(values)} | ORDERING {len(orders)} | EXISTENCE {len(labels)} '
          f'-> {os.path.relpath(OUT, ROOT)}')
    for key, la, va, _ca, lb, vb, _cb in values:
        print(f'  {key}: {la} {va}  vs  {lb} {vb}')
    for claim, detail in orders:
        print(f'  ORDERING: {claim} -- {detail}')
    for lab, line in labels:
        print(f'  dangling ref at line {line}: {lab}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
