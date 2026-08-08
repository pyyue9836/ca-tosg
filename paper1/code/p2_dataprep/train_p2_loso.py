#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 submit-A: scene-level 9-fold LOSO selection + freeze (ONE MODEL PER BUDGET).

The candidate set is PARSED from PROTOCOL.md's ```json CATOSG-CANDIDATES``` block (single source of
truth -- no candidate values are hard-coded here). A candidate = (RF hyper-parameters, class_weight,
lambda). Procedure (PROTOCOL sec 6):

  1. Load the validate grid (masked oracle substrate) + join the 21 ego-side cues (versionless
     dataset_validate.csv). Features = cues + est_snr_db (cell SNR) + channel_is_rayleigh.
  2. 9-fold scene-level LOSO: each scene held out EXACTLY ONCE. For every candidate, fit the RF on the
     8 non-held-out scenes' lambda-oracle labels and score REALISED F1/payload (mean eff / mean
     payload of the selector's own picks) on the held-out scene. Log every (fold x candidate) to
     validate_loso_folds.csv.
  3. Per B_max, pick the candidate whose scene-mean payload <= B_max with the highest scene-mean F1;
     tie-break: F1 -> payload -> shallower max_depth (null=deepest, last) -> smallest candidate index.
  4. tau*(B_max): budget-matched SNR-threshold baseline on the full validate grid.
  5. Freeze one model per budget on all 1980 frames -> selector_B0{10,20,30}.pkl; write
     FROZEN_MANIFEST.json (schema, three sha256, input md5s, scenes, per-budget hp/lambda*/tau*, ts).

CPU only, deterministic (seed from the JSON block). Run:
  /path/to/env/python paper1/code/p2_dataprep/train_p2_loso.py
"""
import hashlib
import itertools
import json
import os
import pickle
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
CUES_CSV = os.path.join(DATA, 'dataset_validate.csv')            # versionless (== dataset_validate_v3.csv)
GRID_CSV = os.path.join(P1, 'data/p2/p2_grid_validate.csv')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
PROTOCOL = os.path.join(P1, 'PROTOCOL.md')
OUT_MODEL = os.path.join(P1, 'data/p2')
OUT_PROV = os.path.join(P1, 'results/p2_dataprep')
MANIFEST = os.path.join(OUT_PROV, 'FROZEN_MANIFEST.json')
FOLDS_CSV = os.path.join(OUT_PROV, 'validate_loso_folds.csv')
MANIFEST_SCHEMA = 'catosg-frozen-manifest/1'

ACTIONS = ['E', 'L', 'F']
PAYLOAD = {'E': 0.0, 'L': 0.024, 'F': 0.99}                     # Msym (PROTOCOL sec 4)
PAYVEC = np.array([PAYLOAD[a] for a in ACTIONS])
BLER_INFEASIBLE = 0.999
EXCLUDE = {
    'sample_id', 'cav_keys', 'channel_type',
    *[f'{m}_{s}' for m in ('late', 'early', 'intermediate', 'compressed')
      for s in ('num_pred', 'num_gt', 'tp', 'fp', 'fn', 'precision', 'recall', 'f1', 'payload_Mbit')],
    *[f'{m}_f1_gain_over_late' for m in ('late', 'early', 'intermediate', 'compressed')],
    *[f'{m}_gain_per_extra_Mbit' for m in ('late', 'early', 'intermediate', 'compressed')],
    'best_method_by_f1', 'best_level_by_f1', 'best_f1', 'best_payload_Mbit',
    'bler_C16', 'bler_C256', 'eff_f1_L', 'eff_f1_C16', 'eff_f1_C256', 'oracle_3way', 'ego_f1',
    'est_snr_db', 'channel_is_rayleigh',
}


def _md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def parse_candidates():
    """Extract and parse the single-source-of-truth CATOSG-CANDIDATES JSON block from PROTOCOL.md."""
    txt = open(PROTOCOL, encoding='utf-8').read()
    m = re.search(r'```json CATOSG-CANDIDATES\s*(\{.*?\})\s*```', txt, re.S)
    if not m:
        raise SystemExit('CATOSG-CANDIDATES block not found in PROTOCOL.md (single source of truth).')
    return json.loads(m.group(1)), hashlib.md5(m.group(1).encode()).hexdigest()


def build_candidate_list(spec):
    """Deterministic enumeration -> list of dicts with a stable candidate index (for tie-break)."""
    hp = spec['hyperparameters']
    combos = itertools.product(hp['n_estimators'], hp['max_depth'], hp['min_samples_leaf'],
                               hp['max_features'], spec['class_weight'], spec['lambda_grid'])
    cands = []
    for i, (ne, md, ml, mf, cw, lam) in enumerate(combos):
        cands.append(dict(index=i, n_estimators=ne, max_depth=md, min_samples_leaf=ml,
                          max_features=mf, class_weight=cw, lam=float(lam)))
    return cands


def lam_labels(eff, bler_F, lam):
    util = eff - lam * PAYVEC[None, :]
    util[bler_F >= BLER_INFEASIBLE, 2] = -np.inf
    return util.argmax(1)


def rf_of(cand, seed):
    return RandomForestClassifier(
        n_estimators=cand['n_estimators'], max_depth=cand['max_depth'],
        min_samples_leaf=cand['min_samples_leaf'], max_features=cand['max_features'],
        class_weight=cand['class_weight'], n_jobs=-1, random_state=seed)


def load():
    grid = pd.read_csv(GRID_CSV)
    cues = pd.read_csv(CUES_CSV)
    feat_cols = [c for c in cues.columns if c not in EXCLUDE]
    merged = grid.merge(cues[['sample_id'] + feat_cols], on='sample_id', how='left')
    assert not merged[feat_cols].isna().any().any(), 'cue join produced NaNs'
    X = merged[feat_cols].copy()
    X['est_snr_db'] = merged['snr_db'].to_numpy()
    X['channel_is_rayleigh'] = (merged['channel'] == 'rayleigh').astype(int).to_numpy()
    names = feat_cols + ['est_snr_db', 'channel_is_rayleigh']
    return (merged, X[names].to_numpy(), names, merged[['eff_E', 'eff_L', 'eff_F']].to_numpy(),
            merged['bler_F'].to_numpy(), merged['scene'].to_numpy())


def loso(cands, X, eff, bler_F, scene, seed):
    """Return per-candidate scene-mean F1/payload + append every (fold x candidate) row to FOLDS."""
    scenes = sorted(pd.unique(scene))
    masks = {s: (scene == s) for s in scenes}
    label_cache = {}
    fold_rows, summary = [], {}
    for c in cands:
        key = c['lam']
        if key not in label_cache:
            label_cache[key] = lam_labels(eff, bler_F, key)
        y = label_cache[key]
        per_f1, per_pay = [], []
        for s in scenes:
            te = masks[s]; tr = ~te
            rf = rf_of(c, seed)
            rf.fit(X[tr], y[tr])
            pred = rf.predict(X[te])
            f1 = float(eff[te][np.arange(te.sum()), pred].mean())
            pay = float(PAYVEC[pred].mean())
            per_f1.append(f1); per_pay.append(pay)
            fold_rows.append(dict(fold_scene=s, candidate_index=c['index'],
                                  n_estimators=c['n_estimators'], max_depth=c['max_depth'],
                                  min_samples_leaf=c['min_samples_leaf'], max_features=c['max_features'],
                                  class_weight=c['class_weight'], **{'lambda': c['lam']},
                                  realised_f1=round(f1, 6), realised_payload=round(pay, 6)))
        summary[c['index']] = dict(scene_mean_f1=float(np.mean(per_f1)),
                                   scene_mean_payload=float(np.mean(per_pay)))
    pd.DataFrame(fold_rows).to_csv(FOLDS_CSV, index=False)
    return summary, scenes


def depth_rank(md):
    return float('inf') if md is None else md                  # null = deepest -> ranked last


def pick_candidate(cands, summary, b_max):
    scored = [(c, summary[c['index']]) for c in cands]
    feasible = [(c, s) for c, s in scored if s['scene_mean_payload'] <= b_max + 1e-9]
    pool, feasible_flag = (feasible, True) if feasible else (scored, False)
    # tie-break: max F1 -> min payload -> shallower model -> smallest index
    best = min(pool, key=lambda cs: (-cs[1]['scene_mean_f1'], cs[1]['scene_mean_payload'],
                                     depth_rank(cs[0]['max_depth']), cs[0]['index']))
    return best[0], best[1], feasible_flag


def pick_tau(merged, eff, spec, b_max):
    awgn = (merged['channel'] == 'awgn').to_numpy(); snr = merged['snr_db'].to_numpy()
    tg = spec['tau_grid']
    taus = np.round(np.arange(tg['start'], tg['stop'] + 1e-9, tg['step']), 3)
    best = None
    for tau in taus:
        pred = np.where(awgn & (snr > tau), 2, 1)              # F else L; rayleigh -> L
        f1 = float(eff[np.arange(len(eff)), pred].mean()); pay = float(PAYVEC[pred].mean())
        if pay <= b_max + 1e-9 and (best is None or f1 > best[1]):
            best = (float(tau), f1, pay)
    if best is None:
        pred = np.ones(len(eff), dtype=int)
        best = (float('inf'), float(eff[np.arange(len(eff)), pred].mean()), float(PAYVEC[pred].mean()))
    return dict(tau_star=best[0], tau_f1=round(best[1], 4), tau_payload=round(best[2], 4))


def freeze(cand, X, eff, bler_F, path, seed):
    y = lam_labels(eff, bler_F, cand['lam'])
    rf = rf_of(cand, seed); rf.fit(X, y)
    with open(path, 'wb') as f:
        pickle.dump(rf, f)
    pred = rf.predict(X)
    f1 = float(eff[np.arange(len(eff)), pred].mean()); pay = float(PAYVEC[pred].mean())
    p, r, fs, sup = precision_recall_fscore_support(y, pred, labels=[0, 1, 2], zero_division=0)
    perclass = {ACTIONS[i]: dict(precision=round(float(p[i]), 4), recall=round(float(r[i]), 4),
                                 f1=round(float(fs[i]), 4), support=int(sup[i])) for i in range(3)}
    return dict(insample_f1=round(f1, 4), insample_payload=round(pay, 4), sha256=_sha256(path),
                perclass=perclass, confusion_ELF=confusion_matrix(y, pred, labels=[0, 1, 2]).tolist())


def main():
    os.makedirs(OUT_MODEL, exist_ok=True); os.makedirs(OUT_PROV, exist_ok=True)
    spec, cand_md5 = parse_candidates()
    seed = spec['seed']
    cands = build_candidate_list(spec)
    merged, X, names, eff, bler_F, scene = load()
    print(f'validate grid: {len(merged)} cells, {len(pd.unique(scene))} scenes, {len(names)} features; '
          f'{len(cands)} candidates x {spec["loso"]["folds"]} folds')

    summary, scenes = loso(cands, X, eff, bler_F, scene, seed)
    assert len(scenes) == spec['loso']['folds'], 'fold count != scenes'

    freeze_ts = datetime.now(timezone.utc).isoformat()
    budgets = {}
    for b in spec['budgets']:
        cand, sc, feas = pick_candidate(cands, summary, b)
        tau = pick_tau(merged, eff, spec, b)
        tag = f'B{int(round(b*100)):03d}'
        model_path = os.path.join(OUT_MODEL, f'selector_{tag}.pkl')
        fr = freeze(cand, X, eff, bler_F, model_path, seed)
        budgets[f'{b:.2f}'] = dict(
            selector=f'selector_{tag}', candidate_index=cand['index'],
            hyperparameters=dict(n_estimators=cand['n_estimators'], max_depth=cand['max_depth'],
                                 min_samples_leaf=cand['min_samples_leaf'], max_features=cand['max_features']),
            class_weight=cand['class_weight'], lambda_star=cand['lam'], lambda_feasible=feas,
            loso_scene_mean_f1=round(sc['scene_mean_f1'], 4),
            loso_scene_mean_payload=round(sc['scene_mean_payload'], 4),
            tau_star=tau['tau_star'], tau_f1=tau['tau_f1'], tau_payload=tau['tau_payload'],
            model=os.path.relpath(model_path, P1), model_sha256=fr['sha256'],
            insample_f1=fr['insample_f1'], insample_payload=fr['insample_payload'],
            perclass=fr['perclass'], confusion_ELF=fr['confusion_ELF'])
        print(f'  B_max={b}: cand#{cand["index"]} cw={cand["class_weight"]} lam*={cand["lam"]} '
              f'LOSO F1={sc["scene_mean_f1"]:.4f}/pay={sc["scene_mean_payload"]:.4f} '
              f'tau*={tau["tau_star"]} | frozen in-sample F1={fr["insample_f1"]}')

    manifest = dict(
        schema=MANIFEST_SCHEMA, protocol='CA-TOSG P2 (PROTOCOL.md)',
        freeze_timestamp=freeze_ts, seed=seed,
        candidate_block_md5=cand_md5, n_candidates=len(cands),
        feature_names=names, n_features=len(names),
        loso=dict(folds=len(scenes), scenes=scenes, each_scene_heldout_once=True),
        aggregation=spec['aggregation'], tie_break=spec['tie_break'],
        inputs=dict(
            train_grid=dict(file='data/p2/p2_grid_validate.csv', md5=_md5(GRID_CSV)),
            cue_source=dict(file='dataset_validate.csv', md5=_md5(CUES_CSV),
                            note='versionless (md5 == dataset_validate_v3.csv)'),
            bler_table=dict(file='results/bler_sionna/bler_sionna.csv', md5=_md5(BLER_CSV))),
        budgets=budgets)
    with open(MANIFEST, 'w') as f:
        json.dump(manifest, f, indent=2)

    with open(os.path.join(OUT_PROV, 'PROVENANCE_train.txt'), 'w') as f:
        f.write('CA-TOSG P2 submit-A -- LOSO selection + freeze (train_p2_loso.py)\n')
        f.write('=' * 72 + '\n')
        f.write(f'freeze_timestamp: {freeze_ts}; seed={seed}; candidate_block_md5={cand_md5}\n')
        f.write(f'{len(cands)} candidates (from PROTOCOL.md CATOSG-CANDIDATES) x {len(scenes)}-fold LOSO; '
                'primary = scene-mean realised F1; tie-break F1>payload>shallower>index.\n')
        f.write('one model per budget:\n')
        for b in spec['budgets']:
            bd = budgets[f'{b:.2f}']
            f.write(f'  B_max={b}: {bd["selector"]} cand#{bd["candidate_index"]} '
                    f'cw={bd["class_weight"]} lambda*={bd["lambda_star"]} tau*={bd["tau_star"]} '
                    f'sha256={bd["model_sha256"][:16]}...\n')
        f.write('models git-excluded (data/p2/); manifest+folds tracked (results/p2_dataprep/).\n')
        f.write('versionless: dataset_validate.csv md5=%s (== dataset_validate_v3.csv).\n' % _md5(CUES_CSV))
    print(f'\nFROZEN_MANIFEST.json + validate_loso_folds.csv + PROVENANCE_train.txt -> results/p2_dataprep/')


if __name__ == '__main__':
    main()
