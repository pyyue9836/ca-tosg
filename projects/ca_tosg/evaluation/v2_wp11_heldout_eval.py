#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R32 D-7 — the Test primary comparison. THE UNSEAL. Zero GPU.

Runs ONE pre-specified comparison at the primary cell beta = 0.20:

    frozen RF candidate 67   vs   the frozen comparator, SNR threshold tau = 16.5

Reported per V2-R28 C-2:
  * non-inferiority   LCB95 of the signed dF1 > -delta, delta = 0.005
  * payload saving    UCB95(dB) < 0 and point-estimate relative saving >= 10 %
  * statistical unit  SCENE-LEVEL bootstrap (P0-8) -- frames within a scene are not independent

The wording rule is R9's and is not negotiable here (C-3): non-inferiority plus payload saving. It
may NOT be written as the RF having better F1, and "same F1" / "no loss" are forbidden.

This is the only module permitted to read the sealed test grid, and it is the LAST step -- nothing
downstream may change lambda, the model, the threshold or the cues on the strength of what it prints
(V2-R32 E-3).

    python projects/ca_tosg/evaluation/v2_test_primary.py --unseal
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
SEALED = os.path.join(ROOT, 'results', 'v2', 'sealed')
FREEZE = os.path.join(ROOT, 'results', 'manifests', 'V2_PRIMARY_FREEZE.json')
TIERC = os.path.join(ROOT, 'results', 'manifests', 'V2_TIERC_FREEZE.json')
OUT_T = os.path.join(ROOT, 'results', 'v2', 'v2_test_primary.json')
B_F, DELTA, BETA, N_BOOT = 3.14175, 0.005, 0.20, 10000


OUT_FA = os.path.join(ROOT, 'results', 'v2', 'v2_heldout_fixed_arms.json')


def fixed_arms():
    """V2-R55 A-1 — descriptive fixed-arm summaries from the frozen held-out grids.

    **This is an aggregation, not an evaluation.** It loads no model, runs no inference and touches
    no primary product: it reads `eff_{E,L,F}` and `B_{E,L,F}`, which are already IN the frozen
    grid, and reduces them. Nothing here can change a frozen component, and nothing downstream may
    select a comparator on the strength of it.

    It lives in THIS module for one reason: gate 22 permits exactly one script to read the sealed
    grid, and that is this one. Putting the aggregation in the paper generator would have meant
    adding a second name to an allow-list -- which is precisely what `V2_UNSEAL_RECORD.json` says
    must not happen ("the file being readable is the consequence of a dated act, not of someone
    editing an allow-list"). So the licensed reader emits an unsealed product, and the product is
    registered.

    Statistic, per A-1: F1 is the mean over each scene's rows, then the equal-weight mean over
    scenes; payload is the mean over all grid rows; full-frame accounting throughout.
    """
    out = {'schema': 'catosg-v2-heldout-fixed-arms/1',
           'why': 'Descriptive secondary reference only (V2-R55 A-5). NOT used to select a '
                  'comparator, and NOT a retest of the primary criterion, which remains the '
                  'frozen tau rule.',
           'statistic': 'F1: mean within scene over all SNR x channel rows, then equal-weight '
                        'mean over scenes. Payload: mean over all grid rows. Full-frame.',
           'splits': {}}
    for sp in ('test', 'culver'):
        g = pd.read_csv(os.path.join(SEALED, f'v2_grid_{sp}_ideal.csv'))
        d = {'n_rows': int(len(g)), 'n_scenes': int(g.scene.nunique()), 'arms': {}}
        for act in ('E', 'L', 'F'):
            d['arms'][act] = {
                'scene_equal_f1': float(g.groupby('scene')[f'eff_{act}'].mean().mean()),
                'mean_payload': float(g[f'B_{act}'].mean())}
        out['splits'][sp] = d
    json.dump(out, open(OUT_FA, 'w'), indent=1)
    print(f'wrote {os.path.relpath(OUT_FA, ROOT)}')
    for sp, d in out['splits'].items():
        for act, v in d['arms'].items():
            print(f'  {sp:7s} Fixed {act}: scene-equal F1 = {v["scene_equal_f1"]:.5f}   '
                  f'payload = {v["mean_payload"]:.5f}')
    return 0


OUT_MP = os.path.join(ROOT, 'results', 'v2', 'v2_matched_payload.json')

# V2-R56 A: the task-only rule's DIRECTION is fixed on the development split, where such choices
# are legitimate, and then applied unchanged to the held-out splits. On validate the L-gain falls
# as the ego's own detected box count rises (corr -0.2234): when the ego already sees a lot,
# cooperation buys less. So the rule requests L on LOW box counts.
TASK_RULE_DIRECTION = 'request L when ego_detected_box_count is low (fixed on validate, r=-0.2234)'
N_RANDOM_REPEATS = 200


def _greedy_match(score, b_l, target, rng=None):
    """Give L to the highest-scoring rows until the realised payload reaches `target`.

    This is how every matched-rate baseline is put on the same realised payload (A-5). For a score
    that is a cue, it IS a threshold rule with a randomised tie-break at the boundary tier, so it
    stays deployable; for the oracle score it is not, and the oracle is labelled accordingly.

    Ties are broken randomly rather than by row order: `snr_db` takes 11 distinct values, so a
    deterministic tie-break would silently order the boundary tier by scene, which is not a
    property of the rule.
    """
    n = len(score)
    jitter = (rng or np.random.default_rng(0)).random(n)
    order = np.lexsort((jitter, -np.asarray(score, float)))
    take = np.zeros(n, bool)
    acc = 0.0
    lim = target * n
    for i in order:
        if acc + b_l[i] > lim:
            break
        take[i] = True
        acc += b_l[i]
    return take


def _scene_equal(vals, scenes, uniq):
    return float(np.mean([vals[scenes == s].mean() for s in uniq]))


def _boot_diff(a, b, scenes, uniq, seed):
    """Scene-level bootstrap of the paired difference a - b (point estimate and LCB95)."""
    d = np.array([a[scenes == s].mean() - b[scenes == s].mean() for s in uniq])
    rng = np.random.default_rng(seed)
    bs = np.array([d[rng.integers(0, len(uniq), len(uniq))].mean() for _ in range(N_BOOT)])
    return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def matched_payload():
    """V2-R56 A/C — secondary analysis: E/L policies at CA-TOSG's OWN realised payload.

    **This is a statistical analysis of already-unsealed per-row results. Nothing is retrained, no
    GPU runs, no perception is re-evaluated, and no frozen component moves.** The frozen forest is
    loaded only to re-derive the action sequence that produced the published primary numbers, and
    the reproduction is ASSERTED against them: if the replayed scene-equal F1 and payload do not
    equal the published values to 1e-12, this refuses to write anything.

    Why not the closed-form estimate: multiplying each arm's split-wide mean F1 by an action share
    assumes a randomly chosen frame scores that arm's average. CA-TOSG's whole claim is that the
    frames it picks are not random, so that estimate can be wrong in either direction. Every number
    below is computed per row.
    """
    fr = json.load(open(FREEZE))
    mp = os.path.join(ROOT, fr['selector']['model_path'])
    if hashlib.sha256(open(mp, 'rb').read()).hexdigest() != fr['selector']['model_sha256']:
        raise SystemExit('frozen model hash moved -- refusing to run')
    import pickle
    rf = pickle.load(open(mp, 'rb'))
    tau = fr['primary_comparator']['tau']

    out = {'schema': 'catosg-v2-matched-payload/1',
           'status': 'SECONDARY ANALYSIS. Not the preregistered primary test, which remains the '
                     'non-inferiority comparison against the frozen tau rule and is unchanged.',
           'criterion': 'g*(B) = argmax_g scene-equal F1(g) s.t. mean realised payload <= B, with '
                        'B set to CA-TOSG\'s OWN realised payload on that split.',
           'task_rule_direction': TASK_RULE_DIRECTION,
           'random_repeats': N_RANDOM_REPEATS, 'boot': N_BOOT, 'splits': {}}

    for sp in ('test', 'culver'):
        g = pd.read_csv(os.path.join(SEALED, f'v2_grid_{sp}_ideal.csv'))
        cues = pd.read_csv(os.path.join(SEALED, f'wp6_cues_{sp}.csv'))
        meta = json.load(open(os.path.join(SEALED, f'wp6_cues_{sp}.json')))
        fi = g.sample_id.to_numpy()
        X = np.column_stack([cues[meta['perception_fields']].to_numpy(float)[fi],
                             g.snr_db.to_numpy(float),
                             (g.channel.to_numpy() == 'rayleigh').astype(float)])
        eff_e = g.eff_E.to_numpy(); eff_l = g.eff_L.to_numpy()
        b_l = g.B_L.to_numpy()
        scenes = g.scene.to_numpy(); uniq = pd.unique(scenes)
        nbox = cues.ego_detected_box_count.to_numpy()[fi].astype(float)
        snr = g.snr_db.to_numpy(float)

        rf_pred = rf.predict(X)
        r = np.arange(len(g))
        eff3 = g[['eff_E', 'eff_L', 'eff_F']].to_numpy()
        b3 = g[['B_E', 'B_L', 'B_F']].to_numpy()
        f1_rf, b_rf = eff3[r, rf_pred], b3[r, rf_pred]

        pub = json.load(open(os.path.join(ROOT, f'results/v2/v2_{sp}_primary.json')))
        got_f1 = _scene_equal(f1_rf, scenes, uniq)
        got_b = float(b_rf.mean())
        for name, got, want in (('scene_equal_f1', got_f1, pub['RF']['scene_equal_f1']),
                                ('mean_payload', got_b, pub['RF']['mean_payload'])):
            if abs(got - want) > 1e-12:
                raise SystemExit(f'{sp}: replayed {name} {got!r} != published {want!r} -- the '
                                 f'frozen policy did not reproduce; refusing to write')

        target = got_b
        pol = {}
        # deployable matched-rate baselines
        for key, score, dep in (
                ('snr_only', snr, True),
                ('task_only', -nbox, True),
                ('oracle_el', eff_l - eff_e, False)):
            take = _greedy_match(score, b_l, target, np.random.default_rng(20260903))
            f1 = np.where(take, eff_l, eff_e)
            pol[key] = {'scene_equal_f1': _scene_equal(f1, scenes, uniq),
                        'mean_payload': float(np.where(take, b_l, 0.0).mean()),
                        'share_L': float(take.mean()), 'deployable': dep, '_f1': f1}
        # Random at CA-TOSG's own rate, repeated. V2-R59 B-2: the reported F1, the difference and
        # the bootstrap must all come from ONE object -- the per-row mean over the repeats. The
        # first version averaged the summary over 200 draws but bootstrapped only draw 0, so a
        # single table row carried two different randomisations and its columns did not subtract
        # (0.87679 - 0.86881 = 0.00798 against a printed 0.00806). Nothing crashed and no gate
        # fired, because every number WAS generator-produced -- they were just not the same number
        # twice.
        acc_f1 = np.zeros(len(g)); rpay = []; per_draw = []
        for k in range(N_RANDOM_REPEATS):
            rng = np.random.default_rng(20260903 + k)
            take = _greedy_match(rng.random(len(g)), b_l, target, rng)
            f1 = np.where(take, eff_l, eff_e)
            acc_f1 += f1
            per_draw.append(_scene_equal(f1, scenes, uniq))
            rpay.append(float(np.where(take, b_l, 0.0).mean()))
        mean_f1 = acc_f1 / N_RANDOM_REPEATS
        pol['random_el'] = {'scene_equal_f1': _scene_equal(mean_f1, scenes, uniq),
                            'draw_lo': float(np.percentile(per_draw, 2.5)),
                            'draw_hi': float(np.percentile(per_draw, 97.5)),
                            'draw_spread_note': 'draw_lo/draw_hi are percentiles ACROSS DRAWS, a '
                                                'different quantity from the scene bootstrap; the '
                                                'two are never mixed.',
                            'mean_payload': float(np.mean(rpay)),
                            'share_L': None, 'deployable': True, '_f1': mean_f1}
        pol['ca_tosg'] = {'scene_equal_f1': got_f1, 'mean_payload': target,
                          'share_L': float((rf_pred == 1).mean()), 'deployable': True,
                          '_f1': f1_rf}

        # C-2: the same machinery against Fixed L, which is NOT payload-matched
        f1_fixed_l = eff_l
        d = {'target_payload': target, 'n_rows': int(len(g)), 'n_scenes': int(len(uniq)),
             'policies': {}, 'vs_ca_tosg': {}}
        for k, v in pol.items():
            d['policies'][k] = {kk: vv for kk, vv in v.items() if not kk.startswith('_')}
            d['policies'][k]['payload_residual_vs_target'] = float(v['mean_payload'] - target)
            if k == 'ca_tosg':
                continue
            pt, lo, hi = _boot_diff(pol['ca_tosg']['_f1'], v['_f1'], scenes, uniq, 20260903)
            d['vs_ca_tosg'][k] = {'delta_f1_point': pt, 'delta_f1_LCB95': lo,
                                  'delta_f1_UCB95': hi}
        # V2-R59 B-4: every row of the table must subtract. Asserted rather than trusted, because
        # the defect it catches passed every existing gate: those verify that a number came from a
        # generator, not that three columns of one row came from the same vector.
        ca_f1 = d['policies']['ca_tosg']['scene_equal_f1']
        for k_, v_ in d['policies'].items():
            if k_ == 'ca_tosg':
                continue
            gap = abs((ca_f1 - v_['scene_equal_f1']) - d['vs_ca_tosg'][k_]['delta_f1_point'])
            if gap > 1e-9:
                raise SystemExit(f'{sp}/{k_}: the column difference disagrees with the reported '
                                 f'delta by {gap:.2e} -- the row is built from more than one '
                                 f'object; refusing to write')
        pt, lo, hi = _boot_diff(pol['ca_tosg']['_f1'], f1_fixed_l, scenes, uniq, 20260903)
        d['vs_fixed_L'] = {'delta_f1_point': pt, 'delta_f1_LCB95': lo, 'delta_f1_UCB95': hi,
                           'fixed_L_scene_equal_f1': _scene_equal(f1_fixed_l, scenes, uniq),
                           'fixed_L_mean_payload': float(b_l.mean()),
                           'note': 'C-2 secondary: Fixed L is NOT payload-matched; it spends more.'}
        out['splits'][sp] = d

    json.dump(out, open(OUT_MP, 'w'), indent=1)
    print(f'wrote {os.path.relpath(OUT_MP, ROOT)}\n')
    for sp, d in out['splits'].items():
        print(f'=== {sp}  (target payload {d["target_payload"]:.5f} Msym, '
              f'{d["n_scenes"]} scenes) ===')
        for k, v in d['policies'].items():
            tag = '' if v['deployable'] else '  [not deployable]'
            print(f'  {k:11s} F1 {v["scene_equal_f1"]:.5f}  payload {v["mean_payload"]:.5f}'
                  f'  resid {v["payload_residual_vs_target"]:+.2e}{tag}')
        for k, v in d['vs_ca_tosg'].items():
            print(f'  CA-TOSG - {k:11s}  {v["delta_f1_point"]:+.5f}   '
                  f'LCB95 {v["delta_f1_LCB95"]:+.5f}')
        v = d['vs_fixed_L']
        print(f'  CA-TOSG - Fixed L      {v["delta_f1_point"]:+.5f}   '
              f'LCB95 {v["delta_f1_LCB95"]:+.5f}   (Fixed L payload {v["fixed_L_mean_payload"]:.5f})')
        print()
    return 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--unseal', action='store_true')
    ap.add_argument('--split', default='test', choices=['test', 'culver'])
    ap.add_argument('--matched-payload', action='store_true',
                    help='V2-R56 A: SECONDARY analysis -- E/L policies at CA-TOSG\'s own realised '
                         'payload. Statistical only; asserts the frozen policy reproduces the '
                         'published primary numbers before writing anything.')
    ap.add_argument('--fixed-arms', action='store_true',
                    help='V2-R55 A-1: aggregate the frozen grids into the descriptive fixed-arm '
                         'summary. Reads no model and writes no primary product.')
    a = ap.parse_args()
    if a.matched_payload:
        return matched_payload()
    if a.fixed_arms:
        return fixed_arms()
    if not a.unseal:
        raise SystemExit('this is the unseal step; pass --unseal deliberately')
    fr = json.load(open(FREEZE))
    tc = json.load(open(TIERC))
    if tc.get('unresolved_items_remaining', 1) != 0:
        raise SystemExit('the Tier C freeze still has unresolved items -- refusing to unseal')
    mp = os.path.join(ROOT, fr['selector']['model_path'])
    if hashlib.sha256(open(mp, 'rb').read()).hexdigest() != fr['selector']['model_sha256']:
        raise SystemExit('frozen model hash moved -- refusing to unseal')
    import pickle
    rf = pickle.load(open(mp, 'rb'))
    tau = fr['primary_comparator']['tau']

    sp = a.split
    g = pd.read_csv(os.path.join(SEALED, f'v2_grid_{sp}_ideal.csv'))
    cues = pd.read_csv(os.path.join(SEALED, f'wp6_cues_{sp}.csv'))
    meta = json.load(open(os.path.join(SEALED, f'wp6_cues_{sp}.json')))
    feat = meta['perception_fields']
    Xf = cues[feat].to_numpy(float)
    fi = g.sample_id.to_numpy()
    X = np.column_stack([Xf[fi], g.snr_db.to_numpy(float),
                         (g.channel.to_numpy() == 'rayleigh').astype(float)])
    eff = g[['eff_E', 'eff_L', 'eff_F']].to_numpy()
    B = g[['B_E', 'B_L', 'B_F']].to_numpy()
    scenes = g.scene.to_numpy()
    r = np.arange(len(g))

    rf_pred = rf.predict(X)
    tau_pred = np.where(g.snr_db.to_numpy(float) >= tau, 2, 1)
    f1_rf, f1_tau = eff[r, rf_pred], eff[r, tau_pred]
    b_rf, b_tau = B[r, rf_pred], B[r, tau_pred]

    us = pd.unique(scenes)
    per = {s: (f1_rf[scenes == s].mean() - f1_tau[scenes == s].mean(),
               b_rf[scenes == s].mean() - b_tau[scenes == s].mean()) for s in us}
    d_f1 = np.array([per[s][0] for s in us]); d_b = np.array([per[s][1] for s in us])
    rng = np.random.default_rng(20260809)
    bf = np.array([d_f1[rng.integers(0, len(us), len(us))].mean() for _ in range(N_BOOT)])
    bb = np.array([d_b[rng.integers(0, len(us), len(us))].mean() for _ in range(N_BOOT)])
    lcb_f1, ucb_b = float(np.percentile(bf, 2.5)), float(np.percentile(bb, 97.5))
    pt_f1, pt_b = float(d_f1.mean()), float(d_b.mean())
    rel = float((b_tau.mean() - b_rf.mean()) / b_tau.mean())

    ni = lcb_f1 > -DELTA
    pay = (ucb_b < 0) and (rel >= 0.10)
    out = {'schema': 'catosg-v2-test-primary/1', 'cell': f'{a.split} @ beta={BETA}', 'delta': DELTA,
           'unit': 'scene-level bootstrap', 'n_scenes': int(len(us)), 'n_rows': int(len(g)),
           'boot': N_BOOT,
           'RF': {'scene_equal_f1': float(np.mean([f1_rf[scenes == s].mean() for s in us])),
                  'mean_payload': float(b_rf.mean())},
           'tau': {'tau': tau,
                   'scene_equal_f1': float(np.mean([f1_tau[scenes == s].mean() for s in us])),
                   'mean_payload': float(b_tau.mean())},
           'delta_f1_point': pt_f1, 'delta_f1_LCB95': lcb_f1,
           'delta_payload_point': pt_b, 'delta_payload_UCB95': ucb_b,
           'relative_payload_saving': rel,
           'non_inferiority_met': bool(ni), 'payload_criterion_met': bool(pay),
           'primary_met': bool(ni and pay),
           'action_mix': {k: float((rf_pred == i).mean()) for i, k in enumerate(['E', 'L', 'F'])},
           'WORDING': 'R9 family: non-inferiority + payload saving. It may NOT be written as the RF '
                      'having better F1; "same F1" and "no loss" are forbidden (V2-R28 C-3).'}
    # V2-R6 B-3 / V2-R34 B-6: BOTH accountings, always, with the difference stated. Culver has
    # 13.09 % no-collaborator frames against test's 5.48 % -- a factor 2.4 -- and on those frames
    # every arm costs zero, so part of any apparent saving is collaborator UNAVAILABILITY rather
    # than policy. The decomposition below separates the two; they may never be conflated.
    hc = g.has_collaborator.to_numpy() == 1
    sub = np.array([s for s in us if hc[scenes == s].any()])
    def acct(mask):
        f1r, f1t = f1_rf[mask], f1_tau[mask]; br, bt = b_rf[mask], b_tau[mask]; sc = scenes[mask]
        u = pd.unique(sc)
        return {'n_rows': int(mask.sum()),
                'RF_scene_equal_f1': float(np.mean([f1r[sc == s].mean() for s in u])),
                'tau_scene_equal_f1': float(np.mean([f1t[sc == s].mean() for s in u])),
                'RF_payload': float(br.mean()), 'tau_payload': float(bt.mean()),
                'relative_saving': float((bt.mean() - br.mean()) / bt.mean())}
    full = acct(np.ones(len(g), bool)); avail = acct(hc)
    out['dual_accounting'] = {
        'full_frame': full, 'collaborator_available_only': avail,
        'no_collaborator_share': float((~hc).mean()),
        'difference_in_relative_saving': full['relative_saving'] - avail['relative_saving'],
        'reading': 'The two figures are reported together and never mixed (V2-R6 B-3). The gap '
                   'between them is the part of the apparent saving that comes from collaborator '
                   'unavailability rather than from policy choice (V2-R6 B-5).'}
    json.dump(out, open(OUT_T.replace('v2_test_primary', f'v2_{sp}_primary'), 'w'), indent=1)
    d = out['dual_accounting']
    print(f'\n  DUAL ACCOUNTING (V2-R6 B-3) -- no-collaborator share '
          f'{d["no_collaborator_share"]*100:.2f} %')
    print(f'    full-frame                saving {full["relative_saving"]*100:.2f} %   '
          f'RF F1 {full["RF_scene_equal_f1"]:.5f}  tau F1 {full["tau_scene_equal_f1"]:.5f}')
    print(f'    collaborator-available    saving {avail["relative_saving"]*100:.2f} %   '
          f'RF F1 {avail["RF_scene_equal_f1"]:.5f}  tau F1 {avail["tau_scene_equal_f1"]:.5f}')
    print(f'    difference attributable to unavailability: '
          f'{d["difference_in_relative_saving"]*100:+.3f} pp')
    print('=' * 78); print(f'TEST PRIMARY -- {out["cell"]}, {out["n_scenes"]} scenes, '
                           f'{out["n_rows"]} rows'); print('=' * 78)
    print(f'  RF   scene-equal F1 {out["RF"]["scene_equal_f1"]:.5f}   payload {out["RF"]["mean_payload"]:.5f}')
    print(f'  tau  scene-equal F1 {out["tau"]["scene_equal_f1"]:.5f}   payload {out["tau"]["mean_payload"]:.5f}  (tau={tau})')
    print(f'  dF1  point {pt_f1:+.5f}   LCB95 {lcb_f1:+.5f}   (delta = -{DELTA})   '
          f'non-inferior: {ni}')
    print(f'  dB   point {pt_b:+.5f}   UCB95 {ucb_b:+.5f}   relative saving {rel*100:.2f} %   '
          f'met: {pay}')
    print(f'  action mix {out["action_mix"]}')
    print(f'\n  PRIMARY CRITERION MET: {out["primary_met"]}')
    print(f'wrote results/v2/v2_{sp}_primary.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
