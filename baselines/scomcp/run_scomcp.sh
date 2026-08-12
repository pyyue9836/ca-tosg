#!/usr/bin/env bash
# ===========================================================================
# SComCP reproduction driver (paper Algorithm 1 three-stage training + figures)
#
# Edit BASE_CKPT to point at a pretrained PointPillars checkpoint (backbone +
# detection head). SComCP freezes these in stages 1-2, so they must be trained
# first. You can reuse any of your existing point_pillar_* checkpoints whose
# backbone matches base_bev_backbone in the configs (layer_nums [3,5,8],
# num_filters [64,128,256], shrink to 256).
# ===========================================================================
set -e
cd "$(dirname "$0")/.."          # repo root

BASE_CKPT="pretrained_models/point_pillar_importance_map_jscc/net_epochXX.pth"  # <-- EDIT
CFG=peiyi_work/02_scomcp_reproduction/configs
LOGS=opencood/logs

latest () { ls -td ${LOGS}/$1_* 2>/dev/null | head -1; }

# --------------------------- Stage 1: selector ----------------------------
echo "===== STAGE 1: importance-aware feature selection (lossless) ====="
python peiyi_work/02_scomcp_reproduction/train_scomcp.py \
    --hypes_yaml ${CFG}/scomcp_stage1_selector.yaml \
    --warm_start ${BASE_CKPT}
S1=$(latest scomcp_stage1_selector); echo "stage1 dir: ${S1}"
CKPT1=$(cat ${S1}/LAST_CKPT.txt)

# --------------------------- Stage 2: codec -------------------------------
echo "===== STAGE 2: transformer-CA semantic codec (Rayleigh, +0.05*MSE) ====="
python peiyi_work/02_scomcp_reproduction/train_scomcp.py \
    --hypes_yaml ${CFG}/scomcp_stage2_codec.yaml \
    --warm_start ${CKPT1}
S2=$(latest scomcp_stage2_codec); echo "stage2 dir: ${S2}"
CKPT2=$(cat ${S2}/LAST_CKPT.txt)

# --------------------------- Stage 3: joint -------------------------------
echo "===== STAGE 3: joint end-to-end fine-tune (Rayleigh) ====="
python peiyi_work/02_scomcp_reproduction/train_scomcp.py \
    --hypes_yaml ${CFG}/scomcp_stage3_joint.yaml \
    --warm_start ${CKPT2}
S3=$(latest scomcp_stage3_joint); echo "stage3 dir (FINAL SComCP): ${S3}"

# =========================== Evaluation / figures ==========================
# Fig. 6 (AWGN) and Fig. 7 (Rayleigh): sweep SNR for every scheme.
# The trained SComCP net (S3) is evaluated under each channel overlay; the
# baseline [35] is a SEPARATE model you train without variant=scomcp.
SNRS=0,2,4,6,8,10,12,14,16,18,20
R=peiyi_work/02_scomcp_reproduction/results

for CH in awgn rayleigh; do
  python peiyi_work/02_scomcp_reproduction/eval_sweep_scomcp.py --model_dir ${S3} \
      --scheme SComCP   --channel ${CH}        --snr_list ${SNRS} --out ${R}/scomcp_${CH}.csv
  python peiyi_work/02_scomcp_reproduction/eval_sweep_scomcp.py --model_dir ${S3} \
      --scheme UpperBound --channel perfect_comm --snr_list ${SNRS} --out ${R}/upper_${CH}.csv
  python peiyi_work/02_scomcp_reproduction/eval_sweep_scomcp.py --model_dir ${S3} \
      --scheme LDPC-16QAM  --channel ldpc16qam  --snr_list ${SNRS} --out ${R}/ldpc16_${CH}.csv
  python peiyi_work/02_scomcp_reproduction/eval_sweep_scomcp.py --model_dir ${S3} \
      --scheme LDPC-256QAM --channel ldpc256qam --snr_list ${SNRS} --out ${R}/ldpc256_${CH}.csv
done

# NOTE: to add the "Baseline [35]" curve, train a model WITHOUT variant=scomcp
# (your existing point_pillar_importance_map_jscc_rayleigh.yaml) and sweep it the
# same way with --scheme Baseline.

python peiyi_work/02_scomcp_reproduction/plot_figures.py
echo "Done. Figures in ${R}/"
