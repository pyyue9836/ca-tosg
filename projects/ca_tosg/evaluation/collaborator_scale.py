#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-C evaluation: collaborator scale N ∈ {1,2,3}, delivery semantics A (Change-log P4-C).

Reads the per-arm caches built by datasets/p4c_sweep.py and replays the FROZEN selectors over the
same 200 paired CSI draws as the mainline. Nothing is retrained and no model is touched.

Three rulings, all following existing protocol rather than inventing anything, and all recorded in
PROVENANCE_p4c.txt:

 1. ONE CANONICAL GT FOR EVERY N. Restricting the CAV set also shrinks the post-processor's union
    GT, so per-N GT would put every arm on a different ruler and make the F1 column meaningless.
    The GT is therefore held at the FULL-set canonical union GT for all arms -- the same
    "one canonical union GT" rule true_e2e_global.py already applies across branches.
 2. DELIVERY, semantics A (all-or-nothing, pre-registered): the feature request succeeds only if
    all N links deliver, so with per-link frame BLER b the expected utility is
        eff_F(N) = comp_N · (1-b)^N + ego · (1 - (1-b)^N)
    which reduces to the mainline expression at N=1. Object-level messages keep BLER_L = 0.
 3. PAYLOAD: one message per collaborator actually addressed, B_a × k_eff (§5: the budget bounds
    the MEAN, so k_eff scales the mean rather than any per-frame cap).
 4. k_eff = min(N, collaborators in that frame). A frame cannot message collaborators it does not
    have: charging the nominal N would bill for unsendable messages and would make Culver N=3
    differ from N=2, which the pre-registered invariant forbids. This ruling was FORCED by that
    invariant firing on the first run -- it is a bug the pre-registration caught, not a choice.

The selector's 23 features contain nothing about N, so its per-frame ACTION is N-independent; what
changes with N is what an action costs and what it delivers.

  python projects/ca_tosg/evaluation/collaborator_scale.py
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(HERE, '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/models', 'projects/ca_tosg/utils'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
_s.path.insert(0, _CT_ROOT)
import deployment as D                                                    # noqa: E402
from projects.ca_tosg.models.oracle import PAYVEC                         # noqa: E402

ROOT = D.P1
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
GS = os.path.join(OPENCOOD, 'peiyi_work/paper1/gs_rerun')
OUT_CSV = os.path.join(ROOT, 'results/sensitivity/collaborator_scale.csv')
PROV = os.path.join(ROOT, 'results/provenance/PROVENANCE_p4c.txt')
MANIFEST = os.path.join(ROOT, 'results/manifests/P4C_MANIFEST.json')
FROZEN = os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')
NS = (1, 2, 3)
LABEL = 'collaborator-scale arm, not deployed'
LABEL_B = 'bracketing variant, validate only, N=2, not deployed'
B_SPLIT, B_N = 'validate', 2
B_SECOND = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')  # placeholder
sys.path.insert(0, OPENCOOD)
from opencood.utils import eval_utils                                     # noqa: E402


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def f1_from_boxes(pred, gt, iou=0.5):
    """Per-frame F1 against a fixed GT (the scorer run_ego_only.py already uses)."""
    pred = np.asarray(pred, np.float32); gt = np.asarray(gt, np.float32)
    pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
    gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
    rs = {iou: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, iou)
    tp = float(sum(rs[iou]['tp'])); fp = float(sum(rs[iou]['fp'])); g = float(rs[iou]['gt'])
    p = tp / (tp + fp) if tp + fp > 0 else 0.0
    r = tp / g if g > 0 else 0.0
    return 2 * p * r / (p + r) if p + r > 0 else 0.0


def second_only_f1(split, gts):
    """Per-frame F1 of the {second-nearest alone} delivered subset (semantics-B bracket)."""
    out = {}
    for branch, key in (('late', 'L'), ('intermediate', 'F')):
        p = os.path.join(GS, 'p4c_B_second/%s_%s.npz' % (branch, split))
        if not os.path.exists(p):
            return None
        z = np.load(p, allow_pickle=True)
        out[key] = np.array([f1_from_boxes(z['boxes'][i], gts[i]) for i in range(len(gts))])
    return out


def per_frame_f1(split):
    """{(branch, N): array of per-frame F1} scored against ONE canonical GT (ruling 1)."""
    comp_full = np.load(os.path.join(GS, 'comp_%s.npz' % split), allow_pickle=True)
    gts = comp_full['gts']                                                # the canonical union GT
    out = {}
    ego = np.load(os.path.join(GS, 'ego_%s.npz' % split), allow_pickle=True)
    out[('E', 0)] = np.array([f1_from_boxes(ego['boxes'][i], gts[i]) for i in range(len(gts))])
    for n in NS:
        for branch, key in (('late', 'L'), ('intermediate', 'F')):
            p = os.path.join(GS, 'p4c_N%d/%s_%s.npz' % (n, branch, split))
            if not os.path.exists(p):
                raise SystemExit('P4-C: missing arm cache %s -- run datasets/p4c_sweep.py first' % p)
            z = np.load(p, allow_pickle=True)
            out[(key, n)] = np.array([f1_from_boxes(z['boxes'][i], gts[i]) for i in range(len(gts))])
    return out, len(gts)


def in_scope_frames(split, ds, kcol, bud):
    """Frames that can distinguish semantics A from B: some frozen selector picks F somewhere on the
    deterministic grid AND the frame has >= 2 collaborators (pre-registered, P4-C-b)."""
    grid = pd.read_csv(os.path.join(D.GRID_DIR, 'p2_grid_%s.csv' % split))
    n = len(ds)
    picked = np.zeros(n, bool)
    for tag in sorted(bud):
        for ch in (False, True):
            for s in sorted(grid['snr_db'].unique()):
                a = D.rf_actions_stacked(bud[tag]['model'], bud[tag]['feat'], ds,
                                         np.full((1, n), float(s)),
                                         np.full((1, n), ch, dtype=bool))[0]
                picked |= (a == 2)
    return picked & (kcol >= 2), picked


def paired_bootstrap(delta, n_boot, seed):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    m = delta[idx].mean(1)
    return float(delta.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    tbl = pd.read_csv(D.BLER_CSV)
    _, bud = D.load_manifest()
    rows, arms = [], {}
    for split in D.SPLITS:
        ds = pd.read_csv(os.path.join(D.DATA, D.DATASET[split]))
        n = len(ds)
        kcol = ds['num_cavs'].to_numpy() - 1                              # collaborators, ego excluded
        f1, n_gt = per_frame_f1(split)
        assert n_gt == n, 'cache/frame mismatch %d vs %d' % (n_gt, n)
        comp_full = np.load(os.path.join(GS, 'comp_%s.npz' % split), allow_pickle=True)
        sec = second_only_f1(split, comp_full['gts']) if split == B_SPLIT else None
        scope, _picked = in_scope_frames(split, ds, kcol, bud) if split == B_SPLIT else (None, None)
        rng = np.random.default_rng(D.CSI_SEED)
        snr_2d = rng.uniform(0, 20, size=(D.N_REPLAY, n))
        is_ray_2d = rng.random(size=(D.N_REPLAY, n)) < 0.5
        bF_2d = np.stack([D.bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(D.N_REPLAY)])
        for tag in sorted(bud):
            b = float(tag)
            act = D.rf_actions_stacked(bud[tag]['model'], bud[tag]['feat'], ds, snr_2d, is_ray_2d)
            F1 = {}; B = {}; RHO = {}
            for N in NS:
                eff_E, eff_L, eff_F = f1[('E', 0)], f1[('L', N)], f1[('F', N)]
                # RULING 4: a frame can only exchange messages with the collaborators it HAS.
                # k_eff = min(N, collaborators) -- charging the nominal N would bill for messages
                # that cannot be sent (and would make Culver N=3 differ from N=2, which the
                # pre-registered invariant forbids). k_eff = 0 -> no message, no payload, no link.
                k_eff = np.minimum(N, kcol).astype(float)
                f = np.empty(D.N_REPLAY); pay = np.empty(D.N_REPLAY); rho = np.zeros(3)
                for r in range(D.N_REPLAY):
                    succ = (1.0 - bF_2d[r]) ** k_eff                      # ruling 2: all k_eff links
                    E = np.stack([eff_E, eff_L, eff_F * succ + eff_E * (1 - succ)], axis=1)
                    a = act[r]
                    f[r] = E[np.arange(n), a].mean()
                    pay[r] = (PAYVEC[a] * k_eff).mean()                   # ruling 3+4: k_eff messages
                    rho += np.bincount(a, minlength=3) / (n * D.N_REPLAY)
                F1[N], B[N], RHO[N] = f, pay, rho
            for N in NS:
                row = dict(split=split, budget=b, N=N, semantics='A', label=LABEL,
                           F1=round(float(F1[N].mean()), 5), F1_std=round(float(F1[N].std()), 5),
                           payload=round(float(B[N].mean()), 5),
                           rho_E=round(float(RHO[N][0]), 4), rho_L=round(float(RHO[N][1]), 4),
                           rho_F=round(float(RHO[N][2]), 4),
                           over_budget=bool(float(B[N].mean()) > b),
                           frames_subset_is_full=int((kcol <= N).sum()),
                           frames_zero_collaborator=int((kcol == 0).sum()),
                           arm_distinct=bool((kcol > N).sum() > 0))
                if N != 1:
                    for nm, d in (('dF_vs_N1', F1[N] - F1[1]), ('dB_vs_N1', B[N] - B[1])):
                        m, lo, hi = paired_bootstrap(d, D.N_BOOT, D.BOOT_SEED)
                        row[nm + '_mean'] = round(m, 5)
                        row[nm + '_lcb95'] = round(lo, 5)
                        row[nm + '_ucb95'] = round(hi, 5)
                rows.append(row)
            print('[%s B%s] ' % (split, tag) + '  '.join(
                'N=%d F1=%.4f B=%.4f%s' % (N, F1[N].mean(), B[N].mean(),
                                           ' OVER' if B[N].mean() > b else '') for N in NS), flush=True)

            # ---- semantics B bracket: validate, N=2, in-scope frames only (pre-registered P4-C-b)
            if split == B_SPLIT and sec is not None:
                N = B_N
                eff_E = f1[('E', 0)]
                c_both, c_near, c_sec = f1[('F', 2)], f1[('F', 1)], sec['F']
                fB = np.empty(D.N_REPLAY); payB = np.empty(D.N_REPLAY)
                for r in range(D.N_REPLAY):
                    b_l = bF_2d[r]
                    k_eff = np.minimum(N, kcol).astype(float)
                    effF = c_both * (1 - b_l) ** k_eff + eff_E * (1 - (1 - b_l) ** k_eff)   # = A
                    # in scope: partial fusion replaces the all-or-nothing collapse to ego
                    p2 = (1 - b_l) ** 2
                    partial = p2 * c_both + b_l * (1 - b_l) * (c_near + c_sec) + b_l ** 2 * eff_E
                    effF = np.where(scope, partial, effF)
                    E = np.stack([eff_E, f1[('L', N)], effF], axis=1)
                    a = act[r]
                    fB[r] = E[np.arange(n), a].mean()
                    payB[r] = (PAYVEC[a] * k_eff).mean()          # payload is charged on REQUEST,
                    #                                               so it is identical under A and B
                m, lo, hi = paired_bootstrap(fB - F1[N], D.N_BOOT, D.BOOT_SEED)
                rows.append(dict(split=split, budget=b, N=N, semantics='B', label=LABEL_B,
                                 F1=round(float(fB.mean()), 5), F1_std=round(float(fB.std()), 5),
                                 payload=round(float(payB.mean()), 5),
                                 rho_E=round(float(RHO[N][0]), 4), rho_L=round(float(RHO[N][1]), 4),
                                 rho_F=round(float(RHO[N][2]), 4),
                                 over_budget=bool(float(payB.mean()) > b),
                                 frames_subset_is_full=int((kcol <= N).sum()),
                                 frames_zero_collaborator=int((kcol == 0).sum()),
                                 arm_distinct=True, frames_in_scope=int(scope.sum()),
                                 dF_vs_A_mean=round(m, 5), dF_vs_A_lcb95=round(lo, 5),
                                 dF_vs_A_ucb95=round(hi, 5)))
                print('           B(bracket) N=2 F1=%.4f (A %.4f, dF %+.5f [%+.4f,%+.4f]) on %d in-scope frames'
                      % (fB.mean(), F1[N].mean(), m, lo, hi, scope.sum()), flush=True)
        for N in NS:
            for branch in ('late', 'intermediate'):
                p = os.path.join(GS, 'p4c_N%d/%s_%s.npz' % (N, branch, split))
                z = np.load(p, allow_pickle=True)
                arms['N%d/%s_%s' % (N, branch, split)] = dict(
                    sha256=_sha256(p), n_new_forwards=int(z['n_new']) if 'n_new' in z else None)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)

    json.dump(dict(schema='catosg-p4c-manifest/1', label=LABEL,
                   protocol='CA-TOSG P4-C (docs/experiment_protocol.md, docs/p4c_plan.md)',
                   semantics='A (all-or-nothing) -- primary, all three splits',
                   note='collaborator-scale arms. NOT the deployed product; the deployed selectors '
                        'are in FROZEN_MANIFEST.json and were only READ by this run.',
                   timestamp=datetime.now(timezone.utc).isoformat(),
                   deployed_manifest_sha256=_sha256(FROZEN), caches=arms),
              open(MANIFEST, 'w'), indent=1)

    with open(PROV, 'w') as f:
        f.write('CA-TOSG P4-C -- collaborator scale N in {1,2,3}, semantics A. DESCRIPTIVE + CI ONLY.\n'
                + '=' * 90 + '\n')
        f.write('Pre-registered (Change-log P4-C, docs/p4c_plan.md) BEFORE any forward pass; delivery\n'
                'semantics fixed at greenlight: A all-or-nothing primary on all three splits.\n')
        f.write('RULING 1 -- one canonical GT for every N: restricting the CAV set also shrinks the\n'
                '  post-processor union GT, which would score each arm on a different ruler. The GT is\n'
                '  held at the FULL-set canonical union GT for all arms (the rule true_e2e_global.py\n'
                '  already applies across branches).\n')
        f.write('RULING 2 -- delivery: eff_F(N) = comp_N*(1-b)^N + ego*(1-(1-b)^N); reduces to the\n'
                '  mainline expression at N=1. BLER_L = 0 as in the mainline.\n')
        f.write('RULING 3 -- payload: one message per collaborator actually addressed (sec 5: the budget\n'
                '  bounds the MEAN, so this scales the mean, not a per-frame cap).\n')
        f.write('RULING 4 -- k_eff = min(N, collaborators in the frame). A frame cannot message\n'
                '  collaborators it does not have. FORCED BY THE PRE-REGISTERED INVARIANT: the first run\n'
                '  charged the nominal N, which made Culver N=3 differ from N=2 in payload while F1 was\n'
                '  identical -- exactly the discrepancy the invariant exists to catch. Fixed, re-run.\n')
        f.write('The selector features carry nothing about N, so its per-frame ACTION is N-independent;\n'
                'N changes what an action costs and what it delivers, not what is chosen.\n')
        f.write('Same 200 paired CSI draws as the mainline replay (seed=%d); CI = paired bootstrap vs the\n'
                'SAME policy at N=1, %d resamples, seed=%d.\n' % (D.CSI_SEED, D.N_BOOT, D.BOOT_SEED))
        f.write('Culver N=3 is identical to N=2 BY CONSTRUCTION (no Culver frame has 3 collaborators) and\n'
                'is not an independent data point. Zero-collaborator frames stay in the denominator.\n')
        f.write('Deployed FROZEN_MANIFEST.json sha256 %s -- read only, untouched.\n' % _sha256(FROZEN)[:16])
    print('wrote %s, %s, %s' % (os.path.relpath(OUT_CSV, ROOT), os.path.relpath(MANIFEST, ROOT),
                                os.path.relpath(PROV, ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
