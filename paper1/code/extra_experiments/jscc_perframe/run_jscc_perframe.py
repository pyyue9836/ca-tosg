#self+ JSCC per-frame F1 sweep: re-run ImportanceMapJSCC inference with --save_npy at
# each SNR, so we can later score per-frame JSCC F1 (graceful, no BLER cliff) and ask
# whether perception cues beat an SNR threshold when the channel has no cliff.
"""
For each SNR we:
  1. template the learned-importance-map JSCC config (set channel_type + snr_db),
  2. copy the stage2 checkpoint as net_epoch1.pth into a fresh model_dir,
  3. run analysis_tools/inference_subset.py --save_npy (dumps per-frame pred/gt .npy),
The npy land in <model_root>/<tag>_snrXX/npy and are scored per-frame by
score_jscc_perframe.py (reuses the pipeline's f1_from_boxes, IoU 0.5, so the JSCC F1
column is directly comparable to late_f1 / compressed_f1).

Run from the OpenCOOD repo root with the sionna310 interpreter, e.g.
  PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \
    peiyi_work/01_paper_ca_tosg/extra_experiments/jscc_perframe/run_jscc_perframe.py \
    --channel awgn --snrs 14 --max_samples 10 --tag smoke      # smoke
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# P1 Step-5 path repair: after the 01_paper_ca_tosg->paper1 rename + moving extra_experiments under
# code/, the repo root is parents[5] (was [4]); inference_subset.py moved to paper1/analysis_tools/;
# the learned stage2 checkpoints live on the H: drive (registered in results/DATA_MANIFEST.md, md5
# awgn 74c1319ab562 / rayleigh c5a02fd77154 / ofdm d75126199898). Checkpoints used AS-IS (no retrain).
REPO = Path(__file__).resolve().parents[5]          # OpenCOOD repo root
INFER = REPO / 'peiyi_work/paper1/analysis_tools/inference_subset.py'
HERE = Path(__file__).resolve().parent
CKPT_ROOT = Path('/mnt/h/opencood_project/outputs/experiment_logs/importance_map_jscc')
CFG = {
    'awgn':     REPO / 'opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn_learned.yaml',
    'rayleigh': REPO / 'opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh_learned.yaml',
    'ofdm':     REPO / 'opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm_learned.yaml',
}
CKPT = {
    'awgn':     CKPT_ROOT / 'stage2_awgn_learned_v3/stage2_whole_map_4000steps.pth',
    'rayleigh': CKPT_ROOT / 'stage2_rayleigh_learned_v3/stage2_whole_map_4000steps.pth',
    'ofdm':     CKPT_ROOT / 'stage2_ofdm_learned_v3/stage2_whole_map_4000steps.pth',
}


def template(text, channel, snr):
    text = re.sub(r"(\n\s*snr_db:\s*)[-+]?[0-9]*\.?[0-9]+", rf"\g<1>{float(snr):.1f}", text)
    text = re.sub(r"(\n\s*channel_type:\s*)[A-Za-z0-9_]+", rf"\g<1>{channel}", text)
    return text


def run_one(channel, snr, tag, model_root, max_samples, num_workers, data_dir=None):
    cfg_text = CFG[channel].read_text()
    if data_dir:  # optionally point validate_dir at another split (e.g. test)
        cfg_text = re.sub(r"(\nvalidate_dir:\s*)'[^']*'", rf"\g<1>'{data_dir}'", cfg_text)
    cfg_text = template(cfg_text, channel, snr)

    name = f"{tag}_{channel}_snr{int(round(snr)):02d}"
    model_dir = Path(model_root) / name
    (model_dir).mkdir(parents=True, exist_ok=True)
    (model_dir / "config.yaml").write_text(cfg_text)
    shutil.copyfile(CKPT[channel], model_dir / "net_epoch1.pth")

    log = model_dir / "inference.log"
    cmd = [sys.executable, "-u", str(INFER),
           "--model_dir", str(model_dir),
           "--fusion_method", "intermediate",
           "--global_sort_detections",
           "--save_npy",
           "--max_samples", str(max_samples),
           "--num_workers", str(num_workers)]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    # NB: do NOT set PYTHONNOUSERSITE -- the env-site numpy (2.2.6) breaks shapely's
    # ABI; the working combo is the user-site numpy 1.26.4 + shapely 2.0.0.
    print(f"[INFO] {name}: channel={channel} snr={snr} max_samples={max_samples} -> {log}")
    with open(log, "w") as f:
        ret = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(REPO), env=env).returncode
    tail = log.read_text(errors="ignore").splitlines()[-3:]
    print(f"[{'OK' if ret == 0 else 'FAIL'}] {name} ret={ret}")
    for t in tail:
        print("    " + t)
    return ret, model_dir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--channel", default="awgn", choices=["awgn", "rayleigh", "ofdm"])
    p.add_argument("--snrs", default="14", help="comma-separated dB list")
    p.add_argument("--max_samples", type=int, default=1000)
    p.add_argument("--num_workers", type=int, default=4)
    p.add_argument("--tag", default="jscc")
    p.add_argument("--data_dir", default=None, help="override validate_dir (e.g. the test split)")
    p.add_argument("--model_root", default=str(HERE / "runs"))
    args = p.parse_args()

    snrs = [float(s) for s in args.snrs.split(",")]
    for snr in snrs:
        ret, md = run_one(args.channel, snr, args.tag, args.model_root,
                          args.max_samples, args.num_workers, args.data_dir)
        if ret != 0:
            print(f"[ABORT] {args.channel} snr={snr} failed; see {md}/inference.log")
            sys.exit(1)
    print("[DONE]", args.tag, args.channel, snrs)


if __name__ == "__main__":
    main()
