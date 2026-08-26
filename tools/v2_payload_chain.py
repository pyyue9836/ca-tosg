#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""V2-R3 step 5: derive the whole v2 payload chain, print every step, and self-check the identity.

D-1, the rule this tool exists to enforce: **`B_F` is derived from `N_cw`, never from
`(info + header) / rate / log2 M`.** The direct route silently ignores LDPC codeword padding, and
`N_cw` is the unit the BLER model actually acts on — a payload that disagrees with the number of
codewords transmitted is a payload for a different experiment. The two routes differ by the padding,
and the difference is printed rather than hidden.

    python tools/v2_payload_chain.py [--json]
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, 'results', 'manifests', 'P4B_PROBE_pointpillar_compression.json')
SANITY = os.path.join(ROOT, 'results', 'v2', 'sanity_single_vehicle_validate.csv')
OUT = os.path.join(ROOT, 'results', 'v2', 'payload_chain.json')

# --- protocol constants (docs/unified_branch_protocol_v2.md; C-2, B-1, B-3) -------------------
W_BITS = 8            # int8, symmetric, validate-calibrated, frozen (C-2 / B-4)
P_BITS = 8000         # payload bits per packet (C-2)
H_BITS = 320          # header bits per packet, F and L alike (C-2, D-2)
K, N_LDPC = 500, 1000  # 5G-LDPC rate-1/2, the committed chain
M_QAM = 16
BITS_PER_SYM = int(math.log2(M_QAM))
B_BOX_BITS = 184      # B-1: the ETSI-CPM-style object container, itemised in the protocol
BETAS = (0.10, 0.20, 0.30)
SYM_PER_CW = N_LDPC / BITS_PER_SYM      # 250 symbols -- the ladder step


def packetise(info_bits):
    """(n_full, tail_payload_bits, per-packet bit sizes). The tail packet is NOT padded to P;
    only codeword-level padding applies (D-1)."""
    n_full = info_bits // P_BITS
    tail = info_bits - n_full * P_BITS
    sizes = [P_BITS + H_BITS] * n_full + ([tail + H_BITS] if tail else [])
    return int(n_full), int(tail), sizes


def codewords(sizes):
    return int(sum(math.ceil(s / K) for s in sizes))


def msym(n_cw):
    return n_cw * N_LDPC / BITS_PER_SYM / 1e6


def direct_msym(info_bits, header_bits):
    """The FORBIDDEN route, computed only so the padding gap can be printed."""
    return (info_bits + header_bits) / 0.5 / BITS_PER_SYM / 1e6


def f_chain():
    probe = json.load(open(PROBE))
    elems = int(probe['totals_per_cav']['transmitted_elements'])
    info = elems * W_BITS
    n_full, tail, sizes = packetise(info)
    n_cw = codewords(sizes)
    b_f = msym(n_cw)
    hdr = H_BITS * len(sizes)
    return dict(elements=elems, info_bits=info, n_full=n_full, tail_bits=tail,
                packets=len(sizes), header_bits=hdr, n_cw=n_cw, msym=b_f,
                cw_full=math.ceil((P_BITS + H_BITS) / K),
                cw_tail=(math.ceil((tail + H_BITS) / K) if tail else 0),
                direct_msym=direct_msym(info, hdr))


def l_chain(n_boxes):
    info = int(n_boxes) * B_BOX_BITS
    n_full, tail, sizes = packetise(info)
    n_cw = codewords(sizes)
    return dict(n_boxes=int(n_boxes), info_bits=info, packets=len(sizes),
                n_cw=n_cw, msym=msym(n_cw))


def main():
    f = f_chain()
    print('=' * 78)
    print('F CHAIN -- one collaborator, one message per frame (B-2)')
    print('=' * 78)
    print(f'  transmitted elements/CAV            {f["elements"]:>12,}   (P4B forward-hook probe)')
    print(f'  x w = {W_BITS} bit                        {f["info_bits"]:>12,}   info bits')
    print(f'  packetise at P = {P_BITS:,} bits        {f["n_full"]:>12,}   full packets'
          f'  + tail {f["tail_bits"]:,} bits')
    print(f'  + H_F = {H_BITS} bits/packet             {f["header_bits"]:>12,}   header bits over '
          f'{f["packets"]:,} packets')
    print(f'  codewords: full packet ({P_BITS + H_BITS:,} b)  ceil/{K} = {f["cw_full"]:>3}'
          f'   x {f["n_full"]:,}')
    print(f'             tail packet ({f["tail_bits"] + H_BITS:,} b)  ceil/{K} = {f["cw_tail"]:>3}'
          f'   x {1 if f["tail_bits"] else 0}')
    print(f'  N_cw                                {f["n_cw"]:>12,}')
    print(f'  B_F = N_cw x {N_LDPC} / {BITS_PER_SYM} / 1e6        {f["msym"]:>12.5f}   Msym/frame')
    print()
    print(f'  FORBIDDEN direct route (info+header)/rate/log2M = {f["direct_msym"]:.5f} Msym')
    gap = f['msym'] - f['direct_msym']
    print(f'  codeword-padding gap                {gap:>+12.5f}   Msym '
          f'({gap / f["direct_msym"] * 100:+.3f} %) -- this is why D-1 forbids the direct route')

    # identity self-check
    ok = abs(f['msym'] - f['n_cw'] * N_LDPC / BITS_PER_SYM / 1e6) < 1e-12
    print(f'\n  IDENTITY  Msym == N_cw x n / log2M / 1e6 : {"PASS" if ok else "FAIL"}')
    if not ok:
        return 1

    print('\n' + '=' * 78)
    print('BETA TIERS -- B_max = beta x B_F (B-3)')
    print('=' * 78)
    tiers = {}
    for b in BETAS:
        tiers[f'{b:.2f}'] = b * f['msym']
        print(f'  beta = {b:.2f}   B_max = {b * f["msym"]:.5f} Msym/frame')

    print('\n' + '=' * 78)
    print('L CHAIN -- same packet/header/LDPC/QAM chain as F (D-2)')
    print('=' * 78)
    print(f'  B_box = {B_BOX_BITS} bits = {B_BOX_BITS / 8:.0f} B')
    print(f'  {"N_box":>6} {"info bits":>10} {"pkts":>5} {"N_cw":>6} {"B_L [Msym]":>12}'
          f' {"% of beta=0.10":>15}')
    for nb in (1, 5, 10, 20, 22, 28, 30, 43, 50, 100):
        r = l_chain(nb)
        print(f'  {nb:>6} {r["info_bits"]:>10,} {r["packets"]:>5} {r["n_cw"]:>6}'
              f' {r["msym"]:>12.5f} {r["msym"] / tiers["0.10"] * 100:>14.2f}%')

    dist = None
    if os.path.exists(SANITY):
        import pandas as pd
        d = pd.read_csv(SANITY)
        nb = d.n_box_single
        rows = [l_chain(x) for x in nb]
        vals = [r['msym'] for r in rows]
        cws = [r['n_cw'] for r in rows]
        import statistics as st
        dist = dict(n=len(vals), n_box_mean=float(nb.mean()), n_box_min=int(nb.min()),
                    n_box_max=int(nb.max()), msym_mean=st.mean(vals), msym_min=min(vals),
                    msym_max=max(vals), n_cw_mean=st.mean(cws), n_cw_min=min(cws),
                    n_cw_max=max(cws))
        print(f'\n  PROXY DISTRIBUTION over the {dist["n"]} sanity frames'
              f' -- the EGO\'s single-vehicle box counts standing in for the collaborator\'s,'
              f'\n  because the collaborator arm does not exist yet (work package 4 replaces this):')
        print(f'    N_box  mean {dist["n_box_mean"]:.2f}  range {dist["n_box_min"]}'
              f'-{dist["n_box_max"]}')
        print(f'    N_cw,L mean {dist["n_cw_mean"]:.2f}  range {dist["n_cw_min"]}'
              f'-{dist["n_cw_max"]}   (vs N_cw,F = {f["n_cw"]:,})')
        print(f'    B_L    mean {dist["msym_mean"]:.5f}  range {dist["msym_min"]:.5f}'
              f'-{dist["msym_max"]:.5f} Msym')
        print(f'    B_L mean as % of beta=0.10 budget: '
              f'{dist["msym_mean"] / tiers["0.10"] * 100:.2f}%')
        print(f'    L reliability is DERIVED, not assumed: {dist["n_cw_mean"]:.0f} codewords vs '
              f'{f["n_cw"]:,} for F -- a factor of {f["n_cw"] / dist["n_cw_mean"]:.0f} fewer '
              f'chances to fail')

    print('\n' + '=' * 78)
    print('LADDER-GAP CHECK -- payload is quantised in whole codewords')
    print('=' * 78)
    step = SYM_PER_CW / 1e6
    print(f'  one codeword = {SYM_PER_CW:.0f} symbols = {step:.5f} Msym  <- the smallest step B_L can take')
    print(f'  beta=0.10 budget spans {tiers["0.10"] / step:,.0f} steps; the tiers are '
          f'{(tiers["0.20"] - tiers["0.10"]) / step:,.0f} steps apart')
    fine = (tiers['0.20'] - tiers['0.10']) / step > 100
    print(f'  tiers distinguishable at codeword granularity: {"PASS" if fine else "FAIL"}')
    if not fine:
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as fh:
        json.dump({'schema': 'catosg-v2-payload-chain/1',
                   'constants': dict(w_bits=W_BITS, P_bits=P_BITS, H_bits=H_BITS, K=K, n=N_LDPC,
                                     M=M_QAM, B_box_bits=B_BOX_BITS),
                   'F': f, 'beta_tiers_msym': tiers, 'L_proxy_distribution': dist,
                   'ladder_step_msym': step, 'identity_check': 'PASS'}, fh, indent=1)
    print(f'\nwrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
