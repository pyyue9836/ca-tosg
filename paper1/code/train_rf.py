#self+ CA-TOSG P1 Step-4: retrain the deployed 3-way selector (L/C16/C256) on the canonical v3
# validate dataset, and SERIALIZE the training-frame list + split seed alongside the pkl.
# -*- coding: utf-8 -*-
"""P1 Step-4 selector retrain.

Trains the deployed selector on data/dataset_validate_v3.csv (canonical F1 + Sionna frame BLER +
ego fallback + lam=0 oracle labels from make_dataset.py). Held-out 30% (stratified, SEED=0) gives
the class-balance + per-class precision/recall acceptance report.

NEW DISCIPLINE RULE (root-cause fix for the P0.2 "which frames trained this pkl?" archaeology):
the training-frame sample_id list, the held-out list, the split seed and test_size, the feature
names, and the dataset md5 are serialized in data/selector_rf_bundle.pkl alongside the deployed
bare-RF data/selector_rf.pkl. The bundle embeds the deployed RF's own md5 so the two cannot drift.
data/selector_rf.pkl stays a BARE RandomForest for backward compatibility with the downstream
loaders (recompute_policy_200seed.py, true_e2e_global.py) that do pickle.load(...).predict(...).

Feature set (deployed 'full' selector): all columns EXCEPT the excluded metric/label/leakage
columns, keeping est_snr_db + channel_is_rayleigh. ego_f1 is a NEW canonical column and is an
OUTCOME (leakage), so it is excluded from the features -- alongside late_f1/compressed_f1 and the
eff_f1_*/bler_*/oracle_3way label machinery.

Deployed selector -> data/selector_rf.pkl (overwrites; v2 pkl backed up to selector_rf_v2.pkl).
Also retains the base/csi/full ablation comparison in results/step4_rf_modes_v3.csv.
"""
import hashlib
import json
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

REPO = '/home/josh/cooperative_semantic_perception/OpenCOOD'
P1 = os.path.join(REPO, 'peiyi_work/paper1')
DATA = os.path.join(P1, 'data')
RESULTS = os.path.join(P1, 'results')
TRAIN_SPLIT = 'validate'
DATASET = os.path.join(DATA, f'dataset_{TRAIN_SPLIT}_v3.csv')
SEED = 0
TEST_SIZE = 0.30
ACTIONS = ['L', 'C16', 'C256']
PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}

EXCLUDE_COLS = {
    'sample_id', 'cav_keys', 'channel_type',
    *[f'{m}_{s}' for m in ('late', 'early', 'intermediate', 'compressed')
      for s in ('num_pred', 'num_gt', 'tp', 'fp', 'fn', 'precision', 'recall',
                'f1', 'payload_Mbit')],
    *[f'{m}_f1_gain_over_late' for m in ('late', 'early', 'intermediate', 'compressed')],
    *[f'{m}_gain_per_extra_Mbit' for m in ('late', 'early', 'intermediate', 'compressed')],
    'best_method_by_f1', 'best_level_by_f1', 'best_f1', 'best_payload_Mbit',
    'bler_C16', 'bler_C256',
    'eff_f1_L', 'eff_f1_C16', 'eff_f1_C256', 'oracle_3way',
    'ego_f1',  # NEW canonical outcome column -> leakage, must be excluded from features
}


def select_features(df, mode):
    cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    if mode == 'base':
        cols = [c for c in cols if c not in ('est_snr_db', 'channel_is_rayleigh')]
    elif mode == 'csi':
        cols = [c for c in cols if c != 'channel_is_rayleigh']
    return cols


def realised(df, actions):
    actions = np.asarray(actions)
    eff = df[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy()
    idx = np.array([ACTIONS.index(a) for a in actions])
    f1 = eff[np.arange(len(df)), idx].mean()
    pay = np.array([PAYLOAD[a] for a in actions]).mean()
    return float(pay), float(f1)


def fit_rf(df_tr, df_te, mode):
    cols = select_features(df_tr, mode)
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=10, min_samples_leaf=4,
        n_jobs=-1, random_state=SEED, class_weight='balanced')
    rf.fit(df_tr[cols], df_tr['oracle_3way'].to_numpy())
    pred = rf.predict(df_te[cols])
    acc = accuracy_score(df_te['oracle_3way'].to_numpy(), pred)
    pay, f1 = realised(df_te, pred)
    return rf, cols, dict(mode=mode, n_features=len(cols), accuracy=round(acc, 4),
                          mean_payload=round(pay, 4), mean_f1=round(f1, 4))


def main():
    df = pd.read_csv(DATASET)
    ds_md5 = hashlib.md5(open(DATASET, 'rb').read()).hexdigest()
    print(f'training split: dataset_{TRAIN_SPLIT}_v3.csv  {df.shape}  md5={ds_md5}')

    df_tr, df_te = train_test_split(df, test_size=TEST_SIZE, random_state=SEED,
                                    stratify=df['oracle_3way'])
    tr_ids = sorted(df_tr['sample_id'].astype(int).tolist())
    te_ids = sorted(df_te['sample_id'].astype(int).tolist())
    print(f'train/test frames: {len(tr_ids)}/{len(te_ids)}  (test_size={TEST_SIZE}, SEED={SEED})')

    # class balance (full-split oracle label distribution + train/test partitions)
    def dist(d):
        vc = d['oracle_3way'].value_counts()
        return {a: int(vc.get(a, 0)) for a in ACTIONS}
    bal = dict(full=dist(df), train=dist(df_tr), test=dist(df_te))
    print('class balance (oracle_3way counts):', bal)

    # deployed 'full' selector + base/csi ablations
    rf_full, cols_full, r_full = fit_rf(df_tr, df_te, 'full')
    rf_base, _, r_base = fit_rf(df_tr, df_te, 'base')
    rf_csi, _, r_csi = fit_rf(df_tr, df_te, 'csi')
    print('mode summary:')
    for r in (r_base, r_csi, r_full):
        print(f"  {r['mode']:5s} nfeat={r['n_features']:2d} acc={r['accuracy']:.4f} "
              f"payload={r['mean_payload']:.4f} F1={r['mean_f1']:.4f}")

    # per-class precision / recall / f1 / support for the DEPLOYED full selector on the held-out 30%
    y_te = df_te['oracle_3way'].to_numpy()
    y_pred = rf_full.predict(df_te[cols_full])
    p, r, f, sup = precision_recall_fscore_support(y_te, y_pred, labels=ACTIONS, zero_division=0)
    rep_rows = []
    for i, a in enumerate(ACTIONS):
        rep_rows.append(dict(cls=a, support=int(sup[i]),
                             precision=round(float(p[i]), 4), recall=round(float(r[i]), 4),
                             f1=round(float(f[i]), 4),
                             full_split_count=bal['full'][a],
                             full_split_frac=round(bal['full'][a] / len(df), 4)))
    rep = pd.DataFrame(rep_rows)
    print('\nper-class report (deployed full selector, held-out 30%):')
    print(rep.to_string(index=False))

    # ---- write deployed pkl (bare RF, backward compatible) + provenance bundle ----
    os.makedirs(RESULTS, exist_ok=True)
    dep_path = os.path.join(DATA, 'selector_rf.pkl')
    if os.path.exists(dep_path):
        os.replace(dep_path, os.path.join(DATA, 'selector_rf_v2.pkl'))  # back up v2
    with open(dep_path, 'wb') as fh:
        pickle.dump(rf_full, fh)
    rf_md5 = hashlib.md5(open(dep_path, 'rb').read()).hexdigest()

    bundle = dict(
        rf=rf_full, feature_names=cols_full, actions=ACTIONS,
        train_split=TRAIN_SPLIT, train_dataset='dataset_%s_v3.csv' % TRAIN_SPLIT,
        train_dataset_md5=ds_md5, deployed_rf_md5=rf_md5,
        split_seed=SEED, test_size=TEST_SIZE,
        train_sample_ids=tr_ids, test_sample_ids=te_ids,
        class_balance=bal, protocol_version='v3-P1-2026-07-12',
        hyperparams=dict(n_estimators=400, max_depth=10, min_samples_leaf=4,
                         class_weight='balanced', random_state=SEED),
    )
    with open(os.path.join(DATA, 'selector_rf_bundle.pkl'), 'wb') as fh:
        pickle.dump(bundle, fh)
    print(f'\ndeployed selector -> data/selector_rf.pkl  md5={rf_md5}')
    print('provenance bundle -> data/selector_rf_bundle.pkl '
          f'(train_ids={len(tr_ids)}, seed={SEED}, test_size={TEST_SIZE}, dataset_md5={ds_md5})')

    # ---- acceptance CSVs ----
    rep.to_csv(os.path.join(RESULTS, 'step4_rf_class_report_v3.csv'), index=False)
    pd.DataFrame([r_base, r_csi, r_full]).to_csv(
        os.path.join(RESULTS, 'step4_rf_modes_v3.csv'), index=False)
    with open(os.path.join(RESULTS, 'step4_rf_train_meta_v3.json'), 'w') as fh:
        json.dump(dict(train_dataset_md5=ds_md5, deployed_rf_md5=rf_md5,
                       split_seed=SEED, test_size=TEST_SIZE,
                       n_train=len(tr_ids), n_test=len(te_ids),
                       class_balance=bal, feature_names=cols_full,
                       modes=[r_base, r_csi, r_full]), fh, indent=2)
    print('acceptance -> results/step4_rf_class_report_v3.csv, step4_rf_modes_v3.csv, '
          'step4_rf_train_meta_v3.json')


if __name__ == '__main__':
    main()
