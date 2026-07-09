#!/usr/bin/env bash
# Unattended end-to-end finisher for the importance-map JSCC reproduction.
# Runs everything SEQUENTIALLY (OPV2V data loading is CPU-bound; no concurrency).
#
# Precondition: the AWGN stage1->stage2->GateC pipeline (run_awgn_stage2_gate.sh)
# is already running. This script waits for that to fully finish (ego_only CSV),
# then: AWGN JSCC sweep -> Rayleigh train+sweep -> OFDM train+sweep ->
# LDPC16/256 baseline sweeps -> upper bound -> all figures -> results summary.
cd /home/josh/cooperative_semantic_perception/OpenCOOD
RUN="conda run --no-capture-output -n opencood python -u"
EXP=experiment_logs/importance_map_jscc
JEVAL=$EXP/jscc_eval
W2C=opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22
ACFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml
RCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_rayleigh.yaml
OCFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_ofdm.yaml
AWGN_S2=$EXP/stage2_awgn_cmplx/stage2_whole_map_6000steps.pth

echo "[WAIT] AWGN GateC done (ego_only_summary.csv)"
until [ -f "$JEVAL/ego_only_summary.csv" ]; do sleep 20; done
echo "[OK] AWGN pipeline finished. Gate-C:"
cat $JEVAL/awgn_identity_summary.csv; cat $JEVAL/ego_only_summary.csv

# ---- AWGN JSCC sweep ----
$RUN analysis_tools/run_jscc_eval.py --config $ACFG --ckpt $AWGN_S2 \
  --channel awgn --snrs 0,3,6,9,12 --max_samples 1000 --num_workers 4 --tag awgn_jscc || true

# ---- Per-channel train (stage1+stage2) + sweep ----
train_and_sweep () {
  local CH=$1 CFG=$2 SNRS=$3
  local S1DIR=$EXP/stage1_${CH}_cmplx
  local S1=$S1DIR/stage1_rec_sttopk_1200steps.pth
  local S2DIR=$EXP/stage2_${CH}_cmplx
  local S2=$S2DIR/stage2_whole_map_3000steps.pth
  echo "=== [$CH] stage1 ==="
  $RUN analysis_tools/stage1_pretrain_jscc_reconstruction_sttopk.py \
    --yaml_path $CFG --warm_ckpt $W2C/net_epoch50.pth \
    --out_dir $S1DIR --max_steps 1200
  echo "=== [$CH] stage2 ==="
  $RUN analysis_tools/stage2_whole_network_map_jscc.py \
    --yaml_path $CFG --stage1_ckpt $S1 --out_dir $S2DIR \
    --max_steps 3000 --lambda_rec 0.5
  echo "=== [$CH] sweep ==="
  $RUN analysis_tools/run_jscc_eval.py --config $CFG --ckpt $S2 \
    --channel $CH --snrs $SNRS --max_samples 1000 --num_workers 4 --tag ${CH}_jscc || true
}
train_and_sweep rayleigh $RCFG 0,5,10,15,20
train_and_sweep ofdm     $OCFG 0,5,10,15,20

# ---- Separate-coding baselines (where2comm host) + upper bound ----
$RUN analysis_tools/run_separate_coding_sweep.py --w2c_dir $W2C --qam 16 \
  --snrs 0,4,6,8,10,12,16 --max_samples 1000 --num_workers 4 --tag ldpc16qam || true
$RUN analysis_tools/run_separate_coding_sweep.py --w2c_dir $W2C --qam 256 \
  --snrs 0,12,16,18,20,22,26 --max_samples 1000 --num_workers 4 --tag ldpc256qam || true
$RUN analysis_tools/run_separate_coding_sweep.py --w2c_dir $W2C --qam none \
  --snrs 0 --max_samples 1000 --num_workers 4 --tag upper_bound || true

# ---- Figures ----
SEP=$EXP/separate_coding_eval
$RUN analysis_tools/make_fig1_framework.py || true
for CH in awgn rayleigh ofdm; do
  $RUN analysis_tools/plot_paper_figures.py --channel $CH \
    --jscc $JEVAL/${CH}_jscc_summary.csv \
    --ldpc16 $SEP/ldpc16qam_summary.csv --ldpc256 $SEP/ldpc256qam_summary.csv \
    --upper_ap05 0.89 --upper_ap07 0.79 || true
done

echo "==================== FINAL RESULTS ===================="
echo "[Gate-C identity ceiling]"; cat $JEVAL/awgn_identity_summary.csv
echo "[ego-only]"; cat $JEVAL/ego_only_summary.csv
for t in awgn rayleigh ofdm; do echo "[$t JSCC]"; cat $JEVAL/${t}_jscc_summary.csv; done
echo "[LDPC16]"; cat $SEP/ldpc16qam_summary.csv
echo "[LDPC256]"; cat $SEP/ldpc256qam_summary.csv
echo "[upper bound]"; cat $SEP/upper_bound_summary.csv
echo "[figures]"; ls -la $EXP/paper_range_figures/*.png
echo "[DONE] FULL REPRODUCTION COMPLETE."
