#self+ P1 Step-4 prerequisite (b): recompute EVERY per-frame F1 column (late/comp/ego, 3 splits)
# from the canonical npz + canonical union GT. NO stale dataset CSV F1 column is reused (the
# validate case proved them untrustworthy: dataset late_f1 0.8636 was a different inference from
# the current npz 0.9082). Canonical GT = comp all-CAV union GT. Overwrites late_f1/compressed_f1,
# adds ego_f1, into data/dataset_{split}_v3.csv (the cue columns are LiDAR-derived and kept as-is).
import os, sys
import numpy as np, pandas as pd, torch
REPO='/home/josh/cooperative_semantic_perception/OpenCOOD'; sys.path.insert(0,REPO)
from opencood.utils import eval_utils
P1=os.path.join(REPO,'peiyi_work/paper1'); GS=os.path.join(P1,'gs_rerun'); D=os.path.join(P1,'data')


def f1(pred, gt, iou=0.5):
    pred=np.asarray(pred,np.float32); gt=np.asarray(gt,np.float32)
    pt=torch.from_numpy(pred) if pred.size else torch.zeros((0,8,3))
    gt_t=torch.from_numpy(gt) if gt.size else torch.zeros((0,8,3))
    rs={iou:{'tp':[],'fp':[],'gt':0,'score':[]}}
    eval_utils.caluclate_tp_fp(pt,torch.ones(len(pt)),gt_t,rs,iou)
    tp=sum(rs[iou]['tp']); fp=sum(rs[iou]['fp']); g=rs[iou]['gt']
    p=tp/(tp+fp) if tp+fp>0 else 0.; r=tp/g if g>0 else 0.
    return (2*p*r/(p+r)) if p+r>0 else 0.


def main():
    summ=[]
    for sp in ('validate','test','culver'):
        la=np.load(f'{GS}/late_{sp}.npz',allow_pickle=True)
        co=np.load(f'{GS}/comp_{sp}.npz',allow_pickle=True)
        eg=np.load(f'{GS}/ego_{sp}.npz',allow_pickle=True)
        canon=co['gts']                              # canonical union GT
        df=pd.read_csv(f'{D}/dataset_{sp}.csv')
        sids=df['sample_id'].astype(int).to_numpy()
        lf=np.array([f1(la['boxes'][s], canon[s]) for s in sids])
        cf=np.array([f1(co['boxes'][s], canon[s]) for s in sids])
        ef=np.array([f1(eg['boxes'][s], canon[s]) for s in sids])
        old_lf=df['late_f1'].to_numpy().mean(); old_cf=df['compressed_f1'].to_numpy().mean()
        df['late_f1']=lf; df['compressed_f1']=cf; df['ego_f1']=ef
        df.to_csv(f'{D}/dataset_{sp}_v3.csv', index=False)
        summ.append(dict(split=sp, n=len(df),
                         late_f1_old=round(old_lf,4), late_f1_v3=round(lf.mean(),4),
                         comp_f1_old=round(old_cf,4), comp_f1_v3=round(cf.mean(),4),
                         ego_f1_v3=round(ef.mean(),4)))
        print(f"{sp:9s} late {old_lf:.4f}->{lf.mean():.4f}  comp {old_cf:.4f}->{cf.mean():.4f}  ego(new)={ef.mean():.4f}  -> dataset_{sp}_v3.csv", flush=True)
    pd.DataFrame(summ).to_csv(os.path.join(P1,'..','..','ca-tosg/paper1/results/canonical_f1_columns_v3.csv'), index=False)
    print("[artifact] results/canonical_f1_columns_v3.csv ; datasets: data/dataset_{split}_v3.csv")


if __name__=='__main__':
    main()
