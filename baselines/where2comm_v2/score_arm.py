#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R51: score a Where2comm grid point with the FROZEN chain, and run the arm's own GT assertion.

Plan v2 §d: the arm is scored by the same functions as every mainline number
(`projects/ca_tosg/evaluation/end_to_end_ap.py` → `opencood.utils.eval_utils`, global-sort AP over
one canonical GT), never by the retired `true_e2e_global.py` selector chain.

The GT-count assertion is a **pre-condition on reporting**, and it fails loudly rather than
skipping — the R48-5 lesson. A scorer that sees a different GT set produces numbers that cannot be
compared with anything in the paper, and the failure is silent unless something asserts.

    python score_arm.py --npz <cache> [--split validate] [--gt-ref results/sensitivity/gt_audit.csv]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
sys.path.insert(0, os.environ.get('OPENCOOD_ROOT',
                                  os.path.expanduser('~/cooperative_semantic_perception/OpenCOOD')))

import end_to_end_ap as E  # noqa: E402  the frozen scorer


def gt_reference(split):
    """(frames, mean GT objects per frame) for this split, from the committed audit product.

    `gt_object_stats.csv` stores the per-frame MEAN (`mean_late_num_gt`, 1 dp) and the frame count,
    not a total -- so the assertion compares those two quantities rather than inventing a total the
    product does not carry.
    """
    import pandas as pd
    # V2-R38 D-2: read the v2 CORNER-filter reference, not the v1 CENTRE-filter one. The old
    # assertion judged a v2 arm against v1's GT convention -- a convention mismatch, not a data
    # fault (centre 27.78 vs corner 26.83). This is NOT a loosened guard: it is the same guard
    # reading the reference that matches the products it is checking. The v1 file is untouched.
    p = os.path.join(ROOT, 'results/v2/gt_audit_v2_corner.csv')
    if not os.path.exists(p):
        return None, p
    d = pd.read_csv(p)
    row = d[d['split'].astype(str).str.lower() == split.lower()]
    if len(row) != 1:
        return None, p
    return (int(row.iloc[0]['n']), float(row.iloc[0]['mean_gt_corner'])), p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True)
    ap.add_argument('--split', default=None)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()

    z = np.load(a.npz, allow_pickle=True)
    boxes, scores, gts = list(z['boxes']), list(z['scores']), list(z['gts'])

    # V2-R39 B-1: a frame with ZERO predictions is stored by numpy as a 0-dimensional object array,
    # and `caluclate_tp_fp` indexes `det_score[order]`, which raises on a 0-d array. At threshold
    # 1.1 (no communication at all) six test frames legitimately produce no detection above the
    # frozen 0.20 score threshold; Culver produces none, which is why only test failed.
    #
    # Normalised HERE, in the arm, and deliberately NOT in end_to_end_ap.py: that scorer is the
    # canonical one behind the FROZEN v1 products, and editing it would put a v1 number at risk to
    # fix a v2 arm's edge case. An empty prediction set contributes zero TPs and zero FPs, so this
    # changes no score anywhere -- it only stops an empty array being mis-shaped.
    def _norm(arr, shape):
        a_ = np.asarray(arr)
        return a_ if a_.ndim == len(shape) and a_.size else np.zeros((0,) + shape[1:], np.float32)
    n_empty = sum(1 for x in scores if np.asarray(x).ndim == 0 or np.asarray(x).size == 0)
    boxes = [_norm(b, (0, 8, 3)) for b in boxes]
    scores = [_norm(s_, (0,)) for s_ in scores]
    if n_empty:
        print(f'  {n_empty} frame(s) with zero predictions normalised to shape (0,) -- '
              f'they contribute no TP and no FP')
    rate = np.asarray(z['comm_rate'], dtype=float)
    thr = float(z['threshold'])
    meta_p = os.path.splitext(a.npz)[0] + '.json'
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    split = a.split or meta.get('split')

    gt_counts = [len(g) if g is not None else 0 for g in gts]
    gt_total = int(sum(gt_counts))

    # --- GT assertion: loud, never skipped -----------------------------------------------
    ref, ref_path = gt_reference(split) if split else (None, '')
    if ref is None:
        print(f'GT ASSERTION UNAVAILABLE: no per-split reference could be read from {ref_path}. '
              f'This is a FAIL, not a skip: an unverifiable GT set makes every AP below '
              f'incomparable with the paper.')
        return 1
    n_ref, mean_ref = ref
    mean_here = gt_total / max(1, len(gts))
    if len(gts) != n_ref or abs(mean_here - mean_ref) > 0.05:
        print(f'GT ASSERTION FAIL [{split}]: this arm sees {len(gts)} frames at {mean_here:.2f} '
              f'GT objects/frame; the committed audit says {n_ref} frames at {mean_ref:.2f}. '
              f'The scorers are not looking at the same scene set.')
        return 1
    print(f'GT assertion PASS [{split}]: {len(gts)} frames, {mean_here:.2f} GT objects/frame '
          f'against {mean_ref:.2f} in {os.path.basename(ref_path)}')

    # --- AP with the frozen chain --------------------------------------------------------
    ST = [E.frame_stats(b, s, E.tt(g, (0, 8, 3))) for b, s, g in zip(boxes, scores, gts)]
    picks = [0] * len(ST)                       # one branch here: this arm's own output
    ap30, ap50, ap70 = E.ap_pick(picks, [ST], gt_counts)

    out = {
        'schema': 'catosg-where2comm-v2-score/1',
        'split': split, 'threshold': thr, 'frames': len(boxes),
        'gt_objects': gt_total, 'mean_comm_rate': float(rate.mean()) if rate.size else None,
        'ap_30': round(float(ap30), 5), 'ap_50': round(float(ap50), 5),
        'ap_70': round(float(ap70), 5),
        'scorer': 'projects/ca_tosg/evaluation/end_to_end_ap.py (global-sort, one canonical GT)',
        'collaborators': meta.get('collaborators'),
    }
    print(json.dumps(out, indent=2))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, 'w') as f:
            json.dump(out, f, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
