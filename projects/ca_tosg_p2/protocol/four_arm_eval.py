#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R11 C — four arms under the LOCKED all-or-nothing accounting. CPU table work only.

Arms, on every one of the 1,980 validate frames x 22 channel cells:
  Fixed E, Fixed L, Fixed F, and the channel-only rule "SNR >= tau -> F, else L".
Under the locked accounting (p2_protocol.md, P2-R11 A) a message is usable only if the whole message
decodes; a failure falls back to E, and the channel is charged for the attempt either way.

  C-2  tau swept at 0.5 dB over the whole range, the entire curve reported, AWGN and Rayleigh apart
  C-3  the per-cell table, with the cells where F beats L marked
  C-4  where the AWGN crossing sits, and what the channel table does and does not sample there
  C-5  per-scene values and scene-level bootstrap intervals; negative scenes reported as they are

    python projects/ca_tosg_p2/protocol/four_arm_eval.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
OUT_JSON = os.path.join(HERE, 'four_arm_eval.json')
OUT_MD = os.path.join(HERE, 'four_arm_eval.md')
V2 = os.path.join(ROOT, 'results', 'v2')
GRID = os.path.join(V2, 'v2_grid_validate_ideal.csv')
WP5 = os.path.join(V2, 'wp5_final_validate.csv')
WP34 = os.path.join(V2, 'wp34_e_l_validate.csv')
CHAIN = os.path.join(V2, 'payload_chain.json')
BLER = os.path.join(ROOT, 'results', 'channel', 'bler_sionna.csv')
TAU_STEP = 0.5                       # P1's sweep step
N_BOOT, BOOT_SEED = 10000, 20260809
CHANNELS = ('awgn', 'rayleigh')


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def scene_equal(v, scenes):
    return float(np.mean([v[scenes == s].mean() for s in np.unique(scenes)]))


def boot(v, scenes, seed=BOOT_SEED):
    u = np.unique(scenes)
    means = np.array([v[scenes == s].mean() for s in u])
    rng = np.random.default_rng(seed)
    bs = means[rng.integers(0, len(u), (N_BOOT, len(u)))].mean(axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {'mean': float(means.mean()), 'lcb95': float(lo), 'ucb95': float(hi)}


def build():
    chain = json.load(open(CHAIN))['F']
    n_cw_F, B_F_sym = chain['n_cw'], chain['msym'] * 1e6
    g = pd.read_csv(GRID, usecols=['sample_id', 'scene', 'snr_db', 'channel', 'p_cw', 'q_L',
                                   'eff_E', 'eff_L', 'B_L', 'has_collaborator'])
    w5 = pd.read_csv(WP5, usecols=['frame', 'f1_clean', 'f1_ego']).set_index('frame')
    w34 = pd.read_csv(WP34, usecols=['frame', 'f1_L']).set_index('frame')
    g['f1_clean'] = w5.f1_clean.loc[g.sample_id].to_numpy()
    g['f1_ego'] = w5.f1_ego.loc[g.sample_id].to_numpy()
    g['f1_L'] = w34.f1_L.loc[g.sample_id].to_numpy()

    # guard: the locked A-2 rule must BE P1's stored eff_L, or the two accountings have drifted apart
    eff_L_rebuilt = g.q_L * g.f1_L + (1 - g.q_L) * g.f1_ego
    d_L = float(np.abs(eff_L_rebuilt - g.eff_L).max())
    if d_L > 1e-9:
        raise SystemExit(f'A-2: P1 eff_L does not reproduce the locked message rule (max |diff| {d_L:g})')
    if float(np.abs(g.eff_E - g.f1_ego).max()) > 1e-12:
        raise SystemExit('eff_E is not the ego-only F1 -- stop')

    g['q_F'] = (1.0 - g.p_cw.to_numpy()) ** n_cw_F
    g['eff_F'] = g.q_F * g.f1_clean + (1 - g.q_F) * g.f1_ego          # A-1, constructed
    g['B_L_sym'] = g.B_L.to_numpy() * 1e6

    def arm_rows(sel_F):
        """sel_F: bool per row, True = request F, False = request L. Returns eff, payload, shares."""
        eff = np.where(sel_F, g.eff_F, g.eff_L)
        pay = np.where(sel_F, B_F_sym, g.B_L_sym)
        q = np.where(sel_F, g.q_F, g.q_L)
        rho_F = np.where(sel_F, q, 0.0)
        rho_L = np.where(sel_F, 0.0, q)
        return eff, pay, rho_F, rho_L, 1.0 - rho_F - rho_L

    arms = {
        'Fixed E': (np.zeros(len(g), bool), g.eff_E.to_numpy(), np.zeros(len(g)),
                    np.zeros(len(g)), np.zeros(len(g)), np.ones(len(g))),
        'Fixed L': (None,) + arm_rows(np.zeros(len(g), bool)),
        'Fixed F': (None,) + arm_rows(np.ones(len(g), bool)),
    }

    def summarise(eff, pay, rF, rL, rE, mask):
        sc = g.scene.to_numpy()[mask]
        return {'scene_equal_f1': scene_equal(eff[mask], sc),
                'qam_symbols_scene_equal': scene_equal(pay[mask], sc),
                'executed_share_E': float(rE[mask].mean()), 'executed_share_L': float(rL[mask].mean()),
                'executed_share_F': float(rF[mask].mean())}

    ch_mask = {c: (g.channel == c).to_numpy() for c in CHANNELS}
    fixed = {}
    for name, tup in arms.items():
        _, eff, pay, rF, rL, rE = tup
        fixed[name] = {c: summarise(eff, pay, rF, rL, rE, ch_mask[c]) for c in CHANNELS}

    # C-2: the tau sweep
    snr = g.snr_db.to_numpy(float)
    taus = np.round(np.arange(-TAU_STEP, 20 + 2 * TAU_STEP, TAU_STEP), 3)
    sweep = []
    for tau in taus:
        sel = snr >= tau
        eff, pay, rF, rL, rE = arm_rows(sel)
        row = {'tau_db': float(tau)}
        for c in CHANNELS:
            row[c] = summarise(eff, pay, rF, rL, rE, ch_mask[c])
            row[c]['requested_share_F'] = float(sel[ch_mask[c]].mean())
        sweep.append(row)
    best = {c: max(sweep, key=lambda r: r[c]['scene_equal_f1']) for c in CHANNELS}

    # C-3: per cell
    cells = []
    for (c, s), t in g.groupby(['channel', 'snr_db']):
        sc = t.scene.to_numpy()
        r = {'channel': c, 'snr_db': int(s), 'p_cw': float(t.p_cw.iloc[0]), 'q_F': float(t.q_F.iloc[0]),
             'q_L_mean': float(t.q_L.mean()),
             'Fixed E': scene_equal(t.eff_E.to_numpy(), sc), 'Fixed L': scene_equal(t.eff_L.to_numpy(), sc),
             'Fixed F': scene_equal(t.eff_F.to_numpy(), sc)}
        r['F_minus_L'] = r['Fixed F'] - r['Fixed L']
        r['F_beats_L'] = bool(r['F_minus_L'] > 0)
        cells.append(r)
    cells.sort(key=lambda r: (r['channel'], r['snr_db']))

    # C-4: where the AWGN crossing sits, and what the channel table samples there
    bl = pd.read_csv(BLER)
    bl = bl[bl.qam == 16]
    crossings = {}
    for c in CHANNELS:
        cc = [r for r in cells if r['channel'] == c]
        cross = [(cc[i]['snr_db'], cc[i + 1]['snr_db']) for i in range(len(cc) - 1)
                 if (cc[i]['F_minus_L'] > 0) != (cc[i + 1]['F_minus_L'] > 0)]
        sampled = sorted(float(x) for x in bl[bl.channel == c].esno_db.unique())
        between = [] if not cross else [x for x in sampled if cross[0][0] < x < cross[0][1]]
        crossings[c] = {'sign_changes_between': [[int(a), int(b)] for a, b in cross],
                        'channel_table_points_strictly_between_the_first_crossing': between,
                        'channel_table_points': sampled}
    c4 = {'crossings': crossings,
          'no_interpolation': 'the crossing is reported as lying between the two sampled points. No value is '
                              'interpolated across it: on AWGN the per-codeword loss falls from 0.04100 at 7 dB to '
                              '0.00013 at 8 dB to 0 at 10 dB, and a straight line through that region would invent '
                              'a number the sweep never measured',
          'what_filling_it_would_need': 'AWGN 16-QAM LDPC (K = 500, n = 1000) runs at 8.5, 9.0 and 9.5 dB with the '
                                        'same codeword count and stopping rule as results/channel/bler_sionna.csv, '
                                        'appended to that table and the grid rebuilt. NOT run here'}

    # C-5: per scene, and bootstrap intervals for the differences that matter
    per_scene, diffs = {}, {}
    for c in CHANNELS:
        m = ch_mask[c]
        sc = g.scene.to_numpy()[m]
        tau_star = best[c]['tau_db']
        sel = snr >= tau_star
        eff_r, pay_r, rF, rL, rE = arm_rows(sel)
        d_FL = (g.eff_F.to_numpy() - g.eff_L.to_numpy())[m]
        d_RL = (eff_r - g.eff_L.to_numpy())[m]
        per_scene[c] = [{'scene': str(s), 'rows': int((sc == s).sum()),
                         'Fixed E': float(g.eff_E.to_numpy()[m][sc == s].mean()),
                         'Fixed L': float(g.eff_L.to_numpy()[m][sc == s].mean()),
                         'Fixed F': float(g.eff_F.to_numpy()[m][sc == s].mean()),
                         'rule_at_tau_star': float(eff_r[m][sc == s].mean()),
                         'F_minus_L': float(d_FL[sc == s].mean()),
                         'rule_minus_L': float(d_RL[sc == s].mean())} for s in np.unique(sc)]
        diffs[c] = {'tau_star_db': tau_star,
                    'Fixed_F_minus_Fixed_L': boot(d_FL, sc), 'rule_minus_Fixed_L': boot(d_RL, sc),
                    'scenes_negative_F_minus_L': [x['scene'] for x in per_scene[c] if x['F_minus_L'] < 0],
                    'scenes_negative_rule_minus_L': [x['scene'] for x in per_scene[c] if x['rule_minus_L'] < 0]}

    return {'schema': 'catosg-p2-four-arm/1',
            'accounting': 'LOCKED all-or-nothing (p2_protocol.md P2-R11 A): a message is usable only if the whole '
                          'message decodes, a failure falls back to E, and payload is charged for the attempt',
            'constructed_column': 'eff_F = q_F * F1_clean + (1 - q_F) * F1_ego with q_F = (1 - p_cw) ** '
                                  f'{n_cw_F}; constructed by P1\'s message rule, not a stored product',
            'guard': {'p1_eff_L_reproduces_the_locked_rule': True, 'max_abs_diff': d_L},
            'inputs': {'grid': sha(GRID), 'wp5': sha(WP5), 'wp34': sha(WP34), 'bler': sha(BLER)},
            'payload_units': 'QAM data symbols; F = %.0f per request, L = per-frame N_cw,L x 250, E = 0' % B_F_sym,
            'fixed_arms': fixed, 'tau_sweep': {'step_db': TAU_STEP, 'rows': sweep,
                                               'best_by_scene_equal_f1': {c: best[c]['tau_db'] for c in CHANNELS}},
            'cells': cells, 'C4': c4, 'per_scene': per_scene, 'differences': diffs,
            'command': 'python projects/ca_tosg_p2/protocol/four_arm_eval.py'}


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/four_arm_eval.py -- do not edit by hand -->',
         '# Four arms under the locked all-or-nothing accounting (P2-R11 C)', '',
         f"**Accounting.** {m['accounting']}.", '', f"**Constructed column.** {m['constructed_column']}.", '',
         f"**Guard.** P1's stored `eff_L` reproduces the locked A-2 rule to {m['guard']['max_abs_diff']:.1e}.", '',
         f"**Payload.** {m['payload_units']}.", '', '## Fixed arms', '',
         '| channel | arm | scene-equal F1 | QAM symbols / frame | executed E | executed L | executed F |',
         '|---|---|---:|---:|---:|---:|---:|']
    for c in CHANNELS:
        for a in ('Fixed E', 'Fixed L', 'Fixed F'):
            v = m['fixed_arms'][a][c]
            L.append(f"| {c} | {a} | {v['scene_equal_f1']:.5f} | {v['qam_symbols_scene_equal']:,.0f} | "
                     f"{v['executed_share_E'] * 100:.1f} % | {v['executed_share_L'] * 100:.1f} % | "
                     f"{v['executed_share_F'] * 100:.1f} % |")
    L += ['', '## C-2 The τ sweep, 0.5 dB steps, channels apart', '',
          'The rule requests F when SNR ≥ τ and L otherwise; both fall back to E on failure. Executed shares are '
          'expectations under the locked accounting.', '']
    for c in CHANNELS:
        L += [f"### {c}", '', '| τ (dB) | scene-equal F1 | QAM symbols / frame | requested F | executed E | '
              'executed L | executed F |', '|---:|---:|---:|---:|---:|---:|---:|']
        for r in m['tau_sweep']['rows']:
            v = r[c]
            L.append(f"| {r['tau_db']:.1f} | {v['scene_equal_f1']:.5f} | {v['qam_symbols_scene_equal']:,.0f} | "
                     f"{v['requested_share_F'] * 100:.1f} % | {v['executed_share_E'] * 100:.1f} % | "
                     f"{v['executed_share_L'] * 100:.1f} % | {v['executed_share_F'] * 100:.1f} % |")
        L += ['', f"Highest scene-equal F1 at τ = {m['tau_sweep']['best_by_scene_equal_f1'][c]:.1f} dB.", '']
    L += ['## C-3 Per cell', '', '| channel | SNR | p_cw | q_F | Fixed E | Fixed L | Fixed F | F − L | F beats L |',
          '|---|---:|---:|---:|---:|---:|---:|---:|:---:|']
    for r in m['cells']:
        L.append(f"| {r['channel']} | {r['snr_db']} | {r['p_cw']:.5f} | {r['q_F']:.3g} | {r['Fixed E']:.5f} | "
                 f"{r['Fixed L']:.5f} | {r['Fixed F']:.5f} | {r['F_minus_L']:+.5f} | "
                 f"{'**yes**' if r['F_beats_L'] else 'no'} |")
    c4 = m['C4']
    L += ['', '## C-4 Where the crossing sits', '']
    for c in CHANNELS:
        v = c4['crossings'][c]
        if v['sign_changes_between']:
            inside = v['channel_table_points_strictly_between_the_first_crossing']
            L.append(f"* **{c}**: F overtakes L between "
                     + ', '.join(f"**{a} and {b} dB**" for a, b in v['sign_changes_between'])
                     + '. Points the channel table samples strictly inside the first such interval: '
                     + (', '.join(f'{x:g} dB' for x in inside) if inside else '**none**') + '.')
        else:
            L.append(f"* **{c}**: **no crossing anywhere in the sampled range** — F does not overtake L at any "
                     'of the eleven SNR points, so there is no interval to locate.')
    L += ['', f"{c4['no_interpolation']}.", '', f"**To fill it:** {c4['what_filling_it_would_need']}.", '',
          '## C-5 Per scene and intervals', '']
    for c in CHANNELS:
        d = m['differences'][c]
        L += [f"### {c} (rule at τ = {d['tau_star_db']:.1f} dB)", '',
              '| scene | rows | Fixed E | Fixed L | Fixed F | rule | F − L | rule − L |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
        for r in m['per_scene'][c]:
            L.append(f"| {r['scene']} | {r['rows']:,} | {r['Fixed E']:.5f} | {r['Fixed L']:.5f} | {r['Fixed F']:.5f} | "
                     f"{r['rule_at_tau_star']:.5f} | {r['F_minus_L']:+.5f} | {r['rule_minus_L']:+.5f} |")
        L += ['', f"Scene-level bootstrap: Fixed F − Fixed L = {d['Fixed_F_minus_Fixed_L']['mean']:+.5f} "
              f"[{d['Fixed_F_minus_Fixed_L']['lcb95']:+.5f}, {d['Fixed_F_minus_Fixed_L']['ucb95']:+.5f}]; "
              f"rule − Fixed L = {d['rule_minus_Fixed_L']['mean']:+.5f} "
              f"[{d['rule_minus_Fixed_L']['lcb95']:+.5f}, {d['rule_minus_Fixed_L']['ucb95']:+.5f}].",
              '', f"Scenes with a negative F − L: "
              + (', '.join(d['scenes_negative_F_minus_L']) if d['scenes_negative_F_minus_L'] else 'none')
              + f". With a negative rule − L: "
              + (', '.join(d['scenes_negative_rule_minus_L']) if d['scenes_negative_rule_minus_L'] else 'none') + '.', '']
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('four arm eval:', 'reproduced' if ok else 'FAIL -- not what the generator writes'); return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md[:4000]); return 0


if __name__ == '__main__':
    sys.exit(main())
