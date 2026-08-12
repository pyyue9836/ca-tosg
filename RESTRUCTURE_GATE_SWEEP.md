# 引用门全仓清扫 (reference sweep) — BEVFormer-style restructure, commit 1

Companion to `RESTRUCTURE_PLAN.md` (the authority) and `RESTRUCTURE_MAP.csv` (the per-file map).
This file answers one question for every tracked file: **is anything live still pointing at it?**
— and, where the answer is no but the file survives anyway, records 【文件 | 活因 | 死期】.

## 0. Scope and method (so a negative claim has a stated scope)

- **Scope**: all **300** git-tracked files on `refactor/bevformer-style-layout` at
  `59a3d1c` (= `p1-phy-rebuild`, = tag `pre-bevformer-style-restructure`). Untracked / gitignored
  material (`data/`, `experiment_logs/`, `pretrained_models/`, `gs_rerun/`, `*.pkl`, `*.pth`) is
  **out of scope** and is not touched by this sweep.
- **Derivation** (scripts committed under `docs/restructure/`, they run against the
  *pre-migration* tree only):
  - `scan_path_literals.py` → `path_literals.csv` — every path literal in every tracked
    `.py/.md/.json/.txt`: 2787 hits, of which **887 are rewrite points** (`relpath_local`,
    `relpath_escaping_repo`, `absolute_path`, `json_internal_relpath`, `local_import`,
    `path_anchor`). These are the `row_type=LITERAL` rows of `RESTRUCTURE_MAP.csv`.
  - `build_refgraph.py` → reachability from **28 live roots** (the 5 gates + the current
    implementation behind each of the 6 headline commands + the figure generators named in
    `REPRODUCE.md` §3 + `main.tex`/`PROTOCOL.md`/`CLAIMS.md`).
  - `classify_liveness.py` → `liveness.csv`. Filename literals are turned into **globs**
    (`f'r10c_decision_log_{split}_{tag}.csv'` → `r10c_decision_log_.*\.csv`) so that
    f-string-built **outputs** count as alive, which a literal-only graph gets wrong.
- **Tool limits, stated rather than hidden**: the glob matcher still misses references that
  never spell a filename — `\bibliography{refs}` (no extension), assets a *future* README will
  embed, and files named only in prose I have not machine-linked. Every such case below is
  hand-classified and labelled `[tool-miss]`. **No file is deleted on the tool's verdict alone**;
  the delete list is 15 hand-checked files, each with a stated reason.

Verdict counts: `LIVE-ROOT 28`, `ALIVE 165`, `ALIVE-DOC 3`, `KEEP-P5 89`, `DELETE 15`.

## 1. Delete list — deletable today

Justification for deleting at all is the supervisor's: *"Git本身就是历史记录"* — every file
below stays permanently reachable at tag **`pre-bevformer-style-restructure` (59a3d1c)**.

**Guard respected**: `results/DATA_MANIFEST.md` (→ `docs/data_manifest.md`) forbids deleting any
GPU-regeneratable cache registered in it. Nothing on this list is registered there, and the two
registered *generators* (`code/regen_preds_with_scores.py`, `code/run_ego_only.py`) are **moved,
not deleted**.

| # | file | why deletable today |
|---|---|---|
| 1 | `paper1/.gitignore` | merged into the root `.gitignore` (contents preserved) |
| 2 | `paper1/README.md` | content redistributed: root `README.md` + `docs/model_zoo.md` + `results/README.md` |
| 3 | `paper1/analysis_tools/build_ldpc_qam_bler_table.py` | builds the **deprecated** 40-block BLER table (1/40 quantisation floor); superseded by `build_bler_sionna.py` |
| 4 | `paper1/results/ldpc_qam_bler_table.csv` | that deprecated table's output — codeword-level BLER was wrongly consumed as frame-level; superseded by `results/channel/bler_sionna.csv` |
| 5 | `paper1/analysis_tools/make_fig1_framework.py` | generated the retired matplotlib fig1; `REPRODUCE.md` §3 already marks fig:overview **manual** (draw.io) |
| 6 | `paper1/code/v3_eval.py` | stale duplicate of `code/extra_experiments/v3_eval.py`; the copy here lacks the OFDM concat, and **every** importer resolves to the `extra_experiments` copy via `sys.path` (verified: 11 importers, all inside `extra_experiments/` or importing `_common` alongside) |
| 7 | `paper1/code/regen_ego_only.py` | superseded by `run_ego_only.py`, which is the DATA_MANIFEST-registered generator for `gs_rerun/ego_*.npz` |
| 8 | `paper1/results/a2_difficulty.csv` | byte-identical duplicate of `results/ablation/a2_difficulty.csv` (`diff` clean) |
| 9 | `paper1/results/a2_difficulty_reliable.csv` | byte-identical duplicate of `results/ablation/a2_difficulty_reliable.csv` |
| 10 | `paper1/code/extra_experiments/out/a2_difficulty_reliable.csv` | **third** byte-identical copy (scratch output dir) |
| 11 | `paper1/paper/figures/ca_tosg_method_overview_ORIG.pdf` | superseded pre-redraw original |
| 12 | `paper1/paper/figures/fig_ap70_awgn.svg` | not `\includegraphics`-ed by `main.tex` (13 includes enumerated) |
| 13 | `paper1/paper/figures/fig_ap70_rayleigh.svg` | as above |
| 14 | `paper1/paper/figures/fig_pareto_culver.pdf` | not included by `main.tex` (only `fig_pareto_test.pdf` is) |
| 15 | `paper1/paper/figures/fig_pareto_validate.pdf` | as above |

Deletions 8–10 collapse three copies of one measurement to one; the surviving copy is
`results/sensitivity/ablation/a2_difficulty{,_reliable}.csv`.

## 2. KEEP-UNTIL-P5 — 【文件 | 活因 | 死期】

89 files are named by nothing that a live root reaches, yet are kept. "P5" below = the state in
which paper 1 is accepted / camera-ready and its result tree is archived. A file whose 死期 has
passed is a delete candidate for the *next* sweep, not this one.

### 2.1 Infrastructure — outside the sweep's remit `[tool-miss]`

| 文件 | 活因 | 死期 |
|---|---|---|
| `.gitignore` | build infrastructure; the matcher only follows content references | never (rewritten in commit 2) |
| `paper/refs.bib` | `main.tex` cites it as `\bibliography{refs}` — no extension, so the glob matcher cannot see it | 论文接收 |
| `env_setup/requirements_py310_safe.txt` → `requirements.txt` | the environment contract (`python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2.2.2`) that `FROZEN_MANIFEST.json` pins | never |
| `env_setup/requirements_no_torch_spconv.txt` | analysis-only install path (no torch/spconv) | 当 environment.yml 覆盖两条安装路径 |

### 2.2 Figure assets — become README/paper assets in commit 4 `[tool-miss]`

| 文件 | 活因 | 死期 |
|---|---|---|
| `paper/figures/ca_tosg_method_overview.svg` → `figs/ca_tosg_overview.svg` | PLAN names it the overview **source**; the `.pdf` beside `main.tex` is its export | 论文接收 |
| `fig_ap50_{awgn,rayleigh}.svg` → `figs/results/` | SVG sources of the AP@0.5 panels | 论文接收 |
| `fig_{pareto_test,payload_awgn,channel_bler_frame}.png` → `figs/results/` | the README display assets (PLAN `figs/results/`) | 论文接收 |
| `results/bler_sionna/bler_old_vs_new.svg` → `results/channel/` | evidence for the old-vs-new BLER table ruling recorded in `docs/experiment_protocol.md` | 论文接收 |

### 2.3 Ablation + verifier code — generates cited numbers, invoked by hand

活因 for all: each writes a CSV that `CLAIMS.md` / `main.tex` / `PARAGRAPH_DRAFTS.md` cites, but
none is wired into one of the 6 headline commands. 死期 for all: **论文接收**.

| 文件 | 活因 (produces) |
|---|---|
| `extra_experiments/_common.py` | shared loader for a1–a9 |
| `extra_experiments/a3_subsets.py` | `results/sensitivity/scene_subsets.csv` |
| `extra_experiments/a4_jscc_aware.py` | JSCC-aware arm of the two-regime analysis |
| `extra_experiments/a5_causality.py` | cue-causality check (appendix) |
| `extra_experiments/a6_l_reliability.py` | `results/sensitivity/l_channel_reliability.csv` |
| `extra_experiments/a9_hardening.py` | `results/sensitivity/multiseed_hardening.csv` |
| `extra_experiments/c_channels.py` | per-channel breakdown |
| `extra_experiments/robustness.py` | `results/sensitivity/ablation/robustness_{aging,staleness,csi_noise}.csv` |
| `code/verify_gamma_mechanism.py` | `results/sensitivity/gamma_mechanism.csv` |
| `code/verify_harm_stratum_structural.py` | `results/sensitivity/harm_stratum_structural.csv` |
| `code/verify_frontier_payload_invariance.py` | `results/sensitivity/frontier_payload_invariance.csv` |
| `code/step4_collab_harm.py` | `results/sensitivity/step4_collaboration_harm.csv` |
| `code/step4_oracle_action_dist.py` | `results/main/step4_oracle_action_dist.csv` |
| `code/gt_audit.py` | `results/sensitivity/gt_audit.csv`, `gt_object_stats.csv` |
| `code/canonical_rescore.py` | `results/sensitivity/canonical_rescore.csv` (canonical-union-GT ruler) |
| `code/true_e2e_ap_inference.py` | GPU-side true-e2e AP inference |
| `code/plot_oracle_action_dist.py` | oracle action-distribution figure |
| `code/paper_style.py` | IEEE figure style imported by every `plot_*` `[tool-miss: imported, not path-referenced]` |
| `p2_dataprep/train_p3_variants.py` | `results/sensitivity/item3_variants.csv` |
| `p2_dataprep/eval_p3c_rician_bracket.py` | `results/sensitivity/item5c_rician_*.csv` |
| `analysis_tools/plot_bler_compare.py`, `plot_paper_figures.py` | old/new BLER comparison + batch figure driver |
| `analysis_tools/ldpc_qam_physical_sanity_n1000_ebn0.py` | becomes `tests/test_channel.py` — **promoted to a gate in commit 2**, so its 死期 is never |

### 2.4 Upstream data producers — the P2 cue source depends on them

死期 for all: **当 `dataset_{split}.csv` 被冻结并登记进 `docs/data_manifest.md` 之后** (they are the
only way to rebuild the cue CSVs the frozen manifest md5-pins).

| 文件 | 活因 |
|---|---|
| `code/test_split_pipeline/{01..05,extract_test_data,run_all}.py` | produces `OpenCOOD/peiyi_work/paper1/data/dataset_test.csv` — the cue source the P2 test grid is built from |
| `code/regen_preds_with_scores.py`, `code/run_ego_only.py` | DATA_MANIFEST-registered regen commands for `gs_rerun/{late,comp,ego}_*.npz` (~10 GPU-min/split) — **protected by the DATA_MANIFEST rule** |

### 2.5 Baseline code — alive because the baselines are unfinished

| 文件 | 活因 | 死期 |
|---|---|---|
| `scomcp_reproduction/*` (10 files) → `baselines/scomcp/` | the SComCP reproduction has **not** yet produced a result table; `results/baselines/scomcp.csv` does not exist | 当 SComCP 行进 Table III 且结果表冻结 |
| `extra_experiments/jscc_perframe/{build_channel_codec_ap,jscc_selector_compare,plot_channel_codec_ap,score_jscc_perframe}.py` | per-frame JSCC scoring behind fig:two_regime + the JSCC selector edge | 论文接收 |
| `analysis_tools/{stage1_*,stage2_*,run_jscc_eval,inference_subset,run_separate_coding_sweep}.py` + 8 `*.sh` | the WCSP2023 ImportanceMapJSCC reproduction: the *only* record of how the learned checkpoints on `H:` were produced | 论文接收 (checkpoints 无法重建) |
| `analysis_tools/MAP_REPRODUCTION_CHANGELOG.md` | that reproduction's change log | 论文接收 |

### 2.6 Result CSVs named only in prose

死期 for all: **论文接收后随 `results/` 归档**. 活因: each is the source of a number quoted in
`CLAIMS.md` / `PARAGRAPH_DRAFTS.md` / `main.tex`, but no *script* reads it back.

`canonical_rescore.csv`, `f1_ap_decoupling_culver.{csv,md}`, `gamma_mechanism.csv`,
`gt_audit.csv`, `gt_object_stats.csv`, `harm_stratum_structural.csv`,
`step4_collaboration_harm.csv`, `true_e2e_global_test.csv` `[tool-miss: named in
paper/figures/README.md]`, `jscc_selector_{awgn,rayleigh}.csv`,
`ablation/robustness_{aging,staleness}.csv`, `step4_PROVENANCE.txt`,
`canonical_gt_PROVENANCE.txt`, `bler_sionna/PROVENANCE_rician.txt`, `policy/STEP5_NOTES.md`,
`DATA_MANIFEST.md`, `INVARIANCE_NOTE.md`.

**Two true orphans** — no reference anywhere in the tree, kept because deleting *measured* data is
worse than carrying it: `results/ego_only_acceptance.csv`,
`results/jscc/channel_codec_ap_test.csv`. 死期: next sweep, if still unreferenced at P5.

## 3. Where this lands

The §2 table is folded into `docs/experiment_protocol.md` **Appendix A** in commit 2 (that file is
`PROTOCOL.md` after its `git mv`); this file keeps the delete list and the method, and its §2
becomes a pointer so the two copies cannot drift.
