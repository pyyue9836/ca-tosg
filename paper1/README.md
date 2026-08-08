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
| Payload–accuracy Pareto (Fig. 4.3) | `results/policy/pareto_points.csv` (200-realisation, current selector — see `results/policy/PROVENANCE.txt`) |
| True e2e AP knee — validate / test / Culver (global-sort) | `results/true_e2e_global_{validate,test,culver}.csv` |
| AP-vs-SNR figure (fig:ap_snr, global-sort) | source `ap_vs_snr/*.csv` **removed in P1.5** (stale JSCC/LDPC summaries); P2 regenerates against `bler_sionna` |
| Two-regime edge (fig:two_regime, Table III) | `results/jscc/two_regime_edge_clean.csv` (deployed), `results/jscc/two_regime_kfold_diag.csv` (in-dist) |
| JSCC selector edge — AWGN / Rayleigh / OFDM | `results/jscc_selector_{awgn,rayleigh,ofdm}.csv` |
| Where2comm baseline (global-sort 0.887/0.871/0.790, epoch-50) | `results/where2comm_ap.csv` |
| Feature importance | `results/feature_importance.csv` — SNR+channel share **pending P2 re-freeze** (do not cite the old 65% figure) |
| Latency | old 52.8 ms **retired and removed in P1.5** (single-version policy); P2 re-measures on the frozen selector |
| Robustness: CSI noise / aging / request delay | `results/robustness_csi_noise.csv`, `results/robustness_csi_aging.csv`, `results/robustness_request_delay.csv` (Rician **removed in P1.5**, convention in doubt; P2 regenerates) |
| Difficulty strata (hard-frame gain) | `results/a2_difficulty.csv`, `results/a2_difficulty_reliable.csv` |
| Ablation / SNR-threshold arm | `results/ablation/a7_ablation.csv`, `results/ablation/a7_cue_value.csv`, `results/snr_threshold.csv` |
| Multi-seed confidence intervals | `results/multiseed_hardening.csv` |
| Model comparison | `results/ablation/a8_models.csv` |
| Generalisation headline — validate / test / Culver | `results/policy/generalisation_{validate,test,culver}.csv` (200-realisation, current selector; validate is in-sample — see provenance) |
| Policy recompute provenance (RF hash / seeds / protocol / in-sample sanity) | `results/policy/PROVENANCE.txt` → `code/recompute_policy_200seed.py` (v3-P1; the old root `policy_recompute_PROVENANCE.txt` was the v2 record, deleted in P1) |
| L-channel reliability / scene subsets | `results/l_channel_reliability.csv`, `results/scene_subsets.csv` |

## ImportanceMapJSCC = learned (importance_source=learned)
All ImportanceMapJSCC results use the **learned** importance map (the faithful reproduction of
Sheng et al. WCSP2023), NOT psm. JSCC-aware analysis (two-regime, SNR-threshold edge) is in
`results/jscc_selector_{awgn,rayleigh,ofdm}.csv`. **BLER table (P1 Step 1, 2026-07-11):**
the current physically-correct table is `results/bler_sionna/bler_sionna.csv` — Sionna 5G-LDPC
(k=500,n=1000) rate-1/2 + 16/256-QAM, adaptive MC (≥100 block errors or 1e5 codewords), Es/N0
axis, with **codeword-level and frame-level** columns (frame = 1−(1−p_cw)^3960; generator `code/plot_bler_frame.py`).
The old `results/ldpc_qam_bler_table.csv` is **DEPRECATED** (40-block MC → 0.025=1/40 quantisation
floor at 12–14 dB; codeword-level BLER wrongly consumed as frame-level) — retained for provenance
only. The global-sort AP-vs-SNR summaries plotted in fig:ap_snr
(learned JSCC / LDPC16 / LDPC256 / identity-upper, AWGN+Rayleigh) were under
`results/ap_vs_snr/*_summary.csv`, **removed in P1.5** (stale JSCC/LDPC summaries); P2 regenerates
them against `bler_sionna`. (The older psm `channel_codec_ap/` set was removed as
stale/inconsistent; OFDM enters the paper only through the F1 edge in `jscc_selector_ofdm.csv`,
not an AP-vs-SNR curve.)

## Not in git (kept local only)
`data/`, `experiment_logs/`, `pretrained_models/`, scomcp models/data, and all `*.pkl/*.pth/*.npy/*.png`.
