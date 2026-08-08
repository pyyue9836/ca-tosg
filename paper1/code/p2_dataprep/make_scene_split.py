#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 data prep (item 10): scene-level 70/30 train/dev split WITHIN validate.

SCENE-FIRST, then channel-copy expansion. The split is defined over SCENES; every channel copy of a
scene's frames inherits the scene's role, so no scene can straddle the train/dev boundary (verified
by check_leakage.py). This script never touches test/Culver -- they are one-shot final-test splits.

Determinism (LABEL-BLIND -- selection uses scene FRAME COUNTS only, never F1/oracle/any response):
with only 9 validate scenes, enumerate all 2^9 scene subsets and pick the DEV subset whose frame
fraction is closest to 0.30, tie-broken deterministically by (#scenes, sorted scene ids). This is a
pure size match to the target ratio (what "scene-level 70/30" means when the scene is the atomic
unit); it does not peek at labels, so it cannot bias the model-selection that dev is used for. The
achieved ratio is reported honestly (uneven scene sizes may prevent an exact 70/30).

Output: results/p2_dataprep/validate_scene_split.csv (scene, role, n_frames) + PROVENANCE_split.txt.
The split artifact is small and TRACKED (auditable); the expanded grid it applies to is in data/p2/.

Run:  /path/to/env/python paper1/code/p2_dataprep/make_scene_split.py
"""
import itertools
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _scene_map import scene_labels  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
OUT_PROV = os.path.join(P1, 'results/p2_dataprep')

SPLIT = 'validate'
DEV_FRAC = 0.30                                                  # target dev fraction (70/30)


def main():
    df = pd.read_csv(os.path.join(DATA, f'dataset_{SPLIT}_v3.csv'))
    _, counts = scene_labels(OPENCOOD, SPLIT, len(df))           # [(scene, n_frames), ...]
    total = sum(c for _, c in counts)
    n = len(counts)

    # LABEL-BLIND exhaustive size match: pick the dev subset whose frame fraction is closest to
    # DEV_FRAC; deterministic tie-break by (#scenes, sorted scene ids). Uses only frame counts.
    best = None
    for k in range(1, n):
        for dev_idx in itertools.combinations(range(n), k):
            dev_f = sum(counts[i][1] for i in dev_idx)
            key = (abs(dev_f / total - DEV_FRAC), k, tuple(sorted(counts[i][0] for i in dev_idx)))
            if best is None or key < best[0]:
                best = (key, set(dev_idx))
    dev_sel = best[1]
    train_scenes = [counts[i] for i in range(n) if i not in dev_sel]
    dev_scenes = [counts[i] for i in range(n) if i in dev_sel]
    if not train_scenes or not dev_scenes:
        raise SystemExit('scene split degenerate (one side empty)')

    train_f = sum(c for _, c in train_scenes); dev_f = sum(c for _, c in dev_scenes)
    rows = ([dict(scene=s, role='train', n_frames=c) for s, c in train_scenes]
            + [dict(scene=s, role='dev', n_frames=c) for s, c in dev_scenes])
    os.makedirs(OUT_PROV, exist_ok=True)
    out_csv = os.path.join(OUT_PROV, 'validate_scene_split.csv')
    pd.DataFrame(rows).sort_values(['role', 'scene']).to_csv(out_csv, index=False)

    print(f'validate scenes: {len(counts)}  frames: {total}')
    print(f'  TRAIN {len(train_scenes)} scenes / {train_f} frames ({train_f/total:.1%})')
    print(f'  DEV   {len(dev_scenes)} scenes / {dev_f} frames ({dev_f/total:.1%})')
    with open(os.path.join(OUT_PROV, 'PROVENANCE_split.txt'), 'w') as f:
        f.write("CA-TOSG P2 data prep -- validate scene-level train/dev split (make_scene_split.py)\n")
        f.write("=" * 72 + "\n")
        f.write("SCENE-FIRST split; channel copies inherit the scene role downstream (no straddle).\n")
        f.write(f"Rule: LABEL-BLIND exhaustive over the 2^{n} scene subsets; DEV = subset with frame "
                f"fraction closest to {DEV_FRAC:.0%}, tie-break (#scenes, sorted scene ids). Frame "
                f"counts only -- no F1/oracle/label used.\n")
        f.write(f"validate: {len(counts)} scenes, {total} frames.\n")
        f.write(f"  TRAIN {len(train_scenes)} scenes / {train_f} frames ({train_f/total:.4f}); "
                f"scenes={[s for s, _ in train_scenes]}\n")
        f.write(f"  DEV   {len(dev_scenes)} scenes / {dev_f} frames ({dev_f/total:.4f}); "
                f"scenes={[s for s, _ in dev_scenes]}\n")
        f.write("test / Culver-City: NOT split here (one-shot final-test splits; see PROTOCOL.md).\n")
        f.write(f"artifact: {os.path.relpath(out_csv, P1)}\n")
    print('wrote', out_csv, '+ PROVENANCE_split.txt')


if __name__ == '__main__':
    main()
