#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLAIMS ledger extractor (P1 / P1.5).

Pulls every number-bearing sentence out of paper/main.tex and emits paper1/CLAIMS.md, an 8-column
ledger:

  Claim | Exact value | Split | Metric | CSV | Generator | Statistical support | Allowed wording

The first two columns are auto-filled (Claim = the sentence; Exact value = the numeric tokens in it,
excluding citation/label/ref keys). The six evidence columns are back-filled BY HAND in P2-P4.

MERGE-PRESERVE (P1.5): on re-run the extractor regenerates columns 1-2 but PRESERVES any hand-filled
evidence column. Rows are matched by a number-insensitive "claim skeleton" (letters only), so a
change in number formatting does not orphan an evidence row. The extractor therefore NEVER clears an
evidence cell a human filled (e.g. the "evidence-orphaned" flag on the 0.801/0.688 identity-ceiling
row). --check exits 1 if CLAIMS.md is stale vs the merged regeneration.

TOKENISATION (P1.5 fixes): (a) \pm/\times/\approx/\le/\ge/\to render as ±/×/≈/≤/≥/→ in the Claim, so
"52.8\pm5.7" reads "52.8 ± 5.7"; (b) thousands separators: "1,980" is one number; (c) glued numbers:
numbers inside \cite{...}/\ref{...}/\label{...}/\eqref{...} keys (e.g. "80211" in ieee80211bd, a cite
year) are stripped BEFORE number extraction and before the value-token qualification.

HEURISTIC (disclosed): a sentence qualifies iff, after stripping ref/cite/label keys, it carries a
value token -- a decimal, an integer (with optional thousands commas) glued to a result unit, or a
percentage. Bare section/equation/figure indices do not qualify.

Run:  python paper1/code/extract_claims.py          # writes paper1/CLAIMS.md (merge-preserving)
      python paper1/code/extract_claims.py --check   # exit 1 if CLAIMS.md is stale
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
TEX = os.path.join(P1, 'paper/main.tex')
OUT = os.path.join(P1, 'CLAIMS.md')

UNIT = r'(?:dB|ms|Msym(?:/frame)?|Mbit(?:/s)?|kbit|bps|Hz|MHz|QAM|-QAM|bit|bits|trees|frames|scenes)'
# value token: decimal | integer(+thousands) glued to a unit | percentage
VALUE_TOKEN = re.compile(r'(?<![\\A-Za-z])(?:\d[\d,]*\.\d+|\d[\d,]*\s*%|\d[\d,]*\s*[+\-]?\s*' + UNIT + r')')
# numbers to LIST in the Exact-value column (decimals, signed, thousands separators)
NUMBER = re.compile(r'[-+]?\d[\d,]*(?:\.\d+)?')
REFKEY = re.compile(r'\\(?:cite[a-z]*|ref|eqref|pageref|label|autoref|Cref|cref)\*?\{[^}]*\}')
EVIDENCE_COLS = 6                                       # Split..Allowed wording


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _strip_refs(text):
    """Remove \\cite/\\ref/\\label/\\eqref keys so their internal digits (ieee80211bd, years) are not
    mined as claim numbers; normalise the LaTeX thousands separator 2{,}000 -> 2,000 so a thousands
    number is one token, not two."""
    return REFKEY.sub(' ', text).replace('{,}', ',')


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
    return s.replace('|', r'\|')


def exact_values(sent):
    vals = []
    for m in NUMBER.finditer(_strip_refs(sent)):
        v = m.group(0)
        if v not in vals:
            vals.append(v)
    return ', '.join(vals).replace('|', r'\|')


def _skeleton(claim):
    """Number-insensitive key for merge-preserve: letters only, lowercased."""
    return re.sub(r'[^a-zA-Z]', '', claim).lower()


def parse_existing(path):
    """Return {skeleton -> [6 evidence cells]} for rows that have ANY non-empty evidence cell."""
    if not os.path.exists(path):
        return {}
    keep = {}
    for line in _read(path).splitlines():
        if not line.startswith('| ') or line.startswith('| # ') or line.startswith('|---'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 9:                            # # | Claim | Exact | +6 evidence
            continue
        claim, ev = cells[1], cells[3:9]
        if any(ev):
            keep[_skeleton(claim)] = ev
    return keep


HEADER = (
    "# CA-TOSG — CLAIMS LEDGER (P1.5)\n\n"
    "Every number-bearing sentence in `paper/main.tex`, one row per claim. **Auto-generated by "
    "`code/extract_claims.py`** (columns 1-2). The six evidence columns are back-filled by hand in "
    "P2–P4 and are **merge-preserved** across re-runs — the extractor never clears an evidence cell "
    "a human filled. A blank evidence cell is an open TODO, not a verified fact.\n\n"
    "Extraction heuristic (script header): a sentence qualifies iff, after ref/cite/label keys are "
    "stripped, it carries a value token (decimal, integer+unit, or percentage). Frozen numbers change "
    "in P2; this ledger forces every one back to a source.\n\n"
    "| # | Claim | Exact value | Split | Metric | CSV | Generator | Statistical support | Allowed wording |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def build():
    prose = strip_tex(_read(TEX))
    preserved = parse_existing(OUT)
    rows, n_pres = [], 0
    for sent in sentences(prose):
        if len(sent) < 8 or is_index_only(sent):
            continue
        claim = clean_claim(sent)
        ev = preserved.get(_skeleton(claim), [''] * EVIDENCE_COLS)
        if any(ev):
            n_pres += 1
        rows.append((claim, exact_values(sent), ev))
    lines = [HEADER]
    for i, (claim, vals, ev) in enumerate(rows, 1):
        lines.append('| %d | %s | %s | %s |\n' % (i, claim, vals, ' | '.join(ev)))
    filled = sum(1 for _, _, ev in rows if any(ev))
    lines.append(f"\n_Total: {len(rows)} number-bearing claims from `paper/main.tex`. "
                 f"Evidence columns: {filled} filled / {len(rows) - filled} pending (P2–P4); "
                 f"{n_pres} preserved across this re-run._\n")
    return ''.join(lines)


def main():
    content = build()
    if '--check' in sys.argv:
        cur = _read(OUT) if os.path.exists(OUT) else ''
        if cur != content:
            print('CLAIMS.md is STALE vs main.tex -- re-run: python code/extract_claims.py')
            sys.exit(1)
        print('CLAIMS.md up to date.')
        return
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'wrote {OUT} ({content.count(chr(10))} lines)')


if __name__ == '__main__':
    main()
