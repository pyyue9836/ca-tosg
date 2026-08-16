#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate: every input artefact the pipeline consumes is registered in docs/assumptions_ledger.md.

The P0 erratum was not a coding error — each half of the pipeline was internally consistent. The
mismatch lived in the *join* between what an artefact physically is (fusion over every collaborator)
and what the pipeline charges for it (one message), and nothing in the repository recorded that
join, so nothing could check it.

This gate makes the record mandatory: an input-artefact reference in pipeline code that no ledger
row covers is a failure. It cannot verify that a registered row is *true* — that is a human
judgement, which is exactly why the row has to be written down and read.

    python tests/test_assumptions_ledger.py [--self-test]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, 'docs', 'assumptions_ledger.md')

# directories whose code consumes input artefacts
SCAN_DIRS = ('projects/ca_tosg/datasets', 'projects/ca_tosg/evaluation', 'tools', 'baselines')

# what counts as an input-artefact reference in source: a cache, a per-frame dataset, or the
# channel table. Outputs (results/*.csv the code writes) are covered by results/README.md instead.
ARTEFACT = re.compile(r"""['"]([^'"]*?(?:%s|\{[a-z_]+\})?[\w{}%%.\-]*\.(?:npz|csv))['"]"""
                      % '', re.X)
INPUT_HINT = re.compile(r'(npz|dataset_|bler_|p2_grid_)')
# references that are outputs or documentation, not inputs
IGNORE = re.compile(r'(results/|docs/|tests/|\.tmp|selftest|forced-fresh)')


def normalise(lit):
    """Collapse the many ways a split placeholder is written into one form.

    Source code writes the same artefact as `comp_%s.npz`, `comp_{split}.npz`, `comp_{SPLIT}.npz`
    and f-string variants. Matching them literally made the gate report 40 "unregistered" artefacts
    that were all registered under one name -- a gate nobody can act on is a gate nobody runs.
    """
    lit = re.sub(r'\{[^}]*\}', '{split}', lit)
    lit = re.sub(r'%[sd]', '{split}', lit)
    return lit


def registered_patterns():
    """Registered artefact tokens from the ledger's first column, normalised the same way the
    source literals are so that `{GS}/comp_{sp}.npz` and `gs_rerun/comp_{split}.npz` compare equal.

    Both the full path and the basename are registered: code refers to the same cache through a
    module constant (`{GS}/comp_{sp}.npz`) that the literal scan cannot resolve.
    """
    pats = []
    for line in open(LEDGER, encoding='utf-8'):
        if not line.startswith('|'):
            continue
        cell = line.split('|')[1].strip()
        for tok in re.findall(r'`([^`]+)`', cell):
            for form in (normalise(tok), os.path.basename(normalise(tok))):
                # a basename of `*.npz` would register EVERY npz -- the self-test caught exactly
                # that, with an invented cache passing the gate. A pattern must carry at least
                # three literal characters of its own.
                stem = os.path.splitext(form)[0]          # the extension is not identifying:
                literal = re.sub(r'[*…]|\{split\}', '', stem)   # "*.npz" would register every cache
                if len(re.sub(r'[^\w]', '', literal)) < 3:
                    continue
                rx = re.escape(form).replace(r'\*', '.*').replace('…', '.*')
                # a registered {split} matches both the placeholder and a concrete split name
                rx = rx.replace(r'\{split\}', r'[\w,.{}]+')
                pats.append(re.compile(rx + '$'))
    return pats


def scan_sources():
    """[(relpath, lineno, literal)] input-artefact references found in pipeline code."""
    out = []
    for d in SCAN_DIRS:
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, d)):
            if '__pycache__' in dirpath:
                continue
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, ROOT)
                for i, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
                    if line.lstrip().startswith('#'):
                        continue
                    for lit in re.findall(r"['\"]([^'\"]*\.(?:npz|csv))['\"]", line):
                        # a literal with whitespace is a log line, not a path
                        if any(c.isspace() for c in lit):
                            continue
                        if INPUT_HINT.search(lit) and not IGNORE.search(lit):
                            out.append((rel, i, lit))
    return out


def covered(lit, pats):
    lit = normalise(lit)
    base = os.path.basename(lit)
    return any(p.search(lit) or p.search(base) for p in pats)


def main() -> int:
    if not os.path.exists(LEDGER):
        print('FAIL: docs/assumptions_ledger.md is missing')
        return 1
    pats = registered_patterns()
    if not pats:
        print('FAIL: the ledger registers no artefact patterns -- the gate would be inert')
        return 1
    refs = scan_sources()
    unregistered = sorted({(r[2], r[0]) for r in refs if not covered(r[2], pats)})
    print(f'assumptions ledger: {len(pats)} registered patterns, '
          f'{len({r[2] for r in refs})} distinct input-artefact literals in pipeline code')

    if '--self-test' in sys.argv:
        fake = 'gs_rerun/unregistered_new_cache_{split}.npz'
        fired = not covered(fake, pats)
        print(f'  self-test: an unregistered artefact is flagged: '
              f'{"FIRES" if fired else "DOES NOT FIRE"}')
        known = 'gs_rerun/ego_validate.npz'
        quiet = covered(known, pats)
        print(f'  self-test: a registered artefact is accepted:   {"OK" if quiet else "BROKEN"}')
        print('SELF-TEST ' + ('PASS' if fired and quiet else 'FAIL'))
        return 0 if (fired and quiet) else 1

    for lit, where in unregistered:
        print(f'  UNREGISTERED  {lit}   ({where})')
    if unregistered:
        print(f'ASSUMPTIONS LEDGER GATE FAIL: {len(unregistered)} artefact(s) used but not '
              'registered. Add a row (semantics / accounting / status) before consuming them.')
        return 1
    print('ASSUMPTIONS LEDGER GATE PASS: every consumed input artefact is registered.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
