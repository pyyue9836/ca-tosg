# CA-TOSG (Channel-Aware Task-Oriented Semantic Granularity Selection for V2V Cooperative Perception)

Per-frame selection of *how much semantics to transmit* in vehicle-to-vehicle cooperative
perception, under a hard per-frame channel-use budget.

## Overview

![CA-TOSG framework](figs/ca_tosg_overview.svg)

## Main idea

The ego vehicle decides, **once per frame**, between three message granularities, using only what
it already has on the ego side — task cues from its own detection, an estimated SNR, and the
channel state:

| Action | Message | Channel use |
|---|---|---|
| **E** | ego-only, transmit nothing | 0 |
| **L** | object-level (boxes + scores) | 0.024 Msym |
| **F** | feature-level (compressed BEV features) | 0.99 Msym |

A feature message is worth its 41× cost only when the channel will actually deliver it *and* the
frame is one where cooperation helps. A random forest over 23 ego-side cues makes that call per
frame; the physical layer (5G-LDPC rate-1/2 + 16/256-QAM, Sionna frame-level BLER) decides whether
the request survives, with ego-only as the failure fallback. One model is frozen per budget.

## Results

Held-out **test** split, 200-realisation deployment (per frame SNR ~ U[0,20] dB, Rayleigh with
probability 0.5), against a budget-matched SNR-threshold policy. Payload in Msym/frame.

| B_max | policy | F1 | payload | AP@0.5 |
|---|---|---|---|---|
| 0.10 | CA-TOSG | 0.9033 | **0.0680** | 0.9181 |
| 0.10 | SNR-threshold | 0.9027 | 0.0724 | 0.9189 |
| 0.20 | CA-TOSG | 0.9046 | **0.0947** | 0.9182 |
| 0.20 | SNR-threshold | 0.9074 | 0.2168 | 0.9190 |
| 0.30 | CA-TOSG | 0.9073 | **0.1870** | 0.9187 |
| 0.30 | SNR-threshold | 0.9094 | 0.3125 | 0.9174 |

Reference points on the same split: Fixed-L AP@0.5 = 0.9189, feature-ceiling = 0.9216, ego-only
= 0.7350. At B_max = 0.20 the selector spends **56% less channel use** than the budget-matched
threshold, for a 0.003 F1 difference.

Sources: `results/main/replay_summary.csv`, `results/main/true_e2e_ap.csv`. Every number in the
manuscript is indexed by `docs/claims.md`; every result file by `results/README.md`.

## Installation

```bash
conda env create -f environment.yml && conda activate catosg
```

Full instructions, including the sibling OpenCOOD checkout this repository evaluates against:
`docs/installation.md`.

## Dataset

OPV2V. Download, the expected directory layout, and the per-frame cue CSVs the selector trains on:
`docs/dataset.md`.

## Getting started

```bash
python tools/prepare_data.py          # frame x SNR x channel grid + scene manifest
python tools/train_selector.py        # LOSO selection + freeze, one model per budget
python tools/evaluate_selector.py     # 200-realisation deployment replay
```

Shortest path from raw OPV2V to the table above: `docs/getting_started.md`.

## Model Zoo

Three frozen selectors, one per budget. sha256, hyper-parameters and the full freeze record:
`docs/model_zoo.md`.

| Budget | model | λ\* | τ\* | LOSO OOF F1 | frozen validate payload |
|---|---|---|---|---|---|
| 0.10 | `selector_B010` | 0.05 | 18.0 dB | 0.9070 | 0.0679 |
| 0.20 | `selector_B020` | 0.02 | 12.0 dB | 0.9087 | 0.0992 |
| 0.30 | `selector_B030` | 0.00 | 8.0 dB | 0.9094 | 0.1570 |

## Reproduction

```bash
python tools/build_bler_table.py      # physical layer: Sionna 5G-LDPC + QAM BLER tables
python tools/evaluate_ap.py           # true end-to-end AP under the frozen selectors
python tools/run_sensitivity.py       # the sensitivity items
python tools/run_baselines.py contextual_bandit --train --evaluate
python tools/generate_figures.py      # every figure main.tex includes
python tools/verify_results.py        # all gates; exit 0 iff the tree is self-consistent
```

The protocol these commands implement — split roles, candidate set, selection and freeze rules —
is `docs/experiment_protocol.md`, and it is the only normative source. `projects/ca_tosg/configs/*.yaml`
are generated from it; `tests/test_manifest.py` re-checks the md5 of every protocol block a config
claims to come from, and byte-compares the regenerated files, so the two cannot drift.

## Citation

```bibtex
@unpublished{yue2026catosg,
  author = {Yue, Peiyi},
  title  = {Task-Oriented Semantic Granularity Selection for Bandwidth-Constrained
            V2V Cooperative Perception},
  note   = {Manuscript in preparation, University of Bristol},
  year   = {2026}
}
```

<sub>`paper2/` and `paper3/` are empty placeholders for future work and are untouched by this
layout.</sub>
