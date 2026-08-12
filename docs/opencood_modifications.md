# OpenCOOD Namespace Modifications

The upstream OpenCOOD package at `../../opencood/` is mostly untouched. The exceptions are listed below: **9 newly added files** and **3 modified files**, all marked with a `#self+ ...` header on line 1.

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
