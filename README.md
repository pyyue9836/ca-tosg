# CA-TOSG — Channel-Aware Task-Oriented Semantic Granularity Selection

> 面向带宽受限 V2V 协作感知的「信道感知 + 任务导向」语义粒度选择
> (IEEE TVT 投稿代码与论文 / code & paper for the IEEE TVT submission, P. Yue, Univ. of Bristol)

---

## 一句话项目简介 / One-line summary

**中文**：每一帧，自车（ego）根据自己的感知线索 + 估计的信道质量，决定向协作车请求哪种消息——
紧凑的**物体级 L**（≈0.024 Mbit）还是压缩的**特征级 C**（LDPC+16/256-QAM）。只有当任务收益值得付出
带宽与信道风险时才用特征级。核心卖点是 **payload–F1 帕累托效率**，而不是平均精度。

**English**: Per frame, the ego vehicle decides—from its own perception cues plus estimated channel
state—which message to request from the collaborator: a compact **object-level L** (≈0.024 Mbit) or a
compressed **feature-level C** (LDPC+16/256-QAM). Feature-level is used only when the task gain justifies
the payload and channel risk. The contribution is **payload–F1 Pareto efficiency**, not average accuracy.

---

## 新手从这里开始 / Start here (reading order)

1. 读 `paper/main.tex`（或 `paper_overleaf.zip` 编译出的 PDF）——论文本体 / the paper itself.
2. 看本文件的「文件夹地图」 / read the folder map below.
3. 想复现核心结果，进 `test_split_pipeline/`（泛化实验）和 `extra_experiments/`（修订实验 A1–A8, C）。

> ⚠️ 这是论文代码路径的**只读快照**（来自更大的 OpenCOOD 工作目录）。脚本里写死的路径
> （如 `opv2v_data_dumping/`、`peiyi_work/05_pretrained_models/`）只在那个完整目录里能跑，
> 这里保留原样是为了可追溯，单独拿出来**不保证能直接运行**。
> This is a read-only snapshot of the paper's code path; hard-coded paths only resolve inside the full
> OpenCOOD tree, so scripts are kept verbatim for traceability and are not expected to run standalone.

---

## 文件夹地图 / Folder map

| 文件夹 / folder | 是什么 / what it is | 看哪个 README |
|---|---|---|
| `paper/` | LaTeX 论文源码 + 图 / paper source + figures | `paper/README.md` |
| `test_split_pipeline/` | OPV2V test + Culver-City **泛化实验**流水线（5 阶段）/ generalisation pipeline | `test_split_pipeline/README.md` |
| `extra_experiments/` | **修订实验 A1–A8 + C**（审稿意见补充）/ revision experiments | `extra_experiments/README.md` |
| `extra_figures/` | 信道 BLER 图 + 定性 BEV 图脚本 / channel-BLER & qualitative-BEV figure scripts | `extra_figures/README.md` |
| `runs/` | 训练/评测**输出**（模型、CSV、图）/ training & eval outputs | `runs/README.md` |
| (根目录脚本) | selector 训练、数据构建、绘图等 / selector training, dataset building, plotting | 见下表 / see below |

---

## 根目录脚本一览 / Root-level scripts

> 命名规律 / naming: 带 `v2` 的是**主用/部署版**；`v1` 是早期 2-way 原型（仅 AWGN），已被取代但保留作历史。
> `v2` scripts are the **main/deployed** version; `v1` is the early 2-way (AWGN-only) prototype, superseded but kept.

| 脚本 / script | 作用 / purpose |
|---|---|
| `make_dataset_v2.py` | **主**：构建信道感知 oracle 数据集（AWGN+Rayleigh，3-way L/C16/C256）/ build the oracle dataset (main) |
| `train_rf_v2.py` | **主**：训练 3-way RF selector（部署模型）/ train the deployed 3-way RF selector |
| `train_rf_multiseed.py` | 5-seed 重复训练，报告均值±方差 / multi-seed training for mean±std |
| `true_e2e_ap_inference.py` | 用缓存 .npy 做**真实端到端 AP** / true end-to-end AP from cached predictions |
| `e2e_inference_verify.py` | 部署模式验证（经验 ego floor）/ deployment-mode verification |
| `where2comm_compare.py` | Where2comm 基线（理想信道单点参考）/ Where2comm baseline reference |
| `csi_noise_ablation.py` | CSI 估计噪声鲁棒性（σ 扫描）/ CSI-noise robustness sweep |
| `rf_latency_benchmark.py` | RF 单帧推理延迟（P50/P95/P99）/ RF inference latency |
| `plot_feature_importance.py` | 特征重要性条形图 / feature-importance bar chart |
| `plot_stacked_area.py` | 决策占比 ρ vs SNR 堆叠面积图 / decision-ratio stacked area |
| `plot_with_rf_v3b.py` | **最终版**：经验 AP 曲线 + RF 策略叠加 / final AP-vs-SNR figures |
| `make_dataset.py`, `train_rf.py`, `snr_decision_plot.py`, `plot_baselines_v3.py` | 早期版本，保留作历史 / earlier versions, kept for history |

---

## 这次修订新增了什么 / What's new in this revision

- **泛化验证** / generalisation: OPV2V test（2,170 帧）+ Culver-City（550 帧，域偏移），冻结 selector 直接迁移
  （`test_split_pipeline/`）。
- **9 组修订实验** / 9 revision experiments（`extra_experiments/`）: A1 帕累托前沿、A2 难度分层、
  A3 场景子集、A4 JSCC-aware、A5 请求延迟/因果、A6 L 可靠性、A7 ablation+SNR 阈值、A8 模型比较、C Rician+信道老化。
- **2 张新图** / 2 new figures（`extra_figures/`）: 信道 BLER 曲线、定性 BEV 对比。

---

## 关键结果 / Key results

| split | payload (Mbit/frame) | F1 | 说明 / note |
|---|---|---|---|
| OPV2V validate | 0.076 | 0.865 | 主结果，回收 oracle F1 的 99.7% / 84.6% 低于 Fixed C16 |
| OPV2V test | 0.081 | 0.888 | 场景不相交,冻结 selector / scene-disjoint, frozen selector |
| Culver-City | 0.085 | 0.891 | 真实路网域偏移 / real-road-layout domain shift |

诚实说明 / honest note：在**平均** F1 上，一个简单 SNR 阈值规则即可匹配 RF；RF 的优势在**带宽效率**
（同 F1、更低 payload）。增益集中在「**困难帧 × 好信道**」（AWGN≥14dB 难帧最高 +0.045 F1）。
On *average* F1 a simple SNR-threshold rule matches the RF; the RF wins on *bandwidth efficiency*, and
the gain concentrates where a hard frame meets a usable channel.
