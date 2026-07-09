#!/usr/bin/env bash
# CORRECTED AWGN separate-coding baseline, faithful to Sheng et al. WCSP 2023 Fig 2.
# Uses the where2comm digital-link path (run_separate_coding_sweep.py ->
# _apply_link_erasure): 8-bit-quant tokens over 1/2 LDPC + 16/256QAM, BLER(snr)
# erasure. High SNR (BLER->0) => reaches the upper bound; low SNR => ego-only.
# This REPLACES the broken v2 baseline (run_jscc_eval --channel ldpcXqam, which
# plateaued at ego-only). Eval only, no retraining.
set -u
cd /home/josh/cooperative_semantic_perception/OpenCOOD
RUN="conda run --no-capture-output -n opencood python -u"
W2C=opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22
J=experiment_logs/importance_map_jscc/jscc_eval

echo "=== AWGN LDPC+16QAM (waterfall ~9 dB) ==="
$RUN analysis_tools/run_separate_coding_sweep.py --w2c_dir $W2C --qam 16 \
  --snrs 0,4,6,8,9,10,11,12,16,20 --max_samples 1000 --num_workers 4 \
  --out_root $J --tag awgn_ldpc16_fix || true

echo "=== AWGN LDPC+256QAM (waterfall ~18 dB) ==="
$RUN analysis_tools/run_separate_coding_sweep.py --w2c_dir $W2C --qam 256 \
  --snrs 0,8,12,14,16,18,20,22 --max_samples 1000 --num_workers 4 \
  --out_root $J --tag awgn_ldpc256_fix || true

echo "=== re-plot AWGN (corrected baseline + existing JSCC + measured upper bound) ==="
$RUN analysis_tools/plot_paper_figures.py --channel awgn \
  --jscc $J/awgn_jscc_summary.csv \
  --ldpc16 $J/awgn_ldpc16_fix_summary.csv \
  --ldpc256 $J/awgn_ldpc256_fix_summary.csv || true

echo "==================== CORRECTED AWGN BASELINE ===================="
echo "[16QAM]";  cut -d, -f1-4 $J/awgn_ldpc16_fix_summary.csv
echo "[256QAM]"; cut -d, -f1-4 $J/awgn_ldpc256_fix_summary.csv
echo "[DONE]"