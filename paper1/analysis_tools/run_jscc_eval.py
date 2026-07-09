"""
General evaluation / SNR-sweep driver for the importance-map JSCC model.

For each requested SNR it writes a temp model_dir/config.yaml (with the JSCC
`channel_type` and `snr_db` set, importance_source/psm preserved), copies the
trained checkpoint as net_epoch1.pth, runs analysis_tools/inference_subset.py on
a fixed frame subset, parses the AP line, and accumulates a summary CSV.

Examples
--------
Gate-C ceiling (perfect channel):
    python run_jscc_eval.py --config <awgn.yaml> --ckpt <stage2.pth> \
        --channel identity --snrs 60 --max_samples 1000 --tag awgn_identity

AWGN sweep:
    python run_jscc_eval.py --config <awgn.yaml> --ckpt <stage2.pth> \
        --channel awgn --snrs 0,2,4,6,8,10,12 --max_samples 1000 --tag awgn_jscc

Ego-only diagnostic:
    python run_jscc_eval.py --config <awgn.yaml> --ckpt <stage2.pth> \
        --channel remote_zero --snrs 0 --max_samples 1000 --tag ego_only
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

AP_PATTERN = re.compile(
    r"The Average Precision at IOU 0\.3 is ([0-9.]+), "
    r"The Average Precision at IOU 0\.5 is ([0-9.]+), "
    r"The Average Precision at IOU 0\.7 is ([0-9.]+)"
)


def update_config(base_text, channel, snr, cr=None):
    text = re.sub(r"(\n\s*snr_db:\s*)[-+]?[0-9]*\.?[0-9]+",
                  rf"\g<1>{float(snr):.1f}", base_text)
    text = re.sub(r"(\n\s*channel_type:\s*)[A-Za-z0-9_]+",
                  rf"\g<1>{channel}", text)
    if cr is not None:
        # paper equal-channel-uses: baseline CR (0.00125/0.0025) vs JSCC 0.005
        text = re.sub(r"(\n\s*cr:\s*)[-+]?[0-9]*\.?[0-9]+",
                      rf"\g<1>{float(cr):.6g}", text)
    return text


def run_one(config_text, ckpt, channel, snr, tag, model_root, out_root, max_samples, num_workers, cr=None, allow_failed=False):
    name = f"{tag}_snr{int(round(snr)):+03d}".replace("+", "p").replace("-", "m")
    model_dir = Path(model_root) / name
    eval_dir = Path(out_root) / name
    model_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    (model_dir / "config.yaml").write_text(update_config(config_text, channel, snr, cr))
    shutil.copyfile(ckpt, model_dir / "net_epoch1.pth")
    log_path = eval_dir / "inference.log"

    cmd = [sys.executable, "-u", "analysis_tools/inference_subset.py",
           "--model_dir", str(model_dir),
           "--fusion_method", "intermediate",
           "--global_sort_detections",
           "--max_samples", str(max_samples),
           "--num_workers", str(num_workers)]
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    print(f"\n[INFO] eval {tag} channel={channel} snr={snr} -> {log_path}")
    with open(log_path, "w", encoding="utf-8") as f:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, env=env)
        for line in proc.stdout:
            f.write(line)
        ret = proc.wait()

    text = log_path.read_text(encoding="utf-8", errors="ignore")
    m = AP_PATTERN.search(text)
    if ret != 0 or m is None:
        msg = f"eval failed for {tag} channel={channel} snr={snr} ret={ret}; log={log_path}"
        if m is None:
            msg += " (AP line not found)"
        if not allow_failed:
            raise RuntimeError(msg)
        print(f"[WARN] {msg}")
        return {"snr_db": snr, "ap_03": "", "ap_05": "", "ap_07": "",
                "return_code": ret, "log": str(log_path)}
    ap03, ap05, ap07 = m.groups()
    print(f"[RESULT] {tag} snr={snr}: AP@0.5={ap05} AP@0.7={ap07}")
    return {"snr_db": snr, "ap_03": ap03, "ap_05": ap05, "ap_07": ap07,
            "return_code": ret, "log": str(log_path)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--ckpt", required=True)
    p.add_argument("--channel", required=True)
    p.add_argument("--snrs", required=True, help="comma-separated list, e.g. 0,2,4,6")
    p.add_argument("--tag", required=True)
    p.add_argument("--max_samples", type=int, default=1000)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--model_root", default="opencood/logs/jscc_eval")
    p.add_argument("--out_root", default="experiment_logs/importance_map_jscc/jscc_eval")
    p.add_argument("--cr", type=float, default=None,
                   help="override importance-map CR (paper: JSCC 0.005, 16QAM 0.00125, 256QAM 0.0025)")
    p.add_argument("--allow_failed", action="store_true",
                   help="write blank rows instead of failing when a run fails; for diagnostics only")
    args = p.parse_args()

    base_text = Path(args.config).read_text()
    snrs = [float(s) for s in args.snrs.split(",")]
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    summary = out_root / f"{args.tag}_summary.csv"

    rows = []
    for snr in snrs:
        rows.append(run_one(base_text, args.ckpt, args.channel, snr, args.tag,
                            args.model_root, args.out_root, args.max_samples, args.num_workers,
                            cr=args.cr, allow_failed=args.allow_failed))
        with open(summary, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["snr_db", "ap_03", "ap_05", "ap_07",
                                              "return_code", "log"])
            w.writeheader()
            w.writerows(rows)
    print(f"\n[DONE] {args.tag} -> {summary}")


if __name__ == "__main__":
    main()
