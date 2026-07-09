# -*- coding: utf-8 -*-
"""Stage-1 smoke test: build model, warm-start, run 1 forward+backward step.

Catches shape/device/key bugs in scomcp_fuse before kicking off real training.
"""
import argparse
import sys
import torch
from torch.utils.data import DataLoader

import opencood.hypes_yaml.yaml_utils as yaml_utils
from opencood.tools import train_utils
from opencood.data_utils.datasets import build_dataset


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--hypes_yaml', default='peiyi_work/02_scomcp_reproduction/configs/scomcp_stage1_selector.yaml')
    p.add_argument('--warm_start', default='peiyi_work/05_pretrained_models/pointpillar_attentive_fusion/pointpillar_attentive_fusion/latest.pth')
    p.add_argument('--model_dir', default='')
    opt = p.parse_args()

    print('[smoke] loading hypes ...')
    hypes = yaml_utils.load_yaml(opt.hypes_yaml, opt)

    print('[smoke] building val dataset (smaller) ...')
    ds = build_dataset(hypes, visualize=False, train=False)
    print('[smoke] dataset size:', len(ds))

    loader = DataLoader(ds, batch_size=hypes['train_params']['batch_size'],
                        num_workers=0, collate_fn=ds.collate_batch_train,
                        shuffle=False, pin_memory=False, drop_last=True)

    print('[smoke] building model ...')
    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('[smoke] device:', device)

    if opt.warm_start:
        print('[smoke] warm_start from', opt.warm_start)
        state = torch.load(opt.warm_start, map_location='cpu')
        if 'model_state_dict' in state:
            state = state['model_state_dict']
        missing, unexpected = model.load_state_dict(state, strict=False)
        print('[smoke] missing keys:', len(missing), 'unexpected:', len(unexpected))
        if missing:
            print('[smoke]   first 5 missing:', missing[:5])
        if unexpected:
            print('[smoke]   first 5 unexpected:', unexpected[:5])

    model.to(device)
    model.train()

    criterion = train_utils.create_loss(hypes)
    optimizer = train_utils.setup_optimizer(hypes, model)

    print('[smoke] fetching 1 batch ...')
    batch = next(iter(loader))
    batch = train_utils.to_device(batch, device)

    print('[smoke] forward ...')
    output = model(batch['ego'])
    print('[smoke] forward OK. output keys:', list(output.keys()) if isinstance(output, dict) else type(output))

    print('[smoke] loss ...')
    loss = criterion(output, batch['ego']['label_dict'])
    print('[smoke] loss:', float(loss))

    print('[smoke] backward ...')
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    print('[smoke] backward OK')

    print('[smoke] ALL OK')


if __name__ == '__main__':
    sys.exit(main())
