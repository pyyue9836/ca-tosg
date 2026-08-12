# `extra_experiments/` — 修订实验 A1–A8 + C / Revision experiments

## 中文

这是为回应审稿/导师意见新增的一批实验。**全部从缓存的逐帧 CSV 计算，不重跑 GPU 推理**，所以又快又可复现。
- `_common.py` —— 公共工具（payload 口径、特征列、effective-F1、策略实现）。所有 `aX_*.py` 都 import 它，是**单一事实来源**。
- `out/` —— 每个实验输出的结果 CSV（见 `out/README.md`）。
- 图直接写到 `../paper/figures/`。

**怎么跑**（在完整 OpenCOOD 目录下）：`PYTHONPATH=. python extra_experiments/aX_xxx.py`

逐个实验：

| 脚本 | 干什么 | 主要结论 |
|---|---|---|
| `a1_pareto.py` | payload–F1 **帕累托前沿** + 拉格朗日 λ 扫描 | CA-TOSG 在前沿上,固定特征级被 dominated |
| `a2_difficulty.py` | 按难度（easy/med/hard）分层 + 「好信道」切片 | 增益集中在**难帧×好信道**（最高 +0.045 F1）|
| `a3_subsets.py` | occlusion/sparse/long-range 场景子集 + 动作占比 | occlusion/sparse 支持；long-range proxy 不支持（诚实记录）|
| `a4_jscc_aware.py` | JSCC vs LDPC 的 AP-SNR 对比 | JSCC graceful,削弱信道驱动；逐帧 JSCC-aware 留作 future work |
| `a5_causality.py` | 请求延迟/决策 staleness | 一帧延迟 18% 决策变化；建议本地同轮 CSI / 持久偏好 |
| `a6_l_reliability.py` | 物体级 L 不可靠/更贵时的敏感性 | L 越不理想,CA-TOSG 价值越大（结论鲁棒）|
| `a7_ablation.py` | 特征 ablation + **SNR 阈值 baseline** | 阈值在平均 F1 上即可匹配 RF；RF 优势是带宽效率 |
| `a8_models.py` | DT/LogReg/SVM/MLP/RF + 阈值 的精度/延迟/体积 | 所有模型 F1 几乎相同；轻量模型可换 |
| `c_channels.py` | Rician 衰落扫描 + CSI 信道老化（Jakes）| 决策随 K 因子从 Rayleigh-like 平滑过渡到 AWGN-like |

## English

Experiments added to address reviewer/advisor feedback. **All computed from cached per-frame CSVs—no
GPU re-inference**, so they are fast and reproducible.
- `_common.py` — shared helpers (payload accounting, feature columns, effective-F1, policy realisation).
  Every `aX_*.py` imports it; it is the single source of truth.
- `out/` — result CSV per experiment (see `out/README.md`).
- Figures are written directly into `../paper/figures/`.

**Run** (inside the full OpenCOOD tree): `PYTHONPATH=. python extra_experiments/aX_xxx.py`

| script | what it does | takeaway |
|---|---|---|
| `a1_pareto.py` | payload–F1 **Pareto frontier** + Lagrangian λ sweep | CA-TOSG is on the frontier; fixed feature-level is dominated |
| `a2_difficulty.py` | easy/med/hard stratification + good-channel cut | gain concentrates on hard frames × usable channel (up to +0.045 F1) |
| `a3_subsets.py` | occlusion/sparse/long-range subsets + action ratios | occlusion/sparse support it; long-range proxy does not (reported honestly) |
| `a4_jscc_aware.py` | JSCC vs LDPC AP-SNR comparison | graceful JSCC weakens the channel case; per-frame JSCC-aware = future work |
| `a5_causality.py` | request-delay / decision staleness | 18% decision change at one-frame delay; use same-round local CSI / persistent preference |
| `a6_l_reliability.py` | sensitivity to object-level L being unreliable/costlier | the worse L gets, the more CA-TOSG helps (robust conclusion) |
| `a7_ablation.py` | feature ablation + **SNR-threshold baseline** | threshold matches RF on mean F1; RF's edge is bandwidth efficiency |
| `a8_models.py` | DT/LogReg/SVM/MLP/RF + threshold: accuracy/latency/size | all models reach the same F1; a lighter one is deployable |
| `c_channels.py` | Rician fading sweep + CSI aging (Jakes) | decisions interpolate smoothly from Rayleigh-like to AWGN-like with K |
