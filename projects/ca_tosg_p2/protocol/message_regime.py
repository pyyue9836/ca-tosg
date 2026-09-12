#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R10 B — what the message all-or-nothing accounting implies, from P1's existing products. CPU only.

  B-1  do P1's message-regime products describe the CURRENT model and payload? Hashes and the commit
       that produced each file are recorded, and the codeword count is checked against the chain.
  B-2  eff_F on all 22 channel cells under three accountings -- message all-or-nothing, fragment-aware
       partial recovery, packet-level -- beside eff_L and eff_E, with the cells where the message
       accounting puts F within 1e-3 of E marked.
  B-3  the plain statement: under the message accounting, in which cells is F usable at all, and is
       there any Rayleigh cell where F beats L.
  B-4  P1's recorded survival probability at p = 0.001.

ONE COLUMN IS CONSTRUCTED, NOT READ. No product holds eff_F under the message accounting: the grid
carries `q_msg_F_descriptive` and nothing else. It is built here by the SAME message-level rule P1
applies to L (protocol sec 4.3): a message that loses any codeword is unusable and the frame falls
back to the ego-only result,

    eff_F_message = q * f1_clean + (1 - q) * f1_ego,    q = (1 - p_cw) ** N_cw

with f1_clean and f1_ego the per-frame P1 products. This is an accounting choice being COSTED, not a
choice being made: P2-R10 B-5 leaves the ruling to Josh.

    python projects/ca_tosg_p2/protocol/message_regime.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
OUT_JSON = os.path.join(HERE, 'message_regime.json')
OUT_MD = os.path.join(HERE, 'message_regime.md')
V2 = os.path.join(ROOT, 'results', 'v2')
CHAIN = os.path.join(V2, 'payload_chain.json')
NEAR_E = 1e-3


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def commit_of(rel):
    r = subprocess.run(['git', 'log', '--oneline', '-1', '--', rel], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or 'not committed'


def scene_equal(v, scenes):
    return float(np.mean([v[scenes == s].mean() for s in np.unique(scenes)]))


def build():
    chain = json.load(open(CHAIN))['F']
    msg = json.load(open(os.path.join(V2, 'wp5_message_validate.json')))
    fin = json.load(open(os.path.join(V2, 'wp5_final_validate.json')))
    files = {}
    for rel in ('results/v2/wp5_message_validate.json', 'results/v2/wp5_final_validate.json',
                'results/v2/wp5_final_validate.csv', 'results/v2/v2_grid_validate_ideal.csv',
                'results/v2/v2_grid_validate_packet.csv', 'results/v2/wp34_e_l_validate.csv'):
        files[rel] = {'sha256': sha(os.path.join(ROOT, rel)), 'commit': commit_of(rel)}

    # B-1: does the message product describe the current model and payload?
    b1 = {'files': files,
          'wp5_message': {'schema': msg['schema'], 'split': msg['split'], 'frames': msg['frames'],
                          'n_cw': msg['n_cw'], 'n_replays': msg['n_replays']},
          'chain_n_cw': chain['n_cw'], 'chain_elements': chain['elements'],
          'n_cw_matches_current_payload': msg['n_cw'] == chain['n_cw'],
          'frames_match_split': msg['frames'] == 1980,
          'what_it_contains': 'per-rate survival probability q, the expected frames surviving, a per-frame '
                              'expected F1 mean and Monte-Carlo AP; it does NOT contain a per-cell or '
                              'per-frame eff_F under the message accounting',
          'grid_has_eff_F_message': False,
          'note_from_the_product': msg['message_regime']['0.001'].get('note', '')}
    if not b1['n_cw_matches_current_payload']:
        raise SystemExit('B-1: the message product was built for a different codeword count -- stop')

    # B-2 / B-3
    gi = pd.read_csv(os.path.join(V2, 'v2_grid_validate_ideal.csv'),
                     usecols=['sample_id', 'scene', 'snr_db', 'channel', 'p_cw', 'eff_E', 'eff_L', 'eff_F'])
    gp = pd.read_csv(os.path.join(V2, 'v2_grid_validate_packet.csv'),
                     usecols=['sample_id', 'snr_db', 'channel', 'eff_F']).rename(columns={'eff_F': 'eff_F_packet'})
    g = gi.merge(gp, on=['sample_id', 'snr_db', 'channel'], validate='one_to_one')
    w5 = pd.read_csv(os.path.join(V2, 'wp5_final_validate.csv'), usecols=['frame', 'f1_clean', 'f1_ego'])
    w5 = w5.set_index('frame')
    g['f1_clean'] = w5.f1_clean.loc[g.sample_id].to_numpy()
    g['f1_ego'] = w5.f1_ego.loc[g.sample_id].to_numpy()
    n_cw = chain['n_cw']
    g['q_msg'] = (1.0 - g.p_cw.to_numpy()) ** n_cw
    g['eff_F_message'] = g.q_msg * g.f1_clean + (1.0 - g.q_msg) * g.f1_ego

    rows = []
    for (ch, snr), t in g.groupby(['channel', 'snr_db']):
        sc = t.scene.to_numpy()
        r = {'channel': ch, 'snr_db': int(snr), 'p_cw': float(t.p_cw.iloc[0]),
             'q_message_survives': float(t.q_msg.iloc[0]),
             'eff_E': scene_equal(t.eff_E.to_numpy(), sc),
             'eff_L': scene_equal(t.eff_L.to_numpy(), sc),
             'eff_F_partial': scene_equal(t.eff_F.to_numpy(), sc),
             'eff_F_packet': scene_equal(t.eff_F_packet.to_numpy(), sc),
             'eff_F_message': scene_equal(t.eff_F_message.to_numpy(), sc)}
        r['message_minus_E'] = r['eff_F_message'] - r['eff_E']
        r['message_within_1e-3_of_E'] = bool(abs(r['message_minus_E']) < NEAR_E)
        r['message_minus_L'] = r['eff_F_message'] - r['eff_L']
        r['partial_minus_L'] = r['eff_F_partial'] - r['eff_L']
        rows.append(r)
    rows.sort(key=lambda x: (x['channel'], x['snr_db']))

    usable = [f"{r['channel'].upper()} {r['snr_db']} dB" for r in rows if not r['message_within_1e-3_of_E']]
    ray = [r for r in rows if r['channel'] == 'rayleigh']
    ray_F_beats_L = [f"{r['channel'].upper()} {r['snr_db']} dB" for r in ray if r['message_minus_L'] > 0]
    awgn_F_beats_L_msg = [f"AWGN {r['snr_db']} dB" for r in rows if r['channel'] == 'awgn' and r['message_minus_L'] > 0]
    ray_partial_beats_L = [f"RAYLEIGH {r['snr_db']} dB" for r in ray if r['partial_minus_L'] > 0]

    return {
        'schema': 'catosg-p2-message-regime/1',
        'what': 'P1 products only, read and recombined on CPU; no model was run and no product was rewritten',
        'B1_provenance': b1,
        'constructed_column': {
            'name': 'eff_F_message',
            'formula': 'q * f1_clean + (1 - q) * f1_ego, q = (1 - p_cw) ** N_cw',
            'n_cw': n_cw,
            'rule_source': "P1's message-level rule for L (protocol sec 4.3): a failed delivery falls back to "
                           'the ego-only result',
            'status': 'CONSTRUCTED here from P1 per-frame products; it is not a stored product, and building it '
                      'is not a decision that this accounting is adopted'},
        'B2_cells': rows, 'near_E_threshold': NEAR_E,
        'B3_statement': {
            'cells_where_F_is_more_than_E_under_message': usable,
            'n_cells_usable': len(usable), 'n_cells_total': len(rows),
            'rayleigh_cells_where_message_F_beats_L': ray_F_beats_L,
            'awgn_cells_where_message_F_beats_L': awgn_F_beats_L_msg,
            'rayleigh_cells_where_partial_F_beats_L': ray_partial_beats_L},
        'B4_recorded_survival': {'p': 0.001, 'q': fin['message_regime']['0.001']['p_message_survives'],
                                 'expected_frames_surviving_of_1980': msg['message_regime']['0.001']['expected_frames_surviving'],
                                 'source': 'results/v2/wp5_final_validate.json and wp5_message_validate.json'},
        'B5_open': {'ruling': 'the accounting -- message all-or-nothing, packet, or partial recovery -- is not '
                              'presupposed here and is left to Josh',
                    'fallback_after_a_failed_send': 'RULE PENDING. What the receiver does when a message that was '
                                                    'sent does not arrive: under the message accounting the frame '
                                                    'falls back to the ego-only result, which is what the column '
                                                    'above costs; under partial recovery it keeps what arrived. '
                                                    'The rule is filled in once the accounting is ruled',
                    'deciding_to_request_L_before_sending': 'RULE PENDING. What the ego requests when it expects F '
                                                            'not to survive. This is a different question from the '
                                                            'one above: it is decided before transmission, from '
                                                            'ego-side cues and the channel estimate only, and it '
                                                            'costs L instead of F rather than falling back after '
                                                            'the fact'},
        'command': 'python projects/ca_tosg_p2/protocol/message_regime.py'}


def markdown(m):
    b1, b3, b4 = m['B1_provenance'], m['B3_statement'], m['B4_recorded_survival']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/message_regime.py -- do not edit by hand -->',
         '# The message all-or-nothing accounting, costed (P2-R10 B)', '', f"**{m['what']}.**", '',
         '## B-1 Do P1\'s message products describe the current model and payload?', '',
         f"`wp5_message_validate.json`: {b1['wp5_message']['frames']:,} frames, "
         f"**N_cw = {b1['wp5_message']['n_cw']:,}**, {b1['wp5_message']['n_replays']} replays. The payload chain "
         f"records {b1['chain_n_cw']:,} codewords for {b1['chain_elements']:,} elements — "
         f"**{'they match' if b1['n_cw_matches_current_payload'] else 'THEY DO NOT MATCH'}**.", '',
         f"What it contains: {b1['what_it_contains']}. The product's own note on the rate 0.001 entry: "
         f"\"{b1['note_from_the_product']}\".", '',
         '| file | commit | sha256 |', '|---|---|---|']
    for k, v in b1['files'].items():
        L.append(f"| `{k}` | {v['commit'][:9]} | `{v['sha256'][:16]}…` |")
    c = m['constructed_column']
    L += ['', f"**One column is constructed, not read.** `{c['name']}` = {c['formula']} with N_cw = {c['n_cw']:,}, "
          f"by {c['rule_source']}. {c['status']}.", '',
          '## B-2 The 22 cells, three accountings', '',
          '| channel | SNR | p_cw | q(message survives) | eff_E | eff_L | F: message | F: partial | F: packet | '
          'message − E | within 1e-3 of E |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|']
    for r in m['B2_cells']:
        L.append(f"| {r['channel']} | {r['snr_db']} | {r['p_cw']:.5f} | {r['q_message_survives']:.3g} | "
                 f"{r['eff_E']:.5f} | {r['eff_L']:.5f} | {r['eff_F_message']:.5f} | {r['eff_F_partial']:.5f} | "
                 f"{r['eff_F_packet']:.5f} | {r['message_minus_E']:+.5f} | "
                 f"{'**yes**' if r['message_within_1e-3_of_E'] else 'no'} |")
    L += ['', '## B-3 The statement', '',
          f"* Under the message accounting F is more than ego-only in **{b3['n_cells_usable']} of "
          f"{b3['n_cells_total']} cells**"
          + (': ' + ', '.join(b3['cells_where_F_is_more_than_E_under_message']) if b3['cells_where_F_is_more_than_E_under_message'] else '')
          + '.',
          f"* Rayleigh cells where the message-accounted F beats L: "
          + (', '.join(b3['rayleigh_cells_where_message_F_beats_L']) if b3['rayleigh_cells_where_message_F_beats_L'] else '**none**') + '.',
          f"* AWGN cells where the message-accounted F beats L: "
          + (', '.join(b3['awgn_cells_where_message_F_beats_L']) if b3['awgn_cells_where_message_F_beats_L'] else '**none**') + '.',
          f"* For contrast, Rayleigh cells where the partial-recovery F beats L: "
          + (', '.join(b3['rayleigh_cells_where_partial_F_beats_L']) if b3['rayleigh_cells_where_partial_F_beats_L'] else '**none**') + '.',
          '', '## B-4 Recorded survival probability', '',
          f"At p = {b4['p']}, q = **{b4['q']:.6g}** — an expectation of {b4['expected_frames_surviving_of_1980']:.6g} "
          f"surviving frames out of 1,980. Source: {b4['source']}.", '',
          '## B-5 Left open', '', f"* **The accounting is not presupposed.** {m['B5_open']['ruling']}.",
          f"* **Fallback after a failed send.** {m['B5_open']['fallback_after_a_failed_send']}.",
          f"* **Deciding to request L before sending.** {m['B5_open']['deciding_to_request_L_before_sending']}."]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('message regime:', 'reproduced' if ok else 'FAIL -- not what the generator writes'); return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md); print(md); return 0


if __name__ == '__main__':
    sys.exit(main())
