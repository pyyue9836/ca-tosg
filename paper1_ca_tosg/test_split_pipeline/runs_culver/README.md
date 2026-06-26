# `test_split_pipeline/runs_culver/` — Culver-City split 结果 / Culver-City results

**中文**：`run_all.py` 用 `CATOSG_SPLIT=test_culver_city` 跑出的 OPV2V Culver-City（550 帧,真实路网域偏移）结果 CSV。
**English**: result CSVs for the OPV2V Culver-City split (550 frames, real-road-layout domain shift), produced by `run_all.py` with `CATOSG_SPLIT=test_culver_city`.

| 文件 / file | 内容 / content |
|---|---|
| `test_frame_features.csv` | 逐帧 21 线索 + late/compressed F1 / per-frame cues + F1 |
| `test_dataset.csv` | + 信道感知 oracle 标签 / + channel-aware oracle labels |
| `test_rf_results.csv` | RF 泛化 headline（acc/payload/F1）/ headline generalisation |
| `test_snr_sweep.csv` | RF 决策/payload/F1 vs SNR |
| `test_true_e2e_ap.csv` | 真实端到端 AP@0.5/0.7 / true end-to-end AP |

> 文件名仍以 `test_` 开头是沿用同一套 pipeline 脚本;内容是 Culver-City 的。
> Filenames keep the `test_` prefix because the same pipeline scripts produce them; the content is Culver-City's.
