#self+ A9: statistical hardening -- multi-seed CIs, bandwidth efficiency, hard-frame significance
# DEPRECATED (P1 Step-5, supervisor 2026-07-12): its role -- multi-seed CIs / hard-frame significance --
# is now ABSORBED by the 200-realisation engine (recompute_policy_200seed.py) and v3_eval.py, which
# carry frame-level paired bootstrap CIs directly. Keeping A9 alive only manufactures a SECOND,
# conflicting set of "hardening" numbers. Do NOT run or cite. Kept for history only.
"""
Three cheap robustness checks (all from cached per-frame CSVs, no GPU):

(1) Multi-seed CIs: re-draw the random per-frame SNR (U[0,20]) and channel (50/50
    AWGN/Rayleigh) for N seeds; for each, recompute the effective F1 and re-run the
    deployed RF (its CSI inputs change), Fixed-L, the channel-aware oracle, and the
    best SNR-threshold rule. Report mean +/- 95% CI over seeds.

(2) Bandwidth efficiency at matched F1: from the seed-averaged threshold payload-F1
    curve, find the payload the SNR-threshold rule needs to MATCH the RF's mean F1,
    and report how much more bandwidth that is than the RF.

(3) Hard-frame gain significance: on hard frames (bottom late-F1 tercile) under a
    usable channel (AWGN, SNR>=14 dB), bootstrap the per-frame (RF - Fixed-L)
    effective-F1 gain; report mean and 95% CI (significant if CI excludes 0).

Output: out/a9_hardening.csv
"""
import os
import numpy as np
import pandas as pd
import _common as C

BLER = pd.read_csv(os.path.join(C.REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv'))
N_SEED = 200
N_BOOT = 2000


def bler_awgn(snr, qam):
    sub = BLER[BLER['qam'] == qam].sort_values('snr_db')
    return np.clip(np.interp(snr, sub['snr_db'], sub['bler'], left=1.0, right=0.0), 0, 1)


def bler_rayleigh(snr_mean, qam, n=240):
    sub = BLER[BLER['qam'] == qam].sort_values('snr_db')
    xs, ys = sub['snr_db'].to_numpy(), sub['bler'].to_numpy()
    gd = np.linspace(-15, 40, n); gl = 10 ** (gd / 10); blg = np.clip(np.interp(gd, xs, ys, left=1, right=0), 0, 1)
    out = np.empty(len(snr_mean))
    for i, gmb in enumerate(snr_mean):
        gb = 10 ** (gmb / 10); pdf = (1 / gb) * np.exp(-gl / gb)
        out[i] = np.clip(np.trapz(blg * pdf * (gl * np.log(10) / 10), gd), 0, 1)
    return out


def eval_seed(df, rf, rng, taus):
    n = len(df)
    snr = rng.uniform(0, 20, n)
    is_ray = rng.random(n) < 0.5
    b16 = np.where(is_ray, bler_rayleigh(snr, 16), bler_awgn(snr, 16))
    b256 = np.where(is_ray, bler_rayleigh(snr, 256), bler_awgn(snr, 256))
    late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy()
    eff = np.stack([late, comp * (1 - b16), comp * (1 - b256)], 1)
    pay = np.array([C.PAYLOAD['L'], C.PAYLOAD['C16'], C.PAYLOAD['C256']])

    d = df.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = is_ray.astype(int)
    rf_a = np.asarray(rf.predict(d[rf.feature_names_in_]))
    ai = {a: i for i, a in enumerate(C.ACTIONS)}
    rf_i = np.array([ai[a] for a in rf_a])
    f1_rf = eff[np.arange(n), rf_i].mean(); pay_rf = pay[rf_i].mean()
    f1_or = eff.max(1).mean(); pay_or = pay[eff.argmax(1)].mean()
    f1_L = eff[:, 0].mean()
    # threshold sweep
    tcurve = []
    for t in taus:
        ti = np.where((~is_ray) & (snr > t), 1, 0)  # C16 if awgn & snr>t else L
        tcurve.append((pay[ti].mean(), eff[np.arange(n), ti].mean()))
    return dict(f1_rf=f1_rf, pay_rf=pay_rf, f1_or=f1_or, f1_L=f1_L,
                gain=f1_rf - f1_L), np.array(tcurve)


def main():
    df = pd.read_csv(C.TEST_CSV)
    rf = C.load_rf()
    taus = np.arange(0, 21, 1.0)
    rng = np.random.default_rng(0)

    recs = []; tcurves = []
    for s in range(N_SEED):
        r, tc = eval_seed(df, rf, np.random.default_rng(s), taus)
        recs.append(r); tcurves.append(tc)
    R = pd.DataFrame(recs); T = np.array(tcurves)  # (seed, tau, [pay,f1])

    def ci(x): return (np.mean(x), np.percentile(x, 2.5), np.percentile(x, 97.5))
    rows = []
    for k in ['f1_rf', 'pay_rf', 'f1_or', 'f1_L', 'gain']:
        m, lo, hi = ci(R[k]); rows.append(dict(metric=k, mean=round(m, 4),
                    ci_lo=round(lo, 4), ci_hi=round(hi, 4)))
    # SNR-threshold rule at fixed tau, same 200-seed protocol as the RF, so it
    # carries a matched CI (no RF-with-CI vs threshold-single-point asymmetry).
    for tau_fixed in (12, 16):
        ti = int(np.where(taus == tau_fixed)[0][0])
        for lbl, col in (('f1_thr%d' % tau_fixed, 1), ('pay_thr%d' % tau_fixed, 0)):
            m, lo, hi = ci(T[:, ti, col]); rows.append(dict(metric=lbl,
                        mean=round(m, 4), ci_lo=round(lo, 4), ci_hi=round(hi, 4)))
    out = pd.DataFrame(rows)

    # (2) bandwidth efficiency at matched F1
    Tm = T.mean(0)  # (tau,[pay,f1]) seed-averaged
    rf_f1 = R['f1_rf'].mean(); rf_pay = R['pay_rf'].mean()
    # interpolate threshold payload at F1 == rf_f1 (threshold F1 increases as tau decreases)
    order = np.argsort(Tm[:, 1])
    thr_pay_at_rf_f1 = float(np.interp(rf_f1, Tm[order, 1], Tm[order, 0]))

    # (3) hard-frame + good-channel bootstrap (fixed canonical channel draw)
    hard = df['late_f1'] <= df['late_f1'].quantile(1/3)
    good = (df['channel_type'] == 'awgn') & (df['est_snr_db'] >= 14)
    sub = df[hard & good]
    rf_a = np.asarray(C.rf_predict(rf, sub))
    effC16 = sub['compressed_f1'].to_numpy() * (1 - sub['bler_C16'].to_numpy())
    effL = sub['late_f1'].to_numpy()
    per = np.where(rf_a == 'L', effL, effC16) - effL  # RF eff - L eff per frame
    bm = np.array([per[np.random.default_rng(b).integers(0, len(per), len(per))].mean()
                   for b in range(N_BOOT)])
    g_mean, g_lo, g_hi = per.mean(), np.percentile(bm, 2.5), np.percentile(bm, 97.5)

    out.to_csv(os.path.join(C.OUTDIR, 'a9_hardening.csv'), index=False)
    print('=== (1) multi-seed CIs (OPV2V test, %d seeds, 95%% CI) ===' % N_SEED)
    print(out.to_string())
    print('\n=== (2) bandwidth efficiency at matched F1 ===')
    print(f'  RF: F1={rf_f1:.4f} at payload={rf_pay:.4f}')
    print(f'  SNR-threshold needs payload={thr_pay_at_rf_f1:.4f} to match that F1 '
          f'=> RF uses {thr_pay_at_rf_f1/rf_pay:.1f}x less bandwidth at equal F1')
    print('\n=== (3) hard+good-channel gain significance (n=%d frames, %d boot) ===' % (len(sub), N_BOOT))
    print(f'  mean RF-over-L gain = {g_mean:+.4f}  95%% CI [{g_lo:+.4f}, {g_hi:+.4f}]  '
          f'{"SIGNIFICANT (CI excludes 0)" if g_lo > 0 else "not significant"}')


if __name__ == '__main__':
    main()
