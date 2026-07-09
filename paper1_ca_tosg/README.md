# CA-TOSG (Paper 1) — Channel-Aware Task-Oriented Semantic Granularity Selection

Clean layout. Every number in the paper / annual review traces to one file in `results/`.

```
data/      per-frame datasets + trained selector (not pushed to git)
results/   final result CSVs (one per reported number)
code/      all scripts (top-level + extra_experiments/ + test_split_pipeline/)
paper/     LaTeX source, figures, refs
```

## Result → file (provenance)

| Reported result | File |
|---|---|
| Payload–accuracy Pareto (Fig. 4.3) | `results/pareto_points.csv` |
| True end-to-end AP@0.5 knee — validate (+0.025) | `results/ap_true_e2e_validate.csv` |
| True end-to-end AP@0.5 knee — test (+0.022) | `results/ap_true_e2e_test.csv` |
| True end-to-end AP@0.5 knee — Culver (+0.053) | `results/ap_true_e2e_culver.csv` |
| Two-regime bars (Fig. 4.5) | `results/two_regime_bars.csv` |
| JSCC selector edge — AWGN/Rayleigh/OFDM | `results/jscc_selector_{awgn,rayleigh,ofdm}.csv` |
| Where2comm baseline (AP 0.897/0.885/0.811, epoch-50) | `results/where2comm_ap.csv` |
| Feature importance (SNR+channel = 65%) | `results/feature_importance.csv` |
| Deployment latency (52.8 ms/frame) | `results/latency_benchmark.csv` |
| Robustness: CSI noise / aging / request delay / Rician | `results/robustness_*.csv` |
| Difficulty strata (hard-frame gain) | `results/difficulty_strata.csv` |
| Ablation / SNR-threshold arm | `results/ablation.csv`, `results/snr_threshold.csv` |
| Multi-seed confidence intervals | `results/multiseed_hardening.csv` |
| Model comparison (RF vs DT vs LR vs threshold) | `results/model_comparison.csv` |
| Generalisation headline — test/Culver | `results/generalisation_{test,culver}.csv` |
| L-channel reliability / scene subsets | `results/l_channel_reliability.csv`, `results/scene_subsets.csv` |

Datasets (`data/dataset_*.csv`) and the trained selector (`data/selector_rf.pkl`) are kept
locally and excluded from git. The OPV2V dataset itself is not stored here.
