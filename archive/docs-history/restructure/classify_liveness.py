#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Liveness classification for the reference-gate sweep.

The plain reference graph under-reports aliveness: result files are written through f-strings
(f'r10c_decision_log_{split}_{tag}.csv'), so a literal-only graph calls a live output "dead".
Here every string literal that looks like a filename is turned into a GLOB (each {...} -> .*),
so both reads and writes are matched.

Verdicts, in priority order:
  ALIVE-IN     read by a live root (or by something a live root reaches)
  ALIVE-OUT    written by / named in a live producer, incl. f-string-built names
  ALIVE-DOC    named by an authority doc (PROTOCOL / CLAIMS / REPRODUCE / DATA_MANIFEST / main.tex)
  KEEP-P5      nothing live names it, but it is kept -- needs an explicit reason + death trigger
  DELETE       nothing live names it and the map says delete
"""
import collections
import csv
import os
import re
import subprocess

REPO = '/home/josh/cooperative_semantic_perception/ca-tosg'
OUT = os.path.dirname(os.path.abspath(__file__))
SCAN_EXT = {'.py', '.md', '.json', '.txt', '.tex', '.yaml', '.yml', '.sh'}

from build_refgraph import LIVE_ROOTS  # noqa: E402

AUTHORITY = ['paper1/PROTOCOL.md', 'paper1/CLAIMS.md', 'paper1/REPRODUCE.md',
             'paper1/results/DATA_MANIFEST.md', 'paper1/paper/main.tex', 'paper1/README.md']

STR_LIT = re.compile(r"""(?:f?['"])([^'"\n]{2,200}?\.(?:py|csv|json|md|txt|tex|yaml|yml|pdf|svg|png|pkl|pt|npz|sh))(?:['"])""")
MD_TOK = re.compile(r'[\w./@+-]*[\w@+-]\.(?:py|csv|json|md|txt|tex|yaml|yml|pdf|svg|png|pkl|pt|npz|sh)\b')
BRACE = re.compile(r'\{[^{}]*\}')


def tracked():
    return subprocess.check_output(['git', '-C', REPO, 'ls-files'], text=True).split()


def read(f):
    try:
        return open(os.path.join(REPO, f), encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


def globs_of(f):
    """every filename-ish literal in f, as a compiled basename regex"""
    txt = read(f)
    out = []
    toks = set(STR_LIT.findall(txt)) | set(MD_TOK.findall(txt))
    for t in toks:
        base = os.path.basename(t)
        if not base or base.startswith('.'):
            continue
        pat = BRACE.sub('[^/]*', re.escape(base).replace(r'\{', '{').replace(r'\}', '}'))
        pat = BRACE.sub('[^/]*', pat)
        try:
            out.append(re.compile('^' + pat + '$'))
        except re.error:
            pass
    return out


def main():
    files = tracked()
    base = {f: os.path.basename(f) for f in files}

    # transitive closure of "referenced by a live root", using globs
    live_set = set(LIVE_ROOTS)
    named = collections.defaultdict(set)     # file -> {namers}
    frontier, seen = list(LIVE_ROOTS), set()
    while frontier:
        src = frontier.pop()
        if src in seen or os.path.splitext(src)[1] not in SCAN_EXT:
            seen.add(src)
            continue
        seen.add(src)
        pats = globs_of(src)
        for f in files:
            if f == src:
                continue
            if any(p.match(base[f]) for p in pats):
                named[f].add(src)
                if f not in seen and os.path.splitext(f)[1] == '.py':
                    frontier.append(f)
                live_set.add(f)

    auth_named = set()
    for a in AUTHORITY:
        pats = globs_of(a)
        for f in files:
            if any(p.match(base[f]) for p in pats):
                auth_named.add(f)

    mp = {}
    with open(os.path.join(OUT, 'RESTRUCTURE_MAP.csv')) as fh:
        for r in csv.DictReader(fh):
            if r['row_type'] == 'FILE' and r['old_path']:
                mp[r['old_path']] = r

    rows = []
    for f in sorted(files):
        d = mp.get(f, {}).get('disposition', '?')
        if d == 'DELETE':
            v = 'DELETE'
        elif f in LIVE_ROOTS:
            v = 'LIVE-ROOT'
        elif f in named:
            v = 'ALIVE'
        elif f in auth_named:
            v = 'ALIVE-DOC'
        else:
            v = 'KEEP-P5'
        rows.append(dict(file=f, verdict=v, disposition=d,
                         new_path=mp.get(f, {}).get('new_path', ''),
                         named_by=';'.join(sorted(named.get(f, set()))[:3])))

    with open(os.path.join(OUT, 'liveness.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['file', 'verdict', 'disposition', 'new_path', 'named_by'])
        w.writeheader()
        w.writerows(rows)

    c = collections.Counter(r['verdict'] for r in rows)
    for k, v in sorted(c.items()):
        print('%-10s %3d' % (k, v))
    print('\n--- KEEP-P5 (nothing live names them) ---')
    for r in rows:
        if r['verdict'] == 'KEEP-P5':
            print('  ', r['file'])


if __name__ == '__main__':
    main()
