# `extra_experiments/out/` — 修订实验结果 CSV / Result CSVs

## 中文

`extra_experiments/` 里各脚本跑出来的结果表（纯数据，可直接看或导入论文）。**这些是输出,不要手改**——重跑对应脚本即可再生。

| 文件 | 来自 | 内容 |
|---|---|---|
| `a1_pareto_points.csv` | `a1_pareto.py` | 各策略在 payload–F1 平面的坐标点 |
| `a2_difficulty.csv` | `a2_difficulty.py` | 全信道下 easy/med/hard 的 F1/增益/动作占比 |
| `a2_difficulty_goodchannel.csv` | `a2_difficulty.py` | 「好信道」（AWGN≥14dB）下的难度分层 |
| `a3_subsets.csv` | `a3_subsets.py` | 场景子集 C 激活率 + 好信道增益 |
| `a5_causality.csv` | `a5_causality.py` | 延迟 vs stale 率 / F1 降幅 |
| `a6_l_reliability.csv` | `a6_l_reliability.py` | L BLER/重传成本 网格 |
| `a7_ablation.csv` | `a7_ablation.py` | 特征子集的 F1/payload |
| `a7_snr_threshold.csv` | `a7_ablation.py` | SNR 阈值 τ 扫描 |
| `a8_models.csv` | `a8_models.py` | 各模型精度/延迟/体积 |
| `c_rician.csv` | `c_channels.py` | Rician 各 K 因子的决策/AP |
| `c_aging.csv` | `c_channels.py` | CSI 延迟 vs F1 |

## English

Result tables produced by the scripts in `extra_experiments/` (plain data; read directly or drop into
the paper). **These are outputs—do not hand-edit**; re-run the corresponding script to regenerate.
See the table above for the source script and contents of each CSV.
