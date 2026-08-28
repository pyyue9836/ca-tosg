#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R19 A — identity alignment of the work-package-2 products. Zero GPU.

WHAT THIS CHECKS, AND WHY ITS CORRECT VALUE IS 100 %
----------------------------------------------------
Every quantity below is an *identity* — a frame either is the frame it claims to be, or the product
is misindexed. There is no legitimate partial reading, so anything under 100 % is a defect and stops
the batch.

    A  frame index integrity   the 1980 / 2170 / 550 rows are 0..N-1: complete, unique, ordered,
                               and the CSV, the JSON summary and the NPZ agree on them
    B  collaborator identity   the CAV that `subset_of` selects is the nearest collaborator by
                               Euclidean distance on lidar_pose[0:2], ties by ascending id --
                               re-derived here INDEPENDENTLY and compared frame by frame
    C  row-1 binding           row 1 of the stacked voxel tensor -- the row WP2 reads as "the
                               collaborator" -- carries that CAV and no other, proved by a
                               bit-comparison against an explicit single-id keep list
    D  payload binding         N_box,t is the SELECTED COLLABORATOR's box count: not the ego's, not
                               a sum over all CAVs; and B_L,t is that count through the sec-4.2 chain

NOT what this checks. It is unrelated to `collab_box_overlap_with_ego` (the 73.6 % figure), which is
a *coordinate-frame* diagnostic and whose correct value is NOT 100 % -- see
`frame_overlap()` in `v2_wp34_e_l_products.py` and the V2-R19 A-1 entry in the change log.

ON THE SECOND IMPLEMENTATION IN PART B. The protocol forbids re-implementing the collaborator rule
in a *product* path, because two definitions drift. An audit is the one place where a second,
independent derivation is the point: it is compared against `subset_of` and never consumed by
anything downstream. It is confined to `nearest_collaborator()` below.

    python projects/ca_tosg/evaluation/v2_alignment_audit.py --split validate
    python projects/ca_tosg/evaluation/v2_alignment_audit.py --split all
"""
from __future__ import annotations

import argparse
import copy
import functools
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('CATOSG_MAX_COLLAB', '1')
os.environ.setdefault('CATOSG_EVAL_RNG', '1')

import torch                                                                    # noqa: E402

from opencood.data_utils import datasets as ocd                                 # noqa: E402
from opencood.data_utils.datasets import basedataset, build_dataset             # noqa: E402
from opencood.hypes_yaml import yaml_utils                                      # noqa: E402
from opencood.utils import catosg_collab_subset, pcd_utils                      # noqa: E402

from v2_single_vehicle_sanity import CKPT, DATA_ROOT                            # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', 'v2')
SPLIT_DIR = {'validate': 'validate', 'test': 'test', 'culver': 'test_culver_city'}

# sec 4.1 / 4.2 -- the L transport chain, restated here so part D does not import a product module
B_BOX_BITS, P_PAYLOAD, H_HDR, K_INFO, N_CW_LEN, M_QAM = 184, 8000, 320, 500, 1000, 16


def l_chain(n_box):
    """sec 4.2: N_box,t -> info bits -> packets (tail unpadded) -> codewords -> Msym."""
    info = n_box * B_BOX_BITS
    if info == 0:
        return 0, 0.0
    n_full, tail = divmod(info, P_PAYLOAD)
    pkts = [P_PAYLOAD] * n_full + ([tail] if tail else [])
    n_cw = sum(math.ceil((p + H_HDR) / K_INFO) for p in pkts)
    return n_cw, n_cw * N_CW_LEN / math.log2(M_QAM) / 1e6


def _id_key(cav_id):
    """Ascending CAV id -- INDEPENDENT re-derivation, deliberately not imported."""
    s = str(cav_id)
    return (0, int(s), '') if s.lstrip('-').isdigit() else (1, 0, s)


def nearest_collaborator(base_data_dict, ego_pose):
    """The nearest non-ego CAV by Euclidean distance on lidar_pose[0:2], ties by ascending id.

    A SECOND implementation of the sec-2 rule, written from the protocol text, existing only to be
    compared against `catosg_collab_subset.subset_of`. Nothing downstream consumes it.
    """
    others = []
    for cav_id, content in base_data_dict.items():
        if content['ego']:
            continue
        p = content['params']['lidar_pose']
        others.append((math.hypot(p[0] - ego_pose[0], p[1] - ego_pose[1]), _id_key(cav_id), cav_id))
    if not others:
        return None, None
    others.sort(key=lambda t: (t[0], t[1]))
    return others[0][2], others[0][0]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def input_hashes(split):
    """V2-R20 B-1: the products this verdict was computed FROM.

    Without these the standing gate would be vacuous -- it would re-read a JSON that says 100 % and
    believe it, even after the products underneath had moved. The gate recomputes these and fails on
    any drift, which is what makes a stored verdict worth trusting between full re-walks.
    """
    out = {}
    for name in (f'wp2_per_agent_{split}.csv', f'wp2_per_agent_{split}.npz',
                 f'wp34_e_l_{split}.csv'):
        p = os.path.join(OUT_DIR, name)
        if os.path.exists(p):
            out[name] = sha256_file(p)
    return out


def load_products(split):
    import pandas as pd
    wp2_csv = os.path.join(OUT_DIR, f'wp2_per_agent_{split}.csv')
    wp2_json = os.path.join(OUT_DIR, f'wp2_per_agent_{split}.json')
    npz = os.path.join(OUT_DIR, f'wp2_per_agent_{split}.npz')
    for p in (wp2_csv, wp2_json, npz):
        if not os.path.exists(p):
            raise SystemExit(f'missing work-package-2 product: {os.path.relpath(p, ROOT)}')
    wp34 = os.path.join(OUT_DIR, f'wp34_e_l_{split}.csv')
    return (pd.read_csv(wp2_csv), json.load(open(wp2_json)),
            np.load(npz, allow_pickle=True),
            pd.read_csv(wp34) if os.path.exists(wp34) else None)


def part_a_index(df, meta, d):
    """Frame index integrity. Correct value: every count equals N, every mismatch list empty."""
    n_rows, n_ds = len(df), int(meta['dataset_frames'])
    f = df.frame.to_numpy()
    expected = np.arange(n_ds)
    npz_f = np.asarray(d['frames'])
    vals, counts = np.unique(f, return_counts=True)
    r = {
        'rows': n_rows, 'dataset_frames': n_ds,
        'every': int(meta.get('every', 1)),
        'rows_equals_dataset_frames': bool(n_rows == n_ds),
        'missing_indices': [int(x) for x in np.setdiff1d(expected, f)],
        'duplicate_indices': [int(x) for x in vals[counts > 1]],
        'out_of_order': bool(not np.all(np.diff(f) > 0)),
        'csv_npz_frames_identical': bool(len(npz_f) == len(f) and np.array_equal(npz_f, f)),
        'npz_array_lengths': {k: int(len(d[k])) for k in
                              ('ego_boxes', 'ego_scores', 'collab_boxes', 'collab_scores', 'gts')},
    }
    r['npz_lengths_all_equal_rows'] = bool(all(v == n_rows for v in r['npz_array_lengths'].values()))
    r['aligned'] = bool(r['rows_equals_dataset_frames'] and not r['missing_indices']
                        and not r['duplicate_indices'] and not r['out_of_order']
                        and r['csv_npz_frames_identical'] and r['npz_lengths_all_equal_rows'])
    r['rate_pct'] = 100.0 if r['aligned'] else 0.0
    return r


def build_ds(split):
    class O:
        model_dir = CKPT
    hypes = yaml_utils.load_yaml(None, O)
    dd = os.path.join(DATA_ROOT, SPLIT_DIR[split])
    if not os.path.isdir(dd):
        raise SystemExit(f'split directory not found: {dd}')
    hypes['root_dir'] = hypes['validate_dir'] = dd
    ds = build_dataset(hypes, visualize=False, train=False)
    ds.catosg_split = split
    return ds


def part_b_identity(ds, df, split, progress=200):
    """Collaborator identity, frame by frame. Correct value: 100 % on every sub-check.

    The point clouds are not needed to decide which CAV is selected -- only the poses are -- so
    `pcd_to_np` is stubbed for the walk. This removes I/O without touching the pose path that the
    rule actually reads.

    `load_yaml` is memoised for the same reason: a 7-CAV frame calls it **36 times**, OPV2V ships
    the slow pure-Python `yaml.Loader`, and the files are static inputs. The memo returns a
    **deepcopy**, which is not an optimisation detail but a correctness requirement --
    `reform_param` MUTATES what `load_yaml` returns (`delay_params['vehicles'] = ...`,
    `delay_params['transformation_matrix'] = ...`), and when the delay timestamp equals the current
    one it holds two references to the same object. Handing out a shared cached dict would let one
    frame's mutation leak into the next, silently. Measured 4.18x, with the resulting poses verified
    byte-identical against the uncached path.
    """
    real_pcd = pcd_utils.pcd_to_np
    real_yaml = basedataset.load_yaml
    pcd_utils.pcd_to_np = lambda *_a, **_k: np.zeros((0, 4), np.float32)
    _memo = functools.lru_cache(maxsize=8192)(real_yaml)
    basedataset.load_yaml = lambda p, *_a, **_k: copy.deepcopy(_memo(p))
    empty = np.zeros((0, 4), np.float32)
    try:
        n = len(df)
        rec, mismatch = [], []
        ego_first_fail, order_fail, com_range_drop = [], [], []
        has_collab_mismatch = []
        n_cav_mismatch = []
        t0 = time.time()
        for i in range(n):
            idx = int(df.frame.iloc[i])
            base = ds.retrieve_base_data(idx, cur_ego_pose_flag=ds.cur_ego_pose_flag)
            for cid in base:
                base[cid]['lidar_np'] = empty
            keys = list(base.keys())
            ego_id = next((c for c in keys if base[c]['ego']), None)
            if ego_id is None or keys[0] != ego_id:
                ego_first_fail.append(idx)
                continue
            ego_pose = base[ego_id]['params']['lidar_pose']

            want_id, want_d = nearest_collaborator(base, ego_pose)          # independent derivation
            sub = catosg_collab_subset.subset_of(base, ego_pose)            # the product rule
            sub_keys = list(sub.keys())

            got_id = sub_keys[1] if len(sub_keys) > 1 else None
            if sub_keys[0] != ego_id or len(sub_keys) > 2:
                order_fail.append(idx)
            if str(got_id) != str(want_id):
                mismatch.append(dict(frame=idx, expected=str(want_id), got=str(got_id),
                                     n_cav_total=len(keys)))

            # COM_RANGE is applied AFTER the subset, inside the CAV loop: a selected collaborator
            # beyond 70 m is dropped and the frame degenerates to |C| = 0 (sec 10.3).
            in_range = want_d is not None and want_d <= ocd.COM_RANGE
            if want_id is not None and not in_range:
                com_range_drop.append(dict(frame=idx, dist=round(float(want_d), 2)))
            expect_n_cav = 1 + (1 if (want_id is not None and in_range) else 0)
            if int(df.n_cav.iloc[i]) != expect_n_cav:
                n_cav_mismatch.append(dict(frame=idx, wp2=int(df.n_cav.iloc[i]),
                                           expected=expect_n_cav))
            if int(df.has_collab.iloc[i]) != int(expect_n_cav >= 2):
                has_collab_mismatch.append(idx)

            rec.append(dict(frame=idx, ego_id=str(ego_id), collab_id=str(got_id),
                            collab_dist_m=None if want_d is None else round(float(want_d), 3),
                            n_cav_available=len(keys)))
            if progress and i % progress == 0:
                print(f'  [B] {i}/{n} frame={idx} ego={ego_id} collab={got_id} '
                      f'of {len(keys)} CAVs', flush=True)
        dt = time.time() - t0
    finally:
        pcd_utils.pcd_to_np = real_pcd
        basedataset.load_yaml = real_yaml

    matched = n - len(mismatch) - len(ego_first_fail)
    r = {
        'frames_walked': n,
        'ego_is_first_failures': ego_first_fail,
        'subset_order_or_size_failures': order_fail,
        'collaborator_id_mismatches': mismatch[:20],
        'collaborator_id_mismatch_count': len(mismatch),
        'n_cav_mismatches': n_cav_mismatch[:20], 'n_cav_mismatch_count': len(n_cav_mismatch),
        'has_collab_mismatches': has_collab_mismatch[:20],
        'has_collab_mismatch_count': len(has_collab_mismatch),
        'selected_collaborator_beyond_COM_RANGE': com_range_drop[:20],
        'selected_collaborator_beyond_COM_RANGE_count': len(com_range_drop),
        'COM_RANGE_m': float(ocd.COM_RANGE),
        'rate_pct': 100.0 * matched / max(n, 1),
        'seconds': round(dt, 1),
    }
    r['aligned'] = bool(not mismatch and not ego_first_fail and not order_fail
                        and not n_cav_mismatch and not has_collab_mismatch)
    return r, rec


def part_c_row_binding(ds, df, rec, n_sample=24):
    """Row 1 of the stacked tensor carries the selected collaborator, and nothing else.

    Positive: MAX_COLLAB=1 vs KEEP_CAVS='<ego>,<collab>' must give a bit-identical row 1.
    Negative: NTH_COLLAB=2, where a second collaborator exists, must give a DIFFERENT row 1 --
    otherwise the comparison would pass no matter which CAV row 1 held.
    """
    def row_digest(idx, row, env):
        old = {k: os.environ.get(k) for k in
               ('CATOSG_MAX_COLLAB', 'CATOSG_KEEP_CAVS', 'CATOSG_NTH_COLLAB')}
        try:
            for k in old:
                os.environ.pop(k, None)
            os.environ.update(env)
            b = ds.collate_batch_test([ds[idx]])['ego']['processed_lidar']
            keep = b['voxel_coords'][:, 0] == row
            if not bool(keep.any()):
                return None
            import hashlib
            h = hashlib.sha256()
            for t in (b['voxel_features'][keep], b['voxel_coords'][keep],
                      b['voxel_num_points'][keep]):
                a = t.numpy() if isinstance(t, torch.Tensor) else np.asarray(t)
                h.update(np.ascontiguousarray(a).tobytes())
            return h.hexdigest()
        finally:
            for k, v in old.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v

    by_frame = {r['frame']: r for r in rec}
    cand = [int(f) for f in df[df.has_collab == 1].frame.tolist() if int(f) in by_frame]
    if not cand:
        return {'sampled': 0, 'aligned': None, 'note': 'no frame with a collaborator'}
    step = max(1, len(cand) // n_sample)
    sample = cand[::step][:n_sample]
    # The negative control only applies where a SECOND collaborator exists, so make sure some such
    # frames are in the sample rather than hoping the even stride lands on them.
    multi = [f for f in cand if by_frame[f]['n_cav_available'] >= 3]
    if multi:
        s2 = max(1, len(multi) // 8)
        for f in multi[::s2][:8]:
            if f not in sample:
                sample.append(f)

    pos_ok, pos_fail, neg_diff, neg_same, neg_na = 0, [], 0, [], 0
    for idx in sample:
        r = by_frame[idx]
        a = row_digest(idx, 1, {'CATOSG_MAX_COLLAB': '1'})
        b = row_digest(idx, 1, {'CATOSG_KEEP_CAVS': f"{r['ego_id']},{r['collab_id']}"})
        if a is not None and a == b:
            pos_ok += 1
        else:
            pos_fail.append(dict(frame=idx, max_collab=a, keep_cavs=b))
        if r['n_cav_available'] >= 3:
            c = row_digest(idx, 1, {'CATOSG_NTH_COLLAB': '2'})
            # Three outcomes, not two. A None from the negative arm means the 2nd-nearest CAV never
            # materialised as a row -- it is beyond COM_RANGE -- so the control is INAPPLICABLE
            # here. Counting that as "differs" would let the control pass vacuously, which is the
            # false-positive shape this repository refuses; counting it as a collision would be a
            # false alarm. It is counted as neither, and the run is required below to have
            # exercised the control for real at least once.
            if c is None or a is None:
                neg_na += 1
            elif c != a:
                neg_diff += 1
            else:
                neg_same.append(dict(frame=idx, nth2=c, max_collab=a))
        else:
            neg_na += 1
    return {
        'sampled': len(sample),
        'positive_bit_identical': pos_ok, 'positive_failures': pos_fail,
        'negative_control_differs': neg_diff, 'negative_control_collisions': neg_same,
        'negative_control_not_applicable': neg_na,
        'negative_control_exercised': bool(neg_diff + len(neg_same) > 0),
        'rate_pct': 100.0 * pos_ok / max(len(sample), 1),
        # The negative control must have RUN somewhere, or the positive result is unfalsified:
        # a comparison that would have passed whichever CAV row 1 held proves nothing.
        'aligned': bool(pos_ok == len(sample) and not neg_same and neg_diff > 0),
    }


def part_d_payload(df, d, wp34):
    """N_box,t is the selected collaborator's count -- not the ego's, not a sum -- and B_L,t
    follows from it through the sec-4.2 chain."""
    npz_collab = np.array([len(x) for x in d['collab_boxes']])
    npz_ego = np.array([len(x) for x in d['ego_boxes']])
    csv_collab = df.n_box_collab.to_numpy()
    r = {
        'wp2_csv_vs_npz_collab_counts_identical': bool(np.array_equal(csv_collab, npz_collab)),
        'wp2_csv_vs_npz_ego_counts_identical': bool(np.array_equal(df.n_box_ego.to_numpy(), npz_ego)),
        'collab_equals_ego_on_all_frames': bool(np.array_equal(npz_collab, npz_ego)),
        'no_collab_frames_have_zero_boxes': bool(
            np.all(npz_collab[df.has_collab.to_numpy() == 0] == 0)),
    }
    if wp34 is not None:
        w = wp34.sort_values('frame')
        same_frames = np.array_equal(w.frame.to_numpy(), df.frame.to_numpy())
        r['wp34_frames_identical_to_wp2'] = bool(same_frames)
        r['wp34_n_box_collab_identical'] = bool(
            same_frames and np.array_equal(w.n_box_collab.to_numpy(), csv_collab))
        chain = [l_chain(int(v)) for v in w.n_box_collab.to_numpy()]
        r['wp34_n_cw_L_recomputes'] = bool(
            np.array_equal(np.array([c[0] for c in chain]), w.n_cw_L.to_numpy()))
        r['wp34_B_L_recomputes'] = bool(np.allclose(
            np.array([c[1] for c in chain]), w.B_L_msym.to_numpy(), rtol=0, atol=1e-12))
        # the payload must NOT be derivable from the ego's counts -- a coincidence check
        ego_chain = [l_chain(int(v)) for v in w.n_box_ego.to_numpy()]
        r['payload_would_differ_if_ego_counts_used'] = bool(
            not np.allclose(np.array([c[1] for c in ego_chain]), w.B_L_msym.to_numpy()))
    r['aligned'] = bool(all(v for k, v in r.items()
                            if k not in ('collab_equals_ego_on_all_frames',)))
    r['rate_pct'] = 100.0 if r['aligned'] else 0.0
    return r


def run(split, sample_c):
    print('=' * 78)
    print(f'V2-R19 A -- identity alignment audit: {split}')
    print('=' * 78)
    df, meta, d, wp34 = load_products(split)
    a = part_a_index(df, meta, d)
    print(f'[A] index integrity            {a["rate_pct"]:.2f} %   '
          f'{"ALIGNED" if a["aligned"] else "FAIL"}')
    ds = build_ds(split)
    b, rec = part_b_identity(ds, df, split)
    print(f'[B] collaborator identity      {b["rate_pct"]:.2f} %   '
          f'{"ALIGNED" if b["aligned"] else "FAIL"}   ({b["seconds"]} s)')
    c = part_c_row_binding(ds, df, rec, sample_c)
    print(f'[C] row-1 binding              {c["rate_pct"]:.2f} %   '
          f'{"ALIGNED" if c["aligned"] else "FAIL"}   ({c["sampled"]} sampled)')
    dd = part_d_payload(df, d, wp34)
    print(f'[D] payload binding            {dd["rate_pct"]:.2f} %   '
          f'{"ALIGNED" if dd["aligned"] else "FAIL"}')

    ok = bool(a['aligned'] and b['aligned'] and c['aligned'] is not False and dd['aligned'])
    out = {'schema': 'catosg-v2-alignment-audit/1', 'split': split,
           'frames': int(len(df)),
           'why': 'Every part is an identity: a frame either is the frame it claims to be or the '
                  'product is misindexed. There is no legitimate partial reading, so the correct '
                  'value is 100 % and anything else stops the batch. This is NOT '
                  'collab_box_overlap_with_ego (73.6 %), which is a coordinate-frame diagnostic '
                  'whose correct value is not 100 %.',
           'input_hashes': input_hashes(split),
           'A_index_integrity': a, 'B_collaborator_identity': b,
           'C_row1_binding': c, 'D_payload_binding': dd,
           'overall_aligned': ok,
           'overall_rate_pct': 100.0 if ok else min(a['rate_pct'], b['rate_pct'], dd['rate_pct'])}
    with open(os.path.join(OUT_DIR, f'alignment_audit_{split}.json'), 'w') as f:
        json.dump(out, f, indent=1)
    import pandas as pd
    pd.DataFrame(rec).to_csv(os.path.join(OUT_DIR, f'collaborator_identity_{split}.csv'),
                             index=False)
    print('-' * 78)
    print(f'{split}: {"ALIGNED 100.00 %" if ok else "NOT ALIGNED -- BATCH STOPS"}')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate', choices=list(SPLIT_DIR) + ['all'])
    ap.add_argument('--sample-c', type=int, default=24)
    args = ap.parse_args()
    splits = list(SPLIT_DIR) if args.split == 'all' else [args.split]
    rc = 0
    for s in splits:
        rc |= run(s, args.sample_c)
    return rc


if __name__ == '__main__':
    sys.exit(main())
