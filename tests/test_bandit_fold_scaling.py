#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard for erratum P4A-1: a LOSO fold's feature scaler must never see the held-out scene.

The defect this exists to prevent: fitting the z-score statistics once on the whole validate grid
and then running LOSO on them, so every fold judged its held-out scene on a scale that scene had
helped set -- and the OOF numbers that leak reached are the substrate lambda is selected on.

Three checks, the last two adversarial:

  1. DIRECT      fold_scaler(X, scene, k) == the statistics of X[scene != k], exactly.
  2. POISON      corrupt ONLY the held-out scene's rows. The fold scaler must be bit-identical to
                 before; the global scaler must move. If the poison did not move the global scaler
                 the test proves nothing, so that is asserted too -- the test must be able to bite.
  3. END-TO-END  run oof_loso with the network training stubbed out, capture the matrices it hands
                 to the trainer, and verify each fold's train AND held-out rows were standardised
                 with the training-scene statistics. This is the assertion that actually covers the
                 code path; 1 and 2 only cover the helper.

  python tests/test_bandit_fold_scaling.py
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'baselines/contextual_bandit'))
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))

import train as T  # noqa: E402

RNG = np.random.default_rng(20260812)
N_SCENE, N_PER, N_FEAT = 4, 25, 6


def toy():
    scene = np.repeat([f's{i}' for i in range(N_SCENE)], N_PER)
    X = RNG.normal(size=(N_SCENE * N_PER, N_FEAT))
    for i in range(N_SCENE):                       # give each scene its own location/scale
        X[scene == f's{i}'] = X[scene == f's{i}'] * (1 + i) + 3 * i
    eff = RNG.random((len(scene), 3)).astype(np.float32)
    return X, eff, scene


def check_direct(X, scene, fails):
    for k in sorted(set(scene)):
        mu, sd = T.fold_scaler(X, scene, k)
        tr = X[scene != k]
        want_mu, want_sd = tr.mean(0), tr.std(0)
        want_sd = np.where(want_sd == 0, 1.0, want_sd)
        if not (np.array_equal(mu, want_mu) and np.array_equal(sd, want_sd)):
            fails.append('fold %s: scaler != statistics of the training scenes' % k)
        held = X[scene == k]
        if np.allclose(mu, np.concatenate([tr, held]).mean(0)):
            fails.append('fold %s: scaler equals the FULL-grid statistics -- held-out scene included'
                         % k)
    print('  1. direct        %d folds: scaler == training-scene statistics' % len(set(scene)))


def check_poison(X, scene, fails):
    k = sorted(set(scene))[0]
    mu0, sd0 = T.fold_scaler(X, scene, k)
    glob0 = X.mean(0)
    Xp = X.copy()
    Xp[scene == k] += 1e4                                   # poison the held-out scene ONLY
    mu1, sd1 = T.fold_scaler(Xp, scene, k)
    glob1 = Xp.mean(0)
    if not (np.array_equal(mu0, mu1) and np.array_equal(sd0, sd1)):
        fails.append('poisoning the HELD-OUT scene changed the fold scaler -- it is not fold-local')
    if np.allclose(glob0, glob1):
        fails.append('the poison did not move the full-grid statistics either: this check cannot '
                     'distinguish the two implementations and proves nothing')
    print('  2. poison        held-out scene +1e4: fold scaler unchanged, global scaler moved '
          '(so the check bites)')


def check_end_to_end(X, eff, scene, fails):
    seen = []
    real_train, real_greedy = T.train_bandit, T.greedy_actions
    T.train_bandit = lambda Xtr, e, lam, blk, seed: seen.append(('train', np.array(Xtr))) or 'net'
    T.greedy_actions = lambda net, Xte: (seen.append(('held', np.array(Xte)))
                                         or np.zeros(len(Xte), dtype=int))
    try:
        blk = {'train': {}, 'network': {}}
        T.oof_loso(X, eff, scene, 0.05, blk, 0)
    finally:
        T.train_bandit, T.greedy_actions = real_train, real_greedy

    scenes = sorted(set(scene))
    if len(seen) != 2 * len(scenes):
        fails.append('oof_loso did not run one train+held pair per fold (%d entries)' % len(seen))
        return
    for i, k in enumerate(scenes):
        mu, sd = T.fold_scaler(X, scene, k)
        for kind, got in (seen[2 * i], seen[2 * i + 1]):
            src = X[scene != k] if kind == 'train' else X[scene == k]
            want = ((src - mu) / sd).astype(np.float32)
            if not np.allclose(got, want, atol=0, rtol=0):
                fails.append('fold %s: the %s matrix was not standardised with the fold-local '
                             'statistics' % (k, kind))
    print('  3. end-to-end    %d folds: train AND held-out standardised with training-scene stats'
          % len(scenes))


def main():
    X, eff, scene = toy()
    fails = []
    print('P4-A fold-local scaling:')
    check_direct(X, scene, fails)
    check_poison(X, scene, fails)
    check_end_to_end(X, eff, scene, fails)
    if fails:
        print('\nFOLD-SCALING GATE FAIL:')
        for f in fails:
            print('  ' + f)
        return 1
    print('FOLD-SCALING GATE PASS: no fold scaler sees its held-out scene.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
