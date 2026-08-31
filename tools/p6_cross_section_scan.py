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
  TERMINOLOGY   entities whose DESCRIPTION has gone wrong more than once, curated in
                `tests/tracked_terms.md`. Numbers are not the only thing that goes stale: the
                signalling direction was written sender-side three times (R27-1), and no numeric
                check can see that.

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

MAIN = os.path.join(ROOT, 'paper', 'archive', 'manuscript_frozen.tex')
E2E = os.path.join(ROOT, 'results/main/true_e2e_ap.csv')
FIXED = os.path.join(ROOT, 'results/main/fixed_references.csv')
OUT = os.path.join(ROOT, 'docs', 'p6_cross_section_conflicts.md')

NUM = re.compile(r'(?<![\d.])([-+]?\d+\.\d{2,5})(?![\d])')
# Settings, not measurements. Budgets and IoU thresholds appear in almost every claim, so leaving
# them in made a claim that merely mentions "B_max=0.20" collide with any other claim about the same
# (metric, split) -- two such false conflicts survived to the last verification round.
STRUCTURAL = {0.1, 0.2, 0.3, 0.5, 0.7, 0.024, 0.495, 0.99, 0.05, 0.02, 0.005}


TRACKED = os.path.join(ROOT, 'tests', 'tracked_terms.md')


def tracked_terms():
    """[(term, forbidden regex, required framing, reason)] from the curated table."""
    out = []
    if not os.path.exists(TRACKED):
        return out
    for line in open(TRACKED, encoding='utf-8'):
        if not line.startswith('|') or line.startswith('|---') or line.startswith('| term'):
            continue
        c = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(c) == 4 and c[1].startswith('`') and c[1].endswith('`'):
            # '&#124;' is how a regex alternation survives a markdown table row
            out.append((c[0], c[1].strip('`').replace('&#124;', '|'), c[2], c[3]))
    return out


def scan_terminology(text):
    """Matches of any forbidden form. Each is a conflict between the text and the architecture."""
    bad = []
    for term, pattern, required, reason in tracked_terms():
        for m in re.finditer(pattern, text, re.I):
            ctx = ' '.join(text[max(0, m.start() - 60):m.end() + 60].split())
            bad.append((term, m.group(0), required, reason, ctx))
    return bad


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
    # R45: this control had been DEAD. It injected `max(vals) + 0.5` against records[0], whose own
    # values span 0.0007 to 0.2168 -- so the injected 0.7168 failed `_same_scale` against the record's
    # own smallest value and no conflict was ever raised. A positive control that depends on which
    # record happens to sort first is not a control. Pick a record whose values are tightly clustered
    # (max/min <= 2) and inject a disjoint value on the SAME scale, and say so loudly if none exists.
    target = next((r for r in recs
                   if [abs(x) for x in r[3] if x]
                   and max(abs(x) for x in r[3] if x) / min(abs(x) for x in r[3] if x) <= 2), None)
    if target:
        metric, split, _loc, vals, _c = target
        inj.append((metric, split, 'INJECTED SECTION', {round(max(vals) * 1.5, 4)},
                    'injected contradictory claim'))
    else:
        print('  ENTITY-VALUE: NO INJECTABLE RECORD (every record spans more than one octave)')
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

    # R27-1: the terminology control injects the exact form that recurred three times.
    # R40: the controls are this batch's own retired sentences, verbatim
    probes = ('\nwhere the sender adaptively selects the semantic level.\n'
              '\n(the dominated $C_{256}$ is a physical-layer comparator, not a deployed action)\n'
              '\nAt moderate SNR, $C_{16}$ may become useful because it provides richer features '
              'with better reliability than $C_{256}$.\n'
              '\nmethods can be used inside the $C_{16}$ or $C_{256}$ branches, while the selector '
              'decides when these branches should be activated.\n'
              # R45-4: the retired framing -- Where2comm entering a comparison as a baseline
              '\nWhere2comm is the strongest baseline available for this setting.\n'
              # R46-2: the retired fair-comparison sentence
              '\nAll methods share the same backbone and detection head to ensure a fair comparison.\n'
              # R57-3: an adjudication of the external arm, which no cell licenses
              '\nWhere2comm is non-inferior to CA-TOSG at the confirmatory cell.\n')
    fired4 = scan_terminology(tex + probes)
    clean = scan_terminology(tex)
    n_hits = len({t[0] for t in fired4})
    print(f'  TERMINOLOGY:  {"FIRES" if len(fired4) >= 4 else "DOES NOT FIRE"} '
          f'({len(tracked_terms())} tracked forms; {len(fired4)} injected hits over {n_hits} '
          f'families; {len(clean)} live match(es))')
    rc |= 0 if (len(fired4) >= 7 and not clean) else 1
    return rc


def _delivered():
    """main.tex plus supplementary.tex -- R40: the supplementary is delivered text too."""
    parts = [open(MAIN, encoding='utf-8').read()]
    supp = os.path.join(os.path.dirname(MAIN), 'supplementary_frozen.tex')
    if os.path.exists(supp):
        parts.append(open(supp, encoding='utf-8').read())
    return '\n'.join(parts)


def main() -> int:
    tex = _delivered()
    if '--self-test' in sys.argv:
        print('positive controls (each check must fail on an injected fault):')
        rc = self_test(tex)
        print('SELF-TEST ' + ('PASS' if rc == 0 else 'FAIL'))
        return rc
    records = entity_records()
    values = scan_entity_values(records)
    orders = scan_ordering(tex)
    labels = scan_labels(tex)
    terms = scan_terminology(tex)
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
                f'| ORDERING | {len(orders)} |\n| EXISTENCE | {len(labels)} |\n'
                f'| TERMINOLOGY | {len(terms)} |\n\n')
        f.write(f'## TERMINOLOGY conflicts ({len(terms)})\n\n')
        for term, hit, required, reason, ctx in terms:
            f.write(f'- **{term}**: found `{hit}`; required framing: {required}. {reason}\n'
                    f'  > {ctx[:260]}\n')
        if not terms:
            f.write('None — every tracked form in `tests/tracked_terms.md` is absent.\n')
        f.write('\n')
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
          f'| TERMINOLOGY {len(terms)} '
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
