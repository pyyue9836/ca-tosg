# `shared_infra/` — 共享基础设施 / Shared infrastructure

## 中文

paper1（及以后论文）依赖、但**不属于某一篇论文独有**的代码与关键小数据。这里是**备份 + 可追溯**用途
（这些东西原本只在本机的完整 OpenCOOD 工作树里）。

### `opencood_modifications/` — 对 OpenCOOD 源码的改动（13 个文件,全部 `#self+` 标记）
按 `opencood/...` 原相对路径保存。**它们物理上应放在完整 OpenCOOD 包的 `opencood/` 下**才能被
`opencood.*` 命名空间和 config 字符串解析；这里是副本备份。
- **新增 10 个**：`models/point_pillar_importance_map_jscc.py`（模型 wrapper）、
  `models/fuse_modules/importance_map_jscc_fuse.py`（ImportanceMapJSCC 复现 = 论文基线 [35]）、
  `models/fuse_modules/scomcp_fuse.py`（SComCP 复现 = 基线）、6 个 ImportanceMapJSCC 信道 config +
  1 个 Where2comm 本地 config。
- **修改 3 个**：`utils/eval_utils.py`（加逐帧 payload + channel-use 带宽指标,CA-TOSG 评测用）、
  `models/fuse_modules/where2comm_fuse.py`（兼容 JSCC fuse 签名）、`hypes_yaml/visualization.yaml`（本地路径）。

### `channel_jscc_baselines/` — 信道模型 + JSCC 基线的关键输入
- `ldpc_qam_bler_table.csv` —— **LDPC+QAM 的 BLER 表**,是整个信道感知 oracle 标注 + A4 图 + Rician
  推导的输入。**没它论文跑不出来。**
- `jscc_eval/*.csv`（25 个）—— ImportanceMapJSCC / LDPC / ego-only 的 per-SNR AP 汇总,A4 图用。

### `scomcp_reproduction/` — SComCP（Gan2026 TVT）复现代码
只放代码 + 配置（`train_scomcp.py`、`eval_sweep_scomcp.py`、`configs/` 等);训练输出/权重(原 240M)
未入库。

## English

Code and small-but-critical data that paper1 (and future papers) depend on but that are **not specific to
one paper**. Kept here for backup and traceability (these originally lived only in the local OpenCOOD tree).

- `opencood_modifications/` — the 13 `#self+` files (10 added, 3 modified) that extend OpenCOOD, saved at
  their original `opencood/...` paths. They must physically sit under a full OpenCOOD package's `opencood/`
  to be import-resolvable; this is a backup copy.
- `channel_jscc_baselines/` — the LDPC+QAM **BLER table** (the input to the channel-aware oracle labelling,
  the Rician derivation, and the A4 figure) and the `jscc_eval/` per-SNR AP summaries.
- `scomcp_reproduction/` — SComCP (Gan2026 TVT) reproduction code only; heavy training outputs excluded.

> ⚠️ 这是备份,不是即跑包。To actually run, drop `opencood_modifications/opencood/*` into a full OpenCOOD
> package and provide the OPV2V data + checkpoints.
