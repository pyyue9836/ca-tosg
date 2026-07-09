#!/usr/bin/env bash
# One-off: evaluate the ALREADY-TRAINED v2 awgn stage2 checkpoint and plot the
# awgn figure, WITHOUT disturbing the running paper_faithful_v2 training.
# - low CPU/IO priority (nice/ionice) so the training dataloaders always win
# - num_workers=2 to avoid starving training's loaders (16 cores total)
# - canonical tags/paths => this IS the real v2 awgn figure (idempotent with the
#   main script's later eval phase, same ckpt => same numbers)
set -u
cd /home/josh/cooperative_semantic_perception/OpenCOOD
# reduce CUDA fragmentation so the eval coexists with training in the same 12GB
# without spiking to OOM (minimize impact; training keeps nice-0 priority)
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
RUN="nice -n19 ionice -c3 conda run --no-capture-output -n opencood python -u"
J=experiment_logs/importance_map_jscc/jscc_eval
ACFG=opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml
A=experiment_logs/importance_map_jscc/stage2_awgn_paperv2/stage2_whole_map_6000steps.pth
NW=2
EV="$RUN analysis_tools/run_jscc_eval.py --config $ACFG --ckpt $A --max_samples 1000 --num_workers $NW"

echo "=== [awgn] identity ceiling ==="
$EV --channel identity   --snrs 60                --cr 0.005   --tag awgn_identity || true
echo "=== [awgn] ego-only ==="
$EV --channel remote_zero --snrs 0                --cr 0.005   --tag ego_only      || true
echo "=== [awgn] JSCC sweep (CR=0.005) ==="
$EV --channel awgn       --snrs 0,2,4,6,8,12,16,20 --cr 0.005   --tag awgn_jscc    || true
echo "=== [awgn] LDPC+16QAM (CR=0.00125) ==="
$EV --channel ldpc16qam  --snrs 0,6,8,9,10,12,16  --cr 0.00125 --tag awgn_ldpc16   || true
echo "=== [awgn] LDPC+256QAM (CR=0.0025) ==="
$EV --channel ldpc256qam --snrs 0,12,15,18,20     --cr 0.0025  --tag awgn_ldpc256  || true

echo "=== [awgn] plot ==="
$RUN analysis_tools/plot_paper_figures.py --channel awgn \
  --jscc $J/awgn_jscc_summary.csv --ldpc16 $J/awgn_ldpc16_summary.csv \
  --ldpc256 $J/awgn_ldpc256_summary.csv --upper_ap05 0.89 --upper_ap07 0.79 || true

echo "==================== v2 AWGN-ONLY RESULTS ===================="
echo "[identity ceiling]"; cut -d, -f1-4 $J/awgn_identity_summary.csv
echo "[ego-only]";         cut -d, -f1-4 $J/ego_only_summary.csv
echo "[awgn JSCC]";        cut -d, -f1-4 $J/awgn_jscc_summary.csv
echo "[awgn LDPC16]";      cut -d, -f1-4 $J/awgn_ldpc16_summary.csv
echo "[awgn LDPC256]";     cut -d, -f1-4 $J/awgn_ldpc256_summary.csv
echo "[DONE] v2 awgn-only complete."
