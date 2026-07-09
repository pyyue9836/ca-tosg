#self+ SComCP repro: full 3-stage training orchestrator with isolated runs/ output dirs
# -*- coding: utf-8 -*-
"""Minimal SComCP smoke run: short three-stage training + one-point AP eval.

Self-contained Python orchestrator (no shell). Writes everything under
`peiyi_work/02_scomcp_reproduction/runs/smoke_v1/` to keep new outputs isolated from existing
`opencood/logs/` and `experiment_logs/`.

Run:
  PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \
      peiyi_work/02_scomcp_reproduction/run_smoke.py [--steps 1000] [--eval_snr 10] [--eval_channel awgn]
"""
import argparse
import os
import statistics
import sys

import torch
import tqdm
import yaml
from torch.utils.data import DataLoader

import opencood.hypes_yaml.yaml_utils as yaml_utils
from opencood.tools import train_utils, inference_utils
from opencood.data_utils.datasets import build_dataset
from opencood.utils import eval_utils
from opencood.models.fuse_modules.importance_map_jscc_fuse import build_channel


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS_ROOT = os.path.join(REPO, 'scomcp_repro', 'runs')
run_dir = None  # set in main() based on --run_name

STAGES = [
    dict(name='stage1',
         cfg=os.path.join(REPO, 'peiyi_work/02_scomcp_reproduction/configs/scomcp_stage1_selector.yaml'),
         gamma=0.0),
    dict(name='stage2',
         cfg=os.path.join(REPO, 'peiyi_work/02_scomcp_reproduction/configs/scomcp_stage2_codec.yaml'),
         gamma=0.05),
    dict(name='stage3',
         cfg=os.path.join(REPO, 'peiyi_work/02_scomcp_reproduction/configs/scomcp_stage3_joint.yaml'),
         gamma=0.0),
]


class _Opt:
    """Stand-in for argparse namespace used by yaml_utils.load_yaml."""
    def __init__(self):
        self.model_dir = ''


def warm_load(model, ckpt_path):
    state = torch.load(ckpt_path, map_location='cpu')
    if 'model_state_dict' in state:
        state = state['model_state_dict']
    miss, unexp = model.load_state_dict(state, strict=False)
    print('  warm_start: %s  (missing=%d  unexpected=%d)'
          % (os.path.basename(ckpt_path), len(miss), len(unexp)))


def train_one_stage(stage, base_ckpt, max_steps, device):
    save_dir = os.path.join(run_dir, stage['name'])
    os.makedirs(save_dir, exist_ok=True)

    hypes = yaml_utils.load_yaml(stage['cfg'], _Opt())
    gamma = stage['gamma']

    with open(os.path.join(save_dir, 'config.yaml'), 'w') as f:
        yaml.dump(hypes, f)

    train_set = build_dataset(hypes, visualize=False, train=True)
    loader = DataLoader(
        train_set, batch_size=hypes['train_params']['batch_size'],
        num_workers=4, collate_fn=train_set.collate_batch_train,
        shuffle=True, pin_memory=False, drop_last=True,
    )

    model = train_utils.create_model(hypes)
    if base_ckpt:
        warm_load(model, base_ckpt)
    model.to(device).train()

    criterion = train_utils.create_loss(hypes)
    optimizer = train_utils.setup_optimizer(hypes, model)
    scheduler = train_utils.setup_lr_schedular(hypes, optimizer, max_steps)

    pbar = tqdm.tqdm(total=max_steps, desc=stage['name'])
    step = 0
    losses = []
    loss_log = open(os.path.join(save_dir, 'train_loss.csv'), 'w')
    loss_log.write('step,loss,det_loss,rec_loss\n')
    while step < max_steps:
        for batch in loader:
            if step >= max_steps:
                break
            optimizer.zero_grad()
            batch = train_utils.to_device(batch, device)
            out = model(batch['ego'])
            det = criterion(out, batch['ego']['label_dict'])
            rec = out.get('rec_loss', None)
            if gamma > 0 and rec is not None:
                total = det + gamma * rec
                rec_val = float(rec.detach().cpu())
            else:
                total = det
                rec_val = 0.0
            total.backward()
            optimizer.step()
            if hypes['lr_scheduler']['core_method'] == 'cosineannealwarm':
                scheduler.step_update(step)

            losses.append(float(total.detach().cpu()))
            loss_log.write('%d,%.6f,%.6f,%.6f\n' %
                           (step, losses[-1], float(det.detach().cpu()), rec_val))
            pbar.update(1)
            step += 1
    pbar.close()
    loss_log.close()

    # Use 'latest.pth' so train_utils.load_saved_model can find it.
    ckpt_out = os.path.join(save_dir, 'latest.pth')
    torch.save(model.state_dict(), ckpt_out)
    tail = losses[-100:] if len(losses) >= 100 else losses
    print('  %s done. last-%d loss avg = %.4f  ->  %s'
          % (stage['name'], len(tail), statistics.mean(tail), ckpt_out))
    return ckpt_out


def set_eval_channel(fusion_net, channel, snr):
    """Reconfigure a trained fusion net's channel for a single SNR point.

    Matches eval_sweep_scomcp.set_eval_channel: switches the diagnostic flags
    AND rebuilds semantic_codec.channel for analog channels (the codec channel
    module is bound at construction, so attribute-only mutation is not enough).
    """
    ch = channel.lower()
    fusion_net.channel_type = ch
    fusion_net.perfect_comm_control = ch in ['perfect_comm', 'perfect', 'upper_bound']
    fusion_net.remote_zero_control = ch in ['remote_zero', 'drop_remote', 'zero']
    fusion_net.ldpc_baseline_control = False
    if ch in ['awgn', 'rayleigh', 'ofdm'] and hasattr(fusion_net, 'semantic_codec'):
        fusion_net.semantic_codec.channel = build_channel(ch, snr)
        fusion_net.semantic_codec.channel.to(next(fusion_net.parameters()).device)
    fusion_net.set_snr(float(snr))


def eval_one_point(ckpt_dir, channel, snr, device, save_dir, max_batches=None):
    """Run AP@0.5 / AP@0.7 on val set at one (channel, SNR) point.

    ckpt_dir must contain config.yaml + latest.pth (or net_epoch*.pth) so
    train_utils.load_saved_model can pick it up.
    """
    os.makedirs(save_dir, exist_ok=True)
    print('\n===== Eval: channel=%s SNR=%s dB =====' % (channel, snr))

    # load_yaml(None, opt) reads <model_dir>/config.yaml (matches eval_sweep).
    opt = _Opt(); opt.model_dir = ckpt_dir
    hypes = yaml_utils.load_yaml(None, opt)

    val_set = build_dataset(hypes, visualize=True, train=False)
    loader = DataLoader(
        val_set, batch_size=1, num_workers=4,
        collate_fn=val_set.collate_batch_test, shuffle=False,
        pin_memory=False, drop_last=False,
    )

    model = train_utils.create_model(hypes)
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(ckpt_dir, model)
    model.eval()

    set_eval_channel(model.fusion_net, channel, snr)

    result_stat = {0.3: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.5: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.7: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}

    n = max_batches if max_batches else len(loader)
    pbar = tqdm.tqdm(total=n, desc='eval')
    with torch.no_grad():
        for i, batch in enumerate(loader):
            if max_batches and i >= max_batches:
                break
            batch = train_utils.to_device(batch, device)
            pred_box, pred_score, gt_box = \
                inference_utils.inference_intermediate_fusion(batch, model, val_set)
            for thr in (0.3, 0.5, 0.7):
                eval_utils.caluclate_tp_fp(pred_box, pred_score, gt_box,
                                            result_stat, thr)
            pbar.update(1)
    pbar.close()

    ap30, _, _ = eval_utils.calculate_ap(result_stat, 0.30, False)
    ap50, _, _ = eval_utils.calculate_ap(result_stat, 0.50, False)
    ap70, _, _ = eval_utils.calculate_ap(result_stat, 0.70, False)
    print('  AP@0.3=%.4f  AP@0.5=%.4f  AP@0.7=%.4f' % (ap30, ap50, ap70))

    n_dets_50 = sum(result_stat[0.5]['tp'])
    print('  (eval saw %d batches; %d TP@0.5 across all batches; gt=%d)'
          % (n if max_batches else len(loader), n_dets_50, result_stat[0.5]['gt']))

    eval_csv = os.path.join(save_dir, 'eval_smoke.csv')
    with open(eval_csv, 'w') as f:
        f.write('channel,snr_db,ap30,ap50,ap70\n')
        f.write('%s,%.1f,%.4f,%.4f,%.4f\n' % (channel, snr, ap30, ap50, ap70))
    print('  ->', eval_csv)
    return ap50, ap70


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--steps', type=int, default=1000,
                   help='Training steps per stage (smoke default = 1000).')
    p.add_argument('--base_ckpt', default=
        '/mnt/h/opencood_project/outputs/experiment_logs/importance_map_jscc/'
        'stage2_rayleigh_v3/stage2_whole_map_4000steps.pth')
    p.add_argument('--eval_snr', type=float, default=10.0)
    p.add_argument('--eval_channel', default='awgn',
                   choices=['awgn', 'rayleigh', 'perfect_comm'])
    p.add_argument('--eval_max_batches', type=int, default=None,
                   help='Cap val eval batches for speed (None = full val).')
    p.add_argument('--skip_train', action='store_true',
                   help='Skip training; only evaluate using run_dir/stage3 (or --eval_model_dir).')
    p.add_argument('--eval_model_dir', default='',
                   help='Override eval source dir (must contain config.yaml + latest.pth or net_epoch*.pth).')
    p.add_argument('--run_name', default='smoke_v1',
                   help='Run dir under peiyi_work/02_scomcp_reproduction/runs/. New runs MUST use a fresh name to keep prior runs untouched.')
    args = p.parse_args()

    global run_dir
    run_dir = os.path.join(RUNS_ROOT, args.run_name)
    os.makedirs(run_dir, exist_ok=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('device=%s  run_dir=%s' % (device, run_dir))

    if not args.skip_train:
        ckpt = args.base_ckpt
        for stage in STAGES:
            print('\n===== %s =====' % stage['name'])
            ckpt = train_one_stage(stage, ckpt, args.steps, device)
        # FINAL_CKPT.txt now records the directory (load_saved_model takes a dir).
        final_dir = os.path.join(run_dir, 'stage3')
        with open(os.path.join(run_dir, 'FINAL_CKPT.txt'), 'w') as f:
            f.write(final_dir)
    else:
        final_dir = args.eval_model_dir or os.path.join(run_dir, 'stage3')

    ap50, ap70 = eval_one_point(
        final_dir, args.eval_channel, args.eval_snr, device,
        os.path.join(run_dir, 'eval'),
        max_batches=args.eval_max_batches,
    )
    print('\nSMOKE RUN COMPLETE.  Final ckpt dir: %s' % final_dir)
    print('  AP@0.5 = %.4f   AP@0.7 = %.4f   (channel=%s  SNR=%s dB)'
          % (ap50, ap70, args.eval_channel, args.eval_snr))


if __name__ == '__main__':
    sys.exit(main())
