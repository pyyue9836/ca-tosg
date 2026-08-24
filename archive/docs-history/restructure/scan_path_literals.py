#!/usr/bin/env python3
"""Tree-independent inventory of every path literal in the ca-tosg repo.

Scope: every git-tracked .py / .md / .json / .txt file (the extensions named in the
restructure brief), plus the JSON manifests' *internal* relpaths, plus python
import / sys.path machinery (those are rewrite points too even though they carry
no slash).

Output: path_literals.csv  (file,line,kind,literal,context)
        summary.txt
Nothing here depends on the target tree: it enumerates what a move would break.
"""
import csv
import json
import os
import re
import subprocess
import sys

REPO = '/home/josh/cooperative_semantic_perception/ca-tosg'
OUT = os.path.dirname(os.path.abspath(__file__))

SCAN_EXT = {'.py', '.md', '.json', '.txt'}

# extensions that make a token a path even without a slash
FILE_EXT = (r'py|csv|json|md|txt|tex|yaml|yml|pdf|svg|png|pkl|joblib|bib|npy|npz|pth|ckpt')

# a path-ish token: at least one of (contains '/', ends with a known extension)
TOK = re.compile(
    r'(?<![\w.])'
    r'((?:\.{1,2}/|/)?(?:[\w.@+-]+/)*[\w.@+-]+\.(?:' + FILE_EXT + r')\b'
    r'|(?:\.{1,2}/)?(?:[\w@+-]+/){1,}[\w@+-]*)'
)

# repo-local top-level segments that make a slash-token *ours* rather than a URL/3rd-party
LOCAL_ROOTS = (
    'paper1', 'paper2', 'paper3', 'code', 'results', 'data', 'paper', 'figures',
    'analysis_tools', 'scomcp_reproduction', 'env_setup', 'opencood_modifications',
    'p2_dataprep', 'extra_experiments', 'test_split_pipeline', 'jscc_perframe',
    'configs', 'docs', 'OpenCOOD', 'peiyi_work', 'opencood', 'opv2v_data_dumping',
)

IMPORT_RE = re.compile(r'^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))')
SYSPATH_RE = re.compile(r'sys\.path|__file__|Path\(__file__\)|os\.path\.dirname|parents\[')

NOISE = re.compile(
    r'^(https?|www\.)'                      # urls
    r'|^(github\.com|arxiv\.org)'
    r'|\.(com|org|net|io|edu)/'
)


def tracked_files():
    out = subprocess.check_output(['git', '-C', REPO, 'ls-files'], text=True)
    return [f for f in out.splitlines() if f]


def local_module_names(files):
    """python modules that live in this repo -> an `import X` of them is a rewrite point."""
    mods = set()
    for f in files:
        if f.endswith('.py'):
            mods.add(os.path.basename(f)[:-3])
    return mods


def classify(tok, path):
    if NOISE.search(tok):
        return None
    if tok.startswith('../'):
        return 'relpath_escaping_repo'
    if tok.startswith('/'):
        return 'absolute_path'
    head = tok.split('/')[0]
    if '/' in tok:
        return 'relpath_local' if head in LOCAL_ROOTS else 'relpath_other'
    return 'bare_filename'


def walk_json_paths(obj, prefix=''):
    """yield (json_pointer, value) for every string value that looks like a path."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_json_paths(v, prefix + '/' + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_json_paths(v, prefix + '[%d]' % i)
    elif isinstance(obj, str):
        if '/' in obj or re.search(r'\.(?:' + FILE_EXT + r')$', obj):
            yield prefix, obj


def main():
    files = tracked_files()
    mods = local_module_names(files)
    rows = []

    for rel in files:
        ext = os.path.splitext(rel)[1]
        if ext not in SCAN_EXT:
            continue
        full = os.path.join(REPO, rel)
        try:
            text = open(full, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        lines = text.splitlines()

        # 1. path-ish tokens, any of the four extensions
        for ln, line in enumerate(lines, 1):
            for m in TOK.finditer(line):
                tok = m.group(1)
                kind = classify(tok, rel)
                if kind is None:
                    continue
                rows.append((rel, ln, kind, tok, line.strip()[:180]))

        # 2. python-only: local imports + __file__/sys.path anchoring
        if ext == '.py':
            for ln, line in enumerate(lines, 1):
                im = IMPORT_RE.match(line)
                if im:
                    name = (im.group(1) or im.group(2) or '').split('.')[0]
                    if name in mods:
                        rows.append((rel, ln, 'local_import', name, line.strip()[:180]))
                if SYSPATH_RE.search(line):
                    rows.append((rel, ln, 'path_anchor', SYSPATH_RE.search(line).group(0),
                                 line.strip()[:180]))

        # 3. json-only: internal relpaths, addressed by json pointer (the manifest hazard)
        if ext == '.json':
            try:
                obj = json.loads(text)
            except ValueError:
                continue
            for ptr, val in walk_json_paths(obj):
                rows.append((rel, 0, 'json_internal_relpath', val, ptr))

    with open(os.path.join(OUT, 'path_literals.csv'), 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['file', 'line', 'kind', 'literal', 'context'])
        w.writerows(rows)

    # summary
    from collections import Counter
    by_kind = Counter(r[2] for r in rows)
    by_file = Counter(r[0] for r in rows)
    with open(os.path.join(OUT, 'summary.txt'), 'w') as fh:
        fh.write('scanned files: %d tracked, %d in scope (%s)\n' % (
            len(files), sum(1 for f in files if os.path.splitext(f)[1] in SCAN_EXT),
            '/'.join(sorted(SCAN_EXT))))
        fh.write('total literals: %d\n\nby kind:\n' % len(rows))
        for k, v in by_kind.most_common():
            fh.write('  %-26s %5d\n' % (k, v))
        fh.write('\ntop 30 files by literal count:\n')
        for k, v in by_file.most_common(30):
            fh.write('  %-70s %4d\n' % (k, v))
    print(open(os.path.join(OUT, 'summary.txt')).read())


if __name__ == '__main__':
    sys.exit(main())
