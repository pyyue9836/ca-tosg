#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate (R23-15): every numeric literal in the delivered text is bound, or explicitly structural.

The existing checks are claim-shaped or table-shaped: `p6_numbers_vs_csv` walks ledger rows and
table cells, the fingerprint sweep greps a list of KNOWN retired values. Neither enumerates the
document. A number that sits in prose, is not part of a ledger row, and was never registered as
retired is invisible to all of them -- which is how `0.187`, `2.3\\times`, `1.7\\times` and the
`{L, C16}` class set survived batch after batch.

This gate enumerates instead. Every decimal literal in `main.tex` must be **covered by a verified
binding**:

  1. it is a literal of a claim whose ledger row names a CSV that CARRIES it (`p6_numbers_vs_csv`'s
     own hit set -- the file is named by the ledger, not searched for); or
  2. it is a table cell that gate located, or a cell the table generator declares derived; or
  3. it is registered in `docs/canonical_quantities.md`, whose gate re-derives it; or
  4. it is listed in `tests/structural_literals.md` with a written reason.

Anything else FAILS: it is a number nothing in the verification chain is responsible for.

**Why coverage and not "does this number exist somewhere in results/".** That weaker rule was
implemented first and measured before being trusted: with 202 committed products, EVERY retired
value this batch removed -- 0.187, 2.3, 1.7, 0.9011, 0.9165, 0.1706, 0.8891, 0.2542, 0.158, 0.251 --
found a coincidental match somewhere and would have passed. A gate that cannot fail is not a gate,
so the rule is binding-coverage, which is the property that actually failed in each of those cases.

Generated documents (`docs/milestone_summary.md`, `results/README.md`) are held to a different and
stronger guarantee: re-running their generator must reproduce them byte for byte.

    python tests/test_numeric_literals.py [--self-test] [--list]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import p6_numbers_vs_csv as p6                                       # noqa: E402
from audit_claims_evidence import results_corpus                     # noqa: E402
from p6_numbers_vs_csv import carries_any_unit                       # noqa: E402

WHITELIST = os.path.join(ROOT, 'tests', 'structural_literals.md')
REGISTER = os.path.join(ROOT, 'tests', 'uncovered_literals.md')   # the R23-15 debt register
# the delivered text: the same targets the fingerprint sweep covers. Explanatory documents that
# exist to quote superseded values (the corrigendum, the protocol change-log) are NOT delivered text.
TARGETS = ('paper/archive/manuscript_frozen.tex',)
# documents that may quote the paper's numbers but must not introduce new ones
ECHO_TARGETS = ('README.md', 'docs/model_zoo.md', 'paper/archive/supplementary_frozen.tex')
# R23-15: generator-written documents are held to the STRONGER guarantee -- re-running the generator
# must reproduce them byte for byte -- rather than to literal binding, because their numbers are
# computed at build time from canonical products and legitimately include derived values that appear
# in no CSV cell (sums, differences). A hand-edit of such a file fails the regeneration check.
GENERATED = {'docs/milestone_summary.md': 'tools/build_milestone_summary.py',
             'results/README.md': 'projects/ca_tosg/utils/results_index.py'}
LITERAL = re.compile(r'(?<![\d.\w])(\d+\.\d+)(?![\d])')
# contexts in which a decimal is not a measurement
SKIP_LINE = re.compile(r'(\\cite|\\label|\\ref|\\includegraphics|\\bibitem|arXiv|doi|'
                       r'IEEE|3GPP|802\.11|version)', re.I)


def bound_in_own_csv():
    """Literals verified inside the CSV their OWN ledger row names, below `distinctive()`'s floor.

    R33: `distinctive()` skips literals with fewer than three decimals and three significant digits,
    because a weak literal cannot *attribute* a file. Once the ledger has named the file, though, the
    literal can still be *verified* in it -- and the summary sentences R33 left in the main text quote
    exactly such values (1.5 / 5.8 / 0.2%). This reads `docs/claims.md` directly rather than
    recomputing claim ids: `audit_claims_evidence.claims_by_section` and the ledger builder disagree
    on the id of some sentences (recorded as a finding in R26-3), and a check that depends on that
    agreement silently covers nothing.
    """
    import re as _re
    ledger = os.path.join(ROOT, 'docs', 'claims.md')
    if not os.path.exists(ledger):
        return set()
    corpus = results_corpus()
    out = set()
    for line in open(ledger, encoding='utf-8'):
        if not line.startswith('| c'):
            continue
        cells = [x.strip() for x in line.strip().strip('|').split('|')]
        if len(cells) != 9:
            continue
        lits = _re.findall(r'(?<![\d.])(\d+\.\d+)(?![\d])', cells[2])
        files = [f for f in _re.findall(r'[\w./-]+\.(?:csv|json)', cells[5] + ' ' + cells[6])
                 if not f.startswith(('docs/', 'tests/', 'paper/'))]
        vals = [corpus[f] for f in files if f in corpus]
        for lit in lits:
            if any(carries_any_unit(v, lit) or carries_any_unit([-x for x in v], lit) for v in vals):
                out.add(lit)
    return out


def figure_caption_literals():
    """Numbers a figure caption prints, verified in the figure generator's own provenance record.

    R36 remounted ten figures. A caption is not a sentence the claims ledger indexes, so its numbers
    had no claim row to ride -- but they are not unbound: `plot_frozen_figs.py` writes every value
    its figures draw into `results/provenance/PROVENANCE_figures.json`, which is a generator-written
    data product. A caption literal is accepted when that record carries it.
    """
    import re as _re
    # R39: each figure generator writes its own provenance record; the qualitative figure's values
    # live in PROVENANCE_qualitative.json, the frozen curves' in PROVENANCE_figures.json.
    provs = ('results/provenance/PROVENANCE_figures.json',
             'results/provenance/PROVENANCE_qualitative.json')
    corpus = results_corpus()
    vals = [v for p_ in provs if p_ in corpus for v in corpus[p_]]
    if not vals:
        return set()
    tex = open(os.path.join(ROOT, TARGETS[0]), encoding='utf-8').read()
    out = set()
    for cap in _re.findall(r'\\caption\{(.*?)\}\s*(?:\\label|\\end\{figure)', tex, _re.S):
        for lit in _re.findall(r'(?<![\d.])(\d+\.\d+)(?![\d])', cap):
            if carries_any_unit(vals, lit) or carries_any_unit([-v for v in vals], lit):
                out.add(lit)
    return out


def registered_debt():
    """{(file, literal)} already recorded as uncovered in the debt register.

    The gate ratchets: existing debt is listed, and anything NEW fails. Shrinking the register is
    deliberate work; growing it silently is what this gate exists to prevent.
    """
    out = set()
    if not os.path.exists(REGISTER):
        return out
    for line in open(REGISTER, encoding='utf-8'):
        m = re.match(r'^- `([\w./]+):\d+` `([\d.]+)`', line)
        if m:
            out.add((m.group(1), m.group(2)))
    return out


def whitelist():
    """{literal: reason} from the reviewable whitelist file."""
    out = {}
    if not os.path.exists(WHITELIST):
        return out
    for line in open(WHITELIST, encoding='utf-8'):
        m = re.match(r'^\|\s*`([\d.]+)`\s*\|\s*(.+?)\s*\|\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def declared_derived():
    """Cells the table generator DECLARES as derived (regime means); `p6_numbers_vs_csv` reports
    them as declared-derived rather than located, and this gate uses the same category."""
    import json
    p = os.path.join(ROOT, 'results/provenance/DERIVED_TABLE_CELLS.json')
    if not os.path.exists(p):
        return set()
    d = json.load(open(p))
    return {str(x) for v in d.values() if isinstance(v, list) for x in v}


def verified_literals():
    """The literals the verification chain is actually responsible for.

    From `p6_numbers_vs_csv`: every claim literal confirmed inside the CSV its OWN ledger row names,
    every located table cell, and every cell the generator declares derived. Misses are deliberately
    excluded -- a miss is the gate reporting that a number is not where it says it is.
    """
    # signs are stripped on BOTH sides: the ledger stores a CI bound as `+0.00005` while the
    # document prints `0.00005` inside a bracket, and a string comparison called six correctly
    # verified literals unbound.
    def bare(x):
        return x.lstrip('+-')
    hits, _misses, derived, _skipped = p6.rows()
    out = {bare(h[2]) for h in hits} | {bare(d[2]) for d in derived}
    found, _missing, derived_cells = p6.table_cells(results_corpus())
    out |= {bare(f[1]) for f in found}
    out |= {bare(c[1]) for c in derived_cells}
    out |= set(p6.STRUCTURAL)
    return out


def registered_derived():
    """Literals the canonical registry prints as derived (its own gate re-derives them)."""
    p = os.path.join(ROOT, 'docs', 'canonical_quantities.md')
    return set(re.findall(r'(\d+\.\d+)', open(p, encoding='utf-8').read()))


def named_sources(text):
    """The committed products a document names in its own body.

    An echo document (README, model_zoo) carries no claim rows, so it cannot ride main.tex's
    verified set. The equivalent discipline is the ledger's: the file must be NAMED, and the value
    must be in that named file -- not "somewhere under results/", which is the rule this gate was
    rewritten to avoid.
    """
    corpus = results_corpus()
    out = {}
    for rel in set(re.findall(r'[\w./-]+\.(?:csv|json)', text)):
        for key in corpus:
            if key.endswith(rel) or rel.endswith(os.path.basename(key)):
                out[key] = corpus[key]
    return out


def scan(verified, wl, derived):
    bad = []
    for rel in TARGETS + ECHO_TARGETS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        text = open(path, encoding='utf-8').read()
        named = named_sources(text) if rel in ECHO_TARGETS else {}
        for i, line in enumerate(text.split('\n'), 1):
            if SKIP_LINE.search(line):
                continue
            for lit in LITERAL.findall(line):
                if lit in wl or lit in derived or lit in verified:
                    continue
                if named and any(carries_any_unit(v, lit) or carries_any_unit([-x for x in v], lit)
                                 for v in named.values()):
                    continue
                bad.append((rel, i, lit, ' '.join(line.split())[:110]))
    return bad


def generated_intact():
    """Each generated document must be reproduced byte-for-byte by re-running its generator.

    The check MUST NOT mutate the working tree. The first implementation let the generator's write
    stand, so a stale file failed once and then passed on the next run because the failing run had
    silently repaired it -- a check that fixes what it is checking cannot report the state it found.
    The original bytes are therefore restored before returning, whatever the outcome.
    """
    import hashlib
    import subprocess
    bad = []
    for rel, gen in GENERATED.items():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        original = open(path, 'rb').read()
        before = hashlib.sha256(original).hexdigest()
        cmd = [sys.executable, os.path.join(ROOT, gen)]
        if gen.endswith('results_index.py'):
            cmd.append('--write')
        try:
            r = subprocess.run(cmd, capture_output=True, cwd=ROOT)
            if r.returncode != 0:
                bad.append((rel, gen, 'generator FAILED: ' + r.stderr.decode()[-200:]))
                continue
            after = hashlib.sha256(open(path, 'rb').read()).hexdigest()
            if before != after:
                bad.append((rel, gen, 'the committed file is NOT what its generator writes'))
        finally:
            with open(path, 'wb') as f:            # restore, always
                f.write(original)
    return bad


def main():
    verified = verified_literals()
    wl, derived = whitelist(), registered_derived() | declared_derived() | bound_in_own_csv() | figure_caption_literals()
    if '--self-test' in sys.argv:
        # the control that matters: every value this batch retired must be UNCOVERED, and the
        # primary cell's own F1 must be covered.
        # 0.8891 is deliberately absent: it is a LIVE value elsewhere (tab:true_e2e_snr, AWGN
        # 12/20 dB), so it must stay covered. Its retired use is blocked by a context-anchored
        # fingerprint instead -- the collision this batch hit when the bare form was tried.
        retired = ('0.187', '2.3', '1.7', '0.9011', '0.9165', '0.1706', '0.2542',
                   '0.158', '0.251')
        leaks = [r for r in retired if r in verified or r in wl or r in derived]
        print('SELF-TEST: retired values still covered -> %s'
              % (', '.join(leaks) if leaks else 'none (all would be caught)'))
        ok_bound = '0.89691' in verified
        print('SELF-TEST: the primary-cell F1 0.89691 -> %s'
              % ('covered (silent)' if ok_bound else 'FALSE POSITIVE'))
        # the ratchet: an invented literal in a delivered file is NEW debt and must fail
        debt = registered_debt()
        fires = ('paper/archive/manuscript_frozen.tex', '0.98765') not in debt and '0.98765' not in verified
        print('SELF-TEST: an invented 0.98765 in main.tex -> %s'
              % ('FIRES' if fires else 'DOES NOT FIRE'))
        return 0 if (not leaks and ok_bound and fires) else 1
    debt = registered_debt()
    all_bad = scan(verified, wl, derived)
    bad = [b for b in all_bad if (b[0], b[2]) not in debt]
    carried = len(all_bad) - len(bad)
    gen_bad = generated_intact()
    for rel, gen, why in gen_bad:
        print(f'  GENERATED {rel}: {why} (regenerate with {gen})')
    print(f'numeric literals: {len(TARGETS + ECHO_TARGETS)} delivered files, {len(GENERATED)} '
          f'generated documents, {len(verified)} verified literals, {len(wl)} structural entries, '
          f'{carried} carried as registered debt ({len(debt)} in the register)')
    if '--list' in sys.argv:
        for rel, ln, lit, ctx in bad:
            print(f'  {rel}:{ln}: {lit}   {ctx}')
    if bad or gen_bad:
        for rel, ln, lit, ctx in bad[:40]:
            print(f'  UNBOUND {rel}:{ln}: {lit}   {ctx}')
        print(f'NUMERIC LITERAL GATE FAIL: {len(bad)} NEW uncovered literal(s), {len(gen_bad)} '
              'generated document(s) not reproduced by their generator. Bind the number to a '
              'product, or record it in tests/uncovered_literals.md with the rest of the debt '
              '(R23-15)')
        return 1
    print(f'NUMERIC LITERAL GATE PASS: no NEW uncovered literal ({carried} carried as registered '
          'debt), and every generated document is byte-reproduced by its generator.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
