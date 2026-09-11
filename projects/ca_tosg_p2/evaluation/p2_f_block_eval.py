#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2 round 1 (f_block_selection.md, LOCKED) — budgeted F: K_F blocks per frame under three rankings,
evaluated with P1's WP5 procedure. Development split only.

What is reused from P1, by import, never re-implemented:
  * the checkpoint, dataset build, forward-invariant check, seeded point shuffle (v2_wp5_final imports)
  * Transport._apply / Transport.patched -- the int8 quantisation and the hook points on the wire
  * the packet-regime rule (CW_PER_PACKET), the straddle rule (element lost if either codeword fails)
  * per-frame F1 (f1_from_boxes), the payload chain (v2_payload_chain)
What is new: which elements are on the wire (K_F blocks), the message's element->codeword map, the
three rankings, and the seed lists of the locked protocol (B-3, D-1).

Per frame:
  1. one UNMASKED full-F forward (int8, all 55 blocks) -- records the collaborator's float
     bottlenecks for the norm ranking and gives an identity check against P1's f1_clean;
  2. one single-vehicle forward of the collaborator -- its own confidence map (B-1); timed on GPU,
     and on CPU for the first --cpu-frames frames (B-4);
  3. for each variant (confidence, norm, random x R): clean, C-1 control (confidence only),
     8 rates x 4 replicates x 2 regimes, p = 1 -- the codeword draw is shared across variants (D-1).

--probe runs the same per-frame workload on a spread of frames with fewer random repeats and writes
timings; the per-frame F1 file it also writes is a by-product for schema checking and is not a result.

    python projects/ca_tosg_p2/evaluation/p2_f_block_eval.py --probe
    python projects/ca_tosg_p2/evaluation/p2_f_block_eval.py --split validate      # D-1, on approval
"""
from __future__ import annotations
import argparse, copy, json, os, sys, time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
P1_EVAL = os.path.join(ROOT, 'projects', 'ca_tosg', 'evaluation')
sys.path.insert(0, P1_EVAL)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(P2, 'protocol'))

import v2_wp5_final as wp5                                                        # noqa: E402  (sets CATOSG_* env)
from v2_wp5_final import (CKPT, DATA_ROOT, SPLIT_DIR, RATES, R_REPS, REGIMES, CW_PER_PACKET, SCALES_JSON,  # noqa: E402
                          Transport, assert_invariants, f1_from_boxes)
from v2_wp5_f_products import BRANCH_ELEMS                                        # noqa: E402
from v2_wp2_per_agent import one_cav                                              # noqa: E402
from round1_lock import element_to_codeword_general, n_cw_for_bits                # noqa: E402
import v2_payload_chain as pcm                                                    # noqa: E402
from torch.utils.data import DataLoader, Subset                                   # noqa: E402
from opencood.data_utils.datasets import build_dataset                            # noqa: E402
from opencood.hypes_yaml import yaml_utils                                        # noqa: E402
from opencood.tools import inference_utils, train_utils                           # noqa: E402
import pandas as pd                                                               # noqa: E402

LOCK = os.path.join(P2, 'protocol', 'round1_lock.json')
RESULTS = os.path.join(P2, 'results')
BASE_SEED = wp5.BASE_SEED                       # 20260809, P1's
R_RAND_LOCKED = 20                              # B-3
VARIANTS_FIXED = ('conf', 'norm')


def draw_seed(frame, rate_idx, rep):
    """D-1: shared by every variant -> paired channel realisations."""
    return [BASE_SEED, 3, int(frame), int(rate_idx), int(rep)]


def random_blocks(frame, rep, n_blocks, k):
    """B-3."""
    return np.sort(np.random.default_rng([BASE_SEED, 2, int(frame), int(rep)]).choice(n_blocks, k, replace=False))


class BlockTransport(Transport):
    """P1's Transport with the wire restricted to K_F blocks (C-3: unsent and failed both zero-filled)."""

    def __init__(self, backbone, scales, lock):
        a1, a3 = lock['A1_block'], lock['A3_budget']
        self.H, self.W = a1['transmitted_grid']
        self.C = list(a1['channels_per_branch'])
        self.br, self.bc = a1['block_cells']
        self.n_blocks, self.K, self.e_block = a1['n_blocks'], a3['K_F'], a1['elements_per_block']
        self.prefix_bits = lock['A2_bitstream']['overhead_bits_per_frame']['mask_bitmap']
        n_msg = self.K * self.e_block
        lo, hi = element_to_codeword_general(n_msg, self.prefix_bits)
        n_cw = int(max(lo.max(), hi.max())) + 1
        if n_cw != a3['n_cw_at_K_F'] or n_cw != n_cw_for_bits(self.prefix_bits + n_msg * pcm.W_BITS):
            raise SystemExit('BLOCK TRANSPORT: codeword count disagrees with the lock')
        super().__init__(backbone, scales, lo, hi)          # cw_lo/cw_hi now index MESSAGE elements
        if tuple(c * self.H * self.W for c in self.C) != tuple(BRANCH_ELEMS):
            raise SystemExit('BLOCK TRANSPORT: branch element counts disagree with P1')
        nbr, nbc = self.H // self.br, self.W // self.bc
        self.flat = []                                        # per branch, per block: flat positions
        for b, c in enumerate(self.C):
            per_block = []
            for blk in range(self.n_blocks):
                i, j = divmod(blk, nbc)
                cc, hh, ww = np.meshgrid(np.arange(c), np.arange(i * self.br, (i + 1) * self.br),
                                         np.arange(j * self.bc, (j + 1) * self.bc), indexing='ij')
                per_block.append((cc * self.H * self.W + hh * self.W + ww).reshape(-1))
            self.flat.append(per_block)
        self.off = np.cumsum([0] + [c * self.br * self.bc for c in self.C])[:-1]
        self.recording, self.recorded = False, [None, None, None]
        self.sel = None

    def to_device(self, dev):
        self.dev = dev
        self.t_lo = torch.from_numpy(self.cw_lo).to(dev)
        self.t_hi = torch.from_numpy(self.cw_hi).to(dev)
        return self

    def set_blocks(self, sel):
        sel = [int(x) for x in sel]
        if len(sel) != self.K or sorted(sel) != sel or len(set(sel)) != self.K:
            raise SystemExit('BLOCK TRANSPORT: selection must be K_F distinct ascending block ids')
        self.sel = sel
        self.F_pos, self.M_pos, self.keep_base = [], [], []
        for b, c in enumerate(self.C):
            F = np.concatenate([self.flat[b][blk] for blk in sel])
            M = np.concatenate([j * self.e_block + self.off[b] + np.arange(c * self.br * self.bc) for j in range(self.K)])
            self.F_pos.append(torch.from_numpy(F).to(self.dev))
            self.M_pos.append(torch.from_numpy(M).to(self.dev))
            kb = torch.zeros(c * self.H * self.W, device=self.dev)
            kb[self.F_pos[b]] = 1.0
            self.keep_base.append(kb)

    def set_full(self):
        """all 55 blocks on the wire, nothing lost -- P1's clean forward"""
        self.n_lost_cw, self.lost_frac = 0, 0.0
        self.masks = [None, None, None]

    def set_clean(self, apply_empty_mask=False):
        self.n_lost_cw, self.lost_frac = 0, 0.0
        self.masks = [kb.clone() for kb in self.keep_base]

    def set_dead(self, dead, regime):
        if regime == 'packet':
            dead = dead.copy()
            hdr = np.arange(0, self.n_cw, CW_PER_PACKET)
            for h in hdr[dead[hdr]]:
                dead[h:min(h + CW_PER_PACKET, self.n_cw)] = True
        self.n_lost_cw = int(dead.sum())
        d = torch.from_numpy(dead).to(self.dev)
        lost_msg = d[self.t_lo] | d[self.t_hi]
        self.lost_frac = float(lost_msg.float().mean().item())
        masks = []
        for b in range(3):
            k = self.keep_base[b].clone()
            k[self.F_pos[b]] = (~lost_msg[self.M_pos[b]]).float()
            masks.append(k)
        self.masks = masks
        return dead

    def _apply(self, x, b):
        if self.recording and x.shape[0] >= 2:
            self.recorded[b] = x[1:2].detach().clone()   # float bottleneck of the nearest collaborator
        return super()._apply(x, b)


def rank_conf(psm, tr):
    """B-1: sigmoid, max over anchors, block score = max over the block's head cells, ties by index."""
    m = torch.sigmoid(psm[0]).amax(dim=0)                        # (Hh, Wh)
    Hh, Wh = m.shape
    nbr, nbc = tr.H // tr.br, tr.W // tr.bc
    rh, rw = Hh // nbr, Wh // nbc
    if rh * nbr != Hh or rw * nbc != Wh:
        raise SystemExit(f'RANK CONF: head grid {Hh}x{Wh} does not tile into {nbr}x{nbc} blocks')
    s = m.view(nbr, rh, nbc, rw).amax(dim=(1, 3)).reshape(-1).double().cpu().numpy()
    return s, np.sort(np.lexsort((np.arange(len(s)), -s))[:tr.K])


def rank_norm(rec, tr):
    """B-2: sum over branches of the per-block L2 norm on the float bottleneck, ties by index."""
    nbr, nbc = tr.H // tr.br, tr.W // tr.bc
    tot = np.zeros(nbr * nbc)
    for b in range(3):
        x = rec[b][0]                                            # (C, H, W)
        sq = (x.double() ** 2).view(x.shape[0], nbr, tr.br, nbc, tr.bc).sum(dim=(0, 2, 4))
        tot += sq.sqrt().reshape(-1).cpu().numpy()
    return tot, np.sort(np.lexsort((np.arange(len(tot)), -tot))[:tr.K])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate', choices=['validate'])
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--rand-reps', type=int, default=R_RAND_LOCKED)
    ap.add_argument('--cpu-frames', type=int, default=3)
    ap.add_argument('--probe', action='store_true', help='60 frames spread over the split, 2 random repeats; timings')
    ap.add_argument('--tag', default='')
    a = ap.parse_args()
    if a.probe:
        a.every, a.limit, a.rand_reps = 33, 60, 2
    out_dir = os.path.join(RESULTS, 'probe' if a.probe else 'round1')
    os.makedirs(out_dir, exist_ok=True)
    lock = json.load(open(LOCK))

    class O:
        model_dir = CKPT
    hypes = yaml_utils.load_yaml(None, O)
    hypes['root_dir'] = hypes['validate_dir'] = os.path.join(DATA_ROOT, SPLIT_DIR[a.split])
    assert_invariants(CKPT, hypes)
    scales = json.load(open(SCALES_JSON))['scales']
    ds = build_dataset(hypes, visualize=False, train=False)
    ds.catosg_split = a.split
    idx = list(range(0, len(ds), a.every))[: (a.limit or None)]
    loader = DataLoader(Subset(ds, idx), batch_size=1, num_workers=4, collate_fn=ds.collate_batch_test,
                        shuffle=False, pin_memory=False)
    model = train_utils.create_model(hypes)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if dev.type == 'cuda':
        model.cuda()
    _, model = train_utils.load_saved_model(CKPT, model)
    model.eval()
    model_cpu = copy.deepcopy(model).cpu().eval() if a.cpu_frames > 0 else None

    tr = BlockTransport(model.backbone, scales, lock).to_device(dev)
    p1 = pd.read_csv(os.path.join(ROOT, 'results', 'v2', f'wp5_final_{a.split}.csv'), usecols=['frame', 'f1_clean'])
    p1_clean = dict(zip(p1.frame.astype(int), p1.f1_clean))
    variants = list(VARIANTS_FIXED) + [f'rand{r}' for r in range(a.rand_reps)]
    n_cond = 1 + len(RATES) * R_REPS * len(REGIMES) + 1
    print(f'{a.split}: {len(idx)} frames | K_F={tr.K} of {tr.n_blocks} blocks | N_cw={tr.n_cw} | '
          f'{len(variants)} variants x {n_cond} conditions (+1 identity control)', flush=True)

    def fwd(pack):
        pb, ps, g = inference_utils.inference_intermediate_fusion(pack, model, ds)
        f = lambda t, shp: t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
        return f(pb, (0, 8, 3)), f(g, (0, 8, 3))

    def sync():
        if dev.type == 'cuda':
            torch.cuda.synchronize()

    rows, timing, ident = [], [], []
    t_all = time.time(); t_prev = time.time()
    for i, batch in enumerate(loader):
        t_load = time.time() - t_prev
        b = train_utils.to_device(batch, dev)
        cav = b['ego']; pack = {'ego': cav}
        frame = idx[i]
        rec = {'frame': frame, 'n_cav': int(cav['record_len'].sum().item())}
        if rec['n_cav'] < 2:
            raise SystemExit(f'frame {frame}: no collaborator; the development split has one on every frame')
        with torch.no_grad():
            # 1. full-F unmasked forward, recording the collaborator's float bottlenecks
            tr.set_full(); tr.recording = True
            sync(); t0 = time.time()
            with tr.patched():
                Bf, G = fwd(pack)
            sync(); t_rec = time.time() - t0
            tr.recording = False
            rec['f1_full_clean'] = f1_from_boxes(Bf, G)
            d_ident = abs(rec['f1_full_clean'] - p1_clean[frame]) if frame in p1_clean else np.nan
            ident.append(d_ident)
            for k in range(3):
                if tuple(tr.recorded[k].shape[1:]) != (tr.C[k], tr.H, tr.W):
                    raise SystemExit(f'branch {k}: bottleneck {tuple(tr.recorded[k].shape[1:])} != lock')
            # 2. collaborator's own confidence map (single-vehicle forward), timed
            col = one_cav(cav, 1)
            sync(); t0 = time.time()
            psm = model(col)['psm']
            sync(); t_col = time.time() - t0
            if tuple(psm.shape[2:]) != tuple(lock['A1_block']['head_grid']):
                raise SystemExit(f'psm grid {tuple(psm.shape[2:])} != lock head grid')
            t_cpu = np.nan
            if model_cpu is not None and i < a.cpu_frames:
                bc = train_utils.to_device(batch, torch.device('cpu'))
                colc = one_cav(bc['ego'], 1)
                t0 = time.time(); _ = model_cpu(colc)['psm']; t_cpu = time.time() - t0
            # 3. rankings
            sel = {}
            s_conf, sel['conf'] = rank_conf(psm, tr)
            s_norm, sel['norm'] = rank_norm(tr.recorded, tr)
            for r in range(a.rand_reps):
                sel[f'rand{r}'] = random_blocks(frame, r, tr.n_blocks, tr.K)
            rec['blocks_conf'] = ' '.join(map(str, sel['conf'])); rec['blocks_norm'] = ' '.join(map(str, sel['norm']))
            rec['overlap_conf_norm'] = int(len(set(sel['conf']) & set(sel['norm'])))
            # 4. the shared codeword draws
            draws = {(ri, rep): np.random.default_rng(draw_seed(frame, ri, rep)).random(tr.n_cw) < p
                     for ri, p in enumerate(RATES) for rep in range(R_REPS)}
            t_fwds = []
            for v in variants:
                tr.set_blocks(sel[v])
                tr.set_clean()
                sync(); t0 = time.time()
                with tr.patched():
                    B, _ = fwd(pack)
                sync(); t_fwds.append(time.time() - t0)
                rec[f'f1_{v}_clean'] = f1_from_boxes(B, G)
                if v == 'conf':                                   # C-1 identity control, once per frame
                    tr.set_dead(np.zeros(tr.n_cw, bool), 'ideal')
                    with tr.patched():
                        Bc, _ = fwd(pack)
                    rec['identity_control_ok'] = int(Bc.shape == B.shape and (B.size == 0 or np.abs(Bc - B).max() == 0))
                for ri, p in enumerate(RATES):
                    for rep in range(R_REPS):
                        for reg in REGIMES:
                            tr.set_dead(draws[(ri, rep)], reg)
                            sync(); t0 = time.time()
                            with tr.patched():
                                B, _ = fwd(pack)
                            sync(); t_fwds.append(time.time() - t0)
                            rec[f'f1_{v}_{reg}_p{p}_r{rep}'] = f1_from_boxes(B, G)
                            if v == 'conf':
                                rec[f'cw_{reg}_p{p}_r{rep}'] = tr.n_lost_cw
                tr.set_dead(np.ones(tr.n_cw, bool), 'ideal')
                with tr.patched():
                    B1, _ = fwd(pack)
                rec[f'f1_{v}_p1.0'] = f1_from_boxes(B1, G)
        rows.append(rec)
        timing.append({'frame': frame, 't_load_s': t_load, 't_record_fwd_s': t_rec, 't_collab_fwd_gpu_s': t_col,
                       't_collab_fwd_cpu_s': t_cpu, 'n_masked_fwd': len(t_fwds), 't_masked_fwd_mean_s': float(np.mean(t_fwds)),
                       't_masked_fwd_median_s': float(np.median(t_fwds)), 't_frame_total_s': time.time() - t_prev})
        t_prev = time.time()
        if i % 5 == 0:
            el = time.time() - t_all
            print(f'  {i}/{len(idx)} frame={frame} {el / (i + 1):.1f}s/frame  fwd {np.mean(t_fwds) * 1e3:.0f}ms  '
                  f'|f1_full - P1 f1_clean| = {d_ident:.2e}  eta {(len(idx) - i - 1) * el / (i + 1) / 60:.0f}min', flush=True)
    dt = time.time() - t_all

    tag = f'_{a.tag}' if a.tag else ''
    pd.DataFrame(rows).to_csv(os.path.join(out_dir, f'f_block_rows_{a.split}{tag}.csv'), index=False)
    T = pd.DataFrame(timing)
    summ = {'schema': 'catosg-p2-round1-eval/1', 'mode': 'probe' if a.probe else 'full', 'split': a.split,
            'frames': len(rows), 'every': a.every, 'frame_ids': idx, 'rand_reps_run': a.rand_reps,
            'rand_reps_locked': R_RAND_LOCKED, 'variants_run': variants, 'conditions_per_variant': n_cond,
            'K_F': tr.K, 'n_blocks': tr.n_blocks, 'n_cw': tr.n_cw, 'lock_sha256_inputs': lock['inputs'],
            'seconds': round(dt, 1), 'sec_per_frame': round(dt / max(len(rows), 1), 3),
            'identity_vs_P1_f1_clean': {'max_abs_diff': float(np.nanmax(ident)), 'frames_compared': int(np.sum(~np.isnan(ident)))},
            'identity_control_all_ok': bool(all(r.get('identity_control_ok', 0) for r in rows)),
            'timing': {c: {'mean': float(T[c].mean()), 'median': float(T[c].median()), 'n': int(T[c].notna().sum())}
                       for c in T.columns if c != 'frame'},
            'device': {'gpu': torch.cuda.get_device_name(0) if dev.type == 'cuda' else 'none',
                       'cpu_threads_torch': torch.get_num_threads(), 'cpu_frames_timed': a.cpu_frames},
            'command': ' '.join(sys.argv)}
    json.dump(summ, open(os.path.join(out_dir, f'f_block_eval_{a.split}{tag}.json'), 'w'), indent=1)
    print(json.dumps({k: summ[k] for k in ('frames', 'sec_per_frame', 'identity_vs_P1_f1_clean', 'identity_control_all_ok', 'timing')}, indent=1))
    print('wrote', os.path.relpath(out_dir, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
