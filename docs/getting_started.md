# Getting started

Shortest path from OPV2V to the table in the root README. Steps 1–2 need the sibling OpenCOOD
checkout and a GPU; everything after that is CPU-only and runs in minutes.

## 0. Prerequisites

`docs/installation.md`, then OPV2V in place per `docs/dataset.md`.

## 1. Per-frame cues (GPU, once)

Detector inference produces `dataset_{split}.csv` — per frame: 21 ego-side cues and the F1 of each
policy (ego-only / object-level / feature-level). It is the one step this repository does not own;
it runs in the sibling OpenCOOD checkout and its outputs are md5-pinned by the frozen manifest.

## 2. Channel substrate

```bash
python tools/build_bler_table.py      # Sionna 5G-LDPC(500,1000) rate-1/2 + 16/256-QAM  (committed)
python tools/prepare_data.py          # frame x 11 SNR x 2 channels -> data/p2/
```

## 3. Train and freeze

```bash
python tools/train_selector.py
```

Reads the candidate block from `docs/experiment_protocol.md`, runs scene-level 9-fold LOSO over
112 candidates, walks the pre-registered order per budget, and freezes the first candidate whose
*frozen* full-validate payload satisfies the budget. Writes
`results/manifests/FROZEN_MANIFEST.json` + the walk evidence chain. Re-running with the same seed
re-audits the winners against the existing manifest and refuses to overwrite on a mismatch.

## 4. Evaluate

```bash
python tools/evaluate_selector.py     # 200-realisation replay -> results/main/replay_summary.csv
python tools/evaluate_ap.py           # true end-to-end AP     -> results/main/true_e2e_ap.csv
```

## 5. Check

```bash
python tools/verify_results.py        # ALL GATES PASS
python tools/generate_figures.py      # -> paper/figures/*.pdf
```

## Where things live

| | |
|---|---|
| `projects/ca_tosg/` | the method: models, datasets, communication, evaluation, utils |
| `tools/` | the only entry points you run |
| `projects/ca_tosg/configs/` | generated view of the protocol, md5-pinned to it |
| `baselines/` | where2comm, scomcp, importance_map_jscc, contextual_bandit |
| `results/` | every committed number; `results/README.md` says which command made each file |
| `tests/` | the gates |
| `docs/experiment_protocol.md` | the normative source for all of the above |
