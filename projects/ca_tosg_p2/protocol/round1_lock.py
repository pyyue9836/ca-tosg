#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R4 A — the arithmetic the round-1 lock rests on, computed by one tool and checked against the
locked text. Payload columns, frozen E-branch boxes and channel constants only; no F output is read
and no network is run.

  A-1  block definition on the transmitted grid (derived from the checkpoint probe, not declared)
  A-2  bitstream layout and itemised per-frame overhead; N_sym,F(K) through P1's chain
  A-3  K_F = max{K : N_sym,F(K) <= B_available} for 802.11bd 20 MHz, D_comm = 100 ms
  A-4  the L bound: N_sym,L at the observed validate maximum against B_available; p99 for the
       expected truncation share
  C-2  AttFusion trainable-parameter count, from the class and from the checkpoint file
  D-2  the pre-registered channel cells, with their p_cw from the P1 grid product, and the hard-frame
       subset size (C-5 rule) with a stricter ladder pre-declared as exploratory

`--check` re-derives everything, compares with round1_lock.json/.md byte for byte, and also asserts
that the locked protocol text states the same K_F, so the number in the prose cannot drift from the
number the tool derives.

    python projects/ca_tosg_p2/protocol/round1_lock.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, sys, warnings

import numpy as np
import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
REPO = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, REPO)
import v2_payload_chain as pcm                                                    # noqa: E402

PROBE = os.path.join(ROOT, 'results/manifests/P4B_PROBE_pointpillar_compression.json')
CHAIN = os.path.join(ROOT, 'results/v2/payload_chain.json')
LINKS = os.path.join(HERE, 'link_scenarios.json')
WP34 = os.path.join(ROOT, 'results/v2/wp34_e_l_validate.csv')
GRID = os.path.join(ROOT, 'results/v2/v2_grid_validate_ideal.csv')
WP2 = os.path.join(ROOT, 'results/v2/wp2_per_agent_validate.npz')
CKPT_FILE = 'latest.pth'
PROTOCOL = os.path.join(HERE, 'f_block_selection.md')
OUT_JSON = os.path.join(HERE, 'round1_lock.json')
OUT_MD = os.path.join(HERE, 'round1_lock.md')

BLOCK_ROWS, BLOCK_COLS = 5, 8                     # A-1
LINK_ROW = ('IEEE 802.11bd', '20 MHz', 'zero-overhead upper bound', 100.0)   # A-3
MASK_BITS_PER_BLOCK = 1                            # A-2: one bit per block, bitmap
QUANT_PARAM_BITS = 0                               # A-2: per-branch int8 scales pre-shared (P1 §3.3)
INDEX_LIST_BITS = 0                                # A-2: raster order + bitmap; no index list
PRIMARY_CELLS = [('awgn', s) for s in (8, 10, 12, 14, 16, 18, 20)]              # D-2(ii)
EXPLORATORY_MISS_LADDER = (3, 5, 8)                # D-2(ii) / D-3
IOU = 0.5


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def msym_for_bits(bits):
    if bits <= 0:
        return 0.0
    _, _, sizes = pcm.packetise(int(bits))
    return pcm.msym(pcm.codewords(sizes))


def n_cw_for_bits(bits):
    _, _, sizes = pcm.packetise(int(bits))
    return pcm.codewords(sizes)


def element_to_codeword_general(n_elem, prefix_bits):
    """P1's mapping (v2_wp5_f_products.element_to_codeword) for a message whose element bits start
    after `prefix_bits` of payload. Same packetisation, same header placement, same straddle rule."""
    e = np.arange(n_elem, dtype=np.int64)
    cw_per_packet = (pcm.P_BITS + pcm.H_BITS + pcm.K - 1) // pcm.K

    def cw_of(bit):
        j = bit // pcm.P_BITS
        local = pcm.H_BITS + (bit - j * pcm.P_BITS)
        return j * cw_per_packet + local // pcm.K
    lo = cw_of(prefix_bits + e * pcm.W_BITS)
    hi = cw_of(prefix_bits + e * pcm.W_BITS + (pcm.W_BITS - 1))
    return lo, hi


def hard_frames():
    """C-5: frames where the FROZEN E branch misses >= 1 ground-truth object at IoU 0.5 (P1 WP2
    product). Returns the per-frame missed count and the scene vector."""
    import torch
    from opencood.utils import eval_utils
    z = np.load(WP2, allow_pickle=True)
    missed = np.empty(len(z['frames']), int)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for i in range(len(z['frames'])):
            pred = np.asarray(z['ego_boxes'][i], np.float32); gt = np.asarray(z['gts'][i], np.float32)
            pt = torch.from_numpy(pred) if pred.size else torch.zeros((0, 8, 3))
            gt_t = torch.from_numpy(gt) if gt.size else torch.zeros((0, 8, 3))
            rs = {IOU: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
            eval_utils.caluclate_tp_fp(pt, torch.ones(len(pt)), gt_t, rs, IOU)
            missed[i] = rs[IOU]['gt'] - int(sum(rs[IOU]['tp']))
    sc = pd.read_csv(GRID, usecols=['sample_id', 'scene']).drop_duplicates().sort_values('sample_id')
    if not np.array_equal(sc.sample_id.to_numpy(), z['frames']):
        raise SystemExit('ROUND1 LOCK: WP2 frames and grid frames differ -- refusing')
    return missed, sc.scene.to_numpy()


def build():
    probe = json.load(open(PROBE))
    tx = [b['transmitted_shape_per_cav'] for b in probe['branches']]
    if len({(s[1], s[2]) for s in tx}) != 1:
        raise SystemExit('ROUND1 LOCK: branches do not share one transmitted grid')
    H, W, C = tx[0][1], tx[0][2], [s[0] for s in tx]
    if H % BLOCK_ROWS or W % BLOCK_COLS:
        raise SystemExit('ROUND1 LOCK: block does not tile the grid')
    n_blocks = (H // BLOCK_ROWS) * (W // BLOCK_COLS)
    per_branch = [c * BLOCK_ROWS * BLOCK_COLS for c in C]
    e_block = sum(per_branch)
    cfg = yaml.load(open(os.path.join(probe['ckpt_dir'], 'config.yaml')), Loader=yaml.UnsafeLoader)  # trusted local OpenCOOD checkpoint config; numpy-tagged values
    ups = cfg['model']['args']['base_bev_backbone']['upsample_strides']
    pre = [b['pre_compression_shape_per_cav'] for b in probe['branches']]
    head = [pre[0][1] * ups[0], pre[0][2] * ups[0]]
    cells_per_block_head = [BLOCK_ROWS * head[0] // H, BLOCK_COLS * head[1] // W]
    rng = cfg['model']['args']['lidar_range'] if 'lidar_range' in cfg['model']['args'] else probe['config']['cav_lidar_range']
    cell_m = [(rng[4] - rng[1]) / H, (rng[3] - rng[0]) / W]

    # A-2 / A-3
    links = json.load(open(LINKS))['rows']
    row = [r for r in links if (r['technology'], r['configuration'], r['capacity_variant'], r['D_comm_ms']) == LINK_ROW]
    if len(row) != 1:
        raise SystemExit('ROUND1 LOCK: link row not found exactly once')
    B_avail = row[0]['capacity_msym']
    mask_bits = n_blocks * MASK_BITS_PER_BLOCK
    overhead_bits = mask_bits + QUANT_PARAM_BITS + INDEX_LIST_BITS

    def bits(K):
        return overhead_bits + K * e_block * pcm.W_BITS
    K_F = 0
    while K_F < n_blocks and msym_for_bits(bits(K_F + 1)) <= B_avail:
        K_F += 1
    n_cw_KF = n_cw_for_bits(bits(K_F))
    lo, hi = element_to_codeword_general(K_F * e_block, overhead_bits)
    if int(max(lo.max(), hi.max())) + 1 != n_cw_KF:
        raise SystemExit('ROUND1 LOCK: element->codeword mapping disagrees with the codeword count')
    straddle = int((lo != hi).sum())
    B_F_full = json.load(open(CHAIN))['F']['msym']
    if abs(msym_for_bits(sum(c * H * W for c in C) * pcm.W_BITS) - B_F_full) > 1e-12:
        raise SystemExit('ROUND1 LOCK: the full tensor does not reproduce B_F')
    ladder = [{'K': K, 'bits': bits(K), 'n_cw': n_cw_for_bits(bits(K)), 'N_sym_msym': msym_for_bits(bits(K)),
               'fits': msym_for_bits(bits(K)) <= B_avail} for K in range(max(1, K_F - 2), min(n_blocks, K_F + 2) + 1)]

    # A-4
    w = pd.read_csv(WP34, usecols=['n_box_collab', 'B_L_msym'])
    nb = w.n_box_collab.to_numpy()
    n_max = int(nb.max())
    L_max = pcm.l_chain(n_max)['msym']
    K_L = 0
    while pcm.l_chain(K_L + 1)['msym'] <= B_avail:
        K_L += 1
    p99 = float(np.percentile(nb, 99))
    trunc_share = float((nb > K_L).mean())

    # C-2
    import torch
    from opencood.models.fuse_modules.self_attn import AttFusion
    att_params = {d: int(sum(p.numel() for p in AttFusion(d).parameters())) for d in C}
    sd = torch.load(os.path.join(probe['ckpt_dir'], CKPT_FILE), map_location='cpu')
    sd = sd.get('model_state_dict', sd)
    keys = list(sd.keys())
    fuse_keys = [k for k in keys if 'fuse' in k]

    # D-2(ii): cells and their p_cw from the P1 grid product; hard-frame subset from the frozen E branch
    g = pd.read_csv(GRID, usecols=['sample_id', 'scene', 'snr_db', 'channel', 'p_cw']).drop_duplicates(['snr_db', 'channel'])
    cells = []
    for ch, s in PRIMARY_CELLS:
        r = g[(g.channel == ch) & (g.snr_db == s)]
        if len(r) != 1:
            raise SystemExit(f'ROUND1 LOCK: cell {ch} {s} dB not found exactly once in the grid')
        cells.append({'channel': ch, 'snr_db': int(s), 'p_cw': float(r.p_cw.iloc[0])})
    missed, sc = hard_frames()
    uniq = np.unique(sc)
    def subset(k):
        m = missed >= k
        return {'min_missed': int(k), 'frames': int(m.sum()), 'share': float(m.mean()),
                'scenes_with_frames': int(len(np.unique(sc[m]))),
                'min_frames_in_a_scene': int(min((m & (sc == s)).sum() for s in uniq))}
    hard = subset(1)

    return {
        'schema': 'catosg-p2-round1-lock/1',
        'what': 'payload arithmetic, frozen E-branch boxes and channel constants only; no F output read, no network run',
        'A1_block': {'transmitted_grid': [H, W], 'channels_per_branch': C, 'block_cells': [BLOCK_ROWS, BLOCK_COLS],
                     'block_bev_m': [round(BLOCK_ROWS * cell_m[0], 6), round(BLOCK_COLS * cell_m[1], 6)],
                     'n_blocks': n_blocks, 'elements_per_block_per_branch': per_branch, 'elements_per_block': e_block,
                     'head_grid': head, 'head_cells_per_block': cells_per_block_head,
                     'block_index': 'raster: index = row_block * (W / cols) + col_block, row-major, 0-based'},
        'A2_bitstream': {
            'layout': '[mask bitmap][block 0..K-1 in ascending block index; within a block branch 0, 1, 2; '
                      'within a branch channel-major C x rows x cols]; then P1 packetisation (8,000-bit '
                      'payload + 320-bit header per packet), LDPC K=500 n=1000, 16-QAM',
            'overhead_bits_per_frame': {'mask_bitmap': mask_bits, 'index_list': INDEX_LIST_BITS,
                                        'quantisation_parameters': QUANT_PARAM_BITS,
                                        'packet_headers': '320 per packet, charged by the P1 chain',
                                        'ldpc_padding': 'charged by the P1 chain', 'request': 'not charged (identical for every action)'},
            'mask_loss_semantics': 'not modelled -- the receiver is assumed to obtain the 55-bit mask correctly and results '
                                   'are conditional on that assumption; metadata corruption is not evaluated (Amendment 1, '
                                   'B-3); the mask bits are still charged as payload',
            'bits_per_block': e_block * pcm.W_BITS},
        'A3_budget': {'link_row': dict(zip(('technology', 'configuration', 'capacity_variant', 'D_comm_ms'), LINK_ROW)),
                      'B_available_msym': B_avail,
                      'why_upper_bound': 'whole channel to one link, every data resource element, continuously; '
                                         'preamble, midambles, MAC, contention, queueing and the request are excluded, '
                                         'so a real link carries less and K_F is an upper bound on blocks sent',
                      'K_F': K_F, 'share_of_blocks': K_F / n_blocks, 'bits_at_K_F': bits(K_F),
                      'n_cw_at_K_F': n_cw_KF, 'N_sym_at_K_F_msym': msym_for_bits(bits(K_F)),
                      'straddling_elements_at_K_F': straddle, 'ladder': ladder,
                      'reference_value_from_draft': 23, 'reference_note': 'kept as reference only (P2-R4 A-3); K_F above is the locked value'},
        'A4_L_bound': {'observed_validate_max_boxes': n_max, 'N_sym_L_at_max_msym': L_max,
                       'fits_B_available': bool(L_max <= B_avail), 'K_max_boxes_under_B_available': K_L,
                       'p99_boxes': p99, 'expected_truncation_share': trunc_share,
                       'rule': 'no truncation if the observed maximum fits; otherwise the collaborator sends the top '
                               'min(N_box, K_max) boxes by confidence, and every policy using L follows the same rule'},
        'C2_attfusion': {'trainable_parameters_by_dim': att_params, 'checkpoint_keys': len(keys),
                         'checkpoint_keys_containing_fuse': fuse_keys, 'checkpoint_file': CKPT_FILE},
        'D2_cells': {'primary': cells, 'rule': 'AWGN at 8 dB and above; p_cw from the P1 grid product'},
        'D2_hard_subset': {'rule': 'frozen E branch misses >= 1 ground-truth object at IoU 0.5, canonical union GT (C-5)',
                           'primary': hard, 'scenes_total': int(len(uniq)),
                           'exploratory_ladder': [subset(k) for k in EXPLORATORY_MISS_LADDER],
                           'missed_quantiles_p25_p50_p75_p90': [float(x) for x in np.percentile(missed, [25, 50, 75, 90])]},
        'inputs': {'probe_sha256': sha(PROBE), 'chain_sha256': sha(CHAIN), 'link_scenarios_sha256': sha(LINKS),
                   'wp34_sha256': sha(WP34), 'grid_sha256': sha(GRID), 'wp2_npz_sha256': sha(WP2),
                   'checkpoint_sha256': sha(os.path.join(probe['ckpt_dir'], CKPT_FILE))},
        'command': 'python projects/ca_tosg_p2/protocol/round1_lock.py'}


def markdown(m):
    a1, a2, a3, a4, c2, d2c, d2h = (m[k] for k in ('A1_block', 'A2_bitstream', 'A3_budget', 'A4_L_bound', 'C2_attfusion', 'D2_cells', 'D2_hard_subset'))
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/round1_lock.py -- do not edit by hand -->',
         '# Round-1 lock arithmetic (P2-R4 A, C-2, D-2)', '', f"**{m['what']}.**", '',
         '## A-1 Block', '',
         f"Transmitted grid {a1['transmitted_grid'][0]} × {a1['transmitted_grid'][1]}, channels per branch "
         f"{a1['channels_per_branch']}. Block = {a1['block_cells'][0]} × {a1['block_cells'][1]} cells = "
         f"{a1['block_bev_m'][0]:.1f} m × {a1['block_bev_m'][1]:.1f} m; **{a1['n_blocks']} blocks**; "
         f"{', '.join(f'{x:,}' for x in a1['elements_per_block_per_branch'])} elements per block on branches 0, 1, 2 = "
         f"**{a1['elements_per_block']:,} elements per block**; {a1['head_cells_per_block'][0]} × {a1['head_cells_per_block'][1]} "
         f"head cells per block (head grid {a1['head_grid'][0]} × {a1['head_grid'][1]}). {a1['block_index']}.", '',
         '## A-2 Bitstream and overhead', '', f"Layout: {a2['layout']}.", '',
         '| item | bits per frame |', '|---|---:|']
    for k, v in a2['overhead_bits_per_frame'].items():
        L.append(f"| {k.replace('_', ' ')} | {v} |")
    L += ['', f"Bits per block: {a2['bits_per_block']:,}. Mask loss: {a2['mask_loss_semantics']}.", '',
          '## A-3 Budget and K_F', '',
          f"Link row: {a3['link_row']['technology']} {a3['link_row']['configuration']}, {a3['link_row']['capacity_variant']}, "
          f"D_comm = {a3['link_row']['D_comm_ms']:.0f} ms → **B_available = {a3['B_available_msym']:.4f} Msym**. "
          f"Upper bound because: {a3['why_upper_bound']}.", '',
          f"**K_F = {a3['K_F']}** of {a1['n_blocks']} blocks ({a3['share_of_blocks'] * 100:.1f} %): "
          f"{a3['bits_at_K_F']:,} bits → {a3['n_cw_at_K_F']:,} codewords → **N_sym,F(K_F) = {a3['N_sym_at_K_F_msym']:.4f} Msym** "
          f"≤ B_available. {a3['straddling_elements_at_K_F']:,} elements straddle two codewords in this message. "
          f"The draft's reference value {a3['reference_value_from_draft']} is kept as reference only.", '',
          '| K | bits | codewords | N_sym (Msym) | fits |', '|---:|---:|---:|---:|:---:|']
    for r in a3['ladder']:
        L.append(f"| {r['K']} | {r['bits']:,} | {r['n_cw']:,} | {r['N_sym_msym']:.4f} | {'yes' if r['fits'] else 'no'} |")
    L += ['', '## A-4 L bound', '',
          f"Observed validate maximum: {a4['observed_validate_max_boxes']} collaborator boxes → N_sym,L = "
          f"{a4['N_sym_L_at_max_msym']:.5f} Msym; fits B_available: **{'yes' if a4['fits_B_available'] else 'no'}** "
          f"→ {'**L is not truncated.**' if a4['fits_B_available'] else 'L is truncated.'} K_max under B_available would be "
          f"{a4['K_max_boxes_under_B_available']:,} boxes; p99 of the box count is {a4['p99_boxes']:.0f}; expected "
          f"truncation share {a4['expected_truncation_share'] * 100:.1f} %. Rule: {a4['rule']}.", '',
          '## C-2 AttFusion', '',
          f"Trainable parameters by feature dimension: {c2['trainable_parameters_by_dim']} (from the class). Checkpoint "
          f"`{c2['checkpoint_file']}`: {c2['checkpoint_keys']} state-dict keys, of which containing \"fuse\": "
          f"{c2['checkpoint_keys_containing_fuse'] or 'none'}. Recorded as fact; the freeze in C-1 does not depend on it.", '',
          '## D-2 Pre-registered cells and hard-frame subset', '',
          f"Primary cells ({d2c['rule']}): " + ', '.join(f"{c['channel'].upper()} {c['snr_db']} dB (p_cw = {c['p_cw']:.5f})" for c in d2c['primary']) + '.', '',
          f"Hard-frame subset ({d2h['rule']}): **{d2h['primary']['frames']:,} of 1,980 frames ({d2h['primary']['share'] * 100:.1f} %)**, "
          f"in {d2h['primary']['scenes_with_frames']} of {d2h['scenes_total']} scenes, at least {d2h['primary']['min_frames_in_a_scene']} per scene. "
          f"Missed-object quantiles p25/p50/p75/p90: {', '.join(f'{x:g}' for x in d2h['missed_quantiles_p25_p50_p75_p90'])}.", '',
          'Exploratory ladder (D-3; reported, never confirmatory):', '',
          '| min missed | frames | share | scenes with frames | min frames in a scene |', '|---:|---:|---:|---:|---:|']
    for s in d2h['exploratory_ladder']:
        L.append(f"| {s['min_missed']} | {s['frames']:,} | {s['share'] * 100:.1f} % | {s['scenes_with_frames']} | {s['min_frames_in_a_scene']} |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        txt = open(PROTOCOL).read() if os.path.exists(PROTOCOL) else ''
        k_ok = f"K_F = {m['A3_budget']['K_F']}" in txt and 'Status: LOCKED' in txt
        print('round1 lock:', 'reproduced' if ok else 'FAIL -- not what the generator writes',
              '| protocol states K_F and LOCKED:', 'yes' if k_ok else 'NO')
        return 0 if (ok and k_ok) else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
