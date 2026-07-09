#!/usr/bin/env bash
# Original-style MAP reproduction v0.
# - Train one MAP-JSCC model with a learned importance map.
# - Evaluate the same checkpoint under AWGN, Rayleigh, and OFDM channels.
# - Use the same checkpoint's identity-channel result as the ceiling.
# - Do not use Where2Comm as an upper bound.
# - Do not plot Rayleigh/OFDM LDPC proxy curves unless channel-matched baselines exist.
set -euo pipefail
cd /home/josh/cooperative_semantic_perception/OpenCOOD

RUN="conda run --no-capture-output -n opencood python -u"
EXP=experiment_logs/importance_map_jscc
J=$EXP/jscc_eval
WARM=opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22/net_epoch50.pth
ACFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml
RCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh.yaml
OCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm.yaml
S1=${S1:-2000}
S2=${S2:-6000}
MAX_SAMPLES=${MAX_SAMPLES:-1000}
NUM_WORKERS=${NUM_WORKERS:-4}
CR_J=0.005
CR_16=0.00125
CR_256=0.0025

S1DIR=$EXP/stage1_map_original_v0
S2DIR=$EXP/stage2_map_original_v0
CKPT=$S2DIR/stage2_whole_map_${S2}steps.pth

mkdir -p "$J"

echo "=== [train] stage1 learned MAP + JSCC reconstruction ==="
$RUN analysis_tools/stage1_pretrain_jscc_reconstruction_sttopk.py \
  --yaml_path "$ACFG" --warm_ckpt "$WARM" --out_dir "$S1DIR" --max_steps "$S1"

echo "=== [train] stage2 whole-network MAP-JSCC ==="
$RUN analysis_tools/stage2_whole_network_map_jscc.py \
  --yaml_path "$ACFG" --stage1_ckpt "$S1DIR/stage1_rec_sttopk_${S1}steps.pth" \
  --out_dir "$S2DIR" --max_steps "$S2" --lambda_rec 0.5

echo "=== [eval] same-checkpoint identity ceiling and ego-only ==="
$RUN analysis_tools/run_jscc_eval.py --config "$ACFG" --ckpt "$CKPT" --channel identity \
  --snrs 60 --cr "$CR_J" --max_samples "$MAX_SAMPLES" --num_workers "$NUM_WORKERS" \
  --tag map_identity
$RUN analysis_tools/run_jscc_eval.py --config "$ACFG" --ckpt "$CKPT" --channel remote_zero \
  --snrs 0 --cr "$CR_J" --max_samples "$MAX_SAMPLES" --num_workers "$NUM_WORKERS" \
  --tag map_ego_only

echo "=== [eval] JSCC channel sweeps, one trained model ==="
$RUN analysis_tools/run_jscc_eval.py --config "$ACFG" --ckpt "$CKPT" --channel awgn \
  --snrs 0,2,4,6,8,12,16,20 --cr "$CR_J" --max_samples "$MAX_SAMPLES" \
  --num_workers "$NUM_WORKERS" --tag awgn_jscc
$RUN analysis_tools/run_jscc_eval.py --config "$RCFG" --ckpt "$CKPT" --channel rayleigh \
  --snrs 0,6,12,15,18,22,26,30 --cr "$CR_J" --max_samples "$MAX_SAMPLES" \
  --num_workers "$NUM_WORKERS" --tag rayleigh_jscc
$RUN analysis_tools/run_jscc_eval.py --config "$OCFG" --ckpt "$CKPT" --channel ofdm \
  --snrs 0,2,4,6,8,12,16,20 --cr "$CR_J" --max_samples "$MAX_SAMPLES" \
  --num_workers "$NUM_WORKERS" --tag ofdm_jscc

echo "=== [eval] AWGN separate-coding proxy baseline only ==="
$RUN analysis_tools/run_jscc_eval.py --config "$ACFG" --ckpt "$CKPT" --channel ldpc16qam \
  --snrs 0,6,8,9,10,12,16 --cr "$CR_16" --max_samples "$MAX_SAMPLES" \
  --num_workers "$NUM_WORKERS" --tag awgn_ldpc16
$RUN analysis_tools/run_jscc_eval.py --config "$ACFG" --ckpt "$CKPT" --channel ldpc256qam \
  --snrs 0,12,15,18,20 --cr "$CR_256" --max_samples "$MAX_SAMPLES" \
  --num_workers "$NUM_WORKERS" --tag awgn_ldpc256

echo "=== [plot] strict figures ==="
$RUN analysis_tools/plot_paper_figures.py --channel awgn \
  --jscc "$J/awgn_jscc_summary.csv" \
  --ldpc16 "$J/awgn_ldpc16_summary.csv" \
  --ldpc256 "$J/awgn_ldpc256_summary.csv" \
  --upper_csv "$J/map_identity_summary.csv"
$RUN analysis_tools/plot_paper_figures.py --channel rayleigh \
  --jscc "$J/rayleigh_jscc_summary.csv" \
  --upper_csv "$J/map_identity_summary.csv"
$RUN analysis_tools/plot_paper_figures.py --channel ofdm \
  --jscc "$J/ofdm_jscc_summary.csv" \
  --upper_csv "$J/map_identity_summary.csv"

echo "==================== MAP ORIGINAL v0 RESULTS ===================="
echo "[identity ceiling]"; cut -d, -f1-4 "$J/map_identity_summary.csv"
echo "[ego-only]"; cut -d, -f1-4 "$J/map_ego_only_summary.csv"
for c in awgn rayleigh ofdm; do
  echo "[$c JSCC]"; cut -d, -f1-4 "$J/${c}_jscc_summary.csv"
done
echo "[AWGN LDPC16 proxy]"; cut -d, -f1-4 "$J/awgn_ldpc16_summary.csv"
echo "[AWGN LDPC256 proxy]"; cut -d, -f1-4 "$J/awgn_ldpc256_summary.csv"
ls -la "$EXP"/paper_range_figures/fig_*jscc_vs_separate.png
echo "[DONE] MAP ORIGINAL v0 COMPLETE."
