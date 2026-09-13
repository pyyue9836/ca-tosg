#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R13 C/D — recompute BOTH arms from the newly measured AWGN p_cw, and judge each point.

C-1 is the point of this file: `Q_F = q_F·F1_clean + (1−q_F)·F1_ego` and
`Q_L = q_L·L1_clean + (1−q_L)·F1_ego` are recomputed from the *same* new p_cw and compared as
`Q_F − Q_L`. L is **not** held at its old value while only F is updated. That matters here: q_L uses
a per-frame N_cw,L between 2 and 21 codewords, so around p_cw ~ 1e-4 the L arm is also losing
messages, and a comparison that froze L would credit F with a margin it has not earned.

C-2 The crossing this produces is an **average-performance crossing estimate under the current data,
scene weights and message model**. It is not a per-frame reliability rule and not a link requirement.

C-3 The new points are written to a **new versioned grid file**. P1's `bler_sionna.csv` and
`v2_grid_validate_ideal.csv` are not modified.

D-1 Each point is reported as supporting L, supporting the complete F, or not distinguishable — the
last whenever the uncertainty carried through from the measurement leaves the sign of Q_F − Q_L open.
D-2 If the crossing cannot be bracketed, it is reported as undetermined. No threshold is forced.

    python awgn_fill_eval.py --selfcheck   # reconstruction guard alone (needs no measurement)
    python awgn_fill_eval.py               # full recomputation (needs bler_awgn_fill.json)
    python awgn_fill_eval.py --check       # byte-reproduce the report
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
V2 = os.path.join(ROOT, 'results', 'v2')
GRID = os.path.join(V2, 'v2_grid_validate_ideal.csv')
WP5 = os.path.join(V2, 'wp5_final_validate.csv')
WP34 = os.path.join(V2, 'wp34_e_l_validate.csv')
CHAIN = os.path.join(V2, 'payload_chain.json')
A5_JSON = os.path.join(HERE, 'four_arm_eval.json')
FILL_JSON = os.path.join(P2, 'results', 'channel', 'bler_awgn_fill.json')
NEW_GRID = os.path.join(P2, 'results', 'grid', 'v2_grid_validate_ideal_p2r13fill.csv')
OUT_JSON = os.path.join(HERE, 'awgn_fill_eval.json')
OUT_MD = os.path.join(HERE, 'awgn_fill_eval.md')
N_BOOT, BOOT_SEED = 10000, 20260809          # P1's settings, unchanged
SYM_PER_CW = 250                             # 1000 coded bits / 4 bits per 16-QAM symbol


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def scene_equal(v, scenes):
    return float(np.mean([v[scenes == s].mean() for s in np.unique(scenes)]))


def boot(v, scenes, seed=BOOT_SEED):
    u = np.unique(scenes)
    means = np.array([v[scenes == s].mean() for s in u])
    rng = np.random.default_rng(seed)
    bs = means[rng.integers(0, len(u), (N_BOOT, len(u)))].mean(axis=1)
    return {'mean': float(means.mean()), 'lcb95': float(np.percentile(bs, 2.5)),
            'ucb95': float(np.percentile(bs, 97.5))}


# --------------------------------------------------------------- frame table
def load_frames():
    """Per-frame quantities that do not depend on the channel, plus a guard proving they don't."""
    g = pd.read_csv(GRID)
    w5 = pd.read_csv(WP5, usecols=['frame', 'f1_clean', 'f1_ego']).set_index('frame')
    w34 = pd.read_csv(WP34, usecols=['frame', 'f1_L']).set_index('frame')

    # B_L must be a property of the frame, not of the cell, or "N_cw,L per frame" is meaningless
    spread = g.groupby('sample_id').B_L.agg(lambda s: s.max() - s.min()).max()
    if spread > 0:
        raise SystemExit(f'B_L varies across cells for the same frame (max spread {spread:g}) -- stop')

    t = g[(g.channel == 'awgn') & (g.snr_db == 8)].copy().reset_index(drop=True)
    p8 = float(t.p_cw.iloc[0])

    # N_cw,L derived two independent ways from the data's own columns, never typed in
    n_from_B = t.B_L.to_numpy() * 1e6 / SYM_PER_CW
    n_from_q = np.log(t.q_L.to_numpy()) / np.log(1.0 - p8)
    if np.abs(n_from_B - np.round(n_from_B)).max() > 1e-9:
        raise SystemExit('N_cw,L from B_L is not integral -- stop')
    if np.abs(np.round(n_from_q) - n_from_B).max() > 0:
        raise SystemExit('N_cw,L from q_L disagrees with N_cw,L from B_L -- stop')
    t['n_cw_L'] = np.round(n_from_B).astype(int)

    t['f1_clean'] = w5.f1_clean.loc[t.sample_id].to_numpy()
    t['f1_ego'] = w5.f1_ego.loc[t.sample_id].to_numpy()
    t['f1_L'] = w34.f1_L.loc[t.sample_id].to_numpy()
    if float(np.abs(t.eff_E.to_numpy() - t.f1_ego.to_numpy()).max()) > 1e-12:
        raise SystemExit('eff_E is not the ego-only F1 -- stop')
    n_cw_F = json.load(open(CHAIN))['F']['n_cw']
    return g, t, int(n_cw_F)


def arms_at(t, n_cw_F, p):
    """Both arms at one per-codeword loss p. Returns (Q_F, Q_L, q_F, q_L) as per-frame arrays."""
    q_F = (1.0 - p) ** n_cw_F
    q_L = (1.0 - p) ** t.n_cw_L.to_numpy()
    Q_F = q_F * t.f1_clean.to_numpy() + (1.0 - q_F) * t.f1_ego.to_numpy()
    Q_L = q_L * t.f1_L.to_numpy() + (1.0 - q_L) * t.f1_ego.to_numpy()
    return Q_F, Q_L, float(q_F), q_L


def reconstruction_guard(g, t, n_cw_F):
    """Rebuild the committed AWGN cells from their own p_cw and require an exact match.

    This is the licence for everything below: if the rebuild reproduces P1's stored eff_L and its
    constructed eff_F at the committed points, the same code applied to the new p_cw is trustworthy.
    """
    out = []
    for s in sorted(g[g.channel == 'awgn'].snr_db.unique()):
        cell = g[(g.channel == 'awgn') & (g.snr_db == s)].set_index('sample_id').loc[t.sample_id]
        p = float(cell.p_cw.iloc[0])
        Q_F, Q_L, q_F, q_L = arms_at(t, n_cw_F, p)
        d_L = float(np.abs(Q_L - cell.eff_L.to_numpy()).max())
        d_q = float(np.abs(q_L - cell.q_L.to_numpy()).max())
        if d_L > 1e-12 or d_q > 1e-12:
            raise SystemExit(f'reconstruction guard failed at {s} dB: eff_L {d_L:g}, q_L {d_q:g}')
        out.append({'snr_db': int(s), 'p_cw': p, 'max_abs_diff_eff_L': d_L, 'max_abs_diff_q_L': d_q})
    return out


# ------------------------------------------------------------------ the work
def diff_at(t, n_cw_F, p):
    """Scene-equal Q_F − Q_L at one p."""
    Q_F, Q_L, _, _ = arms_at(t, n_cw_F, p)
    sc = t.scene.to_numpy()
    return scene_equal(Q_F, sc) - scene_equal(Q_L, sc)


def break_even_p(t, n_cw_F, lo=1e-12, hi=1e-2):
    """The p at which scene-equal Q_F equals scene-equal Q_L, both recomputed (C-1).

    Bisection, after checking the sign actually changes: raising p costs F far more than L (12,567
    codewords against 2-21), so the difference is decreasing in p -- verified, not assumed."""
    f_lo, f_hi = diff_at(t, n_cw_F, lo), diff_at(t, n_cw_F, hi)
    # The difference is NOT monotone over the whole range and it would be wrong to claim it is:
    # once p is large enough that q_F is negligible, Q_F is pinned at the ego value while Q_L keeps
    # falling towards it, so the difference turns and climbs back towards 0. The turning point is
    # located here rather than assumed away.
    pp = np.logspace(-12, -2, 401)
    ff = np.array([diff_at(t, n_cw_F, x) for x in pp])
    turn = int(np.argmin(ff))
    mono_below = bool(all(ff[i] >= ff[i + 1] - 1e-15 for i in range(turn)))
    reg = {'monotone_decreasing_below_p': float(pp[turn]), 'verified_monotone_below_turn': mono_below,
           'turning_point_note': 'above this p the complete F is already lost with near-certainty, so '
                                 'Q_F stops falling while Q_L is still falling and the difference '
                                 'climbs back towards zero. The crossing lies far below it'}
    if f_lo <= 0 or f_hi >= 0:
        return dict(reg, exists=False,
                    reason=f'no sign change over [{lo:g}, {hi:g}]: f(lo)={f_lo:+.6f}, f(hi)={f_hi:+.6f}')
    for _ in range(200):
        mid = math_sqrt(lo, hi)
        if diff_at(t, n_cw_F, mid) > 0:
            lo = mid
        else:
            hi = mid
    pstar = 0.5 * (lo + hi)
    out = dict(reg, exists=True, p_cw=pstar, q_F_at_break_even=float((1.0 - pstar) ** n_cw_F))
    if os.path.exists(A5_JSON):
        a5 = json.load(open(A5_JSON))['A5_break_even']['awgn_break_even']
        out['a5_comparison'] = {
            'a5_p_cw_threshold': a5['p_cw_threshold'], 'a5_q_F_threshold': a5['q_F_threshold'],
            'relative_difference': float(pstar / a5['p_cw_threshold'] - 1.0),
            'source': 'four_arm_eval.json, read rather than retyped'}
    return out


def math_sqrt(a, b):
    """Geometric midpoint -- the quantity spans orders of magnitude, so bisect in log space."""
    return float(np.sqrt(a * b))


def evaluate_point(t, n_cw_F, r):
    """One measured point: both arms, the interval carried through, and the D-1 verdict."""
    sc = t.scene.to_numpy()
    p_lo, p_hi = r['wilson95_lo'], r['wilson95_hi']
    if r['n_err'] == 0:                       # A-2: zero errors is an upper bound, never a zero
        p_lo, p_hi = 0.0, r['one_sided_upper95']
        interval_kind = 'one-sided 95 % upper limit (no error observed)'
        p_point = None
    else:
        interval_kind = 'two-sided Wilson 95 %'
        p_point = r['p_hat']

    def at(p):
        Q_F, Q_L, q_F, q_L = arms_at(t, n_cw_F, p)
        return {'p_cw': p, 'q_F': q_F, 'q_L_mean': float(q_L.mean()),
                'Q_F': scene_equal(Q_F, sc), 'Q_L': scene_equal(Q_L, sc),
                'Q_E': scene_equal(t.f1_ego.to_numpy(), sc),
                'Q_F_minus_Q_L': scene_equal(Q_F, sc) - scene_equal(Q_L, sc)}

    # The range of Q_F - Q_L over the p interval is taken from a dense probe INSIDE that interval,
    # not from its two endpoints: the difference is not monotone everywhere, so an endpoint mapping
    # would only be valid under an assumption this makes unnecessary.
    best, worst = at(p_lo), at(p_hi)
    probe = np.unique(np.concatenate([[p_lo, p_hi], np.linspace(p_lo, p_hi, 201)]))
    vals = np.array([diff_at(t, n_cw_F, float(x)) for x in probe])
    d_lo, d_hi = float(vals.min()), float(vals.max())
    endpoints_are_extremes = bool(abs(vals[0] - d_hi) < 1e-15 and abs(vals[-1] - d_lo) < 1e-15)

    if d_lo > 0:
        verdict, basis = 'supports complete F', 'Q_F − Q_L stays positive across the whole interval'
    elif d_hi < 0:
        verdict, basis = 'supports L', 'Q_F − Q_L stays negative across the whole interval'
    else:
        verdict, basis = ('not distinguishable',
                          'the sign of Q_F − Q_L is not settled by this measurement: the interval on '
                          'p_cw straddles the point where the two arms are equal')

    out = {'esno_db': r['esno_db'], 'n_cw': r['n_cw'], 'n_err': r['n_err'],
           'p_point_estimate': p_point, 'p_interval': [p_lo, p_hi], 'interval_kind': interval_kind,
           'at_p_low': best, 'at_p_high': worst,
           'Q_F_minus_Q_L_interval': [d_lo, d_hi],
           'range_from': 'dense probe of 201 points inside the p interval',
           'endpoints_are_the_extremes': endpoints_are_extremes,
           'verdict': verdict, 'basis': basis}
    if p_point is not None:
        out['at_p_point'] = at(p_point)
        Q_F, Q_L, _, _ = arms_at(t, n_cw_F, p_point)
        out['bootstrap_Q_F_minus_Q_L'] = boot(Q_F - Q_L, sc)
        out['bootstrap_note'] = ('scene-level resampling of the perception side at the point estimate; '
                                 'it does not carry the channel measurement uncertainty, which is what '
                                 'the interval above does')
    return out


def write_new_grid(g, t, n_cw_F, rows, srcs):
    """C-3: a NEW versioned grid file. P1's grid is not touched."""
    keep = list(g.columns)
    base = g.copy()
    base['source'] = 'P1 v2_grid_validate_ideal.csv'
    add = []
    # columns that belong to P1's partial-recovery construction are left empty rather than invented
    p1_only = [c for c in ('p_cw_F', 'q_msg_F_descriptive') if c in keep]
    const_cols = [c for c in ('has_collaborator', 'F_feasible', 'L_feasible', 'B_E', 'B_L', 'B_F')
                  if c in keep]
    for c in const_cols:                      # only copy what is genuinely frame-constant
        spread = g.groupby('sample_id')[c].nunique().max()
        if spread != 1:
            raise SystemExit(f'{c} is not constant per frame; refusing to copy it to the new rows')
    for r in rows:
        if r['esno_db'] in (8.0, 10.0):       # reproduction points: reported, not added to the grid
            continue
        p = r['p_hat'] if r['n_err'] else 0.0
        Q_F, Q_L, q_F, q_L = arms_at(t, n_cw_F, p)
        d = pd.DataFrame({'sample_id': t.sample_id, 'scene': t.scene,
                          'snr_db': r['esno_db'], 'channel': 'awgn',
                          'p_cw': p, 'q_L': q_L, 'eff_E': t.f1_ego, 'eff_L': Q_L, 'eff_F': Q_F})
        for c in const_cols:
            d[c] = t[c].to_numpy()
        for c in p1_only:
            d[c] = ''
        d['source'] = 'P2-R13 measured fill'
        d['p_cw_is_upper_bound'] = bool(r['n_err'] == 0)
        d['n_cw_measured'] = r['n_cw']
        d['n_err_measured'] = r['n_err']
        add.append(d)
    out = pd.concat([base] + add, ignore_index=True, sort=False)
    os.makedirs(os.path.dirname(NEW_GRID), exist_ok=True)
    out.to_csv(NEW_GRID, index=False)
    return {'path': os.path.relpath(NEW_GRID, ROOT), 'rows': int(len(out)),
            'rows_added': int(sum(len(d) for d in add)),
            'added_snr_points': sorted({float(d.snr_db.iloc[0]) for d in add}),
            'p1_grid_untouched_sha256': srcs['grid'],
            'note': 'the added rows carry p_cw from the P2-R13 measurement; where no error was '
                    'observed the stored p_cw is 0 and p_cw_is_upper_bound is True, so no consumer '
                    'can read it as a measured zero without seeing the flag'}


def build():
    if not os.path.exists(FILL_JSON):
        raise SystemExit(f'measurement not present: {os.path.relpath(FILL_JSON, ROOT)}')
    fill = json.load(open(FILL_JSON))
    g, t, n_cw_F = load_frames()
    srcs = {'grid': sha(GRID), 'wp5': sha(WP5), 'wp34': sha(WP34), 'fill': sha(FILL_JSON)}
    guard = reconstruction_guard(g, t, n_cw_F)
    pts = [evaluate_point(t, n_cw_F, r) for r in fill['rows']]
    be = break_even_p(t, n_cw_F)

    # D-2: bracket the crossing using only the verdicts, and say so when it cannot be bracketed
    order = sorted(pts, key=lambda r: r['esno_db'])
    lastL = [r['esno_db'] for r in order if r['verdict'] == 'supports L']
    firstF = [r['esno_db'] for r in order if r['verdict'] == 'supports complete F']
    undec = [r['esno_db'] for r in order if r['verdict'] == 'not distinguishable']
    if lastL and firstF and max(lastL) < min(firstF):
        bracket = {'bracketed': True, 'between_db': [max(lastL), min(firstF)],
                   'undetermined_points_db': [x for x in undec if max(lastL) < x < min(firstF)]}
    else:
        bracket = {'bracketed': False,
                   'reason': 'the measured points do not produce an L-side point below an F-side point',
                   'undetermined_points_db': undec}
    if bracket['bracketed'] and bracket['undetermined_points_db']:
        bracket['reading'] = ('the crossing lies inside this interval, but points inside it are '
                              'themselves undetermined, so it is not narrowed further')

    grid = write_new_grid(g, t, n_cw_F, fill['rows'], srcs)
    return {'schema': 'catosg-p2-awgn-fill-eval/1',
            'registered_in': 'projects/ca_tosg_p2/protocol/p2_protocol.md, Amendment 3 (P2-R13)',
            'what': 'Both arms recomputed from the same measured p_cw (C-1). Table work only: no '
                    'perception inference was run and no held-out split was touched.',
            'n_cw_F': n_cw_F,
            'n_cw_L_range': [int(t.n_cw_L.min()), int(t.n_cw_L.max())],
            'inputs': srcs, 'reconstruction_guard': guard,
            'break_even': be, 'points': pts, 'crossing': bracket, 'new_grid': grid,
            'C2_status_of_the_threshold':
                'an average-performance crossing estimate under the current data, scene weights and '
                'message model -- not a per-frame reliability rule and not a link-layer requirement',
            'command': 'python projects/ca_tosg_p2/protocol/awgn_fill_eval.py'}


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/awgn_fill_eval.py -- do not edit by hand -->',
         '# Both arms recomputed from the measured AWGN p_cw (P2-R13 C/D)', '',
         f"**What this is.** {m['what']}", '',
         f"**Registered in** `{m['registered_in']}` before the measurement ran.", '',
         '## C-1 Both sides move together', '',
         f"`Q_F = q_F·F1_clean + (1−q_F)·F1_ego` with q_F = (1−p_cw)^{m['n_cw_F']:,}, and "
         f"`Q_L = q_L·L1_clean + (1−q_L)·F1_ego` with q_L = (1−p_cw)^N_cw,L and N_cw,L between "
         f"{m['n_cw_L_range'][0]} and {m['n_cw_L_range'][1]} codewords per frame. Both are recomputed "
         'from the same p_cw. L is not held at its old value.', '',
         '**Reconstruction guard.** Rebuilding the committed AWGN cells from their own p_cw reproduces '
         "P1's stored `eff_L` and `q_L` exactly, which is what licenses applying the same code to the "
         'new points:', '', '| SNR (dB) | p_cw | max abs diff in eff_L | max abs diff in q_L |',
         '|---:|---:|---:|---:|']
    for r in m['reconstruction_guard']:
        L.append(f"| {r['snr_db']} | {r['p_cw']:.5g} | {r['max_abs_diff_eff_L']:.1e} | "
                 f"{r['max_abs_diff_q_L']:.1e} |")
    be = m['break_even']
    L += ['', '## The recomputed crossing', '']
    if be['exists']:
        L += [f"With both arms moving, the scene-equal `Q_F` equals the scene-equal `Q_L` at "
              f"**p_cw = {be['p_cw']:.4g}** (q_F = {be['q_F_at_break_even']:.4f}).", '']
        if 'a5_comparison' in be:
            ac = be['a5_comparison']
            rd = ac['relative_difference']
            L += [f"A-5 obtained {ac['a5_p_cw_threshold']:.4g} (q_F {ac['a5_q_F_threshold']:.4f}) by "
                  'holding q_L at 1. Recomputing both arms moves it by '
                  f"**{rd * 100:+.2f} %**, so that approximation was "
                  f"{'sound here' if abs(rd) < 0.01 else 'NOT sound here and the recomputed value is the one to use'}"
                  ': at the crossing the L message spans at most '
                  f"{m['n_cw_L_range'][1]} codewords, so q_L is within {(1 - (1 - be['p_cw']) ** m['n_cw_L_range'][1]) * 100:.3f} % of 1. "
                  f"The value used below is the recomputed one. ({ac['source']}.)", '']
    else:
        L += [f"No crossing exists in the searched range: {be['reason']}.", '']
    L += [f"**Monotonicity, stated rather than assumed.** Q_F − Q_L falls with p_cw only up to "
          f"p_cw ≈ {be['monotone_decreasing_below_p']:.2g}"
          f" ({'verified' if be['verified_monotone_below_turn'] else '**not verified**'}); "
          f"{be['turning_point_note']}. The intervals below are therefore taken from a dense probe "
          'inside each point\'s own p interval, not by mapping its two endpoints.',
          '', f"**What this number is.** {m['C2_status_of_the_threshold']}.", '',
          '## D-1 Per point', '',
          'Each point is judged by the interval carried through from the measurement, not by a point '
          'estimate. A zero-error point is carried through as `[0, one-sided 95 % upper limit]`.', '',
          '| Es/N0 (dB) | k / N | p_cw interval | Q_F − Q_L interval | verdict |',
          '|---:|---:|---|---|---|']
    for r in m['points']:
        lo, hi = r['p_interval']
        dlo, dhi = r['Q_F_minus_Q_L_interval']
        L.append(f"| {r['esno_db']:.1f} | {r['n_err']:,} / {r['n_cw']:,} | "
                 f"[{lo:.3g}, {hi:.3g}] | [{dlo:+.5f}, {dhi:+.5f}] | **{r['verdict']}** |")
    L += ['', 'Basis, point by point:', '']
    for r in m['points']:
        L.append(f"* **{r['esno_db']:.1f} dB** — {r['basis']}. Interval kind: {r['interval_kind']}.")
    L += ['', '### Values at the point estimates', '',
          '| Es/N0 (dB) | p_cw | q_F | mean q_L | Q_E | Q_L | Q_F | Q_F − Q_L | scene bootstrap |',
          '|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in m['points']:
        if 'at_p_point' not in r:
            L.append(f"| {r['esno_db']:.1f} | no error observed | — | — | — | — | — | — | — |")
            continue
        a = r['at_p_point']; b = r['bootstrap_Q_F_minus_Q_L']
        L.append(f"| {r['esno_db']:.1f} | {a['p_cw']:.3g} | {a['q_F']:.4f} | {a['q_L_mean']:.6f} | "
                 f"{a['Q_E']:.5f} | {a['Q_L']:.5f} | {a['Q_F']:.5f} | {a['Q_F_minus_Q_L']:+.5f} | "
                 f"[{b['lcb95']:+.5f}, {b['ucb95']:+.5f}] |")
    L += ['', 'The bootstrap column resamples scenes at the point estimate and therefore carries the '
          'perception-side spread only; the channel measurement uncertainty is the interval column '
          'above. They are different quantities and are not combined.', '',
          '## D-2 Where the crossing sits', '']
    cr = m['crossing']
    if cr['bracketed']:
        a, b = cr['between_db']
        L.append(f"The crossing is bracketed between **{a:.1f} dB and {b:.1f} dB**.")
        if cr.get('undetermined_points_db'):
            L.append('')
            L.append('It is **not narrowed further**: '
                     + ', '.join(f'{x:.1f} dB' for x in cr['undetermined_points_db'])
                     + ' lie inside that interval and are themselves undetermined.')
    else:
        L.append(f"**The crossing is undetermined.** {cr['reason']}."
                 + (' Undetermined points: ' + ', '.join(f'{x:.1f} dB' for x in cr['undetermined_points_db'])
                    + '.' if cr['undetermined_points_db'] else ''))
    L += ['', 'No threshold is forced and no value is interpolated across the gap.', '',
          '## C-3 The new grid file', '']
    ng = m['new_grid']
    L += [f"`{ng['path']}` — {ng['rows']:,} rows, of which {ng['rows_added']:,} are new "
          f"({', '.join(f'{x:.1f} dB' for x in ng['added_snr_points'])} on AWGN). {ng['note']}.", '',
          f"P1's `results/v2/v2_grid_validate_ideal.csv` is unchanged (sha256 "
          f"`{ng['p1_grid_untouched_sha256'][:16]}…`), and `results/channel/bler_sionna.csv` is not "
          'written by this line of work at all.', '',
          '## Inputs', '', '| file | sha256 |', '|---|---|']
    for k, v in m['inputs'].items():
        L.append(f"| {k} | `{v[:16]}…` |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--selfcheck', action='store_true')
    a = ap.parse_args()
    if a.selfcheck:
        g, t, n_cw_F = load_frames()
        rows = reconstruction_guard(g, t, n_cw_F)
        print(f'reconstruction guard: {len(rows)} AWGN cells rebuilt from p_cw, '
              f'max |diff| in eff_L = {max(r["max_abs_diff_eff_L"] for r in rows):.1e}, '
              f'in q_L = {max(r["max_abs_diff_q_L"] for r in rows):.1e}')
        print(f'N_cw,F = {n_cw_F:,}; N_cw,L per frame in [{t.n_cw_L.min()}, {t.n_cw_L.max()}]')
        be = break_even_p(t, n_cw_F)
        print('recomputed break-even (both arms):', json.dumps(be))
        return 0
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = (os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js
              and os.path.exists(OUT_MD) and open(OUT_MD).read() == md)
        print('awgn fill eval:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js)
    open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
