#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R36 A-3 — the provisional Where2comm validate sweep may not reach any reported result.

Protocol: Where2comm thresholds were selected on Validate and remained FROZEN. That historical sweep
predates the deterministic pipeline (V2-R16), so it is kept **only as a tuning record**. The Test and
Culver-City products were regenerated deterministically; the validate sweep was not, and it must not
appear in the manuscript, the supplementary, any figure, or any results comparison.

Why a gate and not a note: "we know not to cite it" is intent, and this repository judges capability
(`docs/gate_design_principles.md` rule 1). The provisional files are still on disk, still loadable,
and still look exactly like the deterministic ones.

  python tests/test_provisional_exclusion.py
  python tests/test_provisional_exclusion.py --self-test
"""
from __future__ import annotations
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the provisional artefacts, by name
PROVISIONAL = re.compile(r'validate_thr[\d.]+\.(npz|json)|provisional_prefix_v2r16')
# where a reported number may live
REPORTED = ('paper/archive/manuscript_frozen.tex',
            'paper/archive/supplementary_frozen.tex')


def scan(targets=REPORTED, root=None):
    root = root or ROOT
    bad = []
    for rel in targets:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
            if PROVISIONAL.search(line):
                bad.append(f'{rel}:{i}: cites a provisional Where2comm validate artefact -- '
                           f'{line.strip()[:80]}')
    return bad


def scan_generators(root=None):
    """A generator that READS a provisional file can put its number into a delivered table."""
    root = root or ROOT
    bad = []
    files = subprocess.check_output(['git', '-C', root, 'ls-files'], text=True).split()
    for rel in [f for f in files if f.endswith('.py') and f.startswith(('tools/', 'projects/'))]:
        if os.path.basename(rel) == os.path.basename(__file__):
            continue
        try:
            src = open(os.path.join(root, rel), encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            code = line.split('#')[0]
            if PROVISIONAL.search(code):
                bad.append(f'{rel}:{i}: reads a provisional Where2comm validate artefact')
    return bad


def self_test():
    import tempfile
    ok = True
    base = scan() + scan_generators()
    print(f'  baseline: {len(base)} finding(s)' + (' -- clean' if not base else ''))
    if base:
        for b in base:
            print('    ' + b)
        return 1
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, 'paper'))
        open(os.path.join(d, 'paper', 'main.tex'), 'w').write(
            'Table~2 uses data/where2comm_v2/validate_thr0.02.npz for the comparison.\n')
        f = scan(('paper/main.tex',), root=d)
        print(f'  {"FIRES  " if f else "SILENT "}  the manuscript cites a provisional artefact')
        ok &= bool(f)
        open(os.path.join(d, 'paper', 'main.tex'), 'w').write(
            'Regenerated deterministically; see data/where2comm_v2/test_thr0.02.npz.\n')
        f2 = scan(('paper/main.tex',), root=d)
        print(f'  {"quiet  " if not f2 else "FIRES  "}  it cites a DETERMINISTIC test artefact '
              f'(must NOT fire)')
        ok &= not f2
    print('PROVISIONAL EXCLUSION SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    bad = scan() + scan_generators()
    print(f'provisional exclusion: {len(REPORTED)} delivered file(s) + every tools/ and projects/ '
          f'generator scanned')
    if bad:
        print('\nPROVISIONAL EXCLUSION GATE FAIL:')
        for b in bad:
            print('  ' + b)
        return 1
    print('PROVISIONAL EXCLUSION GATE PASS: the pre-deterministic Where2comm validate sweep reaches '
          'no delivered file and no generator.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
