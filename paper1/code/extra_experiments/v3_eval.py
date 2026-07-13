#self+ CA-TOSG P1 Step-5: shared 200-realisation evaluator for the ablation experiments (a2/a7/a8/
# robustness). Any number that may appear in the paper MUST go through this (200 realisations + v3 GT
# + Sionna frame BLER + ego fallback); single-frozen-draw eval is DIAGNOSTIC-ONLY.
"""
Mirrors recompute_policy_200seed.py exactly: per realisation draw per-frame SNR~U[0,20] and
channel~Bernoulli(0.5 rayleigh), Sionna frame-level BLER (bler_frame), ego-only fallback
eff_a = comp*(1-BLER_a) + ego*BLER_a, feasibility mask (BLER>=0.999) for the oracle label. The RF is
trained ONCE on the frozen v3 oracle_3way labels (the labels are fixed); only the EVALUATION is
200-realisation. Returns per-realisation frame-mean F1 (so callers get a proper paired series).
"""
import os
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_P1 = os.path.dirname(os.path.dirname(_HERE))
BLER_CSV = os.path.join(_P1, 'results/bler_sionna/bler_sionna.csv')
# Channel USES per frame (Msymbols) at rate-1/2: info bits / coderate / bits_per_symbol. The modulator
# carries the CODED stream (rate-1/2 -> 2x info bits), so C16 = 1.98/0.5/4 = 0.99, C256 = 1.98/0.5/8 =
# 0.495, L = 0.024/0.5/2 (QPSK) = 0.024. (The earlier 1.98/4=0.495 was the UNCODED symbol count -- wrong
# for the rate-1/2 chain used throughout + the Sionna table; corrected 2026-07-12 per supervisor.)
PAYLOAD = {'L': 0.024, 'C16': 0.99, 'C256': 0.495}
ACTIONS = ['L', 'C16', 'C256']
PAYVEC = np.array([PAYLOAD[a] for a in ACTIONS])
BLER_INFEASIBLE = 0.999
N_SEED = 200

_TBL = pd.read_csv(BLER_CSV)
# OFDM rows live in a separate file until the supervisor reviews the curve (PROVENANCE_ofdm.txt) --
# concat them here so 'ofdm' is available for the two-regime edge WITHOUT overwriting the canonical table.
_OFDM = os.path.join(os.path.dirname(BLER_CSV), 'bler_sionna_ofdm.csv')
if os.path.exists(_OFDM):
    _TBL = pd.concat([_TBL, pd.read_csv(_OFDM)], ignore_index=True)
_CHS = tuple(sorted(_TBL.channel.unique()))
_B = {(q, c): (_TBL[(_TBL.qam == q) & (_TBL.channel == c)].sort_values('esno_db').esno_db.to_numpy(),
               _TBL[(_TBL.qam == q) & (_TBL.channel == c)].sort_values('esno_db').bler_frame.to_numpy())
      for q in (16, 256) for c in _CHS}


def _bler(snr, qam, ch):
    xs, ys = _B[(qam, ch)]
    return np.clip(np.interp(snr, xs, ys, left=1.0, right=float(ys[-1])), 0.0, 1.0)


def draws(n, seed):
    rng = np.random.default_rng(seed)
    snr = rng.uniform(0, 20, n); is_ray = rng.random(n) < 0.5
    b16 = np.where(is_ray, _bler(snr, 16, 'rayleigh'), _bler(snr, 16, 'awgn'))
    b256 = np.where(is_ray, _bler(snr, 256, 'rayleigh'), _bler(snr, 256, 'awgn'))
    return snr, is_ray, b16, b256


def eff_of(df, b16, b256):
    late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy(); ego = df['ego_f1'].to_numpy()
    return np.stack([late, comp * (1 - b16) + ego * b16, comp * (1 - b256) + ego * b256], axis=1)


def masked_oracle(eff, b16, b256):
    m = eff.copy()
    m[b16 >= BLER_INFEASIBLE, 1] = -np.inf
    m[b256 >= BLER_INFEASIBLE, 2] = -np.inf
    return m.argmax(1)


def eval_series(df, policy, feat=None, model=None, n_seed=N_SEED, mask=None, csi_noise_sigma=0.0):
    """Return per-realisation frame-mean (f1, payload) arrays for a policy over 200 realisations.
    policy: 'rf' (needs model with .predict + feat), 'oracle', 'fixedL'/'C16'/'C256', or 'threshold:TAU'.
    mask: optional boolean over frames to restrict the reported mean (stratum analysis).
    csi_noise_sigma: if >0, the SELECTOR sees est_snr = true_snr + N(0,sigma) dB (robustness: CSI
    estimation noise / Jakes aging). The channel does not lie -- eff still uses the TRUE snr's BLER;
    only the RF's input est_snr is perturbed."""
    n = len(df)
    sel = np.ones(n, bool) if mask is None else np.asarray(mask, bool)
    f1s, pays = [], []
    for s in range(n_seed):
        snr, is_ray, b16, b256 = draws(n, s)
        eff = eff_of(df, b16, b256)
        if policy == 'rf':
            d = df.copy()
            est = snr if csi_noise_sigma <= 0 else snr + np.random.default_rng(s + 10000).normal(0, csi_noise_sigma, n)
            d['est_snr_db'] = est; d['channel_is_rayleigh'] = is_ray.astype(int)
            idx = np.array([ACTIONS.index(a) for a in np.asarray(model.predict(d[feat]))])
        elif policy == 'oracle':
            idx = masked_oracle(eff, b16, b256)
        elif policy.startswith('fixed'):
            idx = np.full(n, ACTIONS.index(policy.replace('fixed', '')))
        elif policy.startswith('threshold:'):
            tau = float(policy.split(':')[1]); idx = np.where((~is_ray) & (snr > tau), 1, 0)
        else:
            raise ValueError(policy)
        f1s.append(eff[np.arange(n), idx][sel].mean()); pays.append(PAYVEC[idx][sel].mean())
    return np.asarray(f1s), np.asarray(pays)


def summ(f1s, pays):
    return dict(mean_f1=round(float(f1s.mean()), 4), std_f1=round(float(f1s.std()), 4),
               mean_payload=round(float(pays.mean()), 4))


def paired_ci_frames_from(df_a_framemean, df_b_framemean, n_boot=5000, seed=12345):
    d = df_a_framemean - df_b_framemean
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi)


def frame_means(df, policy, feat=None, model=None, n_seed=N_SEED, what='eff', csi_noise_sigma=0.0):
    """Per-FRAME mean over realisations (for frame-level paired bootstrap).
    what='eff' -> mean realised F1 per frame; what='pay' -> mean payload per frame.
    csi_noise_sigma: perturb the selector's est_snr (robustness), eff at TRUE snr (see eval_series)."""
    n = len(df); acc = np.zeros(n)
    for s in range(n_seed):
        snr, is_ray, b16, b256 = draws(n, s)
        eff = eff_of(df, b16, b256)
        if policy == 'rf':
            d = df.copy()
            est = snr if csi_noise_sigma <= 0 else snr + np.random.default_rng(s + 10000).normal(0, csi_noise_sigma, n)
            d['est_snr_db'] = est; d['channel_is_rayleigh'] = is_ray.astype(int)
            idx = np.array([ACTIONS.index(a) for a in np.asarray(model.predict(d[feat]))])
        elif policy == 'oracle':
            idx = masked_oracle(eff, b16, b256)
        elif policy.startswith('fixed'):
            idx = np.full(n, ACTIONS.index(policy.replace('fixed', '')))
        elif policy.startswith('threshold:'):
            tau = float(policy.split(':')[1]); idx = np.where((~is_ray) & (snr > tau), 1, 0)
        acc += (eff[np.arange(n), idx] if what == 'eff' else PAYVEC[idx])
    return acc / n_seed
