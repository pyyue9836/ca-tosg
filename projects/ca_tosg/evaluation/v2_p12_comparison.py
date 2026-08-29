#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R27 E-1 — P1-2's actual test: does the learned selector beat the simple rules at equal budget?

P1-2's criterion is **not** "how close is the selector to its own oracle". It is whether the RF beats
a threshold and a hand rule. So this module compares, at the same budgets and on the same grid:

    frozen RF (candidate 67)   the v2 selector, validate-fitted
    SNR threshold tau          request F when est_snr_db >= tau, else L; tau swept over the
                               pre-registered grid and picked by the same budget-feasible rule
    hand rules                 two-scalar (snr, ego box count) and three-scalar (+ point count)
    Fixed E / Fixed L / Fixed F   the constant policies
    oracle                     per-row argmax of eff, budget-blind -- an upper reference, not a rival

C-1 also lives here: the F-collapse is reported as **two separate questions** (D-3's structure with
F in E's place), and the two answers are never merged into one sentence.

    python projects/ca_tosg/evaluation/v2_p12_comparison.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
V2 = os.path.join(ROOT, 'results', 'v2')
MAN = os.path.join(ROOT, 'results', 'manifests', 'V2_FROZEN_MANIFEST.json')
OUT = os.path.join(V2, 'v2_p12_comparison.json')

from projects.ca_tosg.models.v2_selector import (B_F, load_grid, lam_labels,  # noqa: E402
                                                 parse_candidates, realised)
from sklearn.ensemble import RandomForestClassifier                          # noqa: E402

ACTIONS = ['E', 'L', 'F']


def scene_equal_f1(pred, eff, scenes):
    r = np.arange(len(pred))
    v = eff[r, pred]
    return float(np.mean([v[scenes == s].mean() for s in pd.unique(scenes)]))


def summarise(pred, eff, B, scenes):
    f1_fw, pay = realised(pred, eff, B)
    return {'frame_weighted_f1': float(f1_fw), 'scene_equal_f1': scene_equal_f1(pred, eff, scenes),
            'mean_payload_msym': float(pay),
            'mix': {a: float((pred == i).mean()) for i, a in enumerate(ACTIONS)}}


def main():
    block, cands = parse_candidates()
    g, X, names, eff, B = load_grid('ideal')
    scenes = g.scene.to_numpy()
    snr = g.snr_db.to_numpy(float)
    man = json.load(open(MAN))
    betas = block['budgets']
    tg = block['tau_grid']
    taus = np.arange(tg['start'], tg['stop'] + 1e-9, tg['step'])

    ci = man['walks'][str(betas[0])]['selected_candidate_index']
    c = cands[ci]
    y = lam_labels(eff, B, c['lam'])
    rf = RandomForestClassifier(n_estimators=c['n_estimators'], max_depth=c['max_depth'],
                                min_samples_leaf=c['min_samples_leaf'],
                                max_features=c['max_features'], class_weight=c['class_weight'],
                                random_state=block['seed'], n_jobs=-1).fit(X, y)
    rf_pred = rf.predict(X)

    arms = {'frozen_RF_cand%d' % ci: summarise(rf_pred, eff, B, scenes)}
    for i, a in enumerate(ACTIONS):
        arms['Fixed_' + a] = summarise(np.full(len(eff), i), eff, B, scenes)
    arms['oracle_budget_blind'] = summarise(eff.argmax(1), eff, B, scenes)

    # SNR threshold: F above tau, L below. Picked per budget by the SAME feasible-then-best rule.
    tau_rows = []
    for t in taus:
        p = np.where(snr >= t, 2, 1)
        s = summarise(p, eff, B, scenes)
        tau_rows.append({'tau': float(t), **{k: v for k, v in s.items() if k != 'mix'}})
    tau_df = pd.DataFrame(tau_rows)

    # hand rules: threshold on SNR AND on the ego's own detected box count (a v2_ego_local_23d field)
    cues = pd.read_csv(os.path.join(V2, 'wp6_cues_validate.csv'))
    nbox = cues.ego_detected_box_count.to_numpy()[g.sample_id.to_numpy()]
    hand = {}
    for t in (6.0, 8.0, 10.0, 12.0):
        for nb in (15, 20, 25):
            p = np.where((snr >= t) & (nbox <= nb), 2, 1)
            hand[f'two_scalar_snr{t}_nbox{nb}'] = summarise(p, eff, B, scenes)

    verdict = {}
    for beta in betas:
        bmax = beta * B_F
        feas_tau = tau_df[tau_df.mean_payload_msym <= bmax]
        best_tau = (feas_tau.sort_values(['scene_equal_f1', 'mean_payload_msym'],
                                         ascending=[False, True]).iloc[0]
                    if len(feas_tau) else None)
        feas_hand = {k: v for k, v in hand.items() if v['mean_payload_msym'] <= bmax}
        best_hand = max(feas_hand.items(), key=lambda kv: kv[1]['scene_equal_f1']) \
            if feas_hand else (None, None)
        rf_s = arms['frozen_RF_cand%d' % ci]
        verdict[str(beta)] = {
            'B_max_msym': bmax,
            'RF': {'scene_equal_f1': rf_s['scene_equal_f1'],
                   'payload': rf_s['mean_payload_msym']},
            'best_tau': (None if best_tau is None else
                         {'tau': best_tau.tau, 'scene_equal_f1': best_tau.scene_equal_f1,
                          'payload': best_tau.mean_payload_msym}),
            'best_hand_rule': (None if best_hand[0] is None else
                               {'rule': best_hand[0],
                                'scene_equal_f1': best_hand[1]['scene_equal_f1'],
                                'payload': best_hand[1]['mean_payload_msym']}),
            'Fixed_L': {'scene_equal_f1': arms['Fixed_L']['scene_equal_f1'],
                        'payload': arms['Fixed_L']['mean_payload_msym']},
        }
        d_tau = (None if best_tau is None else rf_s['scene_equal_f1'] - best_tau.scene_equal_f1)
        d_hand = (None if best_hand[0] is None else
                  rf_s['scene_equal_f1'] - best_hand[1]['scene_equal_f1'])
        d_fl = rf_s['scene_equal_f1'] - arms['Fixed_L']['scene_equal_f1']
        verdict[str(beta)]['RF_minus'] = {'tau': d_tau, 'hand_rule': d_hand, 'Fixed_L': d_fl}
        verdict[str(beta)]['RF_beats_all_simple_rules'] = bool(
            (d_tau is None or d_tau > 0) and (d_hand is None or d_hand > 0) and d_fl > 0)

    # C-1: the two questions, answered separately and never merged
    net_F = eff[:, 2] - np.maximum(eff[:, 0], eff[:, 1])
    helps = net_F > 0
    q1 = {'question': 'LEARNING -- on rows where F genuinely has the highest realised utility, does '
                      'the frozen selector choose F?',
          'rows_where_F_is_best': int(helps.sum()),
          'share_of_grid': float(helps.mean()),
          'selector_chose_F_there': float((rf_pred[helps] == 2).mean()) if helps.any() else None,
          'mean_net_gain_where_F_is_best': float(net_F[helps].mean()) if helps.any() else None}
    q2 = {'question': 'DESIGN -- elsewhere, is rho_F = 0 simply what the cost structure implies?',
          'B_F_msym': B_F,
          'lambda_of_frozen_candidate': c['lam'],
          'lambda_times_B_F': c['lam'] * B_F,
          'break_even_lambda_if_gain_is_mean_net': (
              float(net_F[helps].mean() / B_F) if helps.any() else None),
          'note': 'A break-even lambda BELOW the smallest non-zero grid point means the '
                  'pre-registered grid never sampled the region where F could be chosen. That is a '
                  'statement about grid resolution, NOT about whether F is worth its cost -- the '
                  'two must not be merged (V2-R27 B-4).'}

    out = {'schema': 'catosg-v2-p12-comparison/1', 'split': 'validate', 'regime': 'ideal',
           'frozen_candidate_index': ci, 'lambda': c['lam'],
           'metric_note': 'scene_equal_f1 is the scene-equal mean; frame_weighted_f1 weights every '
                          'grid row equally. They are DIFFERENT statistics and are not comparable '
                          'to each other (V2-R27 C-3).',
           'arms': arms, 'hand_rules': hand,
           'tau_sweep': tau_rows, 'verdict_per_budget': verdict,
           'F_collapse_question_1_learning': q1,
           'F_collapse_question_2_design': q2}
    with open(OUT, 'w') as f:
        json.dump(out, f, indent=1)

    print('=' * 96)
    print(f'P1-2 comparison at equal budget -- frozen RF candidate {ci} (lambda {c["lam"]})')
    print('=' * 96)
    print(f'{"arm":34}{"scene-equal F1":>16}{"frame-wtd F1":>15}{"payload Msym":>14}')
    for k in ('frozen_RF_cand%d' % ci, 'Fixed_E', 'Fixed_L', 'Fixed_F', 'oracle_budget_blind'):
        a = arms[k]
        print(f'  {k:32}{a["scene_equal_f1"]:>16.5f}{a["frame_weighted_f1"]:>15.5f}'
              f'{a["mean_payload_msym"]:>14.5f}')
    print()
    for beta, v in verdict.items():
        print(f'beta {beta} (B_max {v["B_max_msym"]:.5f}):')
        print(f'  RF        {v["RF"]["scene_equal_f1"]:.5f} @ {v["RF"]["payload"]:.5f}')
        if v['best_tau']:
            print(f'  best tau  {v["best_tau"]["scene_equal_f1"]:.5f} @ '
                  f'{v["best_tau"]["payload"]:.5f}  (tau={v["best_tau"]["tau"]})')
        if v['best_hand_rule']:
            print(f'  best hand {v["best_hand_rule"]["scene_equal_f1"]:.5f} @ '
                  f'{v["best_hand_rule"]["payload"]:.5f}  ({v["best_hand_rule"]["rule"]})')
        print(f'  Fixed L   {v["Fixed_L"]["scene_equal_f1"]:.5f} @ {v["Fixed_L"]["payload"]:.5f}')
        print(f'  RF - tau {v["RF_minus"]["tau"]}, RF - hand {v["RF_minus"]["hand_rule"]}, '
              f'RF - FixedL {v["RF_minus"]["Fixed_L"]:.5f}')
        print(f'  RF beats ALL simple rules: {v["RF_beats_all_simple_rules"]}')
    print()
    print('F-collapse, two questions (never merged):')
    print(f'  (i) LEARNING: F is genuinely best on {q1["rows_where_F_is_best"]} rows '
          f'({q1["share_of_grid"]*100:.1f} %); the frozen selector chose F on '
          f'{(q1["selector_chose_F_there"] or 0)*100:.1f} % of them')
    print(f'  (ii) DESIGN: lambda*B_F = {q2["lambda_times_B_F"]:.5f}; break-even lambda if the gain '
          f'is the mean net gain = {q2["break_even_lambda_if_gain_is_mean_net"]}')
    print(f'\nwrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
