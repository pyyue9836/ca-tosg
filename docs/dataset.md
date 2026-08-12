# Dataset

## OPV2V

Download OPV2V from the [official release](https://mobility-lab.seas.ucla.edu/opv2v/) and place
the dumping tree inside the sibling OpenCOOD checkout:

```
../OpenCOOD/opv2v_data_dumping/
├── validate/          9 scenes, 1980 frames   <- the ONLY split any fitting touches
├── test/              scene-disjoint          <- one-shot final test
└── test_culver_city/  domain shift            <- one-shot final test
```

Split roles are not a convention here, they are enforced: `docs/experiment_protocol.md` §1 states
the hard bans and `tests/test_data_leakage.py` fails the tree if one is violated.

## What the selector actually trains on

The selector never reads point clouds. It reads two derived tables:

| input | path | produced by |
|---|---|---|
| per-frame ego cues + per-policy F1 | `../OpenCOOD/peiyi_work/paper1/data/dataset_{split}.csv` | detector inference (GPU) |
| frame × SNR × channel grid | `data/p2/p2_grid_{split}.csv` | `python tools/prepare_data.py` |

The grid is the deterministic product **frame × 11 SNR points × 2 channels** (§3), built *after*
the scene partition — never the other way round, which would put channel copies of one scene on
both sides of a split boundary.

```bash
python tools/prepare_data.py --split validate        # -> data/p2/p2_grid_validate.csv
python tools/prepare_data.py --scene-manifest        # -> results/manifests/scene_manifest_validate.csv
```

## What is not in git

`data/`, `experiment_logs/`, `pretrained_models/`, `gs_rerun/` and every `*.pkl / *.pth / *.npz`
are git-excluded: they are large and regenerable. Caches that cost GPU hours to rebuild are
registered in `docs/data_manifest.md` with their md5 and regeneration command, and **a cleanup may
only delete files that are not in that manifest**.
