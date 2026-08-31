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
# V2-R47 B-2: the ruled wording is checked in the ONE official manuscript. The archived
# 4-page brief keeps its own check -- it is frozen, so this can only ever confirm it, but a
# claim that was ruled once is checked wherever it is delivered.
TEX = os.path.join(ROOT, 'paper', 'main.tex')
BRIEF = os.path.join(ROOT, 'paper', 'archive', 'results_brief.tex')

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
            return ['paper/main.tex does not exist -- the official manuscript is the '
                    'delivered text this gate judges']
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


def _inject(src, phrase, replacement, expect=1):
    """Replace `phrase` in the SOURCE, tolerating the line wrapping LaTeX puts in it.

    V2-R48: a plain str.replace() silently did nothing when the phrase happened to be wrapped
    across two lines, so the injection tested nothing and the self-test reported SILENT -- a
    self-test that cannot fail, inside the gate whose whole purpose is to fail on a fluent edit.
    """
    pat = r'\s+'.join(re.escape(w) for w in phrase.split())
    out, n = re.subn(pat, replacement, src)
    assert n == expect, ('injection matched %d times, not %d: %r' % (n, expect, phrase[:50]))
    return out


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
    inj = _inject(src, 'without statistically establishing accuracy preservation',
                  'while preserving accuracy')
    f = check(inj)
    print(f'  {"FIRES  " if f else "SILENT "}  the qualifier is smoothed away ("while preserving '
          f'accuracy")')
    ok &= bool(f)
    inj2 = _inject(src, 'excluded from bit-level budget-matched claims',
                   'compared at a matched budget')
    f2 = check(inj2)
    print(f'  {"FIRES  " if f2 else "SILENT "}  Where2comm given a matched-budget reading')
    ok &= bool(f2)
    # the macro appears in the abstract, the results and the conclusion; all three go
    inj3 = _inject(src, '\\TestSaving', 'ninety-nine', expect=3)
    f3 = check(inj3)
    print(f'  {"quiet  " if not f3 else "FIRES  "}  a macro replaced by prose (content words '
          f'intact; must NOT fire)')
    ok &= not f3
    print('CONCLUSION FIDELITY SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    # V2-R47 B-2: both delivered texts. The brief is frozen, so its half can only confirm --
    # but a gate that stops looking at a document because it is frozen is a gate that would
    # not notice the freeze being broken.
    bad = ['[official] ' + b for b in check()]
    bad += ['[archived brief] ' + b
            for b in check(open(BRIEF, encoding='utf-8').read())]
    print(f'conclusion fidelity: {len(CLAIMS)} ruled claims checked in paper/main.tex '
          f'and in the archived brief')
    if bad:
        print('\nCONCLUSION FIDELITY GATE FAIL:')
        for b in bad:
            print('  ' + b)
        return 1
    print('CONCLUSION FIDELITY GATE PASS: every ruled sentence survived transcription intact.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
