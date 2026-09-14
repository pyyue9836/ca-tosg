#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R25 — hold the predicted F gain inside what the estimated channel allows. No training, no GPU.

**This is a post-hoc method change and is registered as one.** It was proposed after reading the
P2-R24 diagnosis, not before, so it is not a pre-registered hypothesis and nothing below should be
read as confirming one.

    dF_new = clip(dF_hat, -q_F, q_F),   q_F = (1 - p_cw) ** 12567

`p_cw` is looked up from the point-estimate table by the **estimated** channel, that is by the two
model inputs `est_snr_db` and `channel_is_rayleigh`. In this setup the estimated SNR is the cell's own
SNR, so the lookup coincides numerically with the true channel; that is P1's perfect-estimate
idealisation carried over, and it means the clip is exactly as good as the q_F estimate and no better.
A real receiver estimate would be noisier and this arm is optimistic in that respect.

The decision is unchanged: `max{0, dL_hat, dF_new}`, ties within TOL to the cheaper payload. `dL_hat`
is left alone -- L's codeword count varies per frame and this round repairs only the F defect that was
actually diagnosed. Nothing is retrained, no training record is clipped, and the Q table and labels are
untouched.

Where q_F underflows to zero in double precision the clip forces dF_new to exactly zero. That is a
numerical limit of the grid, recorded as such.

    python r25_clip.py [--check]
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
OUT_JSON = os.path.join(HERE, 'r25_clip.json')
OUT_MD = os.path.join(HERE, 'r25_clip.md')

sys.path.insert(0, HERE)
from offline_potential import build_table, scene_equal, boot, ACTIONS, TOL          # noqa: E402
from rf_round1 import outcome, evaluate                                            # noqa: E402
from rf_round2 import load_frame_outcomes, HI_CELLS, cap1                          # noqa: E402
from rf_round4 import decide                                                       # noqa: E402

ORIG, CLIP, RULE = 'RF_regression', 'RF_regression_clipped', 'channel_rule'
INVALID_QF = 0.5          # B-2: an F request where the point-estimate q_F is below this is "useless"

# B-4, written before the numbers were produced and not edited afterwards.
EXPECTATIONS = [
    'the clip targets one diagnosed defect only: the small positive floor in dF_hat on Rayleigh, '
    'where the analytic range is at or near zero. That is where any change should appear',
    'on the good-channel cells q_F is 1, so the clip is inactive there by construction. It cannot '
    'and will not improve the F-versus-L discrimination that P2-R24 found anti-correlated',
    'a fall in payload is not evidence that task information beats the channel-only rule. Payload '
    'and perception are reported side by side and neither substitutes for the other',
    'the clip is only as reliable as q_F is. Here q_F comes from a perfect SNR estimate, so this arm '
    'is an upper bound on what the same clip would achieve with a real receiver estimate. It is not '
    'a link-layer guarantee',
]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def build():
    rows = pd.read_csv(ROWS_GZ)
    held = rows[rows.split == 'held_out'].copy()
    g, n_cw_F, B_F_sym = build_table()
    fo, _ = load_frame_outcomes(g)

    key = ['sample_id', 'channel', 'snr_db']
    if held.duplicated(key).any() or len(held) != len(g):
        raise SystemExit('the held-out rows are not one per grid row')
    held = held.set_index(key).loc[g.set_index(key).index].reset_index()

    # A-1: q_F from the ESTIMATED channel, which is the pair of model inputs.
    est = held[['channel', 'snr_db']].rename(columns={'snr_db': 'est_snr_db'})
    lut = (g[['channel', 'snr_db', 'p_cw']].drop_duplicates()
           .rename(columns={'snr_db': 'est_snr_db'}))
    j = est.merge(lut, on=['channel', 'est_snr_db'], how='left', validate='many_to_one')
    if j.p_cw.isna().any():
        raise SystemExit('an estimated channel has no p_cw in the point-estimate table')
    q_F_est = (1.0 - j.p_cw.to_numpy()) ** n_cw_F
    if float(np.abs(q_F_est - g.q_F.to_numpy()).max()) > 0:
        raise SystemExit('the estimated-channel q_F differs from the grid q_F -- the idealisation '
                         'note in the docstring would be wrong')

    dL_hat = held.dL_hat.to_numpy()
    dF_hat = held.dF_hat.to_numpy()
    dF_new = np.clip(dF_hat, -q_F_est, q_F_est)
    underflow = q_F_est == 0.0
    clipped = dF_new != dF_hat

    # the channel-only rule is the per-row action round 1 already stored; it is read, not refitted
    chan_rule = pd.read_csv(os.path.join(P2, 'results', 'rf', 'rf_round1_oof.csv'),
                            usecols=key + ['pred_channel_rule'])
    chan_rule = chan_rule.set_index(key).loc[g.set_index(key).index].reset_index()
    chosen = {ORIG: decide(dL_hat, dF_hat), CLIP: decide(dL_hat, dF_new),
              RULE: chan_rule.pred_channel_rule.to_numpy().astype(object),
              'offline_optimum': g.a_star.to_numpy().astype(object),
              'fixed_E': np.full(len(g), 'E', object),
              'fixed_L': np.full(len(g), 'L', object),
              'fixed_F': np.full(len(g), 'F', object)}

    if not bool((chosen[ORIG] == held.pred.to_numpy()).all()):
        raise SystemExit('re-deciding from the stored gains does not reproduce round 4\'s own '
                         'actions -- the decision rule or the record has moved')

    ch = g.channel.to_numpy()
    snr = g.snr_db.to_numpy()
    scene = g.scene.to_numpy()
    hi = np.zeros(len(g), bool)
    for c, s in HI_CELLS:
        hi |= (ch == c) & (snr == s)

    def useless_F(sel_mask, action):
        """B-2: F requested where the point-estimate q_F is below the threshold."""
        m = sel_mask & (action == 'F') & (g.q_F.to_numpy() < INVALID_QF)
        return m

    def arm_block(mask, label):
        sc = scene[mask]
        out = {'label': label, 'rows': int(mask.sum()), 'arms': {}}
        for name, act in chosen.items():
            Q, rec, mis, pay = outcome(g, fo, act)
            u = useless_F(mask, act)
            out['arms'][name] = {
                'f1': scene_equal(Q[mask], sc), 'recall': scene_equal(rec[mask], sc),
                'misses_per_frame': scene_equal(mis[mask], sc),
                'qam_symbols': scene_equal(pay[mask], sc),
                'request_share': {a: scene_equal((act[mask] == a).astype(float), sc)
                                  for a in ACTIONS},
                'useless_F_requests': int(u.sum()),
                'useless_F_qam_contribution': scene_equal((u * B_F_sym)[mask], sc)}
        return out

    subsets = [('all 22 cells', np.ones(len(g), bool)), ('AWGN only', ch == 'awgn'),
               ('Rayleigh only', ch == 'rayleigh')]
    per_channel = [arm_block(m, lab) for lab, m in subsets]
    per_cell = [arm_block(((ch == c) & (snr == s)), f'{c} {int(s)} dB')
                for c in ('awgn', 'rayleigh') for s in sorted({int(x) for cc, x in zip(ch, snr)
                                                               if cc == c})]

    pairs = [(CLIP, ORIG), (CLIP, RULE), (CLIP, 'fixed_L')]
    diffs = {}
    for lab, m in subsets + [(f'{c} {s} dB', ((ch == c) & (snr == s))) for c, s in HI_CELLS]:
        sc = scene[m]
        d = {}
        for a, b in pairs:
            v = outcome(g, fo, chosen[a])[0][m] - outcome(g, fo, chosen[b])[0][m]
            per = [{'scene': str(s), 'diff': float(v[sc == s].mean())} for s in np.unique(sc)]
            d[f'{a} - {b}'] = {'bootstrap': boot(v, sc), 'per_scene': per,
                               'scenes_negative': [x['scene'] for x in per if x['diff'] < 0]}
        diffs[lab] = d

    return {'schema': 'catosg-p2-r25-clip/1',
            'status': 'POST-HOC METHOD CHANGE, registered as such. It was proposed after reading the '
                      'P2-R24 diagnosis, so it is not a pre-registered hypothesis and none of the '
                      'numbers below confirm one. No training, no GPU, no change to the Q table, the '
                      'labels or the decision rule',
            'clip': 'dF_new = clip(dF_hat, -q_F, q_F) with q_F = (1 - p_cw) ** %d, p_cw looked up by '
                    'the estimated channel (est_snr_db, channel_is_rayleigh)' % n_cw_F,
            'estimate_idealisation': 'the estimated SNR here IS the cell SNR, so this lookup coincides '
                                     'numerically with the true channel. The clip is exactly as good '
                                     'as the q_F estimate; with a real receiver estimate it would be '
                                     'worse, so this arm is an upper bound on the technique',
            'dL_untouched': 'dL_hat is not clipped: L\'s codeword count varies per frame and this '
                            'round repairs only the diagnosed F defect',
            'underflow_note': 'where q_F underflows to zero in double precision the clip forces '
                              'dF_new to exactly zero; that is a numerical limit of the grid',
            'rows_clipped': int(clipped.sum()), 'rows_clipped_share': float(clipped.mean()),
            'rows_with_q_F_underflow': int(underflow.sum()),
            'clipped_by_channel': {c: int((clipped & (ch == c)).sum()) for c in ('awgn', 'rayleigh')},
            'useless_F_threshold_q_F': INVALID_QF,
            'expectations_and_limits_fixed_in_advance': EXPECTATIONS,
            'inputs': {'round4_rows': sha(ROWS_GZ), 'grid': sha(GRID)},
            'B_F_qam_symbols': B_F_sym,
            'by_channel': per_channel, 'by_cell': per_cell, 'differences': diffs,
            'command': 'python projects/ca_tosg_p2/protocol/r25_clip.py'}


ARM_ORDER = ('offline_optimum', RULE, ORIG, CLIP, 'fixed_L', 'fixed_F', 'fixed_E')


def arm_table(block):
    L = [f"### {block['label']} ({block['rows']:,} rows)", '',
         '| arm | scene-equal F1 | recall | misses / frame | QAM symbols | E | L | F | useless F '
         'requests | their QAM |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for a in ARM_ORDER:
        v = block['arms'].get(a)
        if not v:
            continue
        s = v['request_share']
        L.append(f"| `{a}` | {v['f1']:.5f} | {v['recall']:.5f} | {v['misses_per_frame']:.3f} | "
                 f"{v['qam_symbols']:,.0f} | {s['E'] * 100:.1f} % | {s['L'] * 100:.1f} % | "
                 f"{s['F'] * 100:.1f} % | {v['useless_F_requests']:,} | "
                 f"{v['useless_F_qam_contribution']:,.0f} |")
    L.append('')
    return L


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/r25_clip.py -- do not edit by hand -->',
         '# Holding the predicted F gain inside what the estimated channel allows (P2-R25)', '',
         f"**{cap1(m['status'])}.**", '', f"**The change.** `{m['clip']}`.", '',
         f"**On the estimate.** {cap1(m['estimate_idealisation'])}.", '',
         f"**{cap1(m['dL_untouched'])}.** {cap1(m['underflow_note'])}.", '',
         '## What was expected, written before the numbers', '']
    for e in m['expectations_and_limits_fixed_in_advance']:
        L.append(f"* {cap1(e)}.")
    L += ['', '## How much was clipped', '',
          f"{m['rows_clipped']:,} of 43,560 rows ({m['rows_clipped_share'] * 100:.1f} %) had their "
          f"predicted F gain moved: {m['clipped_by_channel']['awgn']:,} on AWGN and "
          f"{m['clipped_by_channel']['rayleigh']:,} on Rayleigh. "
          f"{m['rows_with_q_F_underflow']:,} rows sit in cells where q_F underflows to zero, so their "
          'clipped gain is exactly zero.', '',
          f"A request is counted as useless where the point-estimate q_F is below "
          f"{m['useless_F_threshold_q_F']}.", '',
          '## B-1, B-2 By channel', '']
    for b in m['by_channel']:
        L += arm_table(b)
    L += ['## Per cell', '']
    for b in m['by_cell']:
        L += arm_table(b)
    L += ['## B-3 Differences, per scene and bootstrapped', '',
          'The six high-reliability cells are listed one by one. Each of them holds exactly one row '
          'per frame, so each row of the table below is already per unique frame; they are not '
          'collapsed into a single line because the predictions differ across the six cells even '
          'though P2-R24 showed the truth does not.', '',
          '| subset | difference | scene-equal mean | bootstrap 95 % | scenes negative |',
          '|---|---|---:|---|---|']
    for lab, d in m['differences'].items():
        for k, v in d.items():
            b = v['bootstrap']
            L.append(f"| {lab} | {k} | {b['mean']:+.5f} | [{b['lcb95']:+.5f}, {b['ucb95']:+.5f}] | "
                     f"{len(v['scenes_negative'])}/9 |")
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
        print('r25 clip:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
