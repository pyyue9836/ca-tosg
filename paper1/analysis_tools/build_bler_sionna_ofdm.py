#self+ P1 Step-5 (supervisor 2026-07-12): OFDM + frequency-selective TDL LDPC+QAM BLER, to CLOSE the
# 802.11bd standards-basis gap -- the digital branch was evaluated only on AWGN + FLAT Rayleigh, but the
# paper's PHY anchor 802.11bd IS an OFDM system whose cross-subcarrier coding carries frequency diversity.
# OFDM-LDPC is the scientifically interesting MIDDLE case between flat-Rayleigh (no diversity, all-dead)
# and AWGN (sharp cliff): frequency diversity should re-open a usable window at high SNR.
"""
SAME framework as build_bler_sionna.py (Es/N0 axis, per-codeword-independent realisation, perfect CSI,
adaptive MC to >=100 block errors / <=1e5 codewords, cliff densified to 0.5 dB, frame BLER =
1-(1-p_cw)^3960). ONE TDL profile, no profile sweep (scope: feeds ONLY Figure A + the two-regime
discussion, NOT the selector training/deployment sweeps; the 200-real protocol channel set stays
AWGN+Rayleigh and channel-type stays binary -- see PROVENANCE hard boundary).

MODEL (documented for PROVENANCE):
  OFDM: 802.11bd 10 MHz numerology -> N_FFT=64, SCS Delta_f=156.25 kHz, N_SC=52 data subcarriers.
  Channel: frequency-selective TDL, exponential power-delay profile, RMS delay spread tau_rms, L taps at
    uniform delays; per-codeword-INDEPENDENT complex tap gains g_l ~ CN(0, P_l) with Sum P_l = 1 (so the
    average subcarrier power E[|H[k]|^2]=1, matching the flat-Rayleigh Es/N0 normalisation). Same
    coherence argument as the flat-Rayleigh table (independent per codeword; ~1-3 ms coherence << frame).
  tau_rms = 100 ns : order-of-magnitude V2V value (3GPP TR 37.885 V2V highway NLOS regime). NOTE: the
    exact TR 37.885 tabulated delay spread should be verified against the document; the qualitative
    finding (frequency diversity opens a high-SNR window) is insensitive to the precise value, which only
    shifts the curve. Flagged for the supervisor to pin the exact citation.
  Coded symbols are frequency-INTERLEAVED across the N_SC subcarriers (symbol i -> subcarrier i mod N_SC),
    the standard 802.11 interleaver assumption, so one 1000-bit codeword spans many independent-ish
    subcarrier gains = frequency diversity. Perfect per-subcarrier CSI (per-symbol effective N0 = N0/|H|^2).
Output: results/bler_sionna/bler_sionna_ofdm.csv (channel='ofdm'); merged into bler_sionna.csv after review.
"""
import os, argparse, math
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np, pandas as pd, tensorflow as tf
tf.config.set_visible_devices([], "GPU")
from sionna.phy.fec.ldpc import LDPC5GEncoder, LDPC5GDecoder
from sionna.phy.mapping import Mapper, Demapper, BinarySource
from sionna.phy.utils import ebnodb2no

K, N = 500, 1000
CODERATE = K / N
N_CW = math.ceil(1.98e6 / K)            # 3960 codewords / feature frame
NUM_ITER = 20
BATCH = 2000
TARGET_ERR = 100
MAX_CW = 100_000
CLIFF_LO, CLIFF_HI = 0.001, 0.9
# OFDM / TDL
N_FFT = 64; N_SC = 52; SCS = 156.25e3        # 802.11bd 10 MHz
TAU_RMS = 100e-9; L_TAPS = 8                  # exponential PDP, V2V order-of-magnitude
HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(HERE)
OUT = os.path.join(P1, "results/bler_sionna")

# exponential PDP taps (uniform delays 0..3*tau_rms), normalised to unit total power
_delays = np.linspace(0, 3 * TAU_RMS, L_TAPS)
_pdp = np.exp(-_delays / TAU_RMS); _pdp = _pdp / _pdp.sum()
_SC_IDX = (np.arange(N_SC) - N_SC // 2)                      # subcarrier indices around DC


def esno_to_no(esno_db, bps):
    ebno_db = esno_db - 10.0 * np.log10(CODERATE * bps)
    return float(ebnodb2no(float(ebno_db), num_bits_per_symbol=bps, coderate=CODERATE)), float(ebno_db)


def _subcarrier_gains(batch):
    """H[batch, N_SC] frequency response of an independent exponential-PDP TDL per codeword."""
    g = tf.complex(tf.random.normal([batch, L_TAPS]), tf.random.normal([batch, L_TAPS])) \
        * tf.cast(tf.sqrt(_pdp / 2.0), tf.complex64)                       # CN(0,P_l)
    phase = -2.0 * np.pi * np.outer(_SC_IDX * SCS, _delays)                # [N_SC, L]
    steer = tf.constant(np.exp(1j * phase), tf.complex64)                  # [N_SC, L]
    return tf.matmul(g, steer, transpose_b=True)                          # [batch, N_SC]


def bler_point(esno_db, bps, enc, dec, mp, dmp, src):
    no, ebno = esno_to_no(esno_db, bps)
    n_cw = n_err = 0
    while n_cw < MAX_CW and n_err < TARGET_ERR:
        b = src([BATCH, K]); c = enc(b); x = mp(c)                        # [B, n_sym] symbols
        n_sym = x.shape[-1]
        H = _subcarrier_gains(BATCH)                                      # [B, N_SC]
        sc = tf.constant(np.arange(n_sym) % N_SC, tf.int32)              # freq-interleave
        Hs = tf.gather(H, sc, axis=1)                                     # [B, n_sym] per-symbol gain
        no_eff = tf.cast(no, tf.float32) / tf.maximum(tf.abs(Hs) ** 2, 1e-6)
        y = x + tf.complex(tf.random.normal(tf.shape(x)), tf.random.normal(tf.shape(x))) \
            * tf.cast(tf.sqrt(no_eff / 2.0), tf.complex64)               # per-subcarrier faded + noise
        llr = dmp(y, no_eff)                                             # perfect per-SC CSI
        bhat = dec(llr)
        blk = tf.reduce_any(tf.not_equal(tf.cast(b, tf.int32), tf.cast(bhat, tf.int32)), axis=-1)
        n_err += int(tf.reduce_sum(tf.cast(blk, tf.int32))); n_cw += BATCH
    return n_err / n_cw, n_cw, n_err, ebno


def sweep(m, coarse):
    bps = int(round(math.log2(m)))
    enc = LDPC5GEncoder(K, N); dec = LDPC5GDecoder(enc, num_iter=NUM_ITER)
    mp = Mapper("qam", bps); dmp = Demapper("app", "qam", bps); src = BinarySource()
    rows = {}
    def run(esno):
        if esno in rows: return rows[esno]
        p, ncw, nerr, ebno = bler_point(esno, bps, enc, dec, mp, dmp, src)
        rows[esno] = dict(qam=m, channel="ofdm", esno_db=round(esno, 2), ebno_db=round(ebno, 2),
                          bler_cw=p, n_cw=ncw, n_err=nerr, bler_frame=1.0 - (1.0 - p) ** N_CW)
        print(f"  {m:3d}QAM ofdm Es/N0={esno:5.1f} BLER_cw={p:.3e} ({nerr}/{ncw}) "
              f"BLER_frame={rows[esno]['bler_frame']:.4f}", flush=True)
        return rows[esno]
    for e in coarse: run(e)
    band = sorted(e for e, r in rows.items() if CLIFF_LO <= r["bler_cw"] <= CLIFF_HI)
    if band:
        lo, hi = band[0] - 1.0, band[-1] + 1.0
        for e in np.round(np.arange(lo, hi + 1e-6, 0.5), 2): run(float(e))
    return [rows[e] for e in sorted(rows)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coarse_16", default="0,2,4,6,8,10,12,14,16")
    ap.add_argument("--coarse_256", default="6,8,10,12,14,16,18,20,22,24")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print(f"OFDM/TDL: N_SC={N_SC} SCS={SCS/1e3:.1f}kHz tau_rms={TAU_RMS*1e9:.0f}ns L={L_TAPS} "
          f"PDP(norm)={np.round(_pdp,3)}", flush=True)
    allrows = []
    for m, coarse in ((16, [float(x) for x in a.coarse_16.split(",")]),
                      (256, [float(x) for x in a.coarse_256.split(",")])):
        print(f"\n===== {m}QAM / ofdm =====", flush=True)
        allrows += sweep(m, coarse)
    df = pd.DataFrame(allrows).sort_values(["qam", "esno_db"])
    df.to_csv(os.path.join(OUT, "bler_sionna_ofdm.csv"), index=False)
    print("\nwrote", os.path.join(OUT, "bler_sionna_ofdm.csv"), df.shape, flush=True)


if __name__ == "__main__":
    main()
