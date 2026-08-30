#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R42 B-1 — the conclusion sentences must survive transcription word for word.

Transcription is not rewriting. The failure mode this guards is not a typo but a *fluent* one: one
smoother subordinate clause and the non-inferiority qualifier is gone, and the sentence still reads
well, which is precisely why nobody catches it on a re-read.

Each entry below is a claim whose wording was fixed by ruling. The check is on CONTENT WORDS, so
LaTeX escaping and line wrapping are allowed to differ while the assertion may not.

  python tests/test_v2_conclusion_fidelity.py
  python tests/test_v2_conclusion_fidelity.py --self-test
"""
from __future__ import annotations
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, 'paper', 'v2_draft', 'main.tex')

# (label, phrases that MUST be present, phrases that must NOT be, anchor for the forbidden scope)
#
# The forbidden list is scoped to a WINDOW around the anchor, not to the whole document. "Msym" is a
# legitimate word in this paper -- it is CA-TOSG's payload unit -- and only becomes wrong beside
# Where2comm. A document-global ban would fire on the correct usage, which is failure mode 3.
CLAIMS = [
    ('abstract primary result',
     ['reduced realised communication payload by', 'on Test', 'on Culver-City',
      'preregistered scene-level non-inferiority criterion was not met on either split',
      'without statistically establishing accuracy preservation'],
     ['maintains accuracy', 'no loss of accuracy', 'at the same accuracy'], None),
    ('Where2comm exclusion',
     ['same data splits, field of view, ground truth and detection metrics',
      'native communication rate', 'floating-point selected features',
      'does not execute the locked', 'excluded from bit-level budget-matched claims'],
     ['matched budget', 'same budget', 'Msym'], 'Where2comm is included as'),
    ('criterion is on the bound',
     ['the bound is what it tests'], [], None),
    ('both halves together',
     ['Neither may be reported without the other'], [], None),
    ('rho_F explanation',
     ['is not an action that never helps', 'conditioning set',
      'no candidate could', 'not evidence that the feature action is worthless'], [], None),
    ('no learned-selector superiority',
     ['not a demonstration that\na learned selector beats simple rules', 'it does not'], [], None),
]


def norm(s):
    s = re.sub(r'\\[a-zA-Z]+\{?|\}|\$|\\\\|~|%', ' ', s)
    return re.sub(r'\s+', ' ', s)


def check(text=None):
    if text is None:
        if not os.path.exists(TEX):
            return ['paper/v2_draft/main.tex does not exist']
        text = open(TEX, encoding='utf-8').read()
    n = norm(text)
    bad = []
    for label, must, mustnot, anchor in CLAIMS:
        # scope the forbidden check to a window after the anchor, if one is given
        if anchor:
            i = n.find(norm(anchor).strip())
            scope = n[i:i + 1400] if i >= 0 else ''
        else:
            scope = n
        for m in must:
            if norm(m).strip() not in n:
                bad.append(f'{label}: LOST in transcription -- "{norm(m).strip()[:70]}"')
        for m in mustnot:
            if norm(m).strip() in scope:
                bad.append(f'{label}: FORBIDDEN phrasing present -- "{m}"')
    return bad


def self_test():
    base = check()
    print(f'  baseline: {len(base)} finding(s)' + (' -- clean' if not base else ''))
    for b in base:
        print('    ' + b)
    if base:
        return 1
    src = open(TEX, encoding='utf-8').read()
    ok = True
    # the exact failure this exists for: a fluent edit that drops the qualifier
    inj = src.replace('without statistically establishing accuracy preservation',
                      'while preserving accuracy')
    f = check(inj)
    print(f'  {"FIRES  " if f else "SILENT "}  the qualifier is smoothed away ("while preserving '
          f'accuracy")')
    ok &= bool(f)
    inj2 = src.replace('excluded from bit-level budget-matched claims',
                       'compared at a matched budget')
    f2 = check(inj2)
    print(f'  {"FIRES  " if f2 else "SILENT "}  Where2comm given a matched-budget reading')
    ok &= bool(f2)
    inj3 = src.replace('\\TestSaving', 'ninety-nine')
    f3 = check(inj3)
    print(f'  {"quiet  " if not f3 else "FIRES  "}  a macro replaced by prose (content words '
          f'intact; must NOT fire)')
    ok &= not f3
    print('CONCLUSION FIDELITY SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    bad = check()
    print(f'conclusion fidelity: {len(CLAIMS)} ruled claims checked in paper/v2_draft/main.tex')
    if bad:
        print('\nCONCLUSION FIDELITY GATE FAIL:')
        for b in bad:
            print('  ' + b)
        return 1
    print('CONCLUSION FIDELITY GATE PASS: every ruled sentence survived transcription intact.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
