#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard for the defect the LAYOUT restructure left behind: an import of a module that was renamed.

The restructure renamed modules (eval_p2_deploy -> deployment, train_p4a_bandit -> train, ...) and
its verification checked that every path CONSTANT still resolved. It never checked that an import
statement still resolves, so two files -- baselines/contextual_bandit/evaluate.py and
projects/ca_tosg/evaluation/p3_variants.py -- could not be executed at all, and nobody noticed
until the code was next run, weeks later.

Static, side-effect-free: the tree is parsed, never imported. For every bare `import X` /
`from X import ...` that is not a standard-library or third-party name, X must correspond to
exactly one .py file in this repository, and that file must exist.

V2-R20 D-4 — REGISTERED EXTERNAL DEPENDENCIES, AND WHY THIS IS A NARROWING RATHER THAN A LOOSENING
--------------------------------------------------------------------------------------------------
This gate used to reject *every* import it could not resolve inside this repository. It therefore
rejected `tests/test_eval_determinism.py`'s import of `catosg_eval_rng`, which really does live in
the sibling OpenCOOD checkout.

**That was not a false positive.** The module was unregistered and uncommitted, so a fresh clone of
this repository could not reproduce a single v2 product. The gate had found a genuine
reproducibility hole and merely lacked the vocabulary to name it.

The fix is not an exemption. One external dependency is now **registered** — in
`results/manifests/V2_SIBLING_DEPENDENCY.json`, pinned to an upstream base commit and to a content
hash — and an import of it is accepted **only** when every one of these holds:

  1. the importing file is exactly the registered importer (`tests/test_eval_determinism.py`);
  2. the module is exactly the registered module (`catosg_eval_rng`);
  3. the manifest exists and still registers that pair;
  4. the resolved path exists in the sibling checkout;
  5. the sibling's base commit equals the registered base commit;
  6. the file's SHA-256 equals the registered hash.

A second external module, a different importer, a moved path, a changed hash, a changed base commit
or a missing manifest all FAIL. The gate is strictly **stronger** than before: it used to check
"resolves in this repo"; it now also checks that the one thing that does not is pinned by content.

*On D-3's "the sibling worktree must be clean for these three files":* under the patch route that
cannot hold and is not claimed -- the files are modified relative to the base commit **by
construction**, which is the entire point of the patch set. Rule 6 replaces it and is stronger: a
clean worktree only says "unmodified since some commit", whereas a content hash says exactly which
bytes.

  python tests/test_intra_repo_imports.py
  python tests/test_intra_repo_imports.py --self-test    # D-5: three injections, all must FIRE
"""
import ast
import hashlib
import json
import os
import subprocess
import sys
import sysconfig

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIBLING = os.path.abspath(os.path.join(os.path.dirname(ROOT), 'OpenCOOD'))
MANIFEST = os.path.join(ROOT, 'results', 'manifests', 'V2_SIBLING_DEPENDENCY.json')
SKIP_DIRS = ('docs/restructure/',)

THIRD_PARTY = {
    'numpy', 'pandas', 'scipy', 'sklearn', 'torch', 'matplotlib', 'yaml', 'tensorflow', 'sionna',
    'seaborn', 'tqdm', 'PIL', 'cv2', 'open3d', 'spconv', 'easydict', 'shapely', 'numba', 'opencood',
    'tensorboardX', 'tensorboard', 'einops', 'timm',
    'cairosvg',      # P4-B-e: SVG->PDF export of the hand-drawn overview figure
    'pypdf',         # R40: the compile gate extracts rendered PDF text to catch a visible "??"

}


def stdlib_names():
    names = set(getattr(sys, 'stdlib_module_names', ()))
    names |= set(sys.builtin_module_names)
    lib = sysconfig.get_paths().get('stdlib', '')
    if os.path.isdir(lib):
        for e in os.listdir(lib):
            names.add(e[:-3] if e.endswith('.py') else e)
    return names


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load_manifest():
    return json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else None


def check_registered(importer, module, lineno, manifest, sibling=SIBLING):
    """[] if this (importer, module) is a fully-verified registered external dependency.

    Every failure path returns a reason. There is no branch that returns [] without having compared
    a content hash -- a registration that is trusted rather than checked would be the exemption this
    gate exists to avoid.
    """
    where = '%s:%d imports %r' % (importer, lineno, module)
    if manifest is None:
        return ['%s -- not in this repository, and no sibling-dependency manifest exists '
                '(build it with tools/build_sibling_dependency_manifest.py)' % where]
    reg = next((r for r in manifest.get('registered_external_imports', [])
                if r.get('module') == module and r.get('importer') == importer), None)
    if reg is None:
        return ['%s -- not in this repository and NOT a registered external dependency. '
                'Register it in V2_SIBLING_DEPENDENCY.json, or remove the import.' % where]
    rel = reg.get('resolves_to')
    rec = (manifest.get('files') or {}).get(rel)
    if rec is None:
        return ['%s -- registered as %s, but that path is not in the manifest file list'
                % (where, rel)]
    p = os.path.join(sibling, rel)
    if not os.path.exists(p):
        return ['%s -- registered as %s, which does not exist in the sibling checkout %s'
                % (where, rel, sibling)]
    out = []
    base = subprocess.run(['git', '-C', sibling, 'rev-parse', 'HEAD'],
                          capture_output=True, text=True).stdout.strip()
    want_base = (manifest.get('upstream') or {}).get('base_commit')
    if base != want_base:
        out.append('%s -- sibling base commit %s != registered %s'
                   % (where, base[:12], (want_base or '?')[:12]))
    got = sha256_file(p)
    if got != rec.get('sha256'):
        out.append('%s -- %s content hash %s != registered %s'
                   % (where, rel, got[:12], (rec.get('sha256') or '?')[:12]))
    return out


def scan(sources, owners, pkgs, known, manifest, sibling=SIBLING):
    """sources: iterable of (relpath, source_text). Returns (fails, n_checked)."""
    fails, n = [], 0
    for f, src in sources:
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            fails.append('%s: does not parse (%s)' % (f, e))
            continue
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split('.')[0]]
            for m in mods:
                if m in known or m in pkgs or m.startswith('_'):
                    continue
                n += 1
                if m not in owners:
                    fails += check_registered(f, m, node.lineno, manifest, sibling)
                elif len(owners[m]) > 1:
                    fails.append('%s:%d imports %r -- ambiguous, %d files own that name: %s'
                                 % (f, node.lineno, m, len(owners[m]), owners[m]))
                elif not os.path.exists(os.path.join(ROOT, owners[m][0])):
                    fails.append('%s:%d imports %r -> %s which does not exist'
                                 % (f, node.lineno, m, owners[m][0]))
    return fails, n


def repo_inputs():
    files = [f for f in subprocess.check_output(['git', '-C', ROOT, 'ls-files'], text=True).split()
             if f.endswith('.py') and not f.startswith(SKIP_DIRS)]
    owners = {}
    for f in files:
        owners.setdefault(os.path.basename(f)[:-3], []).append(f)
    pkgs = {d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d))
            and not d.startswith('.')}
    return files, owners, pkgs, stdlib_names() | THIRD_PARTY


def self_test():
    """D-5: three injections, each of which MUST make the gate fire."""
    import copy
    files, owners, pkgs, known = repo_inputs()
    manifest = load_manifest()
    if manifest is None:
        print('SELF-TEST INCONCLUSIVE: no manifest to perturb')
        return 1
    reg = manifest['registered_external_imports'][0]
    good = [(reg['importer'], 'from %s import sample_seed\n' % reg['module'])]

    base_fails, _ = scan(good, owners, pkgs, known, manifest)
    print('  baseline (registered import, untouched manifest): '
          f'{"clean" if not base_fails else "FAILS -- " + base_fails[0]}')
    if base_fails:
        print('SELF-TEST FAIL: the baseline must be clean or the injections prove nothing')
        return 1

    results = []

    m1 = copy.deepcopy(manifest)
    m1['files'][reg['resolves_to']]['sha256'] = '0' * 64
    f1, _ = scan(good, owners, pkgs, known, m1)
    results.append(('registered hash tampered', bool(f1), f1[0] if f1 else ''))

    m2 = copy.deepcopy(manifest)
    other = [(reg['importer'], 'from catosg_collab_subset import subset_of\n')]
    f2, _ = scan(other, owners, pkgs, known, m2)
    results.append(('a SECOND sibling module imported', bool(f2), f2[0] if f2 else ''))

    m3 = copy.deepcopy(manifest)
    m3['registered_external_imports'] = []
    f3, _ = scan(good, owners, pkgs, known, m3)
    results.append(('dependency registration removed', bool(f3), f3[0] if f3 else ''))

    ok = True
    for name, fired, msg in results:
        print(f'  {"FIRES  " if fired else "SILENT "}  {name}')
        if fired:
            print(f'            -> {msg[:150]}')
        ok &= fired
    print('IMPORT GATE SELF-TEST ' + ('PASS: all three injections fire' if ok else
                                      'FAIL: an injection did not fire'))
    return 0 if ok else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    files, owners, pkgs, known = repo_inputs()
    manifest = load_manifest()
    sources = []
    for f in files:
        try:
            sources.append((f, open(os.path.join(ROOT, f), encoding='utf-8').read()))
        except OSError as e:
            print('  cannot read %s (%s)' % (f, e))
            return 1
    fails, n = scan(sources, owners, pkgs, known, manifest)

    reg = (manifest or {}).get('registered_external_imports', [])
    print('intra-repo imports: %d checked across %d files, %d registered external dependency(ies)'
          % (n, len(files), len(reg)))
    for r in reg:
        print('  registered: %s may import %r -> %s (pinned by content hash)'
              % (r['importer'], r['module'], r['resolves_to']))
    if fails:
        print('\nIMPORT GATE FAIL:')
        for f in fails:
            print('  ' + f)
        return 1
    print('IMPORT GATE PASS: every import resolves to one existing module in this repository, or '
          'to a registered external dependency whose base commit and content hash both match.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
