# Test-split generalisation pipeline

Runs the full evaluation of the deployed CA-TOSG selector (`runs/v2/rf_full.pkl`, trained on the OPV2V validate split) on the **OPV2V test split** (held-out generalisation).

## Prerequisite

Download OPV2V `test.zip` from the [UCLA Box repo](https://ucla.app.box.com/v/UCLA-MobilityLab-OPV2V) and unzip to:

```
/mnt/h/opencood_project/datasets/opv2v_data_dumping/test/
```

The repo's `opv2v_data_dumping/test/` symlink will resolve there automatically.

## Run

```bash
cd /home/josh/cooperative_semantic_perception/OpenCOOD
PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \
    peiyi_work/01_paper_ca_tosg/test_split_pipeline/run_all.py
```

Total run time ≈ **45-50 min** on RTX 5070 + single CPU core.

## Stages

| Stage | Script | Time | Purpose |
|---|---|---|---|
| 1 | `01_gen_predictions.py` | ~15 min GPU | Run OpenCOOD inference on test for late_fusion + attentive_compression; cache per-frame `.npy` |
| 2 | `02_extract_cues_and_f1.py` | ~20 min CPU+IO | Extract 21 LiDAR cues per frame + per-frame `late_f1`/`compressed_f1` against test GT |
| 3 | `03_build_test_dataset.py` | ~10 s CPU | Add channel-aware oracle labels (random SNR + AWGN/Rayleigh) |
| 4 | `04_eval_rf_on_test.py` | ~30 s CPU | Apply `rf_full.pkl` to test, report accuracy / payload / F1 + SNR sweep |
| 5 | `05_true_e2e_ap_on_test.py` | ~10 min CPU | True end-to-end AP@0.5/0.7 at 9 operating points × 5 channel realisations |

## Outputs

All under `runs/` next to the scripts:

```
runs/
├── test_frame_features.csv     # cues + f1 (stage 2)
├── test_dataset.csv            # + oracle labels (stage 3)
├── test_rf_results.csv         # headline RF generalisation table (stage 4)
├── test_snr_sweep.csv          # rf_frac_*/rf_f1/rf_pay vs SNR (stage 4)
└── test_true_e2e_ap.csv        # true end-to-end AP@0.5/0.7 table (stage 5)
```

## What to do with the results

The numbers in `test_rf_results.csv` and `test_true_e2e_ap.csv` go directly into
the new `\subsection{Generalisation to OPV2V Test Split}` in
`paper/main.tex` (template placeholder already exists with `\todo{}` markers
where the numbers slot in).

Once results are in, the Discussion subsection on single-dataset/single-split
limitation should be **deleted** since the limitation has been resolved.
