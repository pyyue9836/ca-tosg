# CA-TOSG — Channel- and Task-Aware Object-Level Communication for Bandwidth-Constrained V2V Cooperative Perception

_All mainline results use the single-collaborator protocol; exceptions (SECOND appendix, Where2comm reference) are labeled where they appear. Tag `pre-p0-corrigendum` marks the pre-correction state._

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Per-frame, receiver-driven selection of *what the collaborator transmits* in vehicle-to-vehicle
cooperative perception, under a mean per-frame communication budget, with every message charged
through a measured LDPC/QAM chain.

## Overview

![CA-TOSG framework](figs/ca_tosg_overview.svg)

## Main idea

The ego vehicle decides, **once per frame**, which representation its collaborator should send,
using only what it already has on the ego side: ego-local perception and availability cues plus an
estimated SNR and channel type. It signals the choice with a two-bit request and the collaborator
complies.

| Action | Message |
|---|---|
| **E** | ego-only, transmit nothing |
| **L** | object-level (boxes + scores) |
| **F** | feature-level (int8 bottleneck) |

The candidate action set is {E, L, F}. **The policy frozen on the development split has support
{E, L}**: as an always-on policy Fixed F costs several times the primary budget, and the frozen
selector never requests it. F is retained as an over-budget fixed-action reference and as the
object of the transport study.

Every message is packetised, LDPC-coded and modulated, and charged in channel uses — payload is
measured, not declared.

## Results

The paper reports three measured results, all under one detector, one field of view and one ground
truth:

1. **At matched realised payload**, the selector exceeds a random selector, an ego-cue threshold and
   an SNR threshold on the Test split, with every pairwise 95% scene-level bootstrap lower bound
   above zero. On Culver-City it has the highest point estimate and the interval against the SNR
   threshold includes zero.
2. **Against always transmitting object level**, it uses substantially less cooperative-perception
   payload at a small scene-equal F1 difference.
3. **Loss position at fixed loss amount** changes the detection outcome, so transport loss affects
   perception through where it falls and not only how much is lost.

The **preregistered** comparison against the frozen SNR-threshold policy is reported with its
outcome: a large payload reduction for which the scene-level non-inferiority criterion was **not**
met on either held-out split.

**Where the numbers live.** Every figure in the manuscript is emitted by
`tools/build_v2_paper_numbers.py` from the closed-out products; none is typed by hand. This README
deliberately carries no result cells, so it cannot drift from them.

* `results/manifests/V2_CLOSEOUT.json` — the closed experiment.
* `results/manifests/PUBLICATION.json` — the manuscript and its inputs, hashed.
* `paper/main.pdf`, `paper/supplementary.pdf` — the results themselves.
* `results/README.md` — an index of every result file.

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
`docs/model_zoo.md`. The table below is written by `tools/build_readme_tables.py` from
`results/manifests/FROZEN_MANIFEST.json`; do not edit it by hand.

| B_max (mean Msym/frame) | model | λ\* | τ\* | LOSO OOF F1 | frozen validate payload |
|---|---|---|---|---|---|
| 0.10 | `selector_B010` | 0.05 | 18.0 dB | 0.8555 | 0.080803 |
| 0.20 | `selector_B020` | 0.02 | 12.0 dB | 0.8606 | 0.150158 |
| 0.30 | `selector_B030` | 0.00 | 8.0 dB | 0.8622 | 0.201607 |

## Reproduction

```bash
python tools/build_bler_table.py      # physical layer: Sionna 5G-LDPC + QAM BLER tables
python tools/evaluate_ap.py           # true end-to-end AP under the frozen selectors
python tools/run_sensitivity.py       # the sensitivity items
python tools/run_baselines.py contextual_bandit --train --evaluate
python tools/generate_figures.py      # every figure main.tex includes
python tools/verify_results.py        # all 35 gates (--content-only = the 19 a clean clone can run)
python tools/apply_opencood_patches.py --check   # the OpenCOOD modifications this project needs
```

The protocol these commands implement — split roles, candidate set, selection and freeze rules —
is `docs/experiment_protocol.md`, and it is the only normative source. `projects/ca_tosg/configs/*.yaml`
are generated from it; `tests/test_manifest.py` re-checks the md5 of every protocol block a config
claims to come from, and byte-compares the regenerated files, so the two cannot drift.

## License

Apache-2.0 — see [`LICENSE`](LICENSE). Copyright 2026 Peiyi Yue, University of Bristol.
The OpenCOOD code this work builds on carries its own licence in the sibling checkout.

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
