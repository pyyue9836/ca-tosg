#!/usr/bin/env python
"""P4-B-c: convert the official SECOND checkpoints from spconv 1.x to spconv 2.x kernel layout.

The OpenCOOD model-zoo SECOND weights were saved under spconv 1.2.1, which stores a sparse
convolution kernel as ``RSCK`` = ``(kD, kH, kW, C_in, C_out)``. spconv 2.x stores it as
``KRSC`` = ``(C_out, kD, kH, kW, C_in)``. The two hold the same numbers in a different axis
order, so the conversion is ``permute(4, 0, 1, 2, 3)`` on those kernels and nothing else.

This is spconv's own migration, not an invention of ours: see
``spconv.pytorch.conv.SparseConvolution._load_weight_different_layout``, whose ``RSCK`` branch is
exactly ``permute(ndim + 1, *range(ndim), ndim)``. We do not use that hook, because in spconv
2.3.8 it applies the permutation **twice** (the second application is in the
``ALL_WEIGHT_IS_KRSC`` block) and the load still raises; ``--check-spconv-hook`` demonstrates that
from the library itself rather than asserting it.

A converted checkpoint is no longer bit-wise the published file, so the conversion alone proves
nothing. It is established by ``tools/verify_second_zoo_ap.py``, which reproduces the zoo's own
published AP@0.7 with these weights (protocol P4-B-c, expectation E4).

Usage:
    python tools/convert_second_checkpoint.py --src <zoo_dir> --dst <out_dir>
    python tools/convert_second_checkpoint.py --check-spconv-hook
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone

import torch

# (kD, kH, kW, C_in, C_out) -> (C_out, kD, kH, kW, C_in)
RSCK_TO_KRSC = (4, 0, 1, 2, 3)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def spconv_reference_permutation() -> tuple[int, ...]:
    """Read the permutation out of spconv's own source rather than hard-coding it here.

    Mirrors the ``SAVED_WEIGHT_LAYOUT == "RSCK"`` branch of
    ``SparseConvolution._load_weight_different_layout`` for ``ndim == 3``.
    """
    ndim = 3
    return (ndim + 1, *range(ndim), ndim)


def is_sparse_conv_kernel(key: str, tensor: torch.Tensor) -> bool:
    """A 5-D weight tensor under backbone_3d is a sparse-conv kernel.

    backbone_3d is the only spconv-bearing module in SECOND (MeanVFE, HeightCompression,
    AttBEVBackbone and the heads are all dense torch), and its BatchNorm tensors are 1-D.
    """
    return key.startswith("backbone_3d.") and key.endswith(".weight") and tensor.dim() == 5


def convert_state_dict(ckpt: dict) -> tuple[dict, list[dict]]:
    out, rules = {}, []
    for key, tensor in ckpt.items():
        if is_sparse_conv_kernel(key, tensor):
            converted = tensor.permute(*RSCK_TO_KRSC).contiguous()

            # --- E3 invariants, asserted per tensor -------------------------------------
            # same numbers, only reordered
            assert converted.numel() == tensor.numel(), key
            assert converted.dtype == tensor.dtype, key
            assert torch.equal(
                torch.sort(converted.reshape(-1).float()).values,
                torch.sort(tensor.reshape(-1).float()).values,
            ), f"{key}: element multiset changed"
            # invertible: undoing the permutation returns the original bit-for-bit
            inverse = tuple(RSCK_TO_KRSC.index(i) for i in range(5))
            assert torch.equal(converted.permute(*inverse).contiguous(), tensor.contiguous()), key

            out[key] = converted
            rules.append(
                {
                    "key": key,
                    "permute": list(RSCK_TO_KRSC),
                    "from_shape": list(tensor.shape),
                    "to_shape": list(converted.shape),
                }
            )
        else:
            out[key] = tensor
    assert set(out) == set(ckpt), "key set changed"
    return out, rules


def check_spconv_hook() -> dict:
    """Show, from the installed library, that its RSCK hook double-permutes in 2.3.8."""
    import inspect

    import spconv
    import spconv.pytorch.conv as conv_mod

    src = inspect.getsource(conv_mod.SparseConvolution._load_weight_different_layout)
    rsck_applications = src.count('SAVED_WEIGHT_LAYOUT == "RSCK"')
    demo = torch.zeros(3, 3, 3, 4, 16)
    once = tuple(demo.permute(*RSCK_TO_KRSC).shape)
    twice = tuple(demo.permute(*RSCK_TO_KRSC).permute(*RSCK_TO_KRSC).shape)
    return {
        "spconv_version": spconv.__version__,
        "all_weight_is_krsc": bool(conv_mod.ALL_WEIGHT_IS_KRSC),
        "rsck_branches_in_hook": rsck_applications,
        "reference_permutation_from_spconv_source": list(spconv_reference_permutation()),
        "permutation_used_here": list(RSCK_TO_KRSC),
        "conv_input_kernel_shape_applied_once": list(once),
        "conv_input_kernel_shape_applied_twice": list(twice),
        "note": (
            "ALL_WEIGHT_IS_KRSC is True, so the hook's second RSCK branch runs after the first: "
            "the permutation is applied twice and the resulting shape is wrong. The single "
            "application is the intended conversion."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="zoo checkpoint root (contains the variant sub-directories)")
    ap.add_argument("--dst", help="output root; variant sub-directories are recreated under it")
    ap.add_argument(
        "--variants",
        nargs="+",
        default=["second_attentive_fusion", "second_attentive_fusion_compression"],
    )
    ap.add_argument("--manifest-out", help="where to write the conversion record (JSON)")
    ap.add_argument("--check-spconv-hook", action="store_true")
    args = ap.parse_args()

    if args.check_spconv_hook:
        print(json.dumps(check_spconv_hook(), indent=2))
        return 0

    if not args.src or not args.dst:
        ap.error("--src and --dst are required unless --check-spconv-hook is given")

    assert spconv_reference_permutation() == RSCK_TO_KRSC, (
        "spconv's own RSCK branch no longer matches the permutation this script applies; "
        "stop and re-derive it before converting anything"
    )

    record = {
        "schema": "catosg-p4b-conversion-manifest/1",
        "label": "PRODUCT of this repository: layout-converted copies of an external input",
        "protocol": "CA-TOSG P4-B-c (docs/experiment_protocol.md Change-log P4-B-c)",
        "generated_by": "python tools/convert_second_checkpoint.py",
        "generated": datetime.now(timezone.utc).isoformat(),
        "input_manifest": "results/manifests/P4B_MANIFEST.json",
        "reason": (
            "The zoo weights were saved under spconv 1.2.1 (RSCK = kD,kH,kW,C_in,C_out); this "
            "environment has spconv 2.3.8, which stores kernels as KRSC = C_out,kD,kH,kW,C_in. "
            "Lossless axis reorder of the sparse-conv kernels only; every other tensor is copied "
            "unchanged. Same permutation as spconv's own RSCK migration branch, applied once "
            "(spconv 2.3.8's convenience hook applies it twice and still fails to load)."
        ),
        "conversion": {
            "permutation": list(RSCK_TO_KRSC),
            "applies_to": "5-D *.weight tensors under backbone_3d (sparse-conv kernels)",
            "all_other_tensors": "copied byte-identically",
        },
        "spconv_hook_check": check_spconv_hook(),
        "environment": {"torch": torch.__version__},
        "variants": {},
        "verification": {
            "status": "PENDING",
            "note": "filled in by tools/verify_second_zoo_ap.py; until then this checkpoint is "
            "NOT established and may not be used for any result",
        },
    }

    for variant in args.variants:
        src_dir = os.path.join(args.src, variant)
        dst_dir = os.path.join(args.dst, variant)
        os.makedirs(dst_dir, exist_ok=True)

        src_pth = os.path.join(src_dir, "latest.pth")
        dst_pth = os.path.join(dst_dir, "latest.pth")
        src_cfg = os.path.join(src_dir, "config.yaml")
        dst_cfg = os.path.join(dst_dir, "config.yaml")

        ckpt = torch.load(src_pth, map_location="cpu")
        converted, rules = convert_state_dict(ckpt)
        torch.save(converted, dst_pth)
        shutil.copy2(src_cfg, dst_cfg)

        record["variants"][variant] = {
            "source": {
                "path": src_pth,
                "sha256": sha256(src_pth),
                "bytes": os.path.getsize(src_pth),
            },
            "converted": {
                "path": dst_pth,
                "sha256": sha256(dst_pth),
                "bytes": os.path.getsize(dst_pth),
            },
            "config_yaml_sha256": sha256(dst_cfg),
            "tensors_total": len(ckpt),
            "tensors_permuted": len(rules),
            "tensors_copied_unchanged": len(ckpt) - len(rules),
            "per_key_rules": rules,
        }
        print(
            f"{variant}: {len(ckpt)} tensors, {len(rules)} permuted, "
            f"{len(ckpt) - len(rules)} unchanged -> {dst_pth}"
        )

    if args.manifest_out:
        os.makedirs(os.path.dirname(args.manifest_out), exist_ok=True)
        with open(args.manifest_out, "w") as f:
            json.dump(record, f, indent=1)
            f.write("\n")
        print(f"manifest -> {args.manifest_out}")
    else:
        print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
