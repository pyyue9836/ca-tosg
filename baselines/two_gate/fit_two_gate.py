#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R21-A: fit and FREEZE the two-gate heuristic (Change-log R21-A pre-registration).

The policy, fixed before this file existed:

    a_t = E              if d_t <= tau_E
          F              else if r_t >= tau_F
          L              otherwise

with `d_t = s * cue_t` and `r_t = 1 - BLER_F(snr, channel)` read from the COMMITTED Sionna table
(zero new parameters). Two free scalars per budget.

Discipline is the mainline walk's, on the mainline's own fitting surface (the deterministic validate
grid, never the replay, never test/Culver):

  candidate      = (cue, sign), six of them, enumerated in the pre-registered order
  per LOSO fold  = fit (tau_E, tau_F) on the 8 in-fold scenes by max frame-weighted F1 subject to
                   frame-weighted payload <= B_max; apply to the held-out scene -> OOF
  candidate score= frame_weighted_oof_f1; feasibility = frame_weighted_oof_payload <= B_max
  tie-break      = [max_f1, min_payload, min_candidate_index]   (`shallower_model` has no analogue
                   here and is dropped, as recorded in the pre-registration)
  refit          = the winner's deployed thresholds, refitted on the FULL validate grid under the
                   same hard constraint
  infeasible     = reported, never relaxed

R21-A-2 AMENDMENT (`--arm dgate`), pre-registered in the change-log of the same name after the rule
above proved unable to bid at two of three budgets: the F gate becomes a conjunction,

    a_t = E if d_t <= tau_E; F if d_t >= tau_D and r_t >= tau_F; else L

-- THREE scalars, labelled as three everywhere. Everything else (candidates, grids, folds, surface,
constraint, tie-break, descriptive-only reporting) is unchanged, and `tau_D = -inf` reduces it
exactly to the two-gate arm, so the amended class strictly contains the pre-registered one.

Output: results/manifests/R21A{,2}_MANIFEST.json + results/baselines/two_gate_runs/

    python tools/run_baselines.py two_gate --train                # R21-A, as pre-registered
    python tools/run_baselines.py two_gate --train --arm dgate    # R21-A-2 amendment
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_CT_ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/utils'):
    sys.path.insert(0, os.path.join(_CT_ROOT, _d))

import deployment as D                                                            # noqa: E402

P1 = D.P1
OUT_RUNS = os.path.join(P1, 'results/baselines/two_gate_runs')
MANIFEST = os.path.join(P1, 'results/manifests/R21A_MANIFEST.json')
MANIFEST_DGATE = os.path.join(P1, 'results/manifests/R21A2_MANIFEST.json')
FOLDS_CSV = os.path.join(P1, 'results/manifests/validate_loso_folds.csv')

# ---- the closed pre-registered candidate set and grids (Change-log R21-A) ----
CUES = ('ego_num_objects', 'pcd_num_points', 'pcd_density_0_20')
SIGNS = (1, -1)
CANDIDATES = [(c, s) for c in CUES for s in SIGNS]            # index 0..5, pre-registered order
Q_GRID = np.round(np.arange(0.05, 1.0001, 0.05), 4)           # 20 quantiles; -inf prepended
TAU_F_GRID = np.round(np.arange(0.0, 1.0001, 0.05), 4)        # 21 values; +inf appended
BUDGETS = (0.10, 0.20, 0.30)
PAY_E, PAY_L, PAY_F = D.PAY['E'], D.PAY['L'], D.PAY['F']


def _md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def fuse(msg):
    raise SystemExit(f'R21-A FUSE: {msg}')


def load_surface():
    """The validate fitting surface: grid rows joined to the per-frame cues."""
    grid = pd.read_csv(os.path.join(D.GRID_DIR, 'p2_grid_validate.csv'))
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET['validate']))
    missing = [c for c in CUES if c not in ds.columns]
    if missing:
        fuse(f'cue(s) absent from the committed cue table: {missing}')
    surf = grid.merge(ds[['sample_id', *CUES]], on='sample_id', how='left')
    if surf[list(CUES)].isna().any().any():
        fuse('cue join left NaNs -- grid sample_ids not covered by the cue table')
    if len(surf) != len(grid):
        fuse('cue join changed the row count')
    return surf


def tau_e_values(d):
    """The pre-registered tau_E ladder for a difficulty vector: -inf, then the 20 quantiles."""
    return np.concatenate([[-np.inf], np.quantile(d, Q_GRID)])


def fit_curve(d_fit, r_fit, effE, effL, effF, tau_e_vals):
    """(F1, payload) for every (tau_E, tau_F) on the pre-registered grid, over the given rows.

    Vectorised by sorting once on d: for a threshold tau_E the E-set is a prefix of that order, so a
    cumulative sum gives every tau_E at O(1) once tau_F fixes the L/F split.
    """
    order = np.argsort(d_fit, kind='stable')
    d_sorted = d_fit[order]
    effE_sorted = effE[order]
    n = len(d_fit)
    ks = np.searchsorted(d_sorted, tau_e_vals, side='right')          # |tau_E| prefix lengths
    cum_effE = np.concatenate([[0.0], np.cumsum(effE_sorted)])
    f1 = np.empty((len(tau_e_vals), len(TAU_F_GRID) + 1))
    pay = np.empty_like(f1)
    for j in range(len(TAU_F_GRID) + 1):
        take_f = (r_fit >= TAU_F_GRID[j]) if j < len(TAU_F_GRID) else np.zeros(n, bool)   # last = +inf
        base_f1 = np.where(take_f, effF, effL)[order]
        base_pay = np.where(take_f, PAY_F, PAY_L)[order]
        cum_f1 = np.concatenate([[0.0], np.cumsum(base_f1)])
        cum_pay = np.concatenate([[0.0], np.cumsum(base_pay)])
        f1[:, j] = (cum_effE[ks] + cum_f1[-1] - cum_f1[ks]) / n
        pay[:, j] = (PAY_E * ks + cum_pay[-1] - cum_pay[ks]) / n
    return f1, pay


def pick(f1, pay, bmax):
    """max_f1 -> min_payload -> first in the pre-registered enumeration order. None if infeasible."""
    feas = pay <= bmax + 1e-12
    if not feas.any():
        return None
    big = np.where(feas, f1, -np.inf)
    best = big.max()
    cand = np.argwhere(big >= best - 1e-12)
    paycand = pay[cand[:, 0], cand[:, 1]]
    keep = cand[paycand <= paycand.min() + 1e-12]
    i, j = keep[0]                                     # enumeration order: tau_E outer, tau_F inner
    return int(i), int(j), float(f1[i, j]), float(pay[i, j])


def fit_curve3(d_fit, r_fit, effE, effL, effF, tau_vals):
    """R21-A-2: (F1, payload) over the (tau_E, tau_D, tau_F) grid; cells with tau_E > tau_D are -inf.

    Same sort-once trick: in d-order the E set is the prefix [0,k_E), the F-eligible set is the
    suffix [k_D,n) intersected with r >= tau_F, and everything else is L.
    """
    order = np.argsort(d_fit, kind='stable')
    d_sorted = d_fit[order]
    n = len(d_fit)
    ks = np.searchsorted(d_sorted, tau_vals, side='right')
    cum_effE = np.concatenate([[0.0], np.cumsum(effE[order])])
    cum_effL = np.concatenate([[0.0], np.cumsum(effL[order])])
    nT, nF = len(tau_vals), len(TAU_F_GRID) + 1
    f1 = np.full((nT, nT, nF), -np.inf)
    pay = np.full((nT, nT, nF), np.inf)
    kE = ks[:, None]
    kD = ks[None, :]
    ok = kE <= kD
    for j in range(nF):
        take_f = (r_fit >= TAU_F_GRID[j]) if j < len(TAU_F_GRID) else np.zeros(n, bool)
        cum_x = np.concatenate([[0.0], np.cumsum(np.where(take_f, effF, effL)[order])])
        cum_p = np.concatenate([[0.0], np.cumsum(np.where(take_f, PAY_F, PAY_L)[order])])
        tot_f1 = cum_effE[kE] + (cum_effL[kD] - cum_effL[kE]) + (cum_x[-1] - cum_x[kD])
        tot_pay = PAY_E * kE + PAY_L * (kD - kE) + (cum_p[-1] - cum_p[kD])
        f1[:, :, j] = np.where(ok, tot_f1 / n, -np.inf)
        pay[:, :, j] = np.where(ok, tot_pay / n, np.inf)
    return f1, pay


def pick3(f1, pay, bmax):
    """max_f1 -> min_payload -> first in enumeration order (tau_E outer, tau_D middle, tau_F inner)."""
    feas = pay <= bmax + 1e-12
    if not feas.any():
        return None
    big = np.where(feas, f1, -np.inf)
    best = big.max()
    cand = np.argwhere(big >= best - 1e-12)
    paycand = pay[cand[:, 0], cand[:, 1], cand[:, 2]]
    keep = cand[paycand <= paycand.min() + 1e-12]
    i, j, k = keep[0]
    return int(i), int(j), int(k), float(f1[i, j, k]), float(pay[i, j, k])


def apply_policy3(d, r, effE, effL, effF, tau_E, tau_D, tau_F):
    """Realised (action index, eff, payload) for one frozen R21-A-2 threshold triple."""
    idx = np.where(d <= tau_E, 0, np.where((d >= tau_D) & (r >= tau_F), 2, 1))
    return idx, np.choose(idx, [effE, effL, effF]), np.choose(idx, [PAY_E, PAY_L, PAY_F])


def apply_policy(d, r, effE, effL, effF, tau_E, tau_F):
    """Realised (action index, eff, payload) arrays for one frozen threshold pair."""
    idx = np.where(d <= tau_E, 0, np.where(r >= tau_F, 2, 1))
    eff = np.choose(idx, [effE, effL, effF])
    pay = np.choose(idx, [PAY_E, PAY_L, PAY_F])
    return idx, eff, pay


def fit_thresholds(arm, d, r, effE, effL, effF, bmax):
    """Fit the arm's thresholds on the given rows. Returns (tau tuple, indices, f1, payload) or None."""
    tvals = tau_e_values(d)
    if arm == 'two_gate':
        sel = pick(*fit_curve(d, r, effE, effL, effF, tvals), bmax)
        if sel is None:
            return None
        i, j, f1, pay = sel
        tF = TAU_F_GRID[j] if j < len(TAU_F_GRID) else np.inf
        return (float(tvals[i]), float(tF)), (i, None, j), f1, pay
    sel = pick3(*fit_curve3(d, r, effE, effL, effF, tvals), bmax)
    if sel is None:
        return None
    i, j, k, f1, pay = sel
    tF = TAU_F_GRID[k] if k < len(TAU_F_GRID) else np.inf
    return (float(tvals[i]), float(tvals[j]), float(tF)), (i, j, k), f1, pay


def apply_thresholds(arm, taus, d, r, effE, effL, effF):
    if arm == 'two_gate':
        return apply_policy(d, r, effE, effL, effF, *taus)
    return apply_policy3(d, r, effE, effL, effF, *taus)


def parse_arm(argv=None):
    """--arm is read here, not only under __main__, so tools/run_baselines.py can pass it through."""
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=('two_gate', 'dgate'), default='two_gate',
                    help='two_gate = R21-A as pre-registered; dgate = the R21-A-2 amendment')
    return ap.parse_known_args(argv)[0].arm


def main(arm=None):
    arm = parse_arm() if arm is None else arm
    os.makedirs(OUT_RUNS, exist_ok=True)
    surf = load_surface()
    scenes = sorted(pd.read_csv(FOLDS_CSV)['fold_scene'].unique())
    if len(scenes) != 9 or set(scenes) != set(surf['scene'].unique()):
        fuse('LOSO scene set does not match the frozen validate scenes')

    r_all = 1.0 - surf['bler_F'].to_numpy(float)
    effE = surf['eff_E'].to_numpy(float)
    effL = surf['eff_L'].to_numpy(float)
    effF = surf['eff_F'].to_numpy(float)
    scene_arr = surf['scene'].to_numpy()

    budgets, walk_rows = {}, []
    for bmax in BUDGETS:
        tag = f'{bmax:.2f}'
        per_cand = []
        for ci, (cue, sign) in enumerate(CANDIDATES):
            d_all = sign * surf[cue].to_numpy(float)
            oof_eff = np.empty(len(surf))
            oof_pay = np.empty(len(surf))
            fold_ok = True
            for sc in scenes:
                te = scene_arr == sc
                tr = ~te
                fit = fit_thresholds(arm, d_all[tr], r_all[tr], effE[tr], effL[tr], effF[tr], bmax)
                if fit is None:                       # no feasible threshold set in this fold
                    fold_ok = False
                    break
                taus = fit[0]
                _, e, p = apply_thresholds(arm, taus, d_all[te], r_all[te],
                                           effE[te], effL[te], effF[te])
                oof_eff[te] = e
                oof_pay[te] = p
            if not fold_ok:
                per_cand.append(dict(candidate_index=ci, cue=cue, sign=sign, feasible=False,
                                     oof_f1=np.nan, oof_payload=np.nan))
                continue
            per_cand.append(dict(candidate_index=ci, cue=cue, sign=sign, feasible=True,
                                 oof_f1=float(oof_eff.mean()), oof_payload=float(oof_pay.mean())))

        for row in per_cand:
            walk_rows.append(dict(budget=bmax, **row))
        feas = [c for c in per_cand if c['feasible'] and c['oof_payload'] <= bmax + 1e-12]
        if not feas:
            budgets[tag] = dict(feasible=False,
                                note='no candidate met the OOF payload constraint; NOT relaxed')
            print(f'[B{int(bmax*100):03d}] INFEASIBLE -- no candidate meets the constraint')
            continue
        best_f1 = max(c['oof_f1'] for c in feas)
        tied = [c for c in feas if c['oof_f1'] >= best_f1 - 1e-12]
        min_pay = min(c['oof_payload'] for c in tied)
        tied = [c for c in tied if c['oof_payload'] <= min_pay + 1e-12]
        win = min(tied, key=lambda c: c['candidate_index'])

        # refit on the FULL validate grid (the mainline's refit-on-all-of-validate analogue)
        d_all = win['sign'] * surf[win['cue']].to_numpy(float)
        fit = fit_thresholds(arm, d_all, r_all, effE, effL, effF, bmax)
        if fit is None:
            fuse(f'budget {tag}: winner {win["cue"]}/{win["sign"]:+d} infeasible on the full grid')
        taus, (i, jD, jF), vf1, vpay = fit
        tE, tF = taus[0], taus[-1]
        tD = taus[1] if arm == 'dgate' else -np.inf
        idx, _, _ = apply_thresholds(arm, taus, d_all, r_all, effE, effL, effF)
        rho = {a: float((idx == k).mean()) for k, a in enumerate(D.ACTIONS)}
        budgets[tag] = dict(
            feasible=True, candidate_index=win['candidate_index'], cue=win['cue'], sign=win['sign'],
            tau_E=(None if np.isneginf(tE) else round(tE, 6)),
            tau_E_is_never_E=bool(np.isneginf(tE)),
            tau_E_quantile=(None if i == 0 else float(Q_GRID[i - 1])),
            tau_D=(None if np.isneginf(tD) else round(float(tD), 6)),
            tau_D_quantile=(None if (arm != 'dgate' or jD == 0) else float(Q_GRID[jD - 1])),
            tau_F=(None if np.isinf(tF) else round(tF, 6)), tau_F_is_never_F=bool(np.isinf(tF)),
            n_candidates=len(CANDIDATES), n_feasible=len(feas),
            loso_frame_weighted_f1=round(win['oof_f1'], 6),
            loso_frame_weighted_payload=round(win['oof_payload'], 6),
            frozen_validate_f1=round(vf1, 6), frozen_validate_payload=round(vpay, 6),
            budget_satisfied=bool(vpay <= bmax + 1e-12),
            validate_grid_rho={k: round(v, 6) for k, v in rho.items()})
        print(f'[B{int(bmax*100):03d}] cand {win["candidate_index"]} '
              f'{win["cue"]}/{win["sign"]:+d}  tau_E={tE:.4g} '
              + (f'tau_D={tD:.4g} ' if arm == 'dgate' else '') + f'tau_F={tF:.4g}  '
              f'OOF f1={win["oof_f1"]:.5f} pay={win["oof_payload"]:.5f}  '
              f'validate f1={vf1:.5f} pay={vpay:.5f}  rho_E={rho["E"]:.4f}', flush=True)

    walk_csv = os.path.join(OUT_RUNS, f'{"r21a2" if arm == "dgate" else "r21a"}_candidate_walk.csv')
    pd.DataFrame(walk_rows).to_csv(walk_csv, index=False)
    man = dict(
        schema=f'catosg-r21a{"2" if arm == "dgate" else ""}-manifest/1',
        protocol=f'CA-TOSG Change-log R21-A{"-2 (AMENDMENT)" if arm == "dgate" else ""} '
                 '(docs/experiment_protocol.md)',
        arm=('three-scalar hand rule: difficulty gate + difficulty-conditioned link gate '
             '(R21-A-2 amendment), DESCRIPTIVE, not deployed') if arm == 'dgate' else
            'two-gate heuristic (difficulty gate + link-reliability gate), DESCRIPTIVE, not deployed',
        n_free_scalars=(3 if arm == 'dgate' else 2),
        policy=('a=E if d<=tau_E; F if d>=tau_D and r>=tau_F; else L.  d=sign*cue, '
                'r=1-BLER_F (committed table)') if arm == 'dgate' else
               'a=E if d<=tau_E; elif r>=tau_F: F; else L.  d=sign*cue, r=1-BLER_F (committed table)',
        candidates=[dict(index=i, cue=c, sign=s) for i, (c, s) in enumerate(CANDIDATES)],
        tau_E_grid='{-inf} U quantile(d, 0.05..1.00 step 0.05)',
        tau_D_grid=('{-inf} U quantile(d, 0.05..1.00 step 0.05), restricted to tau_E <= tau_D'
                    if arm == 'dgate' else None),
        tau_F_grid='{0.00..1.00 step 0.05} U {+inf}',
        selection=dict(surface='data/p2/p2_grid_validate.csv', loso_folds=9,
                       score='frame_weighted_oof_f1', feasibility='frame_weighted_oof_payload<=B_max',
                       tie_break=['max_f1', 'min_payload', 'min_candidate_index'],
                       dropped_tie_break_key='shallower_model (no analogue; recorded in R21-A)'),
        environment=dict(python=sys.version.split()[0], numpy=np.__version__, pandas=pd.__version__),
        inputs={
            'train_grid': dict(file='data/p2/p2_grid_validate.csv',
                               md5=_md5(os.path.join(D.GRID_DIR, 'p2_grid_validate.csv'))),
            'cue_source': dict(file='data/p2/dataset_validate_n1.csv',
                               md5=_md5(os.path.join(D.DATA, D.DATASET['validate']))),
            'bler_table': dict(file='results/channel/bler_sionna.csv', md5=_md5(D.BLER_CSV)),
            'folds_csv': dict(file='results/manifests/validate_loso_folds.csv',
                              sha256=_sha256(FOLDS_CSV)),
        },
        budgets=budgets,
        note='test/Culver were never read by this script. Thresholds transfer as ABSOLUTE values '
             '(the tau_E quantile is a validate quantile; it is NOT re-quantiled per split).')
    out_manifest = MANIFEST_DGATE if arm == 'dgate' else MANIFEST
    with open(out_manifest, 'w') as f:
        json.dump(man, f, indent=1)
    print(f'\nwrote {out_manifest}\n      {walk_csv}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
