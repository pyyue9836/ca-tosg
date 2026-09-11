#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R3 C-2 / C-4 — spatial-block arithmetic for budgeted F transmission. Payload arithmetic only.

Reads three things and nothing else:
  * the checkpoint's transmitted tensor shapes (results/manifests/P4B_PROBE_pointpillar_compression.json)
    and the head's upsampling (the checkpoint config the probe names);
  * the link capacities written by link_scenarios.py;
  * P1's payload chain (tools/v2_payload_chain.py).
It opens no perception output and runs no network: F-1, no feature experiment before lock.

The block mapping is DERIVED from the shapes, not declared. All three transmitted branches share one
spatial grid; a block is a rectangle of cells on that grid, and the tool refuses to run if the grid is
not shared or a block size does not tile it exactly, because a block that covers different ground on
different branches would not be one block.

    python projects/ca_tosg_p2/protocol/f_block_budget.py [--check]      # after link_scenarios.py
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v2_payload_chain as pcm                                                    # noqa: E402

PROBE = os.path.join(ROOT, 'results/manifests/P4B_PROBE_pointpillar_compression.json')
CHAIN = os.path.join(ROOT, 'results/v2/payload_chain.json')
LINKS = os.path.join(HERE, 'link_scenarios.json')
OUT_JSON = os.path.join(HERE, 'f_block_budget.json')
OUT_MD = os.path.join(HERE, 'f_block_budget.md')

# block sizes in transmitted-grid cells (rows, cols). 'primary' is the draft's definition; the other two
# are pre-declared granularities, fixed here so that none can be added after a result is seen.
BLOCKS = [('primary', 5, 8), ('finer', 5, 4), ('finest', 1, 1)]
# rows of link_scenarios.json the budget is shown for: the two 20 MHz technologies named in P2-R3 A-2
ROWS = [('IEEE 802.11bd', '20 MHz', 'zero-overhead upper bound'),
        ('NR sidelink', '20 MHz / 30 kHz', 'zero-overhead upper bound'),
        ('NR sidelink', '20 MHz / 30 kHz', 'minus mandatory minimum PHY overhead')]
# per-frame quantisation signalling: the three per-branch int8 scales are calibrated once and
# pre-shared (docs/unified_branch_protocol_v2.md §3.3), so a frame carries none of them
QUANT_PARAM_BITS_PER_FRAME = 0


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def msym_for_bits(bits):
    """P1's chain for an arbitrary bit count: packetise, 320-bit headers, LDPC codewords, channel uses."""
    if bits <= 0:
        return 0.0
    _, _, sizes = pcm.packetise(int(bits))
    return pcm.msym(pcm.codewords(sizes))


def build():
    probe = json.load(open(PROBE))
    tx = [b['transmitted_shape_per_cav'] for b in probe['branches']]
    pre = [b['pre_compression_shape_per_cav'] for b in probe['branches']]
    Hs, Ws = {s[1] for s in tx}, {s[2] for s in tx}
    if len(Hs) != 1 or len(Ws) != 1:
        raise SystemExit('F BLOCK BUDGET: the branches do not share one transmitted grid -- a block '
                         'would cover different ground on different branches; refusing')
    H, W = Hs.pop(), Ws.pop()
    C = [s[0] for s in tx]
    cfg = probe['config']
    rng, vox = cfg['cav_lidar_range'], cfg['voxel_size']
    extent_x, extent_y = rng[3] - rng[0], rng[4] - rng[1]
    cell_x, cell_y = extent_x / W, extent_y / H

    ckpt_cfg_path = os.path.join(probe['ckpt_dir'], 'config.yaml')
    ckpt = yaml.load(open(ckpt_cfg_path), Loader=yaml.UnsafeLoader)  # trusted local OpenCOOD checkpoint config; it holds numpy-tagged values SafeLoader rejects
    bb = ckpt['model']['args']['base_bev_backbone']
    ups = bb['upsample_strides']
    head_grid = [pre[0][1] * ups[0], pre[0][2] * ups[0]]
    for i in range(len(pre)):
        if [pre[i][1] * ups[i], pre[i][2] * ups[i]] != head_grid:
            raise SystemExit('F BLOCK BUDGET: upsampled branches do not meet on one head grid; refusing')

    B_F = json.load(open(CHAIN))['F']['msym']
    total = sum(c * H * W for c in C)
    if total != probe['totals_per_cav']['transmitted_elements']:
        raise SystemExit('F BLOCK BUDGET: element total disagrees with the probe')
    if abs(msym_for_bits(total * pcm.W_BITS) - B_F) > 1e-12:
        raise SystemExit('F BLOCK BUDGET: the full tensor does not reproduce B_F through the chain')

    links = json.load(open(LINKS))['rows']
    out_blocks = []
    for name, r, c in BLOCKS:
        if H % r or W % c:
            raise SystemExit(f'F BLOCK BUDGET: block {r}x{c} does not tile the {H}x{W} grid exactly')
        nb = (H // r) * (W // c)
        per_branch = [ch * r * c for ch in C]
        e = sum(per_branch)
        mask_bits = nb                                   # one bit per block, fixed per frame
        index_bits_each = max(1, math.ceil(math.log2(nb)))
        mapping = [{'branch': i, 'transmitted_cells': [r, c],
                    'decoded_grid': [pre[i][1], pre[i][2]],
                    'decoded_cells_per_block': [r * pre[i][1] // H, c * pre[i][2] // W]}
                   for i in range(len(pre))]
        budget = []
        for key in ROWS:
            for L in links:
                if (L['technology'], L['configuration'], L['capacity_variant']) != key:
                    continue
                cap, k = L['capacity_msym'], 0
                for kk in range(nb + 1):
                    if msym_for_bits(kk * e * pcm.W_BITS + mask_bits + QUANT_PARAM_BITS_PER_FRAME) <= cap:
                        k = kk
                    else:
                        break
                budget.append({'technology': key[0], 'configuration': key[1], 'capacity_variant': key[2],
                               'D_comm_ms': L['D_comm_ms'], 'capacity_msym': cap, 'k_max_blocks': k,
                               'fraction_of_blocks': k / nb,
                               'N_sym_at_k_max_msym': msym_for_bits(k * e * pcm.W_BITS + mask_bits)})
        out_blocks.append({'name': name, 'rows_x_cols_cells': [r, c],
                           'bev_size_m': [round(r * cell_y, 6), round(c * cell_x, 6)],
                           'n_blocks': nb, 'elements_per_block_per_branch': per_branch,
                           'elements_per_block': e, 'bits_per_block': e * pcm.W_BITS,
                           'mask_bitmap_bits': mask_bits, 'index_list_bits_per_selected_block': index_bits_each,
                           'head_cells_per_block': [r * head_grid[0] // H, c * head_grid[1] // W],
                           'mapping': mapping, 'budget': budget})
    return {
        'schema': 'catosg-p2-f-block-budget/1',
        'what': 'payload arithmetic only; no perception output is read and no network is run',
        'transmitted_grid': [H, W], 'transmitted_channels_per_branch': C,
        'pre_compression_shapes': pre, 'head_grid': head_grid,
        'bev_extent_m': [extent_y, extent_x], 'transmitted_cell_m': [cell_y, cell_x],
        'voxel_size_m': vox[:2], 'quant_param_bits_per_frame': QUANT_PARAM_BITS_PER_FRAME,
        'capacity_note': 'capacities are the link_scenarios.json values; the upper-bound rows overstate '
                         'any real link, so k_max there is an upper bound on blocks sent',
        'inputs': {'probe': os.path.relpath(PROBE, ROOT), 'probe_sha256': sha(PROBE),
                   'checkpoint_config': ckpt_cfg_path, 'checkpoint_config_sha256': sha(ckpt_cfg_path),
                   'link_scenarios_sha256': sha(LINKS)},
        'blocks': out_blocks,
        'command': 'python projects/ca_tosg_p2/protocol/f_block_budget.py'}


def markdown(m):
    H, W = m['transmitted_grid']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/f_block_budget.py -- do not edit by hand -->',
         '# F spatial blocks — mapping and budget (P2-R3 C-2, C-4)', '',
         f"**{m['what'][0].upper() + m['what'][1:]}.**", '',
         f"All three transmitted branches share one {H} × {W} grid; each cell covers "
         f"{m['transmitted_cell_m'][0]:.1f} m × {m['transmitted_cell_m'][1]:.1f} m of the "
         f"{m['bev_extent_m'][0]:.1f} m × {m['bev_extent_m'][1]:.1f} m BEV area. Transmitted channels per "
         f"branch: {m['transmitted_channels_per_branch']}. The detection head works on a "
         f"{m['head_grid'][0]} × {m['head_grid'][1]} grid.", '',
         '## Block definitions', '',
         '| block | cells (rows × cols) | BEV size (m) | blocks | elements / block (b0, b1, b2) | '
         'elements / block | mask bits / frame | index bits / selected block | decoded cells / block '
         '(b0, b1, b2) | head cells / block |',
         '|---|---|---|---:|---|---:|---:|---:|---|---|']
    for b in m['blocks']:
        dec = ', '.join(f"{x['decoded_cells_per_block'][0]}×{x['decoded_cells_per_block'][1]}"
                        for x in b['mapping'])
        L.append(f"| {b['name']} | {b['rows_x_cols_cells'][0]} × {b['rows_x_cols_cells'][1]} "
                 f"| {b['bev_size_m'][0]:.1f} × {b['bev_size_m'][1]:.1f} | {b['n_blocks']:,} "
                 f"| {', '.join(f'{x:,}' for x in b['elements_per_block_per_branch'])} "
                 f"| {b['elements_per_block']:,} | {b['mask_bitmap_bits']:,} "
                 f"| {b['index_list_bits_per_selected_block']} | {dec} "
                 f"| {b['head_cells_per_block'][0]}×{b['head_cells_per_block'][1]} |")
    L += ['', f"Quantisation parameters per frame: {m['quant_param_bits_per_frame']} bits (per-branch "
          'scales pre-shared, `docs/unified_branch_protocol_v2.md` §3.3). Packet headers and LDPC padding '
          'are charged by the P1 chain, not listed separately.', '',
          '## Blocks that fit (k_max)', '', f"{m['capacity_note']}.", '',
          '| block | technology | configuration | capacity | D_comm | capacity (Msym) | k_max | share of '
          'blocks | N_sym at k_max (Msym) |', '|---|---|---|---|---:|---:|---:|---:|---:|']
    for b in m['blocks']:
        for r in b['budget']:
            L.append(f"| {b['name']} | {r['technology']} | {r['configuration']} | {r['capacity_variant']} "
                     f"| {r['D_comm_ms']:.0f} ms | {r['capacity_msym']:.4f} | {r['k_max_blocks']} "
                     f"| {r['fraction_of_blocks'] * 100:.1f} % | {r['N_sym_at_k_max_msym']:.4f} |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and \
             os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('f block budget:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
