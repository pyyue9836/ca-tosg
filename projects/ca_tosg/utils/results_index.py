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
    (r'^manifests/(FROZEN_MANIFEST\.json|validate_loso_folds\.csv|candidate_walk_B\d+\.csv)$',
     'python tools/train_selector.py', 'freeze record + LOSO evidence chain'),
    (r'^manifests/scene_manifest_\w+\.csv$',
     'python tools/prepare_data.py --scene-manifest', 'independent frame->scene manifest'),
    (r'^manifests/P4A_MANIFEST\.json$',
     'python tools/run_baselines.py contextual_bandit --train', 'external baseline, not deployed'),
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
    (r'^main/true_e2e_global_\w+\.csv$',
     'python projects/ca_tosg/evaluation/true_e2e_global.py', 'P1-v3 global-sort scorer'),
    (r'^main/(frontier_\w+|generalisation_\w+|pareto_points|threshold_sweep_\w+|threshold_vs_rf|'
     r'action_dist_20dB|c256_frontier_band)\.csv$',
     'python projects/ca_tosg/evaluation/policy_200seed.py', 'P1-v3 200-realisation policy engine'),
    (r'^main/feature_importance\.csv$',
     'python projects/ca_tosg/evaluation/figures/plot_feature_importance.py',
     'RF feature_importances_ of the deployed selector'),
    (r'^main/step4_oracle_action_dist\.csv$',
     'python projects/ca_tosg/evaluation/action_dist.py', ''),
    (r'^main/step4_(rf_class_report|rf_modes)\.csv|^main/step4_rf_train_meta\.json$',
     'python projects/ca_tosg/models/train_rf_v3.py', 'P1-v3 selector (superseded by the P2 freeze)'),
    (r'^main/ego_only_acceptance\.csv$',
     'python projects/ca_tosg/datasets/run_ego_only.py', ''),
    (r'^sensitivity/(channel_ratio|nonuniform_snr|channel_misclassification|object_message_bler|'
     r'rician_proxy|baseline_sanity)\.csv$', 'python tools/run_sensitivity.py', 'Appendix B items 1-5'),
    (r'^sensitivity/item3_variants\.csv$',
     'python projects/ca_tosg/evaluation/p3_variants.py', 'validate-only, NOT deployed'),
    (r'^sensitivity/item5c_\w+\.csv$',
     'python projects/ca_tosg/evaluation/rician_bracket.py', 'bracketing variant, not deployed'),
    (r'^sensitivity/ablation/a2_difficulty\w*\.csv$',
     'python projects/ca_tosg/evaluation/ablations/a2_difficulty.py', ''),
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
    (r'^sensitivity/(gamma_mechanism|harm_stratum_structural|frontier_payload_invariance|'
     r'c256_dominance_verify)\.csv$',
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
    (r'^baselines/where2comm\.csv$',
     'python baselines/where2comm/compare.py', 'epoch-50 global-sort AP; see its README'),
    (r'^baselines/contextual_bandit\.csv$',
     'python tools/run_baselines.py contextual_bandit --evaluate', ''),
    (r'^baselines/contextual_bandit_runs/.*$',
     'python tools/run_baselines.py contextual_bandit --train|--evaluate', ''),
    (r'^baselines/importance_map_jscc/(two_regime\w*|jscc_ap_f1)\.csv$',
     'python baselines/importance_map_jscc/perframe/build_two_regime_edge_clean.py', ''),
    (r'^baselines/importance_map_jscc/channel_codec_ap_\w+\.csv$',
     'python baselines/importance_map_jscc/perframe/build_channel_codec_ap.py', ''),
    (r'^baselines/importance_map_jscc/jscc_selector_\w+\.csv$',
     'python baselines/importance_map_jscc/perframe/jscc_selector_compare.py', ''),
    (r'^baselines/importance_map_jscc/interp_probe_mae\.csv$',
     'python baselines/importance_map_jscc/perframe/jscc_sweep.py', ''),
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
