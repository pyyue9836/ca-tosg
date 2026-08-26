#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate results/README.md: every committed result file -> the command that produces it.

Attribution is by explicit rule, and a file that matches no rule is listed as UNATTRIBUTED rather
than quietly dropped -- an index that silently omits files is worse than no index.

  python projects/ca_tosg/utils/results_index.py --write
"""
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
OUT = os.path.join(ROOT, 'results/README.md')

# (regex on the results/-relative path, command, note)
RULES = [
    # V2-R1: plan-A products. results/v2/ is the v2 tree; nothing under it feeds the frozen v1
    # manuscript, and the sanity check is its first entry.
    (r'^v2/sanity_single_vehicle_\w+\.(csv|json)$',
     'python projects/ca_tosg/evaluation/v2_single_vehicle_sanity.py',
     'V2-R1 item 2: single-vehicle vs cooperative forward on the unified checkpoint'),
    (r'^v2/sealed/(wp2_held_out_\w+\.json|wp2_f1_ego_\w+\.csv|README\.md)$',
     'python projects/ca_tosg/evaluation/v2_wp2_per_agent.py --held-out-eval',
     'SEALED held-out accuracy -- no tuning or selection step may read it (E-2)'),
    (r'^v2/wp34_e_l_\w+\.(csv|json)$',
     'python projects/ca_tosg/evaluation/v2_wp34_e_l_products.py',
     'work packages 3+4: E products, L late fusion, per-frame B_L from real box counts'),
    (r'^v2/wp2_per_agent_\w+\.(csv|json|npz)$',
     'python projects/ca_tosg/evaluation/v2_wp2_per_agent.py',
     'work package 2: per-agent inference under CATOSG_MAX_COLLAB=1'),
    (r'^v2/int8_clean_delivery_\w+\.csv$',
     'python projects/ca_tosg/evaluation/v2_int8_calibrate.py',
     'V2-R4 step 4: float vs int8 clean delivery on the same frames'),
    (r'^v2/payload_chain\.json$', 'python tools/v2_payload_chain.py',
     'V2-R3 step 5: the whole v2 payload chain with its identity self-check'),
    (r'^manifests/V2_INT8_SCALES\.json$',
     'python projects/ca_tosg/evaluation/v2_int8_calibrate.py',
     'frozen per-branch symmetric int8 transmit scales (validate-calibrated)'),
    (r'^manifests/V2_PROTOCOL_MANIFEST\.json$',
     'python tools/build_v2_protocol_manifest.py',
     'per-section hashes + lock state of docs/unified_branch_protocol_v2.md'),
    (r'^manifests/(FROZEN_MANIFEST\.json|validate_loso_folds\.csv|candidate_walk_B\d+\.csv)$',
     'python tools/train_selector.py', 'freeze record + LOSO evidence chain'),
    (r'^manifests/scene_manifest_\w+\.csv$',
     'python tools/prepare_data.py --scene-manifest', 'independent frame->scene manifest'),
    (r'^manifests/P4B_MANIFEST\.json$',
     '(hand-recorded; the checkpoint is an EXTERNAL INPUT, fetched manually)',
     'P4-B SECOND intermediate-fusion checkpoint -- input only, no inference run'),
    (r'^manifests/P4B_CONVERSION_MANIFEST\.json$',
     'python tools/convert_second_checkpoint.py',
     'P4-B-c spconv 1.x->2.x kernel-layout conversion of the zoo SECOND weights (lossless axis '
     'reorder; established by the verification below, not by the conversion itself)'),
    (r'^manifests/P4B_VERIFICATION_\w+\.json$',
     'python tools/verify_second_zoo_ap.py',
     "P4-B-c expectation E4: reproduces the model zoo's own published AP@0.7 with the converted "
     "weights (no-global-sort, the zoo's own convention)"),
    (r'^manifests/P4B_DUMMY_FORWARD_\w+\.json$',
     'python tools/bev_tensor_probe.py',
     'P4-B-c step 4: transmitted BEV tensor shapes before/after the AutoEncoder bottleneck '
     '(superseded by the P4B_PROBE_* files, which cover both backbones and both conventions)'),
    (r'^p4b/(replay_\w+|replay_summary|action_distribution|perclass_ELF)\.csv$',
     'python projects/ca_tosg/evaluation/second_arm_pipeline.py --stage replay',
     'second-backbone arm, NOT DEPLOYED (descriptive + paired CI only; the arm publishes no '
     'decision file -- see second_arm_pipeline.run_replay)'),
    (r'^p4b/P4B_ANOMALY_REPORT\.md$',
     'python projects/ca_tosg/evaluation/p4b_anomaly_report.py',
     'PROTOCOL section 8 checklist on the second-backbone arm (3 of 7 expectations not met)'),
    (r'^manifests/P4B_(ARM|FROZEN|DATASET|CACHE_LATE|CONVERSION_LATE)_MANIFEST\.json$',
     'python projects/ca_tosg/evaluation/second_arm_pipeline.py',
     'second-backbone arm manifests, NOT DEPLOYED'),
    (r'^p4b/manifests/P4B_\w+\.(json|csv)$',
     'python projects/ca_tosg/evaluation/second_arm_pipeline.py --stage selector',
     'second-backbone arm freeze / LOSO folds / walk, NOT DEPLOYED (arm-private directory)'),
    (r'^manifests/candidate_walk_B\d+\.csv$',
     'python tools/train_selector.py', 'freeze record + LOSO evidence chain'),
    (r'^manifests/P4B_CACHE_MANIFEST\.json$',
     'python projects/ca_tosg/datasets/build_second_caches.py',
     'P4-B-e: SECOND E/F per-frame caches (3 splits); L branch NOT built -- checkpoint absent'),
    (r'^provenance/PROVENANCE_qualitative\.json$',
     'python projects/ca_tosg/evaluation/figures/plot_qualitative_bev.py',
     'fig:qualitative frame recovery + panel numbers'),
    (r'^provenance/PROVENANCE_figures\.json$',
     'python projects/ca_tosg/evaluation/figures/plot_frozen_figs.py',
     'condition-tagged list of every number the frozen figures draw'),
    (r'^manifests/P4B_PROBE_\w+\.json$',
     'python tools/bev_tensor_probe.py',
     'P4-B-d item 2: per-branch pre-compression and transmitted BEV tensor shapes, by forward hook'),
    (r'^channel/payload_conventions\.csv$',
     'python tools/second_payload_and_bler.py',
     'P4-B-d items 1-2: 2 backbones x 2 accounting conventions -> B_F, N_cw, B_max'),
    (r'^channel/payload_anchor_sensitivity\.csv$',
     'python tools/second_payload_and_bler.py',
     'P4-B-d item 2: what re-anchoring the source budget does to the headline channel-use '
     'fraction, using the frozen decision logs\' own action mix'),
    (r'^channel/bler_frame_second\.csv$',
     'python tools/second_payload_and_bler.py',
     'P4-B-d item 3: frame BLER re-derived at N_cw^SECOND from the committed codeword BLER'),
    (r'^channel/bler_onset_second\.csv$',
     'python tools/second_payload_and_bler.py',
     'P4-B-d item 3: feasibility-mask onsets at N_cw 3960 vs N_cw^SECOND'),
    (r'^manifests/P4C_MANIFEST\.json$',
     'python projects/ca_tosg/evaluation/collaborator_scale.py',
     'P4-C arm caches -- "collaborator-scale arm, not deployed"'),
    (r'^sensitivity/collaborator_scale\.csv$',
     'python projects/ca_tosg/evaluation/collaborator_scale.py',
     'P4-C semantics A; caches built by projects/ca_tosg/datasets/p4c_sweep.py'),
    (r'^manifests/FEATURE_ABLATION_MANIFEST\.json$',
     'python projects/ca_tosg/evaluation/feature_ablation.py',
     'FA-1 variant models -- "labeled variant, not deployed", kept apart from FROZEN_MANIFEST'),
    (r'^sensitivity/feature_ablation\.csv$',
     'python projects/ca_tosg/evaluation/feature_ablation.py', 'FA-1 comparison table'),
    (r'^sensitivity/feature_ablation_runs/.*$',
     'python projects/ca_tosg/evaluation/feature_ablation.py', 'FA-1 LOSO + frozen-walk evidence'),
    (r'^manifests/P4A_MANIFEST\.json$',
     'python tools/run_baselines.py contextual_bandit --train', 'internal learned-policy comparator, not deployed'),
    (r'^channel/bler_sionna\.csv$', 'python tools/build_bler_table.py', 'AWGN + Rayleigh'),
    (r'^channel/bler_sionna_ofdm\.csv$', 'python tools/build_bler_table.py --ofdm', ''),
    (r'^channel/bler_sionna_rician\.csv$',
     'python tools/build_bler_table.py --rician_K ...', 'Rician bracket (Appendix B.1)'),
    (r'^channel/bler_old_vs_new\.svg$',
     'python projects/ca_tosg/evaluation/figures/plot_bler_compare.py', 'old-vs-new BLER evidence'),
    (r'^main/(replay_\w+\.csv|replay_summary\.csv|action_distribution\.csv|perclass_ELF\.csv|'
     r'r9_decision\.csv)$', 'python tools/evaluate_selector.py', '200-realisation deployment replay'),
    (r'^main/true_e2e_ap\.csv$', 'python tools/evaluate_ap.py', 'global-sort true end-to-end AP'),
    (r'^main/r10c_\w+\.csv$',
     'python projects/ca_tosg/evaluation/decision_log.py', 'per-frame decision log + accounting'),
    (r'^main/ego_only_acceptance\.csv$',
     'python projects/ca_tosg/datasets/run_ego_only.py', ''),
    (r'^sensitivity/(channel_ratio|nonuniform_snr|channel_misclassification|object_message_bler|'
     r'rician_proxy|baseline_sanity)\.csv$', 'python tools/run_sensitivity.py', 'Appendix B items 1-5'),
    (r'^sensitivity/item3_variants\.csv$',
     'python projects/ca_tosg/evaluation/p3_variants.py', 'validate-only, NOT deployed'),
    (r'^sensitivity/item5c_\w+\.csv$',
     'python projects/ca_tosg/evaluation/rician_bracket.py', 'bracketing variant, not deployed'),
    (r'^sensitivity/difficulty_frozen\.csv$',
     'python projects/ca_tosg/evaluation/difficulty_frozen.py',
     'P5-5 item 7: difficulty stratification under the FROZEN protocol, reliable-channel view '
     'only (the all-channel view is deliberately not reproduced)'),
    (r'^main/fixed_references\.csv$',
     'python projects/ca_tosg/evaluation/fixed_references.py',
     'P5-7 (A): Fixed L / F / C256 / masked-oracle references under the FROZEN replay draw '
     '(no clairvoyant row -- it has no frozen definition)'),
    (r'^main/frozen_curves\.csv$',
     'python projects/ca_tosg/evaluation/frozen_curves.py',
     'P5-7 (D): the single frozen SNR-indexed source for Figs. 4/5/6/8'),
    (r'^main/true_e2e_ap_by_snr\.csv$',
     'python projects/ca_tosg/evaluation/end_to_end_ap_snr.py',
     'P5-5 item 8: true end-to-end AP at pinned SNR; only valid after --verify (the E-8 '
     'uniform-mode reproduction gate) has passed'),
    (r'^sensitivity/ablation/a7_\w+\.csv$',
     'python projects/ca_tosg/evaluation/ablations/a7_ablation.py', ''),
    (r'^sensitivity/ablation/a8_models\.csv$',
     'python projects/ca_tosg/evaluation/ablations/a8_models.py', ''),
    (r'^sensitivity/ablation/robustness_\w+\.csv$',
     'python projects/ca_tosg/evaluation/ablations/robustness.py', ''),
    (r'^sensitivity/(robustness_\w+|multiseed_hardening)\.csv$',
     'python projects/ca_tosg/evaluation/ablations/(robustness|a9_hardening).py', ''),
    (r'^sensitivity/scene_subsets\.csv$',
     'python projects/ca_tosg/evaluation/ablations/a3_subsets.py', ''),
    (r'^sensitivity/l_channel_reliability\.csv$',
     'python projects/ca_tosg/evaluation/ablations/a6_l_reliability.py', ''),
    (r'^sensitivity/snr_threshold\.csv$',
     'python projects/ca_tosg/evaluation/ablations/a7_ablation.py', 'SNR-threshold arm'),
    (r'^sensitivity/(gamma_mechanism|harm_stratum_structural|'
     r'frontier_payload_invariance)\.csv$',
     'python projects/ca_tosg/evaluation/verifiers/verify_<name>.py', 'one-shot claim verifiers'),
    (r'^sensitivity/(canonical_rescore|canonical_f1_columns)\.csv$',
     'python projects/ca_tosg/evaluation/canonical_rescore.py', 'canonical union-GT ruler'),
    (r'^sensitivity/(gt_audit|gt_object_stats)\.csv$',
     'python projects/ca_tosg/evaluation/gt_audit.py', ''),
    (r'^main/step4_collaboration_harm\.csv$',
     'python projects/ca_tosg/evaluation/collab_harm.py', ''),
    (r'^sensitivity/f1_ap_decoupling_culver\.(csv|md)$',
     'python projects/ca_tosg/evaluation/true_e2e_global.py', 'Culver F1-vs-AP decoupling note'),
    (r'^latency/(selector_latency|system_timing)\.csv$',
     'python tools/benchmark_latency.py', 'batch-1 online operating point'),
    # R53: the common-volume diagnostic track. Not a frozen product: it re-scores the SAME cached
    # outputs inside the branches' intersection volume and reports the delta per cell.
    (r'^diagnostics/common_volume_ap\.csv$',
     'python baselines/where2comm_v2/volume_diagnostic.py --splits validate,test,culver '
     '--realisations 20',
     'R53 DIAGNOSTIC TRACK (not frozen): AP inside the common volume x<=70.4, y<=40 beside the '
     'frozen table, per cell, with the GT fraction dropped'),
    # the diagnostic's raw per-run outputs (the promoted copy is diagnostics/common_volume_ap.csv)
    (r'^diagnostic/volume_(diagnostic|delta)_x[\d.]+_y[\d.]+_[a-z-]+\.csv$',
     'python baselines/where2comm_v2/volume_diagnostic.py --splits validate,test,culver '
     '--realisations 20',
     'R53 raw output of the common-volume diagnostic, one file per (volume, split set)'),
    (r'^baselines/where2comm_v2/(sparsity_payload&#124;budget_match)\.csv$'.replace('&#124;', '|'),
     'python baselines/where2comm_v2/sweep.sh then the accounting in the R55/R57 change-log',
     'R55-R57: measured threshold->sparsity and the budget-match verdict per cap (descriptive arm)'),
    (r'^diagnostics/transport_replay_ci\.csv$',
     'python baselines/where2comm_v2/paired_bootstrap.py',
     'R59/R60: paired-bootstrap intervals over CSI realisations for the transport cells'),
    (r'^diagnostics/transport_replay\.csv$',
     'python baselines/where2comm_v2/collect_transport.py',
     'R60: deterministic summary of the seven per-cell transport JSONs'),
    (r'^diagnostics/transport_replay(_[a-z]+_thr[\d.]+_B[\d.]+)?\.(csv|json)$',
     'python baselines/where2comm_v2/transport_replay.py --point <split>:<thr> --budget <B> '
     '[--mix <thr>:<p>]',
     'R58-2: the external arm under the MODELLED transport (own N_cw, shared CSI draw and delivery '
     'coin, failure falls back to its own ego-only forward); --mix is amendment A2'),
    (r'^diagnostics/intersection_gt_track_B0\.30\.csv$',
     'python baselines/where2comm_v2/intersection_gt_track.py --point validate:0.013 '
     '--point test:0.013 --point culver:0.013 --budget 0.30',
     'R57 ideal-delivery track at B_max=0.30 (threshold 0.013 on all three splits)'),
    (r'^diagnostics/intersection_gt_track\.csv$',
     'python baselines/where2comm_v2/intersection_gt_track.py --point validate:0.02 '
     '--point test:0.015 --point culver:0.02',
     'R56 THIRD TRACK (descriptive): Where2comm vs the mainline arms on a GT set made identical by '
     'construction (centre matching, eps=0.5 m, counts asserted equal)'),
    (r'^diagnostics/PROVENANCE_intersection_gt\.txt$',
     'python baselines/where2comm_v2/intersection_gt_track.py --point validate:0.02 '
     '--point test:0.015 --point culver:0.02', 'provenance for the intersection-GT track'),
    (r'^diagnostics/branch_ranges\.csv$',
     'python baselines/where2comm_v2/branch_ranges.py',
     'R53: each branch checkpoint\'s CONFIGURED lidar range, read from its own config'),
    (r'^diagnostics/PROVENANCE_common_volume\.txt$',
     'python baselines/where2comm_v2/volume_diagnostic.py --splits validate,test,culver '
     '--realisations 20',
     'provenance for the common-volume diagnostic track'),
    (r'^baselines/contextual_bandit\.csv$',
     'python tools/run_baselines.py contextual_bandit --evaluate', ''),
    (r'^baselines/contextual_bandit_runs/.*$',
     'python tools/run_baselines.py contextual_bandit --train|--evaluate', ''),
    (r'^baselines/two_gate(_actions)?\.csv$',
     'python tools/run_baselines.py two_gate --evaluate',
     'R21-A two-scalar hand rule, DESCRIPTIVE, not deployed'),
    (r'^baselines/two_gate_dgate(_actions)?\.csv$',
     'python tools/run_baselines.py two_gate --evaluate --arm dgate',
     'R21-A-2 amendment: three-scalar hand rule, DESCRIPTIVE, not deployed'),
    (r'^baselines/two_gate_runs/.*$',
     'python tools/run_baselines.py two_gate --train|--evaluate [--arm dgate]',
     'R21-A / R21-A-2 candidate walks + 200-realisation replays'),
    (r'^manifests/R21A2?_MANIFEST\.json$',
     'python tools/run_baselines.py two_gate --train [--arm dgate]',
     'R21-A / R21-A-2 hand-rule freeze record, not deployed'),
    (r'^baselines/importance_map_jscc/(two_regime\w*|jscc_ap_f1)\.csv$',
     'python baselines/importance_map_jscc/perframe/build_two_regime_edge_clean.py', ''),
    (r'^baselines/importance_map_jscc/channel_codec_ap_\w+\.csv$',
     'python baselines/importance_map_jscc/perframe/build_channel_codec_ap.py', ''),
    (r'^baselines/importance_map_jscc/jscc_selector_\w+\.csv$',
     'python baselines/importance_map_jscc/perframe/jscc_selector_compare.py', ''),
    (r'^baselines/importance_map_jscc/interp_probe_mae\.csv$',
     'python baselines/importance_map_jscc/perframe/jscc_sweep.py', ''),
    # --- back-fill: files committed by the P0 / R18 batches that no rule covered (found when the
    # index was regenerated for R21-A; the index had drifted from 0 unattributed to 6).
    (r'^main/tau_feasible\.csv$|^manifests/TAU_FEASIBLE_MANIFEST\.json$',
     'python projects/ca_tosg/evaluation/tau_feasible.py',
     'R18-3: the budget-matched threshold reference'),
    (r'^main/feature_importance_frozen\.csv$',
     'python projects/ca_tosg/evaluation/feature_importance_frozen.py',
     'importances of the FROZEN selectors (the non-frozen twin is plot_feature_importance.py)'),
    (r'^manifests/N1_DATASET_MANIFEST\.json$',
     'python projects/ca_tosg/evaluation/n1_arm_pipeline.py',
     'P0 ruling (a): the N=1 nearest-collaborator dataset build'),
    (r'^manifests/P0_REPLAY_MANIFEST\.json$',
     '(hand-recorded; no generator -- the P0-3 replay self-check record)',
     'P0-3: bit-identity self-checks of the corrigendum replay'),
    (r'^step4_collaboration_harm\.csv$',
     'python projects/ca_tosg/evaluation/collab_harm.py',
     'P1-v3 collaboration-harm table (regenerated by tools/regenerate_p0_products.py under P0)'),
    (r'^sensitivity/delivery_semantics_bracket\.csv$',
     'python projects/ca_tosg/evaluation/delivery_semantics_bracket.py',
     'R26-2: the two delivery semantics (charge on delivery vs on request) bracketed per budget, '
     'derived from the committed collaborator_scale.csv'),
    (r'^sensitivity/r25_fragmentation_replay\.csv$',
     'python projects/ca_tosg/evaluation/r23_sensitivity.py',
     'R25-3: the fragmentation/HARQ arm carried through the full deployment replay '
     '(6 configurations x 3 splits x 3 budgets, RF / tau / Fixed-L)'),
    (r'^sensitivity/r23_(scene_bootstrap|object_message_bler|fragmentation_harq|fragmentation_bler)\.csv$',
     'python projects/ca_tosg/evaluation/r23_sensitivity.py',
     'R23-C: the three R20 item-10 sensitivities (scene-level bootstrap, L-link reliability, '
     'fragmentation/HARQ), pre-registered in Change-log R23-C'),
    (r'^provenance/.*$', '(written alongside its result by the command above)',
     'provenance records: seeds, hashes, env, protocol'),
]


def rows():
    files = subprocess.check_output(['git', '-C', ROOT, 'ls-files', 'results'], text=True).split()
    out = []
    for f in sorted(files):
        rel = f[len('results/'):]
        if rel == 'README.md':
            continue
        cmd = note = None
        for pat, c, n in RULES:
            if re.match(pat, rel):
                cmd, note = c, n
                break
        out.append((rel, cmd, note))
    return out


def render():
    rs = rows()
    unattributed = [r for r in rs if r[1] is None]
    by_dir = {}
    for rel, cmd, note in rs:
        by_dir.setdefault(os.path.dirname(rel) or '.', []).append((rel, cmd, note))
    L = ['# results/ — what produces what', '',
         'Every committed result file and the command that generates it. Generated by',
         '`python projects/ca_tosg/utils/results_index.py --write`; a file that matches no rule is',
         'listed as **UNATTRIBUTED** rather than omitted.', '',
         '`data/`, `experiment_logs/` and the model binaries are git-excluded: see',
         '`docs/dataset.md` and `docs/data_manifest.md`.', '',
         '| # | directory | files |', '|---|---|---|']
    for d in sorted(by_dir):
        L.append('| | `results/%s/` | %d |' % (d, len(by_dir[d])))
    L.append('')
    for d in sorted(by_dir):
        L += ['## `results/%s/`' % d, '', '| file | generated by | note |', '|---|---|---|']
        for rel, cmd, note in by_dir[d]:
            L.append('| `%s` | %s | %s |' % (os.path.basename(rel),
                                             '`%s`' % cmd if cmd else '**UNATTRIBUTED**',
                                             note or ''))
        L.append('')
    L += ['---', '',
          '%d files indexed, %d unattributed.' % (len(rs), len(unattributed)), '']
    return '\n'.join(L)


def main():
    body = render()
    if '--write' in sys.argv:
        open(OUT, 'w', encoding='utf-8').write(body)
        print('wrote results/README.md (%d bytes)' % len(body))
    else:
        print(body)
    un = [r for r in rows() if r[1] is None]
    for rel, _, _ in un:
        print('UNATTRIBUTED: results/%s' % rel, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
