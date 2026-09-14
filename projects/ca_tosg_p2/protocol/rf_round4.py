#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R19 — round 4: the same inputs, a different learning target. Regress the gain, then decide.

**The only change is what is learned.** Rounds 1 to 3 fitted a classifier to the argmax label. This
round fits a regressor to the two gains

    dL = Q_L - Q_E        dF = Q_F - Q_E

per frame and cell, from the same Q table the labels were built from, and decides at request time by
`max{0, dL_hat, dF_hat}` with ties going to the cheaper payload. The zero is E's own gain, so a frame
whose two predicted gains are both negative falls to E by construction rather than by a rule.

Inputs are back to the 23 dimensions of round 1. The perception model, the complete F/L/E definitions,
the transmission rule, the original 22-cell grid, the nine scene-level folds and the per-fold tau fit
are untouched. A-5 is a gate: the round-1 classifier is re-run here and must reproduce its stored
per-row product exactly, so the target is demonstrably the only variable.

Two choices this file has to state rather than leave implicit:

  * `class_weight` is not carried over. It is a classifier-only parameter with no meaning for a
    regressor, so dropping it removes an inapplicable setting rather than introducing a new one.
    `n_estimators`, `min_samples_leaf`, `max_features` and the seed are read from the same freeze
    manifest round 1 read them from.
  * The two targets are fitted by ONE multi-output forest, not two independent ones, which keeps the
    one-forest-per-fold parity of the earlier rounds. The consequence is that splits are chosen to
    reduce the summed variance of both targets, so the two outputs are coupled. Fitting them
    separately would be a different design, not a tuning knob, and is not tried here.

    python rf_round4.py [--check] [--jobs N]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
ROUND1_OOF = os.path.join(P2, 'results', 'rf', 'rf_round1_oof.csv')
ROWS_GZ = os.path.join(P2, 'results', 'rf', 'rf_round4_rows.csv.gz')
OUT_JSON = os.path.join(HERE, 'rf_round4.json')
OUT_MD = os.path.join(HERE, 'rf_round4.md')

sys.path.insert(0, HERE)
from offline_potential import build_table, scene_equal, boot, ACTIONS, TOL             # noqa: E402
from rf_round1 import (hyperparameters, features, outcome, evaluate, confusion,        # noqa: E402
                       fit_tau, apply_tau, CUES, CUE_META, VOLATILE_FIELDS,
                       strip_volatile, json_diff)
from rf_round2 import (load_frame_outcomes, loss_breakdown, pooled_train,              # noqa: E402
                       run_round, cap1, HI_CELLS)

REG = 'RF_regression'
CLS = 'RF_classification'
MAG_EDGES = [0.0, TOL, 0.005, 0.02, 0.05, 0.10, np.inf]
MAG_LABELS = ['|dF| <= TOL', '(TOL, 0.005]', '(0.005, 0.02]', '(0.02, 0.05]', '(0.05, 0.10]',
              '> 0.10']

# C-1, fixed here before the run. The F request share is deliberately NOT among them.
C1_CRITERIA = {
    'held_out_f1_above_classifier': 'the bootstrap interval of (regression - classification) '
                                    'held-out scene-equal F1 lies entirely above zero',
    'F_not_requested_loss_reduced': 'the summed held-out loss of "should F, chose L" and '
                                    '"should F, chose E" is lower than the classifier\'s',
    'no_new_dominant_error': 'the largest single held-out loss category is no larger than the '
                             'classifier\'s largest single category',
}
C2_CONSEQUENCE = ('if this fails as well, stop changing the random-forest configuration on this input '
                  'and turn to what information is missing before the request. Do not jump to the '
                  'complete feature tensor or to a new neural network')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def regressor_hyperparameters():
    """Round 1's settings minus the one that cannot apply to a regressor."""
    hp = dict(hyperparameters())
    dropped = {k: hp.pop(k) for k in ('class_weight',) if k in hp}
    return hp, dropped


def decide(dL_hat, dF_hat):
    """A-3: max{0, dL_hat, dF_hat}, ties to the cheaper payload. The zero column is E's own gain."""
    vals = np.stack([np.zeros_like(dL_hat), dL_hat, dF_hat], axis=1)
    best = vals.max(axis=1)
    within = vals >= best[:, None] - TOL
    return np.array(ACTIONS)[np.argmax(within, axis=1)].astype(object)


def run_regression(g, cues, cue_fields, dL, dF, jobs, tag):
    """One LOSO pass of the multi-output regressor, keeping training-fold predictions too."""
    from sklearn.ensemble import RandomForestRegressor
    X, names = features(g, cues, cue_fields)
    Y = np.stack([dL, dF], axis=1)
    scenes = g.scene.to_numpy()
    frames = g.sample_id.to_numpy()
    hp, dropped = regressor_hyperparameters()

    oof = np.full((len(g), 2), np.nan)
    train_blocks, folds = [], []
    for s in np.unique(scenes):
        te = scenes == s
        tr = ~te
        if set(np.unique(frames[tr])) & set(np.unique(frames[te])):
            raise SystemExit(f'fold {s}: a frame appears on both sides of the split')
        t0 = time.time()
        rf = RandomForestRegressor(n_jobs=jobs, **hp).fit(X[tr], Y[tr])
        oof[te] = rf.predict(X[te])
        pt = rf.predict(X[tr])
        idx = np.where(tr)[0]
        train_blocks.append({'scene_held_out': str(s), 'idx': idx, 'pred': decide(pt[:, 0], pt[:, 1]),
                             'proba': np.stack([np.zeros(len(idx)), pt[:, 0], pt[:, 1]], axis=1)})
        folds.append({'held_out_scene': str(s), 'train_rows': int(tr.sum()),
                      'test_rows': int(te.sum()), 'seconds': time.time() - t0})
        print(f'  [{tag}] fold {s} ({time.time() - t0:.1f}s)', flush=True)
    if np.isnan(oof).any():
        raise SystemExit('a row was never held out -- the folds do not cover the grid')
    return {'hp': hp, 'dropped_hyperparameters': dropped, 'names': names, 'oof': oof,
            'train_blocks': train_blocks, 'folds': folds}


def regression_quality(true_dL, true_dF, pred, mask, label):
    """B-3: how well the gains themselves are predicted, before any decision is taken."""
    t_dF, p_dF = true_dF[mask], pred[mask, 1]
    t_dL, p_dL = true_dL[mask], pred[mask, 0]

    def corr(a, b):
        if a.std() == 0 or b.std() == 0:
            return None
        return float(np.corrcoef(a, b)[0, 1])

    bins = []
    mag = np.abs(t_dF)
    # pd.cut on a numpy array returns a Categorical, not a Series, so `== lab` is already an ndarray.
    # rf_diagnostics passes a Series here and gets a Series back; copying that line without copying
    # the input type is what broke this. np.asarray covers both.
    cut = pd.cut(mag, bins=MAG_EDGES, labels=MAG_LABELS, include_lowest=True, right=True)
    for lab in MAG_LABELS:
        m = np.asarray(cut == lab)
        if not m.any():
            continue
        bins.append({'bin': lab, 'rows': int(m.sum()), 'mean_true_dF': float(t_dF[m].mean()),
                     'mean_pred_dF': float(p_dF[m].mean()),
                     'mean_bias': float((p_dF[m] - t_dF[m]).mean()),
                     'mean_abs_error': float(np.abs(p_dF[m] - t_dF[m]).mean())})
    return {'label': label, 'rows': int(mask.sum()),
            'corr_dF': corr(t_dF, p_dF), 'corr_dL': corr(t_dL, p_dL),
            'mae_dF': float(np.abs(p_dF - t_dF).mean()), 'mae_dL': float(np.abs(p_dL - t_dL).mean()),
            'mean_true_dF': float(t_dF.mean()), 'mean_pred_dF': float(p_dF.mean()),
            'bias_by_true_magnitude': bins}


def reg_discrimination(pred_dF, labels, mask):
    """B-3: the regression's separation, in its own units."""
    mF, mL = mask & (labels == 'F'), mask & (labels == 'L')
    if not mF.any() or not mL.any():
        return None
    return {'mean_dF_hat_where_F_optimal': float(pred_dF[mF].mean()),
            'mean_dF_hat_where_L_optimal': float(pred_dF[mL].mean()),
            'difference': float(pred_dF[mF].mean() - pred_dF[mL].mean()),
            'rows_F': int(mF.sum()), 'rows_L': int(mL.sum())}


def build(jobs=-1):
    g, n_cw_F, B_F_sym = build_table()
    fo, tp_dev = load_frame_outcomes(g)
    cues = pd.read_csv(CUES)
    cue_fields = list(json.load(open(CUE_META))['perception_fields'])
    labels = g.a_star.to_numpy().astype(object)
    scenes = g.scene.to_numpy()
    ch = g.channel.to_numpy()

    dL = (g.Q_L - g.Q_E).to_numpy()
    dF = (g.Q_F - g.Q_E).to_numpy()

    print(f'{CLS} (the A-5 gate)', flush=True)
    cls = run_round(g, cues, cue_fields, labels, jobs, None, CLS)
    stored = pd.read_csv(ROUND1_OOF)
    same_pred = bool((stored.pred_joint.to_numpy() == cls['oof_pred']).all())
    same_rule = bool((stored.pred_channel_rule.to_numpy() == cls['rule_pred']).all())
    max_dp = float(np.abs(stored[['p_E', 'p_L', 'p_F']].to_numpy() - cls['oof_proba']).max())
    if not (same_pred and same_rule) or max_dp > 1e-12:
        raise SystemExit(f'the classifier re-run is not round 1 ({same_pred}/{same_rule}, '
                         f'max |dp| {max_dp:g}) -- more than the target has changed')
    gate = {'actions_identical_to_round1': same_pred, 'channel_rule_identical': same_rule,
            'max_abs_probability_difference': max_dp,
            'what_this_proves': 'the classification arm below is round 1, so the only difference '
                                'between the two arms is the learning target'}

    print(f'{REG} (two gains, one multi-output forest)', flush=True)
    reg = run_regression(g, cues, cue_fields, dL, dF, jobs, REG)
    reg_pred = decide(reg['oof'][:, 0], reg['oof'][:, 1])

    # ---------------- the per-row product ----------------
    frames = [pd.DataFrame({
        'arm': REG, 'fold': 'held_out', 'split': 'held_out', 'sample_id': g.sample_id.to_numpy(),
        'scene': scenes, 'snr_db': g.snr_db.to_numpy(), 'channel': ch, 'a_star': labels,
        'pred': reg_pred, 'dL_true': dL, 'dF_true': dF,
        'dL_hat': reg['oof'][:, 0], 'dF_hat': reg['oof'][:, 1]})]
    for b in reg['train_blocks']:
        i = b['idx']
        frames.append(pd.DataFrame({
            'arm': REG, 'fold': b['scene_held_out'], 'split': 'training',
            'sample_id': g.sample_id.to_numpy()[i], 'scene': scenes[i],
            'snr_db': g.snr_db.to_numpy()[i], 'channel': ch[i], 'a_star': labels[i],
            'pred': b['pred'], 'dL_true': dL[i], 'dF_true': dF[i],
            'dL_hat': b['proba'][:, 1], 'dF_hat': b['proba'][:, 2]}))
    rows = pd.concat(frames, ignore_index=True)
    os.makedirs(os.path.dirname(ROWS_GZ), exist_ok=True)
    rows.to_csv(ROWS_GZ, index=False, compression={'method': 'gzip', 'mtime': 0})

    # ---------------- B-1 ----------------
    chosen = {REG: reg_pred, CLS: cls['oof_pred'], 'channel_rule': cls['rule_pred'],
              'offline_optimum': labels, 'fixed_E': np.full(len(g), 'E', object),
              'fixed_L': np.full(len(g), 'L', object), 'fixed_F': np.full(len(g), 'F', object)}
    hi = np.zeros(len(g), bool)
    for c, s in HI_CELLS:
        hi |= ((g.channel == c) & (g.snr_db == s)).to_numpy()
    subsets = [('all 22 cells', np.ones(len(g), bool)), ('AWGN only', ch == 'awgn'),
               ('Rayleigh only', ch == 'rayleigh'), ('high-reliability AWGN cells', hi)]
    arms = [evaluate(g, fo, chosen, m, lab) for lab, m in subsets]

    # ---------------- B-2 ----------------
    idx_r, pred_r, _, brk_r = pooled_train(g, labels, scenes, reg['train_blocks'])
    idx_c, pred_c, _, brk_c = pooled_train(g, labels, scenes, cls['train_blocks'])
    b2 = {REG: {'training_pooled': brk_r,
                'held_out': loss_breakdown(g, labels, reg_pred, scenes),
                'confusion_held_out': confusion(labels, reg_pred, ch, np.ones(len(g), bool))},
          CLS: {'training_pooled': brk_c,
                'held_out': loss_breakdown(g, labels, cls['oof_pred'], scenes),
                'confusion_held_out': confusion(labels, cls['oof_pred'], ch, np.ones(len(g), bool))}}

    # ---------------- B-3 ----------------
    train_pred = np.zeros((len(idx_r), 2))
    train_pred[:, 0] = np.concatenate([b['proba'][:, 1] for b in reg['train_blocks']])
    train_pred[:, 1] = np.concatenate([b['proba'][:, 2] for b in reg['train_blocks']])
    b3 = {'held_out': regression_quality(dL, dF, reg['oof'], np.ones(len(g), bool),
                                         'held out, all cells'),
          'held_out_high_reliability': regression_quality(dL, dF, reg['oof'], hi,
                                                          'held out, high-reliability cells'),
          'training_pooled': regression_quality(dL[idx_r], dF[idx_r], train_pred,
                                                np.ones(len(idx_r), bool), 'training, pooled'),
          'discrimination_high_reliability': reg_discrimination(reg['oof'][:, 1], labels, hi),
          'discrimination_all_cells': reg_discrimination(reg['oof'][:, 1], labels,
                                                         np.ones(len(g), bool)),
          'true_gap_high_reliability': {
              'mean_true_dF_where_F_optimal': float(dF[hi & (labels == 'F')].mean()),
              'mean_true_dF_where_L_optimal': float(dF[hi & (labels == 'L')].mean()),
              'difference': float(dF[hi & (labels == 'F')].mean() - dF[hi & (labels == 'L')].mean()),
              'what_it_is': 'the separation that exists in the target itself, which is the ceiling '
                            'the predicted separation beside it is trying to reach'}}

    # ---------------- B-4 ----------------
    b4 = {}
    for lab, m in subsets:
        sc = scenes[m]
        out = {}
        for a, b in ((REG, CLS), (REG, 'channel_rule')):
            d = outcome(g, fo, chosen[a])[0][m] - outcome(g, fo, chosen[b])[0][m]
            per = [{'scene': str(s), 'diff': float(d[sc == s].mean())} for s in np.unique(sc)]
            out[f'{a} - {b}'] = {'bootstrap': boot(d, sc), 'per_scene': per,
                                 'scenes_negative': [x['scene'] for x in per if x['diff'] < 0]}
        b4[lab] = out

    # ---------------- C ----------------
    def cat(b, k):
        return b['categories'].get(k, {}).get('scene_equal_loss', 0.0)
    hr, hc = b2[REG]['held_out'], b2[CLS]['held_out']
    fmiss_r = cat(hr, 'should F, chose L') + cat(hr, 'should F, chose E')
    fmiss_c = cat(hc, 'should F, chose L') + cat(hc, 'should F, chose E')
    top_r = max((v['scene_equal_loss'] for v in hr['categories'].values()), default=0.0)
    top_c = max((v['scene_equal_loss'] for v in hc['categories'].values()), default=0.0)
    d_all = b4['all 22 cells'][f'{REG} - {CLS}']['bootstrap']
    cond = {'held_out_f1_above_classifier': bool(d_all['lcb95'] > 0),
            'F_not_requested_loss_reduced': bool(fmiss_r < fmiss_c),
            'no_new_dominant_error': bool(top_r <= top_c)}
    verdict = ('all three criteria hold: the regression target is an improvement on this input'
               if all(cond.values()) else
               'the criteria are not all met, so this target does not rescue the approach on this '
               'input. ' + C2_CONSEQUENCE)

    return {'schema': 'catosg-p2-rf-round4/1',
            'status': 'DEVELOPMENT VALIDATION ONLY. Nine-fold leave-one-scene-out on validate; no '
                      'held-out-split result and no selection on validate after the folds. test and '
                      'Culver are not opened',
            'the_only_change': 'the learning target: a classifier on the argmax label becomes a '
                               'regressor on the two gains dL = Q_L - Q_E and dF = Q_F - Q_E, from '
                               'the same Q table. Inputs are the 23 of round 1 and nothing else moves',
            'decision_rule': 'max{0, dL_hat, dF_hat}, ties within TOL to the cheaper payload. The zero '
                             'is E\'s own gain, so both-negative falls to E by construction',
            'model_note': 'ONE multi-output forest fits both targets, which keeps one forest per fold '
                          'as in the earlier rounds. Splits therefore reduce the summed variance of '
                          'the two targets and the outputs are coupled. class_weight is dropped '
                          'because it is a classifier-only parameter, not because a new setting was '
                          'wanted; nothing new is introduced',
            'A5_gate': gate, 'hyperparameters': reg['hp'],
            'dropped_hyperparameters': reg['dropped_hyperparameters'],
            'classifier_hyperparameters': cls['hp'],
            'inputs': {'round1_oof': sha(ROUND1_OOF), 'cues': sha(CUES)},
            'row_product': {'path': os.path.relpath(ROWS_GZ, ROOT), 'sha256': sha(ROWS_GZ),
                            'rows': int(len(rows)), 'columns': list(rows.columns)},
            'B1_arms': arms, 'B2_loss': b2, 'B3_regression_quality': b3, 'B4_differences': b4,
            'C1_criteria': C1_CRITERIA, 'C1_conditions': cond, 'C1_verdict': verdict,
            'C1_note': 'the F request share is deliberately not a criterion',
            'C2_consequence': C2_CONSEQUENCE,
            'folds': {REG: reg['folds'], CLS: cls['folds']},
            'command': 'python projects/ca_tosg_p2/protocol/rf_round4.py'}


ARM_ORDER = ('offline_optimum', 'channel_rule', CLS, REG, 'fixed_L', 'fixed_F', 'fixed_E')
CATS = ('should F, chose L', 'should F, chose E', 'should L, chose E', 'should L, chose F',
        'should E, chose L', 'should E, chose F')


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/rf_round4.py -- do not edit by hand -->',
         '# Round 4: regress the gain instead of classifying the label (P2-R19)', '',
         f"**{m['status']}.**", '', f"**The only change.** {cap1(m['the_only_change'])}.", '',
         f"**The decision.** {cap1(m['decision_rule'])}.", '',
         f"**The model.** {cap1(m['model_note'])}. Settings: {m['hyperparameters']}; dropped from the "
         f"classifier's set: {m['dropped_hyperparameters']}.", '',
         '## A-5 That only the target moved', '']
    gt = m['A5_gate']
    L += [f"The classification arm reproduces the stored round-1 product exactly: actions identical "
          f"({gt['actions_identical_to_round1']}), channel-rule actions identical "
          f"({gt['channel_rule_identical']}), largest probability difference "
          f"{gt['max_abs_probability_difference']:.1e}. {cap1(gt['what_this_proves'])}.", '',
          '## B-1 The arms, held out', '']
    for r in m['B1_arms']:
        L += [f"### {r['label']} ({r['rows']:,} rows)", '',
              '| arm | scene-equal F1 | recall | misses / frame | QAM symbols | request E | L | F |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
        for arm in ARM_ORDER:
            v = r['arms'].get(arm)
            if not v:
                continue
            s = v['request_share']
            L.append(f"| `{arm}` | {v['f1']:.5f} | {v['recall']:.5f} | {v['misses_per_frame']:.3f} | "
                     f"{v['qam_symbols']:,.0f} | {s['E'] * 100:.1f} % | {s['L'] * 100:.1f} % | "
                     f"{s['F'] * 100:.1f} % |")
        L.append('')
    L += ['## B-2 The loss, six categories', '',
          '| arm | split | F label recall | agreement | total loss | ' + ' | '.join(CATS) + ' |',
          '|---|---|---:|---:|---:|' + '---:|' * len(CATS)]
    for tag, v in m['B2_loss'].items():
        for key, title in (('training_pooled', 'training'), ('held_out', 'held out')):
            b = v[key]
            cells = [f"{b['categories'].get(c, {}).get('scene_equal_loss', 0.0):+.5f}" for c in CATS]
            L.append(f"| `{tag}` | {title} | "
                     + (f"{b['F_label_recall'] * 100:.1f} %" if b['F_label_recall'] is not None else '—')
                     + f" | {b['agreement_share'] * 100:.1f} % | "
                     f"{b['scene_equal_total_loss']:+.5f} | " + ' | '.join(cells) + ' |')
    L += ['', '### Confusion against a\\*, held out', '']
    for tag, v in m['B2_loss'].items():
        c = v['confusion_held_out']['all']
        L += [f"**`{tag}`** — accuracy {c['accuracy'] * 100:.1f} %", '',
              '| true \\ predicted | E | L | F | recall |', '|---|---:|---:|---:|---:|']
        for a in ACTIONS:
            row = c['matrix_true_by_predicted'][a]
            rec = c['per_action'][a]['recall']
            L.append(f"| **{a}** | {row['E']:,} | {row['L']:,} | {row['F']:,} | "
                     + (f"{rec * 100:.1f} %" if rec is not None else '—') + ' |')
        L.append('')
    b3 = m['B3_regression_quality']
    L += ['## B-3 How well the gains themselves are predicted', '',
          'This is the question underneath the decision: before any action is chosen, does the forest',
          'know how much each message would be worth?', '',
          '| view | rows | corr(dF_hat, dF) | corr(dL_hat, dL) | MAE dF | MAE dL | mean true dF | '
          'mean predicted dF |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for k in ('training_pooled', 'held_out', 'held_out_high_reliability'):
        q = b3[k]
        L.append(f"| {q['label']} | {q['rows']:,} | "
                 + (f"{q['corr_dF']:.4f}" if q['corr_dF'] is not None else '—') + ' | '
                 + (f"{q['corr_dL']:.4f}" if q['corr_dL'] is not None else '—')
                 + f" | {q['mae_dF']:.5f} | {q['mae_dL']:.5f} | {q['mean_true_dF']:+.5f} | "
                 f"{q['mean_pred_dF']:+.5f} |")
    L += ['', '### Bias by how large the true gain is, held out', '',
          '| bin on |dF| | rows | mean true dF | mean predicted dF | mean bias | mean absolute error |',
          '|---|---:|---:|---:|---:|---:|']
    for b in b3['held_out']['bias_by_true_magnitude']:
        L.append(f"| {b['bin']} | {b['rows']:,} | {b['mean_true_dF']:+.5f} | "
                 f"{b['mean_pred_dF']:+.5f} | {b['mean_bias']:+.5f} | {b['mean_abs_error']:.5f} |")
    d, tg = b3['discrimination_high_reliability'], b3['true_gap_high_reliability']
    L += ['', '### Separation on the high-reliability cells, in the regression\'s own units', '']
    if d:
        L += [f"Predicted: mean dF_hat is {d['mean_dF_hat_where_F_optimal']:+.5f} where F is optimal "
              f"and {d['mean_dF_hat_where_L_optimal']:+.5f} where L is, a difference of "
              f"**{d['difference']:+.5f}**.",
              f"In the target itself: {tg['mean_true_dF_where_F_optimal']:+.5f} against "
              f"{tg['mean_true_dF_where_L_optimal']:+.5f}, a difference of **{tg['difference']:+.5f}**. "
              f"{cap1(tg['what_it_is'])}.", '']
    L += ['## B-4 Differences, per scene and bootstrapped', '']
    for lab, v in m['B4_differences'].items():
        L += [f"### {lab}", '', '| difference | scene-equal mean | bootstrap 95 % | scenes negative |',
              '|---|---:|---|---|']
        for k, dd in v.items():
            b = dd['bootstrap']
            L.append(f"| {k} | {b['mean']:+.5f} | [{b['lcb95']:+.5f}, {b['ucb95']:+.5f}] | "
                     f"{len(dd['scenes_negative'])}/9 |")
        L.append('')
    L += ['## C The criteria, fixed before the run', '',
          f"{cap1(m['C1_note'])}.", '', '| criterion | as defined | holds |', '|---|---|:---:|']
    for k, v in m['C1_conditions'].items():
        L.append(f"| `{k}` | {m['C1_criteria'][k]} | {'yes' if v else 'no'} |")
    L += ['', f"**{cap1(m['C1_verdict'])}.**", '', '## Products', '',
          f"`{m['row_product']['path']}` — {m['row_product']['rows']:,} rows, held-out and training, "
          'with the predicted and true gains beside the action taken. Its sha256 is recorded and '
          '`--check` verifies it.', '', '## Inputs', '', '| file | sha256 |', '|---|---|']
    for k, v in m['inputs'].items():
        L.append(f"| {k} | `{v[:16]}…` |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--rerender', action='store_true')
    ap.add_argument('--jobs', type=int, default=-1)
    a = ap.parse_args()

    if a.rerender:
        m = json.load(open(OUT_JSON))
        open(OUT_MD, 'w').write(markdown(m))
        print('rf round4: markdown rewritten from the stored record (no retraining)')
        return 0

    if a.check and not a.full:
        if not os.path.exists(OUT_JSON):
            print('rf round4: FAIL -- no stored record'); return 1
        m = json.load(open(OUT_JSON))
        md_ok = os.path.exists(OUT_MD) and open(OUT_MD).read() == markdown(m)
        have = os.path.exists(ROWS_GZ)
        prod_ok = have and sha(ROWS_GZ) == m['row_product']['sha256']
        print('rf round4:', 'document matches the record' if md_ok else 'FAIL -- document differs')
        print('  per-row product:', 'hash matches the record' if prod_ok
              else ('FAIL -- missing' if not have else 'FAIL -- hash differs'))
        print('  (the record itself is not re-derived at this level; use --check --full)')
        return 0 if (md_ok and prod_ok) else 1

    m = build(a.jobs)
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        stored = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
        diffs = json_diff(strip_volatile(stored), strip_volatile(m))
        md_ok = os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print(f'rf round4: comparison excludes {VOLATILE_FIELDS} -- wall-clock')
        if diffs:
            print(f'  FAIL -- differs at {len(diffs)} path(s):')
            for d in diffs[:20]:
                print('   ', d)
        if not md_ok:
            print('  FAIL -- the document is not what the generator writes')
        if not diffs and md_ok:
            print('  reproduced end to end (everything but the timing fields)')
            return 0
        return 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
