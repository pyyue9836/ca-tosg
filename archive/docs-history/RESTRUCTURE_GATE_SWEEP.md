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

MOVED. The register lives in **`docs/experiment_protocol.md` Appendix D** (Change-log LAYOUT),
so there is exactly one copy. 89 files, grouped by why they are alive; the delete list and the
method stay here.

## 3. Where this lands

The §2 register now lives in `docs/experiment_protocol.md` **Appendix D** (that file is
`PROTOCOL.md` after its `git mv`); this file keeps the delete list and the method, and its §2
is a pointer, so the two cannot drift.
