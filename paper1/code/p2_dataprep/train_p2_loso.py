#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 submit-A (R6): scene-level 9-fold LOSO selection + freeze (ONE MODEL PER BUDGET).

Candidate set PARSED from PROTOCOL.md's ```json CATOSG-CANDIDATES``` block (single source of truth).
A candidate = (RF hyper-parameters, class_weight, lambda). Procedure (PROTOCOL sec 6, R1+R6):

  1. Load the validate grid + join the 21 ego-side cues (versionless dataset_validate.csv; the merge
     is validated many_to_one on a unique-sample_id cue source).
  2. 9-fold scene-level LOSO (each scene held out EXACTLY ONCE): per candidate, fit the RF on the 8
     non-held-out scenes' lambda-oracle labels and record OOF realised F1/payload + the held-out
     scene's n_frames -> validate_loso_folds.csv. The 1008 (=112x9) fits are REUSED from the CSV when
     it already matches the candidate list (only selection/feasibility are recomputed).
  3. R6 SEMANTIC SPLIT: performance = scene-mean realised F1; feasibility = frame-weighted OOF payload
     B_OOF = sum_k N_k*Bbar_k / sum_k N_k. Per B_max: keep B_OOF <= B_max, then max scene-mean F1,
     tie-break B_OOF -> shallower max_depth (null=deepest) -> candidate index.
  4. tau*(B_max): budget-matched SNR-threshold baseline on the full validate grid.
  5. Freeze one model per budget on all 1980 frames; FINAL-CHECK IRON RULE: frozen full-validate mean
     payload <= B_max (strict, no tolerance) for ALL budgets, else NO manifest, NO test/Culver grids,
     fuse. Manifest records loso_scene_mean_f1 / loso_frame_weighted_f1 / loso_frame_weighted_payload /
     frozen_validate_payload / budget_satisfied + env versions + three sha256 + input md5s.

CPU only, deterministic (seed from the JSON block). Run:
  /path/to/env/python paper1/code/p2_dataprep/train_p2_loso.py
"""
import hashlib
import itertools
import json
import os
import pickle
import platform
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
CUES_CSV = os.path.join(DATA, 'dataset_validate.csv')
GRID_CSV = os.path.join(P1, 'data/p2/p2_grid_validate.csv')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
PROTOCOL = os.path.join(P1, 'PROTOCOL.md')
OUT_MODEL = os.path.join(P1, 'data/p2')
OUT_PROV = os.path.join(P1, 'results/p2_dataprep')
MANIFEST = os.path.join(OUT_PROV, 'FROZEN_MANIFEST.json')
FOLDS_CSV = os.path.join(OUT_PROV, 'validate_loso_folds.csv')
MANIFEST_SCHEMA = 'catosg-frozen-manifest/1'

ACTIONS = ['E', 'L', 'F']
PAYLOAD = {'E': 0.0, 'L': 0.024, 'F': 0.99}
PAYVEC = np.array([PAYLOAD[a] for a in ACTIONS])
BLER_INFEASIBLE = 0.999
FOLD_COLS = ['fold_scene', 'candidate_index', 'n_estimators', 'max_depth', 'min_samples_leaf',
             'max_features', 'class_weight', 'lambda', 'n_frames', 'realised_f1', 'realised_payload']
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
    txt = open(PROTOCOL, encoding='utf-8').read()
    m = re.search(r'```json CATOSG-CANDIDATES\s*(\{.*?\})\s*```', txt, re.S)
    if not m:
        raise SystemExit('CATOSG-CANDIDATES block not found in PROTOCOL.md.')
    return json.loads(m.group(1)), hashlib.md5(m.group(1).encode()).hexdigest()


def build_candidate_list(spec):
    hp = spec['hyperparameters']
    combos = itertools.product(hp['n_estimators'], hp['max_depth'], hp['min_samples_leaf'],
                               hp['max_features'], spec['class_weight'], spec['lambda_grid'])
    return [dict(index=i, n_estimators=ne, max_depth=md, min_samples_leaf=ml,
                 max_features=mf, class_weight=cw, lam=float(lam))
            for i, (ne, md, ml, mf, cw, lam) in enumerate(combos)]


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
    if cues['sample_id'].duplicated().any():                    # merge guard: cue source must be per-frame
        raise SystemExit('dataset_validate.csv has duplicate sample_id -- cue source not one-per-frame.')
    feat_cols = [c for c in cues.columns if c not in EXCLUDE]
    merged = grid.merge(cues[['sample_id'] + feat_cols], on='sample_id', how='left',
                        validate='many_to_one')
    assert not merged[feat_cols].isna().any().any(), 'cue join produced NaNs'
    X = merged[feat_cols].copy()
    X['est_snr_db'] = merged['snr_db'].to_numpy()
    X['channel_is_rayleigh'] = (merged['channel'] == 'rayleigh').astype(int).to_numpy()
    names = feat_cols + ['est_snr_db', 'channel_is_rayleigh']
    return (merged, X[names].to_numpy(), names, merged[['eff_E', 'eff_L', 'eff_F']].to_numpy(),
            merged['bler_F'].to_numpy(), merged['scene'].to_numpy())


def _norm_mf(v):
    """max_features canonicalisation: '0.5' (CSV string) and 0.5 (spec float) must compare equal;
    'sqrt' stays a string."""
    try:
        return float(v)
    except (ValueError, TypeError):
        return str(v)


def _cand_sig(row):
    md = None if (pd.isna(row['max_depth'])) else int(row['max_depth'])
    cw = None if (pd.isna(row['class_weight']) or row['class_weight'] == '') else row['class_weight']
    return (int(row['n_estimators']), md, int(row['min_samples_leaf']),
            _norm_mf(row['max_features']), cw, round(float(row['lambda']), 6))


def _cand_sig_from(c):
    return (c['n_estimators'], c['max_depth'], c['min_samples_leaf'],
            _norm_mf(c['max_features']), c['class_weight'], round(c['lam'], 6))


def loso_or_reuse(cands, X, eff, bler_F, scene, seed, nk):
    """Run the 9-fold LOSO, or REUSE validate_loso_folds.csv when it already matches the candidates
    (only adds n_frames if missing). Writes the (fold x candidate) CSV with n_frames."""
    scenes = sorted(pd.unique(scene))
    reuse = False
    if os.path.exists(FOLDS_CSV):
        prev = pd.read_csv(FOLDS_CSV)
        want = {c['index']: _cand_sig_from(c) for c in cands}
        try:
            have = {int(r.candidate_index): _cand_sig(r) for _, r in prev.iterrows()}
            reuse = (len(prev) == len(cands) * len(scenes)
                     and set(have) == set(want) and all(have[i] == want[i] for i in want)
                     and set(prev['fold_scene'].unique()) == set(scenes))
        except Exception:
            reuse = False
    if reuse:
        print(f'  REUSE validate_loso_folds.csv ({len(prev)} rows) -- 1008 fits not recomputed (R6).')
        prev['n_frames'] = prev['fold_scene'].map(nk)           # (re)attach n_frames from the grid
        df = prev[FOLD_COLS].copy()
    else:
        print('  running LOSO from scratch (no reusable folds CSV) ...')
        masks = {s: (scene == s) for s in scenes}
        label_cache, rows = {}, []
        for c in cands:
            if c['lam'] not in label_cache:
                label_cache[c['lam']] = lam_labels(eff, bler_F, c['lam'])
            y = label_cache[c['lam']]
            for s in scenes:
                te = masks[s]; rf = rf_of(c, seed); rf.fit(X[~te], y[~te]); pred = rf.predict(X[te])
                rows.append(dict(fold_scene=s, candidate_index=c['index'],
                                 n_estimators=c['n_estimators'], max_depth=c['max_depth'],
                                 min_samples_leaf=c['min_samples_leaf'], max_features=c['max_features'],
                                 class_weight=c['class_weight'], **{'lambda': c['lam']},
                                 n_frames=int(nk[s]),
                                 realised_f1=round(float(eff[te][np.arange(te.sum()), pred].mean()), 6),
                                 realised_payload=round(float(PAYVEC[pred].mean()), 6)))
        df = pd.DataFrame(rows)[FOLD_COLS]
    df.to_csv(FOLDS_CSV, index=False)
    return df, scenes


def aggregate(fold_df):
    """Per candidate: scene-mean F1 (equal weight) + frame-weighted OOF F1 and payload (weight N_k)."""
    agg = {}
    for ci, g in fold_df.groupby('candidate_index'):
        w = g['n_frames'].to_numpy(dtype=float); W = w.sum()
        agg[int(ci)] = dict(
            scene_mean_f1=float(g['realised_f1'].mean()),
            frame_weighted_f1=float((w * g['realised_f1'].to_numpy()).sum() / W),
            frame_weighted_payload=float((w * g['realised_payload'].to_numpy()).sum() / W))
    return agg


def depth_rank(md):
    return float('inf') if md is None else md


def walk_order(cands, agg, b_max):
    """R7 frozen walk order: OOF-feasible candidates, by frame-weighted OOF F1 desc, tie-break
    lower B_OOF -> shallower model -> candidate index."""
    feasible = [c for c in cands if agg[c['index']]['frame_weighted_payload'] <= b_max]  # strict <=
    feasible.sort(key=lambda c: (-agg[c['index']]['frame_weighted_f1'],
                                 agg[c['index']]['frame_weighted_payload'],
                                 depth_rank(c['max_depth']), c['index']))
    return feasible


def pick_tau(merged, eff, spec, b_max):
    awgn = (merged['channel'] == 'awgn').to_numpy(); snr = merged['snr_db'].to_numpy()
    tg = spec['tau_grid']; taus = np.round(np.arange(tg['start'], tg['stop'] + 1e-9, tg['step']), 3)
    best = None
    for tau in taus:
        pred = np.where(awgn & (snr > tau), 2, 1)
        f1 = float(eff[np.arange(len(eff)), pred].mean()); pay = float(PAYVEC[pred].mean())
        if pay <= b_max and (best is None or f1 > best[1]):
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
    return dict(frozen_validate_f1=round(f1, 4), frozen_validate_payload=round(pay, 6),
                sha256=_sha256(path), perclass=perclass,
                confusion_ELF=confusion_matrix(y, pred, labels=[0, 1, 2]).tolist())


def main():
    os.makedirs(OUT_MODEL, exist_ok=True); os.makedirs(OUT_PROV, exist_ok=True)
    spec, cand_md5 = parse_candidates()
    seed = spec['seed']
    cands = build_candidate_list(spec)
    merged, X, names, eff, bler_F, scene = load()
    nk = merged.groupby('scene')['sample_id'].nunique().to_dict()   # frames per scene (from the grid)
    print(f'validate grid: {len(merged)} cells, {len(nk)} scenes, {len(names)} features; '
          f'{len(cands)} candidates x {spec["loso"]["folds"]} folds')

    fold_df, scenes = loso_or_reuse(cands, X, eff, bler_F, scene, seed, nk)
    assert len(scenes) == spec['loso']['folds'], 'fold count != scenes'
    agg = aggregate(fold_df)

    # --- R7 FROZEN WALK, R9-2c ATOMIC: stage everything to .tmp; promote only after the audit confirms
    #     the winners. A failed re-run (walk exhausted / audit mismatch) NEVER overwrites the existing
    #     valid products -- the .tmp files are discarded and the current manifest/models are kept. ---
    freeze_ts = datetime.now(timezone.utc).isoformat()
    tmps = []                                                         # every staged .tmp path, for cleanup

    def _cleanup():
        for t in tmps:
            if os.path.exists(t):
                os.remove(t)

    orders = {}
    for b in spec['budgets']:
        order = walk_order(cands, agg, b)
        orders[b] = order
        rows = [dict(rank=i, candidate_index=c['index'], n_estimators=c['n_estimators'],
                     max_depth=c['max_depth'], min_samples_leaf=c['min_samples_leaf'],
                     max_features=c['max_features'], class_weight=c['class_weight'], **{'lambda': c['lam']},
                     frame_weighted_f1=round(agg[c['index']]['frame_weighted_f1'], 6),
                     scene_mean_f1=round(agg[c['index']]['scene_mean_f1'], 6),
                     frame_weighted_payload=round(agg[c['index']]['frame_weighted_payload'], 6))
                for i, c in enumerate(order)]
        wtmp = os.path.join(OUT_PROV, f'candidate_walk_B{int(round(b*100)):03d}.csv.tmp')
        pd.DataFrame(rows).to_csv(wtmp, index=False); tmps.append(wtmp)
    print(f'walk orders staged ({", ".join(f"B{int(b*100):03d}:{len(orders[b])}feasible" for b in spec["budgets"])}).')

    budgets, violations, promote = {}, [], []                        # promote = [(tmp, final), ...]
    for b in spec['budgets']:
        tau = pick_tau(merged, eff, spec, b)
        tag = f'B{int(round(b*100)):03d}'
        model_final = os.path.join(OUT_MODEL, f'selector_{tag}.pkl')
        model_tmp = model_final + '.tmp'
        tmps.append(model_tmp)                                        # register early so a fuse path cleans it
        walk_final = os.path.join(OUT_PROV, f'candidate_walk_{tag}.csv')
        walk_tmp = walk_final + '.tmp'
        selected, attempts = None, {}                                 # rank -> (frozen_f1, frozen_pay, passed)
        for depth, cand in enumerate(orders[b]):
            fr = freeze(cand, X, eff, bler_F, model_tmp, seed)        # stage model to .tmp (overwrite until pass)
            passed = fr['frozen_validate_payload'] <= b               # strict <=, no tolerance
            attempts[depth] = (fr['frozen_validate_f1'], fr['frozen_validate_payload'], passed)
            print(f'  B_max={b} walk#{depth} cand#{cand["index"]} cw={cand["class_weight"]} '
                  f'lam*={cand["lam"]} OOF_F1={agg[cand["index"]]["frame_weighted_f1"]:.4f} '
                  f'-> frozen pay={fr["frozen_validate_payload"]:.4f} passed={passed}')
            if passed:
                selected = (cand, depth, fr, agg[cand['index']]); break
        # close the walk evidence chain: append the actual retrain outcome to the pre-registered order.
        # budget_passed is written as a 0/1 INTEGER (R9-2a) but the gate re-derives it, not trusts it.
        wdf = pd.read_csv(walk_tmp)
        wdf['attempted'] = [1 if i in attempts else 0 for i in range(len(wdf))]
        wdf['frozen_validate_f1'] = [round(attempts[i][0], 6) if i in attempts else '' for i in range(len(wdf))]
        wdf['frozen_validate_payload'] = [round(attempts[i][1], 6) if i in attempts else '' for i in range(len(wdf))]
        wdf['budget_passed'] = [int(attempts[i][2]) if i in attempts else '' for i in range(len(wdf))]
        wdf.to_csv(walk_tmp, index=False)
        if selected is None:
            violations.append((b, len(orders[b])))
            continue
        promote += [(model_tmp, model_final), (walk_tmp, walk_final)]
        cand, depth, fr, a = selected
        budgets[f'{b:.2f}'] = dict(
            selector=f'selector_{tag}', candidate_index=cand['index'], walk_depth=depth,
            n_feasible=len(orders[b]),
            hyperparameters=dict(n_estimators=cand['n_estimators'], max_depth=cand['max_depth'],
                                 min_samples_leaf=cand['min_samples_leaf'], max_features=cand['max_features']),
            class_weight=cand['class_weight'], lambda_star=cand['lam'],
            loso_frame_weighted_f1=round(a['frame_weighted_f1'], 4),     # PRIMARY (R7)
            loso_scene_mean_f1=round(a['scene_mean_f1'], 4),            # robustness supplement
            loso_frame_weighted_payload=round(a['frame_weighted_payload'], 6),
            tau_star=tau['tau_star'], tau_f1=tau['tau_f1'], tau_payload=tau['tau_payload'],
            model=os.path.relpath(model_final, P1), model_sha256=fr['sha256'],
            frozen_validate_f1=fr['frozen_validate_f1'], frozen_validate_payload=fr['frozen_validate_payload'],
            budget_satisfied=True, perclass=fr['perclass'], confusion_ELF=fr['confusion_ELF'])
        print(f'  B_max={b}: SELECTED cand#{cand["index"]} at walk_depth={depth} '
              f'(OOF F1={a["frame_weighted_f1"]:.4f}, frozen pay={fr["frozen_validate_payload"]:.4f} <= {b})')

    if violations:                                                   # walk exhausted for some budget
        _cleanup()                                                   # R9-2c: discard .tmp; KEEP existing products
        with open(os.path.join(OUT_PROV, 'PROVENANCE_train.txt'), 'w') as f:
            f.write('CA-TOSG P2 submit-A -- FROZEN WALK EXHAUSTED (no new manifest; existing kept)\n')
            f.write('=' * 72 + '\n')
            f.write(f'freeze attempt {freeze_ts}; seed={seed}; candidate_block_md5={cand_md5}\n')
            f.write('Frozen walk EXHAUSTED for at least one budget: no OOF-feasible candidate passed the '
                    'frozen_validate_payload <= B_max check. Per R9-2c the staged .tmp products were '
                    'DISCARDED and the existing manifest/models are KEPT untouched. Fix = a NEW '
                    'pre-registered Change-log entry expanding the lambda grid, then a full redo.\n\n')
            for b, n in violations:
                f.write(f'  B_max={b}: walk EXHAUSTED ({n} OOF-feasible candidates, none frozen <= {b}).\n')
        raise SystemExit('FROZEN WALK EXHAUSTED for '
                         + ', '.join(f'B={b} ({n} feasible, none passed)' for b, n in violations)
                         + '. Staged .tmp discarded, existing products kept. FUSED.')

    # AUDIT (R8/R9): if a prior manifest exists, the re-executed (same-seed, deterministic) walk winners
    # MUST match it exactly; a mismatch means non-determinism -- discard the .tmp staging and KEEP the
    # existing products (R9-2c: never overwrite on mismatch).
    if os.path.exists(MANIFEST):
        prev = json.load(open(MANIFEST))
        for b in spec['budgets']:
            key = f'{b:.2f}'; new = budgets[key]; old = prev.get('budgets', {}).get(key, {})
            for field in ('candidate_index', 'model_sha256', 'lambda_star', 'tau_star'):
                if new.get(field) != old.get(field):
                    _cleanup()
                    raise SystemExit(f'AUDIT MISMATCH B={b} {field}: re-run {new.get(field)!r} != '
                                     f'manifest {old.get(field)!r}. Staged .tmp discarded, existing '
                                     'products KEPT (R9-2c).')
        print('AUDIT: re-executed walk winners match FROZEN_MANIFEST.json (candidate/sha/lambda*/tau*).')

    env = dict(python=platform.python_version(), sklearn=sklearn.__version__,
               numpy=np.__version__, pandas=pd.__version__)
    walk_files = {f'B{int(round(b*100)):03d}': os.path.join(OUT_PROV, f'candidate_walk_B{int(round(b*100)):03d}.csv')
                  for b in spec['budgets']}
    manifest = dict(
        schema=MANIFEST_SCHEMA, protocol='CA-TOSG P2 (PROTOCOL.md), R9',
        freeze_timestamp=freeze_ts, seed=seed, environment=env,
        candidate_block_md5=cand_md5, n_candidates=len(cands),
        feature_names=names, n_features=len(names),
        loso=dict(folds=len(scenes), scenes=scenes, each_scene_heldout_once=True,
                  n_fold_rows=len(fold_df)),
        aggregation=spec['aggregation'], tie_break=spec['tie_break'], selection='frozen_walk',
        inputs=dict(
            train_grid=dict(file='data/p2/p2_grid_validate.csv', md5=_md5(GRID_CSV)),
            cue_source=dict(file=os.path.relpath(CUES_CSV, P1), md5=_md5(CUES_CSV),
                            note='versionless (md5 == dataset_validate_v3.csv)'),
            bler_table=dict(file='results/bler_sionna/bler_sionna.csv', md5=_md5(BLER_CSV)),
            folds_csv=dict(file=os.path.relpath(FOLDS_CSV, P1), sha256=_sha256(FOLDS_CSV)),
            **{f'walk_{tag}': dict(file=os.path.relpath(p, P1), sha256=_sha256(p + '.tmp'))
               for tag, p in walk_files.items()}),                    # sha of the STAGED (.tmp) walk file
        budgets=budgets)
    manifest_tmp = MANIFEST + '.tmp'
    with open(manifest_tmp, 'w') as f:
        json.dump(manifest, f, indent=2)
    tmps.append(manifest_tmp); promote.append((manifest_tmp, MANIFEST))

    # R9-2c ATOMIC PROMOTE: only now that winners are confirmed do we replace the live products.
    for src, dst in promote:
        os.replace(src, dst)

    with open(os.path.join(OUT_PROV, 'PROVENANCE_train.txt'), 'w') as f:
        f.write('CA-TOSG P2 submit-A (R9) -- frozen-walk selection + freeze, atomic (train_p2_loso.py)\n')
        f.write('=' * 72 + '\n')
        f.write(f'freeze_timestamp: {freeze_ts}; seed={seed}; candidate_block_md5={cand_md5}\n')
        f.write(f'env: {env}\n')
        f.write('R7: PRIMARY = frame-weighted OOF F1; feasibility = frame-weighted OOF payload; '
                'frozen walk = first OOF-feasible candidate (by OOF F1 desc) whose frozen payload <= B_max.\n')
        for b in spec['budgets']:
            bd = budgets[f'{b:.2f}']
            f.write(f'  B_max={b}: {bd["selector"]} cand#{bd["candidate_index"]} walk_depth={bd["walk_depth"]}'
                    f'/{bd["n_feasible"]} cw={bd["class_weight"]} lambda*={bd["lambda_star"]} '
                    f'OOF_F1={bd["loso_frame_weighted_f1"]} (scene-mean {bd["loso_scene_mean_f1"]}) '
                    f'frozen_pay={bd["frozen_validate_payload"]} tau*={bd["tau_star"]} '
                    f'sha256={bd["model_sha256"][:16]}...\n')
        f.write('models git-excluded (data/p2/); manifest+folds+walk-tables tracked (results/p2_dataprep/).\n')
    print('\nAll budgets satisfied -> FROZEN_MANIFEST.json + candidate_walk_B0XX.csv + '
          'validate_loso_folds.csv + PROVENANCE_train.txt')


if __name__ == '__main__':
    main()
