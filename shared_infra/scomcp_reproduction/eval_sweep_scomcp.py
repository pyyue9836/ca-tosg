# -*- coding: utf-8 -*-
"""
SNR-sweep evaluation for the SComCP figures.

One trained perception net is evaluated across SNR and channel models, exactly
as the paper does (Fig. 6 AWGN, Fig. 7 Rayleigh; Upper Bound and LDPC-QAM are
diagnostic channel overlays on the same net).  Produces a CSV with columns
  scheme, channel, snr_db, ap50, ap70, com_rate
that plot_figures.py turns into the paper plots.

Examples
--------
# SComCP, AWGN sweep:
python peiyi_work/02_scomcp_reproduction/eval_sweep_scomcp.py --model_dir <stage3_run> \
    --scheme SComCP --channel awgn --snr_list 0,2,4,6,8,10,12,14,16,18,20 \
    --out peiyi_work/02_scomcp_reproduction/results/scomcp_awgn.csv

# Upper bound (ideal channel, full feature) on the same net:
python peiyi_work/02_scomcp_reproduction/eval_sweep_scomcp.py --model_dir <stage3_run> \
    --scheme UpperBound --channel perfect_comm --snr_list 20 \
    --out peiyi_work/02_scomcp_reproduction/results/upper_awgn.csv
"""
import argparse
import csv

import torch
from tqdm import tqdm
from torch.utils.data import DataLoader

import opencood.hypes_yaml.yaml_utils as yaml_utils
from opencood.tools import train_utils, inference_utils
from opencood.data_utils.datasets import build_dataset
from opencood.utils import eval_utils
from opencood.models.fuse_modules.importance_map_jscc_fuse import build_channel


def parse():
    p = argparse.ArgumentParser()
    p.add_argument('--model_dir', required=True)
    p.add_argument('--scheme', required=True, help='label for the curve, e.g. SComCP')
    p.add_argument('--channel', default='rayleigh',
                   help='awgn | rayleigh | ofdm | perfect_comm | ldpc16qam | ldpc256qam')
    p.add_argument('--snr_list', default='0,2,4,6,8,10,12,14,16,18,20')
    p.add_argument('--out', required=True)
    p.add_argument('--global_sort', action='store_true')
    return p.parse_args()


def set_eval_channel(fusion_net, channel, snr):
    """Reconfigure a trained fusion net's channel/diagnostic mode at eval time."""
    ch = channel.lower()
    fusion_net.channel_type = ch
    fusion_net.perfect_comm_control = ch in ['perfect_comm', 'perfect', 'upper_bound']
    fusion_net.remote_zero_control = ch in ['remote_zero', 'drop_remote', 'zero']
    fusion_net.ldpc_baseline_control = ch in ['ldpc16qam', 'ldpc_16qam',
                                              'ldpc256qam', 'ldpc_256qam']
    if fusion_net.ldpc_baseline_control:
        fusion_net.ldpc_qam_order = 16 if '16' in ch else 256
        if fusion_net._bler_xs is None:
            fusion_net._load_bler_table(
                'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
    # Analog codec channels: rebuild the channel module on the codec.
    if ch in ['awgn', 'rayleigh', 'ofdm'] and hasattr(fusion_net, 'semantic_codec'):
        fusion_net.semantic_codec.channel = build_channel(ch, snr)
        fusion_net.semantic_codec.channel.to(next(fusion_net.parameters()).device)
    fusion_net.set_snr(float(snr))


def run_once(model, dataset, loader, device, global_sort):
    result_stat = {0.3: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.5: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.7: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    coms = []
    for batch_data in tqdm(loader, leave=False):
        with torch.no_grad():
            batch_data = train_utils.to_device(batch_data, device)
            pred_box, pred_score, gt_box = \
                inference_utils.inference_intermediate_fusion(batch_data, model, dataset)
            for thr in (0.3, 0.5, 0.7):
                eval_utils.caluclate_tp_fp(pred_box, pred_score, gt_box, result_stat, thr)
    ap50, _, _ = eval_utils.calculate_ap(result_stat, 0.5, global_sort)
    ap70, _, _ = eval_utils.calculate_ap(result_stat, 0.7, global_sort)
    return ap50, ap70


def main():
    opt = parse()
    # load_yaml(None, opt) reads <model_dir>/config.yaml
    hypes = yaml_utils.load_yaml(None, opt)
    dataset = build_dataset(hypes, visualize=True, train=False)
    loader = DataLoader(dataset, batch_size=1, num_workers=8,
                        collate_fn=dataset.collate_batch_test,
                        shuffle=False, pin_memory=False, drop_last=False)

    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(opt.model_dir, model)
    model.eval()

    snrs = [float(s) for s in opt.snr_list.split(',') if s != '']
    rows = []
    for snr in snrs:
        set_eval_channel(model.fusion_net, opt.channel, snr)
        ap50, ap70 = run_once(model, dataset, loader, device, opt.global_sort)
        print('[%s | %s | SNR=%.1f] AP@0.5=%.4f  AP@0.7=%.4f'
              % (opt.scheme, opt.channel, snr, ap50, ap70))
        rows.append([opt.scheme, opt.channel, snr, ap50, ap70])

    with open(opt.out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['scheme', 'channel', 'snr_db', 'ap50', 'ap70'])
        w.writerows(rows)
    print('wrote %s' % opt.out)


if __name__ == '__main__':
    main()
