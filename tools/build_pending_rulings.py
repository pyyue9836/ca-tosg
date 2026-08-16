#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build docs/p6_pending_rulings.md — the two decision lists, one row per item.

List A: every number a figure draws, cross-checked against caption and body (37 rows).
List B: every ledger claim with no located evidence (52 rows).

Each row carries its location in `paper/main.tex`, the numbers involved, a **suggested** action and
a one-line reason. The suggestion is a heuristic and is labelled as one: the ruling is Peiyi's, and
nothing here edits `main.tex`.

    python tools/build_pending_rulings.py
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tests'))

from audit_claims_evidence import (  # noqa: E402
    claims_by_section, distinctive, ledger_rows, locate_evidence, results_corpus, results_index,
)
from check_figure_consistency import appears, compatible, sentences_with, split_caption_body  # noqa: E402

MAIN = os.path.join(ROOT, 'paper', 'main.tex')
PROV = os.path.join(ROOT, 'results', 'provenance', 'PROVENANCE_figures.json')
OUT = os.path.join(ROOT, 'docs', 'p6_pending_rulings.md')

# which figure each drawn key belongs to, for the location column
FIG_OF = [('f1_', 'Fig.~4 (fig:ap_snr)'), ('payload_', 'Fig.~5 (fig:payload_snr)'),
          ('rho_', 'Fig.~6 (fig:decision_ratio)'), ('pareto_', 'Fig.~8 (fig:pareto)'),
          ('knee', 'Fig.~2 (fig:bler) / Fig.~4')]


def fig_of(key):
    for pre, name in FIG_OF:
        if key.startswith(pre):
            return name
    return '(unmapped)'


def line_of(tex_lines, literal):
    """First main.tex line on which a printed literal occurs (1-indexed), else None."""
    pat = re.compile(r'(?<![\d.])' + re.escape(literal) + r'(?![\d])')
    for i, l in enumerate(tex_lines, 1):
        if pat.search(l):
            return i
    return None


# Standards identifiers are NAMES, not measurements: "802.11bd" and "TR 37.885" must never be
# treated as numbers needing experimental evidence. Without this, the abstract's IEEE 802.11
# citation was proposed for deletion-or-recompute.
STANDARD_IDS = {'802.11', '37.885', '2.11', '11.0'}


def claim_line(tex_lines, claim):
    """Locate the claim's OWN sentence, not the first place one of its numbers happens to appear.

    Matching a bare literal put half of list B on line 34 (the abstract) because that is where
    "802.11" first occurs. Here a distinctive word-run from the claim is matched instead.
    """
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", claim)]
    flats = [' '.join(re.findall(r"[A-Za-z]{4,}", l)).lower() for l in tex_lines]
    # slide the probe across the claim: anchoring at the start fails whenever the sentence opens
    # with a macro (\method{} -> "CA-TOSG" in the cleaned claim but "method" in the source)
    for n in (7, 5, 4):
        for st in range(0, max(1, len(words) - n + 1)):
            probe = ' '.join(words[st:st + n])
            if len(probe) < 18:
                continue
            for i, flat in enumerate(flats, 1):
                if probe in flat:
                    return i
    return None


def build_list_a(tex, tex_lines):
    prov = json.load(open(PROV))
    caption, body = split_caption_body(tex)
    rows = []
    for key, item in sorted(prov['numbers_drawn'].items()):
        val = item['value'] if isinstance(item, dict) else item
        tags = {k: item.get(k) for k in ('split', 'budget', 'channel', 'snr_db')} \
            if isinstance(item, dict) else {}
        tagstr = ' '.join(f'{k}={v}' for k, v in tags.items() if v is not None) or '—'
        state, where, wrong = 'nowhere', [], False
        for side, text in (('caption', caption), ('body', body)):
            lit = appears(val, text)
            if lit is None:
                continue
            wins = sentences_with(text, lit)
            if [w for w in wins if compatible(tags, w)]:
                where.append(side)
            elif wins:
                wrong = True
        if len(where) == 2:
            state = 'both'
        elif len(where) == 1:
            state = f'{where[0]} only'
        if wrong and state == 'nowhere':
            state = 'different condition'

        lit = appears(val, tex) or f'{val}'
        ln = line_of(tex_lines, lit)
        if state == 'both':
            action, why = 'no action', 'figure, caption and body already agree at the same condition'
        elif state == 'different condition':
            action = 'add a condition label'
            why = ('the literal occurs, but only in a sentence pinning a different '
                   'split/budget/channel/SNR — label the condition rather than change the number')
        elif state == 'caption only':
            action = 'add to body, or leave'
            why = 'stated in the caption but nowhere in the running text — fine if deliberate'
        elif state == 'body only':
            action = 'add to caption, or leave'
            why = 'the text states it but the figure caption does not — a reader of the figure alone misses it'
        else:
            action = 'add to caption, or drop from the figure'
            why = 'the figure plots this value but no caption or sentence states it anywhere'
        rows.append((key, val, tagstr, fig_of(key), ln, state, action, why))
    return rows


def build_list_b(tex_lines):
    corpus = results_corpus()
    index = results_index()
    ledger = ledger_rows()
    rows = []
    for section, subsection, cid, claim, exact in claims_by_section():
        cells = ledger.get(cid, [''] * 6)
        if any(cells):
            continue
        found, lits = locate_evidence(exact, corpus)
        if found:
            continue
        lits = [x for x in lits if x.lstrip('+-') not in STANDARD_IDS]
        loc = f'{section}{" → " + subsection if subsection else ""}'
        ln = claim_line(tex_lines, claim)
        if not lits:
            kind = 'no distinctive number'
            action = 'attach evidence (analytic / definitional)'
            why = ('carries only structural constants (mode names, IoU, 2-bit, 802.11bd) — cite the '
                   'derivation or the notation table, no experiment needed')
        else:
            # relaxed second pass: does ANY committed file hold even one of the literals?
            near = []
            for path, vals in corpus.items():
                hit = [x for x in lits if any(round(v, len(x.split('.')[1])) == round(float(x), len(x.split('.')[1])) for v in vals)]
                if hit:
                    near.append((len(hit), path))
            near.sort(reverse=True)
            kind = 'unlocated'
            # Same standard as the audit: a SINGLE common literal attributes nothing. Require two
            # literals in one file, or one literal precise enough (>=4 decimals) to identify a file
            # on its own. Anything weaker is reported as a hint, never as a recommendation --
            # handing over 16 rulings built on coincidental single-value hits would be worse than
            # handing over none.
            strong = None
            if near:
                n_hit, path = near[0]
                if n_hit >= 2 or (len(lits) == 1 and len(lits[0].split('.')[1]) >= 4):
                    strong = (n_hit, path)
            if strong:
                n_hit, path = strong
                gen = index.get(os.path.basename(path), (None, ''))[0]
                action = f'attach evidence → `{path}`'
                why = (f'{n_hit}/{len(lits)} literals co-occur in that file'
                       + (f', generator `{gen}`' if gen else ', generator UNINDEXED'))
            else:
                action = 'recompute from frozen products, or delete the sentence'
                hint = (f' (weak hint only: 1/{len(lits)} literal appears in '
                        f'`{near[0][1]}` — not enough to attribute)') if near else ''
                why = ('no committed result file holds a sufficient combination of its literals — '
                       'either it needs a run, or the sentence has no evidence and should go'
                       + hint)
        rows.append((cid, loc, ln, exact, kind, action, why, claim))
    return rows


def main() -> int:
    tex = open(MAIN, encoding='utf-8').read()
    tex_lines = tex.splitlines()
    a = build_list_a(tex, tex_lines)
    b = build_list_b(tex_lines)

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('# P6 pending rulings — two decision lists\n\n')
        f.write('> **Count correction.** A previous report described list A as "37 items '
                '(8/16/8/5)". That was wrong: the figure-consistency checker prints its 5 '
                '"same value, different condition" entries as *per (key, side) annotations on rows '
                'it has already counted*, not as separate items, and it skips `knee_db` as axis '
                'furniture. The true item count is **33 distinct drawn numbers** (32 in the '
                'checker\'s table + `knee_db`). Nothing was added or removed; only the tally was '
                'double-counted.\n\n')
        f.write('**Nothing here has been acted on and `main.tex` is untouched.** Generated by '
                '`python tools/build_pending_rulings.py`. Every *suggested action* is a heuristic '
                'and is labelled as such; the ruling is Peiyi\'s. Rule each row, then it lands in '
                'one pass.\n\n')
        counts = {}
        for r in a:
            counts[r[5]] = counts.get(r[5], 0) + 1
        f.write(f'| list | rows |\n|---|---|\n| A — figure / caption / body | {len(a)} |\n'
                f'| B — ledger claims with no located evidence | {len(b)} |\n\n')
        f.write('## List A — figure numbers vs caption vs body (%d)\n\n' % len(a))
        f.write('State is condition-aware: a value counts as quoted only in a sentence whose stated '
                'split / budget / channel / SNR does not contradict the one it was drawn at.\n\n')
        f.write('| # | drawn key | value | condition | figure | main.tex line | state | suggested '
                'action | why |\n|---|---|---|---|---|---|---|---|---|\n')
        for i, (k, v, tag, fig, ln, st, act, why) in enumerate(a, 1):
            loc = ln if ln else ('not in main.tex' if st == 'nowhere' else '—')
            f.write(f'| A{i} | `{k}` | {v} | {tag} | {fig} | {loc} | {st} | **{act}** | {why} |\n')
        f.write(f'\n### A-summary\n\n')
        for k, n in sorted(counts.items(), key=lambda x: -x[1]):
            f.write(f'- {k}: {n}\n')

        f.write('\n## List B — ledger claims with no located evidence (%d)\n\n' % len(b))
        f.write('`no distinctive number` = the claim carries only structural constants, so it needs '
                'a citation, not an experiment. `unlocated` = it carries real numbers that no '
                'committed result file holds.\n\n')
        f.write('| # | id | section | main.tex line | exact values | kind | suggested action | why |'
                '\n|---|---|---|---|---|---|---|---|\n')
        for i, (cid, loc, ln, exact, kind, act, why, _claim) in enumerate(b, 1):
            f.write(f'| B{i} | `{cid}` | {loc} | {ln or "—"} | {exact[:52]} | {kind} | **{act}** | '
                    f'{why} |\n')
        f.write('\n### B — full claim text for the rows proposed for deletion or recompute\n\n')
        for i, (cid, loc, ln, exact, kind, act, why, claim) in enumerate(b, 1):
            if act.startswith('recompute'):
                f.write(f'**B{i} `{cid}` — {loc}, line {ln or "?"}**\n\n> {claim}\n\n')
        f.write('\n---\n\n## How to rule\n\nReply with row ids and a verb; ranges and blocks are '
                'fine. Anything not mentioned is left untouched.\n\n'
                '- **List A** verbs: `caption` (state it in the caption), `body` (state it in the '
                'text), `drop` (stop drawing it), `label` (add the condition), `leave`.\n'
                '- **List B** verbs: `evidence` (attach the cited source), `recompute` (I run it '
                'and report cost first), `delete` (remove the sentence), `leave`.\n\n'
                'e.g. `A2-A7 caption; A8 drop; B1-B41 evidence; B44 delete; rest leave`.\n\n'
                'The landing pass applies every ruling in one batch, regenerates the ledger and the '
                'figure-consistency list, and re-runs all nine gates.\n')
    print(f'List A: {len(a)} rows  |  List B: {len(b)} rows')
    for k, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f'  A/{k}: {n}')
    print(f'wrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
