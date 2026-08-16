#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5 batch 3, step 1: attribute every claims-ledger row to a section and to an evidence engine.

The ledger (`docs/claims.md`) is flat: it has no section column, and its evidence columns are
free text. To decide what to do with the legacy-engine material still standing in `main.tex`, we
need two things the ledger does not carry:

  * **which section a claim lives in** -- recovered by re-walking `paper/main.tex` with the same
    sentence splitter the ledger generator uses, tracking `\\section` / `\\subsection` headers;
  * **which engine produced its evidence** -- resolved from `results/README.md` (the file->generator
    index) and then from the generator's own intra-repo import closure, so the LEGACY-ENGINE tag is
    *derived* from the code rather than asserted from memory.

Engine classification, in order of precedence, from the repo's own markers:

  LEGACY-ENGINE  the generator, or anything in its import closure, reads the v3 selector
                 (`train_rf_v3` / `rf_v3` artefacts) or is the v3 200-realisation policy engine
                 (`policy_200seed`) or the v3 global-sort scorer (`true_e2e_global`); or
                 `results/README.md` marks its output "P1-v3".
  FROZEN         the closure reads the frozen selectors (`data/p2/selector_B0*.pkl`) or
                 `FROZEN_MANIFEST.json`.
  ANALYTIC       no result CSV: the evidence is a derivation or a resident gate (tests/*.py).
  UNRESOLVED     a CSV is cited that `results/README.md` does not index.

Nothing here edits `main.tex` or any result. Output: `docs/claims_evidence_audit.md`.

    python tools/audit_claims_evidence.py            # write the audit
    python tools/audit_claims_evidence.py --check    # fail if the audit is stale
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tests'))

from test_result_consistency import (  # noqa: E402  (path set above)
    clean_claim, claim_id, exact_values, is_index_only, sentences, strip_tex,
)

MAIN_TEX = os.path.join(ROOT, 'paper', 'main.tex')
CLAIMS = os.path.join(ROOT, 'docs', 'claims.md')
RESULTS_INDEX = os.path.join(ROOT, 'results', 'README.md')
OUT = os.path.join(ROOT, 'docs', 'claims_evidence_audit.md')

SECTION_RE = re.compile(r'\\(section|subsection)\*?\{')
LABEL_RE = re.compile(r'\\label\{([^}]*)\}')

# markers, matched against a generator's whole import closure (source text)
LEGACY_MARKERS = ('train_rf_v3', 'rf_v3', 'policy_200seed', 'true_e2e_global', 'v3_eval')
FROZEN_MARKERS = ('selector_B0', 'FROZEN_MANIFEST', 'data/p2')


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------- section attribution
def _brace_span(text, open_idx):
    """Return the index just past the '{...}' group that starts at open_idx."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def claims_by_section():
    """[(section, subsection, claim_id, claim, exact)] in document order."""
    tex = strip_tex(read(MAIN_TEX))
    marks = []
    for m in SECTION_RE.finditer(tex):
        end = _brace_span(tex, m.end() - 1)
        title = tex[m.end():end - 1]
        # a \label immediately after the header belongs to it
        tail = tex[end:end + 80]
        lab = LABEL_RE.search(tail)
        label = lab.group(1) if lab and tail.index(lab.group(0)) < 3 else ''
        marks.append((m.start(), end, m.group(1), clean_claim(title), label))

    out, section, subsection = [], '(preamble)', ''
    bounds = [(marks[i][1], marks[i + 1][0] if i + 1 < len(marks) else len(tex))
              for i in range(len(marks))]
    chunks = [(None, None, 0, marks[0][0] if marks else len(tex))]
    chunks += [(marks[i][2], (marks[i][3], marks[i][4]), *bounds[i]) for i in range(len(marks))]

    for kind, head, lo, hi in chunks:
        if kind == 'section':
            section, subsection = head[0] + (f' [{head[1]}]' if head[1] else ''), ''
        elif kind == 'subsection':
            subsection = head[0] + (f' [{head[1]}]' if head[1] else '')
        for sent in sentences(tex[lo:hi]):
            if is_index_only(sent):
                continue
            claim = clean_claim(sent)
            if not claim:
                continue
            out.append((section, subsection, claim_id(claim), claim, exact_values(sent)))
    return out


# ---------------------------------------------------------------- ledger + results index
def text_key(claim):
    """Normalised claim text, for matching a ledger row whose ID was derived differently."""
    return re.sub(r'[^a-z0-9]+', '', claim.lower())


def ledger_rows(by_text=False):
    """{claim_id: [6 evidence cells]} from docs/claims.md.

    `by_text=True` additionally keys each row by its normalised claim text. The two parsers do not
    always agree on a claim's ID -- four claims whose ledger text carries a section-name prefix
    ("Message Candidates[label] At each frame ...") hash differently here -- and an ID-only lookup
    silently reported those rows as PENDING and then value-searched them, which is how a claim with
    committed evidence in the ledger came out labelled LEGACY-ENGINE. ID match still wins; the text
    key is only a fallback.
    """
    rows = {}
    for line in read(CLAIMS).splitlines():
        if not line.startswith('| ') or line.startswith('|---') or ' Claim ' in line:
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 9:
            continue
        rows[cells[0]] = cells[3:9]
        if by_text:
            rows.setdefault('TXT:' + text_key(cells[1]), cells[3:9])
    return rows


def results_index():
    """{filename: (generator, note)} from results/README.md."""
    idx = {}
    for line in read(RESULTS_INDEX).splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        # some generator cells contain a literal '|' inside backticks
        # (`... --train|--evaluate`), which over-splits the row; fold the middle back together
        if len(cells) > 3:
            cells = [cells[0], ' | '.join(cells[1:-1]), cells[-1]]
        if len(cells) != 3 or not cells[0].startswith('`'):
            continue
        name = cells[0].strip('`')
        if not name or name.endswith('/'):
            continue
        idx[os.path.basename(name)] = (cells[1].strip('`'), cells[2])
    return idx


# ---------------------------------------------------------------- engine classification
def module_index():
    files = [f for f in subprocess.check_output(['git', '-C', ROOT, 'ls-files'], text=True).split()
             if f.endswith('.py')]
    by_mod = {}
    for f in files:
        by_mod.setdefault(os.path.splitext(f)[0].replace('/', '.'), f)
        by_mod.setdefault(os.path.splitext(os.path.basename(f))[0], f)
    return by_mod


def import_closure(path, by_mod, seen=None):
    """Every repo .py reachable from `path` by intra-repo imports (transitively).

    Deliberately uncached: a memo keyed on the module would have to be merged into the caller's
    set, and getting that wrong silently truncates a closure (it did -- `tools/evaluate_selector.py`
    came back with 1 module instead of its whole chain, which would have mis-labelled the frozen
    replay generator ANALYTIC).
    """
    seen = seen if seen is not None else set()
    if path in seen or not os.path.exists(os.path.join(ROOT, path)):
        return seen
    seen.add(path)
    try:
        tree = ast.parse(read(os.path.join(ROOT, path)))
    except SyntaxError:
        return seen
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] + [f'{node.module}.{a.name}' for a in node.names]
        for n in names:
            tgt = by_mod.get(n) or by_mod.get(n.split('.')[-1])
            if tgt and tgt not in seen:
                import_closure(tgt, by_mod, seen)
    return seen


def classify_generator(gen_cmd, note, by_mod):
    """-> (engine, script_path or '', why)."""
    if 'P1-v3' in note:
        engine_hint = 'LEGACY-ENGINE'
        why = ['results/README.md marks the output "P1-v3"']
    else:
        engine_hint, why = None, []

    m = re.search(r'([\w/]+\.py)', gen_cmd or '')
    if not m:
        return (engine_hint or 'ANALYTIC', '', why or ['no script in the generator cell'])
    script = m.group(1)
    if not os.path.exists(os.path.join(ROOT, script)):
        alt = by_mod.get(os.path.splitext(os.path.basename(script))[0])
        script = alt or script
    if not os.path.exists(os.path.join(ROOT, script)):
        return (engine_hint or 'UNRESOLVED', script, why + ['script not found in the tree'])

    closure = import_closure(script, by_mod)
    # Match markers against MODULE NAMES and STRING LITERALS only -- never raw source text, or a
    # docstring saying "supersedes true_e2e_global.py" would tag its successor LEGACY.
    blob_parts = [os.path.splitext(os.path.basename(p))[0] for p in closure]
    for p in sorted(closure):
        full = os.path.join(ROOT, p)
        if not os.path.exists(full):
            continue
        try:
            tree = ast.parse(read(full))
        except SyntaxError:
            continue
        docstrings = {ast.get_docstring(n, clean=False) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                        ast.AsyncFunctionDef))}
        # Only PATH/MODULE-shaped literals count. A real dependency appears as `v3_eval` or
        # `data/p2/...`, never inside an English sentence -- and a provenance string that names
        # the retired engine in order to say it is NOT used would otherwise tag its replacement
        # LEGACY, which is exactly what happened to difficulty_frozen.py.
        blob_parts += [n.value for n in ast.walk(tree)
                       if isinstance(n, ast.Constant) and isinstance(n.value, str)
                       and n.value not in docstrings and not any(c.isspace() for c in n.value)]
    blob = '\n'.join(blob_parts)
    legacy = sorted({k for k in LEGACY_MARKERS if k in blob})
    frozen = sorted({k for k in FROZEN_MARKERS if k in blob})
    if legacy:
        why.append(f'closure ({len(closure)} modules) reads {", ".join(legacy)}')
        return ('LEGACY-ENGINE', script, why)
    if frozen:
        why.append(f'closure ({len(closure)} modules) reads {", ".join(frozen)}')
        return (engine_hint or 'FROZEN', script, why)
    return (engine_hint or 'ANALYTIC', script, why + [f'closure ({len(closure)} modules) reads '
                                                      'neither the frozen nor the v3 selectors'])


def evidence_engine(cells, index, by_mod):
    """Classify one ledger row from its CSV + Generator cells."""
    csv_cell, gen_cell = cells[2], cells[3]
    if not csv_cell and not gen_cell:
        return ('PENDING', '', 'evidence columns are blank')
    if csv_cell.startswith('⚠ STALE') or gen_cell.startswith('⚠ STALE'):
        return ('STALE', '', 'flagged STALE by the ledger generator')

    files = re.findall(r'[\w./-]+\.(?:csv|json|md|txt)', csv_cell + ' ' + gen_cell)
    engines, scripts, whys = set(), set(), []
    for f in files:
        gen, note = index.get(os.path.basename(f), (None, ''))
        if gen is None:
            engines.add('UNRESOLVED')
            whys.append(f'{os.path.basename(f)} not indexed in results/README.md')
            continue
        eng, script, why = classify_generator(gen, note, by_mod)
        engines.add(eng)
        if script:
            scripts.add(script)
        whys.append(f'{os.path.basename(f)} <- {gen}: {"; ".join(why)}')

    if not files:  # analytic / gate-backed evidence (tests/*.py, "analytic", main.tex Eq.)
        eng, script, why = classify_generator(gen_cell, '', by_mod)
        return (eng, script, '; '.join(why))

    for pref in ('LEGACY-ENGINE', 'UNRESOLVED', 'FROZEN', 'ANALYTIC'):
        if pref in engines:
            return (pref, ', '.join(sorted(scripts)), ' | '.join(whys))
    return ('ANALYTIC', ', '.join(sorted(scripts)), ' | '.join(whys))


# ---------------------------------------------------------------- value provenance search
RESULTS_DIR = os.path.join(ROOT, 'results')
NUM_IN_FILE = re.compile(r'[-+]?\d+\.\d+|[-+]?\d+')
# literals too common to attribute anything: modes, IoUs, budgets, small counts
BORING = {'0', '1', '2', '3', '4', '5', '8', '10', '16', '20', '100', '256', '400', '1000',
          '0.1', '0.2', '0.3', '0.5', '0.7', '0.9', '1.0', '0.10', '0.20', '0.30', '0.05',
          '0.02', '95', '99', '0.999', '0.24', '110',
          # constants that recur in nearly every file of the paper and attribute nothing
          '0.024', '1.98', '0.99', '0.495', '3.96', '0.005'}


# Standards identifiers are NAMES, not measurements: "802.11bd" and "TR 37.885" can never be
# located in a result file because nothing measured them. tools/build_pending_rulings.py already
# ruled them out of its list; keeping the definition in one place stops the two tools disagreeing
# about whether six citation sentences are "numbers with no evidence".
STANDARD_IDS = {'802.11', '37.885', '2.11', '11.0'}


def distinctive(exact: str):
    """The literals in a claim that could identify the file it came from."""
    out = []
    for tok in [t.strip() for t in exact.split(',') if t.strip()]:
        t = tok.replace(',', '')
        if t.lstrip('+-') in BORING or t in BORING:
            continue
        if t.lstrip('+-') in STANDARD_IDS:
            continue
        if '.' not in t:
            continue                                   # bare integers attribute nothing
        dec = len(t.split('.')[1])
        sig = len(t.lstrip('+-0.').replace('.', ''))
        if dec >= 3 or sig >= 3:
            out.append(t)
    return out


def results_corpus():
    """{relpath: [floats]} over every committed result file (2.8 MB; a full scan is cheap)."""
    corpus = {}
    for dirpath, _dirs, files in os.walk(RESULTS_DIR):
        for name in files:
            if not name.endswith(('.csv', '.json', '.md', '.txt')):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = read(path)
            except (UnicodeDecodeError, OSError):
                continue
            vals = []
            for m in NUM_IN_FILE.finditer(text):
                try:
                    vals.append(float(m.group(0)))
                except ValueError:
                    pass
            corpus[os.path.relpath(path, ROOT)] = vals
    return corpus


def carries(vals, literal):
    """Does this file hold a number that rounds to `literal` at the literal's own precision?"""
    target = float(literal)
    dec = len(literal.split('.')[1])
    return any(round(v, dec) == round(target, dec) for v in vals)


def locate_evidence(exact, corpus, top=3):  # noqa: D401
    """Rank result files by how many of a claim's distinctive literals they contain."""
    lits = distinctive(exact)
    if not lits:
        return [], lits
    scored = []
    for path, vals in corpus.items():
        hit = [x for x in lits if carries(vals, x)]
        if hit:
            scored.append((len(hit), path, hit))
    if not scored:
        return [], lits
    best = max(s[0] for s in scored)
    # Coverage rule, deliberately strict -- a single common literal attributes nothing.
    # >=2 literals must co-occur in the same file, unless the claim has exactly one literal and
    # that literal is precise enough (>=4 decimals) to be an identifier on its own.
    if len(lits) == 1:
        if len(lits[0].split('.')[1]) < 4:
            return [], lits
    elif best < 2:
        return [], lits
    # Among files that carry the same number of literals, the SMALLEST one is the strongest
    # candidate: a 20-row verifier CSV matching 3/3 is evidence, a 200k-value replay dump matching
    # 3/3 is mostly chance. Rank by (literals matched desc, numeric values in the file asc).
    winners = sorted([s for s in scored if s[0] == best],
                     key=lambda s: (-s[0], len(corpus[s[1]]), s[1]))[:top]
    return winners, lits


# ---------------------------------------------------------------- report
def build():
    rows = claims_by_section()
    ledger = ledger_rows(by_text=True)
    index = results_index()
    by_mod = module_index()

    corpus = results_corpus()

    per_section, tally = {}, {}
    for section, subsection, cid, claim, exact in rows:
        cells = ledger.get(cid) or ledger.get('TXT:' + text_key(claim))
        if cells is None:
            # last fallback: one text is a prefix/suffix of the other (the ledger keeps a
            # section-name prefix on three claims). Containment on >=60 normalised characters is
            # specific enough that no two distinct claims in the paper collide -- asserted below.
            k = text_key(claim)
            cand = [v for t, v in ledger.items()
                    if t.startswith('TXT:') and len(k) >= 60
                    and (k in t[4:] or t[4:] in k)]
            cells = cand[0] if len(cand) == 1 else [''] * 6
        engine, script, why = evidence_engine(cells, index, by_mod)
        found, lits = ([], [])
        if engine == 'PENDING':
            # the ledger cell is blank -- go find the number in the committed results instead
            found, lits = locate_evidence(exact, corpus)
            engines, detail, top_engine, top_script = [], [], None, ''
            for i, (_n, path, hit) in enumerate(found):
                gen, note = index.get(os.path.basename(path), (None, ''))
                if gen is None:
                    detail.append(f'{path} [{len(hit)}/{len(lits)}] (not indexed)')
                    continue
                eng, sc, _w = classify_generator(gen, note, by_mod)
                engines.append(eng)
                if top_engine is None:                 # winners are ranked most-specific first
                    top_engine, top_script = eng, sc
                mark = ' **<- most specific**' if i == 0 else ''
                detail.append(f'{path} [{len(hit)}/{len(lits)}] <- {gen} = {eng}{mark}')
            if top_engine:
                # carry the match strength into the label: a 2-of-4 hit is a hint, not an
                # attribution (e.g. a claim's "+-140.8 m" range matching an unrelated config echo),
                # and hiding the fraction would let the weak ones read as settled
                strength = f' [{len(found[0][2])}/{len(lits)}]'
                engine = top_engine + strength + (' (located, ledger cell still blank)'
                                                  if len(set(engines)) == 1
                                                  else ' (located; weaker candidates disagree)')
                script = top_script
                why = 'value search: ' + ' | '.join(detail)
            elif not lits:
                engine = 'PENDING (no distinctive number to locate)'
                why = 'claim carries only structural/definitional numbers'
            else:
                engine = 'PENDING (unlocated)'
                why = f'no committed result file carries {", ".join(lits)}'
        key = (section, subsection)
        per_section.setdefault(key, []).append((cid, claim, exact, engine, script, why, cells))
        tally[engine] = tally.get(engine, 0) + 1

    out = ["# CA-TOSG — claims evidence audit (P5 batch 3, step 1)", "",
           "Auto-generated by `python tools/audit_claims_evidence.py`. **Read-only over "
           "`paper/main.tex`, `docs/claims.md` and `results/README.md`; it edits none of them.**",
           "",
           "Each claim in `docs/claims.md` is attributed to the section it appears in, and its "
           "evidence is classified by the engine that produced it. `LEGACY-ENGINE` means the "
           "generator's import closure reads the retired v3 selector / 200-realisation policy "
           "engine / v3 global-sort scorer — **not** the frozen P2 selectors. A legacy-engine "
           "number and a frozen-replay number are different quantities and may not appear in the "
           "same sentence (PROTOCOL, \"never blend engines\").", "",
           "| engine | claims |", "|---|---|"]
    for k in sorted(tally, key=lambda k: (-tally[k], k)):
        out.append(f"| {k} | {tally[k]} |")
    out += ["", f"Total: **{sum(tally.values())}** claims across "
                f"**{len(per_section)}** (sub)sections.", ""]

    # legacy roster first -- this is what batch 3 has to act on
    out += ["## LEGACY-ENGINE roster (by section)", ""]
    any_legacy = False
    for (section, subsection), items in per_section.items():
        legacy = [i for i in items if i[3].startswith('LEGACY-ENGINE')]
        if not legacy:
            continue
        any_legacy = True
        out.append(f"**{section}{' → ' + subsection if subsection else ''}** — "
                   f"{len(legacy)}/{len(items)} claims")
        out.append("")
        out.append("| ID | claim (truncated) | generator | why LEGACY |")
        out.append("|---|---|---|---|")
        for cid, claim, _exact, _eng, script, why, _cells in legacy:
            out.append(f"| `{cid}` | {claim[:110]}{'…' if len(claim) > 110 else ''} | "
                       f"`{script}` | {why[:180]} |")
        out.append("")
    if not any_legacy:
        out += ["_None._", ""]

    out += ["## Full per-section inventory", ""]
    for (section, subsection), items in per_section.items():
        out.append(f"### {section}{' → ' + subsection if subsection else ''}")
        out.append("")
        out.append("| ID | engine | exact values | claim (truncated) |")
        out.append("|---|---|---|---|")
        for cid, claim, exact, engine, _script, _why, _cells in items:
            out.append(f"| `{cid}` | {engine} | {exact[:60]} | "
                       f"{claim[:130]}{'…' if len(claim) > 130 else ''} |")
        out.append("")
    return '\n'.join(out) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='fail if the committed audit is stale')
    args = ap.parse_args()
    text = build()
    if args.check:
        if not os.path.exists(OUT) or read(OUT) != text:
            print('docs/claims_evidence_audit.md is STALE -- re-run: '
                  'python tools/audit_claims_evidence.py')
            return 1
        print('CLAIMS EVIDENCE AUDIT: up to date')
        return 0
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'wrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
