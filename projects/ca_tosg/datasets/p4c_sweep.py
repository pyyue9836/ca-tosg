#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-C semantics-A sweep: build every (split, N, branch) cache (Change-log P4-C).

Semantics A (all-or-nothing) needs eff for the FULL N-subset only, so one cache per
(split, N, branch); the ego branch is N-independent and is not rebuilt at all.

  python projects/ca_tosg/datasets/p4c_sweep.py            # run it
  python projects/ca_tosg/datasets/p4c_sweep.py --dry-run  # print the plan and the bill

Run from the OpenCOOD checkout with PYTHONPATH=. -- it shells out to p4c_infer.py, which needs the
opencood package, the dataset symlink and the GPU.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OPENCOOD = os.environ.get('CATOSG_OPENCOOD', os.getcwd())
GS = os.path.join(OPENCOOD, 'peiyi_work/paper1/gs_rerun')
MP = 'peiyi_work/paper1/pretrained_models'
SPLITS = ('validate', 'test', 'culver')
NS = (1, 2, 3)

MODEL = {
    ('late', 'validate'): f'{MP}/pointpillar_late_fusion',
    ('late', 'test'): f'{MP}/pointpillar_late_fusion_test_eval',
    ('late', 'culver'): f'{MP}/pointpillar_late_fusion_culver_eval',
    ('intermediate', 'validate'): f'{MP}/pointpillar_attentive_fusion/pointpillar_attentive_fusion_compression',
    ('intermediate', 'test'): f'{MP}/pointpillar_attentive_fusion/pointpillar_attentive_fusion_compression_test_eval',
    ('intermediate', 'culver'): f'{MP}/pointpillar_attentive_fusion/pointpillar_attentive_fusion_compression_culver_eval',
}
BASE = {'late': 'late_%s.npz', 'intermediate': 'comp_%s.npz'}     # the committed full-set caches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    opt = ap.parse_args()
    sys.path.insert(0, HERE)
    from p4c_infer import frames_needing_forward

    jobs, total = [], 0
    for n in NS:
        for split in SPLITS:
            need, nfr, _ = frames_needing_forward(split, n)
            for branch in ('late', 'intermediate'):
                out = os.path.join(GS, 'p4c_N%d' % n, '%s_%s.npz' % (branch, split))
                jobs.append((n, split, branch, len(need), out))
                total += len(need)
    print('%d jobs, %d forward passes total (~%.0f min at 0.37 s/frame)'
          % (len(jobs), total, total * 0.37 / 60), flush=True)
    for n, split, branch, k, out in jobs:
        print('   N=%d %-9s %-13s %5d forwards -> %s' % (n, split, branch, k, os.path.relpath(out, OPENCOOD)))
    if opt.dry_run:
        return 0

    t0 = time.time()
    for i, (n, split, branch, k, out) in enumerate(jobs, 1):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):
            print('[%d/%d] SKIP (exists) %s' % (i, len(jobs), os.path.relpath(out, OPENCOOD)), flush=True)
            continue
        cmd = [sys.executable, os.path.join(HERE, 'p4c_infer.py'),
               '--split', split, '--fusion', branch, '--n', str(n),
               '--model_dir', MODEL[(branch, split)],
               '--base_cache', os.path.join(GS, BASE[branch] % split), '--out', out]
        print('[%d/%d] N=%d %s %s  (%d forwards, elapsed %.1f min)'
              % (i, len(jobs), n, split, branch, k, (time.time() - t0) / 60), flush=True)
        r = subprocess.run(cmd, cwd=OPENCOOD, env={**os.environ, 'PYTHONPATH': OPENCOOD})
        if r.returncode:
            print('FAILED: %s' % ' '.join(cmd), flush=True)
            return r.returncode
    print('sweep done in %.1f min' % ((time.time() - t0) / 60), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
