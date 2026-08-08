#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1.5 item7: export an INDEPENDENT sample_id -> (scene, timestamp, cav_set) manifest.

Different code path from `_scene_map.py` on purpose: `_scene_map` COUNTS the first-CAV frame files
per scene and assigns contiguous sample_id BLOCKS; this script ENUMERATES the actual per-frame
(scene, timestamp) tuples by walking the OPV2V data-dumping tree, and additionally records each
scene's full numeric-CAV directory set. `check_leakage.py` then cross-checks:

  (a) INDEPENDENT-PATH AGREEMENT: this manifest's frame->scene (ordered by sample_id) must equal the
      block-counting frame->scene from `_scene_map` -- two different traversals must agree.
  (b) REAL-DATA CORRECTNESS ANCHOR: the dataset CSV's per-frame `cav_keys` (the CAV ids the original
      builder actually loaded for that frame) must be a subset of the reconstructed scene's CAV set.
      This ties the reconstruction to the build's own per-frame record, catching a mis-assignment
      that internal consistency alone could not.

CPU only, read-only over the dumping tree. Default: validate (the pre-freeze split, PROTOCOL sec 10).

Run:  python paper1/code/p2_dataprep/export_scene_manifest.py [--split validate|test|culver]
"""
import argparse
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DUMP = os.path.join(OPENCOOD, 'opv2v_data_dumping')
OUT_PROV = os.path.join(P1, 'results/p2_dataprep')
SPLIT_DUMP = {'validate': 'validate', 'test': 'test', 'culver': 'test_culver_city'}


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
    print(f'[{split}] {len(df)} frames / {len(scenes)} scenes -> {os.path.relpath(out, P1)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate', choices=['validate', 'test', 'culver'])
    build(ap.parse_args().split)


if __name__ == '__main__':
    main()
