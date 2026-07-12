#self+ CA-TOSG P1 Step-5 Track A scorer: score JSCC decode npz vs CANONICAL GT v3 (comp union GT).
# Per-frame F1 (all boxes, score=ones -- matches recompute_canonical_f1.py) + global-sort AP.
"""
Modes:
  --mode score : for every gs_rerun/jscc_v3/jscc_<ch>_<split>_snr<NN>.npz, per-frame F1 + global-sort
                 AP vs the canonical union GT (gs_rerun/comp_<split>.npz['gts']); writes
                 results/jscc_v3/jscc_ap_f1_v3.csv and per-frame F1 npz jscc_perframe_f1_<ch>_<split>.npz.
  --mode probe : interpolation-validity check. Reads the probe npz at SNR 8/10/12 (validate), computes
                 per-frame F1 at each, then MAE + max|dev| of the linear interp 0.5*(F1_8+F1_12) vs the
                 real F1_10. One row -> results/jscc_v3/interp_probe_mae.csv.
"""
import argparse, glob, os, sys
import numpy as np, pandas as pd, torch
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, *(['..'] * 5)))
sys.path.insert(0, REPO)
from opencood.utils import eval_utils
P1 = os.path.join(REPO, 'peiyi_work/paper1'); GS = os.path.join(P1, 'gs_rerun')
JSCC_DIR = os.path.join(GS, 'jscc_v3'); OUT = os.path.join(P1, 'results/jscc_v3')


def tt(a, shp):
    a = np.asarray(a, np.float32); return torch.from_numpy(a) if a.size else torch.zeros(shp, dtype=torch.float32)


def f1_vs(boxes, canon, iou=0.5):
    """All predicted boxes (score=ones), IoU 0.5 -- identical recipe to recompute_canonical_f1.py."""
    pt = tt(boxes, (0, 8, 3)); gt = tt(canon, (0, 8, 3))
    rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt, rs, iou)
    tp = sum(rs[iou]['tp']); fp = sum(rs[iou]['fp']); g = rs[iou]['gt']
    p = tp / (tp + fp) if tp + fp > 0 else 0.; r = tp / g if g > 0 else 0.
    return (2 * p * r / (p + r)) if p + r > 0 else 0.


def perframe_f1(npz_path, canon_gts):
    d = np.load(npz_path, allow_pickle=True); boxes = list(d['boxes'])
    n = min(len(boxes), len(canon_gts))
    return np.array([f1_vs(boxes[i], canon_gts[i]) for i in range(n)]), n


def global_ap(npz_path, canon_gts, thrs=(0.3, 0.5, 0.7)):
    d = np.load(npz_path, allow_pickle=True); boxes = list(d['boxes']); scores = list(d['scores'])
    n = min(len(boxes), len(canon_gts))
    res = {}
    for thr in thrs:
        rs = {thr: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
        for i in range(n):
            eval_utils.caluclate_tp_fp(tt(boxes[i], (0, 8, 3)), tt(scores[i], (0,)),
                                       tt(canon_gts[i], (0, 8, 3)), rs, thr)
        res[thr] = eval_utils.calculate_ap(rs, thr, True)[0]
    return res[0.3], res[0.5], res[0.7]


def canon_of(split):
    return list(np.load(os.path.join(GS, f'comp_{split}.npz'), allow_pickle=True)['gts'])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--mode', choices=['score', 'probe'], default='score')
    o = ap.parse_args(); os.makedirs(OUT, exist_ok=True)

    if o.mode == 'probe':
        canon = canon_of('validate')
        f1 = {}
        for snr in (8, 10, 12):
            p = os.path.join(JSCC_DIR, f'jscc_awgn_validate_snr{snr:02d}.npz')
            f1[snr], n = perframe_f1(p, canon)
            print(f'  probe snr{snr}: n={n} meanF1={f1[snr].mean():.4f}', flush=True)
        m = min(len(f1[8]), len(f1[10]), len(f1[12]))
        interp10 = 0.5 * (f1[8][:m] + f1[12][:m]); real10 = f1[10][:m]
        mae = float(np.abs(interp10 - real10).mean()); mx = float(np.abs(interp10 - real10).max())
        row = dict(probe='awgn_validate_snr10_from_8_12', n=m, mae=round(mae, 6),
                   max_abs_dev=round(mx, 6), mean_real=round(float(real10.mean()), 4),
                   mean_interp=round(float(interp10.mean()), 4))
        pd.DataFrame([row]).to_csv(os.path.join(OUT, 'interp_probe_mae.csv'), index=False)
        print('\n[PROBE]', row); print('wrote results/jscc_v3/interp_probe_mae.csv')
        return

    rows = []
    for p in sorted(glob.glob(os.path.join(JSCC_DIR, 'jscc_*_snr*.npz'))):
        base = os.path.basename(p)[:-4]                     # jscc_<ch>_<split>_snrNN
        _, ch, split, snrtag = base.split('_'); snr = int(snrtag[3:])
        canon = canon_of(split)
        pf, n = perframe_f1(p, canon); a30, a50, a70 = global_ap(p, canon)
        rows.append(dict(channel=ch, split=split, snr_db=snr, n=n,
                         jscc_f1=round(float(pf.mean()), 4),
                         ap30=round(a30, 4), ap50=round(a50, 4), ap70=round(a70, 4)))
        np.savez(os.path.join(OUT, f'jscc_perframe_f1_{ch}_{split}_snr{snr:02d}.npz'), f1=pf)
        print(f'  {ch} {split} snr{snr}: n={n} F1={pf.mean():.4f} AP50={a50:.4f}', flush=True)
    pd.DataFrame(rows).sort_values(['channel', 'split', 'snr_db']).to_csv(
        os.path.join(OUT, 'jscc_ap_f1_v3.csv'), index=False)
    print('wrote results/jscc_v3/jscc_ap_f1_v3.csv')


if __name__ == '__main__':
    main()
