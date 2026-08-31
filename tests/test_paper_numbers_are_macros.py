#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R48 B — every experimental RESULT in the delivered manuscript comes from a macro.

**What this locks (B-1):** result numbers must be emitted by `tools/build_v2_paper_numbers.py`,
either as a macro or inside a generated table body. **What it does not lock:** LaTeX containing
digits. Section numbers, standard names, metric thresholds, protocol definitions and registered
constants are legitimate literals and are listed in `tests/paper_literal_registry.md`.

Why it exists, precisely: the 4-page results brief carried five hand-typed numbers -- `56.2%`,
`0.01556`, `0.0048`, `0.534`, `0.152` -- in the one paragraph that explains why the feature action
is never selected, the paragraph three people had re-read. **Re-reading checks the meaning, not the
provenance.** Only a machine checks provenance.

Three things are checked:

  1. every numeric literal in the delivered text is a macro reference or a registered exception;
  2. every derived-claim phrase ("x-fold", "orders of magnitude", "percentage points", ...) has a
     macro within reach, so the phrase cannot drift from the arithmetic it claims;
  3. the int8 audit subsample (A-4) is never described as the full split.

Generated files are NOT literal-scanned (B-5): `generated_numbers.tex` and `tables/tbl_*.tex` are
verified by their generator's `--check`, which is a stronger guarantee than literal binding.

  python tests/test_paper_numbers_are_macros.py [--self-test]
"""
from __future__ import annotations
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ('paper/main.tex', 'paper/supplementary.tex')
REGISTRY = os.path.join(ROOT, 'tests', 'paper_literal_registry.md')

NUM = re.compile(r'(?<![\\A-Za-z0-9.])\d[\d,]*(?:\.\d+)?')
# derived claims: a comparative statement whose value is computed, so it must sit beside a macro
DERIVED = re.compile(r'\\times|[0-9]\s*-fold\b|\bfold reduction\b|orders? of magnitude\b'
                     r'|percentage points?\b|\bfactor of\b')
GENERATED = os.path.join(ROOT, 'paper', 'tables', 'generated_numbers.tex')


def generated_macros():
    """The macro names the generator actually emits.

    An earlier draft accepted ANY control sequence as evidence that a derived claim was backed by
    a number. `\\section` then counted, and the check passed on a sentence with no number behind it
    at all -- a gate that cannot fail.
    """
    if not os.path.exists(GENERATED):
        return set()
    return set(re.findall(r'\\newcommand\{\\([A-Za-z]+)\}', open(GENERATED, encoding='utf-8').read()))
# A-4: the int8 figure is a 220-frame audit subsample and may not be read as the full split.
INT8_BAD = re.compile(r'1,?980|full validate|whole validate|all \d[\d,]* frames'
                      r'|entire development split', re.I)


def _blank(m):
    """Replace a match with spaces of the same length, so offsets still map to the source.

    A strip() that shortens the text makes every reported line number wrong, which turns a real
    finding into an unfindable one.
    """
    return re.sub(r'[^\n]', ' ', m.group(0))


def strip(tex):
    """Blank out comments and the constructs where a digit is never a result.

    ORDER MATTERS: display-maths blocks are removed before the environment markers are, or the
    markers vanish first and the block regex no longer has anything to anchor on.
    """
    tex = re.sub(r'(?m)(?<!\\)%.*$', _blank, tex)
    # display maths, including the cases/aligned bodies inside it
    tex = re.sub(r'(?s)\\begin\{(equation\*?|align\*?|gather\*?)\}.*?\\end\{\1\}', _blank, tex)
    tex = re.sub(r'\$[^$]*\$', _blank, tex)                      # inline maths
    # the running head / title block
    tex = re.sub(r'(?s)\\markboth.*?\\maketitle', _blank, tex)
    # table and float scaffolding: column counts, rule spans, column specifications, lengths
    tex = re.sub(r'\\multicolumn\{[^}]*\}\{[^}]*\}', _blank, tex)
    tex = re.sub(r'\\(?:cmidrule|cline)(?:\([^)]*\))?\{[^}]*\}', _blank, tex)
    tex = re.sub(r'\\begin\{(?:tabular|array|longtable)\}(?:\[[^\]]*\])?\{[^}]*\}', _blank, tex)
    tex = re.sub(r'\\setlength\{[^}]*\}\{[^}]*\}', _blank, tex)
    # preamble, cross-references, labels, citations, includes and inputs
    tex = re.sub(r'\\(?:label|ref|eqref|cite|includegraphics|input|documentclass|usepackage|'
                 r'graphicspath|newcommand|providecommand|renewcommand|bibliography\w*|'
                 r'markboth|title|author|texttt|url)'
                 r'(?:\[[^\]]*\])?(?:\{[^{}]*\})?', _blank, tex)
    # environment markers themselves
    tex = re.sub(r'\\(?:begin|end)\{[^}]*\}', _blank, tex)
    return tex


def patterns():
    pats = []
    for line in open(REGISTRY, encoding='utf-8'):
        if line.startswith('RX '):
            pats.append(re.compile(line[3:].strip()))
    return pats


def scan(texts=None):
    """texts: {relpath: source}. Returns a list of findings."""
    if texts is None:
        texts = {}
        for rel in TARGETS:
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                return [(rel, 0, '', 'the delivered document does not exist')]
            texts[rel] = open(p, encoding='utf-8').read()
    pats = patterns()
    gen = generated_macros()
    bad = []
    for rel, raw in texts.items():
        body = strip(raw)
        # A pattern excuses a literal only if its own match COVERS that literal's start. Searching
        # a +/-60 character window instead let any nearby registered pattern excuse an unrelated
        # number: "AP@0.5 of 0.86994" was excused by the 0.5 metric-threshold row, so a hand-typed
        # AP passed the gate. That is the failure this whole file exists to catch.
        covered = []
        for p_ in pats:
            covered += [(mm.start(), max(mm.end(), mm.start() + 1)) for mm in p_.finditer(body)]
        for m in NUM.finditer(body):
            lit = m.group(0)
            if any(a <= m.start() < b for a, b in covered):
                continue
            line = raw[:m.start()].count('\n') + 1
            snippet = re.sub(r'\s+', ' ', raw[max(0, m.start() - 45):m.end() + 45]).strip()
            bad.append((rel, line, lit,
                        'unregistered numeric literal -- a result must come from a macro; '
                        'context: ...%s...' % snippet))
        for m in DERIVED.finditer(body):
            window = body[max(0, m.start() - 200):m.end() + 120]
            if not any('\\' + name in window for name in gen):
                bad.append((rel, 0, m.group(0),
                            'derived claim with no macro within reach -- the phrase can drift '
                            'from the arithmetic'))
        for m in re.finditer(r'IntEightFrames', body):
            window = body[max(0, m.start() - 400):m.end() + 400]
            hit = INT8_BAD.search(window)
            if hit:
                bad.append((rel, 0, hit.group(0),
                            'the int8 figure is a 220-frame audit subsample and is described here '
                            'as the full split (V2-R48 A-4)'))
    return bad


def self_test():
    ok = True
    base = scan()
    print('  baseline: %d finding(s)%s' % (len(base), ' -- clean' if not base else ''))
    for b in base[:20]:
        print('    %s:%s  %r  %s' % b)
    ok &= not base
    src = {rel: open(os.path.join(ROOT, rel), encoding='utf-8').read() for rel in TARGETS}

    inj = dict(src)
    inj['paper/main.tex'] += '\nOn Test it reaches AP@0.5 of 0.86994 under clean delivery.\n'
    f = scan(inj)
    print('  %s  a hand-typed AP value (0.86994)' % ('FIRES ' if f else 'SILENT'))
    ok &= bool(f)

    inj = dict(src)
    inj['paper/main.tex'] += '\nThe cue vector is 23-dimensional by construction.\n'
    f = scan(inj)
    extra = len(f) - len(base)
    print('  %s  the phrase "23-dimensional" (must NOT fire)' % ('quiet ' if extra == 0 else 'FIRES'))
    ok &= extra == 0

    inj = dict(src)
    inj['paper/main.tex'] += ('\n\\section{Unsupported}\nThe saving is two orders of magnitude, '
                              'as anyone can see.\n')
    f = scan(inj)
    fired = any('derived claim' in b[3] for b in f)
    print('  %s  "two orders of magnitude" with no macro in reach' % ('FIRES ' if fired else 'SILENT'))
    ok &= fired

    inj = dict(src)
    inj['paper/main.tex'] += ('\n\\section{Bad int8}\nThe int8 audit covers \\IntEightFrames{} '
                              'frames, i.e. all 1,980 frames of validate.\n')
    f = scan(inj)
    fired = any('audit subsample' in b[3] for b in f)
    print('  %s  the int8 subsample described as the full split' % ('FIRES ' if fired else 'SILENT'))
    ok &= fired

    print('PAPER-NUMBERS SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    bad = scan()
    print('paper numbers are macros: %d delivered document(s) scanned, %d registered exception '
          'pattern(s)' % (len(TARGETS), len(patterns())))
    if bad:
        print('\nPAPER-NUMBERS GATE FAIL:')
        for rel, line, lit, why in bad:
            print('  %s:%s  %r  -- %s' % (rel, line, lit, why))
        return 1
    print('PAPER-NUMBERS GATE PASS: every result number comes from a macro or a generated table.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
