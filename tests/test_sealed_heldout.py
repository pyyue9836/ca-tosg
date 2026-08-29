#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Gate 22 (V2-R6 A) — no live script may be able to read sealed held-out accuracy.

Work package 2 computed an ego AP and a per-frame F1 on `test` and Culver-City before the selector
freeze. Nothing tuned on it, so it was not a breach — but a number sitting where people read it can
inform a decision whether or not anyone meant it to. It was moved to `results/v2/sealed/` and the
generator was changed to require `--held-out-eval`.

**Both of those were repairs. This is the gate that makes them hold.** Sibling of `test_no_retired_writes.py`
(gate 21) and built on the same principle: judge the *capability*, not the intent. A script that can
read the path is a script that will, eventually, by accident.

WHAT IS CHECKED
  1. No live `.py` outside the allow-list may name `results/v2/sealed/` in a non-docstring string
     **and** contain a read primitive.
  2. `--held-out-eval` may only be *passed* by work package 11. Defining the flag is fine; invoking
     another script with it is not.
  3. Held-out accuracy products may exist only under `results/v2/sealed/`. An `ego_ap50` or
     `f1_ego` on a held-out split anywhere else is a leak by placement.
  4. The sealed files' sha256 are recorded (A-2), so work package 11 can prove nothing changed
     between sealing and unsealing.

Zero matches is a FAILURE, not a pass — the same rule gate 21 carries: a scan that finds nothing
because its pattern broke looks exactly like a clean tree.

    python tests/test_sealed_heldout.py [--self-test] [--write-hashes]
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEALED_DIR = os.path.join(ROOT, 'results', 'v2', 'sealed')
SEALED_REL = 'results/v2/sealed'
HASHES = os.path.join(ROOT, 'results', 'manifests', 'V2_SEALED_HASHES.json')
SKIP_DIRS = {'archive', '.git', '__pycache__', '.ipynb_checkpoints', 'node_modules'}
# the gate itself, and the one work package licensed to unseal
# V2-R29 C-1: the held-out PRODUCER must name the sealed directory, because that is where its output
# has to land (A-1). It is allow-listed as a WRITER, and the narrowing is deliberate: it prints only
# structural counts, never an accuracy number (C-6), so allow-listing it does not create a reader.
ALLOW_READ = {os.path.join('tests', 'test_sealed_heldout.py')}

# V2-R30 C-1. A producer must NAME the sealed directory to write there, but naming it is all it may
# do. `ALLOW_READ` skips every check, which is a hole: it exempts a file by NAME when this gate's
# whole principle is to judge CAPABILITY, not intent (V2-R6 A). So a writer goes here instead, and
# is still checked -- it may name the path, and it must not read from it.
ALLOW_WRITE = {os.path.join('projects', 'ca_tosg', 'evaluation', 'v2_heldout_products.py'),
               os.path.join('projects', 'ca_tosg', 'evaluation', 'v2_wp5_final.py'),
               os.path.join('projects', 'ca_tosg', 'evaluation', 'v2_wp6_generate_cues.py'),
               os.path.join('projects', 'ca_tosg', 'evaluation', 'v2_build_grid.py'),
               os.path.join('projects', 'ca_tosg', 'models', 'v2_eff_f.py')}
READ_TOKENS = ('np.load', 'load(', 'read_csv', 'read_json', 'open(', '.read(')
WP11 = 'v2_wp11_heldout_eval.py'          # does not exist yet; named so the allowance is explicit
READ_ATTRS = ('read_csv', 'read_json', 'load', 'read_text', 'read_bytes', 'read', 'readlines',
              'genfromtxt', 'loadtxt', 'glob', 'listdir', 'iglob')
HELD_OUT_TOKENS = ('ego_ap50', 'f1_ego', 'ego_f1_mean', 'f1_E', 'f1_L', 'f1_clean',
                   'eff_E', 'eff_L', 'eff_F', 'scene_equal_f1')

# V2-R29 A-1. Once WP5 runs on test, held-out F1 EXISTS -- and a scope that stopped at WP2 would let
# any debug print leak it. These names may exist ONLY under results/v2/sealed/. The list is by name
# rather than by token because a grid file's accuracy is in its rows, not its header, and a 4 KB head
# scan would not reach it.
SEALED_ONLY_NAMES = (
    'wp34_e_l_test', 'wp6_cues_test', 'wp5_final_test', 'wp5_message_test',
    'v2_grid_test', 'v2_p12_comparison_test',
    'wp34_e_l_culver', 'wp6_cues_culver', 'wp5_final_culver', 'wp5_message_culver',
    'v2_grid_culver', 'v2_p12_comparison_culver',
)


def live_py():
    for dirpath, dirnames, files in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(files):
            if fn.endswith('.py'):
                yield os.path.relpath(os.path.join(dirpath, fn), ROOT)


def _tree(rel):
    try:
        return ast.parse(open(os.path.join(ROOT, rel), encoding='utf-8').read())
    except SyntaxError:
        return None


def _docstring_ids(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if ast.get_docstring(node, clean=False) is not None and node.body \
                    and isinstance(node.body[0], ast.Expr):
                out.add(id(node.body[0].value))
    return out


def scan_reads(rel):
    """(names_sealed_path, read_calls) -- docstrings exempt, as in gate 21."""
    tree = _tree(rel)
    if tree is None:
        return False, ['<unparseable>']
    doc = _docstring_ids(tree)
    names, reads = False, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc:
            if SEALED_REL in node.value or '/sealed/' in node.value or node.value == 'sealed':
                names = True
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in READ_ATTRS:
                reads.add(fn.attr)
            elif isinstance(fn, ast.Name) and fn.id == 'open':
                mode = 'r'
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                if isinstance(mode, str) and ('r' in mode and 'w' not in mode and 'a' not in mode):
                    reads.add('open(...)')
    return names, sorted(reads)


def scan_flag(rel):
    """True if this file PASSES --held-out-eval to something.

    Three things are NOT a use, and the distinction is the whole difficulty:
      * `add_argument('--held-out-eval', ...)` -- the definition;
      * a docstring;
      * an ATTRIBUTION string naming the command, e.g. the row in
        `results_index.py` that records which generator produced a file. That is a catalogue entry,
        not an invocation, and the first draft of this gate flagged it -- a false positive that would
        have taught people to ignore the gate.

    An actual invocation passes the bare flag as its own argv element (`[..., '--held-out-eval']`),
    or embeds it in a command line handed to a shell. So: an exact-match string is a use; a longer
    string containing it is a use only if this file can spawn a process.
    """
    tree = _tree(rel)
    if tree is None:
        return False
    doc = _docstring_ids(tree)
    # The flag must be reachable from a SPAWN CALL'S OWN ARGUMENTS, not merely present in a file
    # that happens to spawn something. `results_index.py` shells out to `git ls-files` for an
    # unrelated reason while cataloguing the command in a table -- a file-level "does it spawn?"
    # test flagged it, which is a false positive that teaches people to ignore the gate.
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        fn = n.func
        is_spawn = ((isinstance(fn, ast.Attribute) and fn.attr in
                     ('run', 'call', 'check_call', 'check_output', 'Popen', 'system'))
                    or (isinstance(fn, ast.Name) and fn.id in ('system', 'execv')))
        if not is_spawn:
            continue
        for arg in list(n.args) + [k.value for k in n.keywords]:
            for c in ast.walk(arg):
                if isinstance(c, ast.Constant) and isinstance(c.value, str) \
                        and '--held-out-eval' in c.value:
                    return True
    # and a bare argv element anywhere is a use in its own right
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in doc and node.value.strip() == '--held-out-eval' \
                and not _is_add_argument(tree, node):
            return True
    return False


def _is_add_argument(tree, target):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'add_argument':
            for a in node.args:
                if a is target:
                    return True
    return False


def stray_products():
    """Held-out accuracy living outside results/v2/sealed/."""
    bad = []
    v2 = os.path.join(ROOT, 'results', 'v2')
    if not os.path.isdir(v2):
        return bad
    for fn in sorted(os.listdir(v2)):
        p = os.path.join(v2, fn)
        if not os.path.isfile(p) or not fn.endswith(('.csv', '.json')):
            continue
        if not any(s in fn for s in ('test', 'culver')):
            continue
        head = open(p, encoding='utf-8', errors='ignore').read(4096)
        for tok in HELD_OUT_TOKENS:
            if tok in head and 'SEALED' not in head and 'NOT COMPUTED' not in head:
                bad.append((os.path.relpath(p, ROOT), tok))
    return bad


def misplaced_heldout_products(v2_dir=None):
    """V2-R29 A-1: a named held-out product sitting outside results/v2/sealed/.

    `stray_products()` catches accuracy tokens in a file HEAD; this catches the file existing at all
    in the open tree. Both are needed: the grid's accuracy lives in 43,560 rows, not in its header.
    """
    bad = []
    v2 = v2_dir or os.path.join(ROOT, 'results', 'v2')
    if not os.path.isdir(v2):
        return bad
    for fn in sorted(os.listdir(v2)):
        if not os.path.isfile(os.path.join(v2, fn)):
            continue
        for stem in SEALED_ONLY_NAMES:
            if fn.startswith(stem):
                bad.append((f'results/v2/{fn}',
                            f'held-out product {stem}* may exist only under {SEALED_REL}/'))
                break
    return bad


def sealed_hashes():
    """sha256 of the sealed VALUES only.

    `README.md` is deliberately excluded. It is prose explaining the seal, not sealed content, and
    hashing it would make every documentation edit look like tampering -- a false-positive generator
    of exactly the kind this gate's own flag rule had to be narrowed twice to avoid. What A-2 needs
    protected is the numbers.
    """
    out = {}
    if os.path.isdir(SEALED_DIR):
        for fn in sorted(os.listdir(SEALED_DIR)):
            p = os.path.join(SEALED_DIR, fn)
            if os.path.isfile(p) and fn.endswith(('.json', '.csv')):
                out[fn] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return out


def sealed_read_lines(rel, root=None):
    """Lines in an allow-listed WRITER that both mention the sealed path and call a read function.

    Line-scoped on purpose: the file legitimately reads NON-sealed inputs (the WP2 npz), so a
    file-level "does it contain a read call" test would fire on every writer and be useless. What
    must never appear is a read whose target is the sealed directory.
    """
    p = os.path.join(root or ROOT, rel)
    hits = []
    try:
        lines = open(p, encoding='utf-8', errors='replace').read().splitlines()
    except OSError:
        return hits
    for i, ln in enumerate(lines, 1):
        code = ln.split('#')[0]
        if 'SEALED' not in code and 'sealed' not in code:
            continue
        if any(t in code for t in READ_TOKENS) and "'w'" not in code and '"w"' not in code:
            hits.append(f'{rel}:{i}: {ln.strip()[:90]}')
    return hits


def check(extra=()):
    bad = []
    scanned = 0
    for rel in list(live_py()) + list(extra):
        if rel in ALLOW_READ or os.path.basename(rel) == WP11:
            continue
        scanned += 1
        if rel in ALLOW_WRITE:
            # allow-listed to WRITE only: still checked, just permitted to name the path
            for h in sealed_read_lines(rel):
                bad.append((rel, f'allow-listed to WRITE only, but reads the sealed path -- {h}'))
            if scan_flag(rel):
                bad.append((rel, 'passes --held-out-eval; only work package 11 may'))
            continue
        names, reads = scan_reads(rel)
        if names and reads:
            bad.append((rel, f'names the sealed path and can read via {reads}'))
        if scan_flag(rel):
            bad.append((rel, 'passes --held-out-eval; only work package 11 may'))
    for p, tok in stray_products():
        bad.append((p, f'held-out accuracy `{tok}` outside {SEALED_REL}/'))
    return bad, scanned


def _v2r29_injections():
    """V2-R29 A-3: the EXTENDED scope must fire on the new WP3/4/5/6 test paths."""
    import tempfile
    ok = True
    for stem in ('wp34_e_l_test', 'wp6_cues_test', 'wp5_final_test', 'v2_grid_test'):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, stem + '.csv'), 'w').write('frame,f1_E\n0,0.5\n')
            fired = bool(misplaced_heldout_products(d))
            print(f'  {"FIRES  " if fired else "SILENT "}  {stem}.csv placed outside sealed/')
            ok &= fired
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, 'wp34_e_l_validate.csv'), 'w').write('frame\n0\n')
        quiet = not misplaced_heldout_products(d)
        print(f'  {"quiet  " if quiet else "FIRES  "}  wp34_e_l_VALIDATE.csv (must NOT fire)')
        ok &= quiet
    # V2-R30 C-3: the allow-listed WRITER must not be able to READ sealed content.
    import tempfile
    w = sorted(ALLOW_WRITE)[0]
    with tempfile.TemporaryDirectory() as d:
        tgt = os.path.join(d, w)
        os.makedirs(os.path.dirname(tgt), exist_ok=True)
        src = open(os.path.join(ROOT, w), encoding='utf-8').read()
        open(tgt, 'w').write(src + "\n_leak = pd.read_csv(os.path.join(SEALED, 'wp34_e_l_test.csv'))\n")
        fired = bool(sealed_read_lines(w, root=d))
        print(f'  {"FIRES  " if fired else "SILENT "}  the allow-listed WRITER made to READ sealed')
        ok &= fired
    clean = not sealed_read_lines(w)
    print(f'  {"quiet  " if clean else "FIRES  "}  the real writer as committed (must NOT fire)')
    ok &= clean
    return ok


def self_test():
    print(f'sealed files registered: {len(sealed_hashes())}')
    live, scanned = check()
    print(f'SELF-TEST: {scanned} live .py scanned -> {len(live)} violation(s) (expected 0)')
    if scanned == 0:
        print('SELF-TEST: the scan found NO files -- a broken scan looks like a clean tree')
        return 1
    fake = os.path.join('projects', 'ca_tosg', 'evaluation', '_selftest_unsealer.py')
    fabs = os.path.join(ROOT, fake)
    fired = quiet = flagged = False
    try:
        open(fabs, 'w').write('import pandas as pd\n'
                              'def go():\n'
                              '    return pd.read_csv("results/v2/sealed/wp2_f1_ego_test.csv")\n')
        fired = any(r == fake for r, _ in check(extra=[fake])[0])
        open(fabs, 'w').write('"""Mentions results/v2/sealed/ in prose only."""\n'
                              'import pandas as pd\n'
                              'def go():\n'
                              '    return pd.read_csv("results/v2/wp2_per_agent_validate.csv")\n')
        quiet = not any(r == fake for r, _ in check(extra=[fake])[0])
        open(fabs, 'w').write('import subprocess\n'
                              'def go():\n'
                              '    subprocess.run(["python", "x.py", "--held-out-eval"])\n')
        flagged = any(r == fake for r, _ in check(extra=[fake])[0])
    finally:
        if os.path.exists(fabs):
            os.remove(fabs)
    print(f'SELF-TEST: planted a reader of sealed/            -> {"FIRES" if fired else "DOES NOT FIRE"}')
    print(f'SELF-TEST: the path in a DOCSTRING only           -> {"silent" if quiet else "FIRES (over-broad)"}')
    print(f'SELF-TEST: planted a caller passing --held-out-eval -> {"FIRES" if flagged else "DOES NOT FIRE"}')
    print(f'SELF-TEST: planted file removed                   -> {"yes" if not os.path.exists(fabs) else "NO"}')
    ok = (not live) and fired and quiet and flagged and not os.path.exists(fabs)
    print('SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main() -> int:
    if '--self-test' in sys.argv:
        ok_ext = _v2r29_injections()
        r = self_test()
        return r if ok_ext else 1
    h = sealed_hashes()
    if '--write-hashes' in sys.argv:
        os.makedirs(os.path.dirname(HASHES), exist_ok=True)
        json.dump({'schema': 'catosg-v2-sealed-hashes/1',
                   'why': 'A-2: work package 11 recomputes these at unseal time. A mismatch means '
                          'something changed between sealing and unsealing -- stop and report.',
                   'files': h}, open(HASHES, 'w'), indent=1)
        print(f'wrote {os.path.relpath(HASHES, ROOT)} ({len(h)} files)')
        return 0
    bad, scanned = check()
    bad += misplaced_heldout_products()
    print(f'sealed-heldout gate: {scanned} live .py scanned, {len(h)} sealed file(s)')
    if scanned == 0 or not h:
        print('SEALED GATE FAIL: nothing scanned or nothing sealed -- a scan that finds nothing '
              'because its pattern broke looks exactly like a clean tree')
        return 1
    if os.path.exists(HASHES):
        rec = json.load(open(HASHES))['files']
        for fn, want in rec.items():
            got = h.get(fn)
            if got != want:
                bad.append((f'{SEALED_REL}/{fn}',
                            'sha256 differs from the record -- sealed content changed'))
    for p, why in bad:
        print(f'  SEAL VIOLATION [{p}]: {why}')
    if bad:
        print(f'SEALED GATE FAIL: {len(bad)} violation(s). Held-out accuracy is readable, or a '
              'sealed file changed (V2-R6 A).')
        return 1
    print('SEALED GATE PASS: no live script can read sealed held-out accuracy; hashes intact.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
