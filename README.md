# CA-TOSG — Channel-Aware Task-Oriented Semantic Granularity Selection for Bandwidth-Constrained V2V Cooperative Perception

Code and paper source for the IEEE TVT submission (P. Yue, University of Bristol).

**Idea.** Instead of always sending a fixed message type, the ego vehicle picks
*per frame* between a compact object-level message **L** (≈0.024 Mbit) and a
compressed feature-level message **C** (LDPC + 16/256-QAM), using a lightweight
Random Forest over online perception cues + estimated channel state. Feature-level
communication is activated only when both the task state and the channel make it
worthwhile.

This repository is a **review snapshot of the paper's code path** (the
`peiyi_work/01_paper_ca_tosg/` subtree of a larger OpenCOOD working copy). Scripts
reference paths such as `opv2v_data_dumping/` and `peiyi_work/05_pretrained_models/`
that exist in that full tree; they are kept verbatim for traceability and are not
expected to run standalone without the dataset and pretrained checkpoints.

## Headline results (OPV2V validate, T = 1,980 frames; mean over SNR 0–20 dB, 50/50 AWGN/Rayleigh)

| Policy | Payload (Mbit/frame) | Mean F1 |
|---|---|---|
| Channel-aware oracle | 0.074 | 0.868 |
| Fixed L | 0.024 | 0.862 |
| Fixed C₁₆ (LDPC+16-QAM) | 0.495 | 0.385 |
| Fixed C₂₅₆ (LDPC+256-QAM) | 0.248 | 0.101 |
| **CA-TOSG (ours)** | **0.076** | **0.865** |

CA-TOSG recovers **99.7%** of the oracle's F1 at **84.6% less bandwidth** than Fixed C₁₆.

## Generalisation (validate-trained selector, applied without retraining)

| Split | Frames | Sel. acc | F1 / oracle | AWGN peak AP@0.5 (Fixed-L → ours) |
|---|---|---|---|---|
| OPV2V test (scene-disjoint) | 2,170 | 88.9% | 99.4% | 0.859 → 0.882 |
| OPV2V Culver-City (domain shift) | 550 | 91.3% | 99.6% | 0.799 → 0.853 |

Under Rayleigh fading the selector stays at the robust Fixed-L point across 0–20 dB
on all splits (deep fades make feature transmission unreliable). See `paper/main.tex`
§V for the full tables and figures.

## Repository layout

```
paper/                     LaTeX source (main.tex, refs.bib) + figures/  ← the paper
paper_overleaf.zip         ready-to-upload Overleaf bundle
test_split_pipeline/       test + Culver-City generalisation pipeline (5 stages + run_all.py)
  runs/                    OPV2V test-split result CSVs
  runs_culver/             Culver-City result CSVs
extra_figures/             scripts for the BLER curve and qualitative BEV figures
runs/                      selector training outputs (RF models *.pkl, per-frame CSVs, figures)
train_rf*.py               Random Forest selector training
true_e2e_ap_inference.py,
e2e_inference_verify.py     end-to-end AP verification
where2comm_compare.py      Where2comm baseline comparison
*.py                       analysis / plotting utilities
```

## Reproducing the generalisation result (inside the full OpenCOOD tree)

```bash
# regular OPV2V test split
CATOSG_SPLIT=test            PYTHONPATH=. python test_split_pipeline/run_all.py
# Culver-City domain-shift split
CATOSG_SPLIT=test_culver_city PYTHONPATH=. python test_split_pipeline/run_all.py
```

Outputs land in `test_split_pipeline/runs/` and `runs_culver/` respectively.

## Relationship to OpenCOOD

The perception backbones (PointPillars late-fusion and attentive-compression) and
the detection/eval code are from the public [OpenCOOD](https://github.com/DerrickXuNu/OpenCOOD)
codebase; they are frozen and unmodified except for a few files documented in
`00_opencood_modifications/` of the full tree. CA-TOSG adds **no learnable
parameters** to the perception pipeline — only the granularity selector.
