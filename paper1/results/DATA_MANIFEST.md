# DATA_MANIFEST — GPU-regeneratable caches (CA-TOSG paper1)

**Rule (supervisor 2026-07-12, learned the hard way when the JSCC decode caches were deleted):**
any cache that needs GPU hours to regenerate MUST be registered here with its md5 + regeneration
command + cost estimate. **Cleanup scripts may ONLY delete files that are NOT in this manifest.**
Three lines of insurance against a full-round GPU re-run.

| cache | path | md5 | regen command | est. cost | status |
|---|---|---|---|---|---|
| late-fusion per-frame boxes+scores | `gs_rerun/late_{validate,test,culver}.npz` | 86334f1bb9f3 / 558364852f0a / 052a798d4ff8 | `code/regen_preds_with_scores.py` (late) | ~GPU 10 min/split | PRESENT |
| compressed per-frame boxes+scores | `gs_rerun/comp_{validate,test,culver}.npz` | 83d5eb8988a3 / f5126baaad88 / 11b61a9e020e | `code/regen_preds_with_scores.py` (comp) | ~GPU 10 min/split | PRESENT |
| ego-only per-frame boxes+scores | `gs_rerun/ego_{validate,test,culver}.npz` | fd66abd89e46 / c14cad677e0a / e62b17375a27 | `code/run_ego_only.py` | ~GPU 10 min/split | PRESENT |
| **JSCC learned stage2 checkpoints** | `/mnt/h/opencood_project/outputs/experiment_logs/importance_map_jscc/stage2_{ch}_learned_v3/stage2_whole_map_4000steps.pth` | awgn 74c1319ab562 / rayleigh c5a02fd77154 / ofdm d75126199898 | training run (NOT retrained per Step-5 scope; used as-is) | 33 MB each | **FOUND on H: (verified, smoke-tested)** |
| **JSCC per-frame decode boxes+scores+gts (36 = 3ch×2split×6SNR)** | `gs_rerun/jscc_v3/jscc_{ch}_{split}_snr{NN}.npz` | 36-npz set md5 `02b9187dc8e1005b` (288 MB) | `code/extra_experiments/jscc_perframe/jscc_v3_sweep.py --mode sweep` | **~10 GPU-hours (full sweep)** | **PRESENT (36/36, survived the 2026-07-12 power outage)** |
| channel_codec_ap JSCC rows | `results/channel_codec_ap/*jscc*` | — | derived from JSCC decode above | — | pending Track A |

## RESOLVED (2026-07-12): JSCC learned checkpoints are on the H: drive
Initial over-call ("missing") was premature — a foreground search excluded `/mnt`; the background
full-disk search found all three canonical learned checkpoints at
`/mnt/h/opencood_project/outputs/experiment_logs/importance_map_jscc/stage2_{ch}_learned_v3/stage2_whole_map_4000steps.pth`
(the `pretrained_models` symlink already points into `/mnt/h/opencood_project`). Filenames match the
driver's expectation exactly; `importance_source: learned` confirmed in the yaml. `run_jscc_perframe.py`
paths REPAIRED (REPO parents[4]->[5]; INFER -> paper1/analysis_tools; CKPT -> H:). Smoke test PASSED
(awgn snr14, 10 frames: AP@.5=0.783, per-frame pred/gt npy written).
**Remaining Track-A setup (not a blocker, engineering):** `inference_subset.py --save_npy` writes pred
BOXES + gt but NOT scores; F1 works from boxes, but AP (global-sort) needs per-box scores -> add a
score dump (mirror `regen_preds_with_scores.py`) before the full sweep. Full sweep = validate(1980) +
test(2170) x {awgn,rayleigh,ofdm} x SNR grid = ~40 min per run; SNR grid + total GPU-hour scope to be
confirmed before committing.
