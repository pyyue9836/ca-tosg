#self+ P0.2 unified-protocol recompute: pareto + generalisation for all 3 splits,
# CURRENT selector, 200 channel realisations (borrowed from a9_hardening.eval_seed),
# replacing the single-draw values that drift (0.0414/0.0755/0.0875). Pure eval, no training.
"""
Protocol (identical to a9_hardening): for each of N_SEED realisations, draw per-frame
SNR ~ U[0,20] and channel ~ 50/50 AWGN/Rayleigh, recompute effective F1
eff = [late_f1, comp_f1*(1-BLER16), comp_f1*(1-BLER256)] (failure->0; the ego-only
fallback is P1 step 5, not here), re-run the CURRENT RF (its CSI features change),
Fixed L/C16/C256 and the channel-aware oracle; average over seeds.

Oracle definition (channel-state-conditioned expected-utility argmax): in each realisation
the oracle picks, per frame, argmax_a of the *expected* F1 eff_a = comp_f1*(1-BLER_a(snr))
at THAT realisation's SNR + channel type -- the same channel information the deployed
selector sees (est SNR + channel type). Block success/failure is NOT sampled; it enters
only as an expectation inside eff. The oracle's only privilege over the selector is that it
knows the per-frame clean utility (late_f1/comp_f1) while the selector sees only cues -- the
standard oracle-imitation asymmetry. This is NOT a clairvoyant post-hoc bound (that would
sample the block outcome and is deferred to P1 step 5). Matches the historical single-draw
oracle (payload ~0.074, C active on ~11% of frames): per-frame and per-(frame,draw) coincide
under a single draw.

Also reported: channel-blind expected-utility policy (argmax over the channel-averaged E[eff],
fixed per frame) -- it collapses to Fixed-L (payload ~0.024), quantifying the policy-level
value of channel information (the +0.005-0.008 F1 and all feature activation).

VALIDATE convention: evaluated on the FULL validate split (1980 frames) INCLUDING the
selector's training frames -> in-sample. train_rf.py uses test_size=0.30 (SEED 0), so ~70%
are training frames; the in-sample accuracy inflation is small (~+0.002 vs the 30% holdout,
see PROVENANCE sanity line). Validate accuracy is therefore NOT directly comparable to the
held-out test / Culver accuracies without this note.

Outputs to a staging dir (nothing in the repo is touched):
  gs_rerun/policy_200seed/pareto_points.csv
  gs_rerun/policy_200seed/generalisation_{validate,test,culver}.csv
  gs_rerun/policy_200seed/PROVENANCE.txt
"""
import os, hashlib
import numpy as np, pandas as pd, pickle
from sklearn.model_selection import train_test_split

HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(HERE)
DATA = os.path.join(P1, 'data'); OUT = os.path.join(P1, 'gs_rerun/policy_200seed')
BLER = pd.read_csv(os.path.join(P1, 'results/ldpc_qam_bler_table.csv'))
RF_PKL = os.path.join(DATA, 'selector_rf.pkl')
N_SEED = 200
PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}
ACTIONS = ['L', 'C16', 'C256']
PAYVEC = np.array([PAYLOAD[a] for a in ACTIONS])


def _awgn(snr, qam):
    s = BLER[BLER.qam == qam].sort_values('snr_db')
    return np.clip(np.interp(snr, s.snr_db, s.bler, left=1., right=0.), 0, 1)

def _ray_grid(qam, grid):
    s = BLER[BLER.qam == qam].sort_values('snr_db'); xs, ys = s.snr_db.to_numpy(), s.bler.to_numpy()
    gd = np.linspace(-15, 40, 400); gl = 10 ** (gd / 10); blg = np.clip(np.interp(gd, xs, ys, left=1, right=0), 0, 1)
    out = np.empty(len(grid))
    for i, gmb in enumerate(grid):
        gb = 10 ** (gmb / 10); pdf = (1 / gb) * np.exp(-gl / gb)
        out[i] = np.clip(np.trapz(blg * pdf * (gl * np.log(10) / 10), gd), 0, 1)
    return out

_GRID = np.linspace(0, 20, 401)
_RAY = {q: _ray_grid(q, _GRID) for q in (16, 256)}
def _ray(snr, qam): return np.interp(snr, _GRID, _RAY[qam])


def eval_split(df, rf, n_seed=N_SEED):
    n = len(df); late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy()
    feat = list(rf.feature_names_in_); acc = {a: i for i, a in enumerate(ACTIONS)}
    rec = {k: [] for k in ('f1_rf', 'pay_rf', 'f1_or', 'pay_or', 'f1_L', 'f1_C16', 'f1_C256', 'acc')}
    eff_sum = np.zeros((n, 3))                      # for channel-blind E[eff]
    base = np.zeros(3)                              # oracle action counts (frame x realisation)
    for s in range(n_seed):
        rng = np.random.default_rng(s)
        snr = rng.uniform(0, 20, n); is_ray = rng.random(n) < 0.5
        b16 = np.where(is_ray, _ray(snr, 16), _awgn(snr, 16))
        b256 = np.where(is_ray, _ray(snr, 256), _awgn(snr, 256))
        eff = np.stack([late, comp * (1 - b16), comp * (1 - b256)], 1)
        eff_sum += eff
        d = df.copy(); d['est_snr_db'] = snr; d['channel_is_rayleigh'] = is_ray.astype(int)
        rf_i = np.array([acc[a] for a in np.asarray(rf.predict(d[feat]))])
        or_i = eff.argmax(1)
        for a in range(3): base[a] += (or_i == a).sum()
        rec['f1_rf'].append(eff[np.arange(n), rf_i].mean()); rec['pay_rf'].append(PAYVEC[rf_i].mean())
        rec['f1_or'].append(eff.max(1).mean()); rec['pay_or'].append(PAYVEC[or_i].mean())
        rec['f1_L'].append(eff[:, 0].mean())
        rec['f1_C16'].append(eff[:, 1].mean()); rec['f1_C256'].append(eff[:, 2].mean())
        rec['acc'].append((rf_i == or_i).mean())
    E = eff_sum / n_seed                            # channel-averaged expected eff
    bi = E.argmax(1)
    out = {k: (float(np.mean(v)), float(np.std(v))) for k, v in rec.items()}
    out['f1_blind'] = (float(E.max(1).mean()), 0.0); out['pay_blind'] = (float(PAYVEC[bi].mean()), 0.0)
    out['base_rate'] = {ACTIONS[a]: float(base[a] / (n * n_seed)) for a in range(3)}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rf = pickle.load(open(RF_PKL, 'rb'))
    rf_md5 = hashlib.md5(open(RF_PKL, 'rb').read()).hexdigest()
    pareto, genl = [], {}
    holdout_line = ''
    r_validate_acc = (float('nan'), 0.0)
    for split in ('validate', 'test', 'culver'):
        df = pd.read_csv(os.path.join(DATA, f'dataset_{split}.csv'))
        r = eval_split(df, rf)
        if split == 'validate':
            r_validate_acc = r['acc']
        note = ' [in-sample: full validate incl. training frames]' if split == 'validate' else ''
        print(f"\n=== {split} (n={len(df)}, {N_SEED} realisations){note} ===")
        print(f"  CA-TOSG(RF)  F1={r['f1_rf'][0]:.4f}±{r['f1_rf'][1]:.4f}  pay={r['pay_rf'][0]:.4f}±{r['pay_rf'][1]:.4f}  acc={r['acc'][0]:.4f}")
        print(f"  Oracle(ch-aware) F1={r['f1_or'][0]:.4f} pay={r['pay_or'][0]:.4f}  |  ch-blind F1={r['f1_blind'][0]:.4f} pay={r['pay_blind'][0]:.4f}")
        print(f"  Fixed L={r['f1_L'][0]:.4f} C16={r['f1_C16'][0]:.4f} C256={r['f1_C256'][0]:.4f}  |  oracle base-rate {r['base_rate']}")
        for pol, pay, f1 in [('Fixed L', PAYLOAD['L'], r['f1_L'][0]),
                             ('Fixed C16', PAYLOAD['C16'], r['f1_C16'][0]),
                             ('Fixed C256', PAYLOAD['C256'], r['f1_C256'][0]),
                             ('Channel-blind EU (->Fixed-L)', r['pay_blind'][0], r['f1_blind'][0]),
                             ('Oracle', r['pay_or'][0], r['f1_or'][0]),
                             ('CA-TOSG (RF, deployed)', r['pay_rf'][0], r['f1_rf'][0])]:
            pareto.append(dict(split=split, policy=pol, payload=round(pay, 4), f1=round(f1, 4)))
        genl[split] = [
            dict(policy='oracle_3way', accuracy=1.0, mean_payload=round(r['pay_or'][0], 4), mean_f1=round(r['f1_or'][0], 4)),
            dict(policy='rf_full', accuracy=round(r['acc'][0], 4), mean_payload=round(r['pay_rf'][0], 4), mean_f1=round(r['f1_rf'][0], 4)),
            dict(policy='channel_blind_EU', accuracy=round(r['base_rate']['L'], 4), mean_payload=round(r['pay_blind'][0], 4), mean_f1=round(r['f1_blind'][0], 4)),
            dict(policy='fixed_L', accuracy=round(r['base_rate']['L'], 4), mean_payload=PAYLOAD['L'], mean_f1=round(r['f1_L'][0], 4)),
            dict(policy='fixed_C16', accuracy=round(r['base_rate']['C16'], 4), mean_payload=round(PAYLOAD['C16'], 4), mean_f1=round(r['f1_C16'][0], 4)),
            dict(policy='fixed_C256', accuracy=round(r['base_rate']['C256'], 4), mean_payload=round(PAYLOAD['C256'], 4), mean_f1=round(r['f1_C256'][0], 4)),
        ]
    # in-sample sanity: validate 30% holdout (SEED=0) dev point, for PROVENANCE only (not a table row)
    dfv = pd.read_csv(os.path.join(DATA, 'dataset_validate.csv'))
    val_insample = [p for p in pareto if p['split'] == 'validate' and p['policy'].startswith('CA-TOSG')][0]
    _, te = train_test_split(dfv, test_size=0.30, random_state=0)
    rh = eval_split(te, rf)
    holdout_line = (
        "sanity_validate_30pct_holdout_SEED0: CA-TOSG F1=%.4f pay=%.4f acc=%.4f "
        "(vs full-1980 in-sample F1=%.4f pay=%.4f acc=%.4f); F1 gap %+.4f, acc inflation %+.4f"
        % (rh['f1_rf'][0], rh['pay_rf'][0], rh['acc'][0],
           val_insample['f1'], val_insample['payload'], r_validate_acc[0],
           val_insample['f1'] - rh['f1_rf'][0], r_validate_acc[0] - rh['acc'][0]))

    pd.DataFrame(pareto).to_csv(os.path.join(OUT, 'pareto_points.csv'), index=False)
    for sp, rows in genl.items():
        pd.DataFrame(rows).to_csv(os.path.join(OUT, f'generalisation_{sp}.csv'), index=False)
    with open(os.path.join(OUT, 'PROVENANCE.txt'), 'w') as f:
        f.write(f"rf_checkpoint_md5: {rf_md5}\nrf_path: data/selector_rf.pkl\n")
        f.write(f"channel_realisations: {N_SEED} (seeds 0..{N_SEED-1})\n")
        f.write("protocol_version: v2-200realisation-2026-07-11\n")
        f.write("protocol: per-frame SNR~U[0,20] x channel~Bernoulli(0.5 Rayleigh); "
                "eff_f1_C = comp_f1*(1-BLER_a(snr)) [expected F1; block success/failure NOT sampled, "
                "enters only as expectation; failure->0 -- ego-only fallback is P1 step 5]; "
                "BLER = results/ldpc_qam_bler_table.csv (codeword-level; P1 replaces with Sionna frame-level).\n")
        f.write("oracle: channel-state-conditioned expected-utility argmax -- per realisation, per frame, "
                "argmax_a eff_a at THAT realisation's est SNR + channel type (same channel info as the deployed "
                "selector); block outcome not sampled. Privilege over selector = knows per-frame clean utility "
                "(late_f1/comp_f1) while selector sees only cues (standard oracle-imitation asymmetry). NOT a "
                "clairvoyant post-hoc bound (deferred to P1 step 5).\n")
        f.write("oracle_aggregation: per realisation take per-frame argmax then mean over frames (per-realisation "
                "oracle F1); then mean over 200 realisations. accuracy = (RF action == oracle action) counted over "
                "frame x realisation pairs.\n")
        f.write("channel_blind_EU: argmax over the channel-averaged E[eff], fixed per frame -> collapses to "
                "Fixed-L (payload ~0.024); reported as an ablation quantifying the policy-level value of channel state.\n")
        f.write("validate_convention: FULL validate (1980 frames) INCLUDING selector training frames = in-sample "
                "(train_rf.py test_size=0.30, SEED 0). Validate accuracy NOT comparable to held-out test/Culver "
                "without this note.\n")
        f.write(holdout_line + "\n")
    print(f"\n[staging] -> {OUT}  (repo untouched)")
    print("PROVENANCE sanity:", holdout_line)


if __name__ == '__main__':
    main()
