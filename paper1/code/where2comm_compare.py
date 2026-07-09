#self+ CA-TOSG paper2: Where2comm baseline AP @ perfect channel (single-point reference)
# -*- coding: utf-8 -*-
"""Where2comm single-point baseline.

Runs inference on OPV2V validate using your existing Where2comm checkpoint
at perfect channel (= upper bound for the spatial-confidence-mask family),
producing AP@0.5 / AP@0.7. Used as a "we did compare with Where2comm"
defence line in §V.E and Discussion.

This script needs GPU. Run command (CPU-side it's ~20 min on RTX 5070):
  PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \\
      peiyi_work/01_paper_ca_tosg/where2comm_compare.py

It auto-discovers the checkpoint in
  /home/josh/cooperative_semantic_perception/OpenCOOD_cleanup_archive_20260604/
   where2comm_intermediate_ckpts/opencood/logs/point_pillar_where2comm_*/
"""
import argparse
import glob
import os
import shutil

import torch
import tqdm
from torch.utils.data import DataLoader


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_where2comm')
ARCHIVE_CKPT_GLOB = ('/home/josh/cooperative_semantic_perception/'
                     'OpenCOOD_cleanup_archive_20260604/where2comm_intermediate_ckpts/'
                     'opencood/logs/point_pillar_where2comm_*/net_epoch37.pth')
CFG = os.path.join(REPO, 'opencood/hypes_yaml/point_pillar_where2comm_local.yaml')


class _Opt:
    model_dir = ''


def stage_ckpt():
    """Copy the latest Where2comm ckpt and config into a clean run dir."""
    os.makedirs(OUT_DIR, exist_ok=True)
    ckpt_src = sorted(glob.glob(ARCHIVE_CKPT_GLOB))[-1]
    if not os.path.exists(CFG):
        raise FileNotFoundError(
            'config not found: %s\n'
            'Where2comm config is required at this path' % CFG)
    print('  ckpt :', ckpt_src)
    print('  cfg  :', CFG)
    shutil.copy(CFG, os.path.join(OUT_DIR, 'config.yaml'))
    dst_ckpt = os.path.join(OUT_DIR, 'latest.pth')
    if not os.path.exists(dst_ckpt):
        os.symlink(ckpt_src, dst_ckpt)
    return OUT_DIR


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--max_samples', type=int, default=None,
                   help='cap eval batches for a fast sanity check (None = full val)')
    args = p.parse_args()

    import opencood.hypes_yaml.yaml_utils as yaml_utils
    from opencood.tools import train_utils, inference_utils
    from opencood.data_utils.datasets import build_dataset
    from opencood.utils import eval_utils

    run_dir = stage_ckpt()
    opt = _Opt(); opt.model_dir = run_dir
    hypes = yaml_utils.load_yaml(None, opt)
    val = build_dataset(hypes, visualize=True, train=False)
    loader = DataLoader(val, batch_size=1, num_workers=4,
                        collate_fn=val.collate_batch_test,
                        shuffle=False, pin_memory=False, drop_last=False)

    model = train_utils.create_model(hypes)
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(run_dir, model)
    model.eval()

    result_stat = {0.3: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.5: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.7: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    n = args.max_samples or len(loader)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    pbar = tqdm.tqdm(total=n, desc='Where2comm eval')
    with torch.no_grad():
        for i, batch in enumerate(loader):
            if args.max_samples and i >= args.max_samples:
                break
            batch = train_utils.to_device(batch, device)
            pred_box, pred_score, gt_box = inference_utils.\
                inference_intermediate_fusion(batch, model, val)
            for thr in (0.3, 0.5, 0.7):
                eval_utils.caluclate_tp_fp(pred_box, pred_score, gt_box,
                                            result_stat, thr)
            pbar.update(1)
    pbar.close()

    ap30, _, _ = eval_utils.calculate_ap(result_stat, 0.30, False)
    ap50, _, _ = eval_utils.calculate_ap(result_stat, 0.50, False)
    ap70, _, _ = eval_utils.calculate_ap(result_stat, 0.70, False)
    print('  Where2comm @ perfect channel: AP@0.3=%.4f AP@0.5=%.4f AP@0.7=%.4f'
          % (ap30, ap50, ap70))

    with open(os.path.join(OUT_DIR, 'result.csv'), 'w') as f:
        f.write('scheme,channel,snr_db,ap30,ap50,ap70\n')
        f.write('Where2comm,perfect,inf,%.4f,%.4f,%.4f\n' % (ap30, ap50, ap70))
    print('wrote', OUT_DIR)


if __name__ == '__main__':
    main()
