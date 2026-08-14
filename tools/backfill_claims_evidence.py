#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-5 item 10: mechanically back-fill the ledger's CSV + Generator cells.

Fills ONLY what can be derived without judgement, and only where the derivation is unambiguous:

  * the row's evidence cells are currently blank, AND
  * `tools/audit_claims_evidence.py`'s value search locates the claim at FULL coverage -- every one
    of its distinctive numeric literals is carried by the same committed result file -- AND
  * that file resolves to exactly one generator in `results/README.md`.

Two of the six evidence columns are written: `CSV` (the located file) and `Generator` (its command,
verbatim from the results index). `Split`, `Metric`, `Statistical support` and `Allowed wording`
are left blank on purpose: they are readings of the claim, not lookups, and inventing them is how a
ledger stops being evidence. Partial-coverage matches are left blank too and reported, because a
2-of-4 literal hit is a hint, not an attribution.

    python tools/backfill_claims_evidence.py            # write
    python tools/backfill_claims_evidence.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from audit_claims_evidence import (  # noqa: E402
    claims_by_section, locate_evidence, read, results_corpus, results_index,
)

CLAIMS = os.path.join(ROOT, 'docs', 'claims.md')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    corpus = results_corpus()
    index = results_index()
    exact_by_id = {cid: exact for _s, _ss, cid, _c, exact in claims_by_section()}

    lines = read(CLAIMS).splitlines(keepends=True)
    filled, partial, unlocated, already = 0, 0, 0, 0
    out = []
    for line in lines:
        if not line.startswith('| c'):
            out.append(line)
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 9:
            out.append(line)
            continue
        cid, ev = cells[0], cells[3:9]
        if any(ev):
            already += 1
            out.append(line)
            continue

        found, lits = locate_evidence(exact_by_id.get(cid, ''), corpus)
        if not found:
            unlocated += 1
            out.append(line)
            continue
        _n, path, hit = found[0]
        gen = index.get(os.path.basename(path), (None, ''))[0]
        if len(hit) != len(lits) or gen is None:
            partial += 1
            out.append(line)
            continue

        # A literal '|' inside a generator command (`... --train|--evaluate`) breaks the row's
        # 9-cell parse, and the ledger generator silently drops an unparseable row's evidence on
        # the next rebuild -- the cell reads as filled here and comes back blank. A backslash
        # escape does NOT help: the parser does a plain str.split('|'). Use the HTML entity, which
        # renders as a pipe and contains none.
        bar = lambda t: t.replace('|', '&#124;')
        cells[5] = '`{}`'.format(bar(path))                      # CSV
        cells[6] = '`{}`'.format(bar(gen))                       # Generator
        filled += 1
        out.append('| ' + ' | '.join(cells) + ' |\n')

    if not args.dry_run:
        with open(CLAIMS, 'w', encoding='utf-8') as f:
            f.writelines(out)

    print(f'already filled          {already}')
    print(f'newly back-filled       {filled}   (full-literal coverage, single generator)')
    print(f'left blank -- partial   {partial}   (located, but not every literal matched)')
    print(f'left blank -- unlocated {unlocated}')
    print(('DRY RUN, nothing written' if args.dry_run else f'wrote {CLAIMS}'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
