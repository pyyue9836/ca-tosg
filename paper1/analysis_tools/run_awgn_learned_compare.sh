#!/usr/bin/env bash
# Controlled experiment: learned importance map vs psm, AWGN only.
# Hypothesis: a learned end-to-end importance map P(F) packs more info into the
# top ~0.125% tokens, lifting the equal-bandwidth LDPC baselines toward the paper.
# ALL outputs are SEPARATELY NAMED — nothing here overwrites the psm v3 results.
#   ckpts:   stage{1,2}_awgn_learned_v3/
#   evals:   jscc_eval/awgn_L_{upper,jscc,ldpc16,ldpc256}_summary.csv
#   figure:  paper_range_figures/learned_compare/fig_awgn_jscc_vs_separate.png
set -u
cd /home/josh/cooperative_semantic_perception/OpenCOOD
RUN="conda run --no-capture-output -n opencood python -u"
EXP=experiment_logs/importance_map_jscc
J=$EXP/jscc_eval
WARM=opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22/net_epoch50.pth
CFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn_learned.yaml
S1=1500; S2=4000; MS=1000; NW=4
CR_J=0.005; CR_16=0.00125; CR_256=0.0025
S1DIR=$EXP/stage1_awgn_learned_v3; S2DIR=$EXP/stage2_awgn_learned_v3
CK=$S2DIR/stage2_whole_map_${S2}steps.pth
OUTDIR=$EXP/paper_range_figures/learned_compare
mkdir -p "$OUTDIR"

EV () { $RUN analysis_tools/run_jscc_eval.py --config "$CFG" --ckpt "$CK" --channel "$1" \
  --snrs "$2" --cr "$3" --max_samples "$MS" --num_workers "$NW" --tag "$4" || true; }

if [ -f "$CK" ]; then
  echo "=== [learned] reuse existing ckpt: $CK ==="
else
  echo "=== [learned] stage1 ==="
  $RUN analysis_tools/stage1_pretrain_jscc_reconstruction_sttopk.py \
    --yaml_path "$CFG" --warm_ckpt "$WARM" --out_dir "$S1DIR" --max_steps "$S1" || exit 1
  echo "=== [learned] stage2 ==="
  $RUN analysis_tools/stage2_whole_network_map_jscc.py \
    --yaml_path "$CFG" --stage1_ckpt "$S1DIR/stage1_rec_sttopk_${S1}steps.pth" \
    --out_dir "$S2DIR" --max_steps "$S2" --lambda_rec 0.5 || exit 1
fi

echo "=== [learned] eval ==="
EV identity     60                    "$CR_J"   awgn_L_upper
EV awgn         0,2,4,6,8,12,16,20    "$CR_J"   awgn_L_jscc
EV ldpc16qam    0,6,8,9,10,12,16      "$CR_16"  awgn_L_ldpc16
EV ldpc256qam   0,12,15,18,20         "$CR_256" awgn_L_ldpc256

echo "=== [learned] plot (separate dir) ==="
$RUN analysis_tools/plot_paper_figures.py --channel awgn \
  --jscc "$J/awgn_L_jscc_summary.csv" --upper_csv "$J/awgn_L_upper_summary.csv" \
  --ldpc16 "$J/awgn_L_ldpc16_summary.csv" --ldpc256 "$J/awgn_L_ldpc256_summary.csv" \
  --out "$OUTDIR" || true

echo "==================== LEARNED vs PSM (AWGN) ===================="
echo "--- learned: upper / ldpc16 / ldpc256 ---"
cut -d, -f1-4 "$J/awgn_L_upper_summary.csv"
cut -d, -f1-4 "$J/awgn_L_ldpc16_summary.csv"
cut -d, -f1-4 "$J/awgn_L_ldpc256_summary.csv"
echo "--- psm (v3 reference): upper / ldpc16 / ldpc256 ---"
cut -d, -f1-4 "$J/awgn_upper_summary.csv"
cut -d, -f1-4 "$J/awgn_ldpc16_summary.csv"
cut -d, -f1-4 "$J/awgn_ldpc256_summary.csv"
echo "[DONE] learned-vs-psm AWGN comparison. figure: $OUTDIR/fig_awgn_jscc_vs_separate.png"
