#self+ CA-TOSG: global-sort true-end-to-end AP under the deployed selector.
# Precomputes per-frame (tp,fp,score) once for the object-level (late) and feature-level
# (attentive-compression) branches, then aggregates per policy/channel realisation with a
# single global confidence sort (COCO-style), using the real per-detection confidences.
# Each branch is scored against ITS OWN ground truth (the late- and intermediate-fusion
# datasets emit different GT; frames are aligned but filtering differs). The mixed selector
# uses, per frame, the chosen branch's GT and GT count. As a result Fixed-L reproduces the
# standalone late-fusion eval and the feature ceiling reproduces the standalone compression eval.
import os, sys, pickle, argparse
import numpy as np, pandas as pd, torch
HERE=os.path.dirname(os.path.abspath(__file__)); P1=os.path.dirname(HERE)
REPO=os.path.dirname(os.path.dirname(P1)); sys.path.insert(0,REPO)
from opencood.utils import eval_utils

BLER_CSV=os.path.join(P1,'experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
RF_PATH=os.path.join(P1,'data/selector_rf.pkl')
OPS=[('awgn',0.0),('awgn',8.0),('awgn',12.0),('awgn',14.0),('awgn',16.0),('awgn',20.0),
     ('rayleigh',0.0),('rayleigh',10.0),('rayleigh',20.0)]
N_REPEAT=5; SEED=0; THRS=(0.3,0.5,0.7)

def bler_awgn(snr,df,qam):
    s=df[df['qam']==qam].sort_values('snr_db')
    return float(np.clip(np.interp(snr,s['snr_db'],s['bler'],left=1.,right=0.),0,1))
def bler_rayleigh(m,df,qam):
    s=df[df['qam']==qam].sort_values('snr_db');xs=s['snr_db'].to_numpy();ys=s['bler'].to_numpy()
    gb=10.**(m/10.);g=np.linspace(-15.,40.,400);gl=10.**(g/10.)
    bg=np.clip(np.interp(g,xs,ys,left=1.,right=0.),0,1);pdf=(1./gb)*np.exp(-gl/gb);jac=gl*np.log(10)/10.
    return float(np.clip(np.trapz(bg*pdf*jac,g),0,1))
def tt(a,shp):
    a=np.asarray(a,dtype=np.float32); return torch.from_numpy(a) if a.size else torch.zeros(shp,dtype=torch.float32)

def frame_stats(pb,ps,gtt):
    """return {thr:(tp,fp,score)} for one frame's box set, scored vs gtt."""
    out={}
    for thr in THRS:
        rs={thr:{'tp':[],'fp':[],'gt':0,'score':[]}}
        eval_utils.caluclate_tp_fp(tt(pb,(0,8,3)),tt(ps,(0,)),gtt,rs,thr)
        out[thr]=(rs[thr]['tp'],rs[thr]['fp'],rs[thr]['score'])
    return out

def ap_pick(pick_comp, LST, CST, lgn, cgn):
    """pick_comp[i] True=use comp(own GT) else late(own GT); global-sort AP with per-frame chosen GT count."""
    res={}
    gt_tot=int(sum(cgn[i] if pick_comp[i] else lgn[i] for i in range(len(pick_comp))))
    for thr in THRS:
        rs={thr:{'tp':[],'fp':[],'gt':gt_tot,'score':[]}}
        for i in range(len(pick_comp)):
            st=(CST if pick_comp[i] else LST)[i][thr]
            rs[thr]['tp']+=st[0]; rs[thr]['fp']+=st[1]; rs[thr]['score']+=st[2]
        res[thr]=eval_utils.calculate_ap(rs,thr,True)[0]
    return res[0.3],res[0.5],res[0.7]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--split',default='validate');ap.add_argument('--late',required=True)
    ap.add_argument('--comp',required=True);ap.add_argument('--cues',required=True);ap.add_argument('--out',required=True)
    o=ap.parse_args()
    dl=np.load(o.late,allow_pickle=True); dc=np.load(o.comp,allow_pickle=True)
    lb,ls,lg=list(dl['boxes']),list(dl['scores']),list(dl['gts'])
    cb,cs,cg=list(dc['boxes']),list(dc['scores']),list(dc['gts'])
    df=pd.read_csv(o.cues).reset_index(drop=True); bler=pd.read_csv(BLER_CSV)
    rf=pickle.load(open(RF_PATH,'rb')); feat=list(rf.feature_names_in_)
    sids=df['sample_id'].astype(int).to_numpy(); n=len(sids)
    print(f'[{o.split}] precomputing per-frame stats for {n} frames (each vs own GT)...',flush=True)
    LST=[];CST=[];lgn=[];cgn=[]
    for k,s in enumerate(sids):
        lgt=tt(lg[s],(0,8,3)); cgt=tt(cg[s],(0,8,3))
        lgn.append(lgt.shape[0]); cgn.append(cgt.shape[0])
        LST.append(frame_stats(lb[s],ls[s],lgt))
        CST.append(frame_stats(cb[s],cs[s],cgt))
        if k%400==0: print(f'  {k}/{n}',flush=True)
    allL=[False]*n; allC=[True]*n
    fL=ap_pick(allL,LST,CST,lgn,cgn); cE=ap_pick(allC,LST,CST,lgn,cgn)
    print(f'[{o.split}] Fixed-L         AP@.3/.5/.7 = {fL[0]:.4f}/{fL[1]:.4f}/{fL[2]:.4f}',flush=True)
    print(f'[{o.split}] Feature ceiling AP@.3/.5/.7 = {cE[0]:.4f}/{cE[1]:.4f}/{cE[2]:.4f}',flush=True)
    rows=[dict(split=o.split,policy='Fixed-L',channel='-',snr_db='-',ap30=fL[0],ap50=fL[1],ap70=fL[2]),
          dict(split=o.split,policy='Feature-ceiling',channel='-',snr_db='-',ap30=cE[0],ap50=cE[1],ap70=cE[2])]
    for ch,snr in OPS:
        d=df.copy(); d['est_snr_db']=snr; d['channel_is_rayleigh']=int(ch=='rayleigh')
        acts=rf.predict(d[feat]); bfn=bler_rayleigh if ch=='rayleigh' else bler_awgn
        b16=bfn(snr,bler,16); b256=bfn(snr,bler,256)
        a30,a50,a70=[],[],[]
        for r in range(N_REPEAT):
            rng=np.random.default_rng(SEED+r)
            pick=[]
            for k in range(n):
                a=acts[k]
                if a=='L': pick.append(False)
                else: pick.append(rng.random() > (b16 if a=='C16' else b256))
            r3=ap_pick(pick,LST,CST,lgn,cgn); a30.append(r3[0]);a50.append(r3[1]);a70.append(r3[2])
        rho_L=float((acts=='L').mean())
        print(f'  {ch:8s} SNR={snr:5.1f}: AP@.5={np.mean(a50):.4f}±{np.std(a50):.4f} AP@.7={np.mean(a70):.4f} rho_L={rho_L:.3f}',flush=True)
        rows.append(dict(split=o.split,policy='CA-TOSG',channel=ch,snr_db=snr,rho_L=rho_L,
                         ap30=float(np.mean(a30)),ap50=float(np.mean(a50)),ap70=float(np.mean(a70)),ap50_std=float(np.std(a50))))
    pd.DataFrame(rows).to_csv(o.out,index=False); print('wrote',o.out,flush=True)

if __name__=='__main__': main()
