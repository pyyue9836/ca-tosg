#!/usr/bin/env python
"""P4-B-c expectation E4: prove the layout-converted SECOND checkpoint by reproducing the zoo's AP.

A converted checkpoint is not bit-wise the published file, so "these are the official weights" has
to be re-earned. This script runs official OpenCOOD intermediate fusion with the converted weights
and checks the result against the OpenCOOD model-zoo row it came from:

    | Attentive | 1.2.1 | SECOND | Intermediate | 63.4/0.99 | 0.826/0.783 | 0.760/0.760 |

The columns are "AP@0.7 for no-compression/compression", so the `_compression` variant's targets are
Default Towns (``test``) 0.783 and Culver City (``test_culver_city``) 0.760. The zoo's own AP
convention is *no* global sort (README: "OPV2V paper does not perform the global sort"), so that is
the number the tolerance is applied to; the global-sort AP is recorded as a separate quantity and
must not be blended with it.

The targets are read out of the OpenCOOD README table at run time, not hard-coded here, so the
comparison cannot silently drift from its source.

Usage:
    python tools/verify_second_zoo_ap.py --ckpt-dir <converted_variant_dir> \
        --data-root <opv2v_root> --opencood <OpenCOOD repo> --out results/manifests/<f>.json
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone

import torch


def zoo_targets_from_readme(opencood_root: str) -> dict:
    """Parse the SECOND/Intermediate row out of OpenCOOD's own README benchmark table."""
    path = os.path.join(opencood_root, "README.md")
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    row = None
    for line in lines:
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 8:
            continue
        if cells[3] == "SECOND" and cells[4] == "Intermediate":
            assert row is None, "more than one SECOND/Intermediate row in the README table"
            row = cells

    assert row is not None, f"SECOND/Intermediate row not found in {path}"

    def pair(cell: str) -> tuple[float, float]:
        nums = re.findall(r"\d+\.\d+", cell)
        assert len(nums) == 2, f"expected two AP values, got {cell!r}"
        return float(nums[0]), float(nums[1])

    towns_nocomp, towns_comp = pair(row[6])
    culver_nocomp, culver_comp = pair(row[7])
    return {
        "source": f"{path} (benchmark table, row 'Attentive | 1.2.1 | SECOND | Intermediate')",
        "column_meaning": "AP@0.7 for no-compression/compression",
        "second_attentive_fusion": {"test": towns_nocomp, "test_culver_city": culver_nocomp},
        "second_attentive_fusion_compression": {"test": towns_comp, "test_culver_city": culver_comp},
    }


def load_check(hypes, ckpt_dir, original_ckpt_dir):
    """E1/E2: the shape story, stated against both the original and the converted file."""
    from opencood.tools import train_utils

    model = train_utils.create_model(hypes)
    msd = model.state_dict()
    perm = (4, 0, 1, 2, 3)

    report = {}
    for tag, d in (("original", original_ckpt_dir), ("converted", ckpt_dir)):
        if d is None:
            continue
        sd = torch.load(os.path.join(d, "latest.pth"), map_location="cpu")
        mismatch, explained = [], 0
        for k in set(sd) & set(msd):
            if tuple(sd[k].shape) == tuple(msd[k].shape):
                continue
            mismatch.append(k)
            if sd[k].dim() == 5 and tuple(sd[k].permute(*perm).shape) == tuple(msd[k].shape):
                explained += 1
        report[tag] = {
            "tensors": len(sd),
            "missing_keys": len(set(msd) - set(sd)),
            "unexpected_keys": len(set(sd) - set(msd)),
            "shape_mismatches": len(mismatch),
            "explained_by_permute_4_0_1_2_3": explained,
            "unexplained": len(mismatch) - explained,
            "mismatched_keys": sorted(mismatch),
        }

    sd = torch.load(os.path.join(ckpt_dir, "latest.pth"), map_location="cpu")
    try:
        model.load_state_dict(sd, strict=True)
        report["strict_load"] = "OK -- all keys matched"
    except Exception as exc:  # pragma: no cover - the failure path is the finding
        report["strict_load"] = f"RAISED: {exc}"
    return report


def run_split(hypes_base, ckpt_dir, split_dir, num_workers):
    from torch.utils.data import DataLoader
    from tqdm import tqdm

    from opencood.data_utils.datasets import build_dataset
    from opencood.tools import inference_utils, train_utils
    from opencood.utils import eval_utils

    hypes = copy.deepcopy(hypes_base)
    hypes["validate_dir"] = split_dir

    dataset = build_dataset(hypes, visualize=False, train=False)
    loader = DataLoader(
        dataset,
        batch_size=1,
        num_workers=num_workers,
        collate_fn=dataset.collate_batch_test,
        shuffle=False,
        pin_memory=False,
        drop_last=False,
    )

    model = train_utils.create_model(hypes)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    _, model = train_utils.load_saved_model(ckpt_dir, model)
    model.eval()

    result_stat = {t: {"tp": [], "fp": [], "gt": 0, "score": []} for t in (0.3, 0.5, 0.7)}
    with torch.no_grad():
        for batch_data in tqdm(loader, desc=os.path.basename(split_dir)):
            batch_data = train_utils.to_device(batch_data, device)
            pred_box, pred_score, gt_box = inference_utils.inference_intermediate_fusion(
                batch_data, model, dataset
            )
            for t in (0.3, 0.5, 0.7):
                eval_utils.caluclate_tp_fp(pred_box, pred_score, gt_box, result_stat, t)

    out = {"frames": len(dataset), "gt_boxes": {str(t): result_stat[t]["gt"] for t in (0.3, 0.5, 0.7)}}
    # `eval_utils.calculate_ap` cumsums result_stat's tp/fp lists IN PLACE, so it is not idempotent:
    # scoring twice off one result_stat gives nonsense the second time. Hand it a fresh copy each
    # call. (OpenCOOD never hits this because inference.py scores once per convention.)
    for gs in (False, True):
        key = "global_sort" if gs else "no_global_sort"
        out[key] = {
            f"ap_{int(t * 100)}": float(
                eval_utils.calculate_ap(copy.deepcopy(result_stat), t, gs)[0]
            )
            for t in (0.3, 0.5, 0.7)
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt-dir", required=True, help="converted variant directory")
    ap.add_argument("--original-ckpt-dir", help="the unconverted zoo directory, for the E1 report")
    ap.add_argument("--data-root", required=True, help="OPV2V root holding the split directories")
    ap.add_argument("--opencood", required=True, help="OpenCOOD repo root (README = target source)")
    ap.add_argument("--splits", nargs="+", default=["test", "test_culver_city"])
    ap.add_argument("--tolerance", type=float, default=0.005)
    ap.add_argument("--num-workers", type=int, default=8)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sys.path.insert(0, args.opencood)
    import opencood.hypes_yaml.yaml_utils as yaml_utils

    variant = os.path.basename(os.path.normpath(args.ckpt_dir))
    targets = zoo_targets_from_readme(args.opencood)
    assert variant in targets, f"no zoo target for variant {variant!r}"
    variant_targets = targets[variant]

    hypes = yaml_utils.load_yaml(os.path.join(args.ckpt_dir, "config.yaml"), None)

    record = {
        "schema": "catosg-p4b-verification/1",
        "protocol": "CA-TOSG P4-B-c expectation E4 (docs/experiment_protocol.md)",
        "generated_by": "python tools/verify_second_zoo_ap.py",
        "generated": datetime.now(timezone.utc).isoformat(),
        "variant": variant,
        "ckpt_dir": args.ckpt_dir,
        "fusion_method": "intermediate",
        "ap_convention_for_pass_fail": "no_global_sort (the zoo's own convention)",
        "tolerance": args.tolerance,
        "zoo_targets": targets,
        "environment": {"torch": torch.__version__, "cuda": torch.cuda.is_available()},
        "load_check": load_check(hypes, args.ckpt_dir, args.original_ckpt_dir),
        "splits": {},
    }

    verdicts = []
    for split in args.splits:
        split_dir = os.path.join(args.data_root, split)
        assert os.path.isdir(split_dir), f"{split_dir} not found"
        res = run_split(hypes, args.ckpt_dir, split_dir, args.num_workers)
        target = variant_targets[split]
        observed = res["no_global_sort"]["ap_70"]
        delta = observed - target
        ok = abs(delta) <= args.tolerance
        verdicts.append(ok)
        res.update(
            {
                "zoo_target_ap_70": target,
                "observed_ap_70_no_global_sort": observed,
                "delta": delta,
                "within_tolerance": ok,
            }
        )
        record["splits"][split] = res
        print(
            f"[{split}] AP@0.7 (no global sort) = {observed:.4f}  target {target:.3f}  "
            f"delta {delta:+.4f}  -> {'PASS' if ok else 'FAIL'}"
        )

    record["verdict"] = "PASS" if all(verdicts) else "FAIL"
    record["meaning"] = (
        "PASS: the layout-converted checkpoint reproduces the published AP within tolerance, so it "
        "is the official weights losslessly reordered. FAIL: the conversion is NOT established and "
        "P4-B stays blocked -- nothing is retuned to make a number fit (E5)."
    )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(record, f, indent=1)
        f.write("\n")
    print(f"\nVERDICT: {record['verdict']}   -> {args.out}")
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
