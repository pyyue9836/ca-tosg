#self+ CA-TOSG paper2: multi-seed (5 seeds) RF training for mean+/-std reporting
# -*- coding: utf-8 -*-
"""Multi-seed RF training: report mean ± std over 5 random splits.

For each of 5 seeds, retrain rf_full (cues + CSI + channel_type) on a fresh
70/30 stratified split, evaluate on the held-out test split, and report:
  accuracy vs oracle, payload, mean F1, top-3 feature importances.

Output:
  runs/v4_multiseed/per_seed.csv  — raw per-seed metrics
  runs/v4_multiseed/summary.csv   — mean ± std for the paper
"""
import json
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/dataset.csv')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_multiseed')
SEEDS = [0, 1, 2, 3, 4]
PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}

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


def realised(df, actions):
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


def run_one_seed(df, seed):
    df_tr, df_te = train_test_split(df, test_size=0.30, random_state=seed,
                                    stratify=df['oracle_3way'])
    cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    X_tr, y_tr = df_tr[cols], df_tr['oracle_3way'].to_numpy()
    X_te, y_te = df_te[cols], df_te['oracle_3way'].to_numpy()
    rf = RandomForestClassifier(
        n_estimators=400, max_depth=10, min_samples_leaf=4,
        n_jobs=-1, random_state=seed, class_weight='balanced')
    rf.fit(X_tr, y_tr)
    pred = rf.predict(X_te)
    acc = accuracy_score(y_te, pred)
    pay, f1 = realised(df_te, pred)
    imp = pd.DataFrame({'feature': cols, 'importance': rf.feature_importances_})
    imp = imp.sort_values('importance', ascending=False).head(3)
    return dict(seed=seed, accuracy=acc, mean_payload=pay, mean_f1=f1,
                imp_top1=imp.iloc[0]['feature'], imp_top1_val=imp.iloc[0]['importance'],
                imp_top2=imp.iloc[1]['feature'], imp_top2_val=imp.iloc[1]['importance'],
                imp_top3=imp.iloc[2]['feature'], imp_top3_val=imp.iloc[2]['importance'])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATASET)
    print(f'dataset: {df.shape}')
    rows = []
    for s in SEEDS:
        r = run_one_seed(df, s)
        rows.append(r)
        print(f'  seed={s}: acc={r["accuracy"]:.4f}  payload={r["mean_payload"]:.4f}  F1={r["mean_f1"]:.4f}')
    df_per = pd.DataFrame(rows)
    df_per.to_csv(os.path.join(OUT_DIR, 'per_seed.csv'), index=False)

    summary = pd.DataFrame({
        'metric': ['accuracy', 'mean_payload', 'mean_f1'],
        'mean': [df_per[k].mean() for k in ('accuracy', 'mean_payload', 'mean_f1')],
        'std':  [df_per[k].std()  for k in ('accuracy', 'mean_payload', 'mean_f1')],
    })
    summary.to_csv(os.path.join(OUT_DIR, 'summary.csv'), index=False)
    print('\n=== mean ± std over %d seeds ===' % len(SEEDS))
    for _, r in summary.iterrows():
        print(f'  {r["metric"]:14s}: {r["mean"]:.4f} ± {r["std"]:.4f}')
    print('wrote', OUT_DIR)


if __name__ == '__main__':
    main()
