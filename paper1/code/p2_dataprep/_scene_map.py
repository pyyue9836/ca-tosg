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

This is the SINGLE source of scene identity for both the split (make_scene_split.py) and the leakage
gate (check_leakage.py), so the split and its audit share one definition by construction.
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
