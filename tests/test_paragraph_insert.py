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
        inserted_body_last="a denser constellation buys channel use at the cost of reach.",
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
            # R23-4 (supervisor ruling, 2026-08-17): the footnote described the deployed classifier
            # as a TWO-element class set {L, C16}. E is a deployed action, so the set is
            # S={E,L,F} and C256's status is exclusion, not membership of a smaller set.
            ("The deployed classifier's class set is $\\{L, \\mathrm{C16}\\}$",
             "The deployed classifier uses $\\mathcal{S}=\\{E,L,F\\}$; $C_{256}$ is excluded "
             "from the deployed action set",
             'R23-4'),
            # R28-1 (supervisor ruling, 2026-08-18): the three pre-corrigendum percentage families
            # in this paragraph are deleted, together with the footnote that explained them. They
            # were full-collaborator fractions sourced from the retired
            # results/sensitivity/c256_dominance_verify.csv (now in tests/retired_products.md).
            # The argument stands on the physical-layer ordering plus the structurally-zero
            # deployment count, which are convention-independent.
            (';\\footnote{Fractions rounded to 0.1 pp. All four come from one run of the dominance-verification procedure, which asserts $\\mathrm{frac\\_dominated}=\\mathrm{frac}(\\mathrm{comp}\\ge\\mathrm{ego}) +\\mathrm{frac}(\\mathrm{comp}<\\mathrm{ego}\\wedge b_{16}=b_{256})$ at the count level; displayed percentages may differ from the total by up to $0.1$~pp due to rounding.} the margin over $\\mathrm{frac}(\\mathrm{comp}\\ge\\mathrm{ego})=$ 99.0 / 94.2 / 99.1\\% is the 0.7 / 4.2 / 0.9\\% of frames where $\\mathrm{comp}<\\mathrm{ego}$ but $b_{16}=b_{256}$ -- both flatline, or both deliver at high SNR -- which tie rather than reverse.',
             ': wherever $b_{16}=b_{256}$ the two modes tie rather than reverse, and wherever $\\mathrm{comp}\\ge\\mathrm{ego}$ the sign of $(\\mathrm{comp}-\\mathrm{ego})(b_{16}-b_{256})$ makes C256 no better.',
             'R28-1a'),
            ("deployment account.} -- and even the oracle's payload-penalised frontier activates it at only 2.5 / 3.2 / 4.5\\% of frames. That a rate-matched, lower-channel-use action earns no more than a marginal share is itself a finding.",
             'deployment account.}. That a rate-matched, lower-channel-use action earns no operational role at all, on physical grounds that hold for any collaborator convention, is itself the finding.',
             'R28-1b'),
            # R30-3 (supervisor ruling, 2026-08-18): the exclusion is restated as SET DOMINATION
            # -- C16 dominates C256 wherever comp>=ego, E dominates every feature mode wherever
            # comp<ego, and the two cases are exhaustive -- so the 'reverses only in the harm
            # regime' concession is removed with the case analysis it belonged to.
            ('The exclusion of C256 from the deployed action set rests on that physical-layer ordering, which no collaborator convention can change: wherever $b_{16}=b_{256}$ the two modes tie rather than reverse, and wherever $\\mathrm{comp}\\ge\\mathrm{ego}$ the sign of $(\\mathrm{comp}-\\mathrm{ego})(b_{16}-b_{256})$ makes C256 no better. Dominance reverses only in the collaboration-harm regime ($\\mathrm{comp}<\\mathrm{ego}$, $b_{16}<b_{256}$; \\S\\ref{sec:harm}).',
             'The exclusion of C256 from the deployed action set follows from set domination, and needs no frame statistics at all. When $\\mathrm{comp}\\ge\\mathrm{ego}$, $C_{16}$ delivers the identical payload at a block-error rate that is never higher, so it is no worse than $C_{256}$ on every such frame. When $\\mathrm{comp}<\\mathrm{ego}$, sending any feature message can only lower the expected utility, and $E$ --- ego-only, no request --- is no worse than either feature mode. The two cases are exhaustive, so $C_{256}$ is dominated on every frame by an action already in $\\{E, C_{16}\\}$: it is globally dominated by the deployed set and can be dropped without a case analysis of when the dominance is strict.',
             'R30-3'),

            # Q2 (supervisor ruling, 2026-08-02): reframe the paragraph's role from a "completeness
            # defence" for retaining C256 to the "exclusion basis" for it -- C256 is dominated by C16
            # and excluded from the now 2-element deployed action set S={L,C16} (Eq.~\ref{eq:action_set}).
            # Approved together with the S={L,C16} formalism change.
            ("We retain C256 for completeness of the granularity ladder spanned by the 2-bit request, yet it earns no operational role:",
             "As established above, $C_{256}$ is dominated by $C_{16}$ and is therefore excluded from the deployed action set $\\mathcal{S}$ (Eq.~\\eqref{eq:action_set}); it completes the granularity ladder addressable by the request field but earns no operational role:",
             "Q2"),
            # R31-1 (supervisor ruling, 2026-08-18): option 1. C256 is reframed as a PHYSICAL-LAYER
            # COMPARATOR -- identical semantic content, different modulation -- excluded from the
            # deployed set BY DESIGN, because modulation order is a transport parameter and not a
            # semantic granularity. Every dominance / zero-support / global-domination statement is
            # withdrawn (they were argued from a retired product and, in III-G, in the wrong
            # direction: C256 is the SMALLER payload). The BLER cliff and Fig. 2 stay as motivation.
            # This ruling supersedes the whole paragraph, so it chains after R28-1a/1b and R30-3.
            ("Of the two feature-level modes, the 256-QAM variant (C256) halves the per-frame channel use of the 16-QAM feature message (0.495 vs. 0.99 Msym for C256 and C16, respectively\\footnote{Feature payload 1.98 Mbit (Eq.~\\eqref{eq:payload}) at LDPC rate-$1/2$ gives 3.96 Mbit of coded bits; $\\div 8$ bit/sym (256-QAM) $=0.495$ Msym, $\\div 4$ bit/sym (16-QAM) $=0.99$ Msym.}) and is thus an apparent bandwidth bargain. The learned selector nonetheless never requests it, for a structural reason whose scope we verify empirically. The two variants carry the identical feature payload and hence share comp; writing the effective F1 as $\\mathrm{eff}=\\mathrm{comp}(1-b)+\\mathrm{ego}\\,b$ -- the expected utility of a delivery that reverts to the ego-only fallback with frame-level failure probability $b$ -- they obey the identity $\\mathrm{eff}_{\\mathrm{C256}}-\\mathrm{eff}_{\\mathrm{C16}}=(\\mathrm{comp}-\\mathrm{ego})(b_{16}-b_{256})$.\\footnote{comp and ego are the frame's own measured F1; $b$ is the frame-level BLER table value at that frame's (channel, SNR) grid point -- a per-grid constant. The identity is therefore algebraic and holds by construction; verification confirms it to $\\max|\\cdot|=0$, checking the implementation for transcription error rather than an empirical regularity.} Since the denser constellation is never better protected ($b_{256}\\ge b_{16}$, with equality only where both flatline or both deliver), the sign is set by $(\\mathrm{comp}-\\mathrm{ego})$. C256 is thus dominated ($\\mathrm{eff}_{\\mathrm{C256}}\\le\\mathrm{eff}_{\\mathrm{C16}}$) wherever $b_{16}=b_{256}$ or $\\mathrm{comp}\\ge\\mathrm{ego}$, which Fig.~\\ref{fig:bler} shows is the whole operating range of interest: the 256-QAM cliff sits strictly to the right of the 16-QAM one, so by the time C256 is reliable the 16-QAM block is already error-free. The exclusion of C256 from the deployed action set follows from set domination, and needs no frame statistics at all. When $\\mathrm{comp}\\ge\\mathrm{ego}$, $C_{16}$ delivers the identical payload at a block-error rate that is never higher, so it is no worse than $C_{256}$ on every such frame. When $\\mathrm{comp}<\\mathrm{ego}$, sending any feature message can only lower the expected utility, and $E$ --- ego-only, no request --- is no worse than either feature mode. The two cases are exhaustive, so $C_{256}$ is dominated on every frame by an action already in $\\{E, C_{16}\\}$: it is globally dominated by the deployed set and can be dropped without a case analysis of when the dominance is strict. Physically, 256-QAM right-shifts the AWGN frame-error cliff from 8.0 to 16.5 dB,\\footnote{Es/N0 onset at which the frame-level BLER first falls below 0.999 -- the same 0.999 constant that defines the feasibility mask -- with 16-QAM at 8.0 dB. Fig.~\\ref{fig:bler} plots this cliff directly, with the 256-QAM BLER curve sitting to the right of the 16-QAM curve.} while under Rayleigh and OFDM (0--20 dB) both flatline at the ego floor (frame-level BLER $\\approx 1$); no SNR window opens C256 before C16. As established above, $C_{256}$ is dominated by $C_{16}$ and is therefore excluded from the deployed action set $\\mathcal{S}$ (Eq.~\\eqref{eq:action_set}); it completes the granularity ladder addressable by the request field but earns no operational role: trained to imitate an oracle that assigns C256 zero support at this operating point, the learned selector never requests it -- 0 of the $396{,}000/434{,}000/110{,}000$ deployment predictions\\footnote{Measured by replaying the 200-realisation deployment (drawn CSI) through the deployed selector and counting C256 predictions $\\to$ 0 / 0 / 0 (validate/test/culver). The deployed classifier uses $\\mathcal{S}=\\{E,L,F\\}$; $C_{256}$ is excluded from the deployed action set -- the imitated oracle labels carry zero C256 at this operating point -- so the count is structurally zero; we report the measured count rather than infer it, verified programmatically from the per-frame deployment account.}. That a rate-matched, lower-channel-use action earns no operational role at all, on physical grounds that hold for any collaborator convention, is itself the finding.",
             "Of the two feature-level modes, the 256-QAM variant ($C_{256}$) carries the \\emph{identical} semantic content as $C_{16}$---the same compressed feature payload of Eq.~\\eqref{eq:payload}---and differs only in modulation order, which halves the per-frame channel use (0.495 vs.\\ 0.99 Msym for $C_{256}$ and $C_{16}$\\footnote{Feature payload 1.98 Mbit (Eq.~\\eqref{eq:payload}) at LDPC rate-$1/2$ gives 3.96 Mbit of coded bits; $\\div 8$ bit/sym (256-QAM) $=0.495$ Msym, $\\div 4$ bit/sym (16-QAM) $=0.99$ Msym.}). It is included as a \\emph{physical-layer comparator}: holding the semantic content fixed and changing only the constellation is what isolates the codec's channel response in Fig.~\\ref{fig:bler}. It is \\emph{not} an element of the deployed action set $\\mathcal{S}=\\{E,L,F\\}$ (Eq.~\\eqref{eq:action_set}), and it is excluded by design rather than by measurement: the selector chooses \\emph{what to send}---a semantic granularity the receiver can request with the 2-bit field---whereas modulation order is a transport parameter of the link, not a granularity. Fig.~\\ref{fig:bler} shows why the distinction is physically consequential: the 256-QAM frame-error cliff sits far to the right of the 16-QAM one (AWGN onset $16.5$ vs.\\ $8.0$~dB\\footnote{Es/N0 onset at which the frame-level BLER first falls below 0.999 -- the same 0.999 constant that defines the feasibility mask. Fig.~\\ref{fig:bler} plots both cliffs directly.}), and under Rayleigh and OFDM both flatline at the ego floor across $0$--$20$~dB, so on this transport a denser constellation buys channel use at the cost of reach.",
             'R31-1'),
            # R37 (page-limit compression, R37-3 fallback): the C256 sentences are shortened; the
            # exclusion-by-design argument, the comparator role and the transport-parameter reason
            # are all preserved, and no number changes.
            ("It is included as a \\emph{physical-layer comparator}: holding the semantic content fixed and changing only the constellation is what isolates the codec's channel response in Fig.~\\ref{fig:bler}. It is \\emph{not} an element of the deployed action set $\\mathcal{S}=\\{E,L,F\\}$ (Eq.~\\eqref{eq:action_set}), and it is excluded by design rather than by measurement: the selector chooses \\emph{what to send}---a semantic granularity the receiver can request with the 2-bit field---whereas modulation order is a transport parameter of the link, not a granularity.",
             "It is a \\emph{physical-layer comparator}: holding semantic content fixed and changing only the constellation isolates the codec's channel response (Fig.~\\ref{fig:bler}). It is \\emph{not} in $\\mathcal{S}$, and is excluded by design rather than by measurement---the selector chooses \\emph{what to send}, a granularity the receiver requests with the 2-bit field, whereas modulation order is a transport parameter of the link.",
             'R37-compress'),
        ],
    ),
    3: dict(
        body_first="A concurrent line of work pushes semantic communication",
        body_last="on an undeliverable feature message.",
        start_anchor="A concurrent line of work pushes semantic communication",
        next_boundary=r"\\(subsection|section)\{",
        subs=[],       # #3 carries no placeholders: \cite{gan2025cods} resolves via the bib
                       # entry added in the infra commit; \method{}/\emph{} are existing macros.
        rulings=[
            # R28-3: the CoDS comparison enumerated the action set without E. E is a deployed
            # action and C256 is not, so the enumeration is ego-only / object-level / feature.
            ('it selects the message \\emph{granularity} per frame -- the compact object-level message or one of the feature-level variants -- and signals the choice through the 2-bit request before any high-payload transmission;',
             'it selects the message \\emph{granularity} per frame -- ego-only operation with no request at all, the compact object-level message, or the feature-level message -- and signals the choice through the 2-bit request before any high-payload transmission;',
             'R28-3'),
],
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
            # R28-4: the second harm quantifier was quoted from the retired pre-corrigendum C256
            # dominance file; re-derived from the N=1 caches by collab_harm.py as 1.3/6.5/0.9%.
            ('and -- from the same per-frame $(\\mathrm{comp}-\\mathrm{ego})$ identity and CSV as the C256 analysis (\\S\\ref{sec:candidates}) -- the compressed-feature message, when delivered, yields lower frame F1 than the ego-only fallback on 1.0 / 5.8 / 0.9\\% of frames.',
             'and -- from the same per-frame $(\\mathrm{comp}-\\mathrm{ego})$ identity, re-derived on the corrected single-collaborator caches -- the compressed-feature message, when delivered, yields lower frame F1 than the ego-only fallback on 1.3 / 6.5 / 0.9\\% of frames.',
             'R28-4'),
            # R34: the paragraph moved to supplementary.tex, where a label defined in the main
            # paper cannot resolve; the cross-reference becomes a named pointer.
            ("the same $0.999$ constant as the \\S\\ref{sec:method} mask",
             "the same $0.999$ constant as the feasibility mask of the main paper",
             'R34-xref'),

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


def _delivered_text():
    """main.tex plus supplementary.tex.

    R33 moved the collaboration-harm subsection (paragraph 2 of this gate) into the supplementary
    document. The insertion guarantee follows the paragraph, not the file it happens to sit in, so
    the gate reads the delivered text as a whole -- the same rule R32 applied to the registry gate.
    """
    parts = [_read(TEX)]
    supp = os.path.join(os.path.dirname(TEX), 'supplementary.tex')
    if os.path.exists(supp):
        parts.append(_read(supp))
    return '\n'.join(parts)


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
            f'para bound not found in the delivered text: {last[:60]!r}. If a ruling rewrote the closing '
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
    actual = _inserted_block(_delivered_text(), cfg)

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
