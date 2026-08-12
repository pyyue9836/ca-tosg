# ImportanceMapJSCC (baseline)

| | |
|---|---|
| **Source paper** | Sheng, Ye, Liang, Jin, Li. *Semantic Communication for Cooperative Perception Based on Importance Map.* Journal of the Franklin Institute, 361, 2024. |
| **Modifications** | Reproduced inside the sibling OpenCOOD checkout on the same PointPillar backbone and OPV2V split. **Use `importance_source: learned`, not `psm`** — only the learned importance map reproduces the paper's absolute values and its gap to the LDPC baseline. Two-stage training: stage-1 reconstruction pre-training, stage-2 whole-network. The paper's upper bound is the *identity channel with the codec kept* (not a codec bypass). Full edit log: `CHANGELOG.md`. |
| **Checkpoint** | `stage2_{awgn,rayleigh,ofdm}_learned_v3/stage2_whole_map_4000steps.pth` on the external `H:` drive (33 MB each), registered in `docs/data_manifest.md`. They are **not retrainable within this project's scope** — treat them as fixed inputs. |
| **Data split** | OPV2V validate + test, SNR sweep over the same Es/N0 axis as the LDPC-QAM tables, so the JSCC and separate-coding curves are directly comparable. |
| **Run command** | `python baselines/importance_map_jscc/perframe/jscc_sweep.py --mode sweep` for the per-frame decode cache (~10 GPU-hours, registered in `docs/data_manifest.md`), then `build_two_regime_edge_clean.py` / `jscc_selector_compare.py` for the tables. `scripts/*.sh` are the original run drivers, kept verbatim as the record of how the checkpoints were produced. |
| **Output** | `results/baselines/importance_map_jscc/` — `two_regime_edge_clean.csv` (deployed), `two_regime_kfold_diag.csv` (in-distribution diagnostic), `jscc_selector_{awgn,rayleigh,ofdm}.csv`, `channel_codec_ap_{validate,test}.csv`, `jscc_ap_f1.csv`. |

**Read the two-regime numbers with their history.** An earlier "+0.027 edge" was a train-on-test
leakage; the clean cross-split result is negative and the k-fold in-distribution diagnostic is
+0.022. `two_regime_edge_clean.csv` is the deployed one — do not quote `two_regime_edge.csv`.
