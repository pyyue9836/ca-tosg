# Paper 1 — CA-TOSG: Channel-Aware Task-Oriented Semantic Granularity Selection

Self-contained: all data, code, results and the manuscript for paper 1 live under this folder.
Every reported number traces to one file in `results/` (table below).

## Layout
```
paper/                  LaTeX source, figures, refs.bib  (the manuscript)
code/                   main experiment scripts (dataset build, RF, e2e AP, jscc_perframe, test-split pipeline)
analysis_tools/         shared analysis code: LDPC-QAM BLER table builder, inference_subset, physical sanity
data/                   per-frame datasets + trained selector          (git-excluded, kept local)
results/                final result CSVs — one per reported number
experiment_logs/        raw eval logs & training runs (incl. OFDM×LDPC) (git-excluded, 6.5 GB, kept local)
pretrained_models/      symlink to checkpoints on H:                    (git-excluded)
opencood_modifications/ README of the #self+ edits made to opencood/
env_setup/              pip requirements
scomcp_reproduction/    reproduction of the SComCP baseline method      (git-excluded data/models)
```

## Result → file (provenance; all data is measured, none hand-authored)

| Reported result | File |
|---|---|
| Payload–accuracy Pareto (Fig. 4.3) | `results/pareto_points.csv` (200-realisation, current selector — see `policy_recompute_PROVENANCE.txt`) |
| True e2e AP knee — validate / test / Culver (global-sort) | `results/true_e2e_global_{validate,test,culver}.csv` |
| AP-vs-SNR figure (fig:ap_snr, global-sort) | `results/ap_vs_snr/*.csv` + `results/true_e2e_global_validate.csv` → `code/plot_ap_snr.py` |
| Two-regime bars (Fig. 4.5) | `results/two_regime_bars.csv` |
| JSCC selector edge — AWGN / Rayleigh / OFDM | `results/jscc_selector_{awgn,rayleigh,ofdm}.csv` |
| Where2comm baseline (global-sort 0.887/0.871/0.790, epoch-50) | `results/where2comm_ap.csv` |
| Feature importance (SNR+channel = 65%) | `results/feature_importance.csv` |
| Latency (52.8 ms/frame) | `results/latency_benchmark.csv` |
| Robustness: CSI noise / aging / request delay / Rician | `results/robustness_*.csv` |
| Difficulty strata (hard-frame gain) | `results/difficulty_strata.csv` |
| Ablation / SNR-threshold arm | `results/ablation.csv`, `results/snr_threshold.csv` |
| Multi-seed confidence intervals | `results/multiseed_hardening.csv` |
| Model comparison | `results/model_comparison.csv` |
| Generalisation headline — validate / test / Culver | `results/generalisation_{validate,test,culver}.csv` (200-realisation, current selector; validate is in-sample — see provenance) |
| Policy recompute provenance (RF hash / seeds / protocol / in-sample sanity) | `results/policy_recompute_PROVENANCE.txt` → `code/recompute_policy_200seed.py` |
| L-channel reliability / scene subsets | `results/l_channel_reliability.csv`, `results/scene_subsets.csv` |

## ImportanceMapJSCC = learned (importance_source=learned)
All ImportanceMapJSCC results use the **learned** importance map (the faithful reproduction of
Sheng et al. WCSP2023), NOT psm. JSCC-aware analysis (two-regime, SNR-threshold edge) is in
`results/jscc_selector_{awgn,rayleigh,ofdm}.csv`. **BLER table (P1 Step 1, 2026-07-11):**
the current physically-correct table is `results/bler_sionna/bler_sionna.csv` — Sionna 5G-LDPC
(k=500,n=1000) rate-1/2 + 16/256-QAM, adaptive MC (≥100 block errors or 1e5 codewords), Es/N0
axis, with **codeword-level and frame-level** columns (frame = 1−(1−p_cw)^3960; old↔new figure
`results/bler_sionna/bler_old_vs_new.pdf`; generator `analysis_tools/build_bler_sionna.py`).
The old `results/ldpc_qam_bler_table.csv` is **DEPRECATED** (40-block MC → 0.025=1/40 quantisation
floor at 12–14 dB; codeword-level BLER wrongly consumed as frame-level) — retained for provenance
only. The global-sort AP-vs-SNR summaries plotted in fig:ap_snr
(learned JSCC / LDPC16 / LDPC256 / identity-upper, AWGN+Rayleigh) are checked in under
`results/ap_vs_snr/*_summary.csv`. (The older psm `channel_codec_ap/` set was removed as
stale/inconsistent; OFDM enters the paper only through the F1 edge in `jscc_selector_ofdm.csv`,
not an AP-vs-SNR curve.)

## Not in git (kept local only)
`data/`, `experiment_logs/`, `pretrained_models/`, scomcp models/data, and all `*.pkl/*.pth/*.npy/*.png`.
