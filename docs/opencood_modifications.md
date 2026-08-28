# OpenCOOD Namespace Modifications

The upstream OpenCOOD package at `../../opencood/` is mostly untouched. The exceptions are **12 newly added files** and **6 modified files**. Most carry a `#self+ ...` header on line 1, but that convention has proven unreliable (see the inventory corrections below). **The authority is `results/manifests/V2_SIBLING_DEPENDENCY.json`, which is machine-checked by gate 24; this page is prose around it.**

These files **physically live in `../../opencood/`** rather than in this directory, because they participate in the `opencood` Python namespace (e.g., `from opencood.models.point_pillar_importance_map_jscc import ...`) and the OpenCOOD codebase resolves model and fusion modules by string name from `hypes_yaml/` configs. Moving them out would require updating dozens of import sites and config strings, breaking compatibility with the upstream training and inference pipelines.

## Files added by the user

| File | Purpose |
|---|---|
| `opencood/models/point_pillar_importance_map_jscc.py` | Top-level perception model wrapper that dispatches to ImportanceMapJSCC / SComCP fuse modules via the `variant:` field. |
| `opencood/models/fuse_modules/importance_map_jscc_fuse.py` | ImportanceMapJSCC fuse module — importance-mask selector + CNN JSCC codec + AWGN / Rayleigh / OFDM / LDPC-QAM channel models. Reproduction of Sheng et al., *J. Franklin Inst.* 2024. |
| `opencood/models/fuse_modules/scomcp_fuse.py` | SComCP fuse module — cross-attention selector + Transformer-CA JSCC codec. Reproduction of Gan et al., *IEEE TVT* 2026. |
| `opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml` | ImportanceMapJSCC config, AWGN channel. |
| `opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn_learned.yaml` | Same, with learned importance source. |
| `opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh.yaml` | ImportanceMapJSCC config, Rayleigh. |
| `opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh_learned.yaml` | Same, with learned importance source. |
| `opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm.yaml` | ImportanceMapJSCC config, OFDM. |
| `opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm_learned.yaml` | Same, with learned importance source. |
| `opencood/hypes_yaml/point_pillar_where2comm_local.yaml` | Local Where2comm eval config (OPV2V validate split). |

## Files modified by the user

| File | Modification |
|---|---|
| `opencood/hypes_yaml/visualization.yaml` | Local OPV2V validate / test path overrides. |
| `opencood/models/fuse_modules/where2comm_fuse.py` | Extensions for compatibility with the ImportanceMapJSCC / SComCP fuse module signature (additional output keys, optional `paper_*` diagnostics). |
| `opencood/utils/eval_utils.py` | Added per-frame payload tracking + channel-use-equivalent bandwidth metrics used by Paper #2's evaluation pipeline. |

## How to spot a user-added file

Open the file. If line 1 starts with `#self+`, it is user-added or user-modified. Otherwise it is pristine upstream OpenCOOD.

## Cleaning up later

If at some point the user wants to fully relocate the namespace-resident code out of `../../opencood/`, the recommended approach is:

1. Physically move each file to `peiyi_work/00_opencood_modifications/` under the same relative path (e.g., `models/point_pillar_importance_map_jscc.py`).
2. Create symlinks at the original locations so the existing `opencood.*` imports keep resolving.
3. For the 3 modified files, hold a separate `*.patch` next to the original; the upstream copy stays unchanged.

This is documented here for the user's future reference; **at present, the cleaner state is to leave the files in `../../opencood/` and rely on the `#self+` headers for discoverability.**

## P4-C collaborator-subset mask (2026-08-13)

| file | edit |
|---|---|
| `opencood/utils/catosg_collab_subset.py` | **new** `#self+` module: ego + the N nearest collaborators by `lidar_pose[0:2]` distance, ties by ascending CAV id. Off unless `CATOSG_MAX_COLLAB` (or `CATOSG_KEEP_CAVS`) is set. |
| `opencood/data_utils/datasets/late_fusion_dataset.py` | one call in `get_item_test`, after the ego pose is found and **before** the CAV loop. |
| `opencood/data_utils/datasets/intermediate_fusion_dataset.py` | one call in `__getitem__`, **before** `get_pairwise_transformation` (which is built from the CAV set). |

Verified both ways before use, on 20 validate frames:
- variable **unset** → output bit-identical to the pre-patch code (0/20 frames differ in boxes,
  scores and gts), and two identical runs also agree, so the pipeline is deterministic;
- `CATOSG_MAX_COLLAB=1` → output differs on **exactly** the frames whose collaborator count exceeds
  1, and on no others.

`max_cav` is deliberately not used for this: its selection order is a loader-internal detail this
project has not pinned, and an experimental arm must not depend on unverified behaviour.

## Inventory correction (P0-4, 2026-08-16)

This page said "9 added / 3 modified". The tree has **11 added / 5 modified**. The files it did not list are:

| file | state | note |
|---|---|---|
| `opencood/models/fuse_modules/scomcp_fuse.py` | added | SComCP reproduction; the arm is archived as a negative reproduction and is not in the paper |
| `opencood/utils/catosg_collab_subset.py` | added | restricts the fused CAV set — the mechanism behind the P4-C arms and the P0 N=1 correction |
| `opencood/data_utils/datasets/intermediate_fusion_dataset.py` | modified | collaborator-subset hook |
| `opencood/data_utils/datasets/late_fusion_dataset.py` | modified | collaborator-subset hook |

**Two modified files carry no `#self+` marker on line 1**, so the documented way to spot a user-modified file does not find them: `opencood/data_utils/datasets/intermediate_fusion_dataset.py`, `opencood/data_utils/datasets/late_fusion_dataset.py`. They are listed here instead; the marker convention is the thing that is unreliable, not the inventory.

The whole set is now exported as portable patches in `patches/opencood/` and applied or checked with `python tools/apply_opencood_patches.py --check|--apply`, so a fresh OpenCOOD checkout can be brought to this state without copying a working tree.

## Inventory correction (V2-R20 D, 2026-08-28) — and this page stops being the authority

This page said "11 added / 5 modified". The tree has **12 added / 6 modified**. Missing were the two
files the V2-R16 determinism fix introduced:

| file | state | note |
|---|---|---|
| `opencood/utils/catosg_eval_rng.py` | added | per-sample deterministic RNG keyed on `(split, scene, frame, cav)`; **v2-critical** |
| `opencood/utils/pcd_utils.py` | modified | `shuffle_points(points, rng=None)`; `None` reproduces the old global behaviour exactly; **v2-critical** |

Worse than the page being stale: **`patches/opencood/` was stale too.** `--check` reported
**15 applied and 1 CONFLICT** — `intermediate_fusion_dataset.py`'s patch predated the RNG threading,
and the two files above had no patch at all. So the portable form, which exists precisely so that a
fresh checkout can reproduce the products, could not have reproduced them. Re-exporting moved
**exactly those three files**; the other fifteen patches came back byte-identical, which is what
established that they were the only drift. Now **18 applied, 0 conflicts**.

**This is the third time this inventory has drifted** (9/3 → 11/5 → 12/6), which is the argument for
not keeping counts by hand. The counts, the file list, the base commit and every content hash now
live in `results/manifests/V2_SIBLING_DEPENDENCY.json`, rebuilt by
`tools/build_sibling_dependency_manifest.py` and verified by gate 24 on every run. **If this page and
that manifest disagree, the manifest is right.**

`python tools/apply_opencood_patches.py --export` and the manifest rebuild are now on the batch
closing checklist in `docs/HANDOFF_V2.md`, because the step existed and was simply never listed.
