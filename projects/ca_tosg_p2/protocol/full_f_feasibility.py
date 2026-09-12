#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R9 items 3-5 — can the COMPLETE F message be sent, and in what time? CPU only, no model run.

Item 3: the payload chain re-derived step by step from the code, checked against the recorded product,
        with QAM data symbols and OFDM symbols kept apart -- they are not the same unit, and 3.14175
        Msym is the first, not the second.
Item 4: for every link configuration already listed in link_scenarios.json, the TIME to send the
        complete F and to send L, whether it finishes inside a 100 ms frame period, and whether a
        continuous 10 Hz stream backlogs. Two arms: an idealised resource upper bound, and an arm with
        the overheads this repository can source.
Item 5: the verdict, and if nothing carries F, which of message size, frame period or resource limit
        the deficit sits in.

No bandwidth is invented to make F fit: the configuration list is the one already committed.

    python projects/ca_tosg_p2/protocol/full_f_feasibility.py [--check]
"""
from __future__ import annotations
import argparse, json, math, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v2_payload_chain as pcm                                                    # noqa: E402

LINKS = os.path.join(HERE, 'link_scenarios.json')
CHAIN = os.path.join(ROOT, 'results', 'v2', 'payload_chain.json')
PROBE = os.path.join(ROOT, 'results', 'manifests', 'P4B_PROBE_pointpillar_compression.json')
WP34 = os.path.join(ROOT, 'results', 'v2', 'wp34_e_l_validate.csv')
OUT_JSON = os.path.join(HERE, 'full_f_feasibility.json')
OUT_MD = os.path.join(HERE, 'full_f_feasibility.md')

FRAME_PERIOD_S = 0.1                       # LiDAR at 10 Hz, as in the protocol
BD_DATA_TONES, BD_SYMBOL_S = 108, 8e-6     # link_scenarios sources S1-S4, S11
BD_MIDAMBLE_M = (4, 20)                    # sourced periodicities, extremes of {4, 8, 10, 16, 20}


def chain_steps():
    """Item 3: every step of the chain, recomputed here and checked against the recorded product."""
    probe = json.load(open(PROBE))
    rec = json.load(open(CHAIN))['F']
    elements = int(probe['totals_per_cav']['transmitted_elements'])
    info_bits = elements * pcm.W_BITS
    n_full, tail, sizes = pcm.packetise(info_bits)
    packets = len(sizes)
    header_bits = pcm.H_BITS * packets
    n_cw = pcm.codewords(sizes)
    coded_bits = n_cw * pcm.N_LDPC
    qam_symbols = coded_bits / pcm.BITS_PER_SYM
    msym = qam_symbols / 1e6
    steps = [
        ('bottleneck elements', elements, 'forward-hook probe of the frozen checkpoint'),
        ('quantisation width (bits/element)', pcm.W_BITS, 'symmetric int8, per-branch pre-shared scales'),
        ('information bits', info_bits, 'elements x width'),
        ('full packets', n_full, f'payload {pcm.P_BITS:,} bits each'),
        ('tail packet payload bits', tail, 'the tail packet is not padded to a full payload'),
        ('packets', packets, 'full packets + tail'),
        ('header bits', header_bits, f'{pcm.H_BITS} bits per packet'),
        ('LDPC codewords', n_cw, f'rate 1/2, K = {pcm.K}, n = {pcm.N_LDPC}, per packet, padded'),
        ('coded bits', coded_bits, 'codewords x n'),
        ('QAM data symbols', int(qam_symbols), f'coded bits / log2({pcm.M_QAM})'),
        ('Msym (QAM data symbols)', msym, 'the unit the protocol calls a channel use'),
    ]
    agree = {'elements': elements == rec['elements'], 'info_bits': info_bits == rec['info_bits'],
             'packets': packets == rec['packets'], 'header_bits': header_bits == rec['header_bits'],
             'n_cw': n_cw == rec['n_cw'], 'msym': abs(msym - rec['msym']) < 1e-12}
    if not all(agree.values()):
        raise SystemExit(f'CHAIN: re-derivation disagrees with the recorded product: {agree}')
    return {'steps': [{'step': a, 'value': b, 'basis': c} for a, b, c in steps],
            'qam_symbols': int(qam_symbols), 'msym': msym, 'n_cw': n_cw, 'coded_bits': coded_bits,
            'verified_against_product': agree,
            'qam_vs_ofdm': 'A QAM data symbol occupies one data subcarrier of one OFDM symbol. An OFDM '
                           'symbol carries as many QAM symbols as it has data subcarriers, so the two '
                           'counts differ by that factor and only the OFDM count has a duration. '
                           '3.14175 Msym is the QAM count; it is not a symbol time and not an OFDM count'}


def bd_rows(qam):
    """802.11bd 20 MHz: OFDM symbols are the unit with a duration."""
    out = []
    n_ofdm = math.ceil(qam / BD_DATA_TONES)
    base_t = n_ofdm * BD_SYMBOL_S
    out.append({'arm': 'idealised upper bound', 'r_sym': BD_DATA_TONES / BD_SYMBOL_S,
                'ofdm_symbols_for_F': n_ofdm, 'time_F_s': base_t,
                'overhead': 'none: every OFDM symbol carries data, continuously, one link'})
    for m in BD_MIDAMBLE_M:
        f = (m + 1) / m               # one NGV-LTF midamble symbol after every m data symbols
        out.append({'arm': f'with midambles every {m} data symbols', 'r_sym': (BD_DATA_TONES / BD_SYMBOL_S) / f,
                    'ofdm_symbols_for_F': math.ceil(n_ofdm * f), 'time_F_s': base_t * f,
                    'overhead': 'midambles only, one NGV-LTF symbol each (assumption); no preamble, no MAC, '
                                'no contention -- still an upper bound'})
    return out


def build():
    ch = chain_steps()
    qam = ch['qam_symbols']
    links = json.load(open(LINKS))
    L = pd.read_csv(WP34, usecols=['B_L_msym']).B_L_msym.to_numpy() * 1e6        # QAM symbols per frame
    L_max, L_med = float(L.max()), float(np.median(L))

    rows = []
    for r in bd_rows(qam):
        rows.append({'technology': 'IEEE 802.11bd', 'configuration': '20 MHz', **r})
    seen = set()
    for r in links['rows']:
        if r['technology'] != 'NR sidelink':
            continue
        key = (r['configuration'], r['capacity_variant'])
        if key in seen:
            continue
        seen.add(key)
        arm = ('idealised upper bound' if r['capacity_variant'] == 'zero-overhead upper bound'
               else 'with mandatory minimum PHY overhead')
        rows.append({'technology': 'NR sidelink', 'configuration': r['configuration'], 'arm': arm,
                     'r_sym': r['R_sym_per_s'], 'time_F_s': qam / r['R_sym_per_s'],
                     'slots_for_F': math.ceil(qam / r['R_sym_per_s'] * r.get('slots_per_s', 0)) if r.get('slots_per_s') else None,
                     'overhead': ('none: whole carrier to one link, every data resource element, continuously'
                                  if arm == 'idealised upper bound' else
                                  'smallest PSCCH (2 symbols x 10 PRB), fewest PSSCH DM-RS (2 symbols, comb), '
                                  'AGC and guard excluded; no PSFCH, no resource-pool sharing, no MAC')})
    for r in rows:
        t = r['time_F_s']
        r['time_F_ms'] = t * 1e3
        r['fits_100ms'] = bool(t <= FRAME_PERIOD_S)
        r['utilisation_at_10hz'] = t / FRAME_PERIOD_S
        r['backlogs_at_10hz'] = bool(t > FRAME_PERIOD_S)
        r['backlog_ms_added_per_frame'] = max(0.0, t * 1e3 - FRAME_PERIOD_S * 1e3)
        r['max_F_rate_hz'] = 1.0 / t
        r['time_L_max_ms'] = L_max / r['r_sym'] * 1e3
        r['time_L_median_ms'] = L_med / r['r_sym'] * 1e3
        r['L_fits_100ms'] = bool(L_max / r['r_sym'] <= FRAME_PERIOD_S)
        r['L_utilisation_at_10hz_max'] = (L_max / r['r_sym']) / FRAME_PERIOD_S
        r['shortfall_factor_F'] = t / FRAME_PERIOD_S

    best = min(rows, key=lambda x: x['time_F_ms'])
    feasible = [r for r in rows if r['fits_100ms']]
    return {
        'schema': 'catosg-p2-full-f-feasibility/1',
        'question': 'can the complete F message (all 55 blocks) be delivered inside one 100 ms frame period, '
                    'and does a continuous 10 Hz stream backlog?',
        'subject': 'F = the complete bottleneck of the frozen checkpoint, existing compression and int8 '
                   'quantisation unchanged; L = the object-level message; E = ego-only. Nothing about F was '
                   'changed for this audit',
        'frame_period_s': FRAME_PERIOD_S,
        'chain': ch,
        'L_reference_qam_symbols': {'max': L_max, 'median': L_med, 'frames': int(len(L))},
        'rows': rows,
        'verdict': {'configurations_examined': len(rows), 'configurations_that_fit': len(feasible),
                    'best_row': {k: best[k] for k in ('technology', 'configuration', 'arm', 'time_F_ms',
                                                      'utilisation_at_10hz', 'max_F_rate_hz')},
                    'candidates_for_a_degradation_experiment': [
                        {k: r[k] for k in ('technology', 'configuration', 'arm', 'time_F_ms')} for r in feasible],
                    'bottleneck': ('message size: the complete F needs '
                                   f'{qam / 1e6:.5f} Msym, while the widest configuration examined delivers at most '
                                   f'{best["r_sym"] * FRAME_PERIOD_S / 1e6:.5f} Msym in a 100 ms period even with no '
                                   'overhead at all. The deficit at the best row is a factor of '
                                   f'{best["shortfall_factor_F"]:.2f}, and every configuration with stated overhead '
                                   'is worse. The frame period and the resource grid are what they are; what does '
                                   'not fit is the message'),
                    'not_proposed': 'no sparse F, no transmission spread across frames and no lower sending rate '
                                    'is proposed here; this audit reports feasibility only'},
        'assumptions_not_matching_a_standard_link': [
            'the P1 chain fixes a rate-1/2 LDPC with K = 500 and n = 1000; that is not the code either standard '
            'specifies, and no standard code was substituted, so the codeword count is not a standard block '
            'segmentation',
            'modulation is fixed at 16-QAM regardless of channel quality; neither standard\'s MCS set is used',
            'one P1 channel use is mapped to one data resource element of the standard grid',
            'the 320-bit header models IP/UDP/application overhead only; no MAC framing of either standard is '
            'charged',
            'the idealised arm gives the whole carrier to one link, continuously, with no preamble, contention, '
            'queueing or retransmission',
            'the 802.11bd tone count and symbol period come from patent text (IEEE 802.11bd-2022 is paywalled); '
            'the midamble arm assumes one NGV-LTF symbol per midamble',
            'n47 bandwidths and subcarrier spacings are verified against TS 38.101-1 V17.0.0 Table 5.3.5-1'],
        'command': 'python projects/ca_tosg_p2/protocol/full_f_feasibility.py'}


def markdown(m):
    ch, v = m['chain'], m['verdict']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/full_f_feasibility.py -- do not edit by hand -->',
         '# Can the complete F be sent? (P2-R9 items 3-5)', '', f"**Question.** {m['question']}", '',
         f"**Subject.** {m['subject']}.", '',
         '## 3 The payload chain, re-derived and checked', '', '| step | value | basis |', '|---|---:|---|']
    for s in ch['steps']:
        val = f"{s['value']:,}" if isinstance(s['value'], int) else (f"{s['value']:.5f}" if isinstance(s['value'], float) else s['value'])
        L.append(f"| {s['step']} | {val} | {s['basis']} |")
    L += ['', f"Every step agrees with the recorded product: {ch['verified_against_product']}.", '',
          f"**QAM symbols are not OFDM symbols.** {ch['qam_vs_ofdm']}.", '',
          '## 4 Time to send, and backlog at 10 Hz', '',
          f"L is shown at its largest frame ({m['L_reference_qam_symbols']['max']:,.0f} QAM symbols) and its median "
          f"({m['L_reference_qam_symbols']['median']:,.0f}).", '',
          '| technology | configuration | arm | R_sym (Msym/s) | **F: time** | fits 100 ms | utilisation at 10 Hz '
          '| backlog added per frame | max F rate | L: max / median | L fits |',
          '|---|---|---|---:|---:|:---:|---:|---:|---:|---:|:---:|']
    for r in m['rows']:
        L.append(f"| {r['technology']} | {r['configuration']} | {r['arm']} | {r['r_sym'] / 1e6:.3f} "
                 f"| **{r['time_F_ms']:.1f} ms** | {'yes' if r['fits_100ms'] else '**no**'} "
                 f"| {r['utilisation_at_10hz']:.2f}× | {r['backlog_ms_added_per_frame']:.1f} ms "
                 f"| {r['max_F_rate_hz']:.2f} Hz | {r['time_L_max_ms']:.2f} / {r['time_L_median_ms']:.2f} ms "
                 f"| {'yes' if r['L_fits_100ms'] else 'no'} |")
    b = v['best_row']
    L += ['', '## 5 Verdict', '',
          f"**{v['configurations_that_fit']} of {v['configurations_examined']} configurations can deliver the "
          f"complete F inside 100 ms.**", '',
          f"The best row is {b['technology']} {b['configuration']}, {b['arm']}: {b['time_F_ms']:.1f} ms, "
          f"{b['utilisation_at_10hz']:.2f}× the frame period, so a 10 Hz stream of complete F messages backlogs "
          f"without bound; the highest rate it could sustain is {b['max_F_rate_hz']:.2f} Hz. L finishes in about a "
          f"millisecond everywhere and never backlogs.", '',
          f"**Candidates for a degradation experiment:** "
          + ('none' if not v['candidates_for_a_degradation_experiment'] else
             ', '.join(f"{c['technology']} {c['configuration']} ({c['arm']})" for c in v['candidates_for_a_degradation_experiment']))
          + '.', '', f"**Where the deficit sits.** {v['bottleneck']}.", '', f"*{v['not_proposed']}.*", '',
          '## Assumptions that do not match a standard link', '']
    L += [f"* {a}." for a in m['assumptions_not_matching_a_standard_link']]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('full F feasibility:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md); print(md); return 0


if __name__ == '__main__':
    sys.exit(main())
