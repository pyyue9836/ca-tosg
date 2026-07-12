#self+ P1 canonical-GT re-score (v3): score late / comp / ego predictions against ONE
# canonical GT = the post-processor union GT @ standard GT_RANGE (=[-140,-40,-3,140,40,1]),
# predictions NOT cropped, all policies on the same ruler. Q4 confirmed late has far preds, so
# no structural range problem and no ±70.4 crop. No visibility filter (GT is one-for-all ->
# visibility is a sensitivity issue, appendix candidate, not canonical). Canonical GT source =
# the intermediate (comp) all-CAV union GT (the cooperative task-truth union).
# Prints and writes results/canonical_rescore_v3.csv with BEFORE (own-GT) vs AFTER (canonical).
import os, sys
import numpy as np, torch, pandas as pd
REPO = '/home/josh/cooperative_semantic_perception/OpenCOOD'; sys.path.insert(0, REPO)
from opencood.utils import eval_utils
GS = os.path.join(REPO, 'peiyi_work/paper1/gs_rerun')
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results/canonical_rescore_v3.csv')


def f1(boxes, gts, iou=0.5):
    vals = []
    for i in range(len(boxes)):
        pred = np.asarray(boxes[i], np.float32); gt = np.asarray(gts[i], np.float32)
        pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
        gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
        rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
        eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, iou)
        tp = sum(rs[iou]['tp']); fp = sum(rs[iou]['fp']); g = rs[iou]['gt']
        p = tp / (tp + fp) if tp + fp > 0 else 0.; r = tp / g if g > 0 else 0.
        vals.append((2 * p * r / (p + r)) if p + r > 0 else 0.)
    return float(np.mean(vals))


def ap(boxes, scores, gts, thr):
    tot = int(sum(len(np.asarray(g)) for g in gts))
    rs = {thr: {'tp': [], 'fp': [], 'gt': tot, 'score': []}}
    for i in range(len(boxes)):
        pb = np.asarray(boxes[i], np.float32); ps = np.asarray(scores[i], np.float32); g = np.asarray(gts[i], np.float32)
        pt = torch.from_numpy(pb) if pb.size else torch.zeros((0, 8, 3))
        gt_t = torch.from_numpy(g) if g.size else torch.zeros((0, 8, 3))
        st = torch.from_numpy(ps) if ps.size else torch.zeros((0,))
        r1 = {thr: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
        eval_utils.caluclate_tp_fp(pt, st, gt_t, r1, thr)
        for k in ('tp', 'fp', 'score'):
            rs[thr][k] += r1[thr][k]
    return eval_utils.calculate_ap(rs, thr, True)[0]


def main():
    rows = []
    for sp in ('validate', 'test', 'culver'):
        la = np.load(f'{GS}/late_{sp}.npz', allow_pickle=True)
        co = np.load(f'{GS}/comp_{sp}.npz', allow_pickle=True)
        eg = np.load(f'{GS}/ego_{sp}.npz', allow_pickle=True)
        canon = co['gts']                                  # canonical = comp all-CAV union GT
        for pol, d, own in [('Fixed-L (late)', la, la['gts']),
                            ('Feature-ceiling (comp)', co, co['gts']),
                            ('ego-only', eg, la['gts'])]:   # ego "before" was scored on late GT
            b, s = d['boxes'], d['scores']
            row = dict(split=sp, policy=pol,
                       F1_before=round(f1(b, own), 4), F1_after=round(f1(b, canon), 4),
                       AP50_before=round(ap(b, s, own, 0.5), 4), AP50_after=round(ap(b, s, canon, 0.5), 4),
                       AP70_before=round(ap(b, s, own, 0.7), 4), AP70_after=round(ap(b, s, canon, 0.7), 4))
            rows.append(row)
            print(f"{sp:9s} {pol:24s} F1 {row['F1_before']}->{row['F1_after']} "
                  f"AP50 {row['AP50_before']}->{row['AP50_after']} AP70 {row['AP70_before']}->{row['AP70_after']}", flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print('\n[artifact]', OUT)


if __name__ == '__main__':
    main()
