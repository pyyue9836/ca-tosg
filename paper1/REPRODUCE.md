# Reproducing CA-TOSG (Paper 1)

Every table and figure in `paper/main.tex` traces to a committed CSV in `results/` and a generator
script in `code/`. This file maps each one to its command, lists the data-prep chain, and states the
randomness. All numbers in the paper are read from these CSVs (never hand-typed); `code/payload_audit.py`
bit-checks the payload chain end-to-end.

> **Repo layout.** Generators run in the **runtime** checkout
> `OpenCOOD/peiyi_work/paper1/` (they compute `REPO` = the OpenCOOD root and read the source datasets
> and caches there). Figures/scripts/CSVs are then copied into this **archive** repo (`ca-tosg/paper1/`)
> and committed. The archive's own outputs carry no `_v3` suffix (cleaned 2026-08, tag `pre-cleanup`);
> the runtime still uses `_v3` names for its inputs (`dataset_{split}_v3.csv`, `gs_rerun/jscc_v3/…`),
> which the archive scripts reference as external inputs.

## 0. Environment

- Python: `/home/josh/miniconda3/envs/sionna310/bin/python` (conda env `sionna310`).
- `PYTHONPATH=/home/josh/cooperative_semantic_perception/OpenCOOD` for every generator (imports
  `opencood.*` + `peiyi_work/paper1/code/extra_experiments/*`).
- Key deps: PyTorch 2.11 + cu128 (RTX 5070, sm_120), `spconv`, `sionna` (link-level BLER), `scikit-learn`
  (RandomForest selector), `numpy`, `pandas`, `matplotlib`.
- GPU needed only for inference stages (§1.b/§1.c); all table/figure post-processing is CPU-only.
- LaTeX toolchain (pdflatex/latexmk) is **not** in this env — compile `paper/main.tex` on Overleaf.

## 1. Data preparation (raw OPV2V → cached per-frame CSVs/npz)

Run from the OpenCOOD repo root with the `sionna310` interpreter and `PYTHONPATH=.`.

a. **Per-frame dataset** `data/dataset_{validate,test,culver}_v3.csv` — 21 ego-side cues + per-method
   clean F1 (late/comp/ego) + Sionna frame BLER columns. Built by `code/make_dataset.py`, then the
   canonical F1 columns are (re)written by `code/recompute_canonical_f1.py` (adds `ego_f1`, the v3
   canonical outcome). These are the runtime *inputs* to everything below.
b. **Global-sort AP caches** `gs_rerun/{late,comp,ego}_{split}.npz` — cached per-frame boxes+scores+GT
   for the late-fusion, attentive-compression, and ego-only checkpoints, via
   `code/regen_preds_with_scores.py` (one call per model_dir/fusion; see `gs_rerun/reproduce.sh`).
c. **JSCC per-frame decodes** `gs_rerun/jscc_v3/jscc_{ch}_{split}_snr{NN}.npz` — importance-map JSCC
   inference over 3 channels × 6 SNRs × {validate,test,culver}, via
   `code/extra_experiments/jscc_perframe/jscc_sweep.py --mode sweep` (~GPU-hours), then scored to
   per-frame F1 by `score_jscc.py --mode score`.
d. **Deployed selector** `data/selector_rf.pkl` — the 400-tree RandomForest, trained once on the full
   `dataset_validate_v3.csv` oracle labels by `code/train_rf.py`. Never retrained for test/culver.

## 2. Tables → generator → source CSV

| Table (main.tex) | command (run in OpenCOOD runtime, `PYTHONPATH=.`) | source CSV (archive path) |
|---|---|---|
| tab:cues | (static; the 21-cue definition table) | — |
| tab:headline (true-e2e headline) | `python code/true_e2e_global.py --split {validate,test,culver} …` | `results/true_e2e_global_{split}.csv` |
| tab:true_e2e / tab:gen_true_e2e / tab:gen_true_e2e_culver | same as above (per split) | `results/true_e2e_global_{validate,test,culver}.csv` |
| tab:headline_agg (RF vs SNR-threshold, 200-real.) | `python code/recompute_policy_200seed.py` | `results/policy/threshold_vs_rf.csv` (+ `policy/pareto_points.csv`, `policy/generalisation_{split}.csv`) |
| tab:two_regime (In-dist / Deployed edge) | `python code/extra_experiments/jscc_perframe/build_two_regime_edge_clean.py` and `kfold_two_regime_diag.py` | `results/jscc/two_regime_edge_clean.csv`, `results/jscc/two_regime_kfold_diag.csv` |
| tab:ablation (cue subsets + threshold) | `python code/extra_experiments/a7_ablation.py` | `results/ablation/a7_ablation.csv`, `ablation/a7_cue_value.csv` |
| §Where2comm numbers | OpenCOOD global-sort eval of the epoch-50 Where2comm checkpoint (eval yaml in the CSV `source` column) — see `results/where2comm_ap_PROVENANCE.txt`. NOT `where2comm_compare.py`, which is DEPRECATED (epoch-37 perfect-channel single point). | `results/where2comm_ap.csv` |

## 3. Figures → generator → source

Run each generator in the OpenCOOD runtime (`PYTHONPATH=.`); the PDF lands in `paper/figures/` and is
copied into this repo. (`fig_*_preview.png` are gitignored previews.)

| Figure | file | generator | data source |
|---|---|---|---|
| fig:overview | `ca_tosg_method_overview.pdf` | **manual** (draw.io; see `paper/DRAW_OVERVIEW_FIGURE.md`) | schematic |
| fig:bler | `fig_channel_bler_frame.pdf` | `code/plot_bler_frame.py` | `results/bler_sionna/bler_sionna.csv` |
| fig:qualitative | `fig_qualitative_bev.pdf` | manual (BEV render) | — |
| fig:ap_snr | `fig_ap50_{awgn,rayleigh}.pdf` | `code/plot_ap_snr.py` | `results/true_e2e_global_validate.csv` + `results/jscc/{jscc_ap_f1,channel_codec_ap_validate}.csv` |
| fig:payload_snr | `fig_payload_awgn.pdf` | `code/plot_pareto_payload.py` | `results/true_e2e_global_validate.csv` |
| fig:decision_ratio | `fig_decisions_{awgn,rayleigh}.pdf` + `fig_stacked_area.pdf` | `code/snr_decision_plot.py`, `code/plot_stacked_area.py` | `results/true_e2e_global_validate.csv`, `results/step4_oracle_action_dist.csv` |
| fig:feat_imp | `fig_feature_importance.pdf` | `code/plot_feature_importance.py` | `results/feature_importance.csv` (RF `feature_importances_` of the deployed selector) |
| fig:pareto | `fig_pareto_test.pdf` | `code/plot_pareto_payload.py` | `results/policy/pareto_points.csv`, `results/true_e2e_global_validate.csv` |
| fig:difficulty | `fig_difficulty.pdf` | `code/extra_experiments/a2_difficulty.py` | `results/a2_difficulty.csv`, `results/a2_difficulty_reliable.csv` |
| fig:two_regime | `fig_two_regime.pdf` | `code/extra_experiments/jscc_perframe/make_two_regime_figure.py` | `results/jscc/two_regime_kfold_diag.csv` (panel b), JSCC per-frame F1 (panel a) |

## 4. Randomness / determinism (from `code/extra_experiments/v3_eval.py`)

- **200-realisation deployment eval** (`N_SEED = 200`): realisation `s` uses `numpy.random.default_rng(s)`
  for `s ∈ 0..199`; per frame `snr ~ U[0,20]` dB, channel type `is_rayleigh = rng.random() < 0.5`
  (Bernoulli 0.5). Fully seeded → deterministic.
- **RandomForest**: `n_estimators=400, max_depth=10, min_samples_leaf=4, class_weight='balanced',
  random_state=0`.
- **k-fold in-distribution diagnostic** (`kfold_two_regime_diag.py`): `StratifiedKFold(5, shuffle=True,
  random_state=0)`.
- **Frame-level paired bootstrap CI** (`paired_ci_frames_from`): `n_boot=5000`, `seed=12345`.
- **CSI-noise robustness**: selector `est_snr` perturbed with `default_rng(s+10000)`; the channel BLER
  always uses the *true* snr.

## 5. Verification (all pass on the committed tree)

```
python code/payload_audit.py                       # 15/15 links MATCH (payload chain -> tables)
python code/verify_paragraph_insert.py 1 2 3       # GATE PASS (hand-written paragraphs verbatim)
grep -nE -f <(grep '^RX ' results/STALE_FINGERPRINTS.md | cut -c4-) paper/main.tex   # expect 0 (block-exit)
python code/extract_claims.py --check              # CLAIMS.md up to date vs main.tex
python code/p2_dataprep/check_leakage.py           # LEAKAGE GATE PASS (resident, P2 data prep)
```

The leakage gate needs the P2 grids (data/p2/, git-excluded); build them first with
`python code/p2_dataprep/expand_grid_clean.py && python code/p2_dataprep/make_scene_split.py`.
