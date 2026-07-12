#self+ CA-TOSG P1 Step-5 Track A: JSCC per-frame decode sweep, boxes+SCORES saved (F1 AND AP),
# scored ONLY against canonical GT v3. Uses the learned stage2 checkpoints on H: (as-is, no retrain).
"""
Drives regen_preds_with_scores.py (which saves per-frame boxes+scores+gts npz) over the JSCC learned
checkpoints, templating the learned yaml per (channel, split, snr). One npz per run:
  <out_dir>/jscc_<channel>_<split>_snr<NN>.npz   (boxes, scores, gts — object arrays)

QUEUE ORDER (supervisor 2026-07-12): AWGN both splits -> Rayleigh both -> OFDM both, so the headline
(AWGN edge + the first scene-disjoint TEST backing) lands first even if the GPU is reclaimed mid-run.
Full sweep = 3 channels x 2 splits x 6 SNRs = 36 runs (~25 GPU-hours). SNR grid 0/4/8/12/16/20.

Modes:
  --mode sweep   : the full 36-run queue (or a subset via --channels/--splits/--snrs).
  --mode probe   : interpolation-validity probe -- decode validate at SNR 8/10/12 (limit frames),
                   so score_jscc_v3.py can report interp(8,12)->10 vs real-10 per-frame F1 MAE.
"""
import argparse, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]                                   # OpenCOOD root
P1 = REPO / 'peiyi_work/paper1'
REGEN = P1 / 'code/regen_preds_with_scores.py'
CKPT_ROOT = Path('/mnt/h/opencood_project/outputs/experiment_logs/importance_map_jscc')
CFG = {c: REPO / f'opencood/hypes_yaml/point_pillar_importance_map_jscc_{c}_learned.yaml'
       for c in ('awgn', 'rayleigh', 'ofdm')}
CKPT = {c: CKPT_ROOT / f'stage2_{c}_learned_v3/stage2_whole_map_4000steps.pth'
        for c in ('awgn', 'rayleigh', 'ofdm')}
DATA = REPO / 'opencood/../opv2v_data_dumping'           # -> OpenCOOD/opv2v_data_dumping
SPLIT_DIR = {'validate': str((REPO / 'opv2v_data_dumping/validate')),
             'test': str((REPO / 'opv2v_data_dumping/test'))}
SNR_GRID = [0, 4, 8, 12, 16, 20]
CH_ORDER = ['awgn', 'rayleigh', 'ofdm']


def template(text, channel, snr, split_dir):
    text = re.sub(r"(\n\s*snr_db:\s*)[-+]?[0-9]*\.?[0-9]+", rf"\g<1>{float(snr):.1f}", text)
    text = re.sub(r"(\n\s*channel_type:\s*)[A-Za-z0-9_]+", rf"\g<1>{channel}", text)
    text = re.sub(r"(\nvalidate_dir:\s*)'[^']*'", rf"\g<1>'{split_dir}'", text)
    return text


def run_one(channel, split, snr, out_dir, model_root, limit, tag):
    cfg = template(CFG[channel].read_text(), channel, snr, SPLIT_DIR[split])
    name = f"{tag}_{channel}_{split}_snr{int(round(snr)):02d}"
    md = Path(model_root) / name
    md.mkdir(parents=True, exist_ok=True)
    (md / 'config.yaml').write_text(cfg)
    shutil.copyfile(CKPT[channel], md / 'net_epoch1.pth')
    out_npz = os.path.join(out_dir, f'jscc_{channel}_{split}_snr{int(round(snr)):02d}.npz')
    log = md / 'regen.log'
    cmd = [sys.executable, '-u', str(REGEN), '--model_dir', str(md),
           '--fusion_method', 'intermediate', '--out', out_npz]
    if limit:
        cmd += ['--limit', str(limit)]
    env = os.environ.copy(); env['PYTHONPATH'] = str(REPO)
    # Retry: an occasional early SIGSEGV (ret=-11, empty log) was observed at model/dataset init
    # (transient, likely a CUDA/TF-init race between back-to-back subprocesses) -- retry up to 3x.
    for attempt in range(1, 4):
        print(f'[RUN] {name} (attempt {attempt}) -> {out_npz}', flush=True)
        with open(log, 'w') as f:
            ret = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(REPO), env=env).returncode
        if ret == 0 and os.path.exists(out_npz):
            break
        print(f"[RETRY] {name} attempt {attempt} ret={ret}", flush=True)
    tail = log.read_text(errors='ignore').splitlines()[-2:]
    print(f"[{'OK' if ret == 0 else 'FAIL'}] {name} ret={ret} (attempt {attempt}): {' | '.join(tail)}", flush=True)
    return ret


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['sweep', 'probe'], default='sweep')
    ap.add_argument('--out_dir', default=str(P1 / 'gs_rerun/jscc_v3'))
    ap.add_argument('--model_root', default=str(HERE / 'runs_v3'))
    ap.add_argument('--channels', default=','.join(CH_ORDER))
    ap.add_argument('--splits', default='validate,test')
    ap.add_argument('--snrs', default=','.join(map(str, SNR_GRID)))
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    if args.mode == 'probe':
        # AWGN validate at 8/10/12, limited frames, for the interpolation-validity check
        chans, splits, snrs, limit, tag = ['awgn'], ['validate'], [8, 10, 12], (args.limit or 200), 'probe'
    else:
        chans = [c for c in CH_ORDER if c in args.channels.split(',')]
        splits = args.splits.split(','); snrs = [float(s) for s in args.snrs.split(',')]
        limit, tag = args.limit, 'jscc'

    queue = [(c, sp, s) for c in chans for sp in splits for s in snrs]  # channel-major = priority
    print(f'[QUEUE] {len(queue)} runs, order channel-major {chans} x splits {splits} x snrs {snrs}', flush=True)
    done = 0
    for c, sp, s in queue:
        ret = run_one(c, sp, s, args.out_dir, args.model_root, limit, tag)
        done += 1
        print(f'[PROGRESS] {done}/{len(queue)} done', flush=True)
    print('[DONE]', args.mode, flush=True)


if __name__ == '__main__':
    main()
