#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstruct frame -> scene for an OPV2V split from the data-dumping directory.

The per-frame dataset (dataset_{split}_v3.csv) carries a running sample_id 0..n-1 but NO scene
column. The OpenCOOD dataset builder iterates scenes in sorted directory order, each scene's frames
contiguous, so sample_id decomposes into contiguous per-scene blocks. We rebuild the block
boundaries by counting the frame files of a scene's first numeric CAV directory (the timestamp
count is identical for every CAV in a scene) and ASSERT the reconstructed total equals the dataset
length -- fail-closed if the scene-order assumption is ever violated (then a scene split cannot be
trusted, so we refuse rather than guess).

This is the SINGLE source of scene identity for the LOSO folds (selector.py) and the leakage
gate (test_data_leakage.py), so the folds and their audit share one definition by construction.
"""
import os

# dataset split name -> data-dumping directory name
SPLIT_DUMP = {'validate': 'validate', 'test': 'test', 'culver': 'test_culver_city'}


def _scene_frame_counts(opencood_root, split):
    d = os.path.join(opencood_root, 'opv2v_data_dumping', SPLIT_DUMP[split])
    if not os.path.isdir(d):
        raise SystemExit(f'scene map: dumping dir absent -> {d} (cannot reconstruct scenes)')
    scenes = sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)))
    counts = []
    for s in scenes:
        sd = os.path.join(d, s)
        cavs = sorted(c for c in os.listdir(sd)
                      if c.isdigit() and os.path.isdir(os.path.join(sd, c)))
        if not cavs:
            raise SystemExit(f'scene map: no numeric CAV dir in {sd}')
        cav = cavs[0]
        n = sum(1 for f in os.listdir(os.path.join(sd, cav))
                if f.endswith('.yaml') and 'additional' not in f and 'data_protocol' not in f)
        counts.append((s, n))
    return counts


def scene_labels(opencood_root, split, n_frames):
    """Return (labels, counts): labels[i] = scene id of frame sample_id=i (length n_frames);
    counts = [(scene, n_frames_in_scene), ...] in sorted-dir order. Asserts sum == n_frames."""
    counts = _scene_frame_counts(opencood_root, split)
    total = sum(c for _, c in counts)
    if total != n_frames:
        raise SystemExit(
            f'{split}: reconstructed {total} frames from {len(counts)} scene dirs != dataset '
            f'{n_frames}. The contiguous-scene-block assumption is broken; refusing to build a '
            f'scene split on an unverified frame->scene map.')
    labels = []
    for s, c in counts:
        labels += [s] * c
    return labels, counts


# ---------------------------------------------------------------------------------------------
# INDEPENDENT scene manifest (was code/p2_dataprep/export_scene_manifest.py; folded in here so both
# scene traversals live in the plan's single datasets/scene_split.py).
#
# Different code path from scene_labels() ON PURPOSE: scene_labels COUNTS the first-CAV frame files
# per scene and assigns contiguous sample_id BLOCKS; build() below ENUMERATES the actual per-frame
# (scene, timestamp) tuples and records each scene's full numeric-CAV set. tests/test_data_leakage.py
# cross-checks the two against each other, and both against the dataset CSV's own per-frame cav_keys.
#
# Run:  python tools/prepare_data.py --scene-manifest [--split validate|test|culver]
# ---------------------------------------------------------------------------------------------
import argparse

import pandas as pd

_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
_OPENCOOD = os.path.join(os.path.dirname(_ROOT), 'OpenCOOD')
DUMP = os.path.join(_OPENCOOD, 'opv2v_data_dumping')
OUT_PROV = os.path.join(_ROOT, 'results/manifests')


def _numeric_cavs(scene_dir):
    return sorted(c for c in os.listdir(scene_dir)
                  if c.isdigit() and os.path.isdir(os.path.join(scene_dir, c)))


def build(split):
    root = os.path.join(DUMP, SPLIT_DUMP[split])
    if not os.path.isdir(root):
        raise SystemExit(f'dumping dir absent -> {root}')
    scenes = sorted(x for x in os.listdir(root) if os.path.isdir(os.path.join(root, x)))
    rows = []
    for s in scenes:
        sd = os.path.join(root, s)
        cavs = _numeric_cavs(sd)
        if not cavs:
            raise SystemExit(f'no numeric CAV dir in {sd}')
        cav_set = '|'.join(cavs)                                 # full scene CAV set (all timestamps)
        ego = cavs[0]                                            # enumerate timestamps off the first CAV
        stamps = sorted(f[:-5] for f in os.listdir(os.path.join(sd, ego))
                        if f.endswith('.yaml') and 'additional' not in f and 'data_protocol' not in f)
        for ts in stamps:
            rows.append(dict(scene=s, timestamp=ts, scene_cav_set=cav_set))
    df = pd.DataFrame(rows)
    df.insert(0, 'sample_id', range(len(df)))
    os.makedirs(OUT_PROV, exist_ok=True)
    out = os.path.join(OUT_PROV, f'scene_manifest_{split}.csv')
    df.to_csv(out, index=False)
    print(f'[{split}] {len(df)} frames / {len(scenes)} scenes -> {os.path.relpath(out, _ROOT)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate', choices=['validate', 'test', 'culver'])
    build(ap.parse_args().split)


if __name__ == '__main__':
    main()
