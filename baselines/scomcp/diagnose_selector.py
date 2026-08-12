#self+ SComCP repro: inspect trained selector top-K behaviour (used to find selector-collapse bug)
# -*- coding: utf-8 -*-
"""Diagnose: how many tokens does the SComCP selector actually keep?

If `paper_k` / `remote_payload_tokens` is ~0 across frames, the selector
collapsed and the codec is effectively a no-op; the channel can't affect
AP because nothing is going through it.
"""
import os
import sys

import torch
from torch.utils.data import DataLoader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import opencood.hypes_yaml.yaml_utils as yaml_utils
from opencood.tools import train_utils
from opencood.data_utils.datasets import build_dataset


CKPT_DIR = 'peiyi_work/02_scomcp_reproduction/runs/v5k/stage2'


class _Opt:
    model_dir = CKPT_DIR


def main():
    hypes = yaml_utils.load_yaml(None, _Opt())
    val = build_dataset(hypes, visualize=True, train=False)
    loader = DataLoader(val, batch_size=1, num_workers=2,
                        collate_fn=val.collate_batch_test,
                        shuffle=False, drop_last=False)

    model = train_utils.create_model(hypes)
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(CKPT_DIR, model)
    model.eval()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    N = 50
    ks, totals, crs = [], [], []
    with torch.no_grad():
        for i, batch in enumerate(loader):
            if i >= N:
                break
            batch = train_utils.to_device(batch, device)
            out = model(batch['ego'])
            k = int(out.get('remote_payload_tokens',
                            out.get('paper_k', torch.tensor(-1))).item() if
                    torch.is_tensor(out.get('remote_payload_tokens',
                                             out.get('paper_k', None))) else -1)
            total = int(out.get('remote_payload_total_tokens',
                                torch.tensor(-1)).item() if
                        torch.is_tensor(out.get('remote_payload_total_tokens', None))
                        else -1)
            cr = float(out.get('paper_cr_actual',
                               torch.tensor(-1)).item() if
                       torch.is_tensor(out.get('paper_cr_actual', None)) else -1)
            ks.append(k); totals.append(total); crs.append(cr)
            if i < 5:
                print('frame %d: kept=%d/%d  CR=%.5f' % (i, k, total, cr))

    import statistics
    print()
    print('over %d frames:' % N)
    print('  kept tokens     : mean=%.1f  median=%d  min=%d  max=%d' %
          (statistics.mean(ks), statistics.median(ks), min(ks), max(ks)))
    print('  total positions : mean=%.1f' % statistics.mean(totals))
    print('  CR (kept/total) : mean=%.6f  median=%.6f' %
          (statistics.mean(crs), statistics.median(crs)))
    if statistics.mean(ks) < 5:
        print('\n!!! Selector collapsed: <5 tokens/frame on average.')
        print('!!! Codec is effectively a no-op; channel cannot affect AP.')


if __name__ == '__main__':
    main()
