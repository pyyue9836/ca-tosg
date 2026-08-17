#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize-compare gate for the 4-hand-written-paragraph insertion (item-12).

PURPOSE. Prove that a paragraph inserted into paper/main.tex is the paragraph_drafts.md
draft verbatim, modified by ONLY the three allowed transforms. The check is not "a human
looked and thinks nothing changed": the script re-derives the expected LaTeX from the draft
by applying the whitelist, then diffs it against the block actually inserted. Any difference
outside the whitelist is a non-zero count and fails the gate.

SOLE SOURCE. The draft is read from results/../results? no -- from paragraph_drafts.md, the
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
DRAFTS = os.path.join(P1, 'paper/paragraph_drafts.md')
TEX = os.path.join(P1, 'paper/main.tex')

# ---- per-paragraph config -----------------------------------------------------------
# body_first / body_last : unique substrings bounding the draft prose (footnote defs excluded).
# start_anchor           : substring on the first line of the inserted block in main.tex
#                          (the \subsection scaffolding line is skipped -- gate starts at prose).
# next_boundary          : regex that ends the inserted block (next sectioning command).
# subs                   : ordered list of (draft_text -> inserted_text) whitelist pairs (T1/T2).
PARAS = {
    1: dict(
        body_first="Of the two feature-level modes, the 256-QAM variant",
        body_last="earns no more than a marginal share is itself a finding.",
        start_anchor="Of the two feature-level modes, the 256-QAM variant",
        next_boundary=r"\\(subsection|section)\{",
        subs=[
            # T1: [^pay] Eq.(7) (payload) resolves to eq:payload, which states both the payload
            # values and the 3.96 coded-bit derivation in one place. (TG-4 removed the duplicate
            # second Eq reference that the draft carried as Eq.(11).)
            ("(Eq.~(7))", "(Eq.~\\eqref{eq:payload})"),
            # T1: R18-final removed the three pre-corrigendum C256 frame fractions and put the
            # qualitative physical-layer argument in their place, which cites the BLER figure. The
            # draft carries the placeholder; this is the declared resolution.
            ("Fig.~[fig:bler]", "Fig.~\\ref{fig:bler}"),
        ],
        rulings=[
            # B2 (supervisor ruling): the [^cliff] cross-ref pointed to fig:channel_codec_ap,
            # a 9-panel AP figure cut in figure consolidation. Redirect to fig:bler (the present
            # codec-cliff BLER figure) and adapt the wording from an AP-grid statement to what
            # fig:bler actually shows (256-QAM BLER curve to the right of the 16-QAM curve).
            ("Fig.~\\ref{fig:channel_codec_ap}'s coarse grid renders this cliff as the 16$\\to$20 dB AP transition.",
             "Fig.~\\ref{fig:bler} plots this cliff directly, with the 256-QAM BLER curve sitting to the right of the 16-QAM curve.",
             "B2"),
            # Q2 (supervisor ruling, 2026-08-02): reframe the paragraph's role from a "completeness
            # defence" for retaining C256 to the "exclusion basis" for it -- C256 is dominated by C16
            # and excluded from the now 2-element deployed action set S={L,C16} (Eq.~\ref{eq:action_set}).
            # Approved together with the S={L,C16} formalism change.
            ("We retain C256 for completeness of the granularity ladder spanned by the 2-bit request, yet it earns no operational role:",
             "As established above, $C_{256}$ is dominated by $C_{16}$ and is therefore excluded from the deployed action set $\\mathcal{S}$ (Eq.~\\eqref{eq:action_set}); it completes the granularity ladder addressable by the request field but earns no operational role:",
             "Q2"),
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
        inserted_body_last=("not a message-format one."),
        rulings=[
            # P5-7 item 10 (Peiyi, 2026-08-14): E is a DEPLOYED action, so the closing sentence
            # can no longer offer an ego-only action as future work.
            ("A remedy adds no signalling overhead: the `11' codeword of the 2-bit request is "
             "unused, so an explicit do-not-request (ego-only) action can be added without any "
             "change to the two-bit message format.",
             "No new signalling is needed to act on this: $E$ (ego-only, issue no request) is "
             "already a deployed action of $\\mathcal{S}$ with its own codepoint, so the remedy is "
             "a selection-policy question---the frozen selectors almost never choose it "
             "(Section~\\ref{sec:pareto})---not a message-format one.",
             'P5-7-10'),
            # P5-5 item 7 (Peiyi, 2026-08-14): the easy-stratum footnote quoted the retired
            # 200-realisation engine's selector. Recomputed under the frozen protocol
            # (results/sensitivity/difficulty_frozen.csv; test / B_max=0.20 / AWGN 16 dB).
            # Same stratum, same n=713, same Fixed-L baseline 0.9866 -- only the SELECTOR's
            # realised F1 moves, which is exactly the engine difference and nothing else.
            ("the selector's realised F1 is $0.9719$ vs the Fixed-$L$ baseline $0.9866$ -- a "
             "gain of $-0.0147$ (frame-level paired $95\\%$ CI $[-0.0179,-0.0115]$; $n=713$ "
             "frames). The selector requests $C_{16}$ on $635$ of these $713$ frames; on the "
             "remaining $78$, where it requests $L$, its output is frame-identical to "
             "Fixed-$L$, so the paired difference arises entirely on the $C_{16}$-request "
             "frames (verified programmatically from the per-frame account) -- the loss",
             # R18-final: re-derived under the single-collaborator convention, so the Fixed-L
             # baseline moves too (0.9866 -> 0.9796) -- the earlier ruling could hold it fixed
             # because only the engine had changed; the corrigendum changes the utilities.
             "the frozen selector's realised F1 at $B_{\\max}=0.20$ is $0.9749$ vs the "
             "Fixed-$L$ baseline $0.9796$ -- a gain of $-0.0047$ (frame-level paired $95\\%$ "
             "CI $[-0.0074,-0.0024]$; $n=713$ frames). The selector requests $F$ on $241$ of "
             "these $713$ frames; on the remaining $472$, where it requests $L$, its output is "
             "frame-identical to Fixed-$L$, so the paired difference arises entirely on the "
             "$F$-request frames -- the loss",
             'P5-5-7'),
        ],
    ),
}


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _draft_section(md, n):
    """Return the raw text of the '## N.' section of paragraph_drafts.md."""
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


def _norm_ws(text):
    return ' '.join(text.split())


def _apply_subs(text, subs):
    for a, b in subs:
        if a not in text:
            sys.exit('whitelist pair source not found in draft:\n  %r' % a)
        text = text.replace(a, b)
    return text


def _apply_rulings(text, rulings):
    """Apply the ruling-authorised rewrites.

    Matching is whitespace-normalised: the draft is hard-wrapped, so a ruling that spans a line
    break would otherwise fail to find its own source and the gate would abort with a confusing
    'source not found'. Normalisation is safe because the final comparison normalises anyway.
    """
    text = _norm_ws(text)
    for a, b, tag in rulings:
        a, b = _norm_ws(a), _norm_ws(b)
        if a not in text:
            sys.exit('ruling %s: source not found in draft:\n  %r' % (tag, a))
        text = text.replace(a, b)
    return text


def _canon(text):
    """T2: canonicalise text-mode LaTeX escapes so escaping is transparent to the diff."""
    for esc, raw in ((r'\_', '_'), (r'\%', '%'), (r'\&', '&'), (r'\#', '#')):
        text = text.replace(esc, raw)
    return text


def _inserted_block(tex, cfg):
    # Bound the inserted block by the draft's own last sentence (body_last), not by the next
    # sectioning command: a paragraph may be followed by relocated prose (e.g. TG-18 moved the
    # subsection's closing sentence to sit after paragraph #3) that is not part of the draft.
    i = tex.index(cfg['start_anchor'])
    rest = tex[i:]
    # When a ruling rewrites the paragraph's LAST sentence, the draft's body_last no longer exists
    # in main.tex. `inserted_body_last` names the replacement so the block is still bounded by a
    # sentence rather than by the next sectioning command.
    last = cfg.get('inserted_body_last', cfg['body_last'])
    if last not in rest:
        raise SystemExit(
            f'para bound not found in main.tex: {last[:60]!r}. If a ruling rewrote the closing '
            f'sentence, declare it in PARAS[n]["inserted_body_last"] and add the ruling.')
    j = rest.index(last) + len(last)
    return rest[:j].strip()


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
