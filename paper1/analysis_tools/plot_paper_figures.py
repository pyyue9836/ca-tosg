"""
Strict plotting for the importance-map JSCC reproduction.

This plotter intentionally refuses to invent an upper bound. The upper-bound
line must come from a measured MAP-JSCC identity/perfect-channel CSV generated
from the same checkpoint and compression setting as the JSCC sweeps.
"""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class CsvError(RuntimeError):
    pass


def _read_rows(path, required=True):
    if path is None:
        if required:
            raise CsvError("required CSV path is missing")
        return []
    p = Path(path)
    if not p.exists():
        if required:
            raise CsvError(f"CSV does not exist: {p}")
        return []
    with p.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if required and not rows:
        raise CsvError(f"CSV has no data rows: {p}")
    for row in rows:
        rc = row.get("return_code", "0")
        if str(rc).strip() not in ("", "0"):
            raise CsvError(f"non-zero return_code in {p}: {rc}")
    return rows


def read_curve(path, required=True, label="curve"):
    rows = _read_rows(path, required=required)
    if not rows:
        return None
    snr, ap05, ap07 = [], [], []
    for row in rows:
        try:
            snr.append(float(row["snr_db"]))
            ap05.append(float(row["ap_05"]))
            ap07.append(float(row["ap_07"]))
        except (KeyError, ValueError) as exc:
            raise CsvError(f"bad {label} row in {path}: {row}") from exc
    order = sorted(range(len(snr)), key=lambda i: snr[i])
    return ([snr[i] for i in order],
            [ap05[i] for i in order],
            [ap07[i] for i in order])


def read_upper(path):
    rows = _read_rows(path, required=True)
    row = rows[0]
    try:
        return float(row["ap_05"]), float(row["ap_07"])
    except (KeyError, ValueError) as exc:
        raise CsvError(f"bad upper-bound row in {path}: {row}") from exc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--channel", required=True, choices=["awgn", "rayleigh", "ofdm"])
    p.add_argument("--jscc", required=True)
    p.add_argument("--upper_csv", required=True,
                   help="measured MAP-JSCC identity/perfect-channel CSV from the same checkpoint/CR")
    p.add_argument("--ldpc16", default=None,
                   help="optional separate-coding CSV; omit when no channel-matched baseline exists")
    p.add_argument("--ldpc256", default=None,
                   help="optional separate-coding CSV; omit when no channel-matched baseline exists")
    p.add_argument("--out", default="experiment_logs/importance_map_jscc/paper_range_figures")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    jscc = read_curve(args.jscc, required=True, label="JSCC")
    l16 = read_curve(args.ldpc16, required=False, label="LDPC+16QAM")
    l256 = read_curve(args.ldpc256, required=False, label="LDPC+256QAM")
    ub05, ub07 = read_upper(args.upper_csv)

    print(f"[INFO] upper bound = AP@0.5 {ub05}, AP@0.7 {ub07}  ({args.upper_csv})")

    titles = {"awgn": "AWGN", "rayleigh": "Rayleigh fading",
              "ofdm": "Time-varying multipath (OFDM)"}
    has_baseline = bool(l16 or l256)
    title_tail = "vs separate coding" if has_baseline else "channel sweep"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))

    for ax, idx, ylab in ((axes[0], 1, "AP@0.5"), (axes[1], 2, "AP@0.7")):
        ax.plot(jscc[0], jscc[idx], "-s", color="#1f77b4", lw=2,
                label="Ours-JSCC", markersize=5)
        if l16:
            ax.plot(l16[0], l16[idx], "--o", color="#d62728", lw=1.8,
                    label="LDPC+16QAM", markersize=4)
        if l256:
            ax.plot(l256[0], l256[idx], "--^", color="#2ca02c", lw=1.8,
                    label="LDPC+256QAM", markersize=4)
        ub = ub05 if idx == 1 else ub07
        ax.axhline(ub, ls=":", color="#ff7f0e", lw=2, label="MAP identity ceiling")
        ax.set_xlabel("SNR (dB)")
        ax.set_ylabel(ylab)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=9)

    axes[0].set_title(f"{titles[args.channel]} - AP@0.5")
    axes[1].set_title(f"{titles[args.channel]} - AP@0.7")
    fig.suptitle(f"Importance-Map JSCC {title_tail} ({titles[args.channel]})",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    for ext in ("png", "pdf"):
        fig.savefig(out_dir / f"fig_{args.channel}_jscc_vs_separate.{ext}",
                    bbox_inches="tight", dpi=180)
    print("[DONE]", out_dir / f"fig_{args.channel}_jscc_vs_separate.png")


if __name__ == "__main__":
    main()
