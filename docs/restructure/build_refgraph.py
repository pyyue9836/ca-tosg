#!/usr/bin/env python3
"""Reference graph over the tracked tree: who references whom, and what is reachable
from the live roots (the 6 commands' current implementations + the 5 gates + the paper).

Used to decide, per file: MOVE (alive) / DELETE (dead today) / KEEP-UNTIL-P5.
"""
import collections
import csv
import json
import os
import re
import subprocess

REPO = '/home/josh/cooperative_semantic_perception/ca-tosg'
OUT = os.path.dirname(os.path.abspath(__file__))
SCAN_EXT = {'.py', '.md', '.json', '.txt', '.tex', '.yaml', '.yml'}

# the 5 gates + the current implementations behind the 6 target commands + the paper itself
LIVE_ROOTS = [
    # gates
    'paper1/code/payload_audit.py',
    'paper1/code/verify_paragraph_insert.py',
    'paper1/code/extract_claims.py',
    'paper1/code/p2_dataprep/check_leakage.py',
    'paper1/results/STALE_FINGERPRINTS.md',
    # tools/prepare_data.py
    'paper1/code/p2_dataprep/expand_grid_clean.py',
    'paper1/code/p2_dataprep/export_scene_manifest.py',
    # tools/build_bler_table.py
    'paper1/analysis_tools/build_bler_sionna.py',
    'paper1/analysis_tools/build_bler_sionna_ofdm.py',
    # tools/train_selector.py
    'paper1/code/p2_dataprep/train_p2_loso.py',
    # tools/evaluate_selector.py
    'paper1/code/p2_dataprep/eval_p2_deploy.py',
    # tools/evaluate_ap.py
    'paper1/code/p2_dataprep/eval_p2_ap.py',
    # tools/run_sensitivity.py
    'paper1/code/p2_dataprep/eval_p3_sensitivity.py',
    # tools/run_baselines.py
    'paper1/code/p2_dataprep/train_p4a_bandit.py',
    'paper1/code/p2_dataprep/eval_p4a_deploy.py',
    # tools/benchmark_latency.py
    'paper1/code/rf_latency_benchmark.py',
    # tools/generate_figures.py  (every figure generator named in REPRODUCE.md sec 3)
    'paper1/code/plot_bler_frame.py',
    'paper1/code/plot_ap_snr.py',
    'paper1/code/plot_pareto_payload.py',
    'paper1/code/snr_decision_plot.py',
    'paper1/code/plot_stacked_area.py',
    'paper1/code/plot_feature_importance.py',
    'paper1/code/extra_experiments/a2_difficulty.py',
    'paper1/code/extra_experiments/jscc_perframe/make_two_regime_figure.py',
    # the paper + its authority docs
    'paper1/paper/main.tex',
    'paper1/PROTOCOL.md',
    'paper1/CLAIMS.md',
    'paper1/REPRODUCE.md',
    'paper1/README.md',
]

FILE_TOK = re.compile(r'[\w./@+-]*[\w@+-]\.(?:py|csv|json|md|txt|tex|yaml|yml|pdf|svg|png|pkl|pt|bib)\b')


def tracked():
    return subprocess.check_output(['git', '-C', REPO, 'ls-files'], text=True).split()


def main():
    files = tracked()
    fset = set(files)
    by_base = collections.defaultdict(list)
    for f in files:
        by_base[os.path.basename(f)].append(f)

    edges = collections.defaultdict(set)      # src -> {dst}
    rev = collections.defaultdict(set)        # dst -> {src}

    for f in files:
        if os.path.splitext(f)[1] not in SCAN_EXT:
            continue
        try:
            txt = open(os.path.join(REPO, f), encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for tok in set(FILE_TOK.findall(txt)):
            base = os.path.basename(tok)
            targets = by_base.get(base, [])
            if len(targets) == 1:
                dst = targets[0]
            elif len(targets) > 1:
                # disambiguate by longest matching suffix
                cand = [t for t in targets if t.endswith(tok.lstrip('./'))]
                dst = cand[0] if len(cand) == 1 else None
            else:
                dst = None
            if dst and dst != f:
                edges[f].add(dst)
                rev[dst].add(f)

    # reachability from live roots
    alive, stack = set(), [r for r in LIVE_ROOTS if r in fset]
    missing_roots = [r for r in LIVE_ROOTS if r not in fset]
    while stack:
        n = stack.pop()
        if n in alive:
            continue
        alive.add(n)
        stack.extend(edges[n])

    rows = []
    for f in sorted(files):
        rows.append(dict(
            file=f,
            ext=os.path.splitext(f)[1],
            is_live_root=f in LIVE_ROOTS,
            reachable=f in alive,
            n_referenced_by=len(rev[f]),
            referenced_by=';'.join(sorted(rev[f])[:6]),
            n_references_out=len(edges[f]),
        ))

    with open(os.path.join(OUT, 'refgraph.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    dead = [r for r in rows if not r['reachable']]
    print('missing live roots:', missing_roots)
    print('tracked=%d  reachable=%d  unreachable=%d' % (len(files), len(alive), len(dead)))
    print('\n--- unreachable, grouped by dir ---')
    g = collections.Counter(os.path.dirname(r['file']) for r in dead)
    for k, v in sorted(g.items()):
        print('  %-46s %3d' % (k, v))
    with open(os.path.join(OUT, 'unreachable.txt'), 'w') as fh:
        for r in dead:
            fh.write('%s\t%d\t%s\n' % (r['file'], r['n_referenced_by'], r['referenced_by']))


if __name__ == '__main__':
    main()
