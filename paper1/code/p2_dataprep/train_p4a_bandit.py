#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-A: match-adaptive EXTERNAL RL baseline -- contextual-bandit selector (Change-log P4-A).

"external baseline, not deployed". Does NOT touch the deployed CA-TOSG selectors, FROZEN_MANIFEST.json,
delta, tau*, or the mainline replay; main.tex untouched. Every parameter is PARSED from the machine-
parseable ```json CATOSG-P4A``` block in PROTOCOL.md (single source of truth; nothing hard-coded here).

Problem form (honest): each frame's choice is INDEPENDENT -> a contextual bandit (single-step context
-> action -> immediate reward), NOT sequential RL. Algorithm: DQN-style single-step Q(s,a) + epsilon-
greedy, target = the immediate reward r(s,a) = eff_a - lambda*B_a (the same Lagrangian objective as
PROTOCOL section 6). State = the 23 deployed features (z-scored on the validate grid); actions {E,L,F}.

Matched protocol (PROTOCOL P4-A (b)): same validate grid + scene split, cached per-frame eff (no new
perception inference), 3 B_max, frame-weighted budget, frozen walk (Bbar_frozen <= B_max, temp-then-
atomic-swap), scene-level 9-fold LOSO for lambda selection. Freezes 3 models -> results/p4a/
P4A_MANIFEST.json (+ models in data/p2/, git-excluded).

Run:  /path/to/env/python paper1/code/p2_dataprep/train_p4a_bandit.py
"""
import hashlib
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval_p2_deploy as D

P1 = D.P1
PROTOCOL = os.path.join(P1, 'PROTOCOL.md')
GRID = os.path.join(D.GRID_DIR, 'p2_grid_validate.csv')
MODELDIR = os.path.join(P1, 'data/p2')                 # git-excluded, like the frozen selectors
OUT = os.path.join(P1, 'results/p4a')
ACTIONS = D.ACTIONS                                     # ['E','L','F']
PAY = np.array([D.PAY[a] for a in ACTIONS])            # [0, 0.024, 0.99]
DEV = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def parse_block():
    txt = open(PROTOCOL, encoding='utf-8').read()
    m = re.search(r'```json CATOSG-P4A\n(.*?)\n```', txt, re.S)
    if not m:
        raise SystemExit('P4-A FUSE: CATOSG-P4A block not found in PROTOCOL.md')
    return json.loads(m.group(1)), hashlib.md5(m.group(0).encode()).hexdigest()


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


class QNet(nn.Module):
    def __init__(self, d_in, hidden):
        super().__init__()
        layers, prev = [], d_in
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU()]; prev = h
        layers += [nn.Linear(prev, 3)]
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


def load_grid(feat):
    grid = pd.read_csv(GRID)
    ds = pd.read_csv(os.path.join(D.DATA, D.DATASET['validate']))
    cue_cols = [c for c in feat if c not in ('est_snr_db', 'channel_is_rayleigh')]
    g = grid.merge(ds[['sample_id'] + cue_cols], on='sample_id', how='left')
    X = np.empty((len(g), len(feat)), dtype=np.float32)
    X[:, [feat.index(c) for c in cue_cols]] = g[cue_cols].to_numpy()
    X[:, feat.index('est_snr_db')] = g['snr_db'].to_numpy()
    X[:, feat.index('channel_is_rayleigh')] = (g['channel'] == 'rayleigh').astype(int).to_numpy()
    eff = g[['eff_E', 'eff_L', 'eff_F']].to_numpy(np.float32)
    scene = g['scene'].to_numpy()
    sid = g['sample_id'].to_numpy()
    return X, eff, scene, sid


def train_bandit(Xz, eff, lam, blk, seed):
    """DQN-style single-step contextual bandit. Returns a trained QNet (on DEV)."""
    tr = blk['train']
    torch.manual_seed(seed); np.random.seed(seed)
    rng = np.random.default_rng(seed)
    net = QNet(Xz.shape[1], blk['network']['hidden']).to(DEV)
    opt = torch.optim.Adam(net.parameters(), lr=tr['lr'])
    Xt = torch.from_numpy(Xz).to(DEV)
    R = torch.from_numpy(eff - lam * PAY[None, :].astype(np.float32)).to(DEV)   # (n,3) reward per action
    n = Xz.shape[0]
    for step in range(tr['steps']):
        frac = min(1.0, step / max(1, tr['epsilon_decay_steps']))
        eps = tr['epsilon_start'] + frac * (tr['epsilon_end'] - tr['epsilon_start'])
        idx = rng.integers(0, n, size=tr['batch'])
        xb = Xt[idx]
        with torch.no_grad():
            q = net(xb)
            greedy = q.argmax(1)
            rand = torch.from_numpy(rng.integers(0, 3, size=tr['batch'])).to(DEV)
            explore = torch.from_numpy(rng.random(tr['batch']) < eps).to(DEV)
            a = torch.where(explore, rand, greedy)                      # epsilon-greedy action
        qb = net(xb).gather(1, a[:, None]).squeeze(1)
        target = R[torch.from_numpy(idx).to(DEV), a]                    # immediate reward (no bootstrap)
        loss = ((qb - target) ** 2).mean()
        opt.zero_grad(); loss.backward(); opt.step()
    net.eval()
    return net


def greedy_actions(net, Xz):
    with torch.no_grad():
        return net(torch.from_numpy(Xz).to(DEV)).argmax(1).cpu().numpy()


def fw_metrics(act, eff, scene):
    """Frame-weighted F1/payload over the given rows (grid mean == frame-weighted, R7a). Also scene-mean."""
    e = eff[np.arange(len(act)), act]; b = PAY[act]
    return float(e.mean()), float(b.mean())


def oof_loso(Xz, eff, scene, lam, blk, seed):
    """Scene-level 9-fold LOSO: train on 8 scenes, OOF F1/payload on the held-out scene; frame-weighted."""
    scenes = sorted(np.unique(scene))
    num = den = pay_num = 0.0
    for sc in scenes:
        tr = scene != sc; te = ~tr
        net = train_bandit(Xz[tr], eff[tr], lam, blk, seed)
        a = greedy_actions(net, Xz[te])
        f1_k, b_k = fw_metrics(a, eff[te], scene[te])
        n_k = int(te.sum())
        num += n_k * f1_k; pay_num += n_k * b_k; den += n_k
    return num / den, pay_num / den                                     # frame-weighted OOF F1, payload


def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(MODELDIR, exist_ok=True)
    blk, blk_md5 = parse_block()
    man_frozen = json.load(open(D.MANIFEST))
    feat = man_frozen['feature_names']
    X, eff, scene, sid = load_grid(feat)
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1.0
    Xz = ((X - mu) / sd).astype(np.float32)
    seed = blk['seed']; lam_grid = blk['lambda_grid']

    # --- LOSO OOF per lambda (selection substrate) ---
    print('LOSO OOF per lambda...', flush=True)
    oof = []
    for li, lam in enumerate(lam_grid):
        f1, pay = oof_loso(Xz, eff, scene, lam, blk, seed)
        oof.append(dict(lambda_index=li, **{'lambda': lam}, oof_f1=round(f1, 5), oof_payload=round(pay, 5)))
        print(f'  lambda={lam:<5} OOF F1={f1:.5f} payload={pay:.5f}', flush=True)
    pd.DataFrame(oof).to_csv(os.path.join(OUT, 'p4a_loso_oof.csv'), index=False)

    # --- frozen walk per budget: order lambda by OOF F1 desc; retrain full; first Bbar_frozen<=B_max ---
    budgets = blk['budgets']
    walk_rows, manifest_budgets = [], {}
    for bmax in budgets:
        order = sorted(oof, key=lambda r: (-r['oof_f1'], r['oof_payload'], r['lambda_index']))
        chosen = None
        for depth, r in enumerate(order):
            lam = r['lambda']
            net = train_bandit(Xz, eff, lam, blk, seed)                 # retrain on FULL validate grid
            a = greedy_actions(net, Xz)
            f1_frozen, pay_frozen = fw_metrics(a, eff, scene)
            passed = pay_frozen <= bmax
            walk_rows.append(dict(budget=bmax, walk_depth=depth, lambda_index=r['lambda_index'],
                                  **{'lambda': lam}, frozen_f1=round(f1_frozen, 5),
                                  frozen_payload=round(pay_frozen, 5), oof_f1=r['oof_f1'], passed=bool(passed)))
            if passed:
                # temp-then-atomic-swap freeze
                tag = f'B{int(round(bmax*100)):03d}'
                tmp = os.path.join(MODELDIR, f'.p4a_bandit_{tag}.pt.tmp')
                final = os.path.join(MODELDIR, f'p4a_bandit_{tag}.pt')
                torch.save(dict(state_dict={k: v.cpu() for k, v in net.state_dict().items()},
                                hidden=blk['network']['hidden'], mu=mu, sd=sd, feat=feat,
                                lam=lam, seed=seed), tmp)
                os.replace(tmp, final)
                chosen = dict(tag=tag, lam=lam, lambda_index=r['lambda_index'], walk_depth=depth,
                              frozen_f1=round(f1_frozen, 5), frozen_payload=round(pay_frozen, 5),
                              oof_f1=r['oof_f1'], model=os.path.relpath(final, P1),
                              model_sha256=_sha256(final))
                print(f'  B{bmax}: lambda*={lam} depth={depth} frozen F1={f1_frozen:.5f} pay={pay_frozen:.5f}', flush=True)
                break
        if chosen is None:
            raise SystemExit(f'P4-A FUSE: walk exhausted for B_max={bmax} (no lambda meets the budget) '
                             '-- fix = new Change-log entry expanding lambda_grid, then full redo.')
        manifest_budgets[f'{bmax:.2f}'] = chosen
    pd.DataFrame(walk_rows).to_csv(os.path.join(OUT, 'p4a_walk.csv'), index=False)

    manifest = dict(
        schema='catosg-p4a-manifest/1', label='external baseline, not deployed',
        p4a_block_md5=blk_md5, algorithm=blk['algorithm'], problem_form=blk['problem_form'],
        seed=seed, network=blk['network'], train=blk['train'], reward=blk['reward'],
        feature_names=feat, budgets=manifest_budgets,
        inputs=dict(grid=dict(file=os.path.relpath(GRID, P1), md5=hashlib.md5(open(GRID, 'rb').read()).hexdigest()),
                    frozen_manifest_sha256=_sha256(D.MANIFEST)),
        env=dict(python=sys.version.split()[0], torch=torch.__version__, numpy=np.__version__, device=str(DEV)),
    )
    json.dump(manifest, open(os.path.join(OUT, 'P4A_MANIFEST.json'), 'w'), indent=1)
    print('wrote results/p4a/{P4A_MANIFEST.json, p4a_loso_oof.csv, p4a_walk.csv} + models in data/p2/ (git-excluded)')


if __name__ == '__main__':
    main()
