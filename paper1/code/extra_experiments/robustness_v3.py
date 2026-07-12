#self+ Robustness triple v3 (200-realisation, PUBLICATION): CSI-estimation noise / Jakes channel aging /
# whole-frame decision staleness. 4.4.4 published numbers -- all re-run under the v3 canonical protocol
# (200 real. + v3 GT + Sionna frame BLER + ego), NOT the old codeword-BLER/failure->0/single-draw path.
"""
All three degrade only the SELECTOR's information; the channel does not lie (eff uses the TRUE snr).
  (1) CSI noise:   selector sees est_snr = true_snr + N(0,sigma), sigma in {0,0.5,1,2,3,5} dB.
  (2) Channel aging: est-snr error from Jakes decorrelation at 60 km/h (fd~327 Hz), delay tau in
      {0,10,20,50} ms -> sigma = sqrt(1-J0(2 pi fd tau)^2) * 6 dB (same dB-spread scaling as v2).
  (3) Decision staleness: the RF decides on frame t-d, applied to frame t (whole-frame round trip at
      10 Hz), d in {0,1,2,5} frames; scenario boundaries respected (sample_id resets).
Each reports realised F1 vs the perturbation + the F1 DROP vs the unperturbed point with a FRAME-level
paired bootstrap 95% CI. Eval split = test (held-out).
Outputs: out/robustness_csi_noise_v3.csv, out/robustness_aging_v3.csv, out/robustness_staleness_v3.csv
"""
import os
import numpy as np
import pandas as pd
from scipy.special import j0
import _common as C
import v3_eval as V

SIGMAS = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
TAUS_MS = [0, 10, 20, 50]
DELAYS = [0, 1, 2, 5]
FC, V_KMH = 5.9e9, 60.0
FD = (V_KMH / 3.6) * FC / 3e8                          # Doppler ~327 Hz


def csi_noise(te, rf, feat):
    rows = []; fm0 = V.frame_means(te, 'rf', feat=feat, model=rf, csi_noise_sigma=0.0)
    for sg in SIGMAS:
        f1s, pays = V.eval_series(te, 'rf', feat=feat, model=rf, csi_noise_sigma=sg)
        drop, lo, hi = (0.0, 0.0, 0.0) if sg == 0 else V.paired_ci_frames_from(
            fm0, V.frame_means(te, 'rf', feat=feat, model=rf, csi_noise_sigma=sg))
        rows.append(dict(sigma_db=sg, mean_f1=round(float(f1s.mean()), 4), std_f1=round(float(f1s.std()), 4),
                         mean_payload=round(float(pays.mean()), 4), f1_drop_vs_0=round(drop, 5),
                         drop_ci_lo=round(lo, 5), drop_ci_hi=round(hi, 5),
                         drop_significant=bool(sg > 0 and (lo > 0 or hi < 0))))
    return pd.DataFrame(rows)


def aging(te, rf, feat):
    rows = []; fm0 = V.frame_means(te, 'rf', feat=feat, model=rf, csi_noise_sigma=0.0)
    for tau in TAUS_MS:
        rho = float(j0(2 * np.pi * FD * tau * 1e-3)); sg = np.sqrt(max(0.0, 1 - rho ** 2)) * 6.0
        f1s, pays = V.eval_series(te, 'rf', feat=feat, model=rf, csi_noise_sigma=sg)
        drop, lo, hi = (0.0, 0.0, 0.0) if tau == 0 else V.paired_ci_frames_from(
            fm0, V.frame_means(te, 'rf', feat=feat, model=rf, csi_noise_sigma=sg))
        rows.append(dict(delay_ms=tau, jakes_rho=round(rho, 3), snr_err_std_db=round(sg, 2),
                         mean_f1=round(float(f1s.mean()), 4), mean_payload=round(float(pays.mean()), 4),
                         f1_drop_vs_0=round(drop, 5), drop_ci_lo=round(lo, 5), drop_ci_hi=round(hi, 5),
                         drop_significant=bool(tau > 0 and (lo > 0 or hi < 0))))
    return pd.DataFrame(rows)


def _segments(df):
    sid = df['sample_id'].to_numpy()
    bounds = [0] + list(np.where(np.diff(sid) < 0)[0] + 1) + [len(df)]
    return [np.arange(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if b - a >= 3]


def staleness(te, rf, feat, n_seed=V.N_SEED):
    """200-real: per realisation compute RF action per frame, then apply the frame t-d action to frame t
    (within scenarios); realised F1 = eff[t, action[t-d]]. Per-frame mean over realisations for the CI."""
    n = len(te); segs = _segments(te)
    late = te['late_f1'].to_numpy(); comp = te['compressed_f1'].to_numpy(); ego = te['ego_f1'].to_numpy()
    acc = {d: np.zeros(n) for d in DELAYS}; cnt = {d: np.zeros(n) for d in DELAYS}
    stale_num = {d: 0 for d in DELAYS}; stale_den = {d: 0 for d in DELAYS}
    for s in range(n_seed):
        snr, is_ray, b16, b256 = V.draws(n, s)
        eff = V.eff_of(te, b16, b256)
        d0 = te.copy(); d0['est_snr_db'] = snr; d0['channel_is_rayleigh'] = is_ray.astype(int)
        act = np.array([V.ACTIONS.index(a) for a in np.asarray(rf.predict(d0[feat]))])
        # oracle action (masked) for the stale-decision-rate
        orac = V.masked_oracle(eff, b16, b256)
        for d in DELAYS:
            for seg in segs:
                if len(seg) <= d:
                    continue
                cur = seg[d:]; past = seg[:len(seg) - d]
                acc[d][cur] += eff[cur, act[past]]; cnt[d][cur] += 1
                stale_num[d] += int((orac[past] != orac[cur]).sum()); stale_den[d] += len(cur)
    fm = {d: np.divide(acc[d], cnt[d], out=np.full(n, np.nan), where=cnt[d] > 0) for d in DELAYS}
    valid0 = ~np.isnan(fm[0])
    rows = []
    for d in DELAYS:
        v = ~np.isnan(fm[d]); f1 = float(np.nanmean(fm[d]))
        if d == 0:
            drop, lo, hi = 0.0, 0.0, 0.0
        else:
            both = valid0 & v
            drop, lo, hi = V.paired_ci_frames_from(fm[0][both], fm[d][both])
        rows.append(dict(delay_frames=d, delay_ms=d * 100,
                         stale_decision_rate=round(stale_num[d] / max(1, stale_den[d]), 4),
                         realised_f1=round(f1, 4), f1_drop_vs_d0=round(drop, 5),
                         drop_ci_lo=round(lo, 5), drop_ci_hi=round(hi, 5),
                         drop_significant=bool(d > 0 and (lo > 0 or hi < 0))))
    return pd.DataFrame(rows)


def main():
    te = pd.read_csv(C.TEST_CSV); rf = C.load_rf(); feat = list(rf.feature_names_in_)
    cn = csi_noise(te, rf, feat); ag = aging(te, rf, feat); st = staleness(te, rf, feat)
    cn.to_csv(os.path.join(C.OUTDIR, 'robustness_csi_noise_v3.csv'), index=False)
    ag.to_csv(os.path.join(C.OUTDIR, 'robustness_aging_v3.csv'), index=False)
    st.to_csv(os.path.join(C.OUTDIR, 'robustness_staleness_v3.csv'), index=False)
    print('=== CSI noise (200-real, test) ==='); print(cn.to_string(index=False))
    print('\n=== Channel aging Jakes 60 km/h fd=%.0f Hz (200-real, test) ===' % FD); print(ag.to_string(index=False))
    print('\n=== Decision staleness (200-real, test) ==='); print(st.to_string(index=False))
    print('\nPublished 4.4.4 drops (max perturbation): csi_noise@5dB=%.4f  aging@50ms=%.4f  staleness@1frame=%.4f'
          % (cn[cn.sigma_db == 5.0].f1_drop_vs_0.iloc[0], ag[ag.delay_ms == 50].f1_drop_vs_0.iloc[0],
             st[st.delay_frames == 1].f1_drop_vs_d0.iloc[0]))


if __name__ == '__main__':
    main()
