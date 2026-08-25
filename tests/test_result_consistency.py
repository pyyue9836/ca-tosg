#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""CLAIMS ledger extractor (P1 / P1.5 / P2).

Pulls every number-bearing sentence out of paper/main.tex and emits docs/claims.md, a 9-column
ledger:

  ID | Claim | Exact value | Split | Metric | CSV | Generator | Statistical support | Allowed wording

The first three columns are auto-filled (ID = stable claim id; Claim = the sentence; Exact value = its
numeric tokens, excluding citation/label/ref keys). The six evidence columns are back-filled by hand
in P2-P4.

STABLE IDs (P2): each claim gets a stable id = 'c'+md5(letters-only skeleton)[:6], so a claim keeps
its id across re-runs / re-orderings / number-formatting changes.

NUMBER-CHANGE -> STALE (P2, no silent retention): evidence is preserved on re-run ONLY while the
claim's Exact value is unchanged. If the numbers change, the evidence is NOT silently kept -- it is
overwritten with a "STALE" flag recording the old value, forcing re-verification. (Unchanged claims
with hand-filled evidence, e.g. the 0.801/0.688 evidence-orphaned row, are preserved verbatim.)

TOKENISATION: \pm/\times/... render as ±/×/...; thousands 2{,}000 -> one token; numbers inside
\cite/\ref/\label/\eqref keys stripped before extraction; residue cleaned (LaTeX en-dash `--` split;
trailing/leading commas stripped; empty tokens dropped).

Run:  python tests/test_result_consistency.py          # writes docs/claims.md
      python tests/test_result_consistency.py --check   # exit 1 if docs/claims.md is stale
"""
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
TEX = os.path.join(P1, 'paper/main.tex')
OUT = os.path.join(P1, 'docs/claims.md')

UNIT = r'(?:dB|ms|Msym(?:/frame)?|Mbit(?:/s)?|kbit|bps|Hz|MHz|QAM|-QAM|bit|bits|trees|frames|scenes)'
VALUE_TOKEN = re.compile(r'(?<![\\A-Za-z])(?:\d[\d,]*\.\d+|\d[\d,]*\s*%|\d[\d,]*\s*[+\-]?\s*' + UNIT + r')')
NUMBER = re.compile(r'[-+]?\d[\d,]*(?:\.\d+)?')
REFKEY = re.compile(r'\\(?:cite[a-z]*|ref|eqref|pageref|label|autoref|Cref|cref)\*?\{[^}]*\}')
EVIDENCE_COLS = 6


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _strip_refs(text):
    """Drop \\cite/\\ref/\\label keys (their digits are not claims); normalise 2{,}000 -> 2,000 and the
    LaTeX en-dash `--` (range separator) -> space so a range does not glue into a signed number."""
    return REFKEY.sub(' ', text).replace('{,}', ',').replace('--', ' ')


def strip_tex(tex):
    m = re.search(r'\\begin\{document\}(.*)\\end\{document\}', tex, re.S)
    if m:
        tex = m.group(1)
    tex = '\n'.join(re.sub(r'(?<!\\)%.*$', '', line) for line in tex.splitlines())
    for env in ('equation', 'align', 'aligned', 'tabular', 'array', 'figure', 'table', 'gather'):
        tex = re.sub(r'\\begin\{%s\*?\}.*?\\end\{%s\*?\}' % (env, env), ' ', tex, flags=re.S)
    tex = re.sub(r'\$\$.*?\$\$', ' ', tex, flags=re.S)
    return tex


def sentences(tex):
    tex = re.sub(r'\s+', ' ', tex)
    tex = re.sub(r'(\d)\.(\d)', r'\1<DOT>\2', tex)
    tex = tex.replace('e.g.', 'e<DOT>g<DOT>').replace('i.e.', 'i<DOT>e<DOT>')
    tex = re.sub(r'\b([A-Z])\.', r'\1<DOT>', tex)
    parts = re.split(r'(?<=[.:])\s+(?=[A-Z\\$])', tex)
    return [p.replace('<DOT>', '.').strip() for p in parts if p.strip()]


def is_index_only(sent):
    return VALUE_TOKEN.search(_strip_refs(sent)) is None


def clean_claim(sent):
    s = sent
    s = REFKEY.sub(lambda m: '[' + re.match(r'\\([a-zA-Z]+)', m.group(0)).group(1) + ']', s)
    for a, b in ((r'\pm', ' ± '), (r'\times', ' × '), (r'\approx', ' ≈ '), (r'\leq', ' ≤ '),
                 (r'\geq', ' ≥ '), (r'\le', ' ≤ '), (r'\ge', ' ≥ '), (r'\to', ' → ')):
        s = s.replace(a, b)
    s = re.sub(r'\\(emph|textbf|textit|method|texttt)\{([^}]*)\}', r'\2', s)
    s = s.replace('\\method{}', 'CA-TOSG').replace('\\method', 'CA-TOSG')
    s = re.sub(r'\\[a-zA-Z]+\*?', '', s)
    s = s.replace('{', '').replace('}', '').replace('~', ' ').replace('$', '')
    s = re.sub(r'\s+', ' ', s).strip()
    # a literal pipe must be the HTML entity, not a backslash escape: parse_existing splits on
    # a raw '|' and a backslash does not shield it (see its docstring)
    return s.replace('|', '&#124;')


def exact_values(sent):
    s = _strip_refs(sent)
    vals = []
    for m in NUMBER.finditer(s):
        v = m.group(0).strip(',')                              # drop trailing/leading comma residue
        # a leading +/- that is really a hyphen after a letter (e.g. "rate-1/2") is not a sign
        if v[:1] in '+-' and m.start() > 0 and s[m.start() - 1].isalpha():
            v = v[1:]
        if v and v not in vals:
            vals.append(v)
    return ', '.join(vals).replace('|', '&#124;')


def _skeleton(claim):
    # letters-only keeps the id number-insensitive (so measured-number changes preserve evidence),
    # PLUS the action/QAM mode identifiers -- otherwise two claims that differ ONLY by C16 vs C256
    # collapse to the same skeleton and collide (cb3af69). R7: recognise ONLY explicit mode markers
    # (C16 / C_16 / 16-QAM / C256 / C_256 / 256-QAM), NOT plain numbers like "16 dB" or "16 %" -- so
    # changing a measured "16 dB" -> "14 dB" keeps the same id (-> STALE), not a new id.
    letters = re.sub(r'[^a-zA-Z]', '', claim).lower()
    # numeric SHAPE, not values: count of numbers + the multiset of their decimal widths. Two
    # sentences that differ only in a measured value keep the same shape (-> same id -> STALE),
    # but 'three 4-decimal values' and 'nine percentages' no longer collide (c6fcc17).
    nums = re.findall(r'\d+(?:\.\d+)?', claim)
    shape = 'n%d_%s' % (len(nums), ''.join(sorted(str(len(x.split('.')[1]) if '.' in x else 0)
                                                  for x in nums)))
    modes = set()
    if re.search(r'C_?16\b|16-?QAM', claim):
        modes.add('16')
    if re.search(r'C_?256\b|256-?QAM', claim):
        modes.add('256')
    return letters + ''.join(sorted(modes)) + '|' + shape


def claim_id(claim):
    return 'c' + hashlib.md5(_skeleton(claim).encode()).hexdigest()[:6]


def parse_existing(path):
    """Return {skeleton: (exact_value, [6 evidence cells])} for every prior row.

    A row that does not parse to exactly 9 cells is a HARD FAILURE, not a skip. It used to be a
    `continue`, which is a gate-level hazard: a cell containing a literal `|` (e.g. a generator
    command `... --train|--evaluate`) over-splits the row, the row is skipped here, and the next
    rebuild re-emits it with EMPTY evidence. The ledger then reads as filled when it is written and
    comes back blank, with nothing anywhere saying so. Escaping does not help either -- the split is
    a plain `str.split('|')` -- so a literal pipe must be written as the entity `&#124;`.
    """
    if not os.path.exists(path):
        return {}
    out, broken = {}, []
    for lineno, line in enumerate(_read(path).splitlines(), 1):
        if not line.startswith('| ') or line.startswith('|---') or ' Claim ' in line:
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 9:
            broken.append((lineno, len(cells), line[:90]))
            continue
        claim, exact, ev = cells[1], cells[2], cells[3:9]
        out[_skeleton(claim)] = (exact, ev)
    if broken:
        sys.stderr.write(
            f'\n{path}: {len(broken)} row(s) do NOT parse to 9 cells. Their evidence would be '
            f'silently dropped on this rebuild, so the run is aborted instead.\n'
            f'A literal "|" inside a cell is the usual cause -- write it as &#124;.\n')
        for lineno, n, head in broken:
            sys.stderr.write(f'  line {lineno}: {n} cells: {head}...\n')
        sys.exit(1)
    return out


HEADER = (
    "# CA-TOSG — CLAIMS LEDGER (P2)\n\n"
    "Every number-bearing sentence in `paper/main.tex`, one row per claim. **Auto-generated by "
    "`tests/test_result_consistency.py`** (ID + Claim + Exact value). Stable `ID` survives re-runs. The six "
    "evidence columns are back-filled by hand in P2–P4; they are preserved on re-run **only while a "
    "claim's Exact value is unchanged** — if a number changes the evidence is flagged **STALE** (never "
    "silently retained). A blank evidence cell is an open TODO.\n\n"
    "_Diagnostic note (PROTOCOL R6/R7): the gap between a candidate's OOF payload and its full-retrain "
    "(frozen) payload is a training→freeze diagnostic of the selection procedure and must NOT be "
    "written into the paper's conclusions._\n\n"
    "| ID | Claim | Exact value | Split | Metric | CSV | Generator | Statistical support | Allowed wording |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def build():
    prose = strip_tex(_read(TEX))
    prev = parse_existing(OUT)
    rows, n_pres, n_stale = [], 0, 0
    for sent in sentences(prose):
        if len(sent) < 8 or is_index_only(sent):
            continue
        claim = clean_claim(sent)
        cid = claim_id(claim)
        exact = exact_values(sent)
        ev = [''] * EVIDENCE_COLS
        skel = _skeleton(claim)
        if skel in prev:
            old_exact, old_ev = prev[skel]
            if any(old_ev):
                if old_exact == exact:
                    ev = old_ev                                # preserve verbatim
                    n_pres += 1
                else:                                          # number changed -> STALE, do NOT retain silently
                    ev = [f'⚠ STALE: value changed ({old_exact} → {exact}); re-verify'] + [''] * (EVIDENCE_COLS - 1)
                    n_stale += 1
        rows.append((cid, claim, exact, ev))
    ids = [cid for cid, _, _, _ in rows]
    if len(set(ids)) != len(ids):
        import collections
        dup = [k for k, v in collections.Counter(ids).items() if v > 1]
        raise SystemExit(f'extract_claims: duplicate stable IDs {dup} -- skeleton collision, fix _skeleton')
    lines = [HEADER]
    for cid, claim, exact, ev in rows:
        lines.append('| %s | %s | %s | %s |\n' % (cid, claim, exact, ' | '.join(ev)))
    filled = sum(1 for _, _, _, ev in rows if any(ev))
    lines.append(f"\n_Total: {len(rows)} number-bearing claims from `paper/main.tex`. "
                 f"Evidence: {filled} filled / {len(rows) - filled} pending (P2–P4); "
                 f"{n_pres} preserved, {n_stale} flagged STALE (numbers changed) this re-run._\n")
    return ''.join(lines)


def assert_round_trips(content):
    """Every row the writer emits must parse back to 9 cells. Closes the loop on the pipe hazard:
    the writer can no longer produce a ledger the reader would silently blank."""
    bad = []
    for lineno, line in enumerate(content.splitlines(), 1):
        if not line.startswith('| ') or line.startswith('|---') or ' Claim ' in line:
            continue
        n = len([c for c in line.strip().strip('|').split('|')])
        if n != 9:
            bad.append((lineno, n, line[:90]))
    if bad:
        sys.stderr.write('\nREFUSING TO WRITE: %d generated row(s) do not round-trip to 9 cells.\n'
                         % len(bad))
        for lineno, n, head in bad:
            sys.stderr.write(f'  line {lineno}: {n} cells: {head}...\n')
        sys.exit(1)


def main():
    content = build()
    assert_round_trips(content)
    if '--check' in sys.argv:
        cur = _read(OUT) if os.path.exists(OUT) else ''
        if cur != content:
            print('docs/claims.md is STALE vs main.tex -- re-run: python tests/test_result_consistency.py')
            sys.exit(1)
        # R20 9a: freshness is not enough -- an unbound or stale row is a FAILURE, not a note.
        # Both were reported as counts for months while the gate passed.
        rows = [l for l in open(OUT, encoding='utf-8') if l.startswith('| c')]
        stale, pend = 0, 0
        for l in rows:
            c = [x.strip() for x in l.strip().strip('|').split('|')]
            if len(c) != 9:
                continue
            if c[3].startswith('\u26a0 STALE'):
                stale += 1
            elif not any(c[3:9]):
                pend += 1
        if stale or pend:
            print('CLAIMS GATE FAIL: %d STALE and %d unbound row(s) in docs/claims.md -- '
                  'rebind them or delete the sentence (R20 9a)' % (stale, pend))
            return 1
        print('docs/claims.md up to date; 0 STALE, 0 unbound (R20 9a).')
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'wrote {OUT} ({content.count(chr(10))} lines)')


if __name__ == '__main__':
    # R23-8: main() RETURNED 1 on an unbound/stale row and nothing propagated it, so the R20-9a
    # check printed "CLAIMS GATE FAIL" while the process exited 0 and verify_results reported PASS.
    sys.exit(main() or 0)
