#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 submit-B / 6d: TRUE end-to-end AP under the FROZEN selectors (descriptive only).

This is the AP companion to deployment.py. It is DESCRIPTIVE: the R9 decision was made once
(deployment.py, r9_decision.csv) and is NOT revisited here. No confirmatory / adjudicative
language is emitted; the table is reported as-is.

Consistency guarantee. The selector application and the channel replay are BIT-IDENTICAL to the F1
deployment: this file imports `load_manifest`, `bler16`, `rf_actions_stacked`, `tau_actions` and the
constants (ACTIONS, DATASET, DATA, MANIFEST, BLER_CSV, N_REPLAY, CSI_SEED) from eval_p2_deploy, and
draws snr_2d / is_ray_2d from the same rng(CSI_SEED) in the same order. So the per-frame action indices
(RF and tau) and the frame BLER_F are the exact draws of the F1 headline run.

AP vs F1 -- the one modelling difference (documented). The F1 deployment scores F with the ANALYTIC
BLER expectation eff_F = comp*(1-bF) + ego*bF. Global-sort AP is computed over box SETS and cannot take
an analytic expectation of a detection set, so the BLER outcome of every F frame is drawn by an explicit
Bernoulli(bF) coin (F delivered -> compressed boxes; F lost -> ego-only boxes). This is the only way to
push AP through a per-frame stochastic channel. The coin uses a SEPARATE, recorded generator
(BLER_COIN_SEED) so the deploy snr/channel draw sequence stays byte-identical; the same coin matrix is
shared by RF and tau within a split (paired). AP is the mean +/- std over the 200 realisations.

Scoring (global-sort, one canonical GT). The v3 scorer convention: every branch (late / comp / ego) is
scored against ONE canonical union GT per frame -- the all-CAV union GT materialised in the comp cache
gts (`comp_{split}.npz`). gt_tot (the AP denominator) is the sum of canonical GT counts, fixed
regardless of the per-frame branch. AP is the OPV2V global-sort AP (opencood.utils.eval_utils,
calculate_ap(..., global_sort_detections=True)), identical to true_e2e_global.py.

Action -> branch: E -> ego; L -> late; F -> comp if the coin survives, else ego.

Policies in the table:
  * Fixed-L        (budget-independent, deterministic): every frame -> late.
  * Feature-ceiling(budget-independent, deterministic): every frame -> comp (F always delivered).
  * ego-only       (budget-independent, deterministic): every frame -> ego.
  * CA-TOSG-RF     (per budget): the frozen selector_B0XX under the deployment replay.
  * SNR-threshold  (per budget): the tau* baseline under the same replay.
No oracle row (kept strictly to deployed policies + fixed references, to avoid any confirmatory read).

Outputs (results/p2_deploy/):
  true_e2e_ap.csv     -- split x budget x policy: ap30/50/70 (mean, and std over 200 realisations for
                         the stochastic RF/tau rows; std=0 / blank for the deterministic references).
  PROVENANCE_ap.txt   -- seeds, GT convention, the AP-vs-F1 coin note, cache hashes.

Run:  /path/to/env/python projects/ca_tosg/evaluation/end_to_end_ap.py
"""
import hashlib
import os
import sys

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# --- ca-tosg layout bootstrap (restructure commit 2/4) ---
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/evaluation/ablations', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
# --- end bootstrap ---
import deployment as D  # bit-identical selector + CSI machinery (single source)

P1 = D.P1
OPENCOOD = D.OPENCOOD
sys.path.insert(0, OPENCOOD)                                # for `import opencood.utils.eval_utils`
# P0 promotion: the mainline caches are the N=1 ones -- N=1 boxes/scores with the
# CANONICAL full-set union GT (the p4c_N1 caches' own gts are per-N and would score on a
# different ruler). Built by tools/build_n1_cache_shim.py; see docs/assumptions_ledger.md.
GS = os.path.join(OPENCOOD, 'peiyi_work/paper1/gs_rerun/n1_mainline')   # ego/late/comp_{split}.npz caches
OUT = D.OUT
# PROV_DIR was used at the bottom of main() but never defined here: the restructure (523f062)
# dropped it, so this script has crashed AFTER computing every AP number and BEFORE writing its
# provenance ever since -- which is why the committed true_e2e_ap.csv is a pre-restructure file.
PROV_DIR = D.PROV_DIR

ACTIONS = D.ACTIONS           # ['E','L','F']
SPLITS = D.SPLITS
N_REPLAY = D.N_REPLAY
CSI_SEED = D.CSI_SEED
BLER_COIN_SEED = 20260810     # SEPARATE from CSI_SEED; recorded in PROVENANCE. AP-only F-BLER coin.
THRS = (0.3, 0.5, 0.7)
LATE, COMP, EGO = 0, 1, 2     # branch indices (ST order), matching true_e2e_global.py
# action index (E=0,L=1,F=2) -> deterministic branch for the non-F actions; F handled by the coin.


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def tt(a, shp):
    a = np.asarray(a, dtype=np.float32)
    return torch.from_numpy(a) if a.size else torch.zeros(shp, dtype=torch.float32)


def frame_stats(pb, ps, gtt):
    """Per-frame per-threshold (tp, fp, score) arrays vs the canonical GT tensor gtt."""
    from opencood.utils import eval_utils
    out = {}
    for thr in THRS:
        rs = {thr: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
        eval_utils.caluclate_tp_fp(tt(pb, (0, 8, 3)), tt(ps, (0,)), gtt, rs, thr)
        out[thr] = (np.asarray(rs[thr]['tp']), np.asarray(rs[thr]['fp']), np.asarray(rs[thr]['score']))
    return out


def ap_pick(picks, ST, gtn):
    """picks[i] in {LATE,COMP,EGO}; ST=[LST,CST,EST]; gtn=per-frame canonical GT counts.
    Global-sort AP vs the ONE canonical GT (gt_tot = sum gtn), identical to true_e2e_global.py."""
    from opencood.utils import eval_utils
    gt_tot = int(sum(gtn))
    res = {}
    for thr in THRS:
        tp = np.concatenate([ST[picks[i]][i][thr][0] for i in range(len(picks))]) if picks else np.array([])
        fp = np.concatenate([ST[picks[i]][i][thr][1] for i in range(len(picks))]) if picks else np.array([])
        sc = np.concatenate([ST[picks[i]][i][thr][2] for i in range(len(picks))]) if picks else np.array([])
        rs = {thr: {'tp': tp.tolist(), 'fp': fp.tolist(), 'gt': gt_tot, 'score': sc.tolist()}}
        res[thr] = eval_utils.calculate_ap(rs, thr, True)[0]
    return res[0.3], res[0.5], res[0.7]


def branch_of(action_idx, coin_survive):
    """Vectorised action-index (0=E,1=L,2=F) -> branch (LATE/COMP/EGO) for one realisation.
    E->EGO, L->LATE, F->COMP if coin survives else EGO."""
    br = np.empty(action_idx.shape, dtype=int)
    br[action_idx == 0] = EGO
    br[action_idx == 1] = LATE
    isF = action_idx == 2
    br[isF] = np.where(coin_survive[isF], COMP, EGO)
    return br


def main():
    os.makedirs(OUT, exist_ok=True)
    man, budgets = D.load_manifest()
    tbl = pd.read_csv(D.BLER_CSV)
    tags = sorted(budgets)                                        # ['0.10','0.20','0.30']

    rows = []
    cache_hashes = {}
    for split in SPLITS:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        sids = ds['sample_id'].astype(int).to_numpy()

        dl = np.load(os.path.join(GS, f'late_{split}.npz'), allow_pickle=True)
        dc = np.load(os.path.join(GS, f'comp_{split}.npz'), allow_pickle=True)
        de = np.load(os.path.join(GS, f'ego_{split}.npz'), allow_pickle=True)
        for tagn, p in (('late', f'late_{split}.npz'), ('comp', f'comp_{split}.npz'), ('ego', f'ego_{split}.npz')):
            cache_hashes[p] = _sha256(os.path.join(GS, p))
        lb, ls = list(dl['boxes']), list(dl['scores'])
        cb, cs, cg = list(dc['boxes']), list(dc['scores']), list(dc['gts'])   # comp gts = canonical union GT
        eb, es = list(de['boxes']), list(de['scores'])

        # precompute per-frame stats vs the canonical GT for the three branches (once per split)
        print(f'[{split}] precomputing per-frame stats for {n} frames vs the canonical union GT...', flush=True)
        LST, CST, EST, gtn = [], [], [], []
        for k, s in enumerate(sids):
            canon = tt(cg[s], (0, 8, 3)); gtn.append(canon.shape[0])
            LST.append(frame_stats(lb[s], ls[s], canon))
            CST.append(frame_stats(cb[s], cs[s], canon))
            EST.append(frame_stats(eb[s], es[s], canon))
            if k % 500 == 0: print(f'  {k}/{n}', flush=True)
        ST = [LST, CST, EST]

        # ---- deterministic reference policies (budget-independent, no replay) ----
        fL = ap_pick([LATE] * n, ST, gtn)
        cE = ap_pick([COMP] * n, ST, gtn)
        eO = ap_pick([EGO] * n, ST, gtn)
        for pol, ap in (('Fixed-L', fL), ('Feature-ceiling', cE), ('ego-only', eO)):
            rows.append(dict(split=split, budget='-', policy=pol,
                             ap30_mean=round(ap[0], 4), ap30_std=0.0,
                             ap50_mean=round(ap[1], 4), ap50_std=0.0,
                             ap70_mean=round(ap[2], 4), ap70_std=0.0, n_realisations=1))
            print(f'[{split}] {pol:16s} AP@.3/.5/.7 = {ap[0]:.4f}/{ap[1]:.4f}/{ap[2]:.4f}', flush=True)

        # ---- replay draws (BIT-IDENTICAL to eval_p2_deploy) ----
        rng = np.random.default_rng(CSI_SEED)
        snr_2d = rng.uniform(0, 20, size=(N_REPLAY, n))
        is_ray_2d = rng.random(size=(N_REPLAY, n)) < 0.5
        bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(N_REPLAY)])
        # separate F-BLER coin (AP only); shared by RF and tau within the split (paired)
        coin_2d = np.random.default_rng(BLER_COIN_SEED).random(size=(N_REPLAY, n))
        survive_2d = coin_2d > bF_2d                                            # (R,n) bool: F delivered

        for tag in tags:
            bd = budgets[tag]; bmax = float(tag)
            rf_idx = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr_2d, is_ray_2d)   # (R,n) 0/1/2
            ta_idx = D.tau_actions(snr_2d, is_ray_2d, bd['tau'])                            # (R,n) 1/2
            for pol, act_2d in (('CA-TOSG-RF', rf_idx), ('SNR-threshold', ta_idx)):
                a30, a50, a70 = [], [], []
                for r in range(N_REPLAY):
                    picks = branch_of(act_2d[r], survive_2d[r]).tolist()
                    v = ap_pick(picks, ST, gtn)
                    a30.append(v[0]); a50.append(v[1]); a70.append(v[2])
                rows.append(dict(split=split, budget=bmax, policy=pol,
                                 ap30_mean=round(float(np.mean(a30)), 4), ap30_std=round(float(np.std(a30)), 4),
                                 ap50_mean=round(float(np.mean(a50)), 4), ap50_std=round(float(np.std(a50)), 4),
                                 ap70_mean=round(float(np.mean(a70)), 4), ap70_std=round(float(np.std(a70)), 4),
                                 n_realisations=N_REPLAY))
                print(f'[{split} B{int(bmax*100):03d}] {pol:14s} '
                      f'AP@.5={np.mean(a50):.4f}+/-{np.std(a50):.4f} AP@.7={np.mean(a70):.4f}', flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, 'true_e2e_ap.csv'), index=False)

    with open(os.path.join(PROV_DIR, 'PROVENANCE_ap.txt'), 'w') as f:
        f.write('CA-TOSG P2 submit-B / 6d -- TRUE end-to-end AP (end_to_end_ap.py). DESCRIPTIVE ONLY.\n' + '=' * 78 + '\n')
        f.write(f'manifest: results/manifests/FROZEN_MANIFEST.json (schema {man["schema"]}, freeze {man["freeze_timestamp"]})\n')
        f.write('Selector application + CSI replay are BIT-IDENTICAL to deployment.py '
                '(imported load_manifest/bler16/rf_actions_stacked/tau_actions; same rng(CSI_SEED) order).\n')
        f.write(f'CSI: {N_REPLAY} paired samplings/split, seed={CSI_SEED} (SNR~U[0,20], channel~Bernoulli(0.5 Rayleigh)).\n')
        f.write(f'AP-vs-F1 modelling note: F1 deploy uses the ANALYTIC BLER expectation; AP requires a per-frame\n'
                f'  Bernoulli(bF) coin (F delivered->compressed boxes, else ego). Coin generator seed={BLER_COIN_SEED}\n'
                f'  (SEPARATE from CSI_SEED so deploy draws stay byte-identical); same coin shared by RF and tau (paired).\n')
        f.write('Scoring: OPV2V global-sort AP (eval_utils.calculate_ap global_sort=True); ONE canonical union GT per\n'
                '  frame = comp cache gts (all-CAV union); gt_tot fixed regardless of branch. Action->branch: '
                'E->ego, L->late, F->comp|ego.\n')
        f.write('Policies: Fixed-L / Feature-ceiling / ego-only (deterministic references, budget-independent); '
                'CA-TOSG-RF + SNR-threshold per budget. No oracle row.\n')
        f.write('AP caches (sha256):\n')
        for p in sorted(cache_hashes):
            f.write(f'  {p}: {cache_hashes[p]}\n')
        f.write('DESCRIPTIVE table; the R9 decision (r9_decision.csv) is not revisited here.\n')
    print('\nwrote results/main/true_e2e_ap.csv + PROVENANCE_ap.txt', flush=True)


if __name__ == '__main__':
    main()
