#self+ CA-TOSG P1 v3: global-sort true-end-to-end AP under the deployed selector.
# THREE v3 changes vs the v2 scorer:
#   (1) ego-only failure fallback: when a requested feature message fails (BLER) the frame falls
#       back to the EGO-ONLY single-vehicle detection, NOT the object-level L (which was not
#       requested). Per-frame pick is 3-way: L -> late, C-success -> comp, C-fail -> ego.
#   (2) ONE canonical union GT for every branch (no per-frame own-GT). All of late/comp/ego are
#       scored against the same canonical union GT (the evaluation-time post-processor union,
#       standard OPV2V GT_RANGE; materialised here from the intermediate/comp npz gts). gt_tot is
#       the canonical GT count, fixed regardless of the per-frame pick.
#   (3) frame-level BLER from the Sionna table (results/bler_sionna/bler_sionna.csv), Es/N0 axis,
#       bler_frame column (= 1-(1-p_cw)^3960). The selector's est SNR is read as Es/N0.
import os, sys, pickle, argparse
import numpy as np, pandas as pd, torch
HERE=os.path.dirname(os.path.abspath(__file__)); P1=os.path.dirname(HERE)
REPO=os.path.dirname(os.path.dirname(P1)); sys.path.insert(0,REPO)
from opencood.utils import eval_utils

BLER_CSV=os.path.join(P1,'results/bler_sionna/bler_sionna.csv')   # frame-level, Es/N0
RF_PATH=os.path.join(P1,'data/selector_rf.pkl')
OPS=[('awgn',0.0),('awgn',8.0),('awgn',12.0),('awgn',14.0),('awgn',16.0),('awgn',20.0),
     ('rayleigh',0.0),('rayleigh',10.0),('rayleigh',20.0)]
N_REPEAT=5; SEED=0; THRS=(0.3,0.5,0.7)
LATE,COMP,EGO=0,1,2

def bler_frame(snr, tbl, qam, channel):
    """Frame-level BLER at Es/N0=snr (dB) for a QAM order over a channel, from the Sionna table."""
    s=tbl[(tbl['qam']==qam)&(tbl['channel']==channel)].sort_values('esno_db')
    return float(np.clip(np.interp(snr, s['esno_db'], s['bler_frame'],
                                   left=1., right=float(s['bler_frame'].iloc[-1])), 0, 1))

def tt(a,shp):
    a=np.asarray(a,dtype=np.float32); return torch.from_numpy(a) if a.size else torch.zeros(shp,dtype=torch.float32)

def frame_stats(pb,ps,gtt):
    out={}
    for thr in THRS:
        rs={thr:{'tp':[],'fp':[],'gt':0,'score':[]}}
        eval_utils.caluclate_tp_fp(tt(pb,(0,8,3)),tt(ps,(0,)),gtt,rs,thr)
        out[thr]=(rs[thr]['tp'],rs[thr]['fp'],rs[thr]['score'])
    return out

def ap_pick(picks, ST, gtn):
    """picks[i] in {LATE,COMP,EGO}; ST=[LST,CST,EST]; gtn=canonical GT count per frame (fixed).
    Global-sort AP scored against the ONE canonical GT (gt_tot = sum of canonical GT counts)."""
    gt_tot=int(sum(gtn)); res={}
    for thr in THRS:
        rs={thr:{'tp':[],'fp':[],'gt':gt_tot,'score':[]}}
        for i in range(len(picks)):
            st=ST[picks[i]][i][thr]
            rs[thr]['tp']+=st[0]; rs[thr]['fp']+=st[1]; rs[thr]['score']+=st[2]
        res[thr]=eval_utils.calculate_ap(rs,thr,True)[0]
    return res[0.3],res[0.5],res[0.7]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--split',default='validate');ap.add_argument('--late',required=True)
    ap.add_argument('--comp',required=True);ap.add_argument('--ego',required=True)
    ap.add_argument('--cues',required=True);ap.add_argument('--out',required=True)
    o=ap.parse_args()
    dl=np.load(o.late,allow_pickle=True); dc=np.load(o.comp,allow_pickle=True); de=np.load(o.ego,allow_pickle=True)
    lb,ls=list(dl['boxes']),list(dl['scores'])
    cb,cs,cg=list(dc['boxes']),list(dc['scores']),list(dc['gts'])   # comp gts = canonical union GT
    eb,es=list(de['boxes']),list(de['scores'])
    df=pd.read_csv(o.cues).reset_index(drop=True); bler=pd.read_csv(BLER_CSV)
    rf=pickle.load(open(RF_PATH,'rb')); feat=list(rf.feature_names_in_)
    sids=df['sample_id'].astype(int).to_numpy(); n=len(sids)
    print(f'[{o.split}] precomputing per-frame stats for {n} frames vs the CANONICAL union GT...',flush=True)
    LST=[];CST=[];EST=[];gtn=[]
    for k,s in enumerate(sids):
        canon=tt(cg[s],(0,8,3)); gtn.append(canon.shape[0])   # canonical GT = comp all-CAV union GT
        LST.append(frame_stats(lb[s],ls[s],canon))
        CST.append(frame_stats(cb[s],cs[s],canon))
        EST.append(frame_stats(eb[s],es[s],canon))
        if k%400==0: print(f'  {k}/{n}',flush=True)
    ST=[LST,CST,EST]
    fL=ap_pick([LATE]*n,ST,gtn); cE=ap_pick([COMP]*n,ST,gtn); eO=ap_pick([EGO]*n,ST,gtn)
    print(f'[{o.split}] Fixed-L         AP@.3/.5/.7 = {fL[0]:.4f}/{fL[1]:.4f}/{fL[2]:.4f}',flush=True)
    print(f'[{o.split}] Feature ceiling AP@.3/.5/.7 = {cE[0]:.4f}/{cE[1]:.4f}/{cE[2]:.4f}',flush=True)
    print(f'[{o.split}] ego-only floor  AP@.3/.5/.7 = {eO[0]:.4f}/{eO[1]:.4f}/{eO[2]:.4f}',flush=True)
    rows=[dict(split=o.split,policy='Fixed-L',channel='-',snr_db='-',ap30=fL[0],ap50=fL[1],ap70=fL[2]),
          dict(split=o.split,policy='Feature-ceiling',channel='-',snr_db='-',ap30=cE[0],ap50=cE[1],ap70=cE[2]),
          dict(split=o.split,policy='ego-only',channel='-',snr_db='-',ap30=eO[0],ap50=eO[1],ap70=eO[2])]
    for ch,snr in OPS:
        d=df.copy(); d['est_snr_db']=snr; d['channel_is_rayleigh']=int(ch=='rayleigh')
        acts=rf.predict(d[feat])
        b16=bler_frame(snr,bler,16,ch); b256=bler_frame(snr,bler,256,ch)
        a30,a50,a70=[],[],[]
        for r in range(N_REPEAT):
            rng=np.random.default_rng(SEED+r)
            picks=[]
            for k in range(n):
                a=acts[k]
                if a=='L': picks.append(LATE)
                else:
                    b=b16 if a=='C16' else b256
                    picks.append(COMP if rng.random()>b else EGO)   # C-success -> comp, C-fail -> ego
            r3=ap_pick(picks,ST,gtn); a30.append(r3[0]);a50.append(r3[1]);a70.append(r3[2])
        rho_L=float((acts=='L').mean())
        print(f'  {ch:8s} SNR={snr:5.1f}: AP@.5={np.mean(a50):.4f}±{np.std(a50):.4f} AP@.7={np.mean(a70):.4f} rho_L={rho_L:.3f}',flush=True)
        rows.append(dict(split=o.split,policy='CA-TOSG',channel=ch,snr_db=snr,rho_L=rho_L,
                         ap30=float(np.mean(a30)),ap50=float(np.mean(a50)),ap70=float(np.mean(a70)),ap50_std=float(np.std(a50))))
    pd.DataFrame(rows).to_csv(o.out,index=False); print('wrote',o.out,flush=True)

if __name__=='__main__': main()
