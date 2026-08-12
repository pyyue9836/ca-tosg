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

  python tests/test_intra_repo_imports.py
"""
import ast
import os
import subprocess
import sys
import sysconfig

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = ('docs/restructure/',)

THIRD_PARTY = {
    'numpy', 'pandas', 'scipy', 'sklearn', 'torch', 'matplotlib', 'yaml', 'tensorflow', 'sionna',
    'seaborn', 'tqdm', 'PIL', 'cv2', 'open3d', 'spconv', 'easydict', 'shapely', 'numba', 'opencood',
    'tensorboardX', 'tensorboard', 'einops', 'timm',
}


def stdlib_names():
    names = set(getattr(sys, 'stdlib_module_names', ()))
    names |= set(sys.builtin_module_names)
    lib = sysconfig.get_paths().get('stdlib', '')
    if os.path.isdir(lib):
        for e in os.listdir(lib):
            names.add(e[:-3] if e.endswith('.py') else e)
    return names


def main():
    files = [f for f in subprocess.check_output(['git', '-C', ROOT, 'ls-files'], text=True).split()
             if f.endswith('.py') and not f.startswith(SKIP_DIRS)]
    owners = {}
    for f in files:
        owners.setdefault(os.path.basename(f)[:-3], []).append(f)
    # a top-level directory is importable as a namespace package (projects/, baselines/, tools/)
    pkgs = {d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d))
            and not d.startswith('.')}
    known = stdlib_names() | THIRD_PARTY
    fails, n = [], 0

    for f in files:
        p = os.path.join(ROOT, f)
        try:
            tree = ast.parse(open(p, encoding='utf-8').read())
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
                    fails.append('%s:%d imports %r -- no such module in this repository (renamed '
                                 'or deleted?)' % (f, node.lineno, m))
                elif len(owners[m]) > 1:
                    fails.append('%s:%d imports %r -- ambiguous, %d files own that name: %s'
                                 % (f, node.lineno, m, len(owners[m]), owners[m]))
                elif not os.path.exists(os.path.join(ROOT, owners[m][0])):
                    fails.append('%s:%d imports %r -> %s which does not exist'
                                 % (f, node.lineno, m, owners[m][0]))

    print('intra-repo imports: %d checked across %d files' % (n, len(files)))
    if fails:
        print('\nIMPORT GATE FAIL:')
        for f in fails:
            print('  ' + f)
        return 1
    print('IMPORT GATE PASS: every intra-repo import resolves to exactly one existing module.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
