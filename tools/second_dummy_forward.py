#!/usr/bin/env python
"""P4-B-c step 4: record the SECOND transmitted-feature tensor before and after compression.

Runs a single forward pass of the verified SECOND intermediate-fusion model and captures the
shapes at the three points that matter for the P4-B payload derivation `B_F^SECOND`:

  spatial_features   HeightCompression output -- the dense BEV tensor entering the 2-D backbone
  pre-compression    input to `compression_modules[0]`, i.e. `blocks[0]`'s output
  bottleneck         output of the AutoEncoder's ENCODER stack -- **this is what is transmitted**
  post-compression   AutoEncoder output after its decoder, back at the pre-compression shape

The bottleneck is the load-bearing one and it is not a named tensor anywhere: OpenCOOD's
`AutoEncoder.forward` runs encoder and decoder back-to-back and returns only the reconstruction, so
the compressed representation exists solely between two statements. It is captured with a forward
hook on the last encoder stage rather than inferred from the config.

This records SHAPES only. It does **not** choose `bits_per_element` and therefore does not produce
`B_F^SECOND` -- that decision is still open (Change-log P4-B item 2).

    python tools/second_dummy_forward.py --ckpt-dir <converted_variant_dir> --data-root <opv2v> \
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt-dir", required=True)
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--opencood", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sys.path.insert(0, args.opencood)
    import opencood.hypes_yaml.yaml_utils as yaml_utils
    from torch.utils.data import DataLoader

    from opencood.data_utils.datasets import build_dataset
    from opencood.tools import train_utils

    hypes = yaml_utils.load_yaml(os.path.join(args.ckpt_dir, "config.yaml"), None)
    hypes = copy.deepcopy(hypes)
    hypes["validate_dir"] = os.path.join(args.data_root, args.split)

    dataset = build_dataset(hypes, visualize=False, train=False)
    loader = DataLoader(dataset, batch_size=1, num_workers=0,
                        collate_fn=dataset.collate_batch_test, shuffle=False)

    model = train_utils.create_model(hypes)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    _, model = train_utils.load_saved_model(args.ckpt_dir, model)
    model.eval()

    caught = {}

    def shape_of(t):
        if hasattr(t, "dense"):          # spconv SparseConvTensor
            return {"type": "SparseConvTensor", "spatial_shape": list(t.spatial_shape),
                    "features": list(t.features.shape)}
        return {"type": "Tensor", "shape": list(t.shape), "elements": int(t.numel()),
                "dtype": str(t.dtype)}

    backbone_2d = model.backbone_2d
    handles = []
    handles.append(model.height_compression.register_forward_hook(
        lambda m, i, o: caught.__setitem__("spatial_features", shape_of(o["spatial_features"]))))

    assert getattr(backbone_2d, "compress", False), (
        "this variant has no compression modules -- pick the _compression variant"
    )
    for idx, comp in enumerate(backbone_2d.compression_modules):
        handles.append(comp.register_forward_pre_hook(
            lambda m, i, k=idx: caught.__setitem__(f"pre_compression_{k}", shape_of(i[0]))))
        handles.append(comp.register_forward_hook(
            lambda m, i, o, k=idx: caught.__setitem__(f"post_compression_{k}", shape_of(o))))
        # the transmitted tensor: output of the LAST encoder stage of this AutoEncoder
        handles.append(comp.encoder[-1].register_forward_hook(
            lambda m, i, o, k=idx: caught.__setitem__(f"bottleneck_{k}", shape_of(o))))

    batch = next(iter(loader))
    batch = train_utils.to_device(batch, device)
    with torch.no_grad():
        model(batch["ego"])
    for h in handles:
        h.remove()

    record = {
        "schema": "catosg-p4b-dummy-forward/1",
        "protocol": "CA-TOSG P4-B-c step 4 (docs/experiment_protocol.md)",
        "generated_by": "python tools/second_dummy_forward.py",
        "generated": datetime.now(timezone.utc).isoformat(),
        "ckpt_dir": args.ckpt_dir,
        "split_sampled": args.split,
        "frames_in_forward": 1,
        "cavs_in_this_frame": int(batch["ego"]["record_len"].sum().item()),
        "config": {
            "compression_layers": backbone_2d.compress_layer,
            "voxel_size": hypes["preprocess"]["args"]["voxel_size"],
            "lidar_range": hypes["preprocess"]["cav_lidar_range"],
            "height_compression_feature_num": hypes["model"]["args"]["height_compression"][
                "feature_num"],
        },
        "tensors": caught,
        "transmitted_tensor": (
            "bottleneck_0 -- the AutoEncoder ENCODER output. Note this is a per-CAV tensor: the "
            "forward runs all CAVs of the frame in one batch, so the leading dimension is the CAV "
            "count, and the per-message element count is elements / cavs."
        ),
        "bits_per_element": "NOT DECIDED -- B_F^SECOND is not derived here (Change-log P4-B item 2)",
    }
    if "bottleneck_0" in caught and "pre_compression_0" in caught:
        pre = caught["pre_compression_0"]["elements"]
        post = caught["bottleneck_0"]["elements"]
        record["compression_ratio_elements"] = round(pre / post, 6)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(record, f, indent=1)
        f.write("\n")
    print(json.dumps(record["tensors"], indent=1))
    print("compression ratio (elements):", record.get("compression_ratio_elements"))
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
