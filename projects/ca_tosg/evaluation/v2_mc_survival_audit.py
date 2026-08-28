#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R19 C — the message-regime Monte Carlo survival counts. Zero GPU, zero forwards.

WHY THIS EXISTS
---------------
`results/v2/wp5_message_validate.json` reports, per loss rate, `ap50_mc_std` = 1.11e-16 — float
epsilon. Reporting that as "the draw has no variance" would be a claim about the random process;
what was actually observed is a standard deviation below display precision. **Those are two
different levels of statement, and the second does not license the first.**

At p = 0.001 the message-survival probability is q = (1-p)^12567 = 3.463e-6, so over the whole
Monte Carlo — 200 replays x 1980 frames — the expected number of surviving messages is

    200 x 1980 x 3.463e-6 = 1.371

which is of order one, **not zero**. A run in which nothing survives is therefore an ordinary
outcome of a process with real variance, and must be written as an observation
("under the fixed Monte-Carlo seed, no surviving message was observed"), never as a necessity
("fallback is certain", "the draw has no variance").

This module recovers what the summary never recorded: the **actual** per-replay survival counts.
It reproduces the exact draw of `v2_wp5_message.py` — same generator, same seed schedule, same
comparison — and counts, without recomputing a single AP.

    rng     = np.random.default_rng(MC_SEED + ri * 7919 + r)
    survive = rng.random(n) < q

    python projects/ca_tosg/evaluation/v2_mc_survival_audit.py --split validate
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, 'results', 'v2')

# Reproduced from the generators rather than re-chosen here; asserted against the product below.
BASE_SEED, SEED_K = 20260809, 1000003
RATES = (0.001, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90)
N_REPLAY = 200
MC_SEED = BASE_SEED + 7 * SEED_K


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate')
    args = ap.parse_args()

    prod_path = os.path.join(OUT_DIR, f'wp5_message_{args.split}.json')
    if not os.path.exists(prod_path):
        raise SystemExit(f'missing product: {os.path.relpath(prod_path, ROOT)}')
    prod = json.load(open(prod_path))

    n, n_cw = int(prod['frames']), int(prod['n_cw'])
    if int(prod['mc_seed_base']) != MC_SEED:
        raise SystemExit(f'seed schedule drifted: product {prod["mc_seed_base"]} vs {MC_SEED}')
    if int(prod['n_replays']) != N_REPLAY:
        raise SystemExit(f'replay count drifted: product {prod["n_replays"]} vs {N_REPLAY}')

    print('=' * 92)
    print(f'V2-R19 C -- message-regime Monte Carlo survival counts: {args.split}, '
          f'{n} frames, N_cw = {n_cw}, {N_REPLAY} replays')
    print('=' * 92)
    print(f'{"p":>7} {"q = (1-p)^N_cw":>16} {"E[surv] / replay":>17} {"E[surv] total":>14} '
          f'{"OBSERVED total":>15} {"replays w/ >0":>13} {"AP@0.5 std (unrounded)":>24}')

    rows = {}
    for ri, p in enumerate((0.0,) + RATES + (1.0,)):
        q = float((1 - p) ** n_cw)
        counts = []
        for r in range(N_REPLAY):
            rng = np.random.default_rng(MC_SEED + ri * 7919 + r)
            counts.append(int((rng.random(n) < q).sum()))
        counts = np.asarray(counts)
        key = str(p)
        pj = prod['message_regime'].get(key, {})
        # the product's own field is the PER-REPLAY expectation, q*n. The whole-Monte-Carlo
        # expectation is N_REPLAY x that, and it is the one that decides whether zero is surprising.
        rows[key] = {
            'p': p, 'q_message_survives': q,
            'expected_surviving_per_replay': q * n,
            'expected_surviving_total_over_all_replays': N_REPLAY * q * n,
            'observed_total_surviving': int(counts.sum()),
            'observed_replays_with_at_least_one': int((counts > 0).sum()),
            'observed_per_replay_min': int(counts.min()),
            'observed_per_replay_max': int(counts.max()),
            'observed_per_replay_counts': counts.tolist(),
            'ap50_mc_std_unrounded': pj.get('ap50_mc_std'),
            'ap70_mc_std_unrounded': pj.get('ap70_mc_std'),
            'ap50_mc_mean_unrounded': pj.get('ap50_mc_mean'),
        }
        r_ = rows[key]
        print(f'{p:>7} {q:>16.6e} {r_["expected_surviving_per_replay"]:>17.5f} '
              f'{r_["expected_surviving_total_over_all_replays"]:>14.4f} '
              f'{r_["observed_total_surviving"]:>15d} '
              f'{r_["observed_replays_with_at_least_one"]:>13d} '
              f'{str(r_["ap50_mc_std_unrounded"]):>24}')

    # The wording rule, applied mechanically rather than chosen after reading the table.
    verdicts = {}
    for key, r_ in rows.items():
        if r_['p'] in (0.0, 1.0):
            continue
        obs, exp_tot = r_['observed_total_surviving'], \
            r_['expected_surviving_total_over_all_replays']
        if obs > 0:
            v = ('OBSERVED SURVIVORS -- the regime is a genuine mixture at this rate; '
                 'report the counts.')
        elif exp_tot >= 0.01:
            v = ('NO SURVIVOR OBSERVED under the fixed Monte-Carlo seed, but the expected count '
                 f'over the whole Monte Carlo is {exp_tot:.4f} -- of the same order as one. This '
                 'is an OBSERVATION, not a necessity. FORBIDDEN wordings: "fallback is certain", '
                 '"the draw has no variance", "std is 0". Permitted: "under the fixed Monte-Carlo '
                 'seed no surviving message was observed".')
        else:
            v = ('NO SURVIVOR OBSERVED and the expected count over the whole Monte Carlo is '
                 f'{exp_tot:.3e} -- far below one. Fallback is effectively certain here, and that '
                 'may be said as an arithmetic consequence of q, still with the count reported.')
        verdicts[key] = v

    out = {
        'schema': 'catosg-v2-mc-survival/1', 'split': args.split,
        'frames': n, 'n_cw': n_cw, 'n_replays': N_REPLAY, 'mc_seed_base': MC_SEED,
        'method': 'Exact replay of v2_wp5_message.py\'s draw: '
                  'np.random.default_rng(MC_SEED + ri*7919 + r).random(n) < q. '
                  'No AP is recomputed; only the survival indicator is counted.',
        'why': 'The product recorded only q*n (the per-replay expectation) and an AP std at float '
               'epsilon. Neither is a survival count, and "std displays as 0.00000" is a statement '
               'about display precision, not about the random process.',
        'rates': rows, 'wording_verdicts': verdicts,
    }
    path = os.path.join(OUT_DIR, f'mc_survival_{args.split}.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('-' * 92)
    for k, v in verdicts.items():
        print(f'  p={k}: {v}')
    print(f'\nwrote {os.path.relpath(path, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
