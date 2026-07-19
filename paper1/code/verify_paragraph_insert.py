#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize-compare gate for the 4-hand-written-paragraph insertion (item-12).

PURPOSE. Prove that a paragraph inserted into paper/main.tex is the PARAGRAPH_DRAFTS.md
draft verbatim, modified by ONLY the three allowed transforms. The check is not "a human
looked and thinks nothing changed": the script re-derives the expected LaTeX from the draft
by applying the whitelist, then diffs it against the block actually inserted. Any difference
outside the whitelist is a non-zero count and fails the gate.

SOLE SOURCE. The draft is read from results/../results? no -- from PARAGRAPH_DRAFTS.md, the
one approved source. The inserted block is read from paper/main.tex between its \subsection
header (or explicit start anchor) and the next \subsection/\section.

======================================================================================
WHITELIST -- the ONLY transforms permitted between draft prose and inserted LaTeX.
A difference is "allowed" iff it is produced by one of these; everything else counts.
  T1  placeholder -> \ref/\eqref/\cite resolution. Declared per paragraph as explicit
      (draft_substring -> inserted_substring) pairs in PARAS[n]['subs']. Same-token
      placeholders that resolve differently (e.g. two \S\ref{sec:method}) are
      disambiguated by including surrounding context in the pair.
  T2  LaTeX-ification: escaping of text-mode special chars the draft did not carry.
      Handled transparently by _canon(): \_ \% \& \# are canonicalised to _ % & # on
      BOTH sides before the diff, so escaping a filename underscore is not a diff. Any
      further markup transform is declared as a (draft -> inserted) pair in 'subs'.
  T3  footnote renumber/inline: markdown "[^k]" marker + "[^k]: <def>" block -> LaTeX
      "\footnote{<def>}" at the marker. Handled structurally by _inline_footnotes():
      the <def> text itself is compared (it is draft content), only the wrapping differs.

RULING-AUTHORISED ADAPTATIONS (per paragraph, in 'rulings'): changes beyond the three
mechanical transforms that a supervisor ruling explicitly authorised (e.g. B2: the
[^cliff] cross-ref to a cut figure is redirected to fig:bler and its wording adapted to
that figure). Each is an explicit (draft -> inserted, ruling_id) triple, applied like a
sub but REPORTED SEPARATELY so the audit trail shows exactly which non-mechanical edits
were made and under which ruling. The gate still requires 0 residual diffs after these.
EXCLUDED SCAFFOLDING (disclosed in the commit, NOT gated): the \subsection{<title>} and
\label{<sec>} that give a Discussion paragraph a home + a cross-ref anchor. These are not
draft prose; the gate compares only the prose body + footnote content.
======================================================================================

Exit 0 and prints "GATE PASS (para N): 0 non-whitelist diffs" iff the normalized expected
== normalized actual. Otherwise prints the unified diff of the non-whitelist residue and
exits 1.
"""
import os
import re
import sys
import difflib

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
DRAFTS = os.path.join(P1, 'results/PARAGRAPH_DRAFTS.md')
TEX = os.path.join(P1, 'paper/main.tex')

# ---- per-paragraph config -----------------------------------------------------------
# body_first / body_last : unique substrings bounding the draft prose (footnote defs excluded).
# start_anchor           : substring on the first line of the inserted block in main.tex
#                          (the \subsection scaffolding line is skipped -- gate starts at prose).
# next_boundary          : regex that ends the inserted block (next sectioning command).
# subs                   : ordered list of (draft_text -> inserted_text) whitelist pairs (T1/T2).
PARAS = {
    1: dict(
        body_first="Among the feature-message candidates we also expose",
        body_last="earns no more than a marginal share is itself a finding.",
        start_anchor="Among the feature-message candidates we also expose",
        next_boundary=r"\\(subsection|section)\{",
        subs=[
            # T1: [^pay] Eq.(7) (payload) and Eq.(11) (coded bits) both resolve to eq:payload,
            # which states both the payload values and the 3.96 coded-bit derivation in one place.
            ("(Eq.~(7))", "(Eq.~\\eqref{eq:payload})"),
            ("(Eq.~(11))", "(Eq.~\\eqref{eq:payload})"),
        ],
        rulings=[
            # B2 (supervisor ruling): the [^cliff] cross-ref pointed to fig:channel_codec_ap,
            # a 9-panel AP figure cut in figure consolidation. Redirect to fig:bler (the present
            # codec-cliff BLER figure) and adapt the wording from an AP-grid statement to what
            # fig:bler actually shows (256-QAM BLER curve to the right of the 16-QAM curve).
            ("Fig.~\\ref{fig:channel_codec_ap}'s coarse grid renders this cliff as the 16$\\to$20 dB AP transition.",
             "Fig.~\\ref{fig:bler} plots this cliff directly, with the 256-QAM BLER curve sitting to the right of the 16-QAM curve.",
             "B2"),
        ],
    ),
    3: dict(
        body_first="A concurrent line of work pushes semantic communication",
        body_last="on an undeliverable feature message.",
        start_anchor="A concurrent line of work pushes semantic communication",
        next_boundary=r"\\(subsection|section)\{",
        subs=[],       # #3 carries no placeholders: \cite{gan2025cods} resolves via the bib
                       # entry added in the infra commit; \method{}/\emph{} are existing macros.
        rulings=[],
    ),
    2: dict(
        body_first="Collaboration is not unconditionally beneficial",
        body_last="without any change to the two-bit message format.",
        start_anchor="Collaboration is not unconditionally beneficial",
        next_boundary=r"\\(subsection|section)\{",
        subs=[
            # T1: the C256-analysis cross-ref resolves to Message Candidates; the OTHER
            # \S\ref{sec:method} (the 0.999 mask) stays sec:method -> not listed (unchanged).
            ("identity and CSV as the C256 analysis (\\S\\ref{sec:method})",
             "identity and CSV as the C256 analysis (\\S\\ref{sec:candidates})"),
        ],
    ),
}


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _draft_section(md, n):
    """Return the raw text of the '## N.' section of PARAGRAPH_DRAFTS.md."""
    m = re.search(r'^## %d\.' % n, md, re.M)
    if not m:
        sys.exit('draft section ## %d. not found' % n)
    nxt = re.search(r'^## \d+\.', md[m.end():], re.M)
    return md[m.start(): m.end() + nxt.start()] if nxt else md[m.start():]


def _extract_body_and_footnotes(section, cfg):
    """Split a draft section into (body_prose, {fnkey: fndef}) using the anchors."""
    i = section.index(cfg['body_first'])
    j = section.index(cfg['body_last']) + len(cfg['body_last'])
    body = section[i:j]
    fns = {}
    for fm in re.finditer(r'^\[\^([A-Za-z0-9]+)\]:\s*(.*?)(?=^\[\^|\nWord count|\Z)',
                          section, re.M | re.S):
        fns[fm.group(1)] = ' '.join(fm.group(2).split())
    return body, fns


def _inline_footnotes(body, fns):
    """T3: replace each [^k] marker with \footnote{<def_k>}; drop the marker syntax."""
    def repl(mm):
        k = mm.group(1)
        if k not in fns:
            sys.exit('footnote [^%s] used in body but no [^%s]: def found' % (k, k))
        return r'\footnote{%s}' % fns[k]
    return re.sub(r'\[\^([A-Za-z0-9]+)\]', repl, body)


def _apply_subs(text, subs):
    for a, b in subs:
        if a not in text:
            sys.exit('whitelist pair source not found in draft:\n  %r' % a)
        text = text.replace(a, b)
    return text


def _apply_rulings(text, rulings):
    for a, b, tag in rulings:
        if a not in text:
            sys.exit('ruling %s: source not found in draft:\n  %r' % (tag, a))
        text = text.replace(a, b)
    return text


def _norm_ws(text):
    return ' '.join(text.split())


def _canon(text):
    """T2: canonicalise text-mode LaTeX escapes so escaping is transparent to the diff."""
    for esc, raw in ((r'\_', '_'), (r'\%', '%'), (r'\&', '&'), (r'\#', '#')):
        text = text.replace(esc, raw)
    return text


def _inserted_block(tex, cfg):
    i = tex.index(cfg['start_anchor'])
    rest = tex[i:]
    b = re.search(cfg['next_boundary'], rest)
    block = rest[:b.start()] if b else rest
    return block.strip()


def gate(n):
    cfg = PARAS[n]
    md = _read(DRAFTS)
    section = _draft_section(md, n)
    body, fns = _extract_body_and_footnotes(section, cfg)
    # forward-transform the draft through the whitelist ONLY:
    expected = _inline_footnotes(body, fns)                        # T3
    expected = _apply_subs(expected, cfg['subs'])                  # T1 (+ declared T2)
    expected = _apply_rulings(expected, cfg.get('rulings', []))    # ruling-authorised
    actual = _inserted_block(_read(TEX), cfg)

    exp_n, act_n = _canon(_norm_ws(expected)), _canon(_norm_ws(actual))  # T2 escapes
    if exp_n == act_n:
        print('GATE PASS (para %d): 0 non-whitelist diffs' % n)
        print('  draft body chars=%d  footnotes=%d  inserted chars=%d'
              % (len(body), len(fns), len(actual)))
        print('  whitelist subs (T1/T2)=%d  ruling-authorised=%s'
              % (len(cfg['subs']), [r[2] for r in cfg.get('rulings', [])] or 0))
        return 0
    print('GATE FAIL (para %d): non-whitelist difference' % n)
    diff = difflib.unified_diff(exp_n.split(), act_n.split(),
                                'expected(draft+whitelist)', 'actual(main.tex)', lineterm='')
    print('\n'.join(diff))
    return 1


if __name__ == '__main__':
    ns = [int(x) for x in sys.argv[1:]] or sorted(PARAS)
    rc = 0
    for n in ns:
        rc |= gate(n)
    sys.exit(rc)
