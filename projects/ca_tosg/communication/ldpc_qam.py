#self+ P1 Step 1: physically-correct LDPC+QAM BLER via Sionna (replaces the 40-block
# min-sum table: its 0.025 floor = 1/40 sampling limit, and its codeword-level BLER was
# wrongly used as frame-level in the pipeline).
"""
Rate-1/2 5G-LDPC (k=500, n=1000) + 16/256-QAM over AWGN and Rayleigh block-fading,
Sionna on CPU (TensorFlow has no sm_120 kernels for the RTX 5070, so GPU is disabled).

X-AXIS = Es/N0 (dB), received symbol SNR -- the quantity a receiver / the selector's
"estimated SNR" feature actually measures. Conversion to the information-bit-normalised
Eb/N0 used by the OLD table:  Eb/N0 = Es/N0 - 10*log10(coderate * bits_per_symbol),
i.e. for rate-1/2:  16-QAM  Eb/N0 = Es/N0 - 3.01 dB ;  256-QAM  Eb/N0 = Es/N0 - 6.02 dB.

Two granularities per point:
  bler_cw    = codeword block-error rate measured by Sionna.
  bler_frame = 1 - (1 - bler_cw)^N_CW ,  N_CW = ceil(1.98e6 / K) = 3960 codewords per
               feature frame (an all-or-nothing feature message spans N_CW codewords;
               under Rayleigh the blocks fade independently, so independence holds).

Adaptive Monte-Carlo per point: keep drawing batches until >= TARGET_ERR block errors OR
>= MAX_CW codewords (whichever first) -> no 1/N quantisation floor. Deep-tail points that
hit MAX_CW with 0 errors report bler_cw as an upper bound (< 1/MAX_CW).

Grid: a coarse pass locates each (modulation, channel) waterfall, then the cliff band
(codeword BLER in [CLIFF_LO, CLIFF_HI]) is densified to 0.5 dB.

Rayleigh = per-codeword-block flat fading with perfect receiver CSI: block power
|h|^2 ~ Exp(1), effective noise scaled by 1/|h|^2 (per-block effective Es/N0 = |h|^2 * mean).
"""
import os, time, argparse, math
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import numpy as np, pandas as pd, tensorflow as tf
tf.config.set_visible_devices([], "GPU")
from sionna.phy.fec.ldpc import LDPC5GEncoder, LDPC5GDecoder
from sionna.phy.mapping import Mapper, Demapper, BinarySource
from sionna.phy.channel import AWGN
from sionna.phy.utils import ebnodb2no

K, N = 500, 1000
CODERATE = K / N
N_CW = math.ceil(1.98e6 / K)          # 3960 codewords / feature frame
NUM_ITER = 20
BATCH = 2000
TARGET_ERR = 100
MAX_CW = 100_000
CLIFF_LO, CLIFF_HI = 0.001, 0.9        # densify codeword-BLER waterfall to 0.5 dB here
HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
OUT = os.path.join(P1, 'results/channel')


PROV_DIR = os.path.join(P1, 'results/provenance')
def esno_to_no(esno_db, bps):
    ebno_db = esno_db - 10.0 * np.log10(CODERATE * bps)
    return float(ebnodb2no(float(ebno_db), num_bits_per_symbol=bps, coderate=CODERATE)), float(ebno_db)


def bler_point(esno_db, bps, channel, enc, dec, mp, dmp, src, rician_k=None):
    """Adaptive-MC codeword BLER at Es/N0 (dB) over AWGN / Rayleigh / Rician block-fading. bps=bits/symbol.
    Rician (rician_k = K factor): per-block |h|^2 non-central with a LOS component, E[|h|^2]=1; K=0 is
    identical in law to the Rayleigh branch, K->inf approaches AWGN. Same per-codeword independent
    block-fading + perfect-CSI structure as Rayleigh (frozen coherence model, see PROVENANCE)."""
    no, ebno = esno_to_no(esno_db, bps)
    n_cw = n_err = 0
    while n_cw < MAX_CW and n_err < TARGET_ERR:
        b = src([BATCH, K]); c = enc(b); x = mp(c)                      # [B, n/m] symbols
        if channel in ("rayleigh", "rician"):
            if channel == "rician":
                los = math.sqrt(rician_k / (rician_k + 1.0)); sig = math.sqrt(1.0 / (2.0 * (rician_k + 1.0)))
                hr = los + sig * tf.random.normal([BATCH, 1]); hi = sig * tf.random.normal([BATCH, 1])
                hp = hr * hr + hi * hi                                  # |h|^2, E[|h|^2]=1 (Rician K)
            else:
                hp = tf.random.gamma([BATCH, 1], 1.0, 1.0)             # |h|^2 ~ Exp(1) (Rayleigh)
            no_b = tf.cast(no, tf.float32) / tf.maximum(hp, 1e-6)       # per-block effective N0
            y = x + tf.complex(tf.random.normal(tf.shape(x)), tf.random.normal(tf.shape(x))) \
                * tf.cast(tf.sqrt(no_b / 2.0), tf.complex64)
            llr = dmp(y, no_b)                                          # perfect-CSI (per-block no)
        else:
            y = AWGN()(x, no); llr = dmp(y, no)
        bhat = dec(llr)
        blk = tf.reduce_any(tf.not_equal(tf.cast(b, tf.int32), tf.cast(bhat, tf.int32)), axis=-1)
        n_err += int(tf.reduce_sum(tf.cast(blk, tf.int32))); n_cw += BATCH
    return n_err / n_cw, n_cw, n_err, ebno


def sweep_channel(channel, m, coarse, rician_k=None):
    bps = int(round(math.log2(m)))            # 16-QAM -> 4 bits/symbol, 256-QAM -> 8
    enc = LDPC5GEncoder(K, N); dec = LDPC5GDecoder(enc, num_iter=NUM_ITER)
    mp = Mapper("qam", bps); dmp = Demapper("app", "qam", bps); src = BinarySource()
    rows = {}
    def run(esno):
        if esno in rows: return rows[esno]
        p, ncw, nerr, ebno = bler_point(esno, bps, channel, enc, dec, mp, dmp, src, rician_k)
        rows[esno] = dict(qam=m, channel=channel, rician_k=(rician_k if channel == "rician" else ""),
                          esno_db=round(esno, 2), ebno_db=round(ebno, 2),
                          bler_cw=p, n_cw=ncw, n_err=nerr,
                          bler_frame=1.0 - (1.0 - p) ** N_CW)
        ktag = f"K={rician_k}" if channel == "rician" else ""
        print(f"  {m:3d}QAM {channel:8s}{ktag:>6s} Es/N0={esno:5.1f} Eb/N0={ebno:5.1f} "
              f"BLER_cw={p:.3e} ({nerr}/{ncw}) BLER_frame={rows[esno]['bler_frame']:.4f}", flush=True)
        return rows[esno]
    for e in coarse: run(e)                                    # coarse pass
    # densify the cliff band to 0.5 dB
    band = sorted(e for e, r in rows.items() if CLIFF_LO <= r["bler_cw"] <= CLIFF_HI)
    if band:
        lo, hi = band[0] - 1.0, band[-1] + 1.0
        for e in np.round(np.arange(lo, hi + 1e-6, 0.5), 2): run(float(e))
    return [rows[e] for e in sorted(rows)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coarse_16", default="0,2,4,6,8,10,12")
    ap.add_argument("--coarse_256", default="6,8,10,12,14,16,18,20,22")
    # Rician mode (P3 item 5): comma-separated K factors. Writes a SEPARATE bler_sionna_rician.csv and
    # does NOT touch the frozen awgn/rayleigh bler_sionna.csv. Wider coarse grid (fading cliffs sit high).
    ap.add_argument("--rician_K", default="")
    ap.add_argument("--coarse_rician_16", default="0,2,4,6,8,10,12,14,16,18,20,24,28")
    ap.add_argument("--coarse_rician_256", default="6,8,10,12,14,16,18,20,22,24,28,32")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if a.rician_K.strip():
        Ks = [float(x) for x in a.rician_K.split(",")]
        rg = {16: [float(x) for x in a.coarse_rician_16.split(",")],
              256: [float(x) for x in a.coarse_rician_256.split(",")]}
        allrows = []
        for k in Ks:
            for m, coarse in rg.items():
                t0 = time.time()
                print(f"\n===== {m}QAM / rician K={k} =====", flush=True)
                allrows += sweep_channel("rician", m, coarse, rician_k=k)
                pd.DataFrame(allrows).to_csv(os.path.join(OUT, "bler_sionna_rician.csv"), index=False)
                print(f"  [{(time.time()-t0)/60:.1f} min]", flush=True)
        print("\n[DONE rician] ->", os.path.join(OUT, "bler_sionna_rician.csv"))
        return

    grids = {16: [float(x) for x in a.coarse_16.split(",")],
             256: [float(x) for x in a.coarse_256.split(",")]}
    allrows = []
    for channel in ("awgn", "rayleigh"):
        for m, coarse in grids.items():
            t0 = time.time()
            print(f"\n===== {m}QAM / {channel} =====", flush=True)
            allrows += sweep_channel(channel, m, coarse)
            pd.DataFrame(allrows).to_csv(os.path.join(OUT, "bler_sionna.csv"), index=False)
            print(f"  [{(time.time()-t0)/60:.1f} min]", flush=True)
    print("\n[DONE] ->", os.path.join(OUT, "bler_sionna.csv"))


if __name__ == "__main__":
    main()
