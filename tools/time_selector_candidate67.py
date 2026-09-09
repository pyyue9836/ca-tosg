#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R68 A / V2-R69 D — time the frozen selector, candidate 67.

**This measures a property of a frozen artefact, not the data.** It reads the model and the frozen
cue vectors; it opens no accuracy, action or utility field, and it touches no held-out result. The
model hash is asserted before anything is timed, so a timing can never describe a different model
than the one the paper freezes.

Why it exists: `results/latency/selector_latency.csv` measures the v1 selectors (candidates 2, 1
and 56). Quoting those for candidate 67 would be a cross-version substitution of exactly the kind
this project has paid for before.

V2-R69 D corrected three defects in the first version of this tool, each of which made the
published number describe a configuration the paper did not claim:

  D-1  the pickled forest carries ``n_jobs=-1`` from training, so ``predict`` ran on every core
       while the paper said "one CPU core". The forest is now forced to ``n_jobs=1``, the process
       is pinned to a single CPU, the BLAS thread limits are set before numpy is imported, and the
       affinity and the observed thread count are recorded beside the number.
  D-2  the channel half of the input was held at 10 dB AWGN for every trial. Real frozen cue rows
       are now crossed with the full 11-point SNR grid and both channel types, and the per-cell
       medians are recorded so a reader can see the spread rather than trust one cell.
  D-3  cue construction was timed on a synthetic Gaussian cloud. It is now timed with the
       production extractor, ``extract_pcd_features``, on real ego point clouds loaded through the
       same dataset path the cue generator uses.

    python tools/time_selector_candidate67.py [--trials 1000] [--cue-frames 100]
"""
from __future__ import annotations
import os

# D-1: the thread limits must be set before numpy, scipy or sklearn is imported -- setting them
# afterwards leaves the pools already built at their default size.
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
           'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[_v] = '1'
_CPU = int(os.environ.get('CATOSG_TIMING_CPU', '0'))
os.sched_setaffinity(0, {_CPU})

import argparse, hashlib, json, platform, sys, time                             # noqa: E402
import numpy as np, pandas as pd                                                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'projects', 'ca_tosg', 'evaluation'))
sys.path.insert(0, os.path.join(ROOT, 'projects', 'ca_tosg', 'datasets'))
FREEZE = os.path.join(ROOT, 'results', 'manifests', 'V2_PRIMARY_FREEZE.json')
OUT = os.path.join(ROOT, 'results', 'latency', 'selector_latency_candidate67.json')
# the cue file supplies INPUTS only; no accuracy, action or utility column is read
CUES = os.path.join(ROOT, 'results', 'v2', 'wp6_cues_validate.csv')
META = os.path.join(ROOT, 'results', 'v2', 'wp6_cues_validate.json')


def n_threads():
    """Threads in this process, read from the kernel rather than assumed."""
    try:
        for line in open('/proc/self/status'):
            if line.startswith('Threads:'):
                return int(line.split()[1])
    except OSError:
        pass
    return None


def cpu_model():
    """D-4 asks for the hardware. platform.processor() returns only 'x86_64' here, which names
    an architecture and not a machine, so the model is read from the kernel."""
    try:
        for line in open('/proc/cpuinfo'):
            if line.startswith('model name'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or 'unknown'


def q(v):
    return {'median_ms': float(np.median(v)), 'p5_ms': float(np.percentile(v, 5)),
            'p95_ms': float(np.percentile(v, 95)), 'n': len(v)}


def cue_construction(n_frames, n_timings):
    """D-3: the production extractor on real ego point clouds.

    Returns (timings, provenance) or (None, reason). A missing dataset is reported, never
    substituted with synthetic points -- a synthetic cloud is what D-3 exists to remove.
    """
    try:
        import v2_wp6_generate_cues as wp6
        from v2_alignment_audit import build_ds
    except Exception as e:
        return None, {'timed': False, 'reason': f'{type(e).__name__}: {e}'}
    try:
        ds = build_ds('validate')
    except SystemExit as e:
        return None, {'timed': False, 'reason': str(e)}
    clouds = []
    for i in range(min(n_frames, len(ds))):
        pts, _, _ = wp6.ego_points(ds, i)
        clouds.append(np.asarray(pts))
    ms = []
    for k in range(n_timings):
        pts = clouds[k % len(clouds)]
        t0 = time.perf_counter()
        wp6.extract_pcd_features(pts)
        ms.append((time.perf_counter() - t0) * 1e3)
    return ms, {'timed': True, 'frames_loaded': len(clouds),
                'points_per_frame': {'median': float(np.median([len(c) for c in clouds])),
                                     'min': int(min(len(c) for c in clouds)),
                                     'max': int(max(len(c) for c in clouds))},
                'function': 'extract_pcd_features -- the production extractor, imported by '
                            'v2_wp6_generate_cues from the v1 definition file',
                'covers': 'the 19 point statistics of the cue vector',
                'excludes': 'point-cloud loading and the ego pose transform, which the ego '
                            'perception stack performs for its own detection regardless'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=1000)
    ap.add_argument('--cue-frames', type=int, default=100)
    a = ap.parse_args()
    if a.trials < 1000:
        raise SystemExit('D-1 requires at least 1000 trials')

    fr = json.load(open(FREEZE))
    mp = os.path.join(ROOT, fr['selector']['model_path'])
    got = hashlib.sha256(open(mp, 'rb').read()).hexdigest()
    if got != fr['selector']['model_sha256']:
        raise SystemExit(f'model hash {got[:12]} != frozen {fr["selector"]["model_sha256"][:12]}')
    import pickle
    rf = pickle.load(open(mp, 'rb'))
    # D-1: the training-time n_jobs travels inside the pickle. Left alone it silently uses every
    # core, which is not the deployment the paper describes.
    trained_n_jobs = getattr(rf, 'n_jobs', None)
    rf.n_jobs = 1

    from grid_builder import SNR_GRID
    feat = json.load(open(META))['perception_fields']
    cues = pd.read_csv(CUES, usecols=feat)                  # inputs only, by name
    P = cues[feat].to_numpy(float)

    # D-2: real cue rows crossed with the full channel grid. Trial i takes perception row i and
    # the (SNR, channel type) cell that keeps every cell equally represented.
    cells = [(float(s), c) for c in (0.0, 1.0) for s in SNR_GRID]
    rows, cell_of = [], []
    for i in range(a.trials):
        s, c = cells[i % len(cells)]
        rows.append(np.concatenate([P[i % len(P)], [s, c]]))
        cell_of.append((s, c))
    X = np.asarray(rows)

    # warm up: the first calls pay import and allocation costs no deployed frame would
    for i in range(20):
        rf.predict(X[i:i + 1])

    inf, threads_seen = [], set()
    for i in range(a.trials):
        row = X[i:i + 1]
        t0 = time.perf_counter(); rf.predict(row); inf.append((time.perf_counter() - t0) * 1e3)
        if i % 50 == 0:
            threads_seen.add(n_threads())

    cell_ms = {}
    for (s, c), ms in zip(cell_of, inf):
        cell_ms.setdefault(f'snr{int(s)}_{"rayleigh" if c else "awgn"}', []).append(ms)
    per_cell = {k: {'median_ms': float(np.median(v)), 'n': len(v)} for k, v in cell_ms.items()}
    cell_medians = [v['median_ms'] for v in per_cell.values()]

    cue_ms, cue_prov = cue_construction(a.cue_frames, max(1000, a.trials))

    out = {'schema': 'catosg-v2-selector-latency/2',
           'what': 'Property of the FROZEN artefact. No accuracy, action or utility field is read '
                   'and no held-out result is touched.',
           'candidate_index': fr['selector']['candidate_index'],
           'model_sha256': got, 'n_estimators': len(rf.estimators_),
           'inference_batch1': q(inf),
           'inference_per_channel_cell': per_cell,
           'inference_cell_median_spread_ms': {
               'min': float(min(cell_medians)), 'max': float(max(cell_medians))},
           'input_conditions': {
               'perception_rows': 'real frozen cue rows from results/v2/wp6_cues_validate.csv',
               'snr_grid_db': [float(s) for s in SNR_GRID],
               'channel_types': ['awgn', 'rayleigh'],
               'cells': len(cells), 'batch_size': 1},
           'thread_configuration': {
               'n_jobs_forced': 1, 'n_jobs_in_pickle': trained_n_jobs,
               'cpu_affinity': sorted(os.sched_getaffinity(0)),
               'blas_env': {v: os.environ[v] for v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                                                       'MKL_NUM_THREADS')},
               'process_threads_observed': sorted(x for x in threads_seen if x is not None)},
           'cue_statistics': q(cue_ms) if cue_ms else None,
           'cue_provenance': cue_prov,
           'detector_dependency': {
               'field': 'ego_detected_box_count',
               'source': 'the ego-only detector output of the deterministic WP2 run; the cue '
                         'generator copies it and asserts equality with WP2 n_box_ego',
               'timed_here': False,
               'consequence': 'the cue vector is not complete until the ego detector this system '
                              'already runs has produced its own detections; that detector time '
                              'is not included in either number above and is not measured'},
           'hardware': {'platform': platform.platform(), 'processor': platform.processor(),
                        'cpu_model': cpu_model(), 'python': platform.python_version(),
                        'cpus_visible': os.cpu_count()},
           'command': 'python tools/time_selector_candidate67.py --trials %d --cue-frames %d'
                      % (a.trials, a.cue_frames),
           'note': 'results/latency/selector_latency.csv measures the v1 candidates (2, 1, 56) and '
                   'does not describe candidate 67.'}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, 'w'), indent=1)
    print(json.dumps({k: out[k] for k in ('inference_batch1', 'inference_cell_median_spread_ms',
                                          'cue_statistics', 'thread_configuration',
                                          'cue_provenance')}, indent=1))
    print('wrote', os.path.relpath(OUT, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
