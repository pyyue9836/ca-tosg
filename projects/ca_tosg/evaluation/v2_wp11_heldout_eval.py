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


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--unseal', action='store_true')
    ap.add_argument('--split', default='test', choices=['test', 'culver'])
    ap.add_argument('--fixed-arms', action='store_true',
                    help='V2-R55 A-1: aggregate the frozen grids into the descriptive fixed-arm '
                         'summary. Reads no model and writes no primary product.')
    a = ap.parse_args()
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
