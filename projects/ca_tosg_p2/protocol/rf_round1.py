#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R15 C — first training round: a random forest that classifies the per-frame optimal action.

CPU only. No perception inference is run: the forest predicts which of E, L and F to request, and the
consequence of that request is looked up in the frozen per-frame outcomes under the locked
all-or-nothing message accounting.

**Development validation only (D-2).** Every number here is leave-one-scene-out on validate. Nothing
is selected on validate after the LOSO finishes, and no held-out result is produced. `test` and
Culver are not opened.

  C-1  input: 21 ego-local cues + est_snr_db + channel_is_rayleigh
  C-2  label: a* = argmax {Q_E, Q_L, Q_F}, ties to the cheaper payload, TOL 1e-9, per frame per cell
  C-3  hyperparameters are P1's frozen selector settings, read from the freeze manifest, not retyped
       and not tuned here. The lambda objective is not used and candidate 67's weights are not loaded
  C-4  scene-level 9-fold LOSO, with a gate asserting all 22 channel versions of a frame stay together
  C-5  arms: joint RF, channel-only tau rule (tau fitted on training scenes only), task-only RF,
       Fixed E/L/F, and the offline optimum
  C-6  scene-equal F1, recall and misses, request shares, QAM symbols, per-scene differences with
       scene-level bootstrap, and the RF's F share beside the offline reference
  C-7  stability: relabel with p_cw_upper95 instead of the point estimate and report what moves
  C-8  confusion matrix against a*, per channel type

    python rf_round1.py [--check] [--jobs N]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
V2 = os.path.join(ROOT, 'results', 'v2')
CUES = os.path.join(V2, 'wp6_cues_validate.csv')
CUE_META = os.path.join(V2, 'wp6_cues_validate.json')
WP5 = os.path.join(V2, 'wp5_final_validate.csv')
WP34 = os.path.join(V2, 'wp34_e_l_validate.csv')
BLER = os.path.join(ROOT, 'results', 'channel', 'bler_sionna.csv')
FREEZE = os.path.join(ROOT, 'results', 'manifests', 'V2_PRIMARY_FREEZE.json')
POTENTIAL = os.path.join(HERE, 'offline_potential.json')
OOF_CSV = os.path.join(P2, 'results', 'rf', 'rf_round1_oof.csv')
OUT_JSON = os.path.join(HERE, 'rf_round1.json')
OUT_MD = os.path.join(HERE, 'rf_round1.md')

sys.path.insert(0, HERE)
from offline_potential import build_table, scene_equal, boot, ACTIONS, TOL   # noqa: E402
from awgn_fill import cp_upper                                                # noqa: E402

TAU_STEP = 0.5
SEED = 0

# Fields that cannot reproduce byte for byte because they measure the run rather than describe the
# result. They are kept in the record because the cost is worth reporting, and excluded from the
# end-to-end comparison -- with the exclusion printed, not left implicit.
VOLATILE_FIELDS = ('seconds',)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def strip_volatile(o):
    if isinstance(o, dict):
        return {k: strip_volatile(v) for k, v in o.items() if k not in VOLATILE_FIELDS}
    if isinstance(o, list):
        return [strip_volatile(v) for v in o]
    return o


def json_diff(stored, fresh, path=''):
    """Every path at which the re-derived record differs from the stored one."""
    out = []
    if isinstance(stored, dict) and isinstance(fresh, dict):
        for k in sorted(set(stored) | set(fresh)):
            if k not in stored:
                out.append(f'{path}/{k}: only in the re-derived record')
            elif k not in fresh:
                out.append(f'{path}/{k}: only in the stored record')
            else:
                out += json_diff(stored[k], fresh[k], f'{path}/{k}')
    elif isinstance(stored, list) and isinstance(fresh, list):
        if len(stored) != len(fresh):
            out.append(f'{path}: {len(stored)} entries stored, {len(fresh)} re-derived')
        else:
            for i, (x, y) in enumerate(zip(stored, fresh)):
                out += json_diff(x, y, f'{path}[{i}]')
    elif stored != fresh:
        out.append(f'{path}: stored {stored!r} vs re-derived {fresh!r}')
    return out


# ------------------------------------------------------------ per-frame outcomes
def frame_outcomes():
    """Recall and misses per frame per action, derived and then verified against integrality.

    The scorer stores F1 and box counts but not TP. For a one-to-one matching
    F1 = 2 TP / (P + G), so TP = F1 (P + G) / 2 -- which is only a valid inversion if it lands on an
    integer for every frame. That is checked here rather than assumed; if the matching were not
    one-to-one the check would fail and no recall would be reported.
    """
    w5 = pd.read_csv(WP5, usecols=['frame', 'n_box_clean', 'f1_clean', 'f1_ego'])
    w34 = pd.read_csv(WP34, usecols=['frame', 'n_gt', 'n_box_ego', 'n_box_L', 'f1_E', 'f1_L'])
    d = w34.merge(w5, on='frame')
    if float(np.abs(d.f1_E - d.f1_ego).max()) > 0:
        raise SystemExit('wp34 f1_E and wp5 f1_ego disagree -- the two products describe different runs')
    if int((d.n_gt <= 0).sum()):
        raise SystemExit('a frame has no ground-truth object; recall would be undefined')
    out = {'frame': d.frame.to_numpy(), 'n_gt': d.n_gt.to_numpy(float)}
    worst = 0.0
    for a, f1, npred in (('E', d.f1_E, d.n_box_ego), ('L', d.f1_L, d.n_box_L),
                         ('F', d.f1_clean, d.n_box_clean)):
        tp = f1.to_numpy() * (npred.to_numpy() + d.n_gt.to_numpy()) / 2.0
        worst = max(worst, float(np.abs(tp - np.round(tp)).max()))
        out[f'tp_{a}'] = np.round(tp)
        out[f'recall_{a}'] = np.round(tp) / d.n_gt.to_numpy()
        out[f'miss_{a}'] = d.n_gt.to_numpy() - np.round(tp)
    if worst > 1e-6:
        raise SystemExit(f'TP from F1 and box counts is not integral (max deviation {worst:g}); '
                         'recall cannot be derived from these products and must not be reported')
    return pd.DataFrame(out), worst


# ------------------------------------------------------------------- features
def features(g, cues, cue_fields):
    """C-1: the 21 ego-local cues joined to each row, plus the two channel fields."""
    c = cues.set_index('frame').loc[g.sample_id.to_numpy()]
    X = c[cue_fields].to_numpy(float)
    est_snr = g.snr_db.to_numpy(float)[:, None]
    is_ray = (g.channel.to_numpy() == 'rayleigh').astype(float)[:, None]
    return np.hstack([X, est_snr, is_ray]), cue_fields + ['est_snr_db', 'channel_is_rayleigh']


def hyperparameters():
    """C-3: P1's frozen selector settings, read from the manifest rather than typed here."""
    hp = json.load(open(FREEZE))['selector']['hyperparameters']
    return {'n_estimators': hp['n_estimators'], 'max_depth': hp['max_depth'],
            'min_samples_leaf': hp['min_samples_leaf'], 'max_features': hp['max_features'],
            'class_weight': hp['class_weight'], 'random_state': SEED}


# ------------------------------------------------------------------- the arms
def outcome(g, fo, chosen):
    """What a per-row action choice yields under the locked accounting.

    A message either decodes whole or the frame falls back to E, so the expected recall and the
    expected miss count mix the action's own value with E's at the same probability the F1 does.
    Payload is charged for the attempt whatever happens.
    """
    idx = {a: (chosen == a) for a in ACTIONS}
    q = np.where(idx['F'], g.q_F.to_numpy(), np.where(idx['L'], g.q_L.to_numpy(), 1.0))
    Q = np.where(idx['E'], g.Q_E.to_numpy(), np.where(idx['L'], g.Q_L.to_numpy(), g.Q_F.to_numpy()))
    rec_a = np.where(idx['F'], fo.recall_F, np.where(idx['L'], fo.recall_L, fo.recall_E))
    mis_a = np.where(idx['F'], fo.miss_F, np.where(idx['L'], fo.miss_L, fo.miss_E))
    rec = q * rec_a + (1 - q) * fo.recall_E
    mis = q * mis_a + (1 - q) * fo.miss_E
    pay = np.where(idx['F'], g.B_F_sym.to_numpy(), np.where(idx['L'], g.B_L_sym.to_numpy(), 0.0))
    return Q, rec, mis, pay


def fit_tau(g, mask):
    """C-5: the channel-only rule, with tau chosen on TRAINING scenes only, per channel type."""
    t = g[mask]
    snr = t.snr_db.to_numpy(float)
    sc = t.scene.to_numpy()
    ch = t.channel.to_numpy()
    taus = np.round(np.arange(-TAU_STEP, 20 + 2 * TAU_STEP, TAU_STEP), 3)
    best = {}
    for c in ('awgn', 'rayleigh'):
        m = ch == c
        if not m.any():
            continue
        scores = []
        for tau in taus:
            sel = snr[m] >= tau
            eff = np.where(sel, t.Q_F.to_numpy()[m], t.Q_L.to_numpy()[m])
            scores.append(scene_equal(eff, sc[m]))
        k = int(np.argmax(scores))
        best[c] = float(taus[k])
    return best


def apply_tau(g, tau):
    snr = g.snr_db.to_numpy(float)
    thr = np.array([tau.get(c, np.inf) for c in g.channel.to_numpy()])
    return np.where(snr >= thr, 'F', 'L')


# ------------------------------------------------------------------ the round
def run_round(g, cues, cue_fields, labels, jobs, tag):
    """One complete LOSO pass. Returns out-of-fold predictions and the per-fold record."""
    from sklearn.ensemble import RandomForestClassifier
    X, names = features(g, cues, cue_fields)
    Xt = X[:, :len(cue_fields)]                      # task-only: the two channel columns removed
    scenes = g.scene.to_numpy()
    frames = g.sample_id.to_numpy()
    uniq = np.unique(scenes)
    hp = hyperparameters()

    oof = {'joint': np.empty(len(g), object), 'task_only': np.empty(len(g), object),
           'channel_rule': np.empty(len(g), object)}
    proba = np.full((len(g), len(ACTIONS)), np.nan)
    folds = []
    for s in uniq:
        te = scenes == s
        tr = ~te
        # C-4 gate: no frame may straddle the split
        if set(np.unique(frames[tr])) & set(np.unique(frames[te])):
            raise SystemExit(f'fold {s}: a frame appears on both sides of the split')
        n_cells_tr = pd.Series(frames[tr]).value_counts().unique()
        n_cells_te = pd.Series(frames[te]).value_counts().unique()
        if len(n_cells_tr) != 1 or len(n_cells_te) != 1 or n_cells_tr[0] != n_cells_te[0]:
            raise SystemExit(f'fold {s}: frames do not all carry the same number of channel versions')
        t0 = time.time()
        rf = RandomForestClassifier(n_jobs=jobs, **hp).fit(X[tr], labels[tr])
        oof['joint'][te] = rf.predict(X[te])
        # C-3: keep the class probabilities, so "the forest ranked F second" can be separated from
        # "the forest saw no value in F at all"
        cls = list(rf.classes_)
        pr = rf.predict_proba(X[te])
        for j, act in enumerate(ACTIONS):
            proba[te, j] = pr[:, cls.index(act)] if act in cls else 0.0
        # C-1: the same forest's F share on the scenes it was fitted on, for fit-versus-generalise
        tr_pred = rf.predict(X[tr])
        rf_t = RandomForestClassifier(n_jobs=jobs, **hp).fit(Xt[tr], labels[tr])
        oof['task_only'][te] = rf_t.predict(Xt[te])
        tau = fit_tau(g, tr)
        oof['channel_rule'][te] = apply_tau(g[te], tau)
        folds.append({'held_out_scene': str(s), 'train_rows': int(tr.sum()),
                      'test_rows': int(te.sum()), 'channel_versions_per_frame': int(n_cells_te[0]),
                      'tau_from_training_scenes': tau,
                      'F_share_in_training_scenes': scene_equal((tr_pred == 'F').astype(float),
                                                                scenes[tr]),
                      'F_share_held_out': scene_equal((oof['joint'][te] == 'F').astype(float),
                                                      scenes[te]),
                      'reference_F_share_in_training_scenes': scene_equal(
                          (labels[tr] == 'F').astype(float), scenes[tr]),
                      'reference_F_share_held_out': scene_equal((labels[te] == 'F').astype(float),
                                                                scenes[te]),
                      'classes_fitted': sorted(cls),
                      'seconds': time.time() - t0})
        print(f'  [{tag}] fold {s}: tau={tau} ({time.time() - t0:.1f}s)', flush=True)
    return oof, folds, names, hp, proba


def evaluate(g, fo, chosen_by_arm, mask, label):
    sc = g.scene.to_numpy()[mask]
    out = {'label': label, 'rows': int(mask.sum()), 'arms': {}}
    for arm, chosen in chosen_by_arm.items():
        Q, rec, mis, pay = outcome(g, fo, chosen)
        star_arr = chosen[mask]
        out['arms'][arm] = {
            'f1': scene_equal(Q[mask], sc), 'recall': scene_equal(rec[mask], sc),
            'misses_per_frame': scene_equal(mis[mask], sc),
            'qam_symbols': scene_equal(pay[mask], sc),
            'request_share': {a: scene_equal((star_arr == a).astype(float), sc) for a in ACTIONS}}
    return out


def differences(g, fo, chosen_by_arm, mask, pairs):
    sc = g.scene.to_numpy()[mask]
    out = {}
    for a, b in pairs:
        Qa = outcome(g, fo, chosen_by_arm[a])[0][mask]
        Qb = outcome(g, fo, chosen_by_arm[b])[0][mask]
        d = Qa - Qb
        per_scene = [{'scene': str(s), 'diff': float(d[sc == s].mean())} for s in np.unique(sc)]
        out[f'{a} - {b}'] = {'bootstrap': boot(d, sc), 'per_scene': per_scene,
                             'scenes_negative': [x['scene'] for x in per_scene if x['diff'] < 0]}
    return out


def confusion(labels, pred, ch, mask):
    out = {}
    for c in ('awgn', 'rayleigh', 'all'):
        m = mask if c == 'all' else (mask & (ch == c))
        tab = {t: {p: int(((labels == t) & (pred == p) & m).sum()) for p in ACTIONS} for t in ACTIONS}
        per = {}
        for a in ACTIONS:
            tp = tab[a][a]
            actual = sum(tab[a].values())
            predicted = sum(tab[t][a] for t in ACTIONS)
            per[a] = {'recall': tp / actual if actual else None,
                      'precision': tp / predicted if predicted else None,
                      'actual': actual, 'predicted': predicted}
        out[c] = {'matrix_true_by_predicted': tab, 'per_action': per,
                  'accuracy': float(((labels == pred) & m).sum() / m.sum()) if m.sum() else None}
    return out


def build(jobs=-1):
    g, n_cw_F, B_F_sym = build_table()
    fo_df, tp_dev = frame_outcomes()
    fo_df = fo_df.set_index('frame').loc[g.sample_id.to_numpy()]

    class FO:
        pass
    fo = FO()
    for a in ACTIONS:
        setattr(fo, f'recall_{a}', fo_df[f'recall_{a}'].to_numpy())
        setattr(fo, f'miss_{a}', fo_df[f'miss_{a}'].to_numpy())

    cues = pd.read_csv(CUES)
    cue_fields = list(json.load(open(CUE_META))['perception_fields'])
    missing = [c for c in cue_fields if c not in cues.columns]
    if missing:
        raise SystemExit(f'cue columns missing from the product: {missing}')

    labels = g.a_star.to_numpy().astype(object)
    print('main round (labels from the p_cw point estimate)', flush=True)
    oof, folds, names, hp, proba = run_round(g, cues, cue_fields, labels, jobs, 'main')

    chosen = dict(oof)
    chosen['fixed_E'] = np.full(len(g), 'E', object)
    chosen['fixed_L'] = np.full(len(g), 'L', object)
    chosen['fixed_F'] = np.full(len(g), 'F', object)
    chosen['offline_optimum'] = labels

    ch = g.channel.to_numpy()
    subsets = [('all 22 cells', np.ones(len(g), bool)), ('AWGN only', ch == 'awgn'),
               ('Rayleigh only', ch == 'rayleigh')]
    pairs = [('joint', 'channel_rule'), ('joint', 'task_only'), ('joint', 'fixed_L'),
             ('joint', 'fixed_F'), ('offline_optimum', 'joint')]
    results = [evaluate(g, fo, chosen, m, lab) for lab, m in subsets]
    diffs = {lab: differences(g, fo, chosen, m, pairs) for lab, m in subsets}

    per_cell = []
    for (c, s), t in g.groupby(['channel', 'snr_db']):
        m = ((g.channel == c) & (g.snr_db == s)).to_numpy()
        sc = g.scene.to_numpy()[m]
        row = {'channel': c, 'snr_db': int(s)}
        for arm in ('joint', 'channel_rule', 'offline_optimum'):
            Q, rec, mis, pay = outcome(g, fo, chosen[arm])
            row[arm] = {'f1': scene_equal(Q[m], sc),
                        'share_F': scene_equal((chosen[arm][m] == 'F').astype(float), sc)}
        per_cell.append(row)
    per_cell.sort(key=lambda r: (r['channel'], r['snr_db']))

    # ---- C-7 stability: relabel from p_cw_upper95 on the cells that have their own sample ----
    bl = pd.read_csv(BLER); bl = bl[bl.qam == 16]
    counts = {(r.channel, float(r.esno_db)): (int(r.n_err), int(r.n_cw)) for r in bl.itertuples()}
    has = np.array([(c, float(s)) in counts for c, s in zip(g.channel, g.snr_db)])
    p_up = np.array([cp_upper(*counts[(c, float(s))]) if (c, float(s)) in counts else np.nan
                     for c, s in zip(g.channel, g.snr_db)])
    qF_up = (1.0 - p_up) ** n_cw_F
    qL_up = (1.0 - p_up) ** (g.B_L_sym.to_numpy() / 250.0)
    QF_up = qF_up * g.f1_clean.to_numpy() + (1 - qF_up) * g.f1_ego.to_numpy()
    QL_up = qL_up * g.f1_L.to_numpy() + (1 - qL_up) * g.f1_ego.to_numpy()
    Qm = np.stack([g.Q_E.to_numpy(), QL_up, QF_up], axis=1)
    best = np.nanmax(Qm, axis=1)
    within = Qm >= best[:, None] - TOL
    lab_up = np.array(ACTIONS)[np.argmax(within, axis=1)].astype(object)
    flip = has & (lab_up != labels)
    stability = {'cells_with_a_sample': int(len({(c, s) for c, s, h in zip(g.channel, g.snr_db, has) if h})),
                 'cells_without': sorted({f'{c} {int(s)} dB' for c, s, h in zip(g.channel, g.snr_db, has)
                                          if not h}),
                 'rows_considered': int(has.sum()),
                 'label_flip_rows': int(flip.sum()),
                 'label_flip_share': float(flip.sum() / has.sum()),
                 'flips_by_direction': {f'{a} -> {b}': int(((labels == a) & (lab_up == b) & has).sum())
                                        for a in ACTIONS for b in ACTIONS if a != b}}
    stability['flips_by_direction'] = {k: v for k, v in stability['flips_by_direction'].items() if v}

    print('stability round (labels from p_cw_upper95)', flush=True)
    oof_up, folds_up, _, _, _ = run_round(g[has].reset_index(drop=True), cues, cue_fields,
                                          lab_up[has], jobs, 'upper95')
    gh = g[has].reset_index(drop=True)
    fo_h = FO()
    for a in ACTIONS:
        setattr(fo_h, f'recall_{a}', getattr(fo, f'recall_{a}')[has])
        setattr(fo_h, f'miss_{a}', getattr(fo, f'miss_{a}')[has])
    gh = gh.assign(q_F=qF_up[has], q_L=qL_up[has], Q_F=QF_up[has], Q_L=QL_up[has])
    ch_up = dict(oof_up)
    ch_up['fixed_L'] = np.full(len(gh), 'L', object)
    ch_up['fixed_F'] = np.full(len(gh), 'F', object)
    ch_up['offline_optimum'] = lab_up[has]
    stability['B2_channel_and_model'] = {
        'what_moved': 'the error rate AND the labels AND the fitted forest. This is the round-1 '
                      'sensitivity check, kept but relabelled: it does not isolate the channel',
        'arms_under_upper_bound': evaluate(gh, fo_h, ch_up, np.ones(len(gh), bool),
                                           'sampled cells, relabelled and refitted'),
        'arms_under_point_estimate_same_rows': evaluate(
            g[has].reset_index(drop=True), fo_h,
            {k: v[has] if len(v) == len(g) else v for k, v in chosen.items()},
            np.ones(int(has.sum()), bool), 'sampled cells, round-1 labels and forest')}

    # B-1: hold round 1's actions fixed and change only the channel assumption, so the difference is
    # the channel uncertainty and nothing else. Every arm keeps the action it chose in round 1,
    # including the offline optimum, whose label is NOT recomputed here.
    fixed_actions = {k: v[has] for k, v in chosen.items()}
    g_pt = g[has].reset_index(drop=True)
    g_up = g_pt.assign(q_F=qF_up[has], q_L=qL_up[has], Q_F=QF_up[has], Q_L=QL_up[has])
    ev_pt = evaluate(g_pt, fo_h, fixed_actions, np.ones(len(g_pt), bool),
                     'same actions, p_cw_point')
    ev_up = evaluate(g_up, fo_h, fixed_actions, np.ones(len(g_up), bool),
                     'same actions, p_cw_upper95')
    stability['B1_channel_only'] = {
        'what_moved': 'only the per-codeword error rate. Actions, labels and forest are those of '
                      'round 1, so every difference below is channel uncertainty alone',
        'point_estimate': ev_pt, 'upper_bound': ev_up,
        'delta': {arm: ev_up['arms'][arm]['f1'] - ev_pt['arms'][arm]['f1'] for arm in ev_pt['arms']},
        'tau_caveat': 'the channel-rule arm keeps the tau fitted in round 1, which was fitted on the '
                      'point-estimate effect columns. Its action set is therefore not re-optimised '
                      'for the upper bound, and the upper-bound column for that arm should be read '
                      'as "the round-1 rule evaluated under a worse channel", not as the best rule '
                      'under that channel'}

    # D-1: the per-row out-of-fold record, saved as a product and hashed into the manifest
    oof_df = pd.DataFrame({
        'sample_id': g.sample_id.to_numpy(), 'scene': g.scene.to_numpy(),
        'snr_db': g.snr_db.to_numpy(), 'channel': g.channel.to_numpy(),
        'a_star': labels, 'pred_joint': oof['joint'], 'pred_task_only': oof['task_only'],
        'pred_channel_rule': oof['channel_rule'],
        'p_E': proba[:, 0], 'p_L': proba[:, 1], 'p_F': proba[:, 2],
        'q_F': g.q_F.to_numpy(), 'q_L': g.q_L.to_numpy(),
        'Q_E': g.Q_E.to_numpy(), 'Q_L': g.Q_L.to_numpy(), 'Q_F': g.Q_F.to_numpy(),
        'B_L_sym': g.B_L_sym.to_numpy()})
    if oof_df[['p_E', 'p_L', 'p_F']].isna().any().any():
        raise SystemExit('a row has no out-of-fold probability -- some row was never held out')
    ps = oof_df[['p_E', 'p_L', 'p_F']].to_numpy().sum(axis=1)
    if float(np.abs(ps - 1.0).max()) > 1e-9:
        raise SystemExit('class probabilities do not sum to 1 -- the class mapping is wrong')
    os.makedirs(os.path.dirname(OOF_CSV), exist_ok=True)
    oof_df.to_csv(OOF_CSV, index=False)

    pot = json.load(open(POTENTIAL))
    ref = {a['label']: a['optimal_share'] for a in pot['analyses']}

    return {'schema': 'catosg-p2-rf-round1/1',
            'status': 'DEVELOPMENT VALIDATION ONLY (D-2). Leave-one-scene-out on validate; no '
                      'selection is made on validate after the LOSO, and no held-out result is '
                      'produced. test and Culver are not opened',
            'accounting': 'LOCKED all-or-nothing: a message is usable only if it decodes whole, a '
                          'failure falls back to E, and payload is charged for the attempt',
            'inputs': {'cues': sha(CUES), 'wp5': sha(WP5), 'wp34': sha(WP34), 'bler': sha(BLER),
                       'freeze': sha(FREEZE), 'potential': sha(POTENTIAL)},
            'features': {'names': names, 'n': len(names),
                         'est_snr_db_note': 'the SNR of the cell, i.e. a perfect estimate. This is '
                                            "P1's idealisation carried over unchanged; a real "
                                            'receiver estimate would be noisier and the joint arm '
                                            'reported here is therefore optimistic in that respect'},
            'hyperparameters': hp,
            'hyperparameter_source': 'results/manifests/V2_PRIMARY_FREEZE.json selector block, read '
                                     'not retyped. Adopted unchanged so that nothing is tuned on '
                                     'validate; the lambda objective is not used and candidate 67 '
                                     "weights are not loaded, only P1's forest settings",
            'recall_derivation': {'method': 'TP = F1 (P + G) / 2, valid for a one-to-one matching',
                                  'integrality_max_deviation': tp_dev,
                                  'verified': 'TP lands on an integer for every frame and action; if '
                                              'it had not, no recall would be reported'},
            'reproducibility': 'the forests are seeded (random_state 0) and the record re-derives '
                               'exactly, apart from the per-fold wall-clock in folds[].seconds, '
                               'which --check --full excludes and names',
            'oof_product': {'path': os.path.relpath(OOF_CSV, ROOT), 'sha256': sha(OOF_CSV),
                            'rows': int(len(oof_df)), 'columns': list(oof_df.columns),
                            'what': 'the per-row out-of-fold record: the label, every arm\'s action, '
                                    'the joint forest\'s three class probabilities, and the channel '
                                    'and effect columns needed to reconstruct any of the above'},
            'folds': folds, 'results': results, 'differences': diffs, 'per_cell': per_cell,
            'confusion': confusion(labels, oof['joint'], ch, np.ones(len(g), bool)),
            'stability_C7': stability,
            'offline_reference_shares': ref,
            'command': 'python projects/ca_tosg_p2/protocol/rf_round1.py'}


def cap1(t):
    """Uppercase the first character only; str.capitalize() would lowercase TP, F1 and E/L/F."""
    return t[:1].upper() + t[1:]


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/rf_round1.py -- do not edit by hand -->',
         '# First RF round: classifying the per-frame optimal action (P2-R15 C)', '',
         f"**{m['status']}.**", '', f"**Accounting.** {m['accounting']}.", '',
         f"**Input.** {m['features']['n']} features: {m['features']['n'] - 2} ego-local cues plus "
         '`est_snr_db` and `channel_is_rayleigh`.', '',
         f"*A caveat that belongs next to every joint number below:* {m['features']['est_snr_db_note']}.",
         '', f"**Hyperparameters.** {m['hyperparameters']} — {m['hyperparameter_source']}.", '',
         f"**Recall.** {m['recall_derivation']['method']}. "
         f"{cap1(m['recall_derivation']['verified'])} "
         f"(largest deviation from an integer: {m['recall_derivation']['integrality_max_deviation']:.1e}).",
         '', '## C-4 The folds, and C-1 fit versus generalise', '',
         'The two F-share columns answer a question that the held-out numbers alone cannot: a forest '
         'that already declines F on the scenes it was fitted on is underfitting the action, whereas '
         'one that requests F in training and not out of fold is failing to generalise.', '',
         '| held-out scene | train rows | test rows | versions/frame | τ from training | RF F share, '
         'training scenes | reference F share, training | RF F share, held out | reference F share, '
         'held out |',
         '|---|---:|---:|---:|---|---:|---:|---:|---:|']
    for f in m['folds']:
        L.append(f"| {f['held_out_scene']} | {f['train_rows']:,} | {f['test_rows']:,} | "
                 f"{f['channel_versions_per_frame']} | {f['tau_from_training_scenes']} | "
                 f"{f['F_share_in_training_scenes'] * 100:.1f} % | "
                 f"{f['reference_F_share_in_training_scenes'] * 100:.1f} % | "
                 f"{f['F_share_held_out'] * 100:.1f} % | "
                 f"{f['reference_F_share_held_out'] * 100:.1f} % |")
    L += ['', 'The gate asserts that no frame appears on both sides and that every frame carries the',
          'same number of channel versions, so all 22 versions of a frame move together.', '',
          '## C-6 Arms', '']
    for r in m['results']:
        L += [f"### {r['label']} ({r['rows']:,} rows)", '',
              '| arm | scene-equal F1 | recall | misses / frame | QAM symbols | request E | L | F |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
        for arm in ('offline_optimum', 'joint', 'task_only', 'channel_rule', 'fixed_E', 'fixed_L',
                    'fixed_F'):
            v = r['arms'][arm]
            s = v['request_share']
            L.append(f"| `{arm}` | {v['f1']:.5f} | {v['recall']:.5f} | {v['misses_per_frame']:.3f} | "
                     f"{v['qam_symbols']:,.0f} | {s['E'] * 100:.1f} % | {s['L'] * 100:.1f} % | "
                     f"{s['F'] * 100:.1f} % |")
        L += ['', '| difference | scene-equal mean | bootstrap 95 % | scenes negative |',
              '|---|---:|---|---|']
        for k, v in m['differences'][r['label']].items():
            b = v['bootstrap']
            L.append(f"| {k} | {b['mean']:+.5f} | [{b['lcb95']:+.5f}, {b['ucb95']:+.5f}] | "
                     + (', '.join(v['scenes_negative']) if v['scenes_negative'] else 'none') + ' |')
        L.append('')
    L += ['### C-8 interpretation rule: the F share beside the offline reference', '',
          'Registered in `training_plan.md` before this was run.', '',
          '| subset | offline reference F | RF request F |', '|---|---:|---:|']
    for r in m['results']:
        ref = m['offline_reference_shares'].get(r['label'])
        rf = r['arms']['joint']['request_share']['F']
        L.append(f"| {r['label']} | " + (f"{ref['F'] * 100:.1f} %" if ref else '—')
                 + f" | {rf * 100:.1f} % |")
    L += ['', '## C-8 Confusion against the offline optimum', '']
    for c, v in m['confusion'].items():
        L += [f"### {c} (accuracy {v['accuracy'] * 100:.1f} %)", '',
              '| true \\ predicted | E | L | F |', '|---|---:|---:|---:|']
        for t in ACTIONS:
            row = v['matrix_true_by_predicted'][t]
            L.append(f"| **{t}** | {row['E']:,} | {row['L']:,} | {row['F']:,} |")
        L += ['', '| action | recall | precision | actual | predicted |', '|---|---:|---:|---:|---:|']
        for a in ACTIONS:
            p = v['per_action'][a]
            L.append(f"| {a} | " + (f"{p['recall'] * 100:.1f} %" if p['recall'] is not None else '—')
                     + ' | ' + (f"{p['precision'] * 100:.1f} %" if p['precision'] is not None else '—')
                     + f" | {p['actual']:,} | {p['predicted']:,} |")
        L.append('')
    st = m['stability_C7']
    b1, b2 = st['B1_channel_only'], st['B2_channel_and_model']
    L += ['## B Stability under the upper bound on p_cw, split into two questions', '',
          'The main analysis uses the p_cw point estimate. Neither table below shows that the',
          'reliability is assured; they show how much of the movement is the channel and how much is',
          'the model responding to a changed channel.', '',
          f"Cells with a sample of their own: {st['cells_with_a_sample']} of 22 "
          f"({st['rows_considered']:,} rows). Excluded for having no sample and therefore no bound: "
          + ', '.join(st['cells_without']) + '.', '',
          '### B-1 Channel only — the actions of round 1 held fixed', '',
          f"{cap1(b1['what_moved'])}.", '',
          '| arm | F1, p_cw_point | F1, p_cw_upper95 | change |', '|---|---:|---:|---:|']
    for arm in ('offline_optimum', 'joint', 'task_only', 'channel_rule', 'fixed_L', 'fixed_F',
                'fixed_E'):
        a1 = b1['point_estimate']['arms'].get(arm)
        a2 = b1['upper_bound']['arms'].get(arm)
        if a1 and a2:
            L.append(f"| `{arm}` | {a1['f1']:.5f} | {a2['f1']:.5f} | {a2['f1'] - a1['f1']:+.5f} |")
    L += ['', f"**B-3.** {b1['tau_caveat']}.", '',
          '### B-2 Channel and model together — relabelled and refitted', '',
          f"{cap1(b2['what_moved'])}.", '',
          f"**Labels flip on {st['label_flip_rows']:,} of {st['rows_considered']:,} rows "
          f"({st['label_flip_share'] * 100:.1f} %)**, by direction: "
          + ', '.join(f'{k} {v:,}' for k, v in st['flips_by_direction'].items()) + '.', '',
          '| arm | F1, round-1 labels and forest | F1, relabelled and refitted | change |',
          '|---|---:|---:|---:|']
    for arm in ('offline_optimum', 'joint', 'task_only', 'fixed_L', 'fixed_F'):
        a1 = b2['arms_under_point_estimate_same_rows']['arms'].get(arm)
        a2 = b2['arms_under_upper_bound']['arms'].get(arm)
        if a1 and a2:
            L.append(f"| `{arm}` | {a1['f1']:.5f} | {a2['f1']:.5f} | {a2['f1'] - a1['f1']:+.5f} |")
    pr = m['oof_product']
    L += ['', '## D-1 The per-row product', '',
          f"`{pr['path']}` — {pr['rows']:,} rows. {cap1(pr['what'])}. Its sha256 is recorded here and "
          '`--check` verifies it.', '']
    L += ['', '## Per cell', '',
          '| channel | SNR | optimum F1 | joint F1 | rule F1 | optimum F share | joint F share | rule F share |',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in m['per_cell']:
        L.append(f"| {r['channel']} | {r['snr_db']} | {r['offline_optimum']['f1']:.5f} | "
                 f"{r['joint']['f1']:.5f} | {r['channel_rule']['f1']:.5f} | "
                 f"{r['offline_optimum']['share_F'] * 100:.1f} % | {r['joint']['share_F'] * 100:.1f} % | "
                 f"{r['channel_rule']['share_F'] * 100:.1f} % |")
    L += ['', '## Inputs', '', '| file | sha256 |', '|---|---|']
    for k, v in m['inputs'].items():
        L.append(f"| {k} | `{v[:16]}…` |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true',
                    help='verify the document against the stored record (cheap). Add --full to '
                         're-derive the record itself by retraining, which costs what the run costs')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--rerender', action='store_true',
                    help='rewrite the markdown from the stored record without retraining')
    ap.add_argument('--jobs', type=int, default=-1)
    a = ap.parse_args()

    if a.rerender:
        m = json.load(open(OUT_JSON))
        open(OUT_MD, 'w').write(markdown(m))
        print('rf round1: markdown rewritten from the stored record (no retraining)')
        return 0

    if a.check and not a.full:
        # The document is checked against the record byte for byte. This does NOT re-derive the
        # record -- 27 forest fits -- and says so rather than implying a verification it did not do.
        if not os.path.exists(OUT_JSON):
            print('rf round1: FAIL -- no stored record to check against'); return 1
        m = json.load(open(OUT_JSON))
        ok = os.path.exists(OUT_MD) and open(OUT_MD).read() == markdown(m)
        prod = m.get('oof_product', {})
        have = os.path.exists(OOF_CSV)
        prod_ok = have and sha(OOF_CSV) == prod.get('sha256')
        print('rf round1:', 'document matches the record' if ok else 'FAIL -- document is not what '
              'the generator writes from the record')
        print('  per-row product:', 'hash matches the record' if prod_ok
              else ('FAIL -- missing' if not have else 'FAIL -- hash differs from the record'))
        print('  (the record itself is not re-derived at this level; use --check --full)')
        return 0 if (ok and prod_ok) else 1

    m = build(a.jobs)
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        stored = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
        diffs = json_diff(strip_volatile(stored), strip_volatile(m))
        md_ok = os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print(f'rf round1: comparison excludes {VOLATILE_FIELDS} -- wall-clock, which measures the '
              'run and not the result')
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
