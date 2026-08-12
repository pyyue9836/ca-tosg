#self+ P1 Step 2 driver: ego-only inference for all 3 splits + acceptance table.
# ego F1/AP are scored against the LATE (canonical cooperative) GT -- the same GT as
# Fixed-L -- so ego-only is a fair, strictly-lower fallback comparison (it misses the
# collaborator-visible objects). Outputs gs_rerun/ego_{split}.npz + prints the summary.
import os, subprocess, sys
import numpy as np, torch
REPO = '/home/josh/cooperative_semantic_perception/OpenCOOD'
sys.path.insert(0, REPO)
from opencood.utils import eval_utils
P1 = os.path.join(REPO, 'peiyi_work/paper1')
PY = '/home/josh/miniconda3/envs/sionna310/bin/python'
GS = os.path.join(P1, 'gs_rerun'); MP = 'peiyi_work/paper1/pretrained_models'
LATE_DIR = {'validate': f'{MP}/pointpillar_late_fusion',
            'test': f'{MP}/pointpillar_late_fusion_test_eval',
            'culver': f'{MP}/pointpillar_late_fusion_culver_eval'}


def f1_from_boxes(pred, gt, iou=0.5):
    pred = np.asarray(pred, np.float32); gt = np.asarray(gt, np.float32)
    pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
    gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
    rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, iou)
    tp = sum(rs[iou]['tp']); fp = sum(rs[iou]['fp']); g = rs[iou]['gt']
    p = tp / (tp + fp) if tp + fp > 0 else 0.; r = tp / g if g > 0 else 0.
    return (2 * p * r / (p + r)) if p + r > 0 else 0.


def ap_global(boxes, scores, gts, thr=0.5):
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
    print('=== Step 2: ego-only inference (3 splits) ===', flush=True)
    for sp, mdir in LATE_DIR.items():
        out = os.path.join(GS, f'ego_{sp}.npz')
        if not os.path.exists(out):
            print(f'\n--- {sp}: ego-only inference ---', flush=True)
            subprocess.check_call([PY, os.path.join(P1, 'code/regen_ego_only.py'),
                                   '--model_dir', mdir, '--out', out],
                                  cwd=REPO, env={**os.environ, 'PYTHONPATH': REPO})
    print('\n=== ACCEPTANCE: ego-only vs Fixed-L (both scored on the LATE canonical GT) ===', flush=True)
    print(f'{"split":9s} {"ego F1":>8s} {"L F1":>8s} | {"ego AP@.5":>10s} {"L AP@.5":>10s}   (ego must be clearly lower)')
    for sp in LATE_DIR:
        eg = np.load(os.path.join(GS, f'ego_{sp}.npz'), allow_pickle=True)
        la = np.load(os.path.join(GS, f'late_{sp}.npz'), allow_pickle=True)
        lg = la['gts']                                   # canonical cooperative GT
        n = min(len(eg['boxes']), len(lg))
        ego_f1 = np.mean([f1_from_boxes(eg['boxes'][i], lg[i]) for i in range(n)])
        L_f1 = np.mean([f1_from_boxes(la['boxes'][i], lg[i]) for i in range(n)])
        ego_ap = ap_global(eg['boxes'][:n], eg['scores'][:n], lg[:n])
        L_ap = ap_global(la['boxes'][:n], la['scores'][:n], lg[:n])
        print(f'{sp:9s} {ego_f1:8.4f} {L_f1:8.4f} | {ego_ap:10.4f} {L_ap:10.4f}', flush=True)


if __name__ == '__main__':
    main()
