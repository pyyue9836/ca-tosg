"""
Separate-source-channel-coding baseline (LDPC + QAM) SNR sweep, hosted on the
where2comm perception model. For each SNR a temp model_dir is created from the
trained where2comm checkpoint with a `link` block injected under
where2comm_fusion; the link erases communicated remote tokens with the
calibrated BLER(snr), so AP reaches the upper bound at high SNR and cliffs at
low SNR.

--qam none produces the clean upper bound (no link erasure).

Example:
    python run_separate_coding_sweep.py \
        --w2c_dir opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22 \
        --qam 16 --snrs 0,2,4,6,8,10,12 --max_samples 1000 --tag ldpc16qam
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

AP_PATTERN = re.compile(
    r"The Average Precision at IOU 0\.3 is ([0-9.]+), "
    r"The Average Precision at IOU 0\.5 is ([0-9.]+), "
    r"The Average Precision at IOU 0\.7 is ([0-9.]+)"
)
BLER_CSV = str(Path("experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv").resolve())


def find_ckpt(w2c_dir):
    cks = sorted(Path(w2c_dir).glob("net_epoch*.pth"),
                 key=lambda p: int(re.findall(r"\d+", p.stem)[-1]))
    if not cks:
        raise FileNotFoundError(f"no net_epoch*.pth in {w2c_dir}")
    return cks[-1]


def run_one(base_cfg, ckpt, qam, snr, tag, model_root, out_root, max_samples, num_workers):
    name = f"{tag}_snr{int(round(snr)):+03d}".replace("+", "p").replace("-", "m")
    model_dir = Path(model_root) / name
    eval_dir = Path(out_root) / name
    model_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Trained config.yaml carries numpy tags, so use the full Loader/Dumper
    # (the repo's own loader is yaml.Loader, so this round-trips cleanly).
    cfg = yaml.load(base_cfg, Loader=yaml.Loader)
    w2c = cfg["model"]["args"]["where2comm_fusion"]
    if qam in ("none", None):
        w2c.pop("link", None)
    else:
        w2c["link"] = {"model": f"ldpc{qam}qam", "snr_db": float(snr), "bler_csv": BLER_CSV}
    (model_dir / "config.yaml").write_text(yaml.dump(cfg, sort_keys=False))
    shutil.copyfile(ckpt, model_dir / "net_epoch1.pth")
    log_path = eval_dir / "inference.log"

    cmd = [sys.executable, "-u", "analysis_tools/inference_subset.py",
           "--model_dir", str(model_dir), "--fusion_method", "intermediate",
           "--global_sort_detections", "--max_samples", str(max_samples),
           "--num_workers", str(num_workers)]
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    print(f"[INFO] baseline {tag} qam={qam} snr={snr} -> {log_path}")
    with open(log_path, "w", encoding="utf-8") as f:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, env=env)
        for line in proc.stdout:
            f.write(line)
        ret = proc.wait()

    m = AP_PATTERN.search(log_path.read_text(errors="ignore"))
    if m is None:
        print(f"[WARN] no AP for {tag} snr={snr} (ret={ret})")
        return {"snr_db": snr, "ap_03": "", "ap_05": "", "ap_07": "",
                "return_code": ret, "log": str(log_path)}
    ap03, ap05, ap07 = m.groups()
    print(f"[RESULT] {tag} snr={snr}: AP@0.5={ap05} AP@0.7={ap07}")
    return {"snr_db": snr, "ap_03": ap03, "ap_05": ap05, "ap_07": ap07,
            "return_code": ret, "log": str(log_path)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--w2c_dir", required=True)
    p.add_argument("--qam", default="16", help="16 / 256 / none")
    p.add_argument("--snrs", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--max_samples", type=int, default=1000)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--model_root", default="opencood/logs/separate_coding_eval")
    p.add_argument("--out_root", default="experiment_logs/importance_map_jscc/separate_coding_eval")
    args = p.parse_args()

    base_cfg = (Path(args.w2c_dir) / "config.yaml").read_text()
    ckpt = find_ckpt(args.w2c_dir)
    snrs = [float(s) for s in args.snrs.split(",")]
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    summary = out_root / f"{args.tag}_summary.csv"

    rows = []
    for snr in snrs:
        rows.append(run_one(base_cfg, ckpt, args.qam, snr, args.tag,
                            args.model_root, args.out_root, args.max_samples, args.num_workers))
        with open(summary, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["snr_db", "ap_03", "ap_05", "ap_07",
                                              "return_code", "log"])
            w.writeheader()
            w.writerows(rows)
    print(f"[DONE] {args.tag} -> {summary}")


if __name__ == "__main__":
    main()
