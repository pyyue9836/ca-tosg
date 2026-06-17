#self+ CA-TOSG paper2 v1: 2-way RF training (cues only / +CSI variants)
# -*- coding: utf-8 -*-
"""Train baseline RF (cues only) vs CSI-aware RF (cues + SNR) for Paper #2.

Reports:
  * classification accuracy vs the channel-aware oracle label
  * feature importance ranking (Top-15 by Gini)
  * mean payload + mean F1 across the 1980-frame test set under each policy

Output: peiyi_work/01_paper_ca_tosg/runs/v1/{rf_baseline.pkl,rf_csi.pkl,feature_importance.csv,
                            summary.json}

Run:
  /home/josh/miniconda3/envs/sionna310/bin/python peiyi_work/01_paper_ca_tosg/train_rf.py
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
RUN_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v1')
DATASET = os.path.join(RUN_DIR, 'dataset.csv')

PAYLOAD_LATE = 0.024   # Mbit
PAYLOAD_COMP = 1.98    # Mbit
SEED = 0

# Columns we must NOT feed to the RF (labels, ground-truth-derived, or leakage).
EXCLUDE_COLS = {
    'sample_id', 'cav_keys',
    # all per-method GT-derived results (would leak the oracle answer)
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
    # added by make_dataset (labels + channel-side)
    'bler_16qam', 'effective_compressed_f1', 'channel_oracle',
}

CSI_COL = 'est_snr_db'


def select_features(df, include_csi):
    cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    if not include_csi and CSI_COL in cols:
        cols.remove(CSI_COL)
    return cols


def evaluate_policy(df_test, pred_labels):
    """Mean payload + mean realised F1 of a policy that emits {compressed,late}.

    Uses the channel-aware effective_compressed_f1 column (already accounts
    for BLER at each row's SNR) so the F1 number reflects the actual receiver-
    side detection quality, not the pre-channel oracle.
    """
    pred = np.asarray(pred_labels)
    f1 = np.where(pred == 'compressed',
                  df_test['effective_compressed_f1'].to_numpy(),
                  df_test['late_f1'].to_numpy())
    payload = np.where(pred == 'compressed', PAYLOAD_COMP, PAYLOAD_LATE)
    return float(payload.mean()), float(f1.mean())


def train_and_report(df_train, df_test, name, include_csi):
    cols = select_features(df_train, include_csi)
    print('\n[%s] features: %d  (CSI included = %s)' %
          (name, len(cols), include_csi))

    # Fit on DataFrame so sklearn embeds feature_names_in_ on the estimator.
    X_train = df_train[cols]
    y_train = df_train['channel_oracle'].to_numpy()
    X_test = df_test[cols]
    y_test = df_test['channel_oracle'].to_numpy()

    rf = RandomForestClassifier(
        n_estimators=300, max_depth=8, min_samples_leaf=4,
        n_jobs=-1, random_state=SEED, class_weight='balanced',
    )
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    mean_payload, mean_f1 = evaluate_policy(df_test, y_pred)

    # Feature importance.
    imp = pd.DataFrame({
        'feature': cols,
        'importance': rf.feature_importances_,
    }).sort_values('importance', ascending=False)

    print('  accuracy vs channel_oracle = %.4f' % acc)
    print('  mean payload / frame       = %.4f Mbit' % mean_payload)
    print('  mean realised F1           = %.4f' % mean_f1)
    print('  top-5 features:')
    for _, r in imp.head(5).iterrows():
        print('    %-30s %.4f' % (r['feature'], r['importance']))

    return rf, imp, dict(
        name=name, include_csi=include_csi, n_features=len(cols),
        accuracy=acc, mean_payload_Mbit=mean_payload, mean_f1=mean_f1,
    )


def oracle_and_fixed_policies(df_test):
    """Reference points to compare RF against."""
    rows = []
    # channel-aware oracle (upper bound).
    or_pl, or_f1 = evaluate_policy(df_test, df_test['channel_oracle'])
    rows.append(dict(name='channel_oracle', accuracy=1.0,
                     mean_payload_Mbit=or_pl, mean_f1=or_f1, n_features=0,
                     include_csi=True))
    # always-late.
    pl, f1 = evaluate_policy(df_test, np.array(['late'] * len(df_test)))
    rows.append(dict(name='fixed_late', accuracy=float((df_test['channel_oracle'] == 'late').mean()),
                     mean_payload_Mbit=pl, mean_f1=f1, n_features=0,
                     include_csi=False))
    # always-compressed.
    pl, f1 = evaluate_policy(df_test, np.array(['compressed'] * len(df_test)))
    rows.append(dict(name='fixed_compressed',
                     accuracy=float((df_test['channel_oracle'] == 'compressed').mean()),
                     mean_payload_Mbit=pl, mean_f1=f1, n_features=0,
                     include_csi=False))
    return rows


def main():
    df = pd.read_csv(DATASET)
    print('dataset:', df.shape)
    df_train, df_test = train_test_split(
        df, test_size=0.30, random_state=SEED, stratify=df['channel_oracle'])
    print('train/test:', df_train.shape, df_test.shape)

    rows = oracle_and_fixed_policies(df_test)
    for r in rows:
        print('[ref] %-20s payload=%.4f  F1=%.4f  acc=%.4f'
              % (r['name'], r['mean_payload_Mbit'], r['mean_f1'], r['accuracy']))

    rf_base, imp_base, r_base = train_and_report(df_train, df_test,
                                                 'rf_baseline', include_csi=False)
    rf_csi,  imp_csi,  r_csi  = train_and_report(df_train, df_test,
                                                 'rf_csi', include_csi=True)
    rows += [r_base, r_csi]

    # Persist.
    with open(os.path.join(RUN_DIR, 'rf_baseline.pkl'), 'wb') as f:
        pickle.dump(rf_base, f)
    with open(os.path.join(RUN_DIR, 'rf_csi.pkl'), 'wb') as f:
        pickle.dump(rf_csi, f)
    imp_base.to_csv(os.path.join(RUN_DIR, 'feature_importance_baseline.csv'),
                    index=False)
    imp_csi.to_csv(os.path.join(RUN_DIR, 'feature_importance_csi.csv'),
                   index=False)
    with open(os.path.join(RUN_DIR, 'summary.json'), 'w') as f:
        json.dump(rows, f, indent=2)
    pd.DataFrame(rows).to_csv(os.path.join(RUN_DIR, 'summary.csv'), index=False)
    print('\nwrote summary to', os.path.join(RUN_DIR, 'summary.json'))


if __name__ == '__main__':
    main()
