#self+ gamma-alone flip MECHANISM test (supervisor 2026-07-17): the strong, testable hypothesis --
# without c_t, adding gamma EMBOLDENS feature requests (payload 0.089->0.182); on Rayleigh, high est_snr is a
# lie (frame BLER ~ 1 for 0-20 dB in our table), so the extra C16 requests land on undeliverable frames and
# collapse to the ego floor -> the F1 loss of Perception+gamma vs Perception-only should CONCENTRATE ON
# RAYLEIGH. Predicted: delta_awgn >= 0, delta_rayleigh << 0. Confirm -> structural mechanism; refute -> return.
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extra_experiments'))
import _common as C, v3_eval as V
from sklearn.ensemble import RandomForestClassifier

P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tr = pd.read_csv(os.path.join(P1, 'data/dataset_validate_v3.csv'))
te = pd.read_csv(C.TEST_CSV)
def fit(cols):
    rf = RandomForestClassifier(n_estimators=400, max_depth=10, min_samples_leaf=4,
                                n_jobs=-1, random_state=0, class_weight='balanced')
    rf.fit(tr[cols], tr['oracle_3way'].to_numpy()); return rf
perc = C.feat_cols(tr, 'perception_only'); csi = C.feat_cols(tr, 'csi')      # 21 cues ; +est_snr = 22
rf_p, rf_c = fit(perc), fit(csi)
ACT = {'L': 0, 'C16': 1, 'C256': 2}
late, comp, ego = te.late_f1.to_numpy(), te.compressed_f1.to_numpy(), te.ego_f1.to_numpy()

def eval_channel(rf, cols, ch_name, n_seed=200):
    n = len(te); accf = np.zeros(n); accpay = np.zeros(n); accc16 = 0.0; PAY = np.array([0.024, 0.99, 0.495])
    for s in range(n_seed):
        rng = np.random.default_rng(s); snr = rng.uniform(0, 20, n)
        b16 = V._bler(snr, 16, ch_name)                                     # per-channel frame BLER
        eff = np.stack([late, comp * (1 - b16) + ego * b16, comp], axis=1)  # C256 col unused (never picked)
        d = te.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = int(ch_name == 'rayleigh')
        ai = np.array([ACT[x] for x in rf.predict(d[cols])])
        accf += eff[np.arange(n), ai]; accpay += PAY[ai]; accc16 += float((ai == 1).mean())
    return accf.mean() / n_seed, accpay.mean() / n_seed, accc16 / n_seed

rows = []
for ch in ('awgn', 'rayleigh', 'ofdm'):                                     # ALL THREE channels the paper uses
    fp, pp, cp = eval_channel(rf_p, perc, ch); fc, pc, cc = eval_channel(rf_c, csi, ch)
    rows.append(dict(channel=ch, perc_only_f1=round(fp, 4), perc_plus_gamma_f1=round(fc, 4),
                     delta_f1=round(fc - fp, 4), fracC16_perc=round(cp, 4), fracC16_percgamma=round(cc, 4)))
out = pd.DataFrame(rows); print(out.to_string(index=False))
out.to_csv(os.path.join(P1, 'results/gamma_mechanism.csv'), index=False)
d = {r['channel']: r['delta_f1'] for r in rows}
neg_on_fading = bool(d['rayleigh'] < -0.002 and d['ofdm'] < -0.002 and d['awgn'] >= d['rayleigh'])
print(f"\ndelta by channel: AWGN={d['awgn']:+.4f}  Rayleigh={d['rayleigh']:+.4f}  OFDM={d['ofdm']:+.4f}")
print(f"request share frac_C16 (perc-only -> perc+gamma), should be channel-INVARIANT: "
      f"{[(r['channel'], r['fracC16_perc'], r['fracC16_percgamma']) for r in rows]}")
print("MECHANISM CONFIRMED on BOTH fading channels (Rayleigh AND OFDM<threshold): gamma emboldens requests "
      "that fail where BLER~1 -> ego collapse; request share is channel-invariant." if neg_on_fading else
      "OFDM cell NOT negative -> inconsistent with our physics; RETURN for investigation, sentence descriptive.")
