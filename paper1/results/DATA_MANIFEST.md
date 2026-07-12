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
| **JSCC learned stage2 checkpoints** | `stage2_{awgn,rayleigh,ofdm}_learned_v3/stage2_whole_map_4000steps.pth` | UNKNOWN | (was a training run, NOT to be retrained per Step-5 scope) | GPU hours (train) | **MISSING from tree** |
| JSCC per-frame decode (per channel×SNR) | `code/extra_experiments/jscc_perframe/runs/<tag>_<ch>_snrNN/npy/` | — | `run_jscc_perframe.py` (needs the checkpoints above) | GPU ~min/(ch,SNR) | **DELETED** |
| channel_codec_ap JSCC rows | `results/channel_codec_ap/*jscc*` | — | derived from JSCC decode above | — | **absent (blocked on JSCC ckpt)** |

## BLOCKER (2026-07-12, Step-5 Phase C/D): JSCC learned checkpoints missing
`run_jscc_perframe.py` expects one per-channel checkpoint
`peiyi_work/04_experiment_logs/importance_map_jscc/stage2_{ch}_learned_v3/stage2_whole_map_4000steps.pth`
(path itself is stale: `04_experiment_logs` was renamed to `experiment_logs`, and the driver's
`REPO=parents[4]` is off by one after `extra_experiments` moved under `code/`). Neither the renamed
path NOR any `stage2_*_learned*` dir NOR any `*4000steps*.pth` exists in the working tree.
The cleanup archive `OpenCOOD_cleanup_archive_20260604/opencood_logs/opencood/logs/` holds per-SNR
snapshot checkpoints `importance_map_jscc_{ch}_..._snr_sweep_stage2_whole_map/snrNN/net_epoch1.pth`
for all three channels, but (a) they are per-SNR snapshots, not the single SNR-agnostic learned
checkpoint the driver copies, and (b) their correspondence to the paper's `importance_source=learned`
reproduction is unverified. Running GPU inference on an unverified checkpoint would silently produce
JSCC numbers that do not match the published reproduction — exactly the contamination P1 is fighting.
**ACTION REQUIRED from supervisor:** locate/confirm the canonical learned JSCC checkpoints (H: drive
backup? or confirm which archived snapshot is canonical) before Track A GPU re-inference.
