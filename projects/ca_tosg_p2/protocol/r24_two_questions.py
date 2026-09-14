#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R24 — two questions answered from stored products. No training, no GPU, no point clouds.

Question one: on a good channel, can the F-versus-L advantage be predicted before the request?
Question two: on a bad channel, where do the useless F requests come from and what do they cost?

Everything is read from round 4's saved per-row output and the frozen Q table. Nothing is refitted,
no prediction is clipped, no threshold is added and no selection rule is changed. `caluclate_tp_fp`
is not touched, no point cloud is loaded, and the per-object "which objects F recovered" analysis
stays an open item with its cost already on the record.

Every bin edge and tolerance below is a module constant, fixed before any diagnostic was read.

    python r24_two_questions.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
ROWS_GZ = os.path.join(P2, 'results', 'rf', 'rf_round4_rows.csv.gz')
GRID = os.path.join(ROOT, 'results', 'v2', 'v2_grid_validate_ideal.csv')
BLER = os.path.join(ROOT, 'results', 'channel', 'bler_sionna.csv')
CHAIN = os.path.join(ROOT, 'results', 'v2', 'payload_chain.json')
OUT_JSON = os.path.join(HERE, 'r24_two_questions.json')
OUT_MD = os.path.join(HERE, 'r24_two_questions.md')

sys.path.insert(0, HERE)
from offline_potential import build_table, scene_equal, ACTIONS, TOL              # noqa: E402
from awgn_fill import cp_upper                                                    # noqa: E402

HI_CELLS = [('awgn', s) for s in (10, 12, 14, 16, 18, 20)]
DFL_BIN_EDGES = [-np.inf, -0.10, -0.05, -0.02, -TOL, TOL, 0.02, 0.05, 0.10, np.inf]
DFL_BIN_LABELS = ['< -0.10', '[-0.10, -0.05)', '[-0.05, -0.02)', '[-0.02, -TOL)', 'tie (|D| <= TOL)',
                  '(TOL, 0.02]', '(0.02, 0.05]', '(0.05, 0.10]', '> 0.10']
EXCESS_TOL = 1e-9            # C-2: below this an excess is floating-point noise, not a decision
CLASS_NAMES = {1: 'F ahead', -1: 'L ahead', 0: 'tie'}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def classify(v, tol=TOL):
    return np.where(v > tol, 1, np.where(v < -tol, -1, 0))


def bin_of(v):
    cut = pd.cut(v, bins=DFL_BIN_EDGES, labels=DFL_BIN_LABELS, right=False)
    return [(lab, np.asarray(cut == lab)) for lab in DFL_BIN_LABELS]


def predict_stats(true_d, pred_d, label):
    """corr, sign agreement, per-bin behaviour and the separation, on one row subset."""
    out = {'label': label, 'rows': int(len(true_d))}
    out['corr'] = (float(np.corrcoef(true_d, pred_d)[0, 1])
                   if len(true_d) > 1 and true_d.std() > 0 and pred_d.std() > 0 else None)
    ct, cp = classify(true_d), classify(pred_d)
    out['sign_agreement'] = float((ct == cp).mean())
    out['true_class_counts'] = {CLASS_NAMES[k]: int((ct == k).sum()) for k in (1, -1, 0)}
    out['pred_class_counts'] = {CLASS_NAMES[k]: int((cp == k).sum()) for k in (1, -1, 0)}
    bins = []
    for lab, m in bin_of(true_d):
        if not m.any():
            continue
        bins.append({'bin': lab, 'rows': int(m.sum()), 'mean_true': float(true_d[m].mean()),
                     'mean_pred': float(pred_d[m].mean()),
                     'sign_correct': float((ct[m] == cp[m]).mean())})
    out['bins'] = bins
    fw, lw = ct == 1, ct == -1
    out['separation'] = {
        'true_F_ahead_mean': float(true_d[fw].mean()) if fw.any() else None,
        'true_L_ahead_mean': float(true_d[lw].mean()) if lw.any() else None,
        'pred_F_ahead_mean': float(pred_d[fw].mean()) if fw.any() else None,
        'pred_L_ahead_mean': float(pred_d[lw].mean()) if lw.any() else None,
        'true_separation': (float(true_d[fw].mean() - true_d[lw].mean())
                            if fw.any() and lw.any() else None),
        'pred_separation': (float(pred_d[fw].mean() - pred_d[lw].mean())
                            if fw.any() and lw.any() else None)}
    return out


def build():
    rows = pd.read_csv(ROWS_GZ)
    g, n_cw_F, B_F_sym = build_table()
    chain = json.load(open(CHAIN))['F']
    if abs(B_F_sym - 3141750.0) > 1e-6:
        raise SystemExit(f'the F payload is {B_F_sym}, not the 3,141,750 the brief names')

    held = rows[rows.split == 'held_out'].copy()
    train = rows[rows.split == 'training'].copy()
    if len(held) != len(g):
        raise SystemExit(f'held-out rows {len(held)} != grid rows {len(g)}')
    key = ['sample_id', 'channel', 'snr_db']
    if held.duplicated(key).any():
        raise SystemExit('a (frame, channel, SNR) key appears twice among the held-out rows')
    reps = sorted(train.groupby(key).size().unique().tolist())

    q = g.set_index(key)
    held = held.set_index(key).loc[q.index].reset_index()
    qq = q.reset_index()

    # ---------------- B-1 ----------------
    dfl_file = (held.dF_true - held.dL_true).to_numpy()
    dfl_q = (qq.Q_F - qq.Q_L).to_numpy()
    err = float(np.abs(dfl_file - dfl_q).max())
    changed = int((classify(dfl_file) != classify(dfl_q)).sum())
    b1 = {'max_abs_difference': err, 'rows_whose_TOL_class_changes': changed,
          'tol': TOL,
          'reading': 'the two routes to D_FL agree to this many decimals, and the difference moves '
                     'no row across the tie boundary' if changed == 0 else
                     'the difference moves rows across the tie boundary and must be resolved before '
                     'anything below is read'}

    dfl_hat = (held.dF_hat - held.dL_hat).to_numpy()
    dfl = dfl_file
    ch = held.channel.to_numpy()
    snr = held.snr_db.to_numpy()
    sid = held.sample_id.to_numpy()
    scene = held.scene.to_numpy()

    hi_mask = np.zeros(len(held), bool)
    for c, s in HI_CELLS:
        hi_mask |= (ch == c) & (snr == s)

    # ---------------- A-2 ----------------
    per_cell_frames = {}
    for c, s in HI_CELLS:
        m = (ch == c) & (snr == s)
        t = qq[m.nonzero()[0]] if False else qq[m]
        per_cell_frames[f'{c} {s} dB'] = pd.DataFrame({
            'sample_id': sid[m], 'q_F': t.q_F.to_numpy(), 'q_L': t.q_L.to_numpy(),
            'D_FL': dfl[m]}).set_index('sample_id').sort_index()
    ref = per_cell_frames[f'awgn {HI_CELLS[0][1]} dB']
    same = {}
    for k, v in per_cell_frames.items():
        same[k] = {'frames': int(len(v)),
                   'max_abs_q_F_diff': float(np.abs(v.q_F - ref.q_F).max()),
                   'max_abs_q_L_diff': float(np.abs(v.q_L - ref.q_L).max()),
                   'max_abs_D_FL_diff': float(np.abs(v.D_FL - ref.D_FL).max())}
    identical = all(v['max_abs_q_F_diff'] == 0 and v['max_abs_q_L_diff'] == 0
                    and v['max_abs_D_FL_diff'] == 0 for v in same.values())
    cls_ref = classify(ref.D_FL.to_numpy())
    bl = pd.read_csv(BLER); bl = bl[bl.qam == 16]
    counts = {(r.channel, float(r.esno_db)): (int(r.n_err), int(r.n_cw)) for r in bl.itertuples()}
    measured = [(c, s) for c, s in HI_CELLS if (c, float(s)) in counts]
    unmeasured = [(c, s) for c, s in HI_CELLS if (c, float(s)) not in counts]
    q_lower = None
    if measured:
        ups = {cp_upper(*counts[(c, float(s))]) for c, s in measured}
        if len(ups) == 1:
            q_lower = float((1.0 - ups.pop()) ** n_cw_F)
    a2 = {'cells': [f'{c} {s} dB' for c, s in HI_CELLS],
          'per_cell': same, 'identical_across_cells': bool(identical),
          'unique_frames': int(len(ref)),
          'frame_counts': {CLASS_NAMES[k]: int((cls_ref == k).sum()) for k in (1, -1, 0)},
          'point_estimate_wording': 'under the current point estimate q_F = q_L = 1 in all six cells',
          'upper_bound_wording': (
              f'the {len(measured)} zero-error measured cells '
              f'({", ".join(f"{c} {s} dB" for c, s in measured)}) have a message success probability '
              f'no lower than about {q_lower:.3f} under the one-sided 95 % upper limit on their error '
              f'rate; {", ".join(f"{c} {s} dB" for c, s in unmeasured)} have no measurement counts of '
              'their own and are not given that lower bound'),
          'q_F_lower_bound_measured_cells': q_lower}

    # ---------------- B-2, B-3, B-4 ----------------
    b2 = {f'{c} {s} dB': predict_stats(dfl[(ch == c) & (snr == s)],
                                       dfl_hat[(ch == c) & (snr == s)], f'{c} {s} dB')
          for c, s in HI_CELLS}
    b2_pooled = predict_stats(dfl[hi_mask], dfl_hat[hi_mask],
                              'six high-reliability cells pooled (supplementary)')

    tr = train.copy()
    tr_hi = np.zeros(len(tr), bool)
    for c, s in HI_CELLS:
        tr_hi |= (tr.channel.to_numpy() == c) & (tr.snr_db.to_numpy() == s)
    b3 = {'available': bool(len(tr) > 0), 'repetitions_per_row': reps,
          'note': 'a training row is a (fold, row) pair: the same frame-cell appears in every fold '
                  'whose held-out scene is not its own, so these rows are not independent samples '
                  'and the counts are inflated by that repetition',
          'high_reliability': predict_stats((tr.dF_true - tr.dL_true).to_numpy()[tr_hi],
                                            (tr.dF_hat - tr.dL_hat).to_numpy()[tr_hi],
                                            'training rows, six high-reliability cells')}
    b4 = {'all 22 cells': predict_stats(dfl, dfl_hat, 'held out, all cells'),
          'AWGN only': predict_stats(dfl[ch == 'awgn'], dfl_hat[ch == 'awgn'],
                                     'held out, AWGN only')}

    # ---------------- C-1 ----------------
    ray = sorted({int(s) for c, s in zip(ch, snr) if c == 'rayleigh'})
    c1 = []
    for s in ray:
        m = (ch == 'rayleigh') & (snr == s)
        p_cw = float(qq.p_cw.to_numpy()[m][0])
        qf = float(qq.q_F.to_numpy()[m][0])
        hit = counts.get(('rayleigh', float(s)))
        up = cp_upper(*hit) if hit else None
        c1.append({'snr_db': s, 'p_cw': p_cw, 'q_F_point_estimate': qf,
                   'p_cw_upper95': up,
                   'q_F_under_upper_limit': float((1.0 - up) ** n_cw_F) if up is not None else None,
                   'q_F_underflowed_to_zero': bool(qf == 0.0),
                   'counts': f'{hit[0]}/{hit[1]}' if hit else None})
    underflowed = [r['snr_db'] for r in c1 if r['q_F_underflowed_to_zero']]

    # ---------------- C-2 ----------------
    f1_ego = qq.f1_ego.to_numpy()
    lo = -qq.q_F.to_numpy() * f1_ego
    hi_b = qq.q_F.to_numpy() * (1.0 - f1_ego)
    above = held.dF_hat.to_numpy() - hi_b
    below = lo - held.dF_hat.to_numpy()
    rm = ch == 'rayleigh'
    c2 = {'tolerance': EXCESS_TOL,
          'definition': 'the analytic range of dF is [-q_F * F1_E, q_F * (1 - F1_E)] because '
                        'dF = q_F * (F1_clean - F1_E) and F1_clean lies in [0, 1]',
          'per_cell': []}
    for s in ray:
        m = rm & (snr == s)
        a, b = above[m], below[m]
        big_a, big_b = a > EXCESS_TOL, b > EXCESS_TOL
        noise = ((a > 0) & ~big_a) | ((b > 0) & ~big_b)
        c2['per_cell'].append({
            'snr_db': s, 'rows': int(m.sum()),
            'above_upper_rows': int(big_a.sum()), 'below_lower_rows': int(big_b.sum()),
            'float_noise_rows': int(noise.sum()),
            'above_upper_share': float(big_a.mean()), 'below_lower_share': float(big_b.mean()),
            'above_excess_p50': float(np.percentile(a[big_a], 50)) if big_a.any() else None,
            'above_excess_p90': float(np.percentile(a[big_a], 90)) if big_a.any() else None,
            'above_excess_max': float(a[big_a].max()) if big_a.any() else None,
            'below_excess_max': float(b[big_b].max()) if big_b.any() else None})

    # ---------------- C-3 ----------------
    Q = np.stack([qq.Q_E.to_numpy(), qq.Q_L.to_numpy(), qq.Q_F.to_numpy()], axis=1)
    Q_star = np.choose([ACTIONS.index(a) for a in held.a_star], Q.T)
    loss_F = Q_star - qq.Q_F.to_numpy()
    req_F = (held.pred.to_numpy() == 'F')
    c3 = []
    for s in ray:
        m = rm & (snr == s)
        sc = scene[m]
        cats = {'above_upper': (above[m] > EXCESS_TOL), 'below_lower': (below[m] > EXCESS_TOL)}
        cats['in_bounds'] = ~(cats['above_upper'] | cats['below_lower'])
        row = {'snr_db': s}
        for name, sel in cats.items():
            I = sel & req_F[m]
            row[name] = {
                'requests': int(I.sum()),
                'loss_contribution': scene_equal(I * loss_F[m], sc),
                'qam_contribution': scene_equal(I * B_F_sym, sc),
                'mean_loss_per_request': float(loss_F[m][I].mean()) if I.any() else None}
        c3.append(row)

    # ---------------- C-4 ----------------
    true_sign = np.sign(qq.f1_clean.to_numpy() - qq.f1_ego.to_numpy())
    c4 = {'method': 'for each frame the expected direction of dF_hat across cells is the sign of '
                    'F1_clean - F1_E: positive should rise with q_F, negative should fall, zero '
                    'should not move. Cells whose q_F underflows to zero in double precision carry '
                    'no usable q_F and are excluded from the direction test rather than counted as '
                    'ties',
          'per_channel': {}}
    for c in ('awgn', 'rayleigh'):
        cells = sorted({int(s) for cc, s in zip(ch, snr) if cc == c})
        usable, excluded = [], []
        for s in cells:
            m = (ch == c) & (snr == s)
            (usable if float(qq.q_F.to_numpy()[m][0]) > 0 else excluded).append(s)
        entry = {'cells': cells, 'usable_cells_db': usable, 'excluded_for_underflow_db': excluded}
        if len(usable) < 2:
            entry['determinable'] = False
            entry['reason'] = (f'only {len(usable)} cell(s) on this channel have a q_F that is '
                               'representable in double precision, so a direction across q_F cannot '
                               'be formed at all. This is a numerical limit of the grid, not a '
                               'property of the predictor')
        else:
            q_by_cell = {s: float(qq.q_F.to_numpy()[(ch == c) & (snr == s)][0]) for s in usable}
            s_lo = min(usable, key=lambda s: q_by_cell[s])
            s_hi = max(usable, key=lambda s: q_by_cell[s])
            idx_lo = {f: i for i, f in enumerate(sid[(ch == c) & (snr == s_lo)])}
            d_lo = held.dF_hat.to_numpy()[(ch == c) & (snr == s_lo)]
            d_hi = held.dF_hat.to_numpy()[(ch == c) & (snr == s_hi)]
            f_hi = sid[(ch == c) & (snr == s_hi)]
            order = np.array([idx_lo[f] for f in f_hi])
            delta = d_hi - d_lo[order]
            sgn = true_sign[(ch == c) & (snr == s_hi)]
            expect_up, expect_dn, expect_flat = sgn > 0, sgn < 0, sgn == 0
            agree = ((expect_up & (delta > 0)) | (expect_dn & (delta < 0))
                     | (expect_flat & (np.abs(delta) <= EXCESS_TOL)))
            entry.update({
                'determinable': True,
                'compared_cells_db': [s_lo, s_hi], 'q_F_at_those_cells': [q_by_cell[s_lo],
                                                                          q_by_cell[s_hi]],
                'frames': int(len(delta)),
                'share_matching_expected_direction': float(agree.mean()),
                'frames_expected_up': int(expect_up.sum()),
                'frames_expected_down': int(expect_dn.sum()),
                'frames_expected_flat': int(expect_flat.sum()),
                'mean_deviation_when_contradicting': (float(np.abs(delta[~agree]).mean())
                                                      if (~agree).any() else 0.0),
                'max_deviation_when_contradicting': (float(np.abs(delta[~agree]).max())
                                                     if (~agree).any() else 0.0)})
        c4['per_channel'][c] = entry

    return {'schema': 'catosg-p2-r24-two-questions/1',
            'status': 'ANALYSIS ONLY. No training, no GPU, no point clouds, no change to OpenCOOD, '
                      'no prediction clipped and no threshold added',
            'fixed_before_reading_any_result': {
                'D_FL_bin_edges': [x if np.isfinite(x) else str(x) for x in DFL_BIN_EDGES],
                'excess_tolerance': EXCESS_TOL, 'tie_tolerance': TOL},
            'inputs': {'round4_rows': sha(ROWS_GZ), 'grid': sha(GRID), 'bler': sha(BLER),
                       'payload_chain': sha(CHAIN)},
            'B_F_qam_symbols': B_F_sym, 'n_cw_F': n_cw_F,
            'A2_high_reliability_cells': a2,
            'B1_identity_check': b1,
            'B2_per_cell': b2, 'B2_pooled_supplementary': b2_pooled,
            'B3_training': b3, 'B4_wider': b4,
            'C1_rayleigh_cells': c1, 'C1_underflowed_cells_db': underflowed,
            'C2_out_of_bounds': c2, 'C3_cost': c3, 'C4_direction': c4,
            'deferred': {
                'caluclate_tp_fp_identity_record': 'deferred; OpenCOOD is not modified this round',
                'point_cloud_neighbourhood_density': 'deferred; no point cloud is loaded this round',
                'which_objects_F_recovered': 'open item; needs the clean boxes re-saved from an '
                                             'intermediate-fusion forward, whose cost is already '
                                             'on the record'},
            'command': 'python projects/ca_tosg_p2/protocol/r24_two_questions.py'}


def cap1(t):
    return t[:1].upper() + t[1:]


def markdown(m):
    a2, b1 = m['A2_high_reliability_cells'], m['B1_identity_check']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/r24_two_questions.py -- do not edit by hand -->',
         '# Two questions, answered from stored products (P2-R24)', '',
         f"**{cap1(m['status'])}.**", '',
         f"**Fixed before any result was read.** Tie tolerance {m['fixed_before_reading_any_result']['tie_tolerance']:g}; "
         f"excess tolerance {m['fixed_before_reading_any_result']['excess_tolerance']:g}; the D_FL bin "
         'edges are module constants.', '',
         '## A-2 The six high-reliability cells', '',
         f"Per-frame `q_F`, `q_L` and `D_FL` are **identical across all six cells**: "
         f"{a2['identical_across_cells']}. Every maximum absolute difference against the reference "
         'cell is zero, so the six cells carry one set of information, not six.', '',
         '| cell | frames | max |Δq_F| | max |Δq_L| | max |ΔD_FL| |', '|---|---:|---:|---:|---:|']
    for k, v in a2['per_cell'].items():
        L.append(f"| {k} | {v['frames']:,} | {v['max_abs_q_F_diff']:.1e} | "
                 f"{v['max_abs_q_L_diff']:.1e} | {v['max_abs_D_FL_diff']:.1e} |")
    fc = a2['frame_counts']
    L += ['', f"**Unique frames: {a2['unique_frames']:,}** — F ahead {fc['F ahead']:,}, L ahead "
          f"{fc['L ahead']:,}, tie {fc['tie']:,}. All high-reliability statistics below are per cell, "
          'each cell holding one row per frame.', '',
          f"{cap1(a2['point_estimate_wording'])}. {cap1(a2['upper_bound_wording'])}.", '',
          '## B-1 The two routes to D_FL agree', '',
          f"`dF_true - dL_true` against `Q_F - Q_L` from the Q table: largest absolute difference "
          f"**{b1['max_abs_difference']:.2e}**, rows whose classification at TOL = "
          f"{b1['tol']:g} changes: **{b1['rows_whose_TOL_class_changes']}**. {cap1(b1['reading'])}.",
          '', '## B-2 Can the F-versus-L advantage be predicted, per cell', '',
          '| cell | rows | corr | sign agreement | true separation | predicted separation |',
          '|---|---:|---:|---:|---:|---:|']
    for k, v in m['B2_per_cell'].items():
        sep = v['separation']
        L.append(f"| {k} | {v['rows']:,} | "
                 + (f"{v['corr']:.4f}" if v['corr'] is not None else '—')
                 + f" | {v['sign_agreement'] * 100:.1f} % | "
                 + (f"{sep['true_separation']:+.5f}" if sep['true_separation'] is not None else '—')
                 + ' | '
                 + (f"{sep['pred_separation']:+.5f}" if sep['pred_separation'] is not None else '—')
                 + ' |')
    p = m['B2_pooled_supplementary']
    L += ['', f"Pooled over the six cells, as a supplement and not a replacement for the per-cell "
          f"rows: corr " + (f"{p['corr']:.4f}" if p['corr'] is not None else '—')
          + f", sign agreement {p['sign_agreement'] * 100:.1f} %.", '',
          '### Behaviour by how large the true advantage is (first high-reliability cell)', '',
          '| bin on D_FL | rows | mean true D_FL | mean predicted D_FL | sign correct |',
          '|---|---:|---:|---:|---:|']
    first = m['B2_per_cell'][next(iter(m['B2_per_cell']))]
    for b in first['bins']:
        L.append(f"| {b['bin']} | {b['rows']:,} | {b['mean_true']:+.5f} | {b['mean_pred']:+.5f} | "
                 f"{b['sign_correct'] * 100:.1f} % |")
    b3 = m['B3_training']
    L += ['', '## B-3 The same thing in sample', '',
          f"Training predictions are present in the round-4 product. {cap1(b3['note'])}: each "
          f"frame-cell appears {b3['repetitions_per_row']} times.", '',
          '| view | rows | corr | sign agreement | true separation | predicted separation |',
          '|---|---:|---:|---:|---:|---:|']
    for v in (b3['high_reliability'],):
        sep = v['separation']
        L.append(f"| {v['label']} | {v['rows']:,} | "
                 + (f"{v['corr']:.4f}" if v['corr'] is not None else '—')
                 + f" | {v['sign_agreement'] * 100:.1f} % | "
                 + (f"{sep['true_separation']:+.5f}" if sep['true_separation'] is not None else '—')
                 + ' | '
                 + (f"{sep['pred_separation']:+.5f}" if sep['pred_separation'] is not None else '—')
                 + ' |')
    L += ['', '## B-4 Wider subsets, held out', '',
          '| subset | rows | corr | sign agreement |', '|---|---:|---:|---:|']
    for k, v in m['B4_wider'].items():
        L.append(f"| {k} | {v['rows']:,} | " + (f"{v['corr']:.4f}" if v['corr'] is not None else '—')
                 + f" | {v['sign_agreement'] * 100:.1f} % |")
    L += ['', '## C-1 What the Rayleigh cells allow', '',
          f"{cap1(m['C2_out_of_bounds']['definition'])}.", '',
          '| SNR | p_cw | q_F (point) | counts | p_cw upper95 | q_F under that limit | q_F underflowed |',
          '|---:|---:|---:|---|---:|---:|:---:|']
    for r in m['C1_rayleigh_cells']:
        L.append(f"| {r['snr_db']} | {r['p_cw']:.5g} | {r['q_F_point_estimate']:.3g} | "
                 f"{r['counts'] or '—'} | "
                 + (f"{r['p_cw_upper95']:.3g}" if r['p_cw_upper95'] is not None else '—') + ' | '
                 + (f"{r['q_F_under_upper_limit']:.3g}" if r['q_F_under_upper_limit'] is not None else '—')
                 + f" | {'yes' if r['q_F_underflowed_to_zero'] else 'no'} |")
    L += ['', f"Cells whose q_F underflows to zero in double precision: "
          + (', '.join(f'{s} dB' for s in m['C1_underflowed_cells_db']) or 'none')
          + '. Where q_F is zero the analytic range collapses to the single point zero, so any '
          'non-zero prediction is outside it by construction. That is a statement about the range, '
          'not yet about the decisions.', '',
          '## C-2 How far outside the range the predictions fall', '',
          f"An excess is counted as a decision only above {m['C2_out_of_bounds']['tolerance']:g}; "
          'anything smaller is floating-point noise and is counted separately.', '',
          '| SNR | rows | above upper | below lower | float noise | above p50 | above p90 | above max |',
          '|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in m['C2_out_of_bounds']['per_cell']:
        L.append(f"| {r['snr_db']} | {r['rows']:,} | {r['above_upper_rows']:,} "
                 f"({r['above_upper_share'] * 100:.1f} %) | {r['below_lower_rows']:,} "
                 f"({r['below_lower_share'] * 100:.1f} %) | {r['float_noise_rows']:,} | "
                 + ' | '.join((f"{r[k]:.2e}" if r[k] is not None else '—')
                              for k in ('above_excess_p50', 'above_excess_p90', 'above_excess_max'))
                 + ' |')
    L += ['', '## C-3 What those requests actually cost', '',
          'Scene-equal contributions, and beside them the request count and the average loss of a '
          'request, which are different quantities and are not mixed.', '',
          '| SNR | category | requests | loss contribution | QAM contribution | mean loss per request |',
          '|---:|---|---:|---:|---:|---:|']
    for r in m['C3_cost']:
        for name in ('above_upper', 'below_lower', 'in_bounds'):
            v = r[name]
            L.append(f"| {r['snr_db']} | `{name}` | {v['requests']:,} | "
                     f"{v['loss_contribution']:+.6f} | {v['qam_contribution']:,.0f} | "
                     + (f"{v['mean_loss_per_request']:+.5f}" if v['mean_loss_per_request'] is not None
                        else '—') + ' |')
    c4 = m['C4_direction']
    L += ['', '## C-4 Does the prediction move across cells the way the truth would', '',
          f"{cap1(c4['method'])}.", '']
    for c, e in c4['per_channel'].items():
        L += [f"### {c}", '',
              f"Cells usable for the test: {e['usable_cells_db'] or 'none'}; excluded for q_F "
              f"underflow: {e['excluded_for_underflow_db'] or 'none'}.", '']
        if not e['determinable']:
            L += [f"**Not determinable.** {cap1(e['reason'])}.", '']
        else:
            L += [f"Compared at {e['compared_cells_db'][0]} dB and {e['compared_cells_db'][1]} dB, "
                  f"where q_F is {e['q_F_at_those_cells'][0]:.3g} and "
                  f"{e['q_F_at_those_cells'][1]:.3g}. Over {e['frames']:,} frames "
                  f"({e['frames_expected_up']:,} expected to rise, {e['frames_expected_down']:,} to "
                  f"fall, {e['frames_expected_flat']:,} to stay), "
                  f"**{e['share_matching_expected_direction'] * 100:.1f} %** move in the expected "
                  f"direction. Where they contradict it, the mean size of the move is "
                  f"{e['mean_deviation_when_contradicting']:.5f} and the largest is "
                  f"{e['max_deviation_when_contradicting']:.5f}.", '']
    L += ['## Deferred and open', '']
    for k, v in m['deferred'].items():
        L.append(f"* `{k}` — {v}.")
    L += ['', '## Inputs', '', '| file | sha256 |', '|---|---|']
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
        print('r24 two questions:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
