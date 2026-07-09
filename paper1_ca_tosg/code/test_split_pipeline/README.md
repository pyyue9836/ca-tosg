# `test_split_pipeline/` — 泛化实验流水线 / Generalisation pipeline

## 中文

把**在 validate 上训练好的** selector（`../runs/v2/rf_full.pkl`，不重训）直接应用到 OPV2V **test** 和
**Culver-City** 两个留出集上，验证跨场景/跨域泛化。

**5 个阶段（按顺序）**：

| 阶段 | 脚本 | 干什么 |
|---|---|---|
| 0 | `extract_test_data.py` | 解压 OPV2V 三层嵌套压缩包（一次性工具）|
| 1 | `01_gen_predictions.py` | 在 test 上跑 late + compressed 两个 backbone 的推理,缓存逐帧 `.npy`（GPU,~15min）|
| 2 | `02_extract_cues_and_f1.py` | 提取 21 个 LiDAR 线索 + 逐帧 late/compressed F1（CPU,~20min）|
| 3 | `03_build_test_dataset.py` | 加信道感知 oracle 标签（随机 SNR + AWGN/Rayleigh）|
| 4 | `04_eval_rf_on_test.py` | 应用 `rf_full.pkl`,报准确率/payload/F1 + SNR 扫描 |
| 5 | `05_true_e2e_ap_on_test.py` | 真实端到端 AP@0.5/0.7（9 工作点 × 5 信道实现）|

`run_all.py` 一键按序跑完 1–5。

**怎么跑**（先下数据,见下）：
```bash
# 常规 test split
CATOSG_SPLIT=test            PYTHONPATH=. python test_split_pipeline/run_all.py
# Culver-City 域偏移 split
CATOSG_SPLIT=test_culver_city PYTHONPATH=. python test_split_pipeline/run_all.py
```
环境变量 `CATOSG_SPLIT` 控制评测哪个 split：`test` 输出到 `runs/`，`test_culver_city` 输出到 `runs_culver/`。

**前置**：从 [UCLA Box](https://ucla.app.box.com/v/UCLA-MobilityLab-OPV2V) 下 `test.zip`，解压到
`/mnt/h/opencood_project/datasets/opv2v_data_dumping/test/`（仓库里的 symlink 会自动指过去）。

**输出**：`runs/`（test）和 `runs_culver/`（Culver）下的结果 CSV——见各自文件夹。

## English

Applies the **validate-trained** selector (`../runs/v2/rf_full.pkl`, not retrained) to the held-out OPV2V
**test** and **Culver-City** splits, measuring cross-scene / cross-domain generalisation.

The 5 stages are listed in the table above; `run_all.py` runs stages 1–5 in order.

**Run** (after downloading data):
```bash
CATOSG_SPLIT=test            PYTHONPATH=. python test_split_pipeline/run_all.py   # regular test
CATOSG_SPLIT=test_culver_city PYTHONPATH=. python test_split_pipeline/run_all.py  # Culver-City
```
The env var `CATOSG_SPLIT` selects the split: `test` → outputs in `runs/`, `test_culver_city` →
`runs_culver/`.

**Prerequisite**: download OPV2V `test.zip` from the UCLA Box repo and unzip to
`/mnt/h/opencood_project/datasets/opv2v_data_dumping/test/` (the repo symlink resolves there).

**Outputs**: result CSVs under `runs/` (test) and `runs_culver/` (Culver-City).
