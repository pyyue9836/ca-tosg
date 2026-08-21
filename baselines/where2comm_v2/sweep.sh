#!/usr/bin/env bash
# R52: the remaining threshold grid, all splits, cached per point. Sequential by design --
# one GPU, and a failed point must not take the rest of the sweep with it.
set -u
CKPT=/mnt/h/wsl_backup/OpenCOOD_20260601_1326/opencood/logs/point_pillar_where2comm_2026_05_22_17_56_51
ROOT=/home/josh/cooperative_semantic_perception/ca-tosg
export PYTHONPATH=/home/josh/cooperative_semantic_perception/OpenCOOD
cd "$ROOT"
# R54: refinement round, registered as an EARLY firing of plan v2 fuse 3. The measured
# threshold->rate map is far steeper than the plan assumed (0.01 -> 0.48, 0.05 -> 0.032,
# 0.10 -> 0.0099), so every threshold at or above 0.10 collapses to "send almost nothing"
# and the rates the budgets actually need (~0.10/0.20/0.30 of dense) sit in the unsampled
# gap between 0.01 and 0.05. The upper five points are replaced by five inside that gap;
# the completed 0.0 / 0.01 / 0.05 / 0.10 points are kept as the anchors and as the
# collapse evidence.
# R55 amendment A1: the LAST refinement round, inside the 0.010-0.015 cliff. Registered as an
# explicit amendment to plan v2 fuse 3, whose single permitted pass was spent in R54. The
# endpoint is pre-registered: after this round there is no further refinement, whether or not
# a point lands within +-20% of a cap.
for thr in 0.011 0.012 0.013; do
  for split in validate test culver; do
    out="data/where2comm_v2/${split}_thr${thr}.npz"
    if [ -f "${out%.npz}.json" ]; then echo "skip $out (done)"; continue; fi
    echo "=== $(date +%H:%M:%S) threshold=$thr split=$split ==="
    python baselines/where2comm_v2/run_inference.py --model_dir "$CKPT" \
        --split "$split" --threshold "$thr" --out "$out" 2>&1 | grep -vE 'RuntimeWarning|lib.inter|too many cavs'
  done
done
# the dense point on the two splits it has not covered yet
for split in test culver; do
  out="data/where2comm_v2/${split}_thr0.0.npz"
  [ -f "${out%.npz}.json" ] && continue
  echo "=== $(date +%H:%M:%S) threshold=0.0 split=$split ==="
  python baselines/where2comm_v2/run_inference.py --model_dir "$CKPT" \
      --split "$split" --threshold 0.0 --out "$out" 2>&1 | grep -vE 'RuntimeWarning|lib.inter|too many cavs'
done
echo "SWEEP COMPLETE $(date +%H:%M:%S)"
