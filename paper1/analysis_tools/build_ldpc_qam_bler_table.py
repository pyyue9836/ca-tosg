"""
Build a calibrated LDPC + QAM BLER lookup table from the in-repo physical-layer
simulator (analysis_tools/ldpc_qam_physical_sanity_n1000_ebn0.py).

This produces the separate-source-channel-coding baseline curve used by the
where2comm link-erasure hook: rate-1/2 LDPC (N=1000) + 16/256QAM over AWGN, with
SNR treated as information-bit-normalized (Eb/N0). The simulation naturally
exhibits the waterfall cliff (16QAM ~ a few dB lower than 256QAM), matching the
paper's separate-coding behaviour. The table is interpolated at eval time.

Output: experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv
        columns: qam, snr_db, ber, bler
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ldpc_qam_physical_sanity_n1000_ebn0 import simulate_ldpc_qam


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_blocks", type=int, default=40,
                        help="blocks per SNR point (numpy min-sum decode is slow; "
                             "40 resolves the waterfall in ~tractable time)")
    parser.add_argument("--out", default="experiment_logs/importance_map_jscc/"
                                         "ldpc_qam_bler_table.csv")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Fine SNR grids covering each modulation's waterfall.
    grids = {
        16: np.arange(-4.0, 16.0 + 1e-6, 2.0),
        256: np.arange(2.0, 26.0 + 1e-6, 2.0),
    }

    rows = []
    for qam, snrs in grids.items():
        for snr in snrs:
            r = simulate_ldpc_qam(M_qam=qam, snr_db=float(snr),
                                  num_blocks=args.num_blocks, K=500,
                                  row_weight=3, seed=2026)
            rows.append({"qam": qam, "snr_db": float(snr),
                         "ber": r["ber"], "bler": r["bler"]})
            print(f"[CAL] {qam}QAM SNR={snr:+5.1f} dB  BER={r['ber']:.5f}  "
                  f"BLER={r['bler']:.4f}")
            pd.DataFrame(rows).to_csv(out_path, index=False)

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    print("\n[DONE] BLER table ->", out_path)
    # Report the waterfall midpoint (BLER ~ 0.5) per QAM as a sanity check.
    for qam in grids:
        sub = df[df.qam == qam].sort_values("snr_db")
        cross = sub[sub.bler <= 0.5]
        mid = float(cross.snr_db.min()) if len(cross) else float("nan")
        print(f"[INFO] {qam}QAM BLER<=0.5 first at SNR={mid} dB")


if __name__ == "__main__":
    main()
