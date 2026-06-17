#self+ A7: selector feature ablation + SNR-threshold baseline (the honesty check)
"""
Channel features dominate the importance ranking, so a reviewer will ask: is a
simple SNR threshold enough? We compare, on a held-out split:
  - RF with feature subsets: channel-only / perception-only / perception+SNR / full,
    and full minus range / density / object-count feature groups;
  - a hand-tuned SNR-threshold rule (if AWGN and SNR > tau -> C16 else L), tau swept;
We report oracle-action accuracy, realised F1, and payload. If RF only marginally
beats the threshold rule, the honest contribution is a lightweight interpretable
channel-aware policy -- which we state plainly.
Train on validate, evaluate on the OPV2V test split.
Outputs: out/a7_ablation.csv, out/a7_snr_threshold.csv
"""
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import _common as C

RANGE_CUES = ['pcd_mean_range', 'pcd_max_range', 'pcd_std_range',
              'pcd_near_20m', 'pcd_mid_20_50m', 'pcd_far_50_80m', 'pcd_very_far_80m',
              'pcd_front_far_30m', 'pcd_front_far_50m']
DENSITY_CUES = ['pcd_density_0_20', 'pcd_density_20_50', 'pcd_density_50_80',
                'pcd_num_points']
OBJCOUNT_CUES = ['ego_num_objects', 'num_cavs']


def train_eval(train, test, cols, label):
    rf = RandomForestClassifier(n_estimators=400, max_depth=10, min_samples_leaf=4,
                                random_state=C.SEED, n_jobs=-1)
    rf.fit(train[cols], train['oracle_3way'])
    pred = rf.predict(test[cols])
    acc = float((pred == test['oracle_3way'].to_numpy()).mean())
    pay, f1 = C.realised(test, pred)
    return dict(policy=label, n_features=len(cols), oracle_acc=round(acc, 4),
                realised_f1=round(f1, 4), payload=round(pay, 4))


def snr_threshold_rule(df, tau):
    awgn = df['channel_type'].to_numpy() == 'awgn'
    snr = df['est_snr_db'].to_numpy()
    return np.where(awgn & (snr > tau), 'C16', 'L')


def main():
    train = pd.read_csv(C.VAL_CSV)
    test = pd.read_csv(C.TEST_CSV)

    rows = []
    full = C.feat_cols(train, 'full')
    configs = [
        ('Channel only (SNR + ch type)', C.feat_cols(train, 'channel_only')),
        ('Perception cues only', C.feat_cols(train, 'perception_only')),
        ('Perception + SNR', C.feat_cols(train, 'csi')),
        ('Full (all features)', full),
        ('Full - range cues', [c for c in full if c not in RANGE_CUES]),
        ('Full - density cues', [c for c in full if c not in DENSITY_CUES]),
        ('Full - object-count cues', [c for c in full if c not in OBJCOUNT_CUES]),
    ]
    for label, cols in configs:
        rows.append(train_eval(train, test, cols, label))
    # references
    pay_or, f1_or = C.realised(test, test['oracle_3way'].to_numpy())
    rows.append(dict(policy='Oracle (upper bound)', n_features=0, oracle_acc=1.0,
                     realised_f1=round(f1_or, 4), payload=round(pay_or, 4)))
    _, f1_L = C.realised(test, np.array(['L'] * len(test)))
    rows.append(dict(policy='Fixed L', n_features=0,
                     oracle_acc=round(float((test['oracle_3way'] == 'L').mean()), 4),
                     realised_f1=round(f1_L, 4), payload=0.024))
    abl = pd.DataFrame(rows)
    abl.to_csv(os.path.join(C.OUTDIR, 'a7_ablation.csv'), index=False)
    print('=== A7 feature ablation (train=validate, eval=test) ===')
    print(abl.to_string())

    # SNR-threshold rule sweep
    trows = []
    for tau in range(0, 21, 2):
        for split, df in [('validate', train), ('test', test)]:
            pred = snr_threshold_rule(df, tau)
            acc = float((pred == df['oracle_3way'].to_numpy()).mean())
            pay, f1 = C.realised(df, pred)
            trows.append(dict(split=split, tau=tau, oracle_acc=round(acc, 4),
                              realised_f1=round(f1, 4), payload=round(pay, 4)))
    tdf = pd.DataFrame(trows)
    tdf.to_csv(os.path.join(C.OUTDIR, 'a7_snr_threshold.csv'), index=False)
    best = tdf[tdf.split == 'test'].sort_values('realised_f1', ascending=False).iloc[0]
    print('\n=== SNR-threshold rule (best tau on test by realised F1) ===')
    print(tdf[tdf.split == 'test'].to_string())
    print(f"\nBEST threshold (test): tau={best['tau']:.0f}  F1={best['realised_f1']:.4f}  "
          f"payload={best['payload']:.4f}")
    rf_full_row = abl[abl.policy == 'Full (all features)'].iloc[0]
    print(f"RF full       (test):           F1={rf_full_row['realised_f1']:.4f}  "
          f"payload={rf_full_row['payload']:.4f}")
    print(f"=> RF beats best threshold by F1 {rf_full_row['realised_f1']-best['realised_f1']:+.4f} "
          f"at payload {rf_full_row['payload']-best['payload']:+.4f}")


if __name__ == '__main__':
    main()
