#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate RESTRUCTURE_MAP.csv: one row per tracked file (row_type=FILE) plus one row per
path literal that a move invalidates (row_type=LITERAL).

Authority for every new_path is RESTRUCTURE_PLAN.md (the supervisor's tree). Anything this
script places OUTSIDE that tree carries note='BEYOND-PLAN: <reason>' so the deviation is
visible rather than silent.

Hard invariant: every tracked file must match exactly one rule. An unmapped file is a build
error, not a silent drop.
"""
import csv
import os
import re
import subprocess
import sys

REPO = '/home/josh/cooperative_semantic_perception/ca-tosg'
OUT = os.path.dirname(os.path.abspath(__file__))
P1 = 'paper1/'

# ---------------------------------------------------------------- dispositions
MOVE, SPLIT, DELETE, KEEP5, UNTOUCHED, REWRITE = ('MOVE', 'SPLIT', 'DELETE', 'KEEP-UNTIL-P5',
                                                  'UNTOUCHED', 'REWRITE-IN-PLACE')

# (regex on the tracked path, disposition, new_path template, commit, note)
# First match wins. {b} = basename, {r} = path relative to paper1/.
RULES = [
 # ---------------------------------------------------------------- root / meta
 (r'^\.gitignore$', REWRITE, '.gitignore', 2, 'absorb paper1/.gitignore; data/ + results paths re-rooted'),
 (r'^README\.md$', REWRITE, 'README.md', 4, 'rewritten to the supervisor README skeleton (10 sections)'),
 (r'^paper1/\.gitignore$', DELETE, '', 2, 'merged into the root .gitignore'),
 (r'^paper2/', UNTOUCHED, '{f}', 0, 'outside paper1/ -- untouched this round'),
 (r'^paper3/', UNTOUCHED, '{f}', 0, 'outside paper1/ -- untouched this round'),

 # ---------------------------------------------------------------- docs
 (r'^paper1/PROTOCOL\.md$', MOVE, 'docs/experiment_protocol.md', 2,
  'THE normative source; configs/ are derived copies, never the reverse'),
 (r'^paper1/REPRODUCE\.md$', MOVE, 'docs/reproducibility.md', 2, ''),
 (r'^paper1/CLAIMS\.md$', MOVE, 'docs/claims.md', 2,
  'BEYOND-PLAN: 7th docs file; machine-checked by tests/test_result_consistency.py, must exist'),
 (r'^paper1/README\.md$', DELETE, '', 4,
  'content redistributed: root README + docs/model_zoo.md + results/README.md'),
 (r'^paper1/opencood_modifications/README\.md$', MOVE, 'docs/opencood_modifications.md', 2,
  'BEYOND-PLAN: 8th docs file; linked from docs/installation.md (the #self+ edit list)'),
 (r'^paper1/results/DATA_MANIFEST\.md$', MOVE, 'docs/data_manifest.md', 2,
  'GPU-cache delete-protection list; a delete list must not be able to delete its own guard'),
 (r'^paper1/results/INVARIANCE_NOTE\.md$', MOVE, 'docs/invariance_note.md', 2, ''),
 (r'^paper1/results/PARAGRAPH_DRAFTS\.md$', MOVE, 'paper/paragraph_drafts.md', 2,
  'input to tests/test_paragraph_insert.py; lives beside main.tex'),
 (r'^paper1/results/STALE_FINGERPRINTS\.md$', MOVE, 'tests/stale_fingerprints.md', 2,
  'gate fixture (block-exit grep), not a result'),
 (r'^paper1/analysis_tools/MAP_REPRODUCTION_CHANGELOG\.md$', MOVE,
  'baselines/importance_map_jscc/CHANGELOG.md', 2, ''),

 # ---------------------------------------------------------------- env
 (r'^paper1/env_setup/requirements_py310_safe\.txt$', MOVE, 'requirements.txt', 2, ''),
 (r'^paper1/env_setup/requirements_no_torch_spconv\.txt$', MOVE,
  'requirements-no-torch-spconv.txt', 2, 'analysis-only install (no torch/spconv)'),

 # ---------------------------------------------------------------- paper + figs
 (r'^paper1/paper/main\.tex$', MOVE, 'paper/main.tex', 2, ''),
 (r'^paper1/paper/refs\.bib$', MOVE, 'paper/refs.bib', 2, ''),
 (r'^paper1/paper/README\.md$', MOVE, 'paper/README.md', 2, ''),
 (r'^paper1/paper/DRAW_OVERVIEW_FIGURE\.md$', MOVE, 'figs/DRAW_OVERVIEW_FIGURE.md', 2,
  'the SVG source lives in figs/, so its drawing instructions do too'),
 (r'^paper1/paper/figures/ca_tosg_method_overview\.svg$', MOVE, 'figs/ca_tosg_overview.svg', 2,
  'PLAN: figs/ca_tosg_overview.svg -- THE SOURCE; paper/figures/*.pdf is its export'),
 (r'^paper1/paper/figures/ca_tosg_method_overview\.pdf$', MOVE,
  'paper/figures/ca_tosg_method_overview.pdf', 2, 'export of figs/ca_tosg_overview.svg (marked in figs/README.md)'),
 (r'^paper1/paper/figures/ca_tosg_method_overview_ORIG\.pdf$', DELETE, '', 2,
  'superseded pre-redraw original; recoverable from tag pre-bevformer-style-restructure'),
 (r'^paper1/paper/figures/fig_ap70_(awgn|rayleigh)\.svg$', DELETE, '', 2,
  'AP@0.7 panels are not \\includegraphics-ed by main.tex (checked: 13 includes)'),
 (r'^paper1/paper/figures/fig_pareto_(culver|validate)\.pdf$', DELETE, '', 2,
  'not included by main.tex (only fig_pareto_test.pdf is)'),
 (r'^paper1/paper/figures/(fig_pareto_test|fig_payload_awgn|fig_channel_bler_frame)\.png$',
  MOVE, 'figs/results/{b}', 2, 'PLAN figs/results/: the README display assets'),
 (r'^paper1/paper/figures/fig_ap50_(awgn|rayleigh)\.svg$', MOVE, 'figs/results/{b}', 2,
  'SVG source of the AP@0.5 panels'),
 (r'^paper1/paper/figures/', MOVE, 'paper/figures/{b}', 2, 'included by main.tex'),

 # ---------------------------------------------------------------- projects/: models
 (r'^paper1/code/p2_dataprep/train_p2_loso\.py$', SPLIT,
  'projects/ca_tosg/models/selector.py + models/oracle.py + models/feature_encoder.py + tools/train_selector.py',
  2, 'PLAN split. Pure relocation: RF ctor/freeze -> selector; ACTIONS/PAYLOAD/lam_labels -> oracle; '
     'EXCLUDE/cue join -> feature_encoder; main() -> tools/train_selector.py'),

 # ---------------------------------------------------------------- projects/: datasets
 (r'^paper1/code/make_dataset\.py$', MOVE, 'projects/ca_tosg/datasets/opv2v.py', 2,
  'PLAN datasets/opv2v.py: 3-way oracle labels on the canonical v3 per-frame datasets'),
 (r'^paper1/code/p2_dataprep/expand_grid_clean\.py$', MOVE,
  'projects/ca_tosg/datasets/grid_builder.py', 2, 'PLAN datasets/grid_builder.py'),
 (r'^paper1/code/p2_dataprep/_scene_map\.py$', SPLIT,
  'projects/ca_tosg/datasets/scene_split.py', 2,
  'PLAN datasets/scene_split.py = _scene_map.py + export_scene_manifest.py concatenated (no name clash)'),
 (r'^paper1/code/p2_dataprep/export_scene_manifest\.py$', SPLIT,
  'projects/ca_tosg/datasets/scene_split.py', 2, 'merged into scene_split.py; driven by tools/prepare_data.py'),
 (r'^paper1/code/test_split_pipeline/', MOVE, 'projects/ca_tosg/datasets/test_split/{b}', 2,
  'BEYOND-PLAN subdir: produces dataset_test.csv, which IS the P2 cue source -- an input producer, not dead'),

 # ---------------------------------------------------------------- projects/: communication
 (r'^paper1/analysis_tools/build_bler_sionna\.py$', SPLIT,
  'projects/ca_tosg/communication/ldpc_qam.py + tools/build_bler_table.py', 2, 'PLAN split'),
 (r'^paper1/analysis_tools/build_bler_sionna_ofdm\.py$', SPLIT,
  'projects/ca_tosg/communication/channel.py + tools/build_bler_table.py', 2, 'PLAN split'),
 (r'^paper1/analysis_tools/build_ldpc_qam_bler_table\.py$', DELETE, '', 2,
  'builds the DEPRECATED 40-block table (quantisation floor); superseded by build_bler_sionna.py'),
 (r'^paper1/analysis_tools/ldpc_qam_physical_sanity_n1000_ebn0\.py$', MOVE,
  'tests/test_channel.py', 2, 'PLAN tests/test_channel.py: the physical-layer sanity gate'),
 (r'^paper1/analysis_tools/plot_bler_compare\.py$', MOVE,
  'projects/ca_tosg/evaluation/figures/plot_bler_compare.py', 2, ''),

 # ---------------------------------------------------------------- projects/: evaluation
 (r'^paper1/code/p2_dataprep/eval_p2_deploy\.py$', SPLIT,
  'projects/ca_tosg/evaluation/deployment.py + tools/evaluate_selector.py', 2, 'PLAN split'),
 (r'^paper1/code/p2_dataprep/eval_p2_ap\.py$', SPLIT,
  'projects/ca_tosg/evaluation/end_to_end_ap.py + tools/evaluate_ap.py', 2, 'PLAN split'),
 (r'^paper1/code/p2_dataprep/eval_p3_sensitivity\.py$', SPLIT,
  'projects/ca_tosg/evaluation/sensitivity.py + tools/run_sensitivity.py', 2, 'PLAN split'),
 (r'^paper1/code/p2_dataprep/eval_p3c_rician_bracket\.py$', MOVE,
  'projects/ca_tosg/evaluation/rician_bracket.py', 2, 'sensitivity item 5c'),
 (r'^paper1/code/p2_dataprep/train_p3_variants\.py$', MOVE,
  'projects/ca_tosg/evaluation/p3_variants.py', 2, 'item-3 misclassification variants'),
 (r'^paper1/code/p2_dataprep/r10c_diagnostic\.py$', MOVE,
  'projects/ca_tosg/evaluation/decision_log.py', 2, 'per-frame decision log + oracle/tau accounting'),
 (r'^paper1/code/p2_dataprep/make_r10_report\.py$', MOVE,
  'projects/ca_tosg/evaluation/report.py', 2, ''),
 (r'^paper1/code/p2_dataprep/anomaly_check\.py$', MOVE,
  'projects/ca_tosg/evaluation/anomaly_check.py', 2, ''),
 (r'^paper1/code/p2_dataprep/check_leakage\.py$', MOVE, 'tests/test_data_leakage.py', 2,
  'PLAN tests/test_data_leakage.py (gate G5)'),
 (r'^paper1/code/recompute_policy_200seed\.py$', MOVE,
  'projects/ca_tosg/evaluation/policy_200seed.py', 2, 'the 200-realisation engine (P1 v3, still cited)'),
 (r'^paper1/code/true_e2e_global\.py$', MOVE,
  'projects/ca_tosg/evaluation/true_e2e_global.py', 2, 'global-sort true-e2e AP scorer'),
 (r'^paper1/code/true_e2e_ap_inference\.py$', MOVE,
  'projects/ca_tosg/evaluation/true_e2e_inference.py', 2, ''),
 (r'^paper1/code/canonical_rescore\.py$', MOVE,
  'projects/ca_tosg/evaluation/canonical_rescore.py', 2, 'canonical-union-GT re-scorer'),
 (r'^paper1/code/recompute_canonical_f1\.py$', MOVE,
  'projects/ca_tosg/evaluation/canonical_f1.py', 2, ''),
 (r'^paper1/code/rf_latency_benchmark\.py$', SPLIT,
  'projects/ca_tosg/evaluation/latency.py + tools/benchmark_latency.py', 2, 'PLAN tools/benchmark_latency.py'),
 (r'^paper1/code/gt_audit\.py$', MOVE, 'projects/ca_tosg/evaluation/gt_audit.py', 2, ''),
 (r'^paper1/code/step4_collab_harm\.py$', MOVE,
  'projects/ca_tosg/evaluation/collab_harm.py', 2, ''),
 (r'^paper1/code/step4_oracle_action_dist\.py$', MOVE,
  'projects/ca_tosg/evaluation/action_dist.py', 2, ''),
 (r'^paper1/code/regen_preds_with_scores\.py$', MOVE,
  'projects/ca_tosg/datasets/regen_preds_with_scores.py', 2,
  'DATA_MANIFEST regen command for gs_rerun/{late,comp}_*.npz -- protected, must not be deleted'),
 (r'^paper1/code/run_ego_only\.py$', MOVE, 'projects/ca_tosg/datasets/run_ego_only.py', 2,
  'DATA_MANIFEST regen command for gs_rerun/ego_*.npz -- protected'),
 (r'^paper1/code/regen_ego_only\.py$', DELETE, '', 2,
  'superseded by run_ego_only.py (the DATA_MANIFEST-registered generator)'),
 (r'^paper1/code/v3_eval\.py$', DELETE, '', 2,
  'stale duplicate of code/extra_experiments/v3_eval.py (older: no OFDM concat); every importer '
  'resolves to the extra_experiments copy via sys.path'),
 (r'^paper1/code/train_rf\.py$', KEEP5,
  'projects/ca_tosg/models/train_rf_v3.py', 2,
  'P1-v3 selector trainer, superseded by the P2 frozen walk but still the generator of the v3 '
  'numbers cited in the P1 tables'),

 # ---------------------------------------------------------------- projects/: utils
 (r'^paper1/code/paper_style\.py$', MOVE, 'projects/ca_tosg/utils/paper_style.py', 2,
  'BEYOND-PLAN utils file: IEEE figure style, imported by every plot_*'),

 # ---------------------------------------------------------------- ablations
 (r'^paper1/code/extra_experiments/v3_eval\.py$', MOVE,
  'projects/ca_tosg/evaluation/v3_eval.py', 2, 'the live 200-realisation evaluator imported by every ablation'),
 (r'^paper1/code/extra_experiments/_common\.py$', MOVE,
  'projects/ca_tosg/evaluation/ablations/_common.py', 2, ''),
 (r'^paper1/code/extra_experiments/README\.md$', MOVE,
  'projects/ca_tosg/evaluation/ablations/README.md', 2, ''),
 (r'^paper1/code/extra_experiments/out/a2_difficulty_reliable\.csv$', DELETE, '', 2,
  'third byte-identical copy of results/a2_difficulty_reliable.csv (scratch output dir)'),
 (r'^paper1/code/extra_experiments/jscc_perframe/', MOVE,
  'baselines/importance_map_jscc/perframe/{b}', 2,
  'per-frame JSCC experiments belong with the ImportanceMapJSCC baseline'),
 (r'^paper1/code/extra_experiments/', MOVE,
  'projects/ca_tosg/evaluation/ablations/{b}', 2,
  'BEYOND-PLAN subdir: a1-a9 + c_channels + robustness generate results/sensitivity/ablation/'),

 # ---------------------------------------------------------------- verifiers -> tests
 (r'^paper1/code/payload_audit\.py$', SPLIT,
  'tests/test_payload.py + projects/ca_tosg/communication/payload.py', 2,
  'PLAN tests/test_payload.py (gate G1); the payload derivation itself becomes communication/payload.py'),
 (r'^paper1/code/extract_claims\.py$', MOVE, 'tests/test_result_consistency.py', 2,
  'PLAN tests/test_result_consistency.py (gate G4: CLAIMS.md vs main.tex)'),
 (r'^paper1/code/verify_paragraph_insert\.py$', MOVE, 'tests/test_paragraph_insert.py', 2,
  'BEYOND-PLAN 6th test file (gate G2); distinct fixture set from test_result_consistency.py'),
 (r'^paper1/code/verify_(c256_dominance|frontier_payload_invariance|gamma_mechanism|harm_stratum_structural)\.py$',
  MOVE, 'projects/ca_tosg/evaluation/verifiers/{b}', 2,
  'one-shot claim verifiers; outputs are cited, so they move rather than die'),

 # ---------------------------------------------------------------- figure generators
 (r'^paper1/code/(plot_ap_snr|plot_bler_frame|plot_feature_importance|plot_oracle_action_dist|'
  r'plot_pareto_payload|plot_stacked_area|snr_decision_plot)\.py$', MOVE,
  'projects/ca_tosg/evaluation/figures/{b}', 2, 'driven by tools/generate_figures.py'),
 (r'^paper1/analysis_tools/plot_paper_figures\.py$', MOVE,
  'projects/ca_tosg/evaluation/figures/plot_paper_figures.py', 2, ''),
 (r'^paper1/analysis_tools/make_fig1_framework\.py$', DELETE, '', 2,
  'generated the retired matplotlib fig1; the overview figure is now the hand-drawn '
  'figs/ca_tosg_overview.svg (REPRODUCE sec 3 marks fig:overview "manual")'),

 # ---------------------------------------------------------------- baselines
 (r'^paper1/code/where2comm_compare\.py$', MOVE, 'baselines/where2comm/compare.py', 2, ''),
 (r'^paper1/code/p2_dataprep/train_p4a_bandit\.py$', MOVE,
  'baselines/contextual_bandit/train.py', 2, 'PLAN baselines/contextual_bandit/'),
 (r'^paper1/code/p2_dataprep/eval_p4a_deploy\.py$', MOVE,
  'baselines/contextual_bandit/evaluate.py', 2, 'PLAN baselines/contextual_bandit/'),
 (r'^paper1/scomcp_reproduction/configs/', MOVE, 'baselines/scomcp/configs/{b}', 2, ''),
 (r'^paper1/scomcp_reproduction/', MOVE, 'baselines/scomcp/{b}', 2, 'PLAN: scomcp moves wholesale'),
 (r'^paper1/analysis_tools/(stage1_pretrain_jscc_reconstruction_sttopk|stage2_whole_network_map_jscc|'
  r'run_jscc_eval|inference_subset|run_separate_coding_sweep)\.py$', MOVE,
  'baselines/importance_map_jscc/{b}', 2, 'WCSP2023 ImportanceMapJSCC reproduction'),
 (r'^paper1/analysis_tools/.*\.sh$', MOVE, 'baselines/importance_map_jscc/scripts/{b}', 2,
  'legacy JSCC run drivers; kept verbatim as the record of how the checkpoints were produced'),

 # ---------------------------------------------------------------- results: manifests / provenance
 (r'^paper1/results/p2_dataprep/FROZEN_MANIFEST\.json$', MOVE,
  'results/manifests/FROZEN_MANIFEST.json', 3, 'COMMIT 3: internal relpaths rewritten'),
 (r'^paper1/results/p4a/P4A_MANIFEST\.json$', MOVE, 'results/manifests/P4A_MANIFEST.json', 3,
  'COMMIT 3: internal relpaths rewritten'),
 (r'^paper1/results/p2_dataprep/candidate_walk_(B\d+)\.csv$', MOVE,
  'results/manifests/candidate_walk_{b}', 3, 'COMMIT 3: sha256-pinned by FROZEN_MANIFEST'),
 (r'^paper1/results/p2_dataprep/validate_loso_folds\.csv$', MOVE,
  'results/manifests/validate_loso_folds.csv', 3, 'COMMIT 3: sha256-pinned by FROZEN_MANIFEST'),
 (r'^paper1/results/p2_dataprep/scene_manifest_validate\.csv$', MOVE,
  'results/manifests/scene_manifest_validate.csv', 3, 'leakage-gate cross-check input'),
 (r'^paper1/results/.*/PROVENANCE.*\.txt$', MOVE, 'results/provenance/{b}', 2, ''),
 (r'^paper1/results/(step4_PROVENANCE|canonical_gt_PROVENANCE|where2comm_ap_PROVENANCE)\.txt$',
  MOVE, 'results/provenance/{b}', 2, ''),
 (r'^paper1/results/policy/STEP5_NOTES\.md$', MOVE, 'results/provenance/STEP5_NOTES.md', 2, ''),
 (r'^paper1/results/p2_deploy/(R10_REPORT\.md|r9_result_claims\.md|anomaly_report\.txt)$', MOVE,
  'results/provenance/{b}', 2, ''),

 # ---------------------------------------------------------------- results: main
 (r'^paper1/results/p2_deploy/headline_action_dist\.csv$', MOVE,
  'results/main/action_distribution.csv', 2, 'PLAN results/main/action_distribution.csv'),
 (r'^paper1/results/p2_deploy/replay_summary\.csv$', MOVE, 'results/main/replay_summary.csv', 2,
  'PLAN results/main/replay_summary.csv'),
 (r'^paper1/results/p2_deploy/true_e2e_ap\.csv$', MOVE, 'results/main/true_e2e_ap.csv', 2,
  'PLAN results/main/true_e2e_ap.csv'),
 (r'^paper1/results/p2_deploy/', MOVE, 'results/main/{b}', 2, 'deployment replay + decision logs'),
 (r'^paper1/results/policy/', MOVE, 'results/main/{b}', 2, '200-realisation policy frontier'),
 (r'^paper1/results/true_e2e_global_(validate|test|culver)\.csv$', MOVE, 'results/main/{b}', 2, ''),
 (r'^paper1/results/(feature_importance|step4_.*|ego_only_acceptance)\.csv$', MOVE,
  'results/main/{b}', 2, ''),
 (r'^paper1/results/step4_rf_train_meta\.json$', MOVE, 'results/main/step4_rf_train_meta.json', 2, ''),

 # ---------------------------------------------------------------- results: sensitivity
 (r'^paper1/results/p3_sensitivity/item1_channel_ratio\.csv$', MOVE,
  'results/sensitivity/channel_ratio.csv', 2, 'PLAN name'),
 (r'^paper1/results/p3_sensitivity/item2_nonuniform_snr\.csv$', MOVE,
  'results/sensitivity/nonuniform_snr.csv', 2, 'PLAN name'),
 (r'^paper1/results/p3_sensitivity/item3_misclass_flip\.csv$', MOVE,
  'results/sensitivity/channel_misclassification.csv', 2, 'PLAN name'),
 (r'^paper1/results/p3_sensitivity/item4_bler_L\.csv$', MOVE,
  'results/sensitivity/object_message_bler.csv', 2, 'PLAN name'),
 (r'^paper1/results/p3_sensitivity/item5_rician\.csv$', MOVE,
  'results/sensitivity/rician_proxy.csv', 2, 'PLAN name'),
 (r'^paper1/results/p3_sensitivity/p3_baseline_sanity\.csv$', MOVE,
  'results/sensitivity/baseline_sanity.csv', 2,
  'MERGE CRITERION 2: its 18 data rows must stay bit-identical across the rename'),
 (r'^paper1/results/p3_sensitivity/', MOVE, 'results/sensitivity/{b}', 2, ''),
 (r'^paper1/results/ablation/', MOVE, 'results/sensitivity/ablation/{b}', 2, ''),
 (r'^paper1/results/a2_difficulty\.csv$', DELETE, '', 2,
  'byte-identical duplicate of results/ablation/a2_difficulty.csv'),
 (r'^paper1/results/a2_difficulty_reliable\.csv$', DELETE, '', 2,
  'byte-identical duplicate of results/ablation/a2_difficulty_reliable.csv'),
 (r'^paper1/results/(robustness_csi_noise|robustness_csi_aging|robustness_request_delay|'
  r'multiseed_hardening|scene_subsets|snr_threshold|l_channel_reliability|gamma_mechanism|'
  r'harm_stratum_structural|c256_dominance_verify|frontier_payload_invariance|'
  r'f1_ap_decoupling_culver|canonical_rescore|canonical_f1_columns|gt_audit|gt_object_stats)\.csv$',
  MOVE, 'results/sensitivity/{b}', 2, ''),
 (r'^paper1/results/f1_ap_decoupling_culver\.md$', MOVE, 'results/sensitivity/{b}', 2, ''),

 # ---------------------------------------------------------------- results: baselines / latency / channel
 (r'^paper1/results/where2comm_ap\.csv$', MOVE, 'results/baselines/where2comm.csv', 2, 'PLAN name'),
 (r'^paper1/results/p4a/p4a_summary\.csv$', MOVE,
  'results/baselines/contextual_bandit.csv', 2, 'PLAN name'),
 (r'^paper1/results/p4a/', MOVE, 'results/baselines/contextual_bandit/{b}', 2, ''),
 (r'^paper1/results/jscc/', MOVE, 'results/baselines/importance_map_jscc/{b}', 2, ''),
 (r'^paper1/results/jscc_selector_(awgn|rayleigh|ofdm)\.csv$', MOVE,
  'results/baselines/importance_map_jscc/{b}', 2, ''),
 (r'^paper1/results/p2_latency/latency_frozen\.csv$', MOVE,
  'results/latency/selector_latency.csv', 2, 'PLAN name'),
 (r'^paper1/results/p2_latency/e2e_timing\.csv$', MOVE,
  'results/latency/system_timing.csv', 2, 'PLAN name'),
 (r'^paper1/results/p2_latency/', MOVE, 'results/latency/{b}', 2, ''),
 (r'^paper1/results/bler_sionna/', MOVE, 'results/channel/{b}', 2,
  'BEYOND-PLAN 7th bucket: the BLER tables are an INPUT to every command, not one command\'s output'),
 (r'^paper1/results/ldpc_qam_bler_table\.csv$', DELETE, '', 2,
  'DEPRECATED 40-block table (1/40 quantisation floor, codeword BLER consumed as frame BLER); '
  'superseded by results/channel/bler_sionna.csv'),
]

NEW_FILES = [
 ('RESTRUCTURE_PLAN.md', 1, 'supervisor plan, verbatim -- the authority for every new_path here'),
 ('RESTRUCTURE_MAP.csv', 1, 'this file'),
 ('RESTRUCTURE_GATE_SWEEP.md', 1, 'delete list + KEEP-UNTIL-P5 list; the P5 table is folded into '
                                  'docs/experiment_protocol.md appendix A in commit 2'),
 ('tools/prepare_data.py', 2, 'PLAN command 1: grid_builder + scene_split drivers'),
 ('tools/build_bler_table.py', 2, 'PLAN command 2'),
 ('tools/train_selector.py', 2, 'PLAN command 3'),
 ('tools/evaluate_selector.py', 2, 'PLAN command 4'),
 ('tools/evaluate_ap.py', 2, 'PLAN command 5'),
 ('tools/generate_figures.py', 2, 'PLAN command 6'),
 ('tools/run_sensitivity.py', 2, 'PLAN tool (not one of the 6 headline commands)'),
 ('tools/run_baselines.py', 2, 'PLAN tool'),
 ('tools/benchmark_latency.py', 2, 'PLAN tool'),
 ('tools/verify_results.py', 2, 'PLAN tool: runs all six tests/ modules'),
 ('projects/ca_tosg/__init__.py', 2, 'package root'),
 ('projects/ca_tosg/utils/manifest.py', 2, 'PLAN utils/manifest.py: THE single relpath resolver + '
                                           'sha256 verifier (commit 3 changes this file only)'),
 ('projects/ca_tosg/utils/provenance.py', 2, 'PLAN utils/provenance.py'),
 ('projects/ca_tosg/utils/seed.py', 2, 'PLAN utils/seed.py'),
 ('projects/ca_tosg/evaluation/metrics.py', 2, 'PLAN evaluation/metrics.py'),
 ('projects/ca_tosg/communication/fallback.py', 2, 'PLAN communication/fallback.py: ego-only fallback rule'),
 ('configs/catosg_b010.yaml', 2, 'PLAN config, DERIVED from the PROTOCOL candidate block + md5-pinned'),
 ('configs/catosg_b020.yaml', 2, 'PLAN config, derived + md5-pinned'),
 ('configs/catosg_b030.yaml', 2, 'PLAN config, derived + md5-pinned'),
 ('configs/phy_ldpc_qam.yaml', 2, 'PLAN config, derived + md5-pinned'),
 ('configs/sensitivity.yaml', 2, 'PLAN config, derived + md5-pinned'),
 ('figs/README.md', 2, 'declares figs/ca_tosg_overview.svg the SOURCE and paper/figures/*.pdf its export'),
 ('tests/test_manifest.py', 3, 'PLAN tests/test_manifest.py: manifest relpath resolution + '
                               'configs == PROTOCOL block assertion'),
 ('docs/installation.md', 4, 'PLAN docs 1/6'),
 ('docs/dataset.md', 4, 'PLAN docs 2/6'),
 ('docs/getting_started.md', 4, 'PLAN docs 3/6'),
 ('docs/model_zoo.md', 4, 'PLAN docs 5/6: B0.10 / B0.20 / B0.30 with sha256, lambda*, tau*'),
 ('results/README.md', 4, 'PLAN: which command generates which file'),
 ('baselines/where2comm/README.md', 4, 'PLAN six elements'),
 ('baselines/scomcp/README.md', 4, 'PLAN six elements (overwrites the moved one)'),
 ('baselines/importance_map_jscc/README.md', 4, 'PLAN six elements'),
 ('baselines/contextual_bandit/README.md', 4, 'PLAN six elements'),
 ('projects/ca_tosg/README.md', 4, 'PLAN projects/ca_tosg/README.md'),
 ('environment.yml', 4, 'PLAN root file: conda spec for the sionna310 env'),
]

NOT_CREATED = [
 ('LICENSE', 'PLAN root file NOT created: choosing a licence is the author\'s legal decision, '
             'not a refactor step'),
 ('figs/selector_pipeline.svg', 'PLAN figs file NOT created: no source asset exists and inventing a '
                                'system diagram would misstate the method; needs Josh\'s draw.io'),
 ('results/baselines/scomcp.csv', 'PLAN results file NOT created: the SComCP reproduction has not '
                                  'produced a result table yet (baselines/scomcp/ is code-only)'),
]


def tracked():
    return subprocess.check_output(['git', '-C', REPO, 'ls-files'], text=True).split()


def apply_rules(f):
    for pat, disp, tmpl, commit, note in RULES:
        m = re.match(pat, f)
        if m:
            new = tmpl.format(b=os.path.basename(f), f=f, r=f[len(P1):] if f.startswith(P1) else f)
            return disp, new, commit, note
    return None


def main():
    files = tracked()
    rows, unmapped = [], []
    for f in sorted(files):
        r = apply_rules(f)
        if r is None:
            unmapped.append(f)
            continue
        disp, new, commit, note = r
        rows.append(dict(row_type='FILE', old_path=f, new_path=new, disposition=disp,
                         commit=commit, detail='', note=note))
    if unmapped:
        print('UNMAPPED (%d) -- refusing to emit a partial map:' % len(unmapped))
        for f in unmapped:
            print('   ', f)
        return 1

    for p, c, n in NEW_FILES:
        rows.append(dict(row_type='FILE', old_path='', new_path=p, disposition='NEW',
                         commit=c, detail='', note=n))
    for p, n in NOT_CREATED:
        rows.append(dict(row_type='FILE', old_path='', new_path=p, disposition='NOT-CREATED',
                         commit=0, detail='', note=n))

    # ---- literal rows: join the scanner output onto the file map
    old2new = {r['old_path']: r for r in rows if r['row_type'] == 'FILE' and r['old_path']}
    lit_path = os.path.join(OUT, 'path_literals.csv')
    n_lit = 0
    if os.path.exists(lit_path):
        REWRITE_KINDS = {'relpath_local', 'relpath_escaping_repo', 'absolute_path',
                         'json_internal_relpath', 'local_import', 'path_anchor'}
        with open(lit_path) as fh:
            for L in csv.DictReader(fh):
                if L['kind'] not in REWRITE_KINDS:
                    continue
                host = old2new.get(L['file'])
                if host is None or host['disposition'] == 'DELETE':
                    continue
                rows.append(dict(row_type='LITERAL', old_path=L['file'], new_path=host['new_path'],
                                 disposition='REWRITE' if L['kind'] != 'path_anchor' else 'RE-ANCHOR',
                                 commit=3 if L['kind'] == 'json_internal_relpath' else host['commit'],
                                 detail='L%s|%s|%s' % (L['line'], L['kind'], L['literal']),
                                 note=L['context'][:120]))
                n_lit += 1

    with open(os.path.join(OUT, 'RESTRUCTURE_MAP.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['row_type', 'old_path', 'new_path', 'disposition',
                                           'commit', 'detail', 'note'])
        w.writeheader()
        w.writerows(rows)

    import collections
    c = collections.Counter(r['disposition'] for r in rows if r['row_type'] == 'FILE')
    print('FILE rows: %d  (tracked=%d)' % (sum(c.values()), len(files)))
    for k, v in sorted(c.items()):
        print('   %-14s %3d' % (k, v))
    print('LITERAL rows: %d' % n_lit)
    return 0


if __name__ == '__main__':
    sys.exit(main())
