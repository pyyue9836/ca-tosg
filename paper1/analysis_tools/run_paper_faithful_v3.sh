#!/usr/bin/env bash
# Clean, strict reproduction of Sheng et al., WCSP 2023 (importance-map JSCC).
# Per-channel END-TO-END (train -> eval -> plot) so the AWGN figure lands first.
#
# Faithful settings:
#   - importance_source=psm (Where2comm spatial-confidence map, the paper's [8] basis)
#   - CR=0.005 (non-zero ratio of importance map), c_complex=64, mask_mode=topk
#   - Baselines: 8-bit quant + 1/2 LDPC(N=1000) + 16/256QAM, equal channel uses via
#     CR_16=0.00125 (1/4), CR_256=0.0025 (1/2)
#   - UPPER BOUND = perfect communication: CR-masked M delivered losslessly
#     (channel=perfect_comm, R=M, no codec, no channel). One line per figure. The
#     paper's definition. (No where2comm-full line.)
#   - Two-stage training (Algorithm 1). SNR: AWGN 0-20, Rayleigh 0-30, OFDM 0-20.
# Sequential only (OPV2V loading is CPU-bound).
set -u
cd /home/josh/cooperative_semantic_perception/OpenCOOD
RUN="conda run --no-capture-output -n opencood python -u"
EXP=experiment_logs/importance_map_jscc
J=$EXP/jscc_eval
WARM=opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22/net_epoch50.pth
S1=${S1:-1500}; S2=${S2:-4000}; MS=${MS:-1000}; NW=${NW:-4}
CR_J=0.005; CR_16=0.00125; CR_256=0.0025
mkdir -p "$J"

EV () {  # CFG CKPT CHANNEL SNRS CR TAG
  $RUN analysis_tools/run_jscc_eval.py --config "$1" --ckpt "$2" --channel "$3" \
    --snrs "$4" --cr "$5" --max_samples "$MS" --num_workers "$NW" --tag "$6" || true
}

do_channel () {  # CH CFG JSNRS L16SNRS L256SNRS  [ego=1]
  local CH=$1 CFG=$2 JS=$3 L16=$4 L256=$5 EGO=${6:-0}
  local S1DIR=$EXP/stage1_${CH}_v3  S2DIR=$EXP/stage2_${CH}_v3
  local CK=$S2DIR/stage2_whole_map_${S2}steps.pth
  if [ -f "$CK" ]; then
    echo "=== [$CH] reuse existing stage2 ckpt (skip training): $CK ==="
  else
    echo "=== [$CH] stage1 ==="
    $RUN analysis_tools/stage1_pretrain_jscc_reconstruction_sttopk.py \
      --yaml_path "$CFG" --warm_ckpt "$WARM" --out_dir "$S1DIR" --max_steps "$S1" \
      || { echo "[FATAL] $CH stage1"; return 1; }
    echo "=== [$CH] stage2 ==="
    $RUN analysis_tools/stage2_whole_network_map_jscc.py \
      --yaml_path "$CFG" --stage1_ckpt "$S1DIR/stage1_rec_sttopk_${S1}steps.pth" \
      --out_dir "$S2DIR" --max_steps "$S2" --lambda_rec 0.5 \
      || { echo "[FATAL] $CH stage2"; return 1; }
  fi
  echo "=== [$CH] eval: upper bound (identity=perfect channel, codec kept) / JSCC / LDPC16 / LDPC256 ==="
  EV "$CFG" "$CK" identity     60          "$CR_J"   ${CH}_upper
  EV "$CFG" "$CK" "$CH"        "$JS"        "$CR_J"   ${CH}_jscc
  EV "$CFG" "$CK" ldpc16qam    "$L16"       "$CR_16"  ${CH}_ldpc16
  EV "$CFG" "$CK" ldpc256qam   "$L256"      "$CR_256" ${CH}_ldpc256
  [ "$EGO" = 1 ] && EV "$CFG" "$CK" remote_zero 0 "$CR_J" ego_only
  echo "=== [$CH] plot ==="
  $RUN analysis_tools/plot_paper_figures.py --channel "$CH" \
    --jscc "$J/${CH}_jscc_summary.csv" --upper_csv "$J/${CH}_upper_summary.csv" \
    --ldpc16 "$J/${CH}_ldpc16_summary.csv" --ldpc256 "$J/${CH}_ldpc256_summary.csv" || true
  echo "=== [$CH] DONE. results: ==="
  echo "[upper]";   cut -d, -f1-4 "$J/${CH}_upper_summary.csv"
  echo "[JSCC]";    cut -d, -f1-4 "$J/${CH}_jscc_summary.csv"
  echo "[LDPC16]";  cut -d, -f1-4 "$J/${CH}_ldpc16_summary.csv"
  echo "[LDPC256]"; cut -d, -f1-4 "$J/${CH}_ldpc256_summary.csv"
}

ACFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml
RCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh.yaml
OCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm.yaml

do_channel awgn     "$ACFG" 0,2,4,6,8,12,16,20    0,6,8,9,10,12,16   0,12,15,18,20   1 || exit 1
do_channel rayleigh "$RCFG" 0,6,12,15,18,22,26,30 0,12,15,18,22,30   0,18,22,25,30   0 || exit 1
do_channel ofdm     "$OCFG" 0,2,4,6,8,12,16,20    0,6,8,10,12,16     0,12,15,18,20   0 || exit 1

echo "[ALL DONE] PAPER-FAITHFUL v3 COMPLETE."
ls -la $EXP/paper_range_figures/fig_*jscc_vs_separate.png
