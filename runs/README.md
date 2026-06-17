# `runs/` — 训练与评测输出 / Training & evaluation outputs

## 中文

这里全是**脚本跑出来的产物**（模型 `.pkl`、数据集 `.csv`、图）。不是手写代码,不要手改。
文件夹名带版本号,反映迭代历史——**新手只需认准 `v2`（主用）**,其余多为早期或专项输出。

| 子目录 | 是什么 | 还在用吗 |
|---|---|---|
| **`v2/`** | **主版本**：3-way 数据集 `dataset.csv` + 部署模型 `rf_full.pkl`（以及 ablation 用的 `rf_base/rf_csi.pkl`）+ 特征重要性 + 图 | ✅ 论文主结果的来源 |
| `v1/` | 早期 2-way（仅 AWGN）原型的数据集 + 模型 | ⚠️ 已被 v2 取代,保留作历史 |
| `v3/`, `v3_with_rf/` | 早期经验 AP-vs-SNR 图（含 RF 叠加）| ⚠️ 论文最终图在 `../paper/figures/` |
| `v4_figures/` | 特征重要性 / 堆叠面积 最终图 | ✅ 已并入 paper/figures |
| `v4_csi_noise/` | CSI 噪声 ablation 结果 + 图 | ✅ |
| `v4_multiseed/` | 5-seed RF 训练的均值±方差 | ✅ |
| `v4_where2comm/` | Where2comm 基线结果 | ✅ |
| `v4_e2e/`, `v4_true_e2e/`, `v4_latency/` | 端到端验证 / 真实 AP / 延迟测量结果 | ✅ |

> 关键文件 / key file：**`v2/rf_full.pkl`** 就是论文部署的 selector,`test_split_pipeline` 和
> `extra_experiments` 都加载它。删不得。

## English

Everything here is **script output** (`.pkl` models, `.csv` datasets, figures)—not source code, don't
hand-edit. Folder names carry version numbers reflecting the iteration history. **Newcomers only need
`v2` (the main version)**; the rest are earlier or special-purpose outputs (see table above).

The canonical artifact is **`v2/rf_full.pkl`**, the deployed selector loaded by both `test_split_pipeline`
and `extra_experiments`. Do not delete it. `v1`, `v3`, `v3_with_rf` are superseded earlier iterations kept
for history; the paper's final figures live in `../paper/figures/`.
