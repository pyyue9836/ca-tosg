#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resurrection gate (R69-2): no live script may be able to write a retired product.

Deleting a product is not the same as retiring it. R67 (c) deleted nine products after a reference
sweep, and the sweep asked "does anything READ this?" -- which is the wrong half of the question. Two
scripts could still have WRITTEN theirs:

  * `regenerate_p0_products.py` carried a job that rebuilt `c256_dominance_verify.csv`. Caught by
    hand in R67 (c) and removed there -- by luck, because nothing was checking.
  * `verify_c256_dominance.py` itself still ended in `out.to_csv(.../c256_dominance_verify.csv)`,
    and `action_dist.py` still ended in `.to_csv(.../step4_oracle_action_dist.csv)`. Both survived
    R67 (c) and R68 unnoticed. One routine run of either would have put a retired, pre-corrigendum
    product back in `results/`, where every downstream tool treats a present file as a real one.

So the register is the source of truth in BOTH directions: `tests/retired_products.md` says a path
may not be evidence, and this gate says a path may not be re-created.

METHOD, and its deliberate over-approximation. Every live `.py` is parsed with `ast`. A file fails if
it contains (a) a string constant naming a retired product, other than the module docstring, and
(b) any write primitive at all (`to_csv`, `to_json`, `savefig`, `json.dump`, `open(..., 'w'/'a')`,
`write_text`, `np.save*`, `shutil.copy*`). This over-approximates: a file that merely holds the name
in a non-docstring string and happens to write something else elsewhere fails too. That direction is
the safe one, and the escape hatch is to name the product in a comment or a docstring, which is what
a record should look like anyway. Under-approximating would mean tracing a path expression through
`os.path.join`, variables and f-strings -- and a resurrection gate that can be defeated by a variable
is not a gate.

NOT SCANNED, by design: `archive/` (nothing there is live; that is the whole point of archiving),
`tests/retired_products.md`'s own readers, and this file.

    python tests/test_no_retired_writes.py [--self-test]
"""
from __future__ import annotations

import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTER = os.path.join(ROOT, 'tests', 'retired_products.md')
SKIP_DIRS = {'archive', '.git', '__pycache__', '.ipynb_checkpoints', 'node_modules'}
# the register and this gate must be able to name the paths they are about
SKIP_FILES = {os.path.join('tests', 'test_no_retired_writes.py')}

WRITE_ATTRS = ('to_csv', 'to_json', 'to_parquet', 'savefig', 'write_text', 'write_bytes',
               'to_pickle', 'save', 'savez', 'savez_compressed', 'dump', 'copy', 'copyfile',
               'copy2', 'move', 'writerow', 'writerows')


def retired_paths():
    """Every `results/...` path the register names, with simple {a,b} brace forms expanded.

    The register writes families as `a2_difficulty{,_reliable}.csv` and
    `true_e2e_global_{test,validate}.csv`; a gate that took those literally would protect neither.
    """
    if not os.path.exists(REGISTER):
        raise SystemExit('tests/retired_products.md is missing -- the register IS this gate')
    out = set()
    # ONLY the first cell of a table row is the retired product. The later columns say what REPLACED
    # it, and those are live products: a naive `results/...` sweep over the file pulled in
    # replay_summary.csv, action_distribution.csv, frozen_curves.csv, difficulty_frozen.csv and
    # feature_importance_frozen.csv and reported 20 "resurrection risks", every one of them a
    # generator doing its job. Same anchored rule p6_numbers_vs_csv.retired_products() uses.
    for line in open(REGISTER, encoding='utf-8').read().splitlines():
        m = re.match(r'^\|\s*`(results/[^`]+)`\s*\|', line)
        if not m:
            continue
        path = m.group(1)
        b = re.search(r'\{([^}]*)\}', path)
        for alt in (b.group(1).split(',') if b else ['']):
            out.add(path[:b.start()] + alt + path[b.end():] if b else path)
    if not out:
        raise SystemExit('no retired product rows parsed from tests/retired_products.md -- the '
                         'table format changed and this gate would silently pass on everything')
    return sorted(out)


def live_py_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if not fn.endswith('.py'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            if rel not in SKIP_FILES:
                yield rel


def scan(rel, names):
    """Return (matched_names, write_calls) for one file. Docstrings are exempt: a record is allowed
    to say what was deleted, and that is how a script explains its own history."""
    try:
        tree = ast.parse(open(os.path.join(ROOT, rel), encoding='utf-8').read())
    except SyntaxError as e:
        return [f'<unparseable: {e}>'], ['<unparseable>']
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d is not None and node.body and isinstance(node.body[0], ast.Expr):
                docstrings.add(id(node.body[0].value))
    matched, writes = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            for name in names:
                if name in node.value or os.path.basename(name) in node.value:
                    matched.add(name)
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in WRITE_ATTRS:
                writes.add(fn.attr)
            elif isinstance(fn, ast.Name) and fn.id == 'open':
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == 'mode' and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if isinstance(mode, str) and ('w' in mode or 'a' in mode or 'x' in mode):
                    writes.add(f"open(..., {mode!r})")
    return sorted(matched), sorted(writes)


def check(names, extra_root_files=()):
    bad = []
    for rel in list(live_py_files()) + list(extra_root_files):
        matched, writes = scan(rel, names)
        if matched and writes:
            bad.append((rel, matched, writes))
    return bad


def self_test():
    """Plant a script that writes a retired path and require the gate to fire on it."""
    names = retired_paths()
    print(f'retired products registered: {len(names)}')
    live = check(names)
    print(f'SELF-TEST: the live tree -> {len(live)} violation(s) (expected 0)')
    victim = names[0]
    fake_rel = os.path.join('projects', 'ca_tosg', 'evaluation', '_selftest_resurrector.py')
    fake_abs = os.path.join(ROOT, fake_rel)
    src = ('"""A docstring may name %s freely -- that must NOT fire."""\n'
           'import pandas as pd\n'
           'def go(df):\n'
           '    df.to_csv("%s", index=False)\n' % (victim, victim))
    fired = docstring_quiet = False
    try:
        with open(fake_abs, 'w', encoding='utf-8') as f:
            f.write(src)
        fired = any(r == fake_rel for r, _m, _w in check(names, extra_root_files=[fake_rel]))
        # and the docstring-only half must stay silent, or the gate is just a name grep
        with open(fake_abs, 'w', encoding='utf-8') as f:
            f.write('"""Mentions %s in prose only."""\nimport pandas as pd\n'
                    'def go(df):\n    df.to_csv("results/main/replay_summary.csv")\n' % victim)
        docstring_quiet = not any(r == fake_rel
                                  for r, _m, _w in check(names, extra_root_files=[fake_rel]))
    finally:
        if os.path.exists(fake_abs):
            os.remove(fake_abs)
    print(f'SELF-TEST: planted a script writing {victim} -> {"FIRES" if fired else "DOES NOT FIRE"}')
    print(f'SELF-TEST: the same name in a DOCSTRING only -> '
          f'{"silent" if docstring_quiet else "FIRES (over-broad)"}')
    print(f'SELF-TEST: planted file removed -> {"yes" if not os.path.exists(fake_abs) else "NO"}')
    ok = not live and fired and docstring_quiet and not os.path.exists(fake_abs)
    print('SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main() -> int:
    if '--self-test' in sys.argv:
        return self_test()
    names = retired_paths()
    bad = check(names)
    print(f'resurrection gate: {len(names)} retired product path(s) from '
          f'tests/retired_products.md, checked against every live .py')
    for rel, matched, writes in bad:
        print(f'  RESURRECTION RISK [{rel}]: names {matched} and can write via {writes}')
    if bad:
        print(f'RESURRECTION GATE FAIL: {len(bad)} live script(s) can re-create a retired product '
              '(R69-2). Remove the write, or archive the script under archive/retired-scripts/.')
        return 1
    print('RESURRECTION GATE PASS: no live script can write a retired product.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
