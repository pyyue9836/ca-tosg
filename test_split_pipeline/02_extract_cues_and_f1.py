#self+ Test-split pipeline 02: extract 21 LiDAR cues + per-frame late/compressed F1 on OPV2V test split; produces test_split_pipeline/runs/test_frame_features.csv mirroring the validate-split schema
"""
Iterates OPV2V test split via the OpenCOOD dataloader, extracts:
  - 21 LiDAR-derived cues (same definitions as the validate cue CSV)
  - late_f1, compressed_f1 by matching the cached .npy predictions against
    the dataloader's ground-truth boxes at IoU 0.5
Produces: runs/test_frame_features.csv with the exact schema needed by
03_build_test_dataset.py.

Usage:
  PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \\
      peiyi_work/01_paper_ca_tosg/test_split_pipeline/02_extract_cues_and_f1.py
"""
import os
import sys
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, REPO)

from opencood.hypes_yaml.yaml_utils import load_yaml
from opencood.data_utils.datasets import build_dataset
from opencood.utils import eval_utils

import torch

SPLIT = os.environ.get('CATOSG_SPLIT', 'test')
TAG = 'culver' if 'culver' in SPLIT else 'test'
RUNS = 'runs' if TAG == 'test' else 'runs_culver'
PRETRAINED = os.path.join(REPO, 'peiyi_work/05_pretrained_models')
LATE_NPY = os.path.join(PRETRAINED, f'pointpillar_late_fusion_{TAG}_eval', 'npy')
COMP_NPY = os.path.join(PRETRAINED, 'pointpillar_attentive_fusion',
    f'pointpillar_attentive_fusion_compression_{TAG}_eval', 'npy')
CONFIG = os.path.join(PRETRAINED, f'pointpillar_late_fusion_{TAG}_eval', 'config.yaml')

OUT_DIR = os.path.join(REPO, f'peiyi_work/01_paper_ca_tosg/test_split_pipeline/{RUNS}')
OUT_CSV = os.path.join(OUT_DIR, 'test_frame_features.csv')
PAYLOAD_LATE = 0.024
PAYLOAD_COMP = 1.98


def extract_pcd_features(pts):
    feats = {}
    pts = np.asarray(pts)
    if pts.size == 0 or pts.ndim < 2:
        names = ['pcd_num_points', 'pcd_mean_range', 'pcd_max_range',
                 'pcd_std_range', 'pcd_near_20m', 'pcd_mid_20_50m',
                 'pcd_far_50_80m', 'pcd_very_far_80m', 'pcd_front_points',
                 'pcd_back_points', 'pcd_left_points', 'pcd_right_points',
                 'pcd_front_far_30m', 'pcd_front_far_50m', 'pcd_density_0_20',
                 'pcd_density_20_50', 'pcd_density_50_80']
        for n in names: feats[n] = 0.0
        return feats
    x, y = pts[:, 0], pts[:, 1]
    r = np.sqrt(x ** 2 + y ** 2)
    feats['pcd_num_points'] = int(len(pts))
    feats['pcd_mean_range'] = float(np.mean(r))
    feats['pcd_max_range'] = float(np.max(r))
    feats['pcd_std_range'] = float(np.std(r))
    feats['pcd_near_20m'] = int((r <= 20).sum())
    feats['pcd_mid_20_50m'] = int(((r > 20) & (r <= 50)).sum())
    feats['pcd_far_50_80m'] = int(((r > 50) & (r <= 80)).sum())
    feats['pcd_very_far_80m'] = int((r > 80).sum())
    feats['pcd_front_points'] = int((x >= 0).sum())
    feats['pcd_back_points'] = int((x < 0).sum())
    feats['pcd_left_points'] = int((y >= 0).sum())
    feats['pcd_right_points'] = int((y < 0).sum())
    feats['pcd_front_far_30m'] = int(((x >= 0) & (r > 30)).sum())
    feats['pcd_front_far_50m'] = int(((x >= 0) & (r > 50)).sum())
    feats['pcd_density_0_20'] = float(feats['pcd_near_20m'] / (np.pi * 20 ** 2))
    feats['pcd_density_20_50'] = float(feats['pcd_mid_20_50m'] /
                                       (np.pi * (50 ** 2 - 20 ** 2)))
    feats['pcd_density_50_80'] = float(feats['pcd_far_50_80m'] /
                                       (np.pi * (80 ** 2 - 50 ** 2)))
    return feats


def load_boxes(npy_dir, sample_id):
    p = os.path.join(npy_dir, f'{sample_id:04d}_pred.npy')
    if not os.path.exists(p):
        return np.zeros((0, 8, 3), dtype=np.float32)
    a = np.load(p, allow_pickle=True)
    return a if a.size > 0 else np.zeros((0, 8, 3), dtype=np.float32)


def f1_from_boxes(pred_arr, gt_arr, iou_thresh=0.5):
    """Frame-level F1: TP via IoU-thresholded match between pred and GT corners."""
    pred_t = torch.from_numpy(pred_arr.astype(np.float32)) if pred_arr.size > 0 \
        else torch.zeros((0, 8, 3), dtype=torch.float32)
    gt_t = torch.from_numpy(gt_arr.astype(np.float32)) if gt_arr.size > 0 \
        else torch.zeros((0, 8, 3), dtype=torch.float32)
    score = torch.ones(len(pred_t), dtype=torch.float32)
    result_stat = {iou_thresh: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pred_t, score, gt_t, result_stat, iou_thresh)
    tp = sum(result_stat[iou_thresh]['tp'])
    fp = sum(result_stat[iou_thresh]['fp'])
    gt_count = result_stat[iou_thresh]['gt']
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / gt_count if gt_count > 0 else 0.0
    return (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0, prec, rec, tp, fp, gt_count


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    hypes = load_yaml(CONFIG)
    dataset = build_dataset(hypes, visualize=True, train=False)
    print(f'OPV2V test loaded. T = {len(dataset)} frames')

    rows = []
    for idx in range(len(dataset)):
        item = dataset[idx]
        cav_keys = list(item.keys())
        ego = item.get('ego', {})
        pts = ego.get('origin_lidar', np.zeros((0, 3)))
        pcd_feats = extract_pcd_features(pts)

        # GT boxes for this frame (same shape as cached *_gt.npy_test.npy)
        gt_path = os.path.join(LATE_NPY, f'{idx:04d}_gt.npy_test.npy')
        gt = np.load(gt_path, allow_pickle=True) if os.path.exists(gt_path) \
            else np.zeros((0, 8, 3))
        # F1 per method
        late_pred = load_boxes(LATE_NPY, idx)
        comp_pred = load_boxes(COMP_NPY, idx)
        late_f1, late_prec, late_rec, late_tp, late_fp, late_gt = \
            f1_from_boxes(late_pred, gt, 0.5)
        comp_f1, comp_prec, comp_rec, comp_tp, comp_fp, comp_gt = \
            f1_from_boxes(comp_pred, gt, 0.5)
        late_fn = max(0, late_gt - late_tp)
        comp_fn = max(0, comp_gt - comp_tp)

        row = {
            'sample_id': idx,
            'num_cavs': len(cav_keys),
            'cav_keys': '|'.join(str(k) for k in cav_keys),
            'ego_num_objects': len(ego.get('object_ids', [])),
            'ego_origin_lidar_shape_0': int(np.asarray(pts).shape[0]),
            'ego_origin_lidar_shape_1': int(np.asarray(pts).shape[1])
                if np.asarray(pts).ndim == 2 else -1,
            'late_num_pred': int(len(late_pred)),
            'late_num_gt': int(late_gt),
            'late_tp': int(late_tp), 'late_fp': int(late_fp),
            'late_fn': int(late_fn),
            'late_precision': float(late_prec), 'late_recall': float(late_rec),
            'late_f1': float(late_f1),
            'late_payload_Mbit': PAYLOAD_LATE,
            'compressed_num_pred': int(len(comp_pred)),
            'compressed_num_gt': int(comp_gt),
            'compressed_tp': int(comp_tp), 'compressed_fp': int(comp_fp),
            'compressed_fn': int(comp_fn),
            'compressed_precision': float(comp_prec),
            'compressed_recall': float(comp_rec),
            'compressed_f1': float(comp_f1),
            'compressed_payload_Mbit': PAYLOAD_COMP,
        }
        row.update(pcd_feats)
        rows.append(row)

        if (idx + 1) % 100 == 0:
            print(f'  processed {idx+1}/{len(dataset)} '
                  f'(late_f1={late_f1:.3f} comp_f1={comp_f1:.3f})')

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f'\nwrote {OUT_CSV}  ({len(df)} rows, {len(df.columns)} cols)')
    print(f'  mean late_f1     = {df["late_f1"].mean():.4f}')
    print(f'  mean compressed_f1 = {df["compressed_f1"].mean():.4f}')


if __name__ == '__main__':
    main()
