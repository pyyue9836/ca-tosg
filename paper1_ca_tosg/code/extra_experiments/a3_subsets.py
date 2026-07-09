#self+ A3: long-range / sparse-LiDAR / occlusion subsets -- selector activates C where it helps
"""
Shows the selector is not randomly saving bandwidth: in subsets that plausibly
need richer semantics it requests feature-level C more often AND the CA-TOSG-over-L
gain (under a channel that can support C) is larger. Subsets (top tercile of a cue,
cached per-frame; proxies are labelled as such):
  Long-range : many far LiDAR returns (pcd_far_50_80m + pcd_very_far_80m)
  Sparse     : few LiDAR points (low pcd_num_points)
  Occlusion* : object-level false positives high (late_fp) -- proxy for occluded/ambiguous scenes
For each subset vs its complement we report the selector's C-activation rate
(all channels) and the CA-TOSG-over-L F1 gain on the reliable-channel cut.
Output: out/a3_subsets.csv
"""
import os
import numpy as np
import pandas as pd
import _common as C

SUBSETS = {
    'Long-range (far points)': lambda d: d['pcd_far_50_80m'] + d['pcd_very_far_80m'],
    'Sparse LiDAR (few points)': lambda d: -d['pcd_num_points'],
    'Occlusion* (late FP high)': lambda d: d['late_fp'],
}


def analyse(name, csv, rf):
    df = pd.read_csv(csv)
    act = np.asarray(C.rf_predict(rf, df))
    good = (df['channel_type'].to_numpy() == 'awgn') & (df['est_snr_db'].to_numpy() >= 14)
    rows = []
    for sname, fn in SUBSETS.items():
        score = fn(df).to_numpy()
        thr = np.quantile(score, 2/3)
        insub = score >= thr
        for grp, mask in [('subset (top 1/3)', insub), ('complement', ~insub)]:
            c16 = float((act[mask] == 'C16').mean())
            cany = float(np.isin(act[mask], ['C16', 'C256']).mean())
            # reliable-channel gain within this group
            gmask = mask & good
            if gmask.sum() >= 20:
                sub = df[gmask]
                _, fL = C.realised(sub, np.array(['L'] * len(sub)))
                _, fR = C.realised(sub, act[gmask])
                gain = fR - fL
            else:
                gain = float('nan')
            rows.append(dict(split=name, subset=sname, group=grp, n=int(mask.sum()),
                             C_activation_rate=round(cany, 3),
                             C16_rate=round(c16, 3),
                             gain_good_channel=round(gain, 4) if gain == gain else None,
                             n_good=int(gmask.sum())))
    return rows


def main():
    rf = C.load_rf()
    rows = []
    for name, csv in [('validate', C.VAL_CSV), ('test', C.TEST_CSV)]:
        rows += analyse(name, csv, rf)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(C.OUTDIR, 'a3_subsets.csv'), index=False)
    # print contrast: subset vs complement C-activation
    for name in ['validate', 'test']:
        print(f'\n=== {name}: C-activation rate (subset vs complement) + good-channel gain ===')
        print(out[out.split == name].to_string())


if __name__ == '__main__':
    main()
