# V2V Cooperative Perception — Research Code / V2V 协作感知科研代码

> Peiyi Yue, University of Bristol. 本仓库按论文组织,每篇论文一个顶层文件夹。
> Organised by paper: one top-level folder per paper. Only useful code is kept here.

---

## 目录 / Contents

| 文件夹 / folder | 内容 / what | 状态 / status |
|---|---|---|
| **`paper1_ca_tosg/`** | **CA-TOSG** —— 信道感知任务导向语义粒度选择(IEEE TVT)的全部代码、实验、论文源码 / the complete CA-TOSG paper | ✅ 完成 / complete |
| `shared_infra/` | 共享基础设施:OpenCOOD 源码改动(13 个 `#self+` 文件)+ BLER 表/JSCC 基线 + SComCP 复现代码 / shared infra: OpenCOOD mods + channel BLER table + JSCC/SComCP baseline code | ✅ 备份 / backed up |
| `paper2_TBD/` | 第二篇论文,占位,待开始 / reserved for the second paper, not started yet | 🚧 待定 / TBD |

每个文件夹内都有自己的 `README.md`(中英双语)详细说明。**先看 [`paper1_ca_tosg/README.md`](paper1_ca_tosg/README.md)。**
Each folder has its own bilingual `README.md`. Start with [`paper1_ca_tosg/README.md`](paper1_ca_tosg/README.md).

---

## 说明 / Notes

- 本仓库只放**论文用到的、整理过的代码**;早期原型、构建产物、超大二进制(模型权重 `.pth`、点云缓存 `.npy`、数据集)**不入库**。
  Only cleaned, paper-used code is kept; early prototypes, build artifacts, and large binaries
  (`.pth` checkpoints, `.npy` caches, datasets) are excluded.
- 代码是论文代码路径的**快照**,依赖完整 OpenCOOD 工作树 + 预训练权重 + 数据集才能实跑;
  这里供审阅与追溯。This is a snapshot for review/traceability; it depends on the full OpenCOOD
  tree, pretrained checkpoints and datasets to actually run.
