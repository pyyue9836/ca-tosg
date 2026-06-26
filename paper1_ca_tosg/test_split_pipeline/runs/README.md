# `test_split_pipeline/runs/` — 常规 test split 结果 / Regular test-split results

**中文**：`run_all.py` 用 `CATOSG_SPLIT=test` 跑出的 OPV2V test（2,170 帧）结果 CSV。
**English**: result CSVs for the OPV2V test split (2,170 frames), produced by `run_all.py` with `CATOSG_SPLIT=test`.

| 文件 / file | 内容 / content |
|---|---|
| `test_frame_features.csv` | 逐帧 21 线索 + late/compressed F1 / per-frame cues + F1 |
| `test_dataset.csv` | + 信道感知 oracle 标签 / + channel-aware oracle labels |
| `test_rf_results.csv` | RF 泛化 headline（acc/payload/F1）/ headline generalisation |
| `test_snr_sweep.csv` | RF 决策/payload/F1 vs SNR |
| `test_true_e2e_ap.csv` | 真实端到端 AP@0.5/0.7 / true end-to-end AP |
