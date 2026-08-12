#self+ Score per-frame JSCC F1 from the saved npy of run_jscc_perframe.py.
# Reuses the pipeline's f1_from_boxes (IoU 0.5/0.7) so jscc_f1 is directly comparable
# to late_f1 / compressed_f1 in runs/v2/dataset.csv.
"""
Scans runs/<tag>_<channel>_snrNN/npy for each requested SNR, computes per-frame F1,
and writes out/jscc_perframe_<tag>_<channel>.csv with columns
  sample_id, snr_db, jscc_f1_05, jscc_f1_07, gt, tp, fp.

Run from repo root with the sionna310 interpreter (PYTHONPATH=. ; do NOT set
PYTHONNOUSERSITE -- needs the user-site numpy 1.26.4).
"""
import argparse
import os
import sys
import numpy as np
import pandas as pd
import torch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), *(['..'] * 4)))
sys.path.insert(0, REPO)
from opencood.utils import eval_utils  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load_pred(npy_dir, idx):
    p = os.path.join(npy_dir, f'{idx:04d}_pred.npy')
    if not os.path.exists(p):
        return np.zeros((0, 8, 3), dtype=np.float32)
    a = np.load(p, allow_pickle=True)
    return a if a.size > 0 else np.zeros((0, 8, 3), dtype=np.float32)


def load_gt(npy_dir, idx):
    p = os.path.join(npy_dir, f'{idx:04d}_gt.npy_test.npy')
    if not os.path.exists(p):
        return np.zeros((0, 8, 3), dtype=np.float32)
    a = np.load(p, allow_pickle=True)
    return a if a.size > 0 else np.zeros((0, 8, 3), dtype=np.float32)


def f1_from_boxes(pred_arr, gt_arr, iou):
    pred_t = torch.from_numpy(pred_arr.astype(np.float32)) if pred_arr.size > 0 \
        else torch.zeros((0, 8, 3), dtype=torch.float32)
    gt_t = torch.from_numpy(gt_arr.astype(np.float32)) if gt_arr.size > 0 \
        else torch.zeros((0, 8, 3), dtype=torch.float32)
    score = torch.ones(len(pred_t), dtype=torch.float32)
    rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pred_t, score, gt_t, rs, iou)
    tp = sum(rs[iou]['tp']); fp = sum(rs[iou]['fp']); g = rs[iou]['gt']
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / g if g > 0 else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return f1, tp, fp, g


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", default="jscc")
    p.add_argument("--channel", default="awgn")
    p.add_argument("--snrs", required=True, help="comma-separated dB list matching the run dirs")
    p.add_argument("--runs_root", default=os.path.join(HERE, "runs"))
    p.add_argument("--out", default=None)
    args = p.parse_args()

    snrs = [float(s) for s in args.snrs.split(",")]
    rows = []
    for snr in snrs:
        npy_dir = os.path.join(args.runs_root, f"{args.tag}_{args.channel}_snr{int(round(snr)):02d}", "npy")
        if not os.path.isdir(npy_dir):
            print(f"[WARN] missing {npy_dir}; skipping snr={snr}"); continue
        n = len({f[:4] for f in os.listdir(npy_dir) if f.endswith('_pred.npy')})
        for idx in range(n):
            f05, tp, fp, g = f1_from_boxes(load_pred(npy_dir, idx), load_gt(npy_dir, idx), 0.5)
            f07, *_ = f1_from_boxes(load_pred(npy_dir, idx), load_gt(npy_dir, idx), 0.7)
            rows.append(dict(sample_id=idx, snr_db=snr, jscc_f1_05=f05,
                             jscc_f1_07=f07, gt=g, tp=tp, fp=fp))
        print(f"  snr={snr:4.0f}  frames={n}  mean jscc_f1@0.5={np.mean([r['jscc_f1_05'] for r in rows if r['snr_db']==snr]):.4f}")
    out = args.out or os.path.join(HERE, "out", f"jscc_perframe_{args.tag}_{args.channel}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print("[DONE] wrote", out, "rows", len(rows))


if __name__ == "__main__":
    main()
