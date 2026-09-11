#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R1 C-2 / C-3 — the P1 artefacts P2 reuses, pinned by path and content hash, and verified.

P2's offline reference decision reuses P1's per-(frame, SNR, channel) effective utilities and P1's
payload chain. Reuse is only safe if what is reused is exactly what P1 produced, so this tool:

  1. hashes every reused file (sha256) and records the path;
  2. re-derives B_F from the payload-chain code and checks it against the recorded product;
  3. re-derives every frame's B_L from its collaborator box count and checks it against the product;
  4. checks C-7 on the reused grid itself -- that B_E, B_L and B_F do not vary with SNR or channel
     type, i.e. that under a fixed MCS the symbol count of an action is not a function of the
     channel, and a bad channel shows up only through the utility.

It reads PAYLOAD columns only. No eff_* / f1_* / outcome column is opened: before the protocol is
locked P2 runs zero experiments, and a manifest builder that looked at utilities would be one.
Development split (validate) only; nothing sealed or held-out is listed or read.

    python projects/ca_tosg_p2/protocol/build_reuse_manifest.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'p2_reuse_manifest.json')
sys.path.insert(0, os.path.join(ROOT, 'tools'))

# role -> (path, what P2 takes from it)
REUSED = [
    ('utility_grid_primary', 'results/v2/v2_grid_validate_ideal.csv',
     'eff_E, eff_L, eff_F per (frame, SNR, channel) under fragment-aware partial recovery; '
     'B_E, B_L, B_F per row'),
    ('utility_grid_primary_meta', 'results/v2/v2_grid_validate_ideal.json',
     'the definitions of eff_L and eff_F and the payload contract the grid was built under'),
    ('utility_grid_packet_sensitivity', 'results/v2/v2_grid_validate_packet.csv',
     'the same columns under packet-level recovery; sensitivity only, as in P1'),
    ('utility_grid_packet_sensitivity_meta', 'results/v2/v2_grid_validate_packet.json',
     'definitions for the packet grid'),
    ('grid_builder', 'projects/ca_tosg/evaluation/v2_build_grid.py',
     'the code that applies the P1 §9.3 interpolation rule and the message-level rule for L'),
    ('interpolation_rule', 'docs/unified_branch_protocol_v2.md',
     '§9.3 (a)-(g): replicate averaging, piecewise-linear in raw p, locked endpoints, no monotone '
     'correction, ideal regime mainline'),
    ('payload_chain_code', 'tools/v2_payload_chain.py',
     'f_chain / l_chain: packetisation, headers, LDPC codeword count, channel uses'),
    ('payload_chain_product', 'results/v2/payload_chain.json', 'B_F = N_cw,F channel uses'),
    ('per_frame_L_payload', 'results/v2/wp34_e_l_validate.csv',
     'n_box_collab, n_cw_L, B_L_msym per validate frame'),
    ('per_frame_L_payload_meta', 'results/v2/wp34_e_l_validate.json', 'provenance of the above'),
]
PAYLOAD_ONLY = ['sample_id', 'snr_db', 'channel', 'B_E', 'B_L', 'B_F']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def build():
    import v2_payload_chain as pcm
    files = []
    for role, rel, takes in REUSED:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            raise SystemExit(f'REUSE MANIFEST: {rel} is missing -- P2 cannot reuse what is not there')
        files.append({'role': role, 'path': rel, 'sha256': sha(p), 'bytes': os.path.getsize(p),
                      'p2_takes': takes})

    pc = json.load(open(os.path.join(ROOT, 'results/v2/payload_chain.json')))
    F = pcm.f_chain()
    chain_F = {'B_F_msym_recomputed': F['msym'], 'B_F_msym_recorded': pc['F']['msym'],
               'N_cw_F_recomputed': F['n_cw'], 'N_cw_F_recorded': pc['F']['n_cw'],
               'match': F['msym'] == pc['F']['msym'] and F['n_cw'] == pc['F']['n_cw']}

    w = pd.read_csv(os.path.join(ROOT, 'results/v2/wp34_e_l_validate.csv'),
                    usecols=['frame', 'n_box_collab', 'n_cw_L', 'B_L_msym'])
    rec = [pcm.l_chain(int(n)) for n in w.n_box_collab]
    dmsym = np.abs(np.array([r['msym'] for r in rec]) - w.B_L_msym.to_numpy())
    dcw = np.array([r['n_cw'] for r in rec]) != w.n_cw_L.to_numpy()
    chain_L = {'frames': int(len(w)), 'max_abs_B_L_diff_msym': float(dmsym.max()),
               'n_cw_L_mismatches': int(dcw.sum()), 'match': bool(dmsym.max() == 0 and not dcw.any())}

    g = pd.read_csv(os.path.join(ROOT, 'results/v2/v2_grid_validate_ideal.csv'), usecols=PAYLOAD_ONLY)
    per_frame = g.groupby('sample_id').agg(nL=('B_L', 'nunique'), nF=('B_F', 'nunique'),
                                           nE=('B_E', 'nunique'))
    first_L = g.groupby('sample_id').B_L.first().sort_index().to_numpy()
    c7 = {'rows': int(len(g)), 'frames': int(len(per_frame)),
          'cells_per_frame': int(g.groupby('sample_id').size().iloc[0]),
          'frames_where_B_L_varies_with_channel': int((per_frame.nL > 1).sum()),
          'frames_where_B_F_varies_with_channel': int((per_frame.nF > 1).sum()),
          'frames_where_B_E_varies_with_channel': int((per_frame.nE > 1).sum()),
          'B_F_distinct_values': sorted(float(x) for x in g.B_F.unique()),
          'grid_B_L_equals_wp34_B_L': bool(np.array_equal(first_L, w.B_L_msym.to_numpy())),
          'columns_read': PAYLOAD_ONLY}
    c7['holds'] = (c7['frames_where_B_L_varies_with_channel'] == 0
                   and c7['frames_where_B_F_varies_with_channel'] == 0
                   and c7['frames_where_B_E_varies_with_channel'] == 0)

    b = w.B_L_msym.to_numpy()
    L_dist = {'frames': int(len(b)), 'mean_msym': float(b.mean()),
              **{k: float(v) for k, v in zip(('min_msym', 'p05_msym', 'p50_msym', 'p95_msym', 'max_msym'),
                                            np.percentile(b, [0, 5, 50, 95, 100]))}}

    ok = chain_F['match'] and chain_L['match'] and c7['holds'] and c7['grid_B_L_equals_wp34_B_L']
    return {'schema': 'catosg-p2-reuse-manifest/1',
            'split': 'validate (development) only; no sealed or held-out product is listed or read',
            'files': files, 'verification': {'payload_chain_F': chain_F, 'payload_chain_L': chain_L,
                                              'C7_symbol_count_independent_of_channel': c7,
                                              'all_pass': ok},
            'L_payload_distribution': L_dist,
            'command': 'python projects/ca_tosg_p2/protocol/build_reuse_manifest.py'}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    txt = json.dumps(m, indent=1) + '\n'
    if a.check:
        if not os.path.exists(OUT) or open(OUT).read() != txt:
            print('REUSE MANIFEST FAIL: recorded manifest is not what the builder writes'); return 1
        print('reuse manifest: reproduced'); return 0 if m['verification']['all_pass'] else 1
    open(OUT, 'w').write(txt)
    v = m['verification']
    print('payload chain F', v['payload_chain_F']['match'], '| payload chain L', v['payload_chain_L']['match'],
          '| C-7 holds', v['C7_symbol_count_independent_of_channel']['holds'], '| all_pass', v['all_pass'])
    print('wrote', os.path.relpath(OUT, ROOT))
    return 0 if v['all_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
