#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P6 gate 1 — every bound number re-checked against the CSV the ledger binds it to.

For each ledger row that cites a committed result file, each distinctive literal in the claim is
looked for **inside that specific file**, at the literal's own printed precision. This is narrower
and stronger than the audit's value search, which ranks candidate files: here the file is already
named, so a miss is a real finding — either the number moved, or it was bound to the wrong product.

Derived quantities (ratios, percentages, differences) legitimately do not appear as cells. Rows whose
generator cell says so, and the quantities registered in `docs/canonical_quantities.md`, are reported
as DERIVED rather than as misses, and the registry gate re-derives those separately.

    python tools/p6_numbers_vs_csv.py [--self-test]
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from audit_claims_evidence import (  # noqa: E402
    carries, claims_by_section, distinctive, ledger_rows, read, results_corpus, text_key,
)

OUT = os.path.join(ROOT, 'docs', 'p6_numbers_vs_csv.md')
DERIVED_HINT = re.compile(r'derived|ratio|percent|registered in|sum|minus|difference|headroom',
                          re.I)


def carries_any_unit(vals, lit):
    """The file holds the literal, or the same quantity as a FRACTION of it.

    The paper prints ratios as percentages (56.3%) while the CSVs store fractions (0.5631). That is
    a unit, not a discrepancy, and treating it as a miss buried 16 correctly-bound numbers. The
    fraction form is only accepted at the precision the percentage was printed to, so 56.3 matches
    0.5631 but not 0.5700.
    """
    if carries(vals, lit):
        return 'exact'
    dec = len(lit.split('.')[1]) if '.' in lit else 0
    target = float(lit) / 100.0
    if any(round(v, dec + 2) == round(target, dec + 2) for v in vals):
        return 'percent form'
    return None


def rows():
    ledger = ledger_rows(by_text=True)
    corpus = results_corpus()
    hits, misses, derived, skipped = [], [], [], 0
    for section, subsection, cid, claim, exact in claims_by_section():
        cells = ledger.get(cid) or ledger.get('TXT:' + text_key(claim))
        if not cells or not any(cells):
            skipped += 1
            continue
        csv_cell, gen_cell = cells[2], cells[3]
        files = [f for f in re.findall(r'[\w./-]+\.(?:csv|json)', csv_cell + ' ' + gen_cell)
                 if not f.startswith(('docs/', 'tests/', 'paper/'))]
        lits = distinctive(exact)
        if not files or not lits:
            skipped += 1
            continue
        loc = f'{section}{" / " + subsection if subsection else ""}'
        for lit in lits:
            found = [(f, carries_any_unit(corpus[f], lit)) for f in files if f in corpus]
            found = [(f, how) for f, how in found if how]
            if found:
                hits.append((cid, loc, lit, found[0][0], found[0][1]))
            elif DERIVED_HINT.search(gen_cell):
                derived.append((cid, loc, lit, files[0], gen_cell[:120]))
            else:
                misses.append((cid, loc, lit, files, claim))
    return hits, misses, derived, skipped


TABLE_RE = re.compile(r'\\label\{(tab:[^}]+)\}(.*?)\\end\{tabular\}', re.S)
CELL_RE = re.compile(r'(?<![\d.])(-?\d+\.\d{2,6})(?![\d])')
# cells that are settings, not measurements: budgets, IoU thresholds, SNR points, payload constants
STRUCTURAL = {'0.10', '0.20', '0.30', '0.024', '0.495', '0.990', '0.99', '0.05', '0.02', '0.00',
              '0.0', '0.5', '0.7', '0.3', '10.0', '12.0', '16.0', '18.0', '20.0', '8.0', '2.0',
              '4.0', '6.0', '14.0', '0.005'}


def _declared_derived():
    """Cells a generator states it DERIVED (regime means etc.), so they exist in no CSV by design."""
    p = os.path.join(ROOT, 'results/provenance/DERIVED_TABLE_CELLS.json')
    if not os.path.exists(p):
        return set()
    d = json.load(open(p))
    return {v for k, vals in d.items() if k.startswith('tab:') for v in vals}


# R23-9: which files may a table cell be located in.
# The corpus walks every .csv/.json/.md/.txt under results/, so a cell could "locate" in a narrative
# or historical document -- a provenance transcript, an anomaly report, the results index -- none of
# which is a canonical product. A retired value quoted inside such a file would therefore pass the
# gate. Binding sources are now restricted to generator-written data products (.csv/.json), minus an
# explicit deny-list of records that exist to quote superseded states.
CANONICAL_EXT = ('.csv', '.json')
# R24-3 narrowing: a PROVENANCE *.txt is a narrative transcript, but a generator-written
# PROVENANCE_*.json is a data product and is the only committed home of some figure-caption values.
# DERIVED_TABLE_CELLS.json stays excluded -- it is the table generator's own declaration of its own
# output, and accepting it is the self-certification R23-9 removed.
NON_CANONICAL = re.compile(r'(README|ANOMALY_REPORT|FUSE_REPORT|corrigendum|p0_corrigendum|'
                           r'PROVENANCE[\w]*\.txt|DERIVED_TABLE_CELLS|/logs/)', re.I)


def canonical_corpus(corpus):
    return {f: v for f, v in corpus.items()
            if f.endswith(CANONICAL_EXT) and not NON_CANONICAL.search(f)}


def table_cells(corpus):
    """R20 9b: EVERY numeric cell of EVERY table in main.tex, checked against the corpus.

    Claim-level checking walks prose sentences, so a table body could (and did) keep a whole block of
    retired numbers while every claim around it was bound -- tab:headline survived two corrigendum
    batches that way. This walks the tabulars themselves.
    """
    tex = open(os.path.join(ROOT, 'paper/main.tex'), encoding='utf-8').read()
    declared = _declared_derived()
    canon = canonical_corpus(corpus)
    found, missing, derived_cells, only_narrative = [], [], [], []
    for label, body in TABLE_RE.findall(tex):
        for lit in CELL_RE.findall(body):
            if lit.lstrip('-') in STRUCTURAL:
                continue
            hit = [f for f, vals in canon.items() if carries_any_unit(vals, lit.lstrip('-'))]
            if not hit:
                wide = [f for f, vals in corpus.items() if carries_any_unit(vals, lit.lstrip('-'))]
                if wide:
                    only_narrative.append((label, lit, wide[0]))
            if hit:
                found.append((label, lit, hit[0]))
            elif lit in declared:
                derived_cells.append((label, lit, 'declared derived'))
            else:
                missing.append((label, lit, None))
    if only_narrative:
        print(f'  R23-9: {len(only_narrative)} cell(s) were previously located ONLY in a '
              f'non-canonical file (narrative/historical); they are no longer accepted:')
        for label, lit, f in only_narrative:
            print(f'    {label}: {lit} -- was located in {f}')
    return found, missing, derived_cells


def self_test():
    """The gate must flag a number that its own bound CSV does not contain."""
    corpus = results_corpus()
    path = 'results/main/replay_summary.csv'
    fake = '0.123456789'
    fired = not carries(corpus[path], fake)
    print(f'  literal absent from its bound CSV is flagged: {"FIRES" if fired else "DOES NOT FIRE"}')
    # and it must NOT flag a literal the file really holds
    real = f'{float(read(os.path.join(ROOT, path)).splitlines()[1].split(",")[3]):.5f}'
    quiet = carries(corpus[path], real)
    print(f'  literal present in its bound CSV is accepted:  {"OK" if quiet else "BROKEN"} ({real})')
    return 0 if (fired and quiet) else 1


def main() -> int:
    if '--self-test' in sys.argv:
        print('positive controls:')
        rc = self_test()
        print('SELF-TEST ' + ('PASS' if rc == 0 else 'FAIL'))
        return rc
    hits, misses, derived, skipped = rows()
    corpus = results_corpus()
    t_found, t_missing, t_derived = table_cells(corpus)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('# P6 gate 1 — numbers vs the CSV each is bound to\n\n')
        f.write('Generated by `python tools/p6_numbers_vs_csv.py`. Each distinctive literal in a '
                'bound claim is looked for **inside the file the ledger names**, at the literal\'s '
                'own precision.\n\n')
        pct = sum(1 for h in hits if h[4] == 'percent form')
        f.write(f'| outcome | count |\n|---|---|\n| found in the bound file | {len(hits)} '
                f'({pct} as the percent form of a stored fraction) |\n'
                f'| DERIVED (registry / stated as derived) | {len(derived)} |\n'
                f'| MISS | {len(misses)} |\n'
                f'| claims with no bound file or no distinctive literal | {skipped} |\n\n')
        f.write(f'## MISS ({len(misses)})\n\n')
        for cid, loc, lit, files, claim in misses:
            f.write(f'- `{cid}` **{lit}** — {loc}\n  - bound to: {", ".join(files)}\n'
                    f'  - > {claim[:220]}\n')
        if not misses:
            f.write('None — every bound literal is present in the file it is bound to.\n')
        f.write(f'\n## TABLE CELLS (R20 9b): {len(t_found)} located, '
                f'{len(t_derived)} declared-derived, {len(t_missing)} unlocated\n\n')
        for label, lit, _ in t_missing:
            f.write(f'- `{label}` cell **{lit}** is in no committed result file\n')
        if not t_missing:
            f.write('Every numeric cell of every table in `main.tex` is located in a committed '
                    'product (structural constants excepted).\n')
        f.write(f'\n## DERIVED ({len(derived)})\n\n')
        for cid, loc, lit, file, gen in derived:
            f.write(f'- `{cid}` {lit} — {loc} — derived from `{file}`: {gen}\n')
    print(f'table cells: {len(t_found)} located, {len(t_derived)} declared-derived, '
          f'{len(t_missing)} UNLOCATED')
    for label, lit, _ in t_missing[:12]:
        print(f'  TABLE MISS {label} {lit}')
    print(f'found {len(hits)} ({sum(1 for h in hits if h[4] == "percent form")} percent-form) '
          f'| derived {len(derived)} | MISS {len(misses)} | '
          f'unbound-or-no-literal {skipped} -> {os.path.relpath(OUT, ROOT)}')
    for cid, loc, lit, files, _c in misses:
        print(f'  MISS {cid} {lit} ({loc}) bound to {files}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
