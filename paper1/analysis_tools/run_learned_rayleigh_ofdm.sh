#!/usr/bin/env bash
# Finish the learned-importance-map set: Rayleigh + OFDM (AWGN learned already done).
# Same faithful pipeline as v3 but importance_source=learned (matches the paper's
# end-to-end importance map, which reproduces the paper's absolute values + LDPC
# gap much better than psm). Outputs to a dedicated learned figure folder.
# Per-channel END-TO-END (train -> eval -> plot). Sequential (CPU-bound loading).
set -u
cd /home/josh/cooperative_semantic_perception/OpenCOOD
RUN="conda run --no-capture-output -n opencood python -u"
EXP=experiment_logs/importance_map_jscc
J=$EXP/jscc_eval
WARM=opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22/net_epoch50.pth
S1=1500; S2=4000; MS=1000; NW=4
CR_J=0.005; CR_16=0.00125; CR_256=0.0025
OUTDIR=$EXP/paper_range_figures/learned_compare
mkdir -p "$OUTDIR"

EV () { $RUN analysis_tools/run_jscc_eval.py --config "$1" --ckpt "$2" --channel "$3" \
  --snrs "$4" --cr "$5" --max_samples "$MS" --num_workers "$NW" --tag "$6" || true; }

do_channel () {  # CH CFG JSNRS L16SNRS L256SNRS
  local CH=$1 CFG=$2 JS=$3 L16=$4 L256=$5
  local S1DIR=$EXP/stage1_${CH}_learned_v3  S2DIR=$EXP/stage2_${CH}_learned_v3
  local CK=$S2DIR/stage2_whole_map_${S2}steps.pth
  if [ -f "$CK" ]; then
    echo "=== [$CH learned] reuse ckpt: $CK ==="
  else
    echo "=== [$CH learned] stage1 ==="
    $RUN analysis_tools/stage1_pretrain_jscc_reconstruction_sttopk.py \
      --yaml_path "$CFG" --warm_ckpt "$WARM" --out_dir "$S1DIR" --max_steps "$S1" \
      || { echo "[FATAL] $CH stage1"; return 1; }
    echo "=== [$CH learned] stage2 ==="
    $RUN analysis_tools/stage2_whole_network_map_jscc.py \
      --yaml_path "$CFG" --stage1_ckpt "$S1DIR/stage1_rec_sttopk_${S1}steps.pth" \
      --out_dir "$S2DIR" --max_steps "$S2" --lambda_rec 0.5 \
      || { echo "[FATAL] $CH stage2"; return 1; }
  fi
  echo "=== [$CH learned] eval ==="
  EV "$CFG" "$CK" identity     60     "$CR_J"   ${CH}_L_upper
  EV "$CFG" "$CK" "$CH"        "$JS"  "$CR_J"   ${CH}_L_jscc
  EV "$CFG" "$CK" ldpc16qam    "$L16" "$CR_16"  ${CH}_L_ldpc16
  EV "$CFG" "$CK" ldpc256qam   "$L256" "$CR_256" ${CH}_L_ldpc256
  echo "=== [$CH learned] plot -> $OUTDIR ==="
  $RUN analysis_tools/plot_paper_figures.py --channel "$CH" \
    --jscc "$J/${CH}_L_jscc_summary.csv" --upper_csv "$J/${CH}_L_upper_summary.csv" \
    --ldpc16 "$J/${CH}_L_ldpc16_summary.csv" --ldpc256 "$J/${CH}_L_ldpc256_summary.csv" \
    --out "$OUTDIR" || true
  echo "=== [$CH learned] DONE ==="
  echo "[upper]"; cut -d, -f1-4 "$J/${CH}_L_upper_summary.csv"
  echo "[JSCC]";  cut -d, -f1-4 "$J/${CH}_L_jscc_summary.csv"
  echo "[LDPC16]"; cut -d, -f1-4 "$J/${CH}_L_ldpc16_summary.csv"
  echo "[LDPC256]"; cut -d, -f1-4 "$J/${CH}_L_ldpc256_summary.csv"
}

RCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh_learned.yaml
OCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm_learned.yaml

do_channel rayleigh "$RCFG" 0,6,12,15,18,22,26,30 0,12,15,18,22,30 0,18,22,25,30 || exit 1
do_channel ofdm     "$OCFG" 0,2,4,6,8,12,16,20    0,6,8,10,12,16   0,12,15,18,20 || exit 1

echo "[ALL DONE] learned Rayleigh+OFDM complete. 3 learned figures in: $OUTDIR"
ls -la $OUTDIR/fig_*jscc_vs_separate.png
