#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R14 C — draft training plan for a joint (task + channel) action selector.

**Written, not run.** Nothing here trains anything, and the plan is not adopted until it is reviewed.
Its numbers are pulled from the frozen artefacts rather than typed, so the plan cannot quietly
describe a configuration the data does not have.

  C-1  objective: predict the perception value of each action from what the ego knows before it
       transmits, then choose. Labels do not come from a channel threshold; the threshold is a
       comparison arm only. Payload is not in the objective.
  C-2  two implementations written side by side: classify a*, or regress Q(a) and take the argmax
  C-3  a constructive definition of active E, pending review
  C-4  the evaluation design
  C-5  draft success criteria, pending review

    python training_plan.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
V2 = os.path.join(ROOT, 'results', 'v2')
CUE_META = os.path.join(V2, 'wp6_cues_validate.json')
GRID = os.path.join(V2, 'v2_grid_validate_ideal.csv')
CHAIN = os.path.join(V2, 'payload_chain.json')
POTENTIAL = os.path.join(HERE, 'offline_potential.json')
OUT_JSON = os.path.join(HERE, 'training_plan.json')
OUT_MD = os.path.join(HERE, 'training_plan.md')
TOL = 1e-9
Q_F_CLEAN = 0.99


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def build():
    cue = json.load(open(CUE_META))
    pot = json.load(open(POTENTIAL))
    chain = json.load(open(CHAIN))['F']
    g = pd.read_csv(GRID, usecols=['sample_id', 'scene', 'snr_db', 'channel', 'B_L'])

    n_perc = int(cue['n_perception_fields'])
    ch_fields = list(cue['channel_fields'])
    total_dim = int(cue['total_dimensions'])
    if n_perc + len(ch_fields) != total_dim:
        raise SystemExit('cue dimensions do not add up -- stop')

    by_label = {a['label']: a for a in pot['analyses']}
    headline = by_label['all 22 cells']
    sys.path.insert(0, HERE)
    from offline_potential import CLEAN_LABEL                           # noqa: E402
    clean_lbl = CLEAN_LABEL
    clean = by_label.get(clean_lbl)
    ref_shares = {lab: {'optimal_share': a['optimal_share'], 'rows': a['rows'],
                        'rule_share_F': a['rule_share_F']} for lab, a in by_label.items()}

    return {'schema': 'catosg-p2-training-plan/1',
            'status': 'DRAFT, written for review. No model is trained, no GPU is used, and nothing in '
                      'this file has been executed as an experiment',
            'inputs': {'cue_meta': sha(CUE_META), 'grid': sha(GRID), 'potential': sha(POTENTIAL)},
            'feature_space': {
                'perception_fields': int(n_perc), 'channel_fields': ch_fields,
                'total_dimensions': total_dim,
                'field_names': list(cue['perception_fields']),
                'correction': 'the brief asked for "the 23-dimensional cue plus estimated SNR plus '
                              'channel type". That double-counts: the 23 dimensions are already '
                              f'{n_perc} perception fields plus the {len(ch_fields)} channel fields '
                              f'{ch_fields}. The input is {n_perc} + {len(ch_fields)} = {total_dim}, '
                              'not 25',
                'point_source': cue['point_source']},
            'data': {'frames': int(g.sample_id.nunique()), 'scenes': int(g.scene.nunique()),
                     'cells': int(g.groupby(['channel', 'snr_db']).ngroups),
                     'rows': int(len(g)),
                     'split_rule': 'validate only. test and Culver are not touched at any point in '
                                   'this plan, including for model selection'},
            'payload': {'F_qam_symbols': chain['msym'] * 1e6, 'F_codewords': chain['n_cw'],
                        'L_qam_symbols_min': float(g.B_L.min() * 1e6),
                        'L_qam_symbols_max': float(g.B_L.max() * 1e6)},
            'headline_potential': {
                'all_cells_G_task': headline['G_task'],
                'all_cells_optimal_share': headline['optimal_share'],
                'clean_cells_G_task': clean['G_task'] if clean else None,
                'clean_cells_optimal_share': clean['optimal_share'] if clean else None,
                'reading': 'these are the offline potentials from offline_potential.md. They bound '
                           'what any predictor could recover and are the reason this plan is worth '
                           'reviewing at all'},
            'C7_label_rule': {
                'rule': 'a*_t = argmax_a Q_t(a) under the locked all-or-nothing message accounting, '
                        f'ties to the cheaper payload, TOL = {TOL:g}',
                'fixed': 'this is the label definition and it does not change during the study',
                'prefer_F_is_not_a_label': 'the idea that F should be preferred where the channel '
                                           'permits it is recorded as a research hypothesis to be '
                                           'tested, not as a labelling rule. It does not enter the '
                                           'targets',
                'forcing_F_is_an_objective_change': 'any scheme that forces F on good-channel frames '
                                                    'is a change of objective, not a tuning choice. It '
                                                    'requires a separate discussion and a separate '
                                                    'pre-registration before it may be tried'},
            'C8_interpretation_rule': {
                'registered_before_training': True,
                'what_is_reported': 'the trained selector\'s realised E/L/F request shares, printed '
                                    'beside the offline reference shares from offline_potential B-1, '
                                    'for the same subsets',
                'reading_1': 'F has limited opportunity under the current data and transmission model',
                'reading_2': 'the inputs or the fitting are insufficient, and the selector is what to '
                             'examine',
                'forbidden': 'neither reading may be written as "F is useless", and neither is grounds '
                             'for reverting to an E/L-only design. Both are statements about this data '
                             'and this model, not about the action',
                'reference_shares': ref_shares},
            'C9_role_of_the_threshold_rule': {
                'status': 'the fixed channel-threshold rule is a COMPARISON ARM only',
                'core_question': 'whether adding task information selects among E, L and F more '
                                 'accurately than the channel alone, and what that does to perception '
                                 'quality and to the QAM-symbol cost',
                'not_the_question': 'whether a better threshold exists. A threshold sweep tunes the '
                                    'comparison arm; it does not test the hypothesis'},
            'C3_active_E': {
                'definition': f'on cells with q_F >= {Q_F_CLEAN} only, a frame is "cooperation is not '
                              f'needed for the task" when Q_E >= max(Q_L, Q_F) - {TOL:g}',
                'excluded': 'frames where E is chosen because the channel destroyed both messages. '
                            'Those are a fallback, not a statement about the task, and the q_F '
                            'restriction is what removes them',
                'status': 'CONSTRUCTIVE AND PENDING REVIEW. It is a definition being proposed, not a '
                          'measured property, and no claim rests on it until it is accepted',
                'caveat': 'two of the clean cells (AWGN 14 dB and 18 dB) have no channel sample of '
                          'their own; the definition should be evaluated on the four cells that do'},
            'command': 'python projects/ca_tosg_p2/protocol/training_plan.py'}


def markdown(m):
    f, d, p = m['feature_space'], m['data'], m['payload']
    h = m['headline_potential']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/training_plan.py -- do not edit by hand -->',
         '# Draft training plan for a joint action selector (P2-R14 C)', '',
         f"**{m['status']}.**", '',
         '## C-1 Objective', '',
         'Predict, from what the ego vehicle knows **before it transmits**, how much perception each',
         'action would be worth, and choose on that basis. Written as a decision:', '',
         '```',
         'a_hat(t, channel state) = argmax over a in {E, L, F} of  Qhat(a | cues_t, est_SNR, channel)',
         '```', '',
         '**What the labels are not.** They are not "F above a channel threshold, L below it". A model',
         'trained on threshold labels can at best rediscover the threshold, and the threshold is',
         'already available for free — it is the comparison arm, not the teacher. Labels come from the',
         'per-frame values under the locked message accounting.', '',
         '**Payload is not in the objective.** No payload penalty, no bandwidth-weighted loss. Payload',
         'is measured and reported beside F1; if a payload trade-off is wanted later it is applied as',
         'a constraint on the decision, not smuggled into the training target.', '',
         '## What the offline potential says this is worth', '',
         f"Over all cells the per-frame optimum beats the channel-only rule by "
         f"**{h['all_cells_G_task']['mean']:+.5f}** scene-equal F1 "
         f"[{h['all_cells_G_task']['lcb95']:+.5f}, {h['all_cells_G_task']['ucb95']:+.5f}]."]
    if h['clean_cells_G_task']:
        c = h['clean_cells_G_task']
        L.append(f"Restricted to the cells where the channel is no longer the variable it is "
                 f"**{c['mean']:+.5f}** [{c['lcb95']:+.5f}, {c['ucb95']:+.5f}] — that second number is "
                 'the one that matters here, because it is the part a task-side model could address.')
    L += ['', 'These are **upper bounds under perfect foresight**, not achievable gains. A predictor',
          'recovers some fraction of them; the fraction is the open question this plan exists to test.',
          '', '## C-2 Two implementations, written side by side', '',
          f"**Input, both variants:** {f['perception_fields']} perception cues + "
          f"{len(f['channel_fields'])} channel fields {f['channel_fields']} = "
          f"**{f['total_dimensions']} dimensions**.", '',
          f"*A correction to the brief:* {f['correction']}.", '',
          f"The perception cues are ego-only by construction — {f['point_source']}", '',
          '### (i) Classify a\\*', '',
          '| | |', '|---|---|',
          '| **Label** | the tie-broken per-frame optimum a\\*, computed under the locked accounting |',
          '| **Loss** | cross-entropy weighted, per sample, by the F1 actually lost if that sample is '
          'misclassified: `w = Q(a*) − Q(second best)`. A frame where all three actions are within '
          'a thousandth of each other must not carry the same weight as one where the wrong choice '
          'costs 0.2 F1 |',
          '| **Reported** | never accuracy alone: the realised scene-equal F1 of the policy, which is '
          'what accuracy is a proxy for and frequently a poor one |',
          '| **Risk** | the label is a hard argmax over three近-tied numbers, so it throws away the '
          'margin information the weighting then has to put back |', '',
          '### (ii) Regress Q(a), then take the argmax', '',
          '| | |', '|---|---|',
          '| **Label** | three targets per row: Q_E, Q_L, Q_F under the locked accounting |',
          '| **Loss** | squared error on each head, plus the same decision-weighted term so the model '
          'is pushed hardest where the ordering is what matters. Q_E needs no channel input; Q_L and '
          'Q_F are the product of a perception term and a delivery term, and the delivery term is '
          'known in closed form — so the honest target for the model is the **perception** term '
          '(F1_clean, F1_L, F1_ego) with q_F and q_L applied afterwards, analytically |',
          '| **Reported** | the same policy F1, plus the regression error per head |',
          '| **Why it may win** | it predicts three quantities that are properties of the scene alone '
          'and lets the known channel arithmetic do the rest, instead of asking one classifier to '
          'learn the channel arithmetic from data it already has in closed form |', '',
          '**Model candidates, both variants:** random forest and gradient boosting (the cue vector is',
          'low-dimensional, tabular and heterogeneous, which is where trees are strong), and a small',
          'MLP as the check that the trees are not leaving anything obvious behind. No deep model: with',
          f"{d['frames']:,} frames over {d['scenes']} scenes there is not the data to justify one.", '',
          '**Selection: leave-one-scene-out.** Nine folds, each holding out one scene entirely.',
          'Hyperparameters and the choice between (i) and (ii) are decided on the LOSO mean of the',
          'realised policy F1 — never on a single fold, never on accuracy.', '',
          '**Freeze rule.** One configuration is frozen before anything is reported as a result: the',
          'model file is hashed into a freeze manifest with its LOSO number, and the reported',
          'evaluation runs that frozen artefact. If a second configuration is tried after seeing the',
          'evaluation, the freeze is void and the report says so.', '',
          f"**Data.** validate only, {d['frames']:,} frames x {d['cells']} cells = {d['rows']:,} rows, "
          f"{d['scenes']} scenes. {d['split_rule']}.", '',
          '## C-3 Active E, defined constructively', '',
          f"{m['C3_active_E']['definition']}.", '',
          f"**What it excludes.** {m['C3_active_E']['excluded']}.", '',
          f"**Status.** {m['C3_active_E']['status']}. {m['C3_active_E']['caveat']}.", '',
          'The distinction this draws is the one P2-R11 B-3 asked for: a frame where the channel',
          'removed the benefit is not a frame where the task had no use for cooperation, and only the',
          'second deserves to be called an ego-only decision.', '',
          '## C-6 What is migrated from P1, and what is not', '',
          'The migration list with paths and sha256 hashes is registered in `p2_protocol.md` and',
          'verified by `build_reuse_manifest.py`. It is kept there rather than here because it is a',
          'protocol commitment, not a plan detail.', '',
          '## C-7 The label rule, fixed', '',
          f"```\n{m['C7_label_rule']['rule']}\n```", '',
          f"{m['C7_label_rule']['fixed'].capitalize()}.", '',
          f"**\"Prefer F\" is not a label.** {m['C7_label_rule']['prefer_F_is_not_a_label']}.", '',
          f"**{m['C7_label_rule']['forcing_F_is_an_objective_change']}**", '',
          '## C-8 How the result will be read, decided in advance', '',
          f"After training, report {m['C8_interpretation_rule']['what_is_reported']}. Registering this "
          'before training is the point: it removes the freedom to pick whichever reading the numbers',
          'happen to flatter.', '',
          '| subset | rows | offline reference: E | L | F | rule requests F |',
          '|---|---:|---:|---:|---:|---:|']
    for lab, r in m['C8_interpretation_rule']['reference_shares'].items():
        o = r['optimal_share']
        L.append(f"| {lab} | {r['rows']:,} | {o['E'] * 100:.1f} % | {o['L'] * 100:.1f} % | "
                 f"{o['F'] * 100:.1f} % | {r['rule_share_F'] * 100:.1f} % |")
    L += ['', 'The trained selector\'s shares go in a matching column beside these.', '',
          f"* **If the offline reference itself rarely chooses F** — the honest reading is that "
          f"{m['C8_interpretation_rule']['reading_1']}.",
          f"* **If the reference chooses F often and the selector does not** — the honest reading is "
          f"that {m['C8_interpretation_rule']['reading_2']}.", '',
          f"**{m['C8_interpretation_rule']['forbidden']}**", '',
          '## C-9 What the threshold rule is for', '',
          'The fixed channel-threshold rule is a **comparison arm only**. The question being tested is '
          f"{m['C9_role_of_the_threshold_rule']['core_question']}.", '',
          f"It is **not** the question of {m['C9_role_of_the_threshold_rule']['not_the_question']}.", '',
          '## C-4 Evaluation design', '',
          '**Arms.** Fixed E, Fixed L, Fixed F, the channel-only rule, a **task-input-only** policy',
          '(the cues without the two channel fields), and the joint selector. The task-only arm is what',
          'separates "the model learned the channel" from "the model learned the scene".', '',
          '**Accounting.** The locked all-or-nothing message rule throughout: no chunking, no partial',
          'recovery, no 100 ms admissibility gate. A message either decodes whole or the frame falls',
          'back to E, and the channel is charged for the attempt either way.', '',
          '**Metrics.** Scene-equal F1 first. Beside it, and never replaced by it: recall and the count',
          'of missed objects (an F1 that holds up while misses rise is a different system), the request',
          'share per action, and the payload in QAM data symbols — '
          f"F is {p['F_qam_symbols']:,.0f} symbols ({p['F_codewords']:,} codewords) against L's "
          f"{p['L_qam_symbols_min']:,.0f} to {p['L_qam_symbols_max']:,.0f}.", '',
          '**Protocol.** Scene-level development and validation; scene-level bootstrap intervals,',
          '10,000 resamples, the seed already in use. Negative scenes are reported as they are.', '',
          '## C-5 Draft success criteria, pending review', '',
          'Stated before any training so they cannot be fitted afterwards. All are scene-equal F1',
          'differences with scene-level bootstrap 95 % intervals.', '',
          '| # | criterion | why this one |', '|---|---|---|',
          '| 1 | joint selector − channel-only rule, interval **entirely above zero** | if the channel '
          'rule is not beaten there is no selector worth deploying, only a threshold |',
          '| 2 | joint selector − task-input-only policy, reported with its interval | shows whether the '
          'channel inputs contribute anything beyond the scene cues |',
          '| 3 | joint selector − Fixed F and − Fixed L, both reported | a policy that beats the rule '
          'but loses to a fixed arm has not earned its complexity |',
          '| 4 | the fraction of the offline potential recovered | states plainly how much of the '
          'headroom the predictor actually reaches |', '',
          '**No payload criterion.** Payload is reported for every arm and is not a success condition;',
          'a payload saving bought with an unmeasured F1 loss is the failure mode this whole line of',
          'work exists to avoid.', '',
          '## Inputs', '', '| file | sha256 |', '|---|---|']
    for k, v in m['inputs'].items():
        L.append(f"| {k} | `{v[:16]}…` |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = (os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js
              and os.path.exists(OUT_MD) and open(OUT_MD).read() == md)
        print('training plan:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
