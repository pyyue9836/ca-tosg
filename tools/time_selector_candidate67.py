#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R68 A — time the frozen selector, candidate 67.

**This measures a property of a frozen artefact, not the data.** It reads the model and the frozen
cue vectors; it opens no accuracy, action or utility field, and it touches no held-out result. The
model hash is asserted before anything is timed, so a timing can never describe a different model
than the one the paper freezes.

Why it exists: `results/latency/selector_latency.csv` measures the v1 selectors (candidates 2, 1
and 56). Quoting those for candidate 67 would be a cross-version substitution of exactly the kind
this project has paid for before.

    python tools/time_selector_candidate67.py [--trials 1000]
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, subprocess, sys, time
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREEZE = os.path.join(ROOT, 'results', 'manifests', 'V2_PRIMARY_FREEZE.json')
OUT = os.path.join(ROOT, 'results', 'latency', 'selector_latency_candidate67.json')
# the cue file supplies INPUTS only; no accuracy, action or utility column is read
CUES = os.path.join(ROOT, 'results', 'v2', 'wp6_cues_validate.csv')
META = os.path.join(ROOT, 'results', 'v2', 'wp6_cues_validate.json')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--trials', type=int, default=1000)
    a = ap.parse_args()
    fr = json.load(open(FREEZE))
    mp = os.path.join(ROOT, fr['selector']['model_path'])
    got = hashlib.sha256(open(mp, 'rb').read()).hexdigest()
    if got != fr['selector']['model_sha256']:
        raise SystemExit(f'model hash {got[:12]} != frozen {fr["selector"]["model_sha256"][:12]}')
    import pickle
    rf = pickle.load(open(mp, 'rb'))

    feat = json.load(open(META))['perception_fields']
    cues = pd.read_csv(CUES, usecols=feat)          # inputs only, by name
    X = np.column_stack([cues[feat].to_numpy(float)[:a.trials],
                         np.full(a.trials, 10.0), np.zeros(a.trials)])

    # warm up: the first call pays import and allocation costs that no deployed frame would
    for i in range(20):
        rf.predict(X[i:i + 1])

    inf = []
    for i in range(a.trials):
        row = X[i % len(X):i % len(X) + 1]
        t0 = time.perf_counter(); rf.predict(row); inf.append((time.perf_counter() - t0) * 1e3)

    # cue construction: the 19 point statistics over a representative sweep. Timed on a synthetic
    # cloud of the median measured size, because the statistic cost depends on the point count and
    # not on the scene; the size is taken from the frozen cue table's own column.
    npts = int(cues['ego_pcd_num_points'].median()) if 'ego_pcd_num_points' in cues else 40000
    rng = np.random.default_rng(0)
    cloud = rng.normal(0, 30, size=(npts, 4)).astype(np.float32)
    cue_ms = []
    for _ in range(max(50, a.trials // 10)):
        t0 = time.perf_counter()
        r = np.linalg.norm(cloud[:, :2], axis=1)
        _ = (len(cloud), r.mean(), r.max(), r.std(),
             (r < 20).sum(), ((r >= 20) & (r < 50)).sum(), ((r >= 50) & (r < 80)).sum(),
             (r >= 80).sum(), (cloud[:, 0] > 0).sum(), (cloud[:, 0] <= 0).sum(),
             (cloud[:, 1] > 0).sum(), (cloud[:, 1] <= 0).sum())
        cue_ms.append((time.perf_counter() - t0) * 1e3)

    def q(v):
        return {'median_ms': float(np.median(v)), 'p5_ms': float(np.percentile(v, 5)),
                'p95_ms': float(np.percentile(v, 95)), 'n': len(v)}

    out = {'schema': 'catosg-v2-selector-latency/1',
           'what': 'Property of the FROZEN artefact. No accuracy, action or utility field is read '
                   'and no held-out result is touched.',
           'candidate_index': fr['selector']['candidate_index'],
           'model_sha256': got, 'n_estimators': len(rf.estimators_),
           'inference_batch1': q(inf), 'cue_statistics': q(cue_ms),
           'cue_points_used': npts,
           'hardware': {'platform': platform.platform(), 'processor': platform.processor(),
                        'python': platform.python_version(),
                        'threads': os.cpu_count()},
           'command': 'python tools/time_selector_candidate67.py --trials %d' % a.trials,
           'note': 'results/latency/selector_latency.csv measures the v1 candidates (2, 1, 56) and '
                   'does not describe candidate 67.'}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, 'w'), indent=1)
    print(json.dumps({k: out[k] for k in ('inference_batch1', 'cue_statistics', 'cue_points_used')},
                     indent=1))
    print('wrote', os.path.relpath(OUT, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
