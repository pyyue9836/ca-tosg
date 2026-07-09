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
| Payload–accuracy Pareto (Fig. 4.3) | `results/pareto_points.csv` |
| True e2e AP@0.5 knee — validate / test / Culver | `results/ap_true_e2e_{validate,test,culver}.csv` |
| Two-regime bars (Fig. 4.5) | `results/two_regime_bars.csv` |
| JSCC selector edge — AWGN / Rayleigh / OFDM | `results/jscc_selector_{awgn,rayleigh,ofdm}.csv` |
| Where2comm baseline (0.897/0.885/0.811, epoch-50) | `results/where2comm_ap.csv` |
| Feature importance (SNR+channel = 65%) | `results/feature_importance.csv` |
| Latency (52.8 ms/frame) | `results/latency_benchmark.csv` |
| Robustness: CSI noise / aging / request delay / Rician | `results/robustness_*.csv` |
| Difficulty strata (hard-frame gain) | `results/difficulty_strata.csv` |
| Ablation / SNR-threshold arm | `results/ablation.csv`, `results/snr_threshold.csv` |
| Multi-seed confidence intervals | `results/multiseed_hardening.csv` |
| Model comparison | `results/model_comparison.csv` |
| Generalisation headline — test / Culver | `results/generalisation_{test,culver}.csv` |
| L-channel reliability / scene subsets | `results/l_channel_reliability.csv`, `results/scene_subsets.csv` |

## Channel × codec coverage (from experiment_logs/opencood_training_logs/jscc_eval/)
Full 3×3 factorial evaluated: {AWGN, Rayleigh, OFDM} × {LDPC+16QAM, LDPC+256QAM, JSCC}, plus Rician fading.
Aggregated AP@0.3/0.5/0.7-vs-SNR for every channel×codec cell (incl. OFDM×LDPC16/256) is in
`results/channel_codec_ap/*_summary.csv`; the LDPC+QAM BLER table is `results/ldpc_qam_bler_table.csv`.

## Not in git (kept local only)
`data/`, `experiment_logs/`, `pretrained_models/`, scomcp models/data, and all `*.pkl/*.pth/*.npy/*.png`.
