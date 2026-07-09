#!/usr/bin/env bash
# Codec-v2 paper-faithful redo.
#   change 1: removed the equal-bandwidth `bw` token-drop from the LDPC baseline
#             -> digital baseline reaches the upper bound at high SNR (BLER->0).
#   change 2: c_complex 16 -> 32 -> JSCC reconstruction near-lossless, identity
#             ceiling approaches the upper bound (closes the 0.85->0.89 gap).
# Retrains all 3 codecs (stage1->stage2), re-sweeps JSCC + LDPC16/256, redraws.
# Sequential only (OPV2V loading is CPU-bound).
set -u
cd /home/josh/cooperative_semantic_perception/OpenCOOD
RUN="conda run --no-capture-output -n opencood python -u"
EXP=experiment_logs/importance_map_jscc
J=$EXP/jscc_eval
W2C=opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22
ACFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml
RCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh.yaml
OCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm.yaml
S1STEPS=2000
S2STEPS=6000

train () {  # CH CFG
  local CH=$1 CFG=$2
  local S1DIR=$EXP/stage1_${CH}_cmplx32
  local S1=$S1DIR/stage1_rec_sttopk_${S1STEPS}steps.pth
  local S2DIR=$EXP/stage2_${CH}_cmplx32
  echo "=== [$CH] stage1 (c_complex=32) ==="
  $RUN analysis_tools/stage1_pretrain_jscc_reconstruction_sttopk.py \
    --yaml_path $CFG --warm_ckpt $W2C/net_epoch50.pth \
    --out_dir $S1DIR --max_steps $S1STEPS || { echo "[FATAL] $CH stage1 failed"; return 1; }
  echo "=== [$CH] stage2 ==="
  $RUN analysis_tools/stage2_whole_network_map_jscc.py \
    --yaml_path $CFG --stage1_ckpt $S1 --out_dir $S2DIR \
    --max_steps $S2STEPS --lambda_rec 0.5 || { echo "[FATAL] $CH stage2 failed"; return 1; }
}

train awgn     $ACFG || exit 1
train rayleigh $RCFG || exit 1
train ofdm     $OCFG || exit 1

AWGN_S2=$EXP/stage2_awgn_cmplx32/stage2_whole_map_${S2STEPS}steps.pth
RAY_S2=$EXP/stage2_rayleigh_cmplx32/stage2_whole_map_${S2STEPS}steps.pth
OFDM_S2=$EXP/stage2_ofdm_cmplx32/stage2_whole_map_${S2STEPS}steps.pth

# ---- Gate C: identity (perfect channel) ceiling + ego-only ----
$RUN analysis_tools/run_jscc_eval.py --config $ACFG --ckpt $AWGN_S2 \
  --channel identity --snrs 60 --max_samples 1000 --num_workers 4 --tag awgn_identity || true
$RUN analysis_tools/run_jscc_eval.py --config $ACFG --ckpt $AWGN_S2 \
  --channel remote_zero --snrs 0 --max_samples 1000 --num_workers 4 --tag ego_only || true
echo "[Gate C] identity ceiling:"; cat $J/awgn_identity_summary.csv
echo "[Gate C] ego-only:";        cat $J/ego_only_summary.csv

# ---- JSCC sweeps ----
$RUN analysis_tools/run_jscc_eval.py --config $ACFG --ckpt $AWGN_S2 \
  --channel awgn --snrs 0,4,8,12,16,20 --max_samples 1000 --num_workers 4 --tag awgn_jscc || true
$RUN analysis_tools/run_jscc_eval.py --config $RCFG --ckpt $RAY_S2 \
  --channel rayleigh --snrs 0,5,10,15,20 --max_samples 1000 --num_workers 4 --tag rayleigh_jscc || true
$RUN analysis_tools/run_jscc_eval.py --config $OCFG --ckpt $OFDM_S2 \
  --channel ofdm --snrs 0,5,10,15,20 --max_samples 1000 --num_workers 4 --tag ofdm_jscc || true

# ---- LDPC16/256 baselines on each channel net (no bw -> reach upper bound high SNR) ----
sep () {  # CH CFG S2
  local CH=$1 CFG=$2 S2=$3
  $RUN analysis_tools/run_jscc_eval.py --config $CFG --ckpt $S2 \
    --channel ldpc16qam  --snrs 0,6,8,10,12,16   --max_samples 1000 --num_workers 4 --tag ${CH}_ldpc16  || true
  $RUN analysis_tools/run_jscc_eval.py --config $CFG --ckpt $S2 \
    --channel ldpc256qam --snrs 0,12,16,18,20,22 --max_samples 1000 --num_workers 4 --tag ${CH}_ldpc256 || true
}
sep awgn     $ACFG $AWGN_S2
sep rayleigh $RCFG $RAY_S2
sep ofdm     $OCFG $OFDM_S2

# ---- redraw figures (upper bound stays where2comm 0.89/0.79) ----
for c in awgn rayleigh ofdm; do
  $RUN analysis_tools/plot_paper_figures.py --channel $c \
    --jscc $J/${c}_jscc_summary.csv --ldpc16 $J/${c}_ldpc16_summary.csv \
    --ldpc256 $J/${c}_ldpc256_summary.csv --upper_ap05 0.89 --upper_ap07 0.79 || true
done

echo "==================== CODEC-v2 RESULTS ===================="
echo "[identity ceiling]"; cat $J/awgn_identity_summary.csv | cut -d, -f1-4
echo "[ego-only]";         cat $J/ego_only_summary.csv | cut -d, -f1-4
for c in awgn rayleigh ofdm; do
  echo "[$c JSCC]";   cat $J/${c}_jscc_summary.csv | cut -d, -f1-4
  echo "[$c LDPC16]"; cat $J/${c}_ldpc16_summary.csv | cut -d, -f1-4
  echo "[$c LDPC256]";cat $J/${c}_ldpc256_summary.csv | cut -d, -f1-4
done
ls -la $EXP/paper_range_figures/fig_*jscc_vs_separate.png
echo "[DONE] CODEC-v2 REPRODUCTION COMPLETE."
