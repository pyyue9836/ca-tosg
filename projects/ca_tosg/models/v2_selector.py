#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R26 E-1 — fit and freeze the v2 selector on validate only. Zero GPU.

The v1 discipline is carried over unchanged and is NOT relaxed because the cue set was amended: the
candidate block is parsed from `docs/experiment_protocol.md` (single normative source), the LOSO is
scene-level 9-fold with each scene held out exactly once, and the per-budget walk uses the
pre-registered tie-break order.

WHAT IS DIFFERENT UNDER v2, AND WHY
------------------------------------
* **features** come from `v2_ego_local_23d` (§9.2) -- ego-local, no ground truth, no post-decision
  information. `ego_num_objects` and `num_cavs` are gone.
* **payload is a per-frame matrix** (§9.3(i)), not the constant `{0, 0.024, 0.99}` vector. It is
  charged for the ATTEMPT and never multiplied by a success probability (§9.3(j)).
* **budgets are β·B_F** (§10.1), not absolute Msym: β ∈ {0.10, 0.20, 0.30} -> B_max = β × 3.14175.
* **feasibility is structural only** (§9.3(o)): the v1 `bler_F < 0.999` mask is retired. With λ ≥ 0
  and B_F > 0, `eff_F ≤ eff_E` already implies `U_F ≤ U_E`, so the objective does the work a
  threshold would have duplicated.

**v1 results are diagnostic only and take no part in any v2 selection** (§9.2 B-4).

    python projects/ca_tosg/models/v2_selector.py
"""
from __future__ import annotations

import itertools
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
V2 = os.path.join(ROOT, 'results', 'v2')
PROTOCOL = os.path.join(ROOT, 'docs', 'experiment_protocol.md')
OUT_MAN = os.path.join(ROOT, 'results', 'manifests', 'V2_FROZEN_MANIFEST.json')
FOLDS = os.path.join(ROOT, 'results', 'manifests', 'v2_validate_loso_folds.csv')

ACTIONS = ['E', 'L', 'F']
B_F = 3.14175


def parse_candidates():
    txt = open(PROTOCOL, encoding='utf-8').read()
    m = re.search(r'```json CATOSG-CANDIDATES\n(.*?)\n```', txt, re.S)
    if not m:
        raise SystemExit('candidate block not found in docs/experiment_protocol.md')
    b = json.loads(m.group(1))
    hp = b['hyperparameters']
    combos = list(itertools.product(hp['n_estimators'], hp['max_depth'], hp['min_samples_leaf'],
                                    hp['max_features'], b['class_weight'], b['lambda_grid']))
    cands = [dict(n_estimators=n, max_depth=d, min_samples_leaf=l, max_features=f,
                  class_weight=c, lam=lam) for n, d, l, f, c, lam in combos]
    return b, cands


def load_grid(regime='ideal'):
    g = pd.read_csv(os.path.join(V2, f'v2_grid_validate_{regime}.csv'))
    cues = pd.read_csv(os.path.join(V2, 'wp6_cues_validate.csv'))
    meta = json.load(open(os.path.join(V2, 'wp6_cues_validate.json')))
    feat_cols = [c for c in meta['perception_fields']]
    X_f = cues[feat_cols].to_numpy(float)                    # per FRAME
    fi = g.sample_id.to_numpy()
    X = np.column_stack([X_f[fi],
                         g.snr_db.to_numpy(float),
                         (g.channel.to_numpy() == 'rayleigh').astype(float)])
    names = feat_cols + ['est_snr_db', 'channel_is_rayleigh']
    eff = g[['eff_E', 'eff_L', 'eff_F']].to_numpy()
    B = g[['B_E', 'B_L', 'B_F']].to_numpy()
    return g, X, names, eff, B


def lam_labels(eff, B, lam):
    """§9.3(m): U = eff - lambda*B, ties broken E > L > F (argmax takes the first maximum)."""
    return (eff - lam * B).argmax(1)


def realised(pred, eff, B):
    r = np.arange(len(pred))
    return eff[r, pred].mean(), B[r, pred].mean()


def main():
    block, cands = parse_candidates()
    seed = block['seed']
    betas = block['budgets']
    g, X, names, eff, B = load_grid('ideal')
    scenes = g.scene.to_numpy()
    uscenes = sorted(pd.unique(scenes))
    print(f'v2 selector: {len(g)} grid rows, {len(names)} features, {len(cands)} candidates, '
          f'{len(uscenes)} scenes')
    print(f'budgets beta {betas} -> B_max {[round(b * B_F, 5) for b in betas]} Msym')

    rows = []
    for ci, c in enumerate(cands):
        y = lam_labels(eff, B, c['lam'])
        for s in uscenes:
            te = scenes == s
            tr = ~te
            if len(np.unique(y[tr])) < 2:
                f1m, bm = realised(np.full(te.sum(), y[tr][0] if tr.any() else 0), eff[te], B[te])
            else:
                rf = RandomForestClassifier(
                    n_estimators=c['n_estimators'], max_depth=c['max_depth'],
                    min_samples_leaf=c['min_samples_leaf'], max_features=c['max_features'],
                    class_weight=c['class_weight'], random_state=seed, n_jobs=-1)
                rf.fit(X[tr], y[tr])
                f1m, bm = realised(rf.predict(X[te]), eff[te], B[te])
            rows.append(dict(fold_scene=s, candidate_index=ci, **{k: c[k] for k in c},
                             n_frames=int(te.sum()), realised_f1=f1m, realised_payload=bm))
        if ci % 16 == 0:
            print(f'  candidate {ci}/{len(cands)}', flush=True)
    folds = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(FOLDS), exist_ok=True)
    folds.to_csv(FOLDS, index=False)
    print(f'wrote {os.path.relpath(FOLDS, ROOT)}  ({len(folds)} rows)')

    # R6 semantic split: performance = scene-mean F1; feasibility = frame-weighted payload
    agg = folds.groupby('candidate_index').apply(
        lambda d: pd.Series({
            'scene_mean_f1': d.realised_f1.mean(),
            'frame_weighted_f1': np.average(d.realised_f1, weights=d.n_frames),
            'frame_weighted_payload': np.average(d.realised_payload, weights=d.n_frames)}),
        include_groups=False).reset_index()
    for k in ('lam', 'max_depth', 'min_samples_leaf', 'max_features', 'class_weight'):
        agg[k] = [cands[i][k] for i in agg.candidate_index]

    walks, frozen = {}, {}
    for beta in betas:
        bmax = beta * B_F
        feas = agg[agg.frame_weighted_payload <= bmax].copy()
        walks[str(beta)] = {
            'B_max_msym': bmax, 'n_feasible': int(len(feas)), 'n_candidates': int(len(agg))}
        if not len(feas):
            walks[str(beta)]['selected'] = None
            continue
        feas['depth_key'] = [999 if d is None or (isinstance(d, float) and np.isnan(d)) else d
                             for d in feas.max_depth]
        feas = feas.sort_values(['scene_mean_f1', 'frame_weighted_payload', 'depth_key',
                                 'candidate_index'], ascending=[False, True, True, True])
        best = feas.iloc[0]
        ci = int(best.candidate_index)
        c = cands[ci]
        y = lam_labels(eff, B, c['lam'])
        rf = RandomForestClassifier(
            n_estimators=c['n_estimators'], max_depth=c['max_depth'],
            min_samples_leaf=c['min_samples_leaf'], max_features=c['max_features'],
            class_weight=c['class_weight'], random_state=seed, n_jobs=-1).fit(X, y)
        pred = rf.predict(X)
        f1_full, b_full = realised(pred, eff, B)
        mix = {a: float((pred == i).mean()) for i, a in enumerate(ACTIONS)}
        walks[str(beta)].update({
            'selected_candidate_index': ci, 'lambda': c['lam'],
            'loso_scene_mean_f1': float(best.scene_mean_f1),
            'loso_frame_weighted_f1': float(best.frame_weighted_f1),
            'loso_frame_weighted_payload': float(best.frame_weighted_payload),
            'frozen_validate_f1': float(f1_full), 'frozen_validate_payload': float(b_full),
            'budget_satisfied': bool(b_full <= bmax), 'action_mix': mix,
            'oracle_f1': float(eff.max(1).mean())})
        frozen[str(beta)] = walks[str(beta)]
        print(f'  beta {beta}: cand {ci} lam {c["lam"]}  LOSO scene-mean F1 '
              f'{best.scene_mean_f1:.5f}  payload {best.frame_weighted_payload:.5f}  '
              f'frozen {f1_full:.5f} @ {b_full:.5f}  mix {mix}')

    # IRON RULE: every frozen model must satisfy its budget on full validate, or nothing is written
    bad = [b for b, w in frozen.items() if not w['budget_satisfied']]
    man = {'schema': 'catosg-v2-frozen-manifest/1', 'split': 'validate', 'regime': 'ideal',
           'features': names, 'n_features': len(names), 'cue_schema': 'v2_ego_local_23d',
           'candidates': len(cands), 'seed': seed, 'B_F_msym': B_F, 'betas': betas,
           'feasibility': 'structural only (§9.3(o)); the v1 bler_F<0.999 mask is retired',
           'v1_status': 'DIAGNOSTIC ONLY -- takes no part in any v2 selection (§9.2 B-4)',
           'walks': walks, 'iron_rule_violations': bad}
    if bad:
        print(f'\nIRON RULE VIOLATED at beta {bad} -- manifest NOT written')
        with open(OUT_MAN + '.FAILED', 'w') as f:
            json.dump(man, f, indent=1)
        return 1
    with open(OUT_MAN, 'w') as f:
        json.dump(man, f, indent=1)
    print(f'wrote {os.path.relpath(OUT_MAN, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
