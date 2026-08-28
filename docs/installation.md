# Installation

CPU is enough for everything except the detector inference that produces the per-frame caches
(see `docs/dataset.md`); the selector, the replay, the sensitivity sweep and all gates are CPU-only.

## 1. Environment

```bash
conda env create -f environment.yml
conda activate catosg
```

The frozen manifests pin the exact versions the models were trained under, and
`tests/test_data_leakage.py` reads them back:

| package | pinned |
|---|---|
| python | 3.10.18 |
| scikit-learn | 1.7.0 |
| numpy | 1.26.4 |
| pandas | 2.2.2 |

A different scikit-learn will not reproduce the frozen `model_sha256` values byte-for-byte.

`requirements.txt` is the pip equivalent; `requirements-no-torch-spconv.txt` is the analysis-only
subset (no torch, no spconv): enough for the selector, the replay, and the content-tier checks
(`python tools/verify_results.py --content-only`).

## 2. Sionna (physical layer)

`tools/build_bler_table.py` needs Sionna (`sionna.phy`) and TensorFlow. It is only required to
*regenerate* the BLER tables; `results/channel/bler_sionna*.csv` are committed, so every downstream
command runs without it.

## 3. The OpenCOOD checkout

This repository evaluates a cooperative-perception stack that lives in a **sibling** OpenCOOD
checkout — the manifests refer to it as `../OpenCOOD/`:

```
cooperative_semantic_perception/
├── ca-tosg/        <- this repository
└── OpenCOOD/       <- sibling checkout, provides the detector + per-frame cue CSVs
```

The edits this work makes to OpenCOOD (each marked `#self+` on line 1 of the file) are listed in
`docs/opencood_modifications.md`. Detector inference, and only that, needs a CUDA GPU and spconv.

## 4. Check the install

```bash
python tools/verify_results.py --content-only
```

Expected on a clean clone: `ALL GATES PASS (content tier only)`. The full run
(`python tools/verify_results.py`, no flag) additionally needs the git-excluded `data/p2/` grids and
models and the sibling OpenCOOD checkout; without them its fourteen artefact-tier gates fail loudly by
design rather than skipping — a gate that cannot verify must never report success. The two tiers are
spelled out in `docs/reproducibility.md` §5; `docs/dataset.md` says how to rebuild the artefacts.
