#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Work package 1 — forward invariants. Run as a precondition of every v2 product generator.

验证三动作使用相同 checkpoint hash、FOV、score threshold 和 NMS。

Everything plan A claims rests on one sentence: *the three actions differ only in what is
transmitted*. That sentence is not self-enforcing. This module turns it into an assertion that runs
before any product is written, so a drifted config cannot produce a plausible-looking result.

The reference values are read from `docs/unified_branch_protocol_v2.md` -- **not typed here** -- so a
protocol amendment cannot leave this checker behind agreeing with a retired number.

    python projects/ca_tosg/evaluation/v2_wp1_invariants.py            # check
    python projects/ca_tosg/evaluation/v2_wp1_invariants.py --self-test
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, REPO)
PROTOCOL = os.path.join(ROOT, 'docs', 'unified_branch_protocol_v2.md')
CKPT = ('/mnt/h/opencood_project/pretrained_models/pointpillar_attentive_fusion/'
        'pointpillar_attentive_fusion_compression')


def protocol_reference():
    """The invariants, parsed out of the protocol so this file holds no second copy."""
    t = open(PROTOCOL, encoding='utf-8').read()
    ref = {}
    m = re.search(r'`latest\.pth`[^|]*sha256 `([0-9a-f]{64})`', t)
    ref['weights_sha256'] = m.group(1) if m else None
    m = re.search(r'`config\.yaml`[^|]*sha256 `([0-9a-f]{64})`', t)
    ref['config_sha256'] = m.group(1) if m else None
    m = re.search(r'x ∈ \[\*\*−?([\d.]+), ([\d.]+)\*\*\], y ∈ \[\*\*−?([\d.]+), ([\d.]+)\*\*\]', t)
    if m:
        ref['x_range'] = [-float(m.group(1)), float(m.group(2))]
        ref['y_range'] = [-float(m.group(3)), float(m.group(4))]
    m = re.search(r'detection score threshold \| \*\*([\d.]+)\*\*', t)
    ref['score_threshold'] = float(m.group(1)) if m else None
    m = re.search(r'NMS IoU threshold \| \*\*([\d.]+)\*\*', t)
    ref['nms_thresh'] = float(m.group(1)) if m else None
    missing = [k for k, v in ref.items() if v is None]
    if missing:
        raise SystemExit(f'WP1: could not parse {missing} out of the protocol -- the wording moved '
                         'and this checker would otherwise pass on nothing')
    return ref


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def observed(model_dir=CKPT, hypes=None):
    from opencood.hypes_yaml import yaml_utils
    if hypes is None:
        class O:
            pass
        O.model_dir = model_dir
        hypes = yaml_utils.load_yaml(None, O)
    rng = hypes['preprocess']['cav_lidar_range']
    return {
        'weights_sha256': sha256(os.path.join(model_dir, 'latest.pth')),
        'config_sha256': sha256(os.path.join(model_dir, 'config.yaml')),
        'x_range': [float(rng[0]), float(rng[3])],
        'y_range': [float(rng[1]), float(rng[4])],
        'score_threshold': float(hypes['postprocess']['target_args']['score_threshold']),
        'nms_thresh': float(hypes['postprocess']['nms_thresh']),
    }, hypes


def check(model_dir=CKPT, hypes=None, verbose=True):
    ref = protocol_reference()
    obs, hypes = observed(model_dir, hypes)
    bad = []
    for k, want in ref.items():
        got = obs[k]
        ok = (got == want)
        if not ok:
            bad.append((k, want, got))
        if verbose:
            w = str(want)[:20] + ('…' if len(str(want)) > 20 else '')
            g = str(got)[:20] + ('…' if len(str(got)) > 20 else '')
            print(f'  {"OK  " if ok else "FAIL"}  {k:18} protocol {w:24} observed {g}')
    return bad, hypes


def assert_invariants(model_dir=CKPT, hypes=None):
    """The precondition call. Every v2 product generator invokes this before writing anything."""
    bad, hypes = check(model_dir, hypes, verbose=False)
    if bad:
        lines = '\n'.join(f'    {k}: protocol {w!r} vs observed {g!r}' for k, w, g in bad)
        raise SystemExit('WP1 FORWARD-INVARIANT FAILURE -- refusing to generate products:\n'
                         + lines)
    return hypes


def self_test():
    """A checker that cannot fail is not a checker: perturb each invariant and require a failure."""
    ref = protocol_reference()
    _, hypes = observed()
    print('SELF-TEST: perturbing each invariant in turn')
    ok = True
    import copy
    for key, path in (('score_threshold', ('postprocess', 'target_args', 'score_threshold')),
                      ('nms_thresh', ('postprocess', 'nms_thresh')),
                      ('x_range', ('preprocess', 'cav_lidar_range'))):
        h = copy.deepcopy(hypes)
        node = h
        for k in path[:-1]:
            node = node[k]
        if key == 'x_range':
            node[path[-1]] = list(node[path[-1]])
            node[path[-1]][0] = -70.4
        else:
            node[path[-1]] = float(node[path[-1]]) + 0.31
        bad, _ = check(hypes=h, verbose=False)
        fired = any(b[0] == key for b in bad)
        print(f'  {key:18} -> {"FIRES" if fired else "DOES NOT FIRE"}')
        ok &= fired
    live, _ = check(verbose=False)
    print(f'  live tree            -> {len(live)} failure(s) (expected 0)')
    ok &= not live
    print('SELF-TEST ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main() -> int:
    if '--self-test' in sys.argv:
        return self_test()
    print('WP1 forward invariants -- reference values parsed from the protocol')
    bad, _ = check()
    if bad:
        print(f'WP1 FAIL: {len(bad)} invariant(s) differ from the protocol')
        return 1
    print('WP1 PASS: checkpoint hashes, FOV, score threshold and NMS all match the protocol.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
