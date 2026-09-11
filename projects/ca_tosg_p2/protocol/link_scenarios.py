#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R1 C-6, revised under P2-R3 A-2, B and D-1 — link scenarios, computed before any scenario is
chosen. Zero GPU; no perception output is read.

For each standard configuration this computes R_sym, the data-carrying channel uses per second, and for
two candidate windows D_comm asks whether N_sym(a) <= R_sym * D_comm holds for

  * F as P1 transmits it (one constant payload);
  * F with branch 2 compressed at branch 1's ratio -- a REFERENCE column only (P2-R3 B-3), never a
    design basis;
  * L on every validate frame, as observed;
  * L at the only structural bound the detection pipeline has (P2-R3 D-1).

N_sym is P1's billing chain, reused and verified by build_reuse_manifest.py; one P1 channel use is
mapped to one data resource element. That mapping is an assumption and is recorded as one.

WHAT IS AND IS NOT A CHOICE HERE (no back-selection of parameters)
  * NR sidelink rows are EXHAUSTIVE over the n47 channel bandwidths crossed with every FR1 SCS; all
    twelve combinations are marked valid for n47 in TS 38.101-1 Table 5.3.5-1.
  * IEEE 802.11bd is computed at 20 MHz, the configuration the instruction names.
  * D_comm takes one LiDAR period and half of it, as instructed.
  * The PRIMARY capacity is a ZERO-OVERHEAD UPPER BOUND: the whole channel, every data resource
    element, continuously, for one link. Anything real lowers it.

Every parameter carries its source, quoted. Where a value is derived, the derivation is written out.

    python projects/ca_tosg_p2/protocol/link_scenarios.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import v2_payload_chain as pcm                                                    # noqa: E402

OUT_JSON = os.path.join(HERE, 'link_scenarios.json')
OUT_MD = os.path.join(HERE, 'link_scenarios.md')
PROBE = os.path.join(ROOT, 'results/manifests/P4B_PROBE_pointpillar_compression.json')
CHAIN = os.path.join(ROOT, 'results/v2/payload_chain.json')
WP34 = os.path.join(ROOT, 'results/v2/wp34_e_l_validate.csv')
POSTPROC = os.path.join(os.path.dirname(ROOT), 'OpenCOOD', 'opencood', 'data_utils', 'post_processor',
                        'voxel_postprocessor.py')

LIDAR_HZ = 10.0
D_COMM_S = {'one LiDAR period': 1.0 / LIDAR_HZ, 'half LiDAR period': 0.5 / LIDAR_HZ}

SOURCES = {
    'S1': 'US 11,516,635 B2 and US 11,432,119 B2 (NGV, Google Patents text): "encode the PPDU for '
          'transmission in a 20 MHz channel of 128 sub-carriers spaced apart by 156.25 kHz."',
    'S2': 'US 12,068,986 B2 (NGV, Google Patents text as returned by fetch): "a tone plan for 20 MHz may '
          'be configured by applying a 40 MHz tone plan of the 802.11ac standard"; "a signal may be '
          'transmitted by using 114 tones"; "[-58:-2, 2:58]"; "6 pilot tones, which is the same as the '
          'tone plan for the 40 MHz band"; for the one-DC-tone variant "[-58:-1, 1:58]", "108 data tones '
          'and 8 pilot tones". To be checked against the patent PDF before lock.',
    'S3': 'US 9,246,649 B2 (802.11ac, Google Patents text): "a 40 MHz signal ... for a VHT-SIG-B uses '
          '114 tones, including 108 data tones and six pilot tones ... with three DC tones".',
    'S4': 'US 11,432,119 B2: "encode the PPDU for transmission in a 10 MHz channel of 64 sub-carriers '
          'spaced apart by 156.25 kHz with an orthogonal frequency division multiplexing (OFDM) symbol '
          'period of 8 micro-seconds (usec)."',
    'S5': 'M. Harounabadi et al., "V2X in 3GPP Standardization: NR Sidelink in Rel-16 and Beyond", IEEE '
          'Commun. Standards Mag., 2021 (arXiv:2104.11135), sec. 5.1.3: "two frequency bands are defined '
          'as the operating bands of V2X on the PC5 interface [8]: 5.9 GHz band (n47), 2.5 GHz band '
          '(n38). The supported channel bandwidth in both frequency bands are 10, 20, 30, and 40 MHz."',
    'S6': 'P. Liu et al., "5G New Radio Sidelink Link-Level Simulator and Performance Analysis", MSWiM '
          '2022 (NIST pub 935091): "scs can only be 15 kHz, 30 kHz, or 60 kHz in Frequency Range 1 '
          '(FR1)"; the first symbol "is used for AGC ... and it is a duplication of the following OFDM '
          'symbol"; "In an SL slot without PSFCH, the OFDM symbol with index sl_StartSymbol + '
          'sl_LengthSymbols - 1 functions as a guard symbol"; "the PSCCH can occupy 10, 12, 15, 20, or 25 '
          'Physical Resource Blocks" over "two or three OFDM symbols" (the source prints PSSCH; the '
          'parameter it describes is sl_TimeResourcePSCCH); "the number of OFDM symbols that contain '
          'DM-RS can be 2, 3, or 4"; PSSCH DM-RS "are assigned to the REs with k = 2m".',
    'S7': '3GPP TS 38.101-1 V17.0.0 (2020-12), Table 5.3.2-1 "Maximum transmission bandwidth '
          'configuration NRB", read from the public mirror panel.castle.cloud/view_spec/38101-1-h00/pdf/: '
          'SCS 15 kHz -- 10 MHz 52, 20 MHz 106, 30 MHz 160, 40 MHz 216; 30 kHz -- 24, 51, 78, 106; '
          '60 kHz -- 11, 24, 38, 51.',
    'S8': 'G. Naik, B. Choudhury, J.-M. Park, "IEEE 802.11bd & 5G NR V2X", arXiv:1903.08391: "NR defines '
          'the duration corresponding to 14 OFDM symbols as one slot, while a sub-frame has a fixed '
          'duration of 1 msec."',
    'S9': 'MathWorks, "NR V2X Sidelink PSCCH and PSSCH Throughput": reference measurement channel '
          'R.PSSCH.2-1.1 from "TS 38.101-4 Section 11 ... A.6, SL reference measurements channels", at '
          '20 MHz and 30 kHz. Cited only to show 20 MHz / 30 kHz is a 3GPP reference configuration.',
    'S10': '3GPP TS 38.101-1 V17.0.0 (same mirror): Table 5.2E.1-1 "V2X operating bands in FR1" lists n47 '
           'with sidelink transmission and reception at 5855 MHz - 5925 MHz, HD, PC5; Table 5.3.5-1 '
           '"Channel bandwidths for each NR band" marks four channel bandwidths "Yes10" for n47 under each '
           'of SCS 15, 30 and 60 kHz, with NOTE 10: "These UE channel bandwidths are applicable to '
           'sidelink operation."; Table 6.2E.3.1-1 lists channel bandwidths "10, 20, 30, 40" MHz for NS_01 '
           'on the Table 5.2E.1-1 bands. Text extraction does not keep column positions, so the four n47 '
           'bandwidths are identified through Table 6.2E.3.1-1 and [S5].',
    'S11': 'arXiv:2203.17114, "A Methodology for Abstracting the Physical Layer of Direct V2X '
           'Communications Technologies" (public secondary source): IEEE 802.11p uses "10 MHz bandwidth", '
           '"52 subcarriers with subcarrier spacing of 156.25 kHz (4 of them used as pilot)", OFDM symbol '
           'duration "8 μs". It covers 802.11p at 10 MHz, not 802.11bd at 20 MHz.',
    'S12': 'results/manifests/P4B_PROBE_pointpillar_compression.json (forward-hook probe of the P1 '
           'checkpoint) and docs/unified_branch_protocol_v2.md §3.2 (branch table) and §3.3 (int8, '
           'per-branch pre-shared scales).',
    'S13': 'OpenCOOD opencood/data_utils/post_processor/voxel_postprocessor.py, post_process: score '
           'threshold, large-box and abnormal-z removal, rotated NMS, range mask -- no limit on the number '
           'of predicted boxes. postprocess.max_num sizes the ground-truth array only '
           '(base_postprocessor.py). Anchor grid and anchor count from the checkpoint config.',
}

BD20 = {'tones_used': 114, 'pilot_tones': 6, 'subcarrier_spacing_hz': 156_250.0, 'symbol_period_s': 8e-6}
BD20['data_tones'] = BD20['tones_used'] - BD20['pilot_tones']
BD20_DERIVATION = (
    'Data tones: 114 tones used minus 6 pilots = 108 [S2]; the one-DC-tone variant of the same source '
    'states "108 data tones and 8 pilot tones" directly [S2]; and 108 is the 802.11ac 40 MHz data-tone '
    'count [S3], as it must be if the 20 MHz NGV plan is the 40 MHz VHT plan [S2]. The two variants '
    'agree, so there is one value, not two. Symbol period: the FFT period is 1/156.25 kHz = 6.4 us at '
    '20 MHz as at 10 MHz because the spacing is the same [S1, S4]; the guard interval is assumed equal, '
    'giving 8 us [S4]. At that spacing the 8 us symbol is corroborated by a public secondary source for '
    '802.11p [S11]. No public secondary source was located for the 20 MHz tone count itself, and '
    'IEEE 802.11bd-2022 is paywalled and was not consulted; the value rests on patent text.')

NR_BW_MHZ = (10, 20, 30, 40)                       # S5, S10
NR_SCS_KHZ = (15, 30, 60)                          # S6, S10
NR_NRB = {                                         # S7 (primary)
    (10, 15): 52, (10, 30): 24, (10, 60): 11,
    (20, 15): 106, (20, 30): 51, (20, 60): 24,
    (30, 15): 160, (30, 30): 78, (30, 60): 38,
    (40, 15): 216, (40, 30): 106, (40, 60): 51,
}
NR_SYMBOLS_PER_SLOT = 14                           # S8, normal cyclic prefix
NR_SUBCARRIERS_PER_RB = 12
NR_AGC_SYMBOLS, NR_GUARD_SYMBOLS = 1, 1            # S6, slot without PSFCH
NR_MIN_PSCCH_SYMBOLS, NR_MIN_PSCCH_PRB = 2, 10     # S6, smallest allowed
NR_MIN_DMRS_SYMBOLS = 2                            # S6, fewest allowed
NR_DMRS_RE_FRACTION = 0.5                          # S6, DM-RS on k = 2m
NR_REFERENCE_CONFIG = (20, 30)                     # S9

CONFIGS = [('IEEE 802.11bd', '20 MHz', None)] + \
          [('NR sidelink', f'{bw} MHz / {scs} kHz', (bw, scs)) for bw in NR_BW_MHZ for scs in NR_SCS_KHZ]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def msym_for_bits(bits):
    if bits <= 0:
        return 0.0
    _, _, sizes = pcm.packetise(int(bits))
    return pcm.msym(pcm.codewords(sizes))


def r_sym_nr(bw, scs, overhead):
    mu = {15: 0, 30: 1, 60: 2}[scs]
    slots_per_s = 1000 * 2 ** mu
    n_rb = NR_NRB[(bw, scs)]
    n_sc = n_rb * NR_SUBCARRIERS_PER_RB
    sym = NR_SYMBOLS_PER_SLOT - NR_AGC_SYMBOLS - NR_GUARD_SYMBOLS
    re = n_sc * sym
    if overhead:
        re -= NR_MIN_PSCCH_SYMBOLS * NR_MIN_PSCCH_PRB * NR_SUBCARRIERS_PER_RB
        re -= NR_MIN_DMRS_SYMBOLS * int(n_sc * NR_DMRS_RE_FRACTION)
    return re * slots_per_s, {'n_rb': n_rb, 'slots_per_s': slots_per_s}


def facts():
    """P2-R3 A-2 and B-3 inputs, read from the probe, never typed."""
    probe = json.load(open(PROBE))
    b = probe['branches']
    tx = [x['transmitted_elements_per_cav'] for x in b]
    pre_total = probe['totals_per_cav']['pre_compression_elements']
    tx_total = probe['totals_per_cav']['transmitted_elements']
    unc = [x for x in b if not x['compressed']]
    if len(unc) != 1:
        raise SystemExit('LINK SCENARIOS: expected exactly one uncompressed branch')
    ratio_b1 = b[1]['ratio']
    if unc[0]['transmitted_elements_per_cav'] % ratio_b1:
        raise SystemExit('LINK SCENARIOS: branch 2 is not divisible by branch 1 ratio')
    b2c_elements = tx[0] + tx[1] + int(unc[0]['transmitted_elements_per_cav'] // ratio_b1)
    cfg = yaml.load(open(os.path.join(probe['ckpt_dir'], 'config.yaml')), Loader=yaml.UnsafeLoader)  # trusted local OpenCOOD checkpoint config; numpy-tagged values
    ups = cfg['model']['args']['base_bev_backbone']['upsample_strides']
    head = [b[0]['pre_compression_shape_per_cav'][1] * ups[0], b[0]['pre_compression_shape_per_cav'][2] * ups[0]]
    anchors = head[0] * head[1] * int(cfg['model']['args']['anchor_num'])
    return {'pre_compression_elements': pre_total, 'transmitted_elements': tx_total,
            'compression_ratio': pre_total / tx_total, 'w_bits': pcm.W_BITS,
            'branch2_elements': unc[0]['transmitted_elements_per_cav'],
            'branch2_share_of_transmitted': unc[0]['transmitted_elements_per_cav'] / tx_total,
            'branch1_ratio': ratio_b1, 'F_b2c_elements': b2c_elements,
            'F_b2c_msym': msym_for_bits(b2c_elements * pcm.W_BITS),
            'head_grid': head, 'anchor_num': int(cfg['model']['args']['anchor_num']),
            'anchor_count': anchors, 'postprocess_max_num_role': 'ground-truth array size only [S13]',
            'probe_sha256': sha(PROBE), 'postprocessor_sha256': sha(POSTPROC)}


def build():
    pc = json.load(open(CHAIN))
    B_F = float(pc['F']['msym'])
    fx = facts()
    if abs(msym_for_bits(fx['transmitted_elements'] * pcm.W_BITS) - B_F) > 1e-12:
        raise SystemExit('LINK SCENARIOS: the probe element total does not reproduce B_F')
    w = pd.read_csv(WP34, usecols=['n_box_collab', 'B_L_msym'])
    B_L = w.B_L_msym.to_numpy()
    L_obs_max_boxes = int(w.n_box_collab.max())
    L_anchor_msym = pcm.l_chain(fx['anchor_count'])['msym']
    rows = []
    for tech, label, key in CONFIGS:
        variants = [('zero-overhead upper bound', False)]
        if key is not None:
            variants.append(('minus mandatory minimum PHY overhead', True))
        for vname, oh in variants:
            if key is None:
                r = BD20['data_tones'] / BD20['symbol_period_s']
                detail = {'data_tones': BD20['data_tones'], 'symbol_period_s': BD20['symbol_period_s']}
                flag = '802.11bd values from patent text; standard not consulted (paywalled); see derivation'
            else:
                r, detail = r_sym_nr(*key, oh)
                flag = ('3GPP reference configuration [S9]; ' if key == NR_REFERENCE_CONFIG else '') + \
                       'n47 bandwidth and SCS verified [S10]'
            for dname, d in D_COMM_S.items():
                cap = r * d / 1e6
                rows.append({
                    'technology': tech, 'configuration': label, 'capacity_variant': vname,
                    'D_comm_name': dname, 'D_comm_ms': d * 1e3, 'R_sym_per_s': r, 'capacity_msym': cap,
                    **detail,
                    'F_B_msym': B_F, 'F_reachable': bool(B_F <= cap), 'F_over_capacity': B_F / cap,
                    'F_b2c_msym': fx['F_b2c_msym'], 'F_b2c_reachable': bool(fx['F_b2c_msym'] <= cap),
                    'F_b2c_over_capacity': fx['F_b2c_msym'] / cap,
                    'L_obs_max_B_msym': float(B_L.max()),
                    'L_obs_frames_reachable_fraction': float((B_L <= cap).mean()),
                    'L_anchor_bound_msym': L_anchor_msym,
                    'L_anchor_bound_reachable': bool(L_anchor_msym <= cap), 'flag': flag})
    twenty = [r for r in rows if r['configuration'].startswith('20 MHz')
              and r['capacity_variant'] == 'zero-overhead upper bound' and r['D_comm_ms'] == 100.0]
    return {
        'schema': 'catosg-p2-link-scenarios/2',
        'question': 'N_sym(a) <= R_sym * D_comm',
        'N_sym_source': 'P1 payload chain, verified by build_reuse_manifest.py; one P1 channel use '
                        'mapped to one data resource element (assumption)',
        'configuration_rule': 'NR: every n47 bandwidth x every FR1 SCS (all valid for n47, S10). '
                              '802.11bd: 20 MHz, as instructed. D_comm: one and half a 10 Hz LiDAR '
                              'period. No configuration was added, removed or reordered after computing.',
        'capacity_rule': 'primary = zero-overhead upper bound (whole channel, one link, continuous); NR also '
                         'shown minus the mandatory minimum PHY overhead',
        'excluded_from_upper_bound': ['802.11bd preamble and midambles', 'MAC headers and framing',
                                      'channel access contention and backoff', 'queueing',
                                      'the request itself', 'retransmission',
                                      'NR PSCCH, DM-RS, SCI2 and PSFCH (upper-bound rows)',
                                      'NR resource-pool sharing with other UEs'],
        'F_facts': fx, 'twenty_mhz_100ms_upper_bound_F_over_capacity':
            [min(r['F_over_capacity'] for r in twenty), max(r['F_over_capacity'] for r in twenty)],
        'L_bound': {'pipeline_cap_on_predicted_boxes': None,
                    'observed_validate_max_boxes': L_obs_max_boxes,
                    'observed_validate_max_B_L_msym': float(B_L.max()),
                    'anchor_count_bound_boxes': fx['anchor_count'], 'anchor_count_bound_msym': L_anchor_msym,
                    'anchor_bound_reachable_in_every_row': all(r['L_anchor_bound_reachable'] for r in rows)},
        'bd20_derivation': BD20_DERIVATION, 'sources': SOURCES, 'rows': rows,
        'L_payload_frames': int(len(B_L)),
        'command': 'python projects/ca_tosg_p2/protocol/link_scenarios.py'}


def markdown(m):
    fx, lb = m['F_facts'], m['L_bound']
    lo, hi = m['twenty_mhz_100ms_upper_bound_F_over_capacity']
    n_f = sum(r['F_reachable'] for r in m['rows'])
    best = min(m['rows'], key=lambda r: r['F_over_capacity'])
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/link_scenarios.py -- do not edit by hand -->',
         '# P2 link scenarios — computed before any scenario is chosen', '',
         f"**Question.** {m['question']}. **N_sym:** {m['N_sym_source']}.", '',
         f"**Configurations.** {m['configuration_rule']}", '',
         f"**Capacity.** {m['capacity_rule']}. Excluded from the upper bound: "
         + '; '.join(m['excluded_from_upper_bound']) + '.', '',
         '## What F already is (P2-R3 A-2) [S12]', '',
         f"* In-network compression is already applied: {fx['pre_compression_elements']:,} elements before "
         f"compression, {fx['transmitted_elements']:,} transmitted ({fx['compression_ratio']:.2f}×).",
         f"* Each transmitted element is quantised to {fx['w_bits']} bits.",
         f"* Branch 2 is not compressed: {fx['branch2_elements']:,} elements, "
         f"{fx['branch2_share_of_transmitted'] * 100:.1f} % of what is transmitted.",
         f"* On the 20 MHz rows at D_comm = 100 ms, F needs {lo:.2f}–{hi:.2f}× the zero-overhead upper bound; "
         'a real link, with sharing and overhead, needs more.', '',
         '## Result', '',
         f"F is {m['rows'][0]['F_B_msym']:.5f} Msym on every frame and is reachable in **{n_f} of "
         f"{len(m['rows'])} rows**. Closest row: {best['technology']} {best['configuration']}, "
         f"{best['capacity_variant']}, {best['D_comm_ms']:.0f} ms, at {best['F_over_capacity']:.3f}× capacity.", '',
         f"**Reference only, not a design basis (P2-R3 B-3):** with branch 2 compressed at branch 1's ratio "
         f"(1/{fx['branch1_ratio']:g}), F would be {fx['F_b2c_elements']:,} elements = {fx['F_b2c_msym']:.5f} "
         f"Msym; its ratio to capacity is the `F b2c / cap` column.", '',
         '## L bound (P2-R3 D-1) [S13]', '',
         '* **The detection pipeline has no cap on the number of predicted boxes.** `postprocess.max_num` '
         'sizes the ground-truth array, not the prediction list.',
         f"* The only structural bound is the anchor count: {lb['anchor_count_bound_boxes']:,} anchors "
         f"(head grid {fx['head_grid'][0]} × {fx['head_grid'][1]} × {fx['anchor_num']}), "
         f"= {lb['anchor_count_bound_msym']:.5f} Msym — reachable in every row: "
         f"**{'yes' if lb['anchor_bound_reachable_in_every_row'] else 'no'}**.",
         f"* Observed on validate (informative, not a bound): at most {lb['observed_validate_max_boxes']} "
         f"collaborator boxes, {lb['observed_validate_max_B_L_msym']:.5f} Msym.", '',
         '| technology | configuration | capacity | D_comm | R_sym (Msym/s) | capacity (Msym) | F reachable '
         '| F / cap | F b2c / cap | L observed frames reachable | L anchor bound reachable | flag |',
         '|---|---|---|---:|---:|---:|:---:|---:|---:|---:|:---:|---|']
    for r in m['rows']:
        L.append(f"| {r['technology']} | {r['configuration']} | {r['capacity_variant']} | {r['D_comm_ms']:.0f} ms "
                 f"| {r['R_sym_per_s'] / 1e6:.3f} | {r['capacity_msym']:.4f} | {'yes' if r['F_reachable'] else 'no'} "
                 f"| {r['F_over_capacity']:.3f} | {r['F_b2c_over_capacity']:.3f} "
                 f"| {r['L_obs_frames_reachable_fraction'] * 100:.1f} % "
                 f"| {'yes' if r['L_anchor_bound_reachable'] else 'no'} | {r['flag']} |")
    L += ['', 'Scenarios are chosen by Josh and the supervisor and written into the protocol afterwards; no '
          'parameter here may be revised to change any column.', '',
          '## 802.11bd 20 MHz derivation', '', m['bd20_derivation'], '', '## Sources', '']
    L += [f"* **[{k}]** {v}" for k, v in m['sources'].items()]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and \
             os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('link scenarios:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md.split('| technology')[0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
