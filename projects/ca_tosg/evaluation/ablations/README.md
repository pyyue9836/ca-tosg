# `evaluation/ablations/` — 修订实验 A3–A8 + robustness / Revision experiments

> **Rewritten in R67 (c).** The old text described a `extra_experiments/` directory with an `out/`
> subdirectory and an `A1–A8 + C` line-up, none of which exists here: `a1_pareto.py`,
> `a2_difficulty.py` and `c_channels.py` were deleted in R67 (c), `a9_hardening.py` in R65, and the
> outputs go to `results/`, not `out/`. Every script and path named below is in this tree.

## 中文

为回应审稿/导师意见新增的一批实验。**全部从缓存的逐帧 CSV 计算，不重跑 GPU 推理**，所以又快又可复现。

* `_common.py` —— 公共工具（payload 口径、特征列、effective-F1、策略实现），所有 `aX_*.py` 都 import 它，是**单一事实来源**。
* `v3_eval.py`（上一层目录）—— 共用的 200 次实现评估器。**凡是可能进论文的数字都必须走它**；单次冻结抽样只作诊断。
* 结果 CSV 写到 `results/sensitivity/` 与 `results/sensitivity/ablation/`；每个文件由谁生成见 `results/README.md`。

**怎么跑**（仓库根目录，`conda activate sionna310`）：`python projects/ca_tosg/evaluation/ablations/aX_xxx.py`

## English

Experiments added to answer reviewer/advisor questions. **All computed from cached per-frame CSVs —
no GPU re-inference**, so they are fast and reproducible.

* `_common.py` — shared helpers (payload accounting, feature columns, effective-F1, policy
  realisation). Every `aX_*.py` imports it; it is the single source of truth.
* `../v3_eval.py` — the shared 200-realisation evaluator. **Any number that may reach the paper must
  go through it**; a single frozen draw is diagnostic-only. It is also the only surviving
  implementation of the retired v3 policy engine's CSI draw.
* Result CSVs land in `results/sensitivity/` and `results/sensitivity/ablation/`; the file → generator
  map is `results/README.md`.

**Run** (repo root, `conda activate sionna310`): `python projects/ca_tosg/evaluation/ablations/aX_xxx.py`

| 脚本 / script | 干什么 / what it does | 状态 / status |
|---|---|---|
| `a3_subsets.py` | occlusion / sparse / long-range 场景子集 + 动作占比 · occlusion/sparse/long-range subsets + action ratios | **DIAGNOSTIC**, 单次冻结抽样，未被 main.tex 引用；要引用必须先过 200 次协议 · single frozen draw, cited by nothing; must be re-run under the 200-realisation protocol before any number is quoted |
| `a4_jscc_aware.py` | JSCC vs LDPC 的 AP–SNR 对比 · JSCC vs LDPC AP-SNR comparison | 从缓存的 ImportanceMapJSCC 复现读取 · reads the cached ImportanceMapJSCC reproduction |
| `a5_causality.py` | 请求延迟 / 决策 staleness · request delay and decision staleness | 10 Hz 下一帧往返 = 决策晚一帧 · one-frame round trip at 10 Hz |
| `a6_l_reliability.py` | L 不可靠 / 更贵时的敏感性 · sensitivity to L being unreliable or costlier | 重新推导信道感知 oracle 并重评已部署选择器 · re-derives the channel-aware oracle, re-evaluates the deployed selector |
| `a7_ablation.py` | 特征 ablation + **SNR 阈值 baseline** · feature ablation + SNR-threshold baseline | **PUBLICATION** (200 realisations, train=validate, eval=test) |
| `a8_models.py` | DT / LogReg / SVM / MLP / RF + 阈值：精度、延迟、体积 · accuracy, latency, size | **PUBLICATION** (200 realisations; latency at batch 1) |
| `robustness.py` | CSI 噪声 / Jakes 信道老化 / 决策 staleness 三连 · CSI noise, Jakes aging, decision staleness | **PUBLICATION** (200 realisations) |

Read the `PUBLICATION` / `DIAGNOSTIC` marker in each file's header before quoting anything from it —
it is the file's own statement of whether its numbers may enter the paper.

## 已删除的实验 / Deleted experiments

Recorded so their absence reads as a decision, not a gap. Each was scored by the retired v3 engine.

| 脚本 / script | 何时 / when | 由什么取代 / superseded by |
|---|---|---|
| `a1_pareto.py` | R67 (c) | no λ>0 frontier exists under the frozen protocol; the payload–F1 plane is `fig_pareto_test.pdf` from `results/main/frozen_curves.csv` |
| `a2_difficulty.py` (+ its two CSVs) | R67 (c) | `../difficulty_frozen.py` → `results/sensitivity/difficulty_frozen.csv` (R66-1/2) |
| `c_channels.py` | R67 (c) | the Rician bracket is `../rician_bracket.py` → `results/sensitivity/item5c_*.csv` |
| `a9_hardening.py` | R65 | `results/sensitivity/multiseed_hardening.csv` is the surviving product |
