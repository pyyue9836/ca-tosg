#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FA-1 feature ablation: channel-only / task-only / combined (Change-log FA-1, Appendix E).

Pre-registered before anything here was written or run. What each half of the selector's input
buys, measured by running the MAINLINE pipeline with only the feature columns changed:

  channel_only  2 features (est_snr_db, channel_is_rayleigh)   trained here
  task_only     the 21 ego-side cues                           trained here
  combined      all 23 -- the DEPLOYED frozen models, referenced, NEVER retrained

Everything else is the mainline, reusing its functions rather than re-implementing them: the same
validate grid and cue join (`feature_encoder.load`), the same 112-candidate table parsed from the
protocol, the same scene-level 9-fold LOSO, the same frame-weighted OOF feasibility, the same
frozen walk with the hard check `Bbar_frozen <= B_max`, one model per B_max. The variant spec
itself is parsed from Appendix E, and the base feature list from FROZEN_MANIFEST.json, so the
ablation cannot drift from the deployed feature vector.

Every product is labelled "labeled variant, not deployed" and the variant manifest is written to
results/manifests/FEATURE_ABLATION_MANIFEST.json -- deliberately NOT into FROZEN_MANIFEST.json.

Outputs:
  results/sensitivity/feature_ablation.csv                      the comparison table
  results/sensitivity/feature_ablation_runs/                     per-variant LOSO + walk evidence
  results/manifests/FEATURE_ABLATION_MANIFEST.json               variant model sha256s
  results/provenance/PROVENANCE_fa.txt

Run:  python projects/ca_tosg/evaluation/feature_ablation.py
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# --- ca-tosg layout bootstrap ---
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/models', 'projects/ca_tosg/utils',
           'projects/ca_tosg/datasets'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
sys.path.insert(0, _CT_ROOT)
# --- end bootstrap ---
import deployment as D                                                   # noqa: E402
from projects.ca_tosg.models import selector as S                        # noqa: E402
from projects.ca_tosg.models.feature_encoder import load                 # noqa: E402
from projects.ca_tosg.models.oracle import PAYVEC                        # noqa: E402

ROOT = D.P1
PROTOCOL = os.path.join(ROOT, 'docs/experiment_protocol.md')
FROZEN = os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')
OUT_CSV = os.path.join(ROOT, 'results/sensitivity/feature_ablation.csv')
RUNS = os.path.join(ROOT, 'results/sensitivity/feature_ablation_runs')
MODELDIR = os.path.join(ROOT, 'data/p2')                                 # git-excluded, like the deployed
MANIFEST = os.path.join(ROOT, 'results/manifests/FEATURE_ABLATION_MANIFEST.json')
PROV = os.path.join(ROOT, 'results/provenance/PROVENANCE_fa.txt')
LABEL = 'labeled variant, not deployed'
ACTIONS = ['E', 'L', 'F']


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def parse_spec():
    txt = open(PROTOCOL, encoding='utf-8').read()
    m = re.search(r'```json CATOSG-FEATURE-ABLATION\s*(\{.*?\})\s*```', txt, re.S)
    if not m:
        raise SystemExit('FA FUSE: CATOSG-FEATURE-ABLATION block not found in the protocol')
    return json.loads(m.group(1)), hashlib.md5(m.group(1).encode()).hexdigest()


def variant_columns(spec, names):
    """variant -> list of column indices into the 23-feature vector, per the pre-registered rule."""
    ch = spec['channel_features']
    missing = [c for c in ch if c not in names]
    if missing:
        raise SystemExit('FA FUSE: channel features %s absent from the deployed feature vector' % missing)
    out = {}
    for v, d in spec['variants'].items():
        keep = d['keep']
        if keep == 'channel_features':
            cols = [names.index(c) for c in ch]
        elif keep == 'complement_of_channel_features':
            cols = [i for i, c in enumerate(names) if c not in ch]
        elif keep == 'all':
            cols = list(range(len(names)))
        else:
            raise SystemExit('FA FUSE: unknown keep rule %r' % keep)
        out[v] = (cols, bool(d.get('train', False)))
    return out


def feature_matrix(feat, cues_df, snr_flat, ray_flat):
    """(m, |feat|) matrix in the variant's column order. Unlike deployment._feature_matrix this
    tolerates a feature list WITHOUT the channel columns (task_only) or without any cue (channel_only)."""
    cue_cols = [c for c in feat if c not in ('est_snr_db', 'channel_is_rayleigh')]
    reps = len(snr_flat) // len(cues_df)
    big = np.empty((len(snr_flat), len(feat)))
    if cue_cols:
        big[:, [feat.index(c) for c in cue_cols]] = np.tile(cues_df[cue_cols].to_numpy(), (reps, 1))
    if 'est_snr_db' in feat:
        big[:, feat.index('est_snr_db')] = snr_flat
    if 'channel_is_rayleigh' in feat:
        big[:, feat.index('channel_is_rayleigh')] = ray_flat.astype(int)
    return big


def actions_stacked(model, feat, cues_df, snr_2d, is_ray_2d):
    R, n = snr_2d.shape
    big = feature_matrix(feat, cues_df, snr_2d.reshape(-1), is_ray_2d.reshape(-1))
    return np.asarray(model.predict(big), dtype=int).reshape(R, n)


# ------------------------------------------------------------------ training (mainline pipeline)
def loso(cands, X, eff, bler_F, scene, seed, nk):
    """Scene-level 9-fold LOSO, 112 candidates -- the mainline procedure, on the variant's columns."""
    scenes = sorted(pd.unique(scene))
    masks = {s: (scene == s) for s in scenes}
    label_cache, rows = {}, []
    for j, c in enumerate(cands):
        if c['lam'] not in label_cache:
            label_cache[c['lam']] = S.lam_labels(eff, bler_F, c['lam'])
        y = label_cache[c['lam']]
        for s in scenes:
            te = masks[s]
            rf = S.rf_of(c, seed)
            rf.fit(X[~te], y[~te])
            pred = rf.predict(X[te])
            rows.append(dict(fold_scene=s, candidate_index=c['index'], n_frames=int(nk[s]),
                             **{'lambda': c['lam']},
                             realised_f1=round(float(eff[te][np.arange(te.sum()), pred].mean()), 6),
                             realised_payload=round(float(PAYVEC[pred].mean()), 6)))
        if (j + 1) % 20 == 0:
            print('    LOSO %d/%d candidates' % (j + 1, len(cands)), flush=True)
    return pd.DataFrame(rows)


def train_variant(name, cols, names, X, eff, bler_F, scene, cands, spec, seed, nk, budgets):
    feat = [names[i] for i in cols]
    Xv = X[:, cols]
    print('  [%s] %d features, LOSO over %d candidates x 9 folds ...' % (name, len(feat), len(cands)),
          flush=True)
    fold_df = loso(cands, Xv, eff, bler_F, scene, seed, nk)
    fold_df.to_csv(os.path.join(RUNS, 'fa_loso_folds_%s.csv' % name), index=False)
    agg = S.aggregate(fold_df)

    out = {}
    for b in budgets:
        tag = 'B%03d' % round(b * 100)
        order = S.walk_order(cands, agg, b)
        rows, chosen = [], None
        model_path = os.path.join(MODELDIR, 'fa_%s_%s.pkl' % (name, tag))
        for depth, cand in enumerate(order):
            fr = S.freeze(cand, Xv, eff, bler_F, model_path, seed)
            passed = fr['frozen_validate_payload'] <= b                  # strict, no tolerance
            rows.append(dict(rank=depth, candidate_index=cand['index'], **{'lambda': cand['lam']},
                             oof_f1=round(agg[cand['index']]['frame_weighted_f1'], 6),
                             oof_payload=round(agg[cand['index']]['frame_weighted_payload'], 6),
                             frozen_validate_f1=fr['frozen_validate_f1'],
                             frozen_validate_payload=fr['frozen_validate_payload'],
                             budget_passed=int(passed)))
            if passed:
                chosen = dict(variant=name, tag=tag, label=LABEL, features=feat, n_features=len(feat),
                              candidate_index=cand['index'], walk_depth=depth, n_feasible=len(order),
                              lambda_star=cand['lam'], class_weight=cand['class_weight'],
                              hyperparameters=dict(n_estimators=cand['n_estimators'],
                                                   max_depth=cand['max_depth'],
                                                   min_samples_leaf=cand['min_samples_leaf'],
                                                   max_features=cand['max_features']),
                              loso_frame_weighted_f1=round(agg[cand['index']]['frame_weighted_f1'], 4),
                              loso_frame_weighted_payload=round(
                                  agg[cand['index']]['frame_weighted_payload'], 6),
                              frozen_validate_f1=fr['frozen_validate_f1'],
                              frozen_validate_payload=fr['frozen_validate_payload'],
                              budget_satisfied=True, perclass=fr['perclass'],
                              model=os.path.relpath(model_path, ROOT), model_sha256=fr['sha256'])
                break
        pd.DataFrame(rows).to_csv(os.path.join(RUNS, 'fa_walk_%s_%s.csv' % (name, tag)), index=False)
        if chosen is None:
            raise SystemExit('FA FUSE: walk exhausted for %s B_max=%s -- reported, not patched' % (name, b))
        print('    %s %s: cand#%d depth %d lam*=%s frozen F1=%.5f pay=%.5f' %
              (name, tag, chosen['candidate_index'], chosen['walk_depth'], chosen['lambda_star'],
               chosen['frozen_validate_f1'], chosen['frozen_validate_payload']), flush=True)
        out[tag] = chosen
    return out, feat


# ------------------------------------------------------------------ evaluation
def paired_bootstrap(delta, n_boot, seed):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    means = delta[idx].mean(1)
    return float(delta.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    for d in (RUNS, os.path.dirname(OUT_CSV), MODELDIR, os.path.dirname(MANIFEST),
              os.path.dirname(PROV)):
        os.makedirs(d, exist_ok=True)
    spec, spec_md5 = parse_spec()
    frozen = json.load(open(FROZEN))
    names_deployed = frozen['feature_names']

    cand_spec, cand_md5 = S.parse_candidates()
    seed = cand_spec['seed']
    cands = S.build_candidate_list(cand_spec)
    budgets = cand_spec['budgets']

    merged, X, names, eff, bler_F, scene = load()
    if names != names_deployed:
        raise SystemExit('FA FUSE: cue join produced %d features, manifest says %d -- refusing to '
                         'ablate a feature vector that is not the deployed one'
                         % (len(names), len(names_deployed)))
    nk = merged.groupby('scene')['sample_id'].nunique().to_dict()
    cols = variant_columns(spec, names)
    print('validate grid %s, %d candidates, budgets %s' % (X.shape, len(cands), budgets), flush=True)

    trained, feats = {}, {}
    for v, (c, do_train) in cols.items():
        feats[v] = [names[i] for i in c]
        if do_train:
            trained[v], feats[v] = train_variant(v, c, names, X, eff, bler_F, scene, cands, spec,
                                                 seed, nk, budgets)

    manifest = dict(
        schema='catosg-feature-ablation-manifest/1', label=LABEL,
        protocol='CA-TOSG FA-1 (docs/experiment_protocol.md Appendix E)',
        note='VARIANT models. NOT the deployed product -- the deployed selectors are in '
             'results/manifests/FROZEN_MANIFEST.json and are untouched by this run.',
        freeze_timestamp=datetime.now(timezone.utc).isoformat(), seed=seed,
        fa_block_md5=spec_md5, candidate_block_md5=cand_md5,
        deployed_manifest_sha256=_sha256(FROZEN),
        variants={v: dict(features=feats[v], n_features=len(feats[v]),
                          trained=bool(cols[v][1]),
                          budgets=trained.get(v, {}) or 'referenced from FROZEN_MANIFEST.json')
                  for v in cols},
    )
    json.dump(manifest, open(MANIFEST, 'w'), indent=1)
    print('wrote %s' % os.path.relpath(MANIFEST, ROOT), flush=True)

    # ---- evaluation: the SAME 200 paired CSI draws as the mainline replay
    tbl = pd.read_csv(D.BLER_CSV)
    _, rfbud = D.load_manifest()
    rows = []
    for split in D.SPLITS:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
        rng = np.random.default_rng(D.CSI_SEED)
        snr_2d = rng.uniform(0, 20, size=(D.N_REPLAY, n))
        is_ray_2d = rng.random(size=(D.N_REPLAY, n)) < 0.5
        bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(D.N_REPLAY)])
        for b in budgets:
            tag = 'B%03d' % round(b * 100)
            key = '%.2f' % b
            acts = {}
            for v in cols:
                if cols[v][1]:
                    import pickle
                    mp = os.path.join(ROOT, trained[v][tag]['model'])
                    if _sha256(mp) != trained[v][tag]['model_sha256']:
                        raise SystemExit('FA FUSE: %s %s sha mismatch' % (v, tag))
                    acts[v] = actions_stacked(pickle.load(open(mp, 'rb')), feats[v], ds, snr_2d, is_ray_2d)
                else:
                    acts[v] = D.rf_actions_stacked(rfbud[key]['model'], rfbud[key]['feat'], ds,
                                                   snr_2d, is_ray_2d)
            acts['tau_reference'] = D.tau_actions(snr_2d, is_ray_2d, rfbud[key]['tau'])
            F = {k: np.empty(D.N_REPLAY) for k in acts}
            B = {k: np.empty(D.N_REPLAY) for k in acts}
            RHO = {k: np.zeros(3) for k in acts}
            for r in range(D.N_REPLAY):
                E = D.eff_matrix(ego, late, comp, bF_2d[r])
                for k, a in acts.items():
                    F[k][r] = E[np.arange(n), a[r]].mean()
                    B[k][r] = PAYVEC[a[r]].mean()
                    RHO[k] += np.bincount(a[r], minlength=3) / (n * D.N_REPLAY)
            for k in acts:
                row = dict(split=split, budget=b, variant=k, label=LABEL if k in cols and cols[k][1]
                           else ('deployed (reference)' if k == 'combined' else 'tau rule (reference)'),
                           n_features=len(feats[k]) if k in feats else '',
                           F1=round(float(F[k].mean()), 5), F1_std=round(float(F[k].std()), 5),
                           payload=round(float(B[k].mean()), 5),
                           rho_E=round(float(RHO[k][0]), 4), rho_L=round(float(RHO[k][1]), 4),
                           rho_F=round(float(RHO[k][2]), 4),
                           over_budget=bool(float(B[k].mean()) > b))
                if k != 'combined':                                   # paired CI vs the deployed model
                    for nm, d in (('dF_vs_combined', F[k] - F['combined']),
                                  ('dB_vs_combined', B[k] - B['combined'])):
                        m, lo, hi = paired_bootstrap(d, D.N_BOOT, D.BOOT_SEED)
                        row[nm + '_mean'] = round(m, 5)
                        row[nm + '_lcb95'] = round(lo, 5)
                        row[nm + '_ucb95'] = round(hi, 5)
                rows.append(row)
            print('[%s %s] ' % (split, tag) + '  '.join(
                '%s F1=%.4f B=%.4f rhoF=%.3f' % (k, F[k].mean(), B[k].mean(), RHO[k][2])
                for k in acts), flush=True)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)

    with open(PROV, 'w') as f:
        f.write('CA-TOSG FA-1 -- feature ablation (feature_ablation.py). DESCRIPTIVE + CI ONLY.\n' + '=' * 88 + '\n')
        f.write('Pre-registered in the Change-log (FA-1) and Appendix E BEFORE this code existed; '
                'variant spec md5=%s, candidate block md5=%s.\n' % (spec_md5, cand_md5))
        f.write('Variants: ' + '; '.join('%s (%d feat, %s)' % (v, len(feats[v]),
                'trained here' if cols[v][1] else 'DEPLOYED, referenced not retrained') for v in cols) + '\n')
        f.write('Pipeline for the trained variants is the mainline one, reusing its functions: same '
                'validate grid + cue join, same 112 candidates from the protocol block, scene-level '
                '9-fold LOSO, frame-weighted OOF feasibility, frozen walk with Bbar_frozen <= B_max '
                '(strict), one model per B_max. Only the feature columns differ.\n')
        f.write('Evaluation: the SAME 200 paired CSI draws as the mainline replay (seed=%d), 3 splits; '
                'RF variants, the deployed combined model and the tau rule all replay the SAME draws. '
                'Paired bootstrap CI vs the deployed combined model, %d resamples, seed=%d.\n'
                % (D.CSI_SEED, D.N_BOOT, D.BOOT_SEED))
        f.write('Every trained product is "%s"; variant sha256 live in %s, deliberately NOT in '
                'FROZEN_MANIFEST.json (sha256 %s, untouched by this run).\n'
                % (LABEL, os.path.relpath(MANIFEST, ROOT), _sha256(FROZEN)[:16]))
        f.write('NO decision is taken here: the confirmatory primary was spent once at R9. '
                'sec 8 anti-forcing: the pre-registered expectations are checks, not targets.\n')
    print('wrote %s + %s' % (os.path.relpath(OUT_CSV, ROOT), os.path.relpath(PROV, ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
