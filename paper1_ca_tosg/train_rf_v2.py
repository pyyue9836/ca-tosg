#self+ CA-TOSG paper2 v2: 3-way RF training — deployed selector (cues + CSI + channel type)
# -*- coding: utf-8 -*-
"""V2 3-way RF: predicts {L, C16, C256} from cues + CSI + channel type.

Compares:
  * channel-aware 3-way oracle (upper bound)
  * fixed L / C16 / C256
  * RF baseline (cues only, no CSI, no channel type)
  * RF + CSI (cues + estimated SNR)
  * RF + CSI + channel (cues + SNR + channel-type one-hot)  <-- proposed

Outputs: peiyi_work/01_paper_ca_tosg/runs/v2/{rf_*.pkl,summary.{csv,json},feature_importance_*}
"""
import json
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2')
DATASET = os.path.join(RUN_DIR, 'dataset.csv')

PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}  # Mbit channel-use eq.
SEED = 0

EXCLUDE_COLS = {
    'sample_id', 'cav_keys', 'channel_type',
    'late_num_pred', 'late_num_gt', 'late_tp', 'late_fp', 'late_fn',
    'late_precision', 'late_recall', 'late_f1', 'late_payload_Mbit',
    'early_num_pred', 'early_num_gt', 'early_tp', 'early_fp', 'early_fn',
    'early_precision', 'early_recall', 'early_f1', 'early_payload_Mbit',
    'intermediate_num_pred', 'intermediate_num_gt', 'intermediate_tp',
    'intermediate_fp', 'intermediate_fn', 'intermediate_precision',
    'intermediate_recall', 'intermediate_f1', 'intermediate_payload_Mbit',
    'compressed_num_pred', 'compressed_num_gt', 'compressed_tp',
    'compressed_fp', 'compressed_fn', 'compressed_precision',
    'compressed_recall', 'compressed_f1', 'compressed_payload_Mbit',
    'late_f1_gain_over_late', 'late_gain_per_extra_Mbit',
    'early_f1_gain_over_late', 'early_gain_per_extra_Mbit',
    'intermediate_f1_gain_over_late', 'intermediate_gain_per_extra_Mbit',
    'compressed_f1_gain_over_late', 'compressed_gain_per_extra_Mbit',
    'best_method_by_f1', 'best_level_by_f1', 'best_f1', 'best_payload_Mbit',
    'bler_C16', 'bler_C256',
    'eff_f1_L', 'eff_f1_C16', 'eff_f1_C256',
    'oracle_3way',
}


def select_features(df, mode):
    """mode: 'base' (no CSI, no channel) | 'csi' (CSI only) | 'full' (both)."""
    cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    if mode == 'base':
        for c in ('est_snr_db', 'channel_is_rayleigh'):
            if c in cols: cols.remove(c)
    elif mode == 'csi':
        if 'channel_is_rayleigh' in cols: cols.remove('channel_is_rayleigh')
    return cols


def realised(df, actions):
    """Return (mean payload, mean F1) for a policy that emits per-frame actions."""
    actions = np.asarray(actions)
    f1 = np.choose(
        (actions == 'C256').astype(int) * 2 + (actions == 'C16').astype(int),
        [df['eff_f1_L'].to_numpy(), df['eff_f1_C16'].to_numpy(),
         df['eff_f1_C256'].to_numpy()],
    )
    pay = np.zeros_like(f1)
    for a in PAYLOAD:
        pay[actions == a] = PAYLOAD[a]
    return float(pay.mean()), float(f1.mean())


def fit_rf(df_train, df_test, name, mode):
    cols = select_features(df_train, mode)
    print('\n[%s] mode=%s  #features=%d' % (name, mode, len(cols)))
    X_tr = df_train[cols]; y_tr = df_train['oracle_3way'].to_numpy()
    X_te = df_test[cols];  y_te = df_test['oracle_3way'].to_numpy()
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=10, min_samples_leaf=4,
        n_jobs=-1, random_state=SEED, class_weight='balanced')
    rf.fit(X_tr, y_tr)
    pred = rf.predict(X_te)
    acc = accuracy_score(y_te, pred)
    pay, f1 = realised(df_test, pred)
    imp = pd.DataFrame({
        'feature': cols, 'importance': rf.feature_importances_,
    }).sort_values('importance', ascending=False)
    print('  acc vs oracle = %.4f' % acc)
    print('  payload (Mbit channel-use eq.) = %.4f' % pay)
    print('  realised F1 = %.4f' % f1)
    print('  top-5 features:')
    for _, r in imp.head(5).iterrows():
        print('    %-30s %.4f' % (r['feature'], r['importance']))
    return rf, imp, dict(name=name, mode=mode, n_features=len(cols),
                         accuracy=acc, mean_payload=pay, mean_f1=f1)


def reference_rows(df_test):
    rows = []
    pay, f1 = realised(df_test, df_test['oracle_3way'].to_numpy())
    rows.append(dict(name='oracle_3way', mode='oracle', n_features=0,
                     accuracy=1.0, mean_payload=pay, mean_f1=f1))
    for a in ('L', 'C16', 'C256'):
        pred = np.array([a] * len(df_test))
        pay, f1 = realised(df_test, pred)
        acc = float((df_test['oracle_3way'] == a).mean())
        rows.append(dict(name='fixed_' + a, mode='fixed', n_features=0,
                         accuracy=acc, mean_payload=pay, mean_f1=f1))
    return rows


def main():
    df = pd.read_csv(DATASET)
    print('dataset:', df.shape)
    df_tr, df_te = train_test_split(df, test_size=0.30, random_state=SEED,
                                    stratify=df['oracle_3way'])
    print('train/test:', df_tr.shape, df_te.shape)

    rows = reference_rows(df_te)
    for r in rows:
        print('[ref] %-15s payload=%.4f  F1=%.4f' %
              (r['name'], r['mean_payload'], r['mean_f1']))

    rf_base, imp_base, r_base = fit_rf(df_tr, df_te, 'rf_base', 'base')
    rf_csi, imp_csi, r_csi = fit_rf(df_tr, df_te, 'rf_csi', 'csi')
    rf_full, imp_full, r_full = fit_rf(df_tr, df_te, 'rf_full', 'full')
    rows += [r_base, r_csi, r_full]

    for name, obj in [('rf_base', rf_base), ('rf_csi', rf_csi),
                      ('rf_full', rf_full)]:
        with open(os.path.join(RUN_DIR, name + '.pkl'), 'wb') as f:
            pickle.dump(obj, f)
    imp_base.to_csv(os.path.join(RUN_DIR, 'feature_importance_base.csv'),
                    index=False)
    imp_csi.to_csv(os.path.join(RUN_DIR, 'feature_importance_csi.csv'),
                   index=False)
    imp_full.to_csv(os.path.join(RUN_DIR, 'feature_importance_full.csv'),
                    index=False)
    with open(os.path.join(RUN_DIR, 'summary.json'), 'w') as f:
        json.dump(rows, f, indent=2)
    pd.DataFrame(rows).to_csv(os.path.join(RUN_DIR, 'summary.csv'), index=False)
    print('\nwrote', os.path.join(RUN_DIR, 'summary.json'))


if __name__ == '__main__':
    main()
