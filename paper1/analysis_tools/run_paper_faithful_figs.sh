#!/usr/bin/env bash
# Paper-faithful redo: single shared perception net.
#   - extend AWGN JSCC sweep to the full SNR axis
#   - run the separate-coding (LDPC+16/256QAM) baseline ON EACH CHANNEL'S JSCC net
#     (so JSCC and baseline share one ceiling; baseline cliffs at low SNR and
#      converges to the JSCC ceiling at high SNR, never exceeding the upper bound)
#   - redraw Fig.2/3/4 (JSCC / LDPC16 / LDPC256 / upper bound 0.89/0.79)
cd /home/josh/cooperative_semantic_perception/OpenCOOD
RUN="conda run --no-capture-output -n opencood python -u"
EXP=experiment_logs/importance_map_jscc
J=$EXP/jscc_eval
SEP=$EXP/separate_coding_eval
ACFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml
RCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh.yaml
OCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm.yaml
AWGN_S2=$EXP/stage2_awgn_cmplx/stage2_whole_map_6000steps.pth
RAY_S2=$EXP/stage2_rayleigh_cmplx/stage2_whole_map_3000steps.pth
OFDM_S2=$EXP/stage2_ofdm_cmplx/stage2_whole_map_3000steps.pth

# 1) extend AWGN JSCC sweep to full axis (rayleigh/ofdm already 0..20)
$RUN analysis_tools/run_jscc_eval.py --config $ACFG --ckpt $AWGN_S2 \
  --channel awgn --snrs 0,4,8,12,16,20 --max_samples 1000 --num_workers 4 --tag awgn_jscc || true

# 2) JSCC-hosted separate-coding baselines, per channel net
sep () {  # CH CFG S2
  local CH=$1 CFG=$2 S2=$3
  $RUN analysis_tools/run_jscc_eval.py --config $CFG --ckpt $S2 \
    --channel ldpc16qam  --snrs 0,8,10,12,16     --max_samples 1000 --num_workers 4 --tag ${CH}_ldpc16  || true
  $RUN analysis_tools/run_jscc_eval.py --config $CFG --ckpt $S2 \
    --channel ldpc256qam --snrs 0,12,16,18,20,22 --max_samples 1000 --num_workers 4 --tag ${CH}_ldpc256 || true
}
sep awgn     $ACFG $AWGN_S2
sep rayleigh $RCFG $RAY_S2
sep ofdm     $OCFG $OFDM_S2

# 3) redraw the three figures
$RUN analysis_tools/plot_paper_figures.py --channel awgn \
  --jscc $J/awgn_jscc_summary.csv --ldpc16 $J/awgn_ldpc16_summary.csv \
  --ldpc256 $J/awgn_ldpc256_summary.csv --upper_ap05 0.89 --upper_ap07 0.79 || true
$RUN analysis_tools/plot_paper_figures.py --channel rayleigh \
  --jscc $J/rayleigh_jscc_summary.csv --ldpc16 $J/rayleigh_ldpc16_summary.csv \
  --ldpc256 $J/rayleigh_ldpc256_summary.csv --upper_ap05 0.89 --upper_ap07 0.79 || true
$RUN analysis_tools/plot_paper_figures.py --channel ofdm \
  --jscc $J/ofdm_jscc_summary.csv --ldpc16 $J/ofdm_ldpc16_summary.csv \
  --ldpc256 $J/ofdm_ldpc256_summary.csv --upper_ap05 0.89 --upper_ap07 0.79 || true

echo "==================== FAITHFUL RESULTS ===================="
for c in awgn rayleigh ofdm; do
  echo "[$c JSCC]"; cat $J/${c}_jscc_summary.csv | cut -d, -f1-4
  echo "[$c LDPC16]"; cat $J/${c}_ldpc16_summary.csv | cut -d, -f1-4
  echo "[$c LDPC256]"; cat $J/${c}_ldpc256_summary.csv | cut -d, -f1-4
done
ls -la $EXP/paper_range_figures/fig_*jscc_vs_separate.png
echo "[DONE] PAPER-FAITHFUL FIGURES COMPLETE."
