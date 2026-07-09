# -*- coding: utf-8 -*-
"""
Three-stage trainer for the SComCP reproduction (paper Algorithm 1).

Differences vs opencood/tools/train.py:
  * --warm_start <ckpt.pth>: load weights (strict=False) at epoch 0, so a later
    stage starts from the previous stage's network without resuming its epoch
    counter.  Used to chain stage1 -> stage2 -> stage3.
  * Adds the transmission MSE term gamma * rec_loss to the detection loss, where
    gamma = hypes['scomcp_train']['rec_loss_weight'] (0.05 in stage 2, 0 else),
    matching paper eq. 22.
  * Submodule freezing is driven by model args 'freeze' (handled in the model).

Usage:
  python peiyi_work/02_scomcp_reproduction/train_scomcp.py \
      --hypes_yaml peiyi_work/02_scomcp_reproduction/configs/scomcp_stage2_codec.yaml \
      --warm_start opencood/logs/scomcp_stage1_selector_xxx/net_epoch30.pth
"""
import argparse
import os
import statistics

import torch
import tqdm
from tensorboardX import SummaryWriter
from torch.utils.data import DataLoader

import opencood.hypes_yaml.yaml_utils as yaml_utils
from opencood.tools import train_utils
from opencood.data_utils.datasets import build_dataset


def parse():
    p = argparse.ArgumentParser()
    p.add_argument('--hypes_yaml', required=True)
    p.add_argument('--model_dir', default='', help='resume from this run dir')
    p.add_argument('--warm_start', default='',
                   help='checkpoint .pth to initialise weights from (epoch reset to 0)')
    return p.parse_args()


def warm_start(model, ckpt_path):
    """Load weights non-strictly so new modules (selector/codec) start fresh."""
    state = torch.load(ckpt_path, map_location='cpu')
    if 'model_state_dict' in state:
        state = state['model_state_dict']
    missing, unexpected = model.load_state_dict(state, strict=False)
    print('[warm_start] loaded %s' % ckpt_path)
    print('[warm_start] missing keys (trained fresh): %d' % len(missing))
    print('[warm_start] unexpected keys (ignored):   %d' % len(unexpected))
    return model


def main():
    opt = parse()
    hypes = yaml_utils.load_yaml(opt.hypes_yaml, opt)
    gamma = float(hypes.get('scomcp_train', {}).get('rec_loss_weight', 0.0))
    print('[SComCP] rec_loss weight gamma = %.4f' % gamma)

    print('----------------- Dataset Building ------------------')
    train_set = build_dataset(hypes, visualize=False, train=True)
    val_set = build_dataset(hypes, visualize=False, train=False)

    train_loader = DataLoader(train_set, batch_size=hypes['train_params']['batch_size'],
                              num_workers=8, collate_fn=train_set.collate_batch_train,
                              shuffle=True, pin_memory=False, drop_last=True)
    val_loader = DataLoader(val_set, batch_size=hypes['train_params']['batch_size'],
                            num_workers=8, collate_fn=train_set.collate_batch_train,
                            shuffle=False, pin_memory=False, drop_last=True)

    print('--------------- Creating Model ------------------')
    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    if opt.model_dir:
        init_epoch, model = train_utils.load_saved_model(opt.model_dir, model)
        saved_path = opt.model_dir
    else:
        init_epoch = 0
        if opt.warm_start:
            model = warm_start(model, opt.warm_start)
        saved_path = train_utils.setup_train(hypes)

    if torch.cuda.is_available():
        model.to(device)

    criterion = train_utils.create_loss(hypes)
    optimizer = train_utils.setup_optimizer(hypes, model)
    num_steps = len(train_loader)
    scheduler = train_utils.setup_lr_schedular(hypes, optimizer, num_steps)
    writer = SummaryWriter(saved_path)

    epoches = hypes['train_params']['epoches']
    print('Training start (stage config: %s)' % hypes['name'])

    for epoch in range(init_epoch, max(epoches, init_epoch)):
        if hypes['lr_scheduler']['core_method'] != 'cosineannealwarm':
            scheduler.step(epoch)
        else:
            scheduler.step_update(epoch * num_steps + 0)
        for pg in optimizer.param_groups:
            print('learning rate %.7f' % pg['lr'])

        pbar = tqdm.tqdm(total=len(train_loader), leave=True)
        for i, batch_data in enumerate(train_loader):
            model.train()
            optimizer.zero_grad()
            batch_data = train_utils.to_device(batch_data, device)

            output_dict = model(batch_data['ego'])
            det_loss = criterion(output_dict, batch_data['ego']['label_dict'])

            # paper eq. 22: add gamma * MSE transmission loss when configured.
            rec = output_dict.get('rec_loss', None)
            if gamma > 0 and rec is not None:
                final_loss = det_loss + gamma * rec
            else:
                final_loss = det_loss

            criterion.logging(epoch, i, len(train_loader), writer, pbar=pbar)
            if gamma > 0 and rec is not None:
                writer.add_scalar('rec_loss', float(rec.detach().cpu()),
                                  epoch * num_steps + i)
            pbar.update(1)

            final_loss.backward()
            optimizer.step()
            if hypes['lr_scheduler']['core_method'] == 'cosineannealwarm':
                scheduler.step_update(epoch * num_steps + i)

        if epoch % hypes['train_params']['save_freq'] == 0:
            torch.save(model.state_dict(),
                       os.path.join(saved_path, 'net_epoch%d.pth' % (epoch + 1)))

        if epoch % hypes['train_params']['eval_freq'] == 0:
            losses = []
            with torch.no_grad():
                for batch_data in val_loader:
                    model.eval()
                    batch_data = train_utils.to_device(batch_data, device)
                    output_dict = model(batch_data['ego'])
                    losses.append(criterion(output_dict,
                                            batch_data['ego']['label_dict']).item())
            avg = statistics.mean(losses)
            print('At epoch %d, validation loss = %f' % (epoch, avg))
            writer.add_scalar('Validate_Loss', avg, epoch)

    print('Stage finished, checkpoints in %s' % saved_path)
    # convenience: write the final checkpoint path for the runner to chain.
    with open(os.path.join(saved_path, 'LAST_CKPT.txt'), 'w') as f:
        f.write(os.path.join(saved_path, 'net_epoch%d.pth' % epoches))


if __name__ == '__main__':
    main()
