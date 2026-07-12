#self+ CA-TOSG P1 Step-5 v3: 200-realisation policy eval on the canonical v3 protocol.
# Replaces the v2 engine (OLD codeword BLER + failure->0). v2 is frozen at main 8ab7693; this is
# the p1-phy-rebuild version. v2 and v3 numbers never share a table.
"""
V3 protocol (vs the v2 recompute this file used to hold):
  * datasets           : data/dataset_{split}_v3.csv (canonical late_f1/compressed_f1/ego_f1).
  * BLER               : Sionna FRAME-level table results/bler_sionna/bler_sionna.csv (bler_frame
                         column, Es/N0 axis) for BOTH awgn and rayleigh -- no numerical Rayleigh
                         averaging (Rayleigh frame BLER = 1 across 0-20 dB directly from the table).
  * failure fallback   : ego-only.  eff_a = comp*(1-BLER_a) + ego*BLER_a  (expected F1; the block
                         success/failure is NOT sampled for the expected-utility policies -- it enters
                         only as an expectation, exactly as in v2).
  * feasibility mask   : BLER_a >= 0.999 removes action a from the ORACLE's feasible set (label
                         semantics: an undeliverable request spends channel-use for zero info). Same
                         constraint used in make_dataset.py. lambda stays pinned = 0.

Policies evaluated per realisation (per-frame SNR~U[0,20] x channel~Bernoulli(0.5 rayleigh)):
  Fixed L / C16 / C256                     -- single actions.
  Channel-blind EU                         -- argmax over the channel-averaged E[eff]; collapses to L.
  Oracle (ch-aware, feasibility-masked)    -- per realisation per frame argmax of the EXPECTED eff at
                                              that draw's SNR+channel, C masked where BLER>=0.999.
  CA-TOSG (RF, deployed)                   -- data/selector_rf.pkl (v3-retrained) on the drawn CSI.
  SNR-threshold baseline (RE-TUNED)        -- awgn & snr>tau -> C16 else L; tau swept on a FINE grid
                                              (0.5 dB) on the NEW terrain, best tau reported per split.
                                              v2's tau in {12,14,16} is NOT reused (knee moved to ~8 dB).
  Clairvoyant upper bound (SEPARATE)       -- the ONLY policy that SAMPLES the per-frame block outcome
                                              and takes the post-hoc max over actions. Genuine upper
                                              bound; labelled distinctly from the (non-clairvoyant) oracle.

Outputs (staging gs_rerun/policy_200seed_v3/; nothing in the repo tree touched):
  pareto_points.csv, generalisation_{validate,test,culver}.csv,
  threshold_sweep_{validate,test,culver}.csv, action_dist_20dB.csv, PROVENANCE.txt
"""
import os, hashlib
import numpy as np, pandas as pd, pickle

HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(HERE)
DATA = os.path.join(P1, 'data'); OUT = os.path.join(P1, 'gs_rerun/policy_200seed_v3')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
RF_PKL = os.path.join(DATA, 'selector_rf.pkl')
N_SEED = 200
PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}
ACTIONS = ['L', 'C16', 'C256']
PAYVEC = np.array([PAYLOAD[a] for a in ACTIONS])
BLER_INFEASIBLE = 0.999
TAU_GRID = np.round(np.arange(0.0, 20.0001, 0.5), 3)   # fine-grid SNR-threshold retune
LAMS = np.concatenate([[0.0], np.geomspace(1e-3, 5.0, 40)])  # Lagrangian frontier (200-real averaged)
N_BOOT = 5000                                           # paired bootstrap over realisations
BOOT_SEED = 12345

_TBL = pd.read_csv(BLER_CSV)
def _bler(qam, channel):
    s = _TBL[(_TBL.qam == qam) & (_TBL.channel == channel)].sort_values('esno_db')
    return s.esno_db.to_numpy(), s.bler_frame.to_numpy()
_B = {(q, c): _bler(q, c) for q in (16, 256) for c in ('awgn', 'rayleigh')}
def bler_frame(snr, qam, channel):
    xs, ys = _B[(qam, channel)]
    return np.clip(np.interp(snr, xs, ys, left=1.0, right=float(ys[-1])), 0.0, 1.0)


def eval_split(df, rf, n_seed=N_SEED):
    n = len(df)
    late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy()
    ego = df['ego_f1'].to_numpy()
    feat = list(rf.feature_names_in_); acc = {a: i for i, a in enumerate(ACTIONS)}
    keys = ('f1_rf', 'pay_rf', 'f1_or', 'pay_or', 'f1_L', 'f1_C16', 'f1_C256',
            'acc', 'f1_clair', 'pay_clair')
    rec = {k: [] for k in keys}
    tau_f1 = {t: [] for t in TAU_GRID}; tau_pay = {t: [] for t in TAU_GRID}
    # Lagrangian frontier accumulators (200-realisation averaged; same masked-argmax machinery
    # as the oracle row, just with a lambda*payload penalty). Per-lambda sums over realisations.
    fr_f1 = np.zeros(len(LAMS)); fr_pay = np.zeros(len(LAMS))
    fr_c256 = np.zeros(len(LAMS)); fr_c16 = np.zeros(len(LAMS)); fr_l = np.zeros(len(LAMS))
    eff_sum = np.zeros((n, 3)); base = np.zeros(3)
    # per-FRAME realised-eff accumulators (for the frame-level paired bootstrap -- the frame/scene
    # is the generalisation unit; channel realisations are averaged out as an MC nuisance).
    rf_framesum = np.zeros(n); tau_framesum = {t: np.zeros(n) for t in TAU_GRID}
    for s in range(n_seed):
        rng = np.random.default_rng(s)
        snr = rng.uniform(0, 20, n); is_ray = rng.random(n) < 0.5
        b16 = np.where(is_ray, bler_frame(snr, 16, 'rayleigh'), bler_frame(snr, 16, 'awgn'))
        b256 = np.where(is_ray, bler_frame(snr, 256, 'rayleigh'), bler_frame(snr, 256, 'awgn'))
        eff = np.stack([late, comp * (1 - b16) + ego * b16,
                        comp * (1 - b256) + ego * b256], axis=1)   # EXPECTED eff
        eff_sum += eff

        # oracle: feasibility-masked expected-utility argmax
        masked = eff.copy()
        masked[b16 >= BLER_INFEASIBLE, 1] = -np.inf
        masked[b256 >= BLER_INFEASIBLE, 2] = -np.inf
        or_i = masked.argmax(1)
        for a in range(3): base[a] += (or_i == a).sum()

        # deployed RF on drawn CSI
        d = df.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = is_ray.astype(int)
        rf_i = np.array([acc[a] for a in np.asarray(rf.predict(d[feat]))])

        rf_framesum += eff[np.arange(n), rf_i]
        rec['f1_rf'].append(eff[np.arange(n), rf_i].mean()); rec['pay_rf'].append(PAYVEC[rf_i].mean())
        rec['f1_or'].append(eff[np.arange(n), or_i].mean()); rec['pay_or'].append(PAYVEC[or_i].mean())
        rec['f1_L'].append(eff[:, 0].mean())
        rec['f1_C16'].append(eff[:, 1].mean()); rec['f1_C256'].append(eff[:, 2].mean())
        rec['acc'].append((rf_i == or_i).mean())

        # SNR-threshold baseline sweep (awgn & snr>tau -> C16 else L)
        awgn = ~is_ray
        for t in TAU_GRID:
            ti = np.where(awgn & (snr > t), 1, 0)     # 1=C16, 0=L
            te = eff[np.arange(n), ti]
            tau_f1[t].append(te.mean()); tau_pay[t].append(PAYVEC[ti].mean()); tau_framesum[t] += te

        # clairvoyant upper bound: SAMPLE the block outcome, post-hoc max over actions
        succ16 = rng.random(n) > b16; succ256 = rng.random(n) > b256
        real = np.stack([late,
                         np.where(succ16, comp, ego),
                         np.where(succ256, comp, ego)], axis=1)
        cl_i = real.argmax(1)
        rec['f1_clair'].append(real[np.arange(n), cl_i].mean()); rec['pay_clair'].append(PAYVEC[cl_i].mean())

        # Lagrangian frontier (feasibility-masked argmax of eff - lam*payload), this realisation
        mask_inf = np.zeros((n, 3)); mask_inf[b16 >= BLER_INFEASIBLE, 1] = -np.inf
        mask_inf[b256 >= BLER_INFEASIBLE, 2] = -np.inf
        for li, lam in enumerate(LAMS):
            obj = eff - lam * PAYVEC[None, :] + mask_inf
            fi = obj.argmax(1)
            fr_f1[li] += eff[np.arange(n), fi].mean(); fr_pay[li] += PAYVEC[fi].mean()
            fr_c256[li] += (fi == 2).mean(); fr_c16[li] += (fi == 1).mean(); fr_l[li] += (fi == 0).mean()

    E = eff_sum / n_seed; bi = E.argmax(1)
    out = {k: (float(np.mean(v)), float(np.std(v))) for k, v in rec.items()}
    out['f1_blind'] = (float(E[np.arange(n), bi].mean()), 0.0)
    out['pay_blind'] = (float(PAYVEC[bi].mean()), 0.0)
    out['base_rate'] = {ACTIONS[a]: float(base[a] / (n * n_seed)) for a in range(3)}
    tau_tab = [(float(t), float(np.mean(tau_f1[t])), float(np.mean(tau_pay[t]))) for t in TAU_GRID]
    out['tau_tab'] = tau_tab
    out['best_tau'] = max(tau_tab, key=lambda r: r[1])   # (tau, f1, payload)
    out['frontier'] = [dict(lam=round(float(LAMS[i]), 5),
                            payload=round(float(fr_pay[i] / n_seed), 4),
                            f1=round(float(fr_f1[i] / n_seed), 4),
                            frac_C256=round(float(fr_c256[i] / n_seed), 5),
                            frac_C16=round(float(fr_c16[i] / n_seed), 5),
                            frac_L=round(float(fr_l[i] / n_seed), 5)) for i in range(len(LAMS))]
    # per-FRAME mean realised eff (averaged over realisations) for RF and each tau -> frame-level
    # paired bootstrap (the honest generalisation test; the frame/scene is the iid unit).
    out['rf_framemean'] = rf_framesum / n_seed
    out['tau_framemean'] = {float(t): tau_framesum[t] / n_seed for t in TAU_GRID}
    # raw per-realisation series (realisation-level CI = MC precision of the channel average, kept
    # only as a diagnostic; NOT the generalisation test).
    out['f1_rf_series'] = np.asarray(rec['f1_rf'])
    out['tau_f1_series'] = {float(t): np.asarray(tau_f1[t]) for t in TAU_GRID}
    return out


def paired_ci_frames(rf_fm, tau_fm, n_boot=N_BOOT):
    """95% percentile bootstrap CI of the mean paired difference (RF - tau) resampling FRAMES --
    the scene population is the generalisation unit; channel realisations are averaged out first."""
    d = rf_fm - tau_fm
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi)


def paired_ci_reals(rf_series, tau_series, n_boot=N_BOOT):
    """Diagnostic only: CI resampling REALISATIONS (MC precision of the channel average, not a
    generalisation test -- gives a spuriously tight interval)."""
    d = rf_series - tau_series
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi)


def action_dist_20db(df, rf, split):
    """Selector vs oracle action distribution at the 20 dB edge (both channels) -- selector
    extrapolation check now that the knee has moved to ~8 dB."""
    feat = list(rf.feature_names_in_); rows = []
    for ch in ('awgn', 'rayleigh'):
        snr = 20.0
        b16 = float(bler_frame(np.array([snr]), 16, ch)[0]); b256 = float(bler_frame(np.array([snr]), 256, ch)[0])
        late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy(); ego = df['ego_f1'].to_numpy()
        eff = np.stack([late, comp * (1 - b16) + ego * b16, comp * (1 - b256) + ego * b256], axis=1)
        masked = eff.copy()
        if b16 >= BLER_INFEASIBLE: masked[:, 1] = -np.inf
        if b256 >= BLER_INFEASIBLE: masked[:, 2] = -np.inf
        or_a = np.array(ACTIONS)[masked.argmax(1)]
        d = df.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = int(ch == 'rayleigh')
        rf_a = np.asarray(rf.predict(d[feat]))
        for who, a in (('oracle', or_a), ('selector', rf_a)):
            rows.append(dict(split=split, channel=ch, snr_db=snr, who=who,
                             frac_L=round(float((a == 'L').mean()), 4),
                             frac_C16=round(float((a == 'C16').mean()), 4),
                             frac_C256=round(float((a == 'C256').mean()), 4),
                             agree_with_oracle=round(float((rf_a == or_a).mean()), 4) if who == 'selector' else 1.0))
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    rf = pickle.load(open(RF_PKL, 'rb'))
    rf_md5 = hashlib.md5(open(RF_PKL, 'rb').read()).hexdigest()
    pareto, genl, dist20, tvr, c256_bands = [], {}, [], [], []
    ds_md5 = {}
    for split in ('validate', 'test', 'culver'):
        path = os.path.join(DATA, f'dataset_{split}_v3.csv')
        df = pd.read_csv(path); ds_md5[split] = hashlib.md5(open(path, 'rb').read()).hexdigest()
        r = eval_split(df, rf)
        bt_tau, bt_f1, bt_pay = r['best_tau']
        note = ' [in-sample: full validate incl. training frames]' if split == 'validate' else ''
        print(f"\n=== {split} (n={len(df)}, {N_SEED} realisations){note} ===")
        print(f"  CA-TOSG(RF)   F1={r['f1_rf'][0]:.4f}+-{r['f1_rf'][1]:.4f}  pay={r['pay_rf'][0]:.4f}  acc={r['acc'][0]:.4f}")
        print(f"  Oracle(mask)  F1={r['f1_or'][0]:.4f}  pay={r['pay_or'][0]:.4f}   | ch-blind F1={r['f1_blind'][0]:.4f} pay={r['pay_blind'][0]:.4f}")
        print(f"  Clairvoyant   F1={r['f1_clair'][0]:.4f}  pay={r['pay_clair'][0]:.4f}  (samples block outcome, post-hoc max)")
        print(f"  Best-tau SNR  tau={bt_tau:.1f}  F1={bt_f1:.4f}  pay={bt_pay:.4f}")
        print(f"  Fixed L={r['f1_L'][0]:.4f} C16={r['f1_C16'][0]:.4f} C256={r['f1_C256'][0]:.4f}  | oracle base-rate {r['base_rate']}")

        for pol, pay, f1 in [('Fixed L', PAYLOAD['L'], r['f1_L'][0]),
                             ('Fixed C16', PAYLOAD['C16'], r['f1_C16'][0]),
                             ('Fixed C256', PAYLOAD['C256'], r['f1_C256'][0]),
                             ('Channel-blind EU (->Fixed-L)', r['pay_blind'][0], r['f1_blind'][0]),
                             ('SNR-threshold (best tau)', bt_pay, bt_f1),
                             ('CA-TOSG (RF, deployed)', r['pay_rf'][0], r['f1_rf'][0]),
                             ('Oracle (ch-aware, masked)', r['pay_or'][0], r['f1_or'][0]),
                             ('Clairvoyant (post-hoc, samples block)', r['pay_clair'][0], r['f1_clair'][0])]:
            pareto.append(dict(split=split, policy=pol, payload=round(pay, 4), f1=round(f1, 4)))

        genl[split] = [
            dict(policy='oracle_masked', accuracy=1.0, mean_payload=round(r['pay_or'][0], 4), mean_f1=round(r['f1_or'][0], 4)),
            dict(policy='clairvoyant_upper', accuracy=float('nan'), mean_payload=round(r['pay_clair'][0], 4), mean_f1=round(r['f1_clair'][0], 4)),
            dict(policy='rf_full', accuracy=round(r['acc'][0], 4), mean_payload=round(r['pay_rf'][0], 4), mean_f1=round(r['f1_rf'][0], 4)),
            dict(policy=f'snr_threshold_best(tau={bt_tau:.1f})', accuracy=float('nan'), mean_payload=round(bt_pay, 4), mean_f1=round(bt_f1, 4)),
            dict(policy='channel_blind_EU', accuracy=round(r['base_rate']['L'], 4), mean_payload=round(r['pay_blind'][0], 4), mean_f1=round(r['f1_blind'][0], 4)),
            dict(policy='fixed_L', accuracy=round(r['base_rate']['L'], 4), mean_payload=PAYLOAD['L'], mean_f1=round(r['f1_L'][0], 4)),
            dict(policy='fixed_C16', accuracy=round(r['base_rate']['C16'], 4), mean_payload=round(PAYLOAD['C16'], 4), mean_f1=round(r['f1_C16'][0], 4)),
            dict(policy='fixed_C256', accuracy=round(r['base_rate']['C256'], 4), mean_payload=round(PAYLOAD['C256'], 4), mean_f1=round(r['f1_C256'][0], 4)),
        ]
        pd.DataFrame([dict(split=split, tau=t, f1=round(f1, 4), payload=round(p, 4))
                      for (t, f1, p) in r['tau_tab']]).to_csv(
            os.path.join(OUT, f'threshold_sweep_{split}.csv'), index=False)
        dist20 += action_dist_20db(df, rf, split)

        # --- frontier (200-realisation averaged) + C256 lambda-band -> payload region ---
        fr = r['frontier']
        pd.DataFrame(fr).to_csv(os.path.join(OUT, f'frontier_{split}.csv'), index=False)
        c256_on = [row for row in fr if row['frac_C256'] > 0.0]
        if c256_on:
            c256_band = dict(split=split,
                             max_frac_C256=round(max(row['frac_C256'] for row in fr), 5),
                             lam_lo=min(row['lam'] for row in c256_on),
                             lam_hi=max(row['lam'] for row in c256_on),
                             payload_lo=round(min(row['payload'] for row in c256_on), 4),
                             payload_hi=round(max(row['payload'] for row in c256_on), 4))
        else:
            c256_band = dict(split=split, max_frac_C256=0.0, lam_lo=None, lam_hi=None,
                             payload_lo=None, payload_hi=None)
        c256_bands.append(c256_band)

        # --- RF vs tau-frontier Pareto fairness (the central finding, honest) ---
        rf_pay, rf_f1 = r['pay_rf'][0], r['f1_rf'][0]
        # (a) best tau-F1 achievable at payload <= RF payload (same-or-less bandwidth)
        le = [(t, f1, p) for (t, f1, p) in r['tau_tab'] if p <= rf_pay + 1e-9]
        tau_at_rf = max(le, key=lambda x: x[1]) if le else (None, None, None)
        # (b) does ANY tau point Pareto-dominate RF (>= F1 AND <= payload, strict in one)?
        dom = [(t, f1, p) for (t, f1, p) in r['tau_tab']
               if f1 >= rf_f1 - 1e-9 and p <= rf_pay - 1e-9] + \
              [(t, f1, p) for (t, f1, p) in r['tau_tab']
               if f1 >= rf_f1 + 1e-9 and p <= rf_pay + 1e-9]
        bt_tau, bt_f1, bt_pay = r['best_tau']
        # (c) paired bootstrap 95% CI of RF - tau@matched-payload
        #     PRIMARY = frame-level (scene = generalisation unit); diagnostic = realisation-level.
        if tau_at_rf[0] is not None:
            dmean, dlo, dhi = paired_ci_frames(r['rf_framemean'], r['tau_framemean'][tau_at_rf[0]])
            rmean, rlo, rhi = paired_ci_reals(r['f1_rf_series'], r['tau_f1_series'][tau_at_rf[0]])
            sig = (dlo > 0) or (dhi < 0)
        else:
            dmean = dlo = dhi = rmean = rlo = rhi = float('nan'); sig = False
        tvr.append(dict(
            split=split, rf_payload=round(rf_pay, 4), rf_f1=round(rf_f1, 4),
            bestF1_tau=bt_tau, bestF1_tau_f1=round(bt_f1, 4), bestF1_tau_payload=round(bt_pay, 4),
            tau_at_rf_payload=(round(tau_at_rf[0], 1) if tau_at_rf[0] is not None else None),
            tau_at_rf_payload_f1=(round(tau_at_rf[1], 4) if tau_at_rf[1] is not None else None),
            tau_at_rf_payload_payload=(round(tau_at_rf[2], 4) if tau_at_rf[2] is not None else None),
            rf_dominates_tau_frontier=(len(dom) == 0),
            rf_minus_tau_at_rf_payload_f1=round(dmean, 5),
            frame_ci95_lo=round(dlo, 5), frame_ci95_hi=round(dhi, 5), significant_frame=sig,
            realisation_ci95_lo=round(rlo, 5), realisation_ci95_hi=round(rhi, 5)))

    pd.DataFrame(pareto).to_csv(os.path.join(OUT, 'pareto_points.csv'), index=False)
    for sp, rows in genl.items():
        pd.DataFrame(rows).to_csv(os.path.join(OUT, f'generalisation_{sp}.csv'), index=False)
    pd.DataFrame(dist20).to_csv(os.path.join(OUT, 'action_dist_20dB.csv'), index=False)
    pd.DataFrame(tvr).to_csv(os.path.join(OUT, 'threshold_vs_rf.csv'), index=False)
    pd.DataFrame(c256_bands).to_csv(os.path.join(OUT, 'c256_frontier_band.csv'), index=False)
    print('\n=== 20 dB selector-vs-oracle action distribution ===')
    print(pd.DataFrame(dist20).to_string(index=False))
    print('\n=== RF vs re-tuned SNR-threshold @matched payload (PRIMARY: frame-level paired 95% CI) ===')
    print(pd.DataFrame(tvr)[['split', 'rf_payload', 'rf_f1', 'tau_at_rf_payload', 'tau_at_rf_payload_f1',
                             'rf_minus_tau_at_rf_payload_f1', 'frame_ci95_lo', 'frame_ci95_hi',
                             'significant_frame', 'realisation_ci95_lo', 'realisation_ci95_hi']].to_string(index=False))
    print('\n=== C256 activation band on the 200-realisation Lagrangian frontier ===')
    print(pd.DataFrame(c256_bands).to_string(index=False))

    with open(os.path.join(OUT, 'PROVENANCE.txt'), 'w') as f:
        f.write("CA-TOSG P1 Step-5 v3 200-realisation policy eval\n")
        f.write(f"rf_checkpoint_md5: {rf_md5}  rf_path: data/selector_rf.pkl (v3-retrained)\n")
        for sp in ('validate', 'test', 'culver'):
            f.write(f"dataset_{sp}_v3_md5: {ds_md5[sp]}\n")
        f.write(f"channel_realisations: {N_SEED} (seeds 0..{N_SEED-1}); protocol_version: v3-P1-2026-07-12\n")
        f.write("BLER: results/bler_sionna/bler_sionna.csv (frame-level bler_frame, Es/N0); "
                "awgn+rayleigh direct table lookup (Rayleigh frame BLER=1 across 0-20 dB, no numerical avg).\n")
        f.write("eff_a = comp*(1-BLER_a) + ego*BLER_a (ego-only fallback; expected F1, block NOT sampled).\n")
        f.write("oracle: channel-state-conditioned expected-utility argmax, feasibility mask "
                f"BLER>=%.3f removes C from the feasible set. lambda pinned = 0.\n" % BLER_INFEASIBLE)
        f.write("SNR-threshold baseline RE-TUNED on the v3 terrain: awgn & snr>tau -> C16 else L; "
                f"tau grid {TAU_GRID[0]}..{TAU_GRID[-1]} step 0.5 dB; best tau = argmax mean realised F1 "
                "per split (v2's tau in {12,14,16} NOT reused -- the frame cliff moved to ~8 dB).\n")
        f.write("clairvoyant_upper: the ONLY policy that SAMPLES the per-frame block success/failure "
                "(succ_a ~ Bernoulli(1-BLER_a)) and takes the post-hoc max over actions of the realised F1 "
                "(L->late, C-success->comp, C-fail->ego). Genuine post-hoc upper bound, separate from the oracle.\n")
        f.write("validate = FULL 1980 frames incl. selector training frames (in-sample; not comparable to "
                "held-out test/culver without this note).\n")
    print(f"\n[staging] -> {OUT}  (repo untouched)")


if __name__ == '__main__':
    main()
