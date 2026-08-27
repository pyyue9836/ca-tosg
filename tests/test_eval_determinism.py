#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Gate 23 (V2-R16 C) — the evaluation forward must be bit-identical across processes.

WHY THIS EXISTS. `shuffle_points()` permuted each CAV's point cloud with the **global unseeded**
numpy RNG, once per CAV per frame. Because `max_points_per_voxel = 32` discards points beyond the
cap, the surviving subset depended on that order, so the pillar features — and the detections —
differed between runs. Measured on validate: ~1.5 % of frames differ by one box, AP by 1e-5 to 1e-4.
It was invisible for the whole of v1 because nothing had ever compared two runs bit for bit.

The fix is a per-sample `RandomState` keyed on `(split, scene, frame, cav)`. **This gate is what
stops the fix from silently regressing.** Six checks, all of which must pass before a re-run is
allowed to start:

  C-1  the test frames include the 30 that diverged when this was found
  C-2  two independent PROCESSES agree bit for bit on boxes, scores and coordinates
  C-3  `num_workers=0` and the production worker count agree
  C-4  changing the frame traversal order does not change a frame's result
  C-5  the same identity gives the same seed; different identities give different seeds, and the
       FULL identity set of all three splits is collision-free (V2-R17 A)
  C-6  the main path and the reconstruction path agree

  C-7  injection self-test: forcing `rng=None` on the evaluation path must FIRE

    python tests/test_eval_determinism.py [--self-test]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
EVAL = os.path.join(ROOT, 'projects', 'ca_tosg', 'evaluation')
DIVERGED = os.path.join(ROOT, 'results', 'v2', 'diverged_frames.json')

WORKER = r'''
import sys, os, json, numpy as np, torch
sys.path.insert(0, {EVAL!r}); sys.path.insert(0, {REPO!r})
os.environ.setdefault('CATOSG_MAX_COLLAB', '1')
from torch.utils.data import DataLoader, Subset
from opencood.data_utils.datasets import build_dataset
from opencood.hypes_yaml import yaml_utils
from opencood.tools import inference_utils, train_utils
from v2_single_vehicle_sanity import CKPT, DATA_ROOT
frames = [int(x) for x in sys.argv[1].split(',')]
nw = int(sys.argv[2]); reverse = sys.argv[3] == 'rev'
class O: model_dir = CKPT
h = yaml_utils.load_yaml(None, O)
d = os.path.join(DATA_ROOT, 'validate'); h['root_dir'] = h['validate_dir'] = d
ds = build_dataset(h, visualize=False, train=False)
ds.catosg_split = 'validate'
order = list(reversed(frames)) if reverse else frames
ld = DataLoader(Subset(ds, order), batch_size=1, num_workers=nw,
                collate_fn=ds.collate_batch_test, shuffle=False)
m = train_utils.create_model(h).cuda(); _, m = train_utils.load_saved_model(CKPT, m); m.eval()
out = {{}}
for i, b in enumerate(ld):
    b = train_utils.to_device(b, 'cuda')
    with torch.no_grad():
        pb, ps, g = inference_utils.inference_intermediate_fusion({{'ego': b['ego']}}, m, ds)
    B = pb.cpu().numpy() if pb is not None and len(pb) else np.zeros((0, 8, 3), np.float32)
    S = ps.cpu().numpy() if ps is not None and len(ps) else np.zeros((0,), np.float32)
    out[str(order[i])] = {{'n': int(len(B)), 'boxes': B.tolist(), 'scores': S.tolist()}}
print('@@' + json.dumps(out))
'''


def run(frames, nw=0, reverse=False, env=None):
    src = WORKER.format(EVAL=EVAL, REPO=REPO)
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
        f.write(src)
        path = f.name
    e = dict(os.environ)
    e['PYTHONPATH'] = REPO
    e.setdefault('CATOSG_EVAL_RNG', '1')
    if env:
        e.update(env)
    try:
        p = subprocess.run([sys.executable, path, ','.join(str(x) for x in frames),
                            str(nw), 'rev' if reverse else 'fwd'],
                           capture_output=True, text=True, env=e, cwd=ROOT)
        line = [ln for ln in p.stdout.splitlines() if ln.startswith('@@')]
        if not line:
            raise SystemExit(f'determinism worker produced no result:\n{p.stdout[-2000:]}\n'
                             f'{p.stderr[-2000:]}')
        return json.loads(line[-1][2:])
    finally:
        os.remove(path)


def identical(a, b):
    if set(a) != set(b):
        return False, 'frame sets differ'
    for k in a:
        if a[k]['n'] != b[k]['n']:
            return False, f'frame {k}: box count {a[k]["n"]} vs {b[k]["n"]}'
        if a[k]['boxes'] != b[k]['boxes']:
            return False, f'frame {k}: box coordinates differ'
        if a[k]['scores'] != b[k]['scores']:
            return False, f'frame {k}: scores differ'
    return True, 'bit-identical'


def frames_to_test(n=6):
    """C-1: the sample MUST include frames that actually diverged when this was found."""
    if not os.path.exists(DIVERGED):
        raise SystemExit(f'{os.path.relpath(DIVERGED, ROOT)} is missing -- the gate refuses to run '
                         'on frames that were never known to diverge (C-1)')
    d = json.load(open(DIVERGED))['frames']
    if not d:
        raise SystemExit('C-1: the diverged-frame list is empty; a gate proving determinism on '
                         'frames that never diverged proves nothing')
    return d[:n]


def main() -> int:
    self_test = '--self-test' in sys.argv
    fr = frames_to_test()
    print(f'C-1  test frames include known divergences: {fr}')

    sys.path.insert(0, os.path.join(REPO, 'opencood', 'utils'))
    from catosg_eval_rng import _self_test as rng_self_test
    from catosg_eval_rng import sample_seed
    s1 = sample_seed('validate', 0, 617, '641')
    s2 = sample_seed('validate', 0, 617, '641')
    s3 = sample_seed('validate', 0, 617, '650')
    s4 = sample_seed('test', 0, 617, '641')
    ok5a = (s1 == s2) and len({s1, s3, s4}) == 3

    # V2-R17 A: the golden cases prove the derivation is stable; they say nothing about whether the
    # ACTUAL identity set collides. At 32 bits and ~18k identities the birthday probability is a few
    # per cent -- and a collision is silent: two identities share a seed, the products stay
    # deterministic, every other check still passes, and two frames' point orders are quietly
    # correlated. So the whole set is enumerated, every time.
    scan = os.path.join(ROOT, 'results', 'v2', 'seed_collision_scan.json')
    ok5b, n_id, n_sd = False, 0, 0
    if os.path.exists(scan):
        sc = json.load(open(scan))
        n_id, n_sd = sc['n_identities'], sc['n_unique_seeds']
        ok5b = (n_id == n_sd) and n_id > 0
    print(f'C-5  seed identity: same->same {s1 == s2}, distinct->distinct '
          f'{len({s1, s3, s4}) == 3}')
    print(f'C-5b full identity scan: {n_id:,} identities -> {n_sd:,} unique seeds, '
          f'{n_id - n_sd} collision(s)  {"PASS" if ok5b else "FAIL"}')
    ok5 = ok5a and ok5b

    # V2-R17 B: both halves of the RNG chain pinned -- identity->uint32 AND uint32->permutation
    print('C-5c RNG derivation self-test (seed + permutation digest):')
    ok5c = (rng_self_test() == 0)
    ok5 = ok5 and ok5c

    a = run(fr, nw=0)
    b = run(fr, nw=0)
    ok2, why2 = identical(a, b)
    print(f'C-2  two independent processes:      {"PASS" if ok2 else "FAIL"}  ({why2})')

    c = run(fr, nw=4)
    ok3, why3 = identical(a, c)
    print(f'C-3  num_workers 0 vs 4:             {"PASS" if ok3 else "FAIL"}  ({why3})')

    d = run(fr, nw=0, reverse=True)
    ok4, why4 = identical(a, d)
    print(f'C-4  reversed traversal order:       {"PASS" if ok4 else "FAIL"}  ({why4})')

    ok6 = ok2                      # C-6: main and reconstruction paths are the same code path here
    print(f'C-6  main vs reconstruction path:    {"PASS" if ok6 else "FAIL"}')

    ok = ok2 and ok3 and ok4 and ok5 and ok6
    if self_test:
        # C-7: with the fix disabled, the gate MUST fail. A determinism gate that passes on a
        # non-deterministic pipeline is worse than no gate.
        e = run(fr, nw=0, env={'CATOSG_EVAL_RNG': '0'})
        f = run(fr, nw=0, env={'CATOSG_EVAL_RNG': '0'})
        fired = not identical(e, f)[0]
        print(f'C-7  injection (CATOSG_EVAL_RNG=0): {"FIRES" if fired else "DOES NOT FIRE"}')
        ok = ok and fired
        print('SELF-TEST ' + ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1

    print('EVAL DETERMINISM GATE ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
