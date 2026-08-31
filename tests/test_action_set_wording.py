#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate: every sentence that names the DEPLOYED ACTION SET must enumerate it completely.

Twice now the paper has described the deployed set without $E$ -- once as a two-element class set
`{L, C16}` (a footnote in sec:candidates, retired in R23-4) and once in the Conclusion, which listed
"a compact object-level message $L$ or a compressed feature-level message" and stopped (R23-5). Both
survived every existing gate, because a missing element is not a wrong number and leaves no
fingerprint to grep for.

The rule this gate enforces is positive, not a blacklist: a sentence that speaks about the deployed
action set (or the classifier's class set) must either name all three actions, or be a statement
about what is EXCLUDED from the set, which by construction does not enumerate it.

    python tests/test_action_set_wording.py [--self-test]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, 'paper', 'archive', 'manuscript_frozen.tex')

# a sentence is "about the deployed set" if it says so in one of these ways
TRIGGER = re.compile(r'(deployed (semantic )?action set|deployed classifier[^.]{0,40}class set|'
                     r"classifier's class set|deployed action set)", re.I)
# ... unless it is a statement about exclusion from the set (those legitimately name only C256)
EXCLUSION = re.compile(r'(exclu(ded|sion) (from|of)|not (in|included in) the deployed|'
                       r'not a deployed action|physical-layer comparator)', re.I)
# the three actions, in any of the forms the paper uses
HAS_E = re.compile(r'(\$E\$|\\\{E,\s*L,\s*F\\\}|\bego-only\b)')
HAS_L = re.compile(r'(\$L\$|\\\{E,\s*L,\s*F\\\}|\bobject-level\b)')
HAS_F = re.compile(r'(\$F\$|\\\{E,\s*L,\s*F\\\}|\bfeature-level\b|16-QAM)')


def sentences(text):
    """Split on sentence enders that are not part of a LaTeX macro, keeping 1-based line numbers."""
    out, buf, line = [], [], 1
    start = 1
    for ch in text:
        buf.append(ch)
        if ch == '\n':
            line += 1
        if ch in '.!?' and len(buf) > 1:
            out.append((start, ''.join(buf)))
            buf, start = [], line
    if buf:
        out.append((start, ''.join(buf)))
    return out


def violations(text):
    bad = []
    for ln, s in sentences(text):
        if not TRIGGER.search(s) or EXCLUSION.search(s):
            continue
        missing = [n for n, rx in (('E', HAS_E), ('L', HAS_L), ('F', HAS_F)) if not rx.search(s)]
        if missing:
            bad.append((ln, ''.join(missing), ' '.join(s.split())[:150]))
    return bad


def delivered():
    """main.tex plus supplementary.tex (R40: the supplementary is delivered text)."""
    parts = [open(TEX, encoding='utf-8').read()]
    supp = os.path.join(os.path.dirname(TEX), 'supplementary_frozen.tex')
    if os.path.exists(supp):
        parts.append(open(supp, encoding='utf-8').read())
    return '\n'.join(parts)


def main():
    text = delivered()
    if '--self-test' in sys.argv:
        # the exact R23-5 regression: the Conclusion sentence with E removed again
        probe = (r'The selector outputs a per-frame communication mode from the deployed action '
                 r'set---a compact object-level message $L$ or a compressed feature-level message '
                 r'under 16-QAM coding.')
        fires = bool(violations(probe))
        print('SELF-TEST: retired Conclusion form (no $E$) -> %s'
              % ('FIRES' if fires else 'DOES NOT FIRE'))
        # and a positive control that must NOT fire
        ok = not violations(r'The ego vehicle selects one mode from the deployed action set '
                            r'$\mathcal{S}=\{E,L,F\}$.')
        print('SELF-TEST: complete enumeration -> %s' % ('silent' if ok else 'FALSE POSITIVE'))
        return 0 if (fires and ok) else 1
    bad = violations(text)
    n = len(sentences(text))
    print(f'action-set wording: {n} sentences scanned in the archived manuscript + supplementary')
    for ln, missing, s in bad:
        print(f'  main.tex:~{ln}: deployed action set named without {missing}: {s}')
    if bad:
        print(f'ACTION-SET GATE FAIL: {len(bad)} sentence(s) describe the deployed action set '
              'without enumerating it (R23-5)')
        return 1
    print('ACTION-SET GATE PASS: every deployed-action-set sentence names E, L and F.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
