# Model Zoo

_All numbers reflect the P0-corrected single-collaborator protocol (tag `pre-p0-corrigendum` marks the pre-correction state)._

Three frozen selectors, one per bandwidth budget. Every field below is read from
`results/manifests/FROZEN_MANIFEST.json`, which is the freeze record: the sha256 is verified
before the model is loaded by every evaluation command, so a swapped or retrained `.pkl` is
a hard failure, not a silent difference.

**Frozen** 2026-08-09 15:12:53 UTC, seed 0, python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2.2.2.

The model binaries live in `data/p2/` and are **git-excluded** (35-60 MB each); rebuild them
with `python tools/train_selector.py`, which re-audits the walk winners against this manifest
and refuses to overwrite on a mismatch.

| budget | model | candidate | walk depth | λ\* | τ\* | max_depth | min_samples_leaf | sha256 |
|---|---|---|---|---|---|---|---|---|
| 0.10 | `selector_B010` | #58 | 6 / 90 | 0.05 | 18.0 dB | None | 2 | `d15efbe0f5b69a0b…` |
| 0.20 | `selector_B020` | #1 | 2 / 107 | 0.02 | 12.0 dB | 10 | 2 | `fc9c2c0b5661bca4…` |
| 0.30 | `selector_B030` | #56 | 0 / 112 | 0.0 | 8.0 dB | None | 2 | `ed77c2c7c8fbaefd…` |

All three use `n_estimators=400`, `max_features="sqrt"`, `class_weight=None` (the class cost
is carried by λ, not by re-weighting).

| budget | LOSO frame-weighted OOF F1 | LOSO scene-mean F1 | LOSO OOF payload | frozen validate F1 | frozen validate payload | ≤ B_max |
|---|---|---|---|---|---|---|
| 0.10 | 0.907 | 0.907 | 0.055978 | 0.9111 | 0.067887 | yes |
| 0.20 | 0.9087 | 0.9082 | 0.197463 | 0.9118 | 0.099231 | yes |
| 0.30 | 0.9094 | 0.9101 | 0.245147 | 0.9133 | 0.156962 | yes |

## Per-class behaviour (frozen, validate)

| budget | | precision | recall | F1 | support |
|---|---|---|---|---|---|
| 0.10 | **E** | 0.9975 | 1.0 | 0.9988 | 401 |
|  | **L** | 0.9997 | 1.0 | 0.9998 | 41156 |
|  | **F** | 1.0 | 0.993 | 0.9965 | 2003 |
| 0.20 | **E** | 0.9819 | 0.9844 | 0.9831 | 385 |
|  | **L** | 0.9744 | 0.9974 | 0.9858 | 38855 |
|  | **F** | 0.9685 | 0.7627 | 0.8534 | 4320 |
| 0.30 | **E** | 1.0 | 1.0 | 1.0 | 335 |
|  | **L** | 0.9994 | 1.0 | 0.9997 | 37197 |
|  | **F** | 1.0 | 0.996 | 0.998 | 6028 |

## Inputs pinned by the freeze

| input | file | hash |
|---|---|---|
| `train_grid` | `data/p2/p2_grid_validate.csv` | `3314418d4e53ff30…` |
| `cue_source` | `../OpenCOOD/peiyi_work/paper1/data/dataset_validate.csv` | `d357b38e802455bf…` |
| `bler_table` | `results/channel/bler_sionna.csv` | `be3f5e1278ddda6e…` |
| `folds_csv` | `results/manifests/validate_loso_folds.csv` | `8a394d9a32e0c4e2…` |
| `walk_B010` | `results/manifests/candidate_walk_B010.csv` | `16287a7a6b31b3af…` |
| `walk_B020` | `results/manifests/candidate_walk_B020.csv` | `f24963e5acce8243…` |
| `walk_B030` | `results/manifests/candidate_walk_B030.csv` | `7d2a97a0244363bf…` |

Deployment numbers for these models: `results/main/replay_summary.csv` (F1 / payload) and
`results/main/true_e2e_ap.csv` (AP). Latency at the batch-1 online operating point:
`results/latency/selector_latency.csv`.
