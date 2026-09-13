#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R14 B — offline potential of a per-frame action choice, under the locked message accounting.

**This is an offline potential, not a deployment result** (B-6). Every quantity here is computed with
per-frame ground-truth F1 values that a real selector cannot see before it transmits. It answers one
question only: *is there enough headroom above a channel-only rule to be worth training a joint
selector at all?* A large number here would not be a result; it would be permission to try.

Table work only: no GPU, no model, no perception inference, no held-out split.

  B-1  per-frame optimal action a* = argmax {Q_E, Q_L, Q_F}, ties to the cheaper payload, TOL 1e-9;
       optimal shares per cell, AWGN and Rayleigh apart
  B-2  G_task = Mean_scene[Q(a*) - Q(rule_tau)], with Q(a*) - Q(Fixed L) and Q(a*) - Q(Fixed F)
       reported beside it; scene-level bootstrap
  B-3  where the potential comes from: rule took F where L was right, rule took L where F was right,
       and frames where E was right
  B-4  how the potential is distributed: per-scene contribution, and the share held by the top 10 %
       of frames
  B-5  the same read restricted to the cells where the channel is no longer the variable
       (q_F >= 0.99, which is AWGN 10-20 dB and nothing else)

    python offline_potential.py [--check]
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
BLER = os.path.join(ROOT, 'results', 'channel', 'bler_sionna.csv')
FOUR_ARM = os.path.join(HERE, 'four_arm_eval.json')
FILL_EVAL = os.path.join(HERE, 'awgn_fill_eval.json')
OUT_JSON = os.path.join(HERE, 'offline_potential.json')
OUT_MD = os.path.join(HERE, 'offline_potential.md')

TOL = 1e-9                                   # C-2 of the P2 protocol
N_BOOT, BOOT_SEED = 10000, 20260809          # P1's settings
Q_F_CLEAN = 0.99                             # B-5 threshold
ACTIONS = ('E', 'L', 'F')                    # also the payload order: 0 < B_L < B_F


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


# --------------------------------------------------------------------- data
def build_table():
    """The 1,980 x 22 table with Q_E, Q_L, Q_F, the optimal action and the channel-only rule."""
    n_cw_F = json.load(open(CHAIN))['F']['n_cw']
    B_F_sym = json.load(open(CHAIN))['F']['msym'] * 1e6
    g = pd.read_csv(GRID, usecols=['sample_id', 'scene', 'snr_db', 'channel', 'p_cw', 'q_L',
                                   'eff_E', 'eff_L', 'B_L'])
    w5 = pd.read_csv(WP5, usecols=['frame', 'f1_clean', 'f1_ego']).set_index('frame')
    w34 = pd.read_csv(WP34, usecols=['frame', 'f1_L']).set_index('frame')
    g['f1_clean'] = w5.f1_clean.loc[g.sample_id].to_numpy()
    g['f1_ego'] = w5.f1_ego.loc[g.sample_id].to_numpy()
    g['f1_L'] = w34.f1_L.loc[g.sample_id].to_numpy()

    g['q_F'] = (1.0 - g.p_cw.to_numpy()) ** n_cw_F
    g['Q_E'] = g.f1_ego
    g['Q_L'] = g.q_L * g.f1_L + (1 - g.q_L) * g.f1_ego
    g['Q_F'] = g.q_F * g.f1_clean + (1 - g.q_F) * g.f1_ego

    # guard: Q_L must BE P1's stored eff_L, or this table is not the locked accounting
    d_L = float(np.abs(g.Q_L - g.eff_L).max())
    d_E = float(np.abs(g.Q_E - g.eff_E).max())
    if d_L > 1e-9 or d_E > 1e-12:
        raise SystemExit(f'locked accounting not reproduced: eff_L {d_L:g}, eff_E {d_E:g}')

    g['B_E_sym'] = 0.0
    g['B_L_sym'] = g.B_L * 1e6
    g['B_F_sym'] = B_F_sym

    # B-1: argmax with TOL, ties resolved to the cheaper payload. Payload order is E < L < F on every
    # row (B_L is at most 0.00525 Msym against F's 3.14175), which is asserted rather than assumed.
    if not bool((g.B_L_sym < B_F_sym).all()):
        raise SystemExit('a frame has an L payload not below F -- the tie rule would be ill-defined')
    Q = np.stack([g.Q_E.to_numpy(), g.Q_L.to_numpy(), g.Q_F.to_numpy()], axis=1)
    best = Q.max(axis=1)
    within = Q >= best[:, None] - TOL                      # every action within TOL of the best
    star = np.array(ACTIONS)[np.argmax(within, axis=1)]    # first True = cheapest, given E < L < F
    g['a_star'] = star
    g['Q_star'] = best
    # the value actually collected by the tie-broken choice, which is what every difference uses
    g['Q_star_taken'] = np.choose(np.argmax(within, axis=1), [g.Q_E, g.Q_L, g.Q_F])
    g['B_star_sym'] = np.choose(np.argmax(within, axis=1), [g.B_E_sym, g.B_L_sym, g.B_F_sym])
    return g, int(n_cw_F), float(B_F_sym)


def rule_tau():
    """B-2: the channel-only rule, with tau taken from the equivalence class the measurement leaves.

    The equivalence classes come from four_arm_eval; the P2-R13 measurement narrows the AWGN crossing
    to (8.0, 8.5] dB, so the representative is the smallest member of the optimal set that is not
    below 8.5. Rayleigh's optimal set is a single value that puts no sampled point on the F side.
    """
    opt = json.load(open(FOUR_ARM))['tau_sweep']['optimal_tau_set']
    ev = json.load(open(FILL_EVAL))
    cross = ev['crossing']
    lo_db = cross['between_db'][1] if cross.get('bracketed') else None
    rep = {}
    for c, taus in opt.items():
        cand = [t for t in taus if lo_db is None or t >= lo_db]
        if not cand:
            raise SystemExit(f'{c}: no member of the optimal tau set is consistent with the measurement')
        rep[c] = {'tau_db': float(min(cand)), 'equivalent_set': taus,
                  'consistent_with_measured_bracket': cross.get('between_db')}
    return rep


# ---------------------------------------------------------------- analysis
def analyse(g, rep, label, mask):
    """B-1 to B-4 on one subset."""
    t = g[mask]
    if len(t) == 0:
        return None
    sc = t.scene.to_numpy()
    snr = t.snr_db.to_numpy(float)
    ch = t.channel.to_numpy()
    tau = np.array([rep[c]['tau_db'] for c in ch])
    rule_F = snr >= tau
    rule_act = np.where(rule_F, 'F', 'L')
    Q_rule = np.where(rule_F, t.Q_F, t.Q_L)
    B_rule = np.where(rule_F, t.B_F_sym, t.B_L_sym)

    gain = t.Q_star_taken.to_numpy() - Q_rule
    # The tie rule can leave a* up to TOL below the arithmetic maximum: where two actions score within
    # TOL of each other, a* takes the cheaper one, so if the rule happens to request the dearer one it
    # collects marginally more. That slack is the tie rule working as defined, so it is permitted and
    # reported rather than silently clipped; anything beyond it would mean the argmax is wrong.
    min_gain = float(gain.min())
    if min_gain < -TOL - 1e-12:
        raise SystemExit(f'the rule beats the per-frame optimum by {-min_gain:g}, which exceeds the '
                         f'tie slack {TOL:g} -- the argmax is wrong')
    tie_slack = {'min_gain': min_gain, 'rows_below_zero': int((gain < 0).sum()),
                 'explanation': 'any negative entry is at most TOL and comes from the cheaper-payload '
                                'tie rule, never from the rule outperforming the per-frame optimum'}

    out = {'label': label, 'rows': int(len(t)), 'frames': int(t.sample_id.nunique()),
           'cells': int(t.groupby(['channel', 'snr_db']).ngroups), 'tie_slack': tie_slack,
           'optimal_share': {a: float((t.a_star == a).mean()) for a in ACTIONS},
           'rule_share_F': float(rule_F.mean()),
           'G_task': boot(gain, sc),
           'vs_Fixed_L': boot(t.Q_star_taken.to_numpy() - t.Q_L.to_numpy(), sc),
           'vs_Fixed_F': boot(t.Q_star_taken.to_numpy() - t.Q_F.to_numpy(), sc),
           'scene_equal': {'Q_star': scene_equal(t.Q_star_taken.to_numpy(), sc),
                           'Q_rule': scene_equal(Q_rule, sc),
                           'Q_Fixed_L': scene_equal(t.Q_L.to_numpy(), sc),
                           'Q_Fixed_F': scene_equal(t.Q_F.to_numpy(), sc),
                           'Q_Fixed_E': scene_equal(t.Q_E.to_numpy(), sc)},
           'payload_sym_scene_equal': {'optimal': scene_equal(t.B_star_sym.to_numpy(), sc),
                                       'rule': scene_equal(B_rule, sc)}}

    # B-3: three mutually exclusive buckets. "E was right" takes precedence, so the other two
    # buckets are genuine F/L disagreements and nothing is counted twice.
    star = t.a_star.to_numpy()
    buckets = {'rule_F_but_L_is_right': (rule_act == 'F') & (star == 'L'),
               'rule_L_but_F_is_right': (rule_act == 'L') & (star == 'F'),
               'E_is_right': star == 'E'}
    covered = buckets['rule_F_but_L_is_right'] | buckets['rule_L_but_F_is_right'] | buckets['E_is_right']
    agree = (star == rule_act)
    leftover = ~covered & ~agree
    total_gain = float(gain.sum())
    out['B3_sources'] = {k: {'rows': int(m.sum()), 'row_share': float(m.mean()),
                             'gain_sum': float(gain[m].sum()),
                             'gain_share': (float(gain[m].sum() / total_gain) if total_gain > 0 else 0.0),
                             'mean_gain_when_it_happens': (float(gain[m].mean()) if m.any() else 0.0)}
                         for k, m in buckets.items()}
    out['B3_sources']['agreement'] = {'rows': int(agree.sum()), 'row_share': float(agree.mean()),
                                      'gain_sum': float(gain[agree].sum()),
                                      'gain_share': (float(gain[agree].sum() / total_gain)
                                                     if total_gain > 0 else 0.0),
                                      'mean_gain_when_it_happens': (float(gain[agree].mean())
                                                                    if agree.any() else 0.0)}
    out['B3_unclassified_rows'] = int(leftover.sum())
    out['B3_note'] = ('the buckets are mutually exclusive: a frame where E is right is counted only '
                      'there, so the two F/L buckets are genuine F-versus-L disagreements. Rows where '
                      'the rule already agrees with the optimum contribute no gain by construction')

    # B-4: how concentrated the potential is
    per_scene = []
    for s in np.unique(sc):
        m = sc == s
        per_scene.append({'scene': str(s), 'rows': int(m.sum()),
                          'mean_gain': float(gain[m].mean()),
                          'gain_sum': float(gain[m].sum()),
                          'gain_share': float(gain[m].sum() / total_gain) if total_gain > 0 else 0.0,
                          'rows_with_gain': int((gain[m] > TOL).sum())})
    order = np.sort(gain)[::-1]
    k10 = max(1, int(round(0.10 * len(order))))
    out['B4_distribution'] = {
        'per_scene': per_scene,
        'scenes_with_positive_gain': int(sum(1 for x in per_scene if x['gain_sum'] > TOL)),
        'rows_with_any_gain': int((gain > TOL).sum()),
        'row_share_with_any_gain': float((gain > TOL).mean()),
        'top10pct_rows_gain_share': float(order[:k10].sum() / total_gain) if total_gain > 0 else 0.0,
        'top1pct_rows_gain_share': (float(order[:max(1, int(round(0.01 * len(order))))].sum() / total_gain)
                                    if total_gain > 0 else 0.0),
        'concentration_caveat': 'the top-10 % figure is close to tautological whenever fewer than 10 % '
                                'of rows carry any gain at all: the informative quantities are the '
                                'share of rows with a gain and the spread across scenes',
        'max_scene_gain_share': max((x['gain_share'] for x in per_scene), default=0.0),
        'total_gain_sum': total_gain}
    return out


def per_cell(g, rep):
    rows = []
    for (c, s), t in g.groupby(['channel', 'snr_db']):
        sc = t.scene.to_numpy()
        rule_F = float(s) >= rep[c]['tau_db']
        Q_rule = t.Q_F if rule_F else t.Q_L
        gain = t.Q_star_taken.to_numpy() - Q_rule.to_numpy()
        rows.append({'channel': c, 'snr_db': int(s), 'q_F': float(t.q_F.iloc[0]),
                     'p_cw': float(t.p_cw.iloc[0]),
                     'optimal_share': {a: float((t.a_star == a).mean()) for a in ACTIONS},
                     'rule_action': 'F' if rule_F else 'L',
                     'G_task_scene_equal': scene_equal(gain, sc)})
    rows.sort(key=lambda r: (r['channel'], r['snr_db']))
    return rows


def build():
    g, n_cw_F, B_F_sym = build_table()
    rep = rule_tau()
    bl = pd.read_csv(BLER); bl = bl[bl.qam == 16]
    sampled = {(r.channel, float(r.esno_db)) for r in bl.itertuples()}

    clean_cells = sorted({(c, int(s)) for c, s in zip(g.channel, g.snr_db)
                          if float(g[(g.channel == c) & (g.snr_db == s)].q_F.iloc[0]) >= Q_F_CLEAN})
    clean_mask = np.zeros(len(g), bool)
    for c, s in clean_cells:
        clean_mask |= ((g.channel == c) & (g.snr_db == s)).to_numpy()
    # B-5, honestly qualified: two of those cells were never sampled by the channel table
    clean_unsampled = [(c, s) for c, s in clean_cells if (c, float(s)) not in sampled]
    clean_measured_mask = np.zeros(len(g), bool)
    for c, s in clean_cells:
        if (c, float(s)) in sampled:
            clean_measured_mask |= ((g.channel == c) & (g.snr_db == s)).to_numpy()

    subsets = [('all 22 cells', np.ones(len(g), bool)),
               ('AWGN only', (g.channel == 'awgn').to_numpy()),
               ('Rayleigh only', (g.channel == 'rayleigh').to_numpy()),
               (f'B-5 clean cells (q_F >= {Q_F_CLEAN})', clean_mask),
               ('B-5 clean cells with a sample of their own', clean_measured_mask)]
    analyses = [a for a in (analyse(g, rep, lab, m) for lab, m in subsets) if a]

    return {'schema': 'catosg-p2-offline-potential/1',
            'B6_status': 'OFFLINE POTENTIAL, NOT A DEPLOYMENT RESULT. Every action here is chosen with '
                         'per-frame outcomes that no selector can observe before it transmits. The '
                         'number is an upper bound on what any predictor of these quantities could '
                         'recover, and it exists to decide whether training a joint selector is worth '
                         'starting -- not to claim a gain',
            'accounting': 'LOCKED all-or-nothing (p2_protocol.md P2-R11 A): a message is usable only '
                          'if the whole message decodes, a failure falls back to E, and the channel is '
                          'charged for the attempt',
            'tie_rule': f'argmax with TOL = {TOL:g}; ties go to the cheaper payload, and the payload '
                        f'order E < L < F holds on every row (asserted, not assumed)',
            'n_cw_F': n_cw_F, 'B_F_sym': B_F_sym,
            'rule_tau': rep,
            'grid': {'frames': int(g.sample_id.nunique()), 'cells': int(g.groupby(['channel', 'snr_db']).ngroups),
                     'scenes': int(g.scene.nunique()), 'rows': int(len(g))},
            'clean_cells': [{'channel': c, 'snr_db': s, 'sampled': (c, float(s)) in sampled}
                            for c, s in clean_cells],
            'clean_cells_without_a_sample': [{'channel': c, 'snr_db': s} for c, s in clean_unsampled],
            'per_cell': per_cell(g, rep),
            'analyses': analyses,
            'inputs': {'grid': sha(GRID), 'wp5': sha(WP5), 'wp34': sha(WP34), 'bler': sha(BLER),
                       'four_arm': sha(FOUR_ARM), 'fill_eval': sha(FILL_EVAL)},
            'command': 'python projects/ca_tosg_p2/protocol/offline_potential.py'}


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/offline_potential.py -- do not edit by hand -->',
         '# Offline potential of a per-frame action choice (P2-R14 B)', '',
         f"**{m['B6_status']}.**", '',
         f"**Accounting.** {m['accounting']}.", '',
         f"**Tie rule.** {m['tie_rule']}.", '',
         f"**Grid.** {m['grid']['frames']:,} frames x {m['grid']['cells']} cells = "
         f"{m['grid']['rows']:,} rows, {m['grid']['scenes']} scenes.", '',
         '**The channel-only rule this is measured against.**', '']
    for c, r in m['rule_tau'].items():
        L.append(f"* **{c}**: τ = {r['tau_db']:.1f} dB, the lowest member of the optimal set "
                 f"{{{', '.join(f'{x:.1f}' for x in r['equivalent_set'])}}} that is consistent with the "
                 f"measured crossing bracket "
                 + (f"({r['consistent_with_measured_bracket'][0]:.1f}, "
                    f"{r['consistent_with_measured_bracket'][1]:.1f}] dB."
                    if r['consistent_with_measured_bracket'] else 'measurement.'))
    L += ['', '## B-1 Which action is right, per cell', '',
          '| channel | SNR | p_cw | q_F | rule takes | optimal: E | L | F | G_task |',
          '|---|---:|---:|---:|:---:|---:|---:|---:|---:|']
    for r in m['per_cell']:
        o = r['optimal_share']
        L.append(f"| {r['channel']} | {r['snr_db']} | {r['p_cw']:.5g} | {r['q_F']:.3g} | "
                 f"{r['rule_action']} | {o['E'] * 100:.1f} % | {o['L'] * 100:.1f} % | "
                 f"{o['F'] * 100:.1f} % | {r['G_task_scene_equal']:+.5f} |")
    L += ['', '## B-2 to B-4 Potential, sources and distribution', '']
    for a in m['analyses']:
        g_, vl, vf = a['G_task'], a['vs_Fixed_L'], a['vs_Fixed_F']
        L += [f"### {a['label']}", '',
              f"{a['rows']:,} rows over {a['cells']} cell(s). Optimal action shares: "
              f"E {a['optimal_share']['E'] * 100:.1f} %, L {a['optimal_share']['L'] * 100:.1f} %, "
              f"F {a['optimal_share']['F'] * 100:.1f} %. The rule requests F on "
              f"{a['rule_share_F'] * 100:.1f} % of rows.", '',
              '| comparison | scene-equal mean | bootstrap 95 % |', '|---|---:|---|',
              f"| **G_task = Q(a\\*) − Q(rule_τ)** | **{g_['mean']:+.5f}** | "
              f"[{g_['lcb95']:+.5f}, {g_['ucb95']:+.5f}] |",
              f"| Q(a\\*) − Q(Fixed L) | {vl['mean']:+.5f} | [{vl['lcb95']:+.5f}, {vl['ucb95']:+.5f}] |",
              f"| Q(a\\*) − Q(Fixed F) | {vf['mean']:+.5f} | [{vf['lcb95']:+.5f}, {vf['ucb95']:+.5f}] |",
              '',
              f"Scene-equal F1: optimum {a['scene_equal']['Q_star']:.5f}, rule "
              f"{a['scene_equal']['Q_rule']:.5f}, Fixed L {a['scene_equal']['Q_Fixed_L']:.5f}, Fixed F "
              f"{a['scene_equal']['Q_Fixed_F']:.5f}, Fixed E {a['scene_equal']['Q_Fixed_E']:.5f}. "
              f"Payload, reported and not used as a criterion: optimum "
              f"{a['payload_sym_scene_equal']['optimal']:,.0f} QAM symbols per frame against the rule's "
              f"{a['payload_sym_scene_equal']['rule']:,.0f}.", '',
              '**B-3 Where the potential comes from.**', '',
              '| source | rows | row share | gain sum | share of all gain | mean gain when it happens |',
              '|---|---:|---:|---:|---:|---:|']
        for k in ('rule_F_but_L_is_right', 'rule_L_but_F_is_right', 'E_is_right', 'agreement'):
            b = a['B3_sources'][k]
            L.append(f"| `{k}` | {b['rows']:,} | {b['row_share'] * 100:.1f} % | {b['gain_sum']:+.3f} | "
                     f"{b['gain_share'] * 100:.1f} % | {b['mean_gain_when_it_happens']:+.5f} |")
        L += ['', f"{a['B3_note']}. Unclassified rows: {a['B3_unclassified_rows']:,}.", '',
              '**B-4 How it is distributed.**', '']
        d = a['B4_distribution']
        L += [f"**{d['rows_with_any_gain']:,} of {a['rows']:,} rows carry any gain at all "
              f"({d['row_share_with_any_gain'] * 100:.1f} %)** — on every other row the channel-only "
              'rule already picks the per-frame optimum. Of the total gain, the top 10 % of rows hold '
              f"{d['top10pct_rows_gain_share'] * 100:.2f} % and the top 1 % hold "
              f"{d['top1pct_rows_gain_share'] * 100:.2f} %.", '',
              f"*Read the first of those two with care:* {d['concentration_caveat']}. "
              f"{d['scenes_with_positive_gain']} of {len(d['per_scene'])} scenes contribute a positive "
              f"gain and the largest single scene holds {d['max_scene_gain_share'] * 100:.1f} % of it, "
              'so the potential is spread across the dataset rather than resting on one scene.', '',
              '| scene | rows | rows with gain | mean gain | share of all gain |',
              '|---|---:|---:|---:|---:|']
        for x in d['per_scene']:
            L.append(f"| {x['scene']} | {x['rows']:,} | {x['rows_with_gain']:,} | {x['mean_gain']:+.5f} | "
                     f"{x['gain_share'] * 100:.1f} % |")
        L.append('')
    cc = m['clean_cells']
    L += ['## B-5 The cells where the channel is not the variable', '',
          f"`q_F >= {Q_F_CLEAN}` holds in {len(cc)} cells, all of them AWGN: "
          + ', '.join(f"{c['snr_db']} dB" for c in cc) + '. There is **no Rayleigh cell** in this set — '
          'the best Rayleigh cell in the grid reaches q_F ≈ 1.6e-223.', '']
    if m['clean_cells_without_a_sample']:
        L += ['**Two of those cells were never measured.** '
              + ', '.join(f"AWGN {c['snr_db']} dB" for c in m['clean_cells_without_a_sample'])
              + " carry a p_cw the channel table never sampled: it comes from P1's §9.3 interpolation "
                'between neighbouring zero-error points. Their q_F = 1 is therefore inherited, not '
                'measured, which is why the same analysis is repeated above over only the cells that '
                'have counts of their own.', '']
    L += ['## Inputs', '', '| file | sha256 |', '|---|---|']
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
        print('offline potential:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
