#self+ A7 v3 (200-realisation, PUBLICATION): feature ablation -- what do perception cues add over
# channel state alone, under the v3 canonical protocol (200 real. + v3 GT + Sionna frame BLER + ego).
"""
Published claim (4.4.4): "cues add <X over channel state alone". Under v3 the ego floor widened the
feasible window, so the cue marginal value MAY rise (same mechanism as the LDPC-side edge) -- measured,
not assumed. Train an RF per feature subset on the FROZEN v3 oracle_3way labels (labels are fixed);
EVALUATE each over 200 channel realisations on the held-out TEST split (train=validate). Report mean F1
+ payload (200-real) per subset, the key delta (full - channel_only = "cues add ..."), and its
FRAME-level paired bootstrap 95% CI. Single-frozen-draw numbers are NOT used here.
Outputs: out/a7_ablation_v3.csv + out/a7_cue_value_v3.csv
"""
import os
import numpy as np
import pandas as pd
import _common as C
import v3_eval as V

RANGE_CUES = {'pcd_mean_range', 'pcd_max_range', 'pcd_std_range', 'pcd_near_20m', 'pcd_mid_20_50m',
              'pcd_far_50_80m', 'pcd_very_far_80m', 'pcd_front_far_30m', 'pcd_front_far_50m'}
DENSITY_CUES = {'pcd_density_0_20', 'pcd_density_20_50', 'pcd_density_50_80', 'pcd_num_points'}
OBJCOUNT_CUES = {'ego_num_objects', 'num_cavs'}


def fit(df_tr, cols):
    from sklearn.ensemble import RandomForestClassifier
    rf = RandomForestClassifier(n_estimators=400, max_depth=10, min_samples_leaf=4,
                                n_jobs=-1, random_state=C.SEED, class_weight='balanced')
    rf.fit(df_tr[cols], df_tr['oracle_3way'].to_numpy())
    return rf


def main():
    tr = pd.read_csv(C.VAL_CSV); te = pd.read_csv(C.TEST_CSV)
    full = C.feat_cols(tr, 'full')
    configs = [
        ('Channel only (SNR + ch type)', C.feat_cols(tr, 'channel_only')),
        ('Perception cues only', C.feat_cols(tr, 'perception_only')),
        ('Perception + SNR', C.feat_cols(tr, 'csi')),
        ('Full (all features)', full),
        ('Full - range cues', [c for c in full if c not in RANGE_CUES]),
        ('Full - density cues', [c for c in full if c not in DENSITY_CUES]),
        ('Full - object-count cues', [c for c in full if c not in OBJCOUNT_CUES]),
    ]
    rows = {}; fm = {}
    for label, cols in configs:
        rf = fit(tr, cols)
        f1s, pays = V.eval_series(te, 'rf', feat=cols, model=rf)
        rows[label] = dict(policy=label, n_features=len(cols), **V.summ(f1s, pays))
        fm[label] = V.frame_means(te, 'rf', feat=cols, model=rf)
    f1o, payo = V.eval_series(te, 'oracle'); rows['Oracle (upper bound)'] = dict(
        policy='Oracle (upper bound)', n_features=0, **V.summ(f1o, payo))
    f1L, payL = V.eval_series(te, 'fixedL'); rows['Fixed L'] = dict(
        policy='Fixed L', n_features=0, **V.summ(f1L, payL))

    df = pd.DataFrame(list(rows.values()))
    d_cues, lo_c, hi_c = V.paired_ci_frames_from(fm['Full (all features)'], fm['Channel only (SNR + ch type)'])
    d_csi, lo_s, hi_s = V.paired_ci_frames_from(fm['Perception + SNR'], fm['Channel only (SNR + ch type)'])
    print('=== A7 v3 200-realisation feature ablation (train=validate, eval=test) ===')
    print(df.to_string(index=False))
    print(f"\ncues_add_over_channel_alone (Full - Channel-only): {d_cues:+.5f}  95% CI [{lo_c:+.5f}, {hi_c:+.5f}]  "
          f"{'significant' if (lo_c>0 or hi_c<0) else 'NOT significant'}")
    print(f"perception+SNR - channel-only:                     {d_csi:+.5f}  95% CI [{lo_s:+.5f}, {hi_s:+.5f}]")
    df.to_csv(os.path.join(C.OUTDIR, 'a7_ablation_v3.csv'), index=False)
    pd.DataFrame([dict(delta='cues_add_over_channel_alone', value=round(d_cues, 5), ci_lo=round(lo_c, 5),
                       ci_hi=round(hi_c, 5), significant=bool(lo_c > 0 or hi_c < 0)),
                  dict(delta='perception+SNR_minus_channel_only', value=round(d_csi, 5), ci_lo=round(lo_s, 5),
                       ci_hi=round(hi_s, 5), significant=bool(lo_s > 0 or hi_s < 0))]).to_csv(
        os.path.join(C.OUTDIR, 'a7_cue_value_v3.csv'), index=False)
    print('wrote out/a7_ablation_v3.csv + a7_cue_value_v3.csv')


if __name__ == '__main__':
    main()
