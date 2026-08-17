#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R23-C: the three R20-item-10 sensitivities, exactly as pre-registered in Change-log R23-C.

  1. scene-level bootstrap of the primary cell (test @ B_max=0.20), with R20's own ruling applied;
  2. L-link reliability, BLER_L in {0, 0.01, 0.05, 0.10}, analytic reweighting on the DEPLOYMENT draw;
  3. fragmentation / HARQ, k in {2,4} with one retransmission, frame BLER re-derived from the
     committed CODEWORD BLER at N_cw = 3960.

Zero GPU. Everything reads the committed caches, the frozen selectors and the committed BLER table,
and every arm re-uses `deployment.py`'s generator, seed, draw order and eff definition. Three
invariants are asserted at run time rather than assumed:

  * the BLER_L = 0 row must reproduce `replay_summary.csv` exactly;
  * fragmentation WITHOUT HARQ must leave the frame BLER unchanged for every k (it is algebraically
    independent of k, so a difference means the implementation is wrong);
  * the k=1 no-HARQ frame BLER re-derived here must reproduce the committed `bler_frame` column.

Outputs (results/sensitivity/): r23_scene_bootstrap.csv, r23_object_message_bler.csv,
r23_fragmentation_harq.csv, r23_fragmentation_bler.csv + PROVENANCE_r23c.txt

    python projects/ca_tosg/evaluation/r23_sensitivity.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import deployment as D                                                            # noqa: E402

OUT = os.path.join(D.P1, 'results/sensitivity')
PROV = os.path.join(D.PROV_DIR, 'PROVENANCE_r23c.txt')
REPLAY_SUMM = os.path.join(D.P1, 'results/main/replay_summary.csv')

N_CW = 3960                    # 1.98 Mbit / K=500, the payload chain's own number (tests/test_payload)
BLER_L_GRID = (0.0, 0.01, 0.05, 0.10)
K_FRAGS = (1, 2, 4)
BLER_INFEASIBLE = 0.999        # PROTOCOL sec 4, the feasibility-mask constant
DELTA = D.DELTA


def fuse(msg):
    raise SystemExit(f'R23-C FUSE: {msg}')


def draws(ds):
    """The deployment draw: same generator, seed and call order as deployment.main()."""
    n = len(ds)
    rng = np.random.default_rng(D.CSI_SEED)
    snr_2d = rng.uniform(0, 20, size=(D.N_REPLAY, n))
    is_ray_2d = rng.random(size=(D.N_REPLAY, n)) < 0.5
    return snr_2d, is_ray_2d


def eff_L_blerL(late, ego, bler_L):
    """eff_L' = late(1-BLER_L) + ego*BLER_L. eff_E and eff_F are untouched (R23-C item 2)."""
    return late * (1 - bler_L) + ego * bler_L


# ---------------------------------------------------------------- 1. scene bootstrap
def scene_bootstrap(rows, prov):
    split, bmax, tag = 'test', 0.20, '0.20'
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
    n = len(ds)
    grid = pd.read_csv(os.path.join(D.GRID_DIR, f'p2_grid_{split}.csv'))
    scene_of = grid.drop_duplicates('sample_id').set_index('sample_id')['scene']
    scenes = ds['sample_id'].map(scene_of)
    if scenes.isna().any():
        fuse('frame -> scene mapping incomplete for the test split')
    scenes = scenes.to_numpy()
    uscenes = np.unique(scenes)

    _, budgets = D.load_manifest()
    bd = budgets[tag]
    tbl = pd.read_csv(D.BLER_CSV)
    snr_2d, is_ray_2d = draws(ds)
    bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(D.N_REPLAY)])
    rf_idx = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr_2d, is_ray_2d)
    ta_idx = D.tau_actions(snr_2d, is_ray_2d, bd['tau'])

    ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
    dF_frame = np.zeros(n)
    dB_frame = np.zeros(n)
    for r in range(D.N_REPLAY):
        E = D.eff_matrix(ego, late, comp, bF_2d[r])
        dF_frame += E[np.arange(n), rf_idx[r]] - E[np.arange(n), ta_idx[r]]
        dB_frame += D.PAYVEC[rf_idx[r]] - D.PAYVEC[ta_idx[r]]
    dF_frame /= D.N_REPLAY
    dB_frame /= D.N_REPLAY

    idx_by_scene = [np.flatnonzero(scenes == s) for s in uscenes]
    rng = np.random.default_rng(D.BOOT_SEED)
    bF1 = np.empty(D.N_BOOT); bB = np.empty(D.N_BOOT)
    for b in range(D.N_BOOT):
        pick = rng.integers(0, len(uscenes), size=len(uscenes))
        sel = np.concatenate([idx_by_scene[p] for p in pick])       # frame-weighted, as pre-registered
        bF1[b] = dF_frame[sel].mean()
        bB[b] = dB_frame[sel].mean()
    out = {}
    for name, mean_v, boot in (('dF', dF_frame.mean(), bF1), ('dB', dB_frame.mean(), bB)):
        lo, hi = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
        out[name] = (float(mean_v), lo, hi)

    ref = pd.read_csv(REPLAY_SUMM)
    p = ref[(ref.split == split) & (np.isclose(ref.budget, bmax))].iloc[0]
    crosses = out['dF'][1] <= -DELTA
    verdict = ('INCONCLUSIVE under scene-level resampling (R20 item 10.1 ruling)' if crosses
               else 'R9 condition 1 survives scene-level resampling')
    for name, unit in (('dF', 'F1'), ('dB', 'Msym')):
        m, lo, hi = out[name]
        rows.append(dict(split=split, budget=bmax, quantity=name, unit=unit,
                         resampling='scene (cluster)', n_units=len(uscenes),
                         mean=round(m, 6), lcb95=round(lo, 6), ucb95=round(hi, 6),
                         published_mean=round(float(p[f'{name}_mean']), 6),
                         published_lcb95=round(float(p[f'{name}_lcb95']), 6),
                         published_ucb95=round(float(p[f'{name}_ucb95']), 6),
                         width_ratio=round((hi - lo) / (float(p[f'{name}_ucb95'])
                                                        - float(p[f'{name}_lcb95'])), 3),
                         delta=DELTA if name == 'dF' else None,
                         crosses_minus_delta=(bool(crosses) if name == 'dF' else None),
                         verdict=(verdict if name == 'dF' else '')))
    prov.append(f'1. scene bootstrap: {len(uscenes)} test scenes, {D.N_BOOT} resamples, '
                f'seed={D.BOOT_SEED}; dF scene-level [{out["dF"][1]:+.5f}, {out["dF"][2]:+.5f}] vs '
                f'published [{p.dF_lcb95:+.5f}, {p.dF_ucb95:+.5f}]; {verdict}')
    print(f'[1] scene bootstrap  dF={out["dF"][0]:+.5f} [{out["dF"][1]:+.5f}, {out["dF"][2]:+.5f}] '
          f'({len(uscenes)} scenes)  vs published [{p.dF_lcb95:+.5f}, {p.dF_ucb95:+.5f}]  -> {verdict}')
    return out


# ---------------------------------------------------------------- 2. L-link reliability
def object_message_bler(rows, prov):
    _, budgets = D.load_manifest()
    tbl = pd.read_csv(D.BLER_CSV)
    ref = pd.read_csv(REPLAY_SUMM)
    for split in D.SPLITS:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy()
        comp = ds['compressed_f1'].to_numpy()
        snr_2d, is_ray_2d = draws(ds)
        bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(D.N_REPLAY)])
        for tag in sorted(budgets):
            bd = budgets[tag]; bmax = float(tag)
            rf_idx = D.rf_actions_stacked(bd['model'], bd['feat'], ds, snr_2d, is_ray_2d)
            ta_idx = D.tau_actions(snr_2d, is_ray_2d, bd['tau'])
            for bl in BLER_L_GRID:
                effL = eff_L_blerL(late, ego, bl)
                F = {k: np.empty(D.N_REPLAY) for k in ('RF', 'TA', 'L')}
                B = {k: np.empty(D.N_REPLAY) for k in ('RF', 'TA', 'L')}
                for r in range(D.N_REPLAY):
                    E = np.stack([ego, effL, comp * (1 - bF_2d[r]) + ego * bF_2d[r]], axis=1)
                    for k, idx in (('RF', rf_idx[r]), ('TA', ta_idx[r])):
                        F[k][r] = E[np.arange(n), idx].mean(); B[k][r] = D.PAYVEC[idx].mean()
                    F['L'][r] = E[:, 1].mean(); B['L'][r] = D.PAY['L']
                dF = F['RF'] - F['TA']
                m, lo, hi = D.paired_bootstrap(dF, D.N_BOOT, D.BOOT_SEED)
                if bl == 0.0:                                   # pre-registered invariant
                    p = ref[(ref.split == split) & (np.isclose(ref.budget, bmax))].iloc[0]
                    if abs(round(F['RF'].mean(), 5) - float(p.F1_RF)) > 1e-5:
                        fuse(f'BLER_L=0 does not reproduce replay_summary at {split} B{bmax}: '
                             f'{F["RF"].mean():.5f} vs {float(p.F1_RF):.5f}')
                rows.append(dict(split=split, budget=bmax, bler_L=bl,
                                 F1_RF=round(F['RF'].mean(), 5), F1_tau=round(F['TA'].mean(), 5),
                                 F1_FixedL=round(F['L'].mean(), 5),
                                 B_RF=round(B['RF'].mean(), 5), B_tau=round(B['TA'].mean(), 5),
                                 dF_mean=round(m, 5), dF_lcb95=round(lo, 5), dF_ucb95=round(hi, 5),
                                 payload_reduction=round(float((B['TA'].mean() - B['RF'].mean())
                                                               / B['TA'].mean()), 5)))
        print(f'[2] BLER_L sweep done: {split}', flush=True)
    prov.append(f'2. BLER_L in {BLER_L_GRID}: frozen actions, deployment draw (seed={D.CSI_SEED}); '
                'eff_L only is reweighted; payload is invariant by construction; the BLER_L=0 row '
                'is asserted equal to replay_summary.csv at every split x budget.')


# ---------------------------------------------------------------- 3. fragmentation / HARQ
def frag_bler(b_cw, k, harq):
    """Frame BLER for k fragments of N_cw/k codewords, all required, with 0 or 1 retransmission."""
    q = 1.0 - np.power(1.0 - b_cw, N_CW / k)            # one fragment fails
    if harq:
        q = q ** 2                                       # ... and fails again on the retransmission
    return 1.0 - np.power(1.0 - q, k), q


def fragmentation(rows_b, rows, prov):
    tbl = pd.read_csv(D.BLER_CSV)
    t16 = tbl[tbl.qam == 16].copy()
    # invariant (a): k=1, no HARQ must reproduce the committed bler_frame column
    b1, _ = frag_bler(t16.bler_cw.to_numpy(), 1, False)
    if not np.allclose(b1, t16.bler_frame.to_numpy(), atol=1e-6):
        fuse('k=1 no-HARQ frame BLER does not reproduce the committed bler_frame column')
    # invariant (b): fragmentation WITHOUT HARQ is independent of k
    for k in K_FRAGS:
        bk, _ = frag_bler(t16.bler_cw.to_numpy(), k, False)
        if not np.allclose(bk, b1, atol=1e-9):
            fuse(f'no-HARQ frame BLER changed with k={k}; it is algebraically independent of k')

    for _, r in t16.iterrows():
        for k in K_FRAGS:
            for harq in (False, True):
                b, q = frag_bler(np.array([r.bler_cw]), k, harq)
                rows_b.append(dict(qam=16, channel=r.channel, esno_db=r.esno_db,
                                   bler_cw=r.bler_cw, k=k, harq=int(harq),
                                   n_cw_per_fragment=int(N_CW / k),
                                   q_fragment=round(float(q[0]), 6),
                                   bler_frame=round(float(b[0]), 6),
                                   payload_factor=round(float(1 + (1 - (1 - r.bler_cw)
                                                                   ** (N_CW / k)) if harq else 1.0), 6),
                                   feasible=bool(b[0] < BLER_INFEASIBLE)))

    # what the paper's Rayleigh conclusion has to survive
    for k in K_FRAGS:
        for harq in (False, True):
            for ch in ('awgn', 'rayleigh'):
                s = t16[t16.channel == ch].sort_values('esno_db')
                b, q = frag_bler(s.bler_cw.to_numpy(), k, harq)
                ok = np.flatnonzero(b < BLER_INFEASIBLE)
                onset = float(s.esno_db.to_numpy()[ok[0]]) if len(ok) else float('nan')
                in_range = s.esno_db.between(0, 20)
                rows.append(dict(channel=ch, k=k, harq=int(harq),
                                 n_cw_per_fragment=int(N_CW / k),
                                 cliff_onset_db=onset,
                                 min_bler_frame_0_20db=round(float(b[in_range.to_numpy()].min()), 6),
                                 feasible_points_0_20db=int((b[in_range.to_numpy()]
                                                             < BLER_INFEASIBLE).sum()),
                                 mean_payload_factor=round(float(np.mean(1 + q if harq else
                                                                         np.ones_like(q))), 6)))
    ray = [r for r in rows if r['channel'] == 'rayleigh' and r['harq'] == 1]
    worst = min(r['min_bler_frame_0_20db'] for r in ray)
    prov.append(f'3. fragmentation/HARQ: N_cw={N_CW}; no-HARQ frame BLER asserted independent of k '
                f'and equal to the committed column at k=1. With one retransmission and k in '
                f'{K_FRAGS[1:]}, the LOWEST Rayleigh frame BLER over 0-20 dB is {worst:.6f} '
                f'(feasibility mask {BLER_INFEASIBLE}).')
    print(f'[3] fragmentation/HARQ: lowest Rayleigh frame BLER over 0-20 dB with HARQ = {worst:.6f}')
    return worst


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    prov = []
    sb, bl, fr, fb = [], [], [], []
    scene_bootstrap(sb, prov)
    object_message_bler(bl, prov)
    fragmentation(fb, fr, prov)
    pd.DataFrame(sb).to_csv(os.path.join(OUT, 'r23_scene_bootstrap.csv'), index=False)
    pd.DataFrame(bl).to_csv(os.path.join(OUT, 'r23_object_message_bler.csv'), index=False)
    pd.DataFrame(fr).to_csv(os.path.join(OUT, 'r23_fragmentation_harq.csv'), index=False)
    pd.DataFrame(fb).to_csv(os.path.join(OUT, 'r23_fragmentation_bler.csv'), index=False)
    with open(PROV, 'w') as f:
        f.write('CA-TOSG R23-C -- the three R20 item-10 sensitivities (r23_sensitivity.py).\n'
                'Pre-registered in Change-log R23-C BEFORE this file existed. Zero GPU.\n' + '=' * 88 + '\n')
        f.write(f'CSI: the deployment draw, {D.N_REPLAY} realisations/split, seed={D.CSI_SEED}; '
                f'bootstrap {D.N_BOOT} resamples, seed={D.BOOT_SEED}; delta={DELTA}.\n')
        for line in prov:
            f.write(line + '\n')
        f.write('Frozen selectors, tau*, delta, the BLER table and every deployed product are '
                'unchanged; nothing here is a decision except the R20 item-10.1 ruling, which is '
                'applied verbatim.\n')
    print(f'\nwrote {OUT}/r23_{{scene_bootstrap,object_message_bler,fragmentation_harq,'
          f'fragmentation_bler}}.csv\n      {PROV}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
