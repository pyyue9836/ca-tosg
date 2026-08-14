#!/usr/bin/env python
"""P4-B-d: measure what an OpenCOOD AttBEVBackbone model actually puts on the wire.

Runs one forward pass and records, per fusion branch, the two quantities the paper's payload
accounting can be anchored to:

  pre-compression   the branch's block output -- the cross-link BEV tensor BEFORE any AutoEncoder.
                    This is what `main.tex` §"Message Construction and Payload Accounting" charges
                    its declared bits-per-element budget against.
  transmitted       what actually crosses the link: the AutoEncoder ENCODER output where the branch
                    is compressed, and the block output itself where it is not.

The distinction matters because `AttBEVBackbone` compresses branch `idx` only while
``compression - idx > 0``. A model with three branches and ``compression: 2`` therefore ships its
third branch **uncompressed**, while a two-branch model compresses both -- so two backbones are not
automatically comparable at the bottleneck.

Neither number is inferrable from the config alone: ``AutoEncoder.forward`` runs encoder and decoder
back to back and returns only the reconstruction, so the compressed representation exists solely
between two statements and has to be caught with a forward hook.

This records SHAPES. It chooses no bit-depth and derives no payload -- that is
``tests/test_payload.py``'s job (P4-B-d item 1).

    python tools/bev_tensor_probe.py --ckpt-dir <variant_dir> --data-root <opv2v> \
        --opencood <OpenCOOD repo> --out results/manifests/<file>.json
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone

import torch


def find_att_bev_backbone(model):
    """The 2-D backbone is `backbone_2d` on SECOND and `backbone` on PointPillar -- find it by type."""
    hits = [(name, m) for name, m in model.named_children()
            if type(m).__name__ == 'AttBEVBackbone']
    assert len(hits) == 1, f'expected exactly one AttBEVBackbone, found {[h[0] for h in hits]}'
    return hits[0]


def shape_of(t):
    if hasattr(t, 'dense'):                      # spconv SparseConvTensor
        return {'type': 'SparseConvTensor', 'spatial_shape': list(t.spatial_shape),
                'features': list(t.features.shape)}
    return {'type': 'Tensor', 'shape': list(t.shape), 'elements': int(t.numel()),
            'dtype': str(t.dtype)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt-dir', required=True)
    ap.add_argument('--data-root', required=True)
    ap.add_argument('--opencood', required=True)
    ap.add_argument('--split', default='test')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    sys.path.insert(0, args.opencood)
    import opencood.hypes_yaml.yaml_utils as yaml_utils
    from torch.utils.data import DataLoader

    from opencood.data_utils.datasets import build_dataset
    from opencood.tools import train_utils

    hypes = copy.deepcopy(yaml_utils.load_yaml(os.path.join(args.ckpt_dir, 'config.yaml'), None))
    hypes['validate_dir'] = os.path.join(args.data_root, args.split)

    dataset = build_dataset(hypes, visualize=False, train=False)
    loader = DataLoader(dataset, batch_size=1, num_workers=0,
                        collate_fn=dataset.collate_batch_test, shuffle=False)

    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    _, model = train_utils.load_saved_model(args.ckpt_dir, model)
    model.eval()

    bb_name, backbone = find_att_bev_backbone(model)
    n_branches = len(backbone.blocks)
    n_compressed = len(backbone.compression_modules) if getattr(backbone, 'compress', False) else 0

    caught, handles = {}, []
    handles.append(backbone.register_forward_pre_hook(
        lambda m, i: caught.__setitem__('spatial_features', shape_of(i[0]['spatial_features']))))
    for i, blk in enumerate(backbone.blocks):
        handles.append(blk.register_forward_hook(
            lambda m, inp, out, k=i: caught.__setitem__(f'pre_compression_{k}', shape_of(out))))
    for i in range(n_compressed):
        handles.append(backbone.compression_modules[i].encoder[-1].register_forward_hook(
            lambda m, inp, out, k=i: caught.__setitem__(f'bottleneck_{k}', shape_of(out))))
    # what each branch hands to cross-CAV fusion (the reconstruction, where the branch is compressed)
    for i, fuse in enumerate(backbone.fuse_modules):
        handles.append(fuse.register_forward_pre_hook(
            lambda m, inp, k=i: caught.__setitem__(f'fusion_input_{k}', shape_of(inp[0]))))

    batch = next(iter(loader))
    batch = train_utils.to_device(batch, device)
    with torch.no_grad():
        model(batch['ego'])
    for h in handles:
        h.remove()

    cavs = int(batch['ego']['record_len'].sum().item())

    branches, pre_total, tx_total = [], 0, 0
    for i in range(n_branches):
        pre = caught[f'pre_compression_{i}']['elements'] // cavs
        compressed = i < n_compressed
        tx = (caught[f'bottleneck_{i}']['elements'] // cavs) if compressed else pre
        pre_total += pre
        tx_total += tx
        branches.append({
            'branch': i,
            'compressed': compressed,
            'pre_compression_shape_per_cav': caught[f'pre_compression_{i}']['shape'][1:],
            'pre_compression_elements_per_cav': pre,
            'transmitted_shape_per_cav': (caught[f'bottleneck_{i}']['shape'][1:] if compressed
                                          else caught[f'pre_compression_{i}']['shape'][1:]),
            'transmitted_elements_per_cav': tx,
            'ratio': round(pre / tx, 6),
            'what_is_transmitted': ('AutoEncoder encoder output (bottleneck)' if compressed
                                    else 'the block output itself -- this branch is NOT compressed'),
        })

    record = {
        'schema': 'catosg-bev-tensor-probe/1',
        'protocol': 'CA-TOSG P4-B-d item 2 (docs/experiment_protocol.md)',
        'generated_by': 'python tools/bev_tensor_probe.py',
        'generated': datetime.now(timezone.utc).isoformat(),
        'ckpt_dir': args.ckpt_dir,
        'model_core_method': hypes['model']['core_method'],
        'backbone_attribute': bb_name,
        'split_sampled': args.split,
        'frames_in_forward': 1,
        'cavs_in_this_frame': cavs,
        'config': {
            'compression': backbone.compress_layer if getattr(backbone, 'compress', False) else 0,
            'num_filters': hypes['model']['args']['base_bev_backbone']['num_filters'],
            'layer_nums': hypes['model']['args']['base_bev_backbone']['layer_nums'],
            'voxel_size': hypes['preprocess']['args']['voxel_size'],
            'cav_lidar_range': hypes['preprocess']['cav_lidar_range'],
        },
        'branches_total': n_branches,
        'branches_compressed': n_compressed,
        'branches_uncompressed': n_branches - n_compressed,
        'branches': branches,
        'totals_per_cav': {
            'spatial_features_elements': caught['spatial_features']['elements'] // cavs,
            'pre_compression_elements': pre_total,
            'transmitted_elements': tx_total,
            'overall_ratio': round(pre_total / tx_total, 6),
        },
        'raw_tensors_as_hooked_all_cavs': caught,
        'note': ('elements are PER CAV: the forward runs all CAVs of the frame in one batch, so the '
                 'hooked leading dimension is the CAV count and every count above is divided by it. '
                 'No bit-depth is chosen here and no payload is derived.'),
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(record, f, indent=1)
        f.write('\n')

    print(f"{record['model_core_method']}  branches={n_branches} "
          f"(compressed {n_compressed}, uncompressed {n_branches - n_compressed})  cavs={cavs}")
    for b in branches:
        print(f"  branch {b['branch']}: pre {b['pre_compression_shape_per_cav']} "
              f"= {b['pre_compression_elements_per_cav']:>9,}  ->  tx "
              f"{b['transmitted_shape_per_cav']} = {b['transmitted_elements_per_cav']:>9,}  "
              f"({b['ratio']:g}x){'' if b['compressed'] else '   [NOT COMPRESSED]'}")
    t = record['totals_per_cav']
    print(f"  TOTAL per CAV: pre-compression {t['pre_compression_elements']:,}  "
          f"transmitted {t['transmitted_elements']:,}  ({t['overall_ratio']:g}x)")
    print(f'-> {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
