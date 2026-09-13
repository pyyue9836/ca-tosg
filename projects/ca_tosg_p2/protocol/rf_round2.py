#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R17 — round 2: the same forest with max_depth 8, and the training-set view round 1 lacked.

**One thing changes: max_depth None -> 8.** Trees, minimum leaf, class weight, the 23 inputs, the
message-accounted labels, the cheaper-payload tie rule, the original 22-cell grid, the nine
scene-level folds, the per-fold tau fit and the seed are all read from the same places round 1 read
them from. No other depth is tried.

Depth 8 is a **pre-selected diagnostic setting**. It is not claimed to be optimal and it is not
expected to beat the channel-only rule; it exists to separate "the forest overfits the F/L boundary"
from "the inputs cannot express the benefit".

Round 1 is re-run here rather than quoted, because its training-set predictions were never saved. The
re-run is held to the stored round-1 product row by row, so "everything else unchanged" is verified
rather than asserted.

  B-1  every fold saves its training-scene and held-out predictions and probabilities
  B-2  the training set is read the same way the held-out set is: confusion against a*, F recall, and
       the same loss decomposition -- so "did it pick the same frames in sample" is answered, not just
       "what share did it request"
  C    round 1, round 2 and the channel rule side by side; training against held out; the P(F)
       discrimination on the high-reliability cells; per-scene differences with bootstrap intervals
  D    the reading rule, fixed in code before the run

    python rf_round2.py [--check] [--jobs N]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
ROUND1_JSON = os.path.join(HERE, 'rf_round1.json')
ROUND1_OOF = os.path.join(P2, 'results', 'rf', 'rf_round1_oof.csv')
ROWS_GZ = os.path.join(P2, 'results', 'rf', 'rf_round2_rows.csv.gz')
OUT_JSON = os.path.join(HERE, 'rf_round2.json')
OUT_MD = os.path.join(HERE, 'rf_round2.md')

sys.path.insert(0, HERE)
from offline_potential import build_table, scene_equal, boot, ACTIONS, TOL      # noqa: E402
from rf_round1 import (frame_outcomes, features, hyperparameters, outcome,      # noqa: E402
                       fit_tau, apply_tau, evaluate, confusion, CUES, CUE_META,
                       VOLATILE_FIELDS, strip_volatile, json_diff)

ROUNDS = [('round1_depth_None', None), ('round2_depth_8', 8)]
HI_CELLS = [('awgn', s) for s in (10, 12, 14, 16, 18, 20)]

# D: fixed here, before the run, so the reading cannot be chosen after seeing the numbers.
D_RULES = {
    'held_out_improvement_is_material': 'the bootstrap interval of (round 2 - round 1) held-out '
                                        'scene-equal F1 lies entirely above zero',
    'training_cost_is_slight': 'the scene-equal training loss rises at all under depth 8',
    'still_no_discrimination': 'P(F | F optimal) - P(F | L optimal) on the high-reliability AWGN '
                               'cells stays at or below 0.05 out of fold',
    'dominant_loss_unchanged': 'the largest single loss category out of fold is still '
                               '"should F, chose L"',
    'D1': 'training slightly worse and held-out materially better -> the overfitting explanation is '
          'supported',
    'D2': 'training and held-out both worse -> depth 8 is too strong a constraint. This is NOT '
          'evidence against the task cues and must not be read as such',
    'D3': 'no discrimination out of fold and the dominant loss unchanged -> stop sweeping parameters '
          'and turn to whether the inputs can express the collaboration benefit at all',
}
DISCRIMINATION_FLOOR = 0.05


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


class FO:
    """The per-frame recall and miss arrays, sliced to a row subset."""

    def __init__(self, src, idx=None):
        for a in ACTIONS:
            for k in ('recall', 'miss'):
                v = getattr(src, f'{k}_{a}')
                setattr(self, f'{k}_{a}', v if idx is None else v[idx])


def load_frame_outcomes(g):
    fo_df, tp_dev = frame_outcomes()
    fo_df = fo_df.set_index('frame').loc[g.sample_id.to_numpy()]

    class Src:
        pass
    src = Src()
    for a in ACTIONS:
        setattr(src, f'recall_{a}', fo_df[f'recall_{a}'].to_numpy())
        setattr(src, f'miss_{a}', fo_df[f'miss_{a}'].to_numpy())
    return FO(src), tp_dev


def loss_breakdown(g, labels, pred, scenes):
    """The C-2 decomposition, on whatever row subset is handed in."""
    q = np.stack([g.Q_E.to_numpy(), g.Q_L.to_numpy(), g.Q_F.to_numpy()], axis=1)
    Qs = np.choose([ACTIONS.index(a) for a in labels], q.T)
    Qp = np.choose([ACTIONS.index(a) for a in pred], q.T)
    loss = Qs - Qp
    if float(loss.min()) < -TOL - 1e-12:
        raise SystemExit('the forest beats the labelled optimum beyond the tie slack')
    total = scene_equal(loss, scenes)
    cats = {}
    for star in ACTIONS:
        for p in ACTIONS:
            if star == p:
                continue
            m = (labels == star) & (pred == p)
            if not m.any():
                continue
            cats[f'should {star}, chose {p}'] = {
                'rows': int(m.sum()), 'scene_equal_loss': scene_equal(loss * m, scenes),
                'mean_loss_per_row': float(loss[m].mean())}
    return {'scene_equal_total_loss': total,
            'categories': dict(sorted(cats.items(), key=lambda kv: -kv[1]['scene_equal_loss'])),
            'F_label_recall': (float((pred[labels == 'F'] == 'F').mean())
                               if (labels == 'F').any() else None),
            'F_request_share_scene_equal': scene_equal((pred == 'F').astype(float), scenes),
            'agreement_share': float((labels == pred).mean())}


def discrimination(proba, labels, mask):
    """P(F | F optimal) - P(F | L optimal) on a row subset. Flat or inverted means no signal."""
    pf = proba[:, 2]
    mF, mL = mask & (labels == 'F'), mask & (labels == 'L')
    if not mF.any() or not mL.any():
        return None
    return {'mean_p_F_where_F_optimal': float(pf[mF].mean()),
            'mean_p_F_where_L_optimal': float(pf[mL].mean()),
            'difference': float(pf[mF].mean() - pf[mL].mean()),
            'rows_F': int(mF.sum()), 'rows_L': int(mL.sum())}


def run_round(g, cues, cue_fields, labels, jobs, max_depth, tag):
    """One LOSO pass at one depth, keeping the training-scene predictions as well as the held-out ones."""
    from sklearn.ensemble import RandomForestClassifier
    X, names = features(g, cues, cue_fields)
    scenes = g.scene.to_numpy()
    frames = g.sample_id.to_numpy()
    hp = dict(hyperparameters())
    hp['max_depth'] = max_depth

    oof_pred = np.empty(len(g), object)
    oof_proba = np.full((len(g), len(ACTIONS)), np.nan)
    rule_pred = np.empty(len(g), object)
    train_blocks, folds = [], []
    for s in np.unique(scenes):
        te = scenes == s
        tr = ~te
        if set(np.unique(frames[tr])) & set(np.unique(frames[te])):
            raise SystemExit(f'fold {s}: a frame appears on both sides of the split')
        t0 = time.time()
        rf = RandomForestClassifier(n_jobs=jobs, **hp).fit(X[tr], labels[tr])
        cls = list(rf.classes_)

        def proba_of(mat):
            pr = rf.predict_proba(mat)
            out = np.zeros((len(mat), len(ACTIONS)))
            for j, act in enumerate(ACTIONS):
                if act in cls:
                    out[:, j] = pr[:, cls.index(act)]
            return out

        oof_pred[te] = rf.predict(X[te])
        oof_proba[te] = proba_of(X[te])
        tr_pred = rf.predict(X[tr])
        tr_proba = proba_of(X[tr])
        tau = fit_tau(g, tr)
        rule_pred[te] = apply_tau(g[te], tau)

        idx = np.where(tr)[0]
        train_blocks.append({'scene_held_out': str(s), 'idx': idx, 'pred': tr_pred,
                             'proba': tr_proba})
        gb = g.iloc[idx]
        folds.append({
            'held_out_scene': str(s), 'train_rows': int(tr.sum()), 'test_rows': int(te.sum()),
            'tau_from_training_scenes': tau,
            'train': loss_breakdown(gb, labels[idx], tr_pred, scenes[idx]),
            'held_out': loss_breakdown(g[te], labels[te], oof_pred[te], scenes[te]),
            'seconds': time.time() - t0})
        print(f'  [{tag}] fold {s}: train F recall '
              f'{folds[-1]["train"]["F_label_recall"]:.3f}, held-out F recall '
              f'{folds[-1]["held_out"]["F_label_recall"]:.3f} ({time.time() - t0:.1f}s)', flush=True)
    return {'hp': hp, 'names': names, 'oof_pred': oof_pred, 'oof_proba': oof_proba,
            'rule_pred': rule_pred, 'train_blocks': train_blocks, 'folds': folds}


def pooled_train(g, labels, scenes, blocks):
    """B-2: the training view, pooled over folds. A row is a (fold, row) pair, since a scene is a
    training scene in eight of the nine folds."""
    idx = np.concatenate([b['idx'] for b in blocks])
    pred = np.concatenate([b['pred'] for b in blocks])
    proba = np.vstack([b['proba'] for b in blocks])
    return idx, pred, proba, loss_breakdown(g.iloc[idx], labels[idx], pred, scenes[idx])


def mean_over_folds(folds, split, path):
    vals = []
    for f in folds:
        v = f[split]
        for k in path:
            v = v[k] if isinstance(v, dict) else None
            if v is None:
                break
        if v is not None:
            vals.append(v)
    return float(np.mean(vals)) if vals else None


def build(jobs=-1):
    g, n_cw_F, B_F_sym = build_table()
    fo, tp_dev = load_frame_outcomes(g)
    cues = pd.read_csv(CUES)
    cue_fields = list(json.load(open(CUE_META))['perception_fields'])
    labels = g.a_star.to_numpy().astype(object)
    scenes = g.scene.to_numpy()
    ch = g.channel.to_numpy()

    results = {}
    for name, depth in ROUNDS:
        print(f'{name} (max_depth={depth})', flush=True)
        results[name] = run_round(g, cues, cue_fields, labels, jobs, depth, name)

    # "everything else unchanged" is checked, not claimed: the re-run of round 1 must reproduce the
    # stored per-row product exactly.
    stored = pd.read_csv(ROUND1_OOF)
    r1 = results['round1_depth_None']
    same_pred = bool((stored.pred_joint.to_numpy() == r1['oof_pred']).all())
    same_rule = bool((stored.pred_channel_rule.to_numpy() == r1['rule_pred']).all())
    max_dp = float(np.abs(stored[['p_E', 'p_L', 'p_F']].to_numpy() - r1['oof_proba']).max())
    if not (same_pred and same_rule) or max_dp > 1e-12:
        raise SystemExit(f'the re-run of round 1 does not reproduce the stored product '
                         f'(actions match: {same_pred}/{same_rule}, max |dp| {max_dp:g}) -- '
                         'the configuration is not the one that produced it')
    reproduction = {'round1_oof_actions_identical': same_pred,
                    'round1_channel_rule_identical': same_rule,
                    'round1_max_abs_probability_difference': max_dp,
                    'what_this_proves': 'the only difference between the two rounds below is '
                                        'max_depth; every other input, split, seed and rule is the '
                                        'one that produced the stored round-1 record'}

    # ---------------- B-1: the per-row product, both rounds, both splits ----------------
    frames = []
    for name, _ in ROUNDS:
        r = results[name]
        frames.append(pd.DataFrame({
            'round': name, 'fold': 'held_out', 'split': 'held_out',
            'sample_id': g.sample_id.to_numpy(), 'scene': scenes, 'snr_db': g.snr_db.to_numpy(),
            'channel': ch, 'a_star': labels, 'pred': r['oof_pred'],
            'p_E': r['oof_proba'][:, 0], 'p_L': r['oof_proba'][:, 1], 'p_F': r['oof_proba'][:, 2]}))
        for b in r['train_blocks']:
            i = b['idx']
            frames.append(pd.DataFrame({
                'round': name, 'fold': b['scene_held_out'], 'split': 'training',
                'sample_id': g.sample_id.to_numpy()[i], 'scene': scenes[i],
                'snr_db': g.snr_db.to_numpy()[i], 'channel': ch[i], 'a_star': labels[i],
                'pred': b['pred'], 'p_E': b['proba'][:, 0], 'p_L': b['proba'][:, 1],
                'p_F': b['proba'][:, 2]}))
    rows = pd.concat(frames, ignore_index=True)
    os.makedirs(os.path.dirname(ROWS_GZ), exist_ok=True)
    rows.to_csv(ROWS_GZ, index=False, compression={'method': 'gzip', 'mtime': 0})

    # ---------------- C-1: the arms ----------------
    chosen = {'round1_RF': results['round1_depth_None']['oof_pred'],
              'round2_RF_depth8': results['round2_depth_8']['oof_pred'],
              'channel_rule': results['round1_depth_None']['rule_pred'],
              'offline_optimum': labels,
              'fixed_E': np.full(len(g), 'E', object),
              'fixed_L': np.full(len(g), 'L', object),
              'fixed_F': np.full(len(g), 'F', object)}
    hi = np.zeros(len(g), bool)
    for c, s in HI_CELLS:
        hi |= ((g.channel == c) & (g.snr_db == s)).to_numpy()
    subsets = [('all 22 cells', np.ones(len(g), bool)), ('AWGN only', ch == 'awgn'),
               ('Rayleigh only', ch == 'rayleigh'), ('high-reliability AWGN cells', hi)]
    arms = [evaluate(g, fo, chosen, m, lab) for lab, m in subsets]

    # ---------------- C-2: training against held out ----------------
    train_pool = {}
    for name, _ in ROUNDS:
        r = results[name]
        idx, pred, proba, brk = pooled_train(g, labels, scenes, r['train_blocks'])
        train_pool[name] = {'idx': idx, 'pred': pred, 'proba': proba, 'breakdown': brk}
    c2 = {}
    for name, _ in ROUNDS:
        r, tp = results[name], train_pool[name]
        oof = loss_breakdown(g, labels, r['oof_pred'], scenes)
        def cat(b, k):
            return b['categories'].get(k, {}).get('scene_equal_loss', 0.0)
        c2[name] = {
            'training_pooled': {'F_label_recall': tp['breakdown']['F_label_recall'],
                                'total_loss': tp['breakdown']['scene_equal_total_loss'],
                                'loss_should_F_chose_L': cat(tp['breakdown'], 'should F, chose L'),
                                'loss_should_F_chose_E': cat(tp['breakdown'], 'should F, chose E'),
                                'F_request_share': tp['breakdown']['F_request_share_scene_equal'],
                                'agreement_share': tp['breakdown']['agreement_share']},
            'held_out': {'F_label_recall': oof['F_label_recall'],
                         'total_loss': oof['scene_equal_total_loss'],
                         'loss_should_F_chose_L': cat(oof, 'should F, chose L'),
                         'loss_should_F_chose_E': cat(oof, 'should F, chose E'),
                         'F_request_share': oof['F_request_share_scene_equal'],
                         'agreement_share': oof['agreement_share']},
            'held_out_breakdown': oof,
            'training_breakdown': tp['breakdown'],
            'mean_over_folds': {
                'train_F_recall': mean_over_folds(r['folds'], 'train', ['F_label_recall']),
                'held_out_F_recall': mean_over_folds(r['folds'], 'held_out', ['F_label_recall'])},
            'confusion_training_pooled': confusion(labels[tp['idx']], tp['pred'],
                                                   ch[tp['idx']], np.ones(len(tp['idx']), bool)),
            'confusion_held_out': confusion(labels, r['oof_pred'], ch, np.ones(len(g), bool))}

    # ---------------- C-3: discrimination on the high-reliability cells ----------------
    c3 = {}
    for name, _ in ROUNDS:
        r, tp = results[name], train_pool[name]
        hi_tr = hi[tp['idx']]
        c3[name] = {'held_out': discrimination(r['oof_proba'], labels, hi),
                    'training_pooled': discrimination(tp['proba'], labels[tp['idx']], hi_tr),
                    'held_out_all_cells': discrimination(r['oof_proba'], labels,
                                                         np.ones(len(g), bool))}

    # ---------------- C-4: per-scene differences ----------------
    c4 = {}
    for lab, m in subsets:
        sc = scenes[m]
        out = {}
        for a, b in (('round2_RF_depth8', 'channel_rule'), ('round2_RF_depth8', 'round1_RF')):
            Qa = outcome(g, fo, chosen[a])[0][m]
            Qb = outcome(g, fo, chosen[b])[0][m]
            d = Qa - Qb
            per = [{'scene': str(s), 'diff': float(d[sc == s].mean())} for s in np.unique(sc)]
            out[f'{a} - {b}'] = {'bootstrap': boot(d, sc), 'per_scene': per,
                                 'scenes_negative': [x['scene'] for x in per if x['diff'] < 0]}
        c4[lab] = out

    # ---------------- D: the reading, by the rule fixed above ----------------
    d_all = c4['all 22 cells']['round2_RF_depth8 - round1_RF']['bootstrap']
    tl1 = c2['round1_depth_None']['training_pooled']['total_loss']
    tl2 = c2['round2_depth_8']['training_pooled']['total_loss']
    ol1 = c2['round1_depth_None']['held_out']['total_loss']
    ol2 = c2['round2_depth_8']['held_out']['total_loss']
    disc2 = c3['round2_depth_8']['held_out']
    top2 = next(iter(c2['round2_depth_8']['held_out_breakdown']['categories']), None)
    cond = {'held_out_improvement_is_material': bool(d_all['lcb95'] > 0),
            'training_cost_is_slight': bool(tl2 > tl1),
            'training_also_worse': bool(tl2 > tl1),
            'held_out_also_worse': bool(ol2 > ol1),
            'still_no_discrimination': bool(disc2 is not None
                                            and disc2['difference'] <= DISCRIMINATION_FLOOR),
            'dominant_loss_unchanged': bool(top2 == 'should F, chose L')}
    verdicts = []
    if cond['training_cost_is_slight'] and cond['held_out_improvement_is_material']:
        verdicts.append(('D1', D_RULES['D1']))
    if cond['training_also_worse'] and cond['held_out_also_worse']:
        verdicts.append(('D2', D_RULES['D2']))
    if cond['still_no_discrimination'] and cond['dominant_loss_unchanged']:
        verdicts.append(('D3', D_RULES['D3']))

    return {'schema': 'catosg-p2-rf-round2/1',
            'status': 'DEVELOPMENT VALIDATION ONLY. Nine-fold leave-one-scene-out on validate; no '
                      'held-out-split result, no selection on validate after the folds. test and '
                      'Culver are not opened',
            'the_only_change': 'max_depth None -> 8. Trees, minimum leaf, class weight, inputs, '
                               'labels, tie rule, grid, folds, per-fold tau fit and seed are '
                               'unchanged, and the reproduction check below proves it',
            'depth_8_status': 'a PRE-SELECTED DIAGNOSTIC SETTING. No other depth was tried, it is not '
                              'claimed to be optimal, and it is not expected to beat the channel rule',
            'reproduction_of_round1': reproduction,
            'hyperparameters': {name: results[name]['hp'] for name, _ in ROUNDS},
            'inputs': {'round1_json': sha(ROUND1_JSON), 'round1_oof': sha(ROUND1_OOF),
                       'cues': sha(CUES)},
            'row_product': {'path': os.path.relpath(ROWS_GZ, ROOT), 'sha256': sha(ROWS_GZ),
                            'rows': int(len(rows)), 'columns': list(rows.columns),
                            'what': 'every fold of both rounds, training rows and held-out rows, with '
                                    'the action taken and the three class probabilities. A training '
                                    'row appears once per fold in which its scene was a training '
                                    'scene, which is eight of the nine'},
            'recall_derivation_max_deviation': tp_dev,
            'C1_arms': arms, 'C2_train_vs_held_out': c2, 'C3_discrimination': c3,
            'C4_differences': c4,
            'D_rules_fixed_before_the_run': D_RULES,
            'D_discrimination_floor': DISCRIMINATION_FLOOR,
            'D_conditions': cond, 'D_verdicts': [{'rule': k, 'reading': v} for k, v in verdicts],
            'folds': {name: results[name]['folds'] for name, _ in ROUNDS},
            'command': 'python projects/ca_tosg_p2/protocol/rf_round2.py'}


def cap1(t):
    return t[:1].upper() + t[1:]


ARM_ORDER = ('offline_optimum', 'channel_rule', 'round1_RF', 'round2_RF_depth8', 'fixed_L',
             'fixed_F', 'fixed_E')


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/rf_round2.py -- do not edit by hand -->',
         '# Round 2: the same forest at max_depth 8 (P2-R17)', '',
         f"**{m['status']}.**", '', f"**The only change.** {cap1(m['the_only_change'])}.", '',
         f"**What depth 8 is.** {cap1(m['depth_8_status'])}.", '',
         '## That nothing else moved', '']
    rp = m['reproduction_of_round1']
    L += [f"Re-running round 1 here reproduces the stored per-row product exactly: actions identical "
          f"({rp['round1_oof_actions_identical']}), channel-rule actions identical "
          f"({rp['round1_channel_rule_identical']}), largest probability difference "
          f"{rp['round1_max_abs_probability_difference']:.1e}. {cap1(rp['what_this_proves'])}.", '',
          '| round | max_depth | n_estimators | min_samples_leaf | max_features | class_weight | seed |',
          '|---|---|---:|---:|---|---|---:|']
    for name, hp in m['hyperparameters'].items():
        L.append(f"| `{name}` | {hp['max_depth']} | {hp['n_estimators']} | "
                 f"{hp['min_samples_leaf']} | {hp['max_features']} | {hp['class_weight']} | "
                 f"{hp['random_state']} |")
    L += ['', '## C-1 The arms, held out', '']
    for r in m['C1_arms']:
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
    L += ['## C-2 Training against held out', '',
          'A training row is a (fold, row) pair: a scene is a training scene in eight of the nine',
          'folds, so the pooled training view has eight times the rows of the held-out view. The',
          'question it answers is whether the forest picks the **same frames** in sample, not merely',
          'whether it requests F as often.', '',
          '| round | split | F label recall | F request share | agreement with a\\* | total loss | '
          'loss: should F chose L | loss: should F chose E |', '|---|---|---:|---:|---:|---:|---:|---:|']
    for name, v in m['C2_train_vs_held_out'].items():
        for split in ('training_pooled', 'held_out'):
            s = v[split]
            L.append(f"| `{name}` | {split.replace('_', ' ')} | "
                     + (f"{s['F_label_recall'] * 100:.1f} %" if s['F_label_recall'] is not None else '—')
                     + f" | {s['F_request_share'] * 100:.1f} % | {s['agreement_share'] * 100:.1f} % | "
                     f"{s['total_loss']:+.5f} | {s['loss_should_F_chose_L']:+.5f} | "
                     f"{s['loss_should_F_chose_E']:+.5f} |")
    L += ['', '### Confusion against a\\*, pooled', '']
    for name, v in m['C2_train_vs_held_out'].items():
        for key, title in (('confusion_training_pooled', 'training'), ('confusion_held_out', 'held out')):
            c = v[key]['all']
            L += [f"**`{name}`, {title}** — accuracy {c['accuracy'] * 100:.1f} %", '',
                  '| true \\ predicted | E | L | F | recall |', '|---|---:|---:|---:|---:|']
            for a in ACTIONS:
                row = c['matrix_true_by_predicted'][a]
                rec = c['per_action'][a]['recall']
                L.append(f"| **{a}** | {row['E']:,} | {row['L']:,} | {row['F']:,} | "
                         + (f"{rec * 100:.1f} %" if rec is not None else '—') + ' |')
            L.append('')
    L += ['## C-3 Does P(F) separate F from L on the high-reliability cells', '',
          'The difference is mean P(F) where F is optimal minus mean P(F) where L is. Zero or negative',
          'means the probability carries no signal about F, whatever the request share looks like.', '',
          '| round | split / subset | P(F) where F optimal | where L optimal | difference |',
          '|---|---|---:|---:|---:|']
    for name, v in m['C3_discrimination'].items():
        for key, title in (('training_pooled', 'training, high-reliability cells'),
                           ('held_out', 'held out, high-reliability cells'),
                           ('held_out_all_cells', 'held out, all cells')):
            d = v.get(key)
            if not d:
                continue
            L.append(f"| `{name}` | {title} | {d['mean_p_F_where_F_optimal']:.4f} | "
                     f"{d['mean_p_F_where_L_optimal']:.4f} | {d['difference']:+.4f} |")
    L += ['', '## C-4 Differences, per scene and bootstrapped', '']
    for lab, v in m['C4_differences'].items():
        L += [f"### {lab}", '', '| difference | scene-equal mean | bootstrap 95 % | scenes negative |',
              '|---|---:|---|---|']
        for k, d in v.items():
            b = d['bootstrap']
            L.append(f"| {k} | {b['mean']:+.5f} | [{b['lcb95']:+.5f}, {b['ucb95']:+.5f}] | "
                     f"{len(d['scenes_negative'])}/9 |")
        L.append('')
    L += ['## D The reading, by the rule fixed before the run', '',
          '| condition | as defined | holds |', '|---|---|:---:|']
    for k, v in m['D_conditions'].items():
        desc = m['D_rules_fixed_before_the_run'].get(k, '—')
        L.append(f"| `{k}` | {desc} | {'yes' if v else 'no'} |")
    L += ['', f"The discrimination floor was fixed at {m['D_discrimination_floor']}.", '']
    if m['D_verdicts']:
        for d in m['D_verdicts']:
            L.append(f"* **{d['rule']}** — {d['reading']}.")
    else:
        L.append('* **No pre-registered rule fires.** The conditions above are reported as they are '
                 'and no reading is substituted after the fact.')
    L += ['', '## Products', '',
          f"`{m['row_product']['path']}` — {m['row_product']['rows']:,} rows. "
          f"{cap1(m['row_product']['what'])}. Its sha256 is recorded and `--check` verifies it.", '',
          '## Inputs', '', '| file | sha256 |', '|---|---|']
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
        print('rf round2: markdown rewritten from the stored record (no retraining)')
        return 0

    if a.check and not a.full:
        if not os.path.exists(OUT_JSON):
            print('rf round2: FAIL -- no stored record'); return 1
        m = json.load(open(OUT_JSON))
        md_ok = os.path.exists(OUT_MD) and open(OUT_MD).read() == markdown(m)
        have = os.path.exists(ROWS_GZ)
        prod_ok = have and sha(ROWS_GZ) == m['row_product']['sha256']
        print('rf round2:', 'document matches the record' if md_ok else 'FAIL -- document differs')
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
        print(f'rf round2: comparison excludes {VOLATILE_FIELDS} -- wall-clock')
        if diffs:
            print(f'  FAIL -- the re-derived record differs at {len(diffs)} path(s):')
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
