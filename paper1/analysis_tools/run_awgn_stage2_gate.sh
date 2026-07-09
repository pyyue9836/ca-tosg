#!/usr/bin/env bash
# AWGN: wait for stage1 codec ckpt, run stage2 whole-network training, then
# Gate-C evals (identity ceiling + ego-only baseline). Fully autonomous.
set -e
cd /home/josh/cooperative_semantic_perception/OpenCOOD

CFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml
STAGE1=experiment_logs/importance_map_jscc/stage1_awgn_cmplx/stage1_rec_sttopk_3000steps.pth
STAGE2_DIR=experiment_logs/importance_map_jscc/stage2_awgn_cmplx
STAGE2=$STAGE2_DIR/stage2_whole_map_6000steps.pth
RUN="conda run --no-capture-output -n opencood python -u"

echo "[WAIT] stage1 ckpt: $STAGE1"
until [ -f "$STAGE1" ]; do sleep 15; done
echo "[OK] stage1 ckpt present. Starting stage2."

$RUN analysis_tools/stage2_whole_network_map_jscc.py \
  --yaml_path $CFG --stage1_ckpt $STAGE1 \
  --out_dir $STAGE2_DIR --max_steps 6000 --lambda_rec 0.5

echo "[OK] stage2 done. Gate-C evals."
$RUN analysis_tools/run_jscc_eval.py --config $CFG --ckpt $STAGE2 \
  --channel identity --snrs 60 --max_samples 1000 --tag awgn_identity
$RUN analysis_tools/run_jscc_eval.py --config $CFG --ckpt $STAGE2 \
  --channel remote_zero --snrs 0 --max_samples 1000 --tag ego_only

echo "[GATE-C RESULTS]"
grep -H . experiment_logs/importance_map_jscc/jscc_eval/awgn_identity_summary.csv
grep -H . experiment_logs/importance_map_jscc/jscc_eval/ego_only_summary.csv
echo "[DONE] AWGN stage2 + Gate-C complete."
