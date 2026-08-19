#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate (R45-6): the delivered documents may not contradict the protocol's own verdicts.

Every other gate here compares the paper against **data**. None compared it against the **record**.
That gap has cost twice:

  * `docs/experiment_protocol.md` recorded, with numbers, that "conclusions are insensitive to this
    constant" is *false as written* — and `main.tex` kept asserting it for four more batches;
  * the protocol carries "SUPERSEDED BY R31-1" over the C256 set-domination argument, and the
    withdrawn form had to be hunted site by site rather than blocked.

The pairs live in `tests/protocol_claims.md`, in the same probe style as the comparison-direction
gate. For each row:

  1. the `protocol_probe` must still be present in the protocol — the record is the anchor, and a
     row whose anchor has vanished is stale, not passing;
  2. the `retired_regex` must match **nothing** in `main.tex` + `supplementary.tex`;
  3. the `required_probe`, when given, must appear in at least one delivered document.

    python tests/test_protocol_reconciliation.py [--self-test] [--verbose]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIRS = os.path.join(ROOT, 'tests', 'protocol_claims.md')
PROTOCOL = os.path.join(ROOT, 'docs', 'experiment_protocol.md')
DOCS = (os.path.join(ROOT, 'paper', 'main.tex'),
        os.path.join(ROOT, 'paper', 'supplementary.tex'))


def rows():
    out = []
    for line in open(PAIRS, encoding='utf-8'):
        if not line.startswith('|') or line.startswith('|---') or line.startswith('| id ')\
           or line.startswith('| column '):
            continue
        # strip the markdown code fences too: leaving them in silently made every pattern
        # unmatchable, which is a gate that cannot fail (found by the self-test, R45-6).
        c = [x.strip().strip('`').strip().replace('&#124;', '|')
             for x in line.strip().strip('|').split('|')]
        if len(c) != 6 or c[2] not in ('false-as-written', 'superseded'):
            continue
        out.append(tuple(c))
    return out


def delivered():
    return {os.path.basename(p): open(p, encoding='utf-8').read()
            for p in DOCS if os.path.exists(p)}


def check(protocol, docs, verbose=False):
    bad = []
    for cid, probe, verdict, retired, required, _why in rows():
        if probe not in protocol:
            bad.append((cid, f'protocol anchor missing: {probe[:60]!r} is no longer in '
                             'docs/experiment_protocol.md -- the pair is stale'))
            continue
        rx = re.compile(retired, re.I)
        hits = [(name, m.group(0)) for name, text in docs.items() for m in rx.finditer(text)]
        if hits:
            where = '; '.join(f'{n}: {h[:60]!r}' for n, h in hits[:3])
            bad.append((cid, f'the protocol records this as {verdict}, but the paper still says it '
                             f'({len(hits)} site(s)) -- {where}'))
        if required and not any(required in t for t in docs.values()):
            bad.append((cid, f'replacement claim absent: no delivered document contains '
                             f'{required[:60]!r}'))
        if verbose and not hits:
            print(f'  PASS  {cid}: {verdict}; 0 retired sites, replacement present')
    return bad


def self_test():
    """Inject each retired form and require the gate to fire on it."""
    protocol = open(PROTOCOL, encoding='utf-8').read()
    docs = delivered()
    live = check(protocol, docs)
    print(f'SELF-TEST: the live documents -> {len(live)} failure(s) (expected 0)')
    fired = 0
    probes = {
        'anchor-insensitivity': 'the conclusions are insensitive to this constant.',
        'where2comm-baseline': 'Where2comm is the strongest baseline for this setting.',
        'c256-dominance': 'Fixed $C_{256}$ is dominated by $C_{256}$ on both axes.',
        'latency-budget': 'which fits the $100$~ms budget of a $10$~Hz cycle.',
    }
    for cid, probe in probes.items():
        injected = dict(docs)
        first = sorted(injected)[0]
        injected[first] = injected[first] + '\n' + probe + '\n'
        base = {b[1] for b in check(protocol, docs) if b[0] == cid}
        got = [b for b in check(protocol, injected) if b[0] == cid and b[1] not in base]
        print(f'SELF-TEST: injected retired form for {cid} -> '
              f'{"FIRES" if got else "DOES NOT FIRE"}')
        fired += bool(got)
    # and a stale-anchor control: the record itself disappearing must fail, not pass
    stale = check(protocol.replace(rows()[0][1], 'REMOVED'), docs)
    print('SELF-TEST: protocol anchor removed -> %s' % ('FIRES' if stale else 'DOES NOT FIRE'))
    return 0 if (not live and fired == len(probes) and stale) else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    protocol = open(PROTOCOL, encoding='utf-8').read()
    docs = delivered()
    bad = check(protocol, docs, verbose='--verbose' in sys.argv)
    print(f'protocol reconciliation: {len(rows())} recorded verdict(s) checked against '
          f'{len(docs)} delivered document(s)')
    for cid, msg in bad:
        print(f'  CONTRADICTION [{cid}]: {msg}')
    if bad:
        print(f'PROTOCOL RECONCILIATION GATE FAIL: {len(bad)} contradiction(s) between the paper '
              'and the protocol record (R45-6)')
        return 1
    print('PROTOCOL RECONCILIATION GATE PASS: no delivered sentence contradicts a recorded verdict.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
