#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4-B-d items 1-3: B_F^SECOND on the declared convention, the cross-convention table, and the
frame-BLER / feasibility mask re-derived at the SECOND codeword count.

Nothing here is typed in. Every constant is read from the artefact that owns it:

  bits-per-element   `B_C / elements_declared`, where `B_C` is the source budget printed in
                     `paper/main.tex` and `elements_declared` is rebuilt from the JSCC config's own
                     range / voxel / stride / channel fields -- the same derivation
                     `tests/test_payload.py (0a)` already performs.
  element counts     `results/manifests/P4B_PROBE_*.json` (per-CAV, measured by forward hook).
  code rate, K,      `projects/ca_tosg/communication/ldpc_qam.py` (the module that generated the
  bits/symbol        committed BLER table) and `main.tex` Eq.(7).
  codeword BLER      `results/channel/bler_sionna.csv`, column `bler_cw` -- no new Sionna run.

Outputs (new files; the mainline BLER table is NOT touched):
  results/channel/payload_conventions.csv   2 backbones x 2 conventions, and what re-anchoring does
  results/channel/bler_frame_second.csv     frame BLER at N_CW^SECOND + the mask onsets

    python tools/second_payload_and_bler.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'paper', 'archive', 'manuscript_frozen.tex')
LDPC = os.path.join(ROOT, 'projects', 'ca_tosg', 'communication', 'ldpc_qam.py')
BLER = os.path.join(ROOT, 'results', 'channel', 'bler_sionna.csv')
PROBE = {
    'pointpillar': os.path.join(ROOT, 'results/manifests/P4B_PROBE_pointpillar_compression.json'),
    'second': os.path.join(ROOT, 'results/manifests/P4B_PROBE_second_compression.json'),
}
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
JSCC_CFG = os.path.join(OPENCOOD,
                        'opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn_learned.yaml')
DECISION_LOG = os.path.join(ROOT, 'results/main/r10c_decision_log_{split}_B{b}.csv')
OUT_DIR = os.path.join(ROOT, 'results', 'channel')

BUDGET_FRACTIONS = (0.10, 0.20, 0.30)


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


# ------------------------------------------------------------------ constants, all derived
def declared_source_budget_mbit():
    """B_C, the declared feature source budget, parsed from main.tex rather than typed in."""
    tex = read(MAIN)
    m = re.search(r'fixed source budget of \$B_C \\approx ([0-9.]+)\$~Mbit', tex)
    assert m, 'declared source budget not found in main.tex'
    return float(m.group(1))


def declared_element_count():
    """Rebuild the declared 2.16e6-element tensor from the JSCC config's own fields."""
    assert os.path.exists(JSCC_CFG), (
        f'JSCC config absent -> {JSCC_CFG}. This is an artefact-tier input; the derivation cannot '
        'be completed without it and must FAIL rather than fall back to a literal.'
    )
    t = read(JSCC_CFG)
    rng = [float(x) for x in re.search(r'cav_lidar_range:\s*&?\w*\s*\[([^\]]+)\]', t).group(1).split(',')]
    vox = float(re.search(r'voxel_size:\s*&?\w*\s*\[([^\]]+)\]', t).group(1).split(',')[0])
    stride = int(re.search(r'feature_stride:\s*(\d+)', t).group(1))
    ch = int(re.search(r'head_dim:\s*(\d+)', t).group(1))
    fx = round(round((rng[3] - rng[0]) / vox) / stride)
    fy = round(round((rng[4] - rng[1]) / vox) / stride)
    return ch * fy * fx, (ch, fy, fx)


def ldpc_params():
    """K, N, code rate from the module that produced the committed BLER table."""
    src = read(LDPC)
    k, n = re.search(r'^K,\s*N\s*=\s*(\d+),\s*(\d+)', src, re.M).groups()
    return int(k), int(n)


def bits_per_symbol_from_paper():
    """The bits/symbol divisors used by Eq.(7), read from main.tex."""
    tex = read(MAIN)
    # Eq.(7); P5 batch 2 renamed C_16 -> F in policy context, so accept either spelling of the
    # 16-QAM symbol. A missing match must raise, not silently fall back to a literal.
    m16 = re.search(r'B_\{(?:F|C_\{16\})\}\s*=\s*3\.96/(\d+)', tex)
    m256 = re.search(r'B_\{C_\{256\}\}\s*=\s*3\.96/(\d+)', tex)
    assert m16, '16-QAM divisor not found in main.tex Eq.(7)'
    assert m256, '256-QAM divisor not found in main.tex Eq.(7)'
    return {16: int(m16.group(1)), 256: int(m256.group(1))}


def probe_totals(key):
    d = json.loads(read(PROBE[key]))
    return d, d['totals_per_cav']


# ------------------------------------------------------------------ item 1 + 2
def payload_chain(elements, bit_per_elem, code_rate, bps, k_info):
    info_bits = elements * bit_per_elem
    coded_bits = info_bits / code_rate
    return {
        'elements': elements,
        'info_mbit': info_bits / 1e6,
        'coded_mbit': coded_bits / 1e6,
        'msym': coded_bits / bps / 1e6,
        'n_cw': math.ceil(info_bits / k_info),
    }


ACTIONS = ('E', 'L', 'F')


def rho_L_from_frozen_logs():
    """Frozen per-frame action mix, read from the frozen decision logs (not the v3 engine).

    The `rf` column holds the action LABEL ('E'/'L'/'F'), not an index -- comparing it to 0/1/2
    returns all-zero shares silently, so the label set is asserted rather than assumed.
    """
    out = {}
    for split in ('validate', 'test', 'culver'):
        for b in ('010', '020', '030'):
            p = DECISION_LOG.format(split=split, b=b)
            if not os.path.exists(p):
                continue
            rf = pd.read_csv(p)['rf'].astype(str)
            unknown = set(rf.unique()) - set(ACTIONS)
            assert not unknown, f'{p}: unexpected action labels {unknown}; expected {ACTIONS}'
            shares = {f'rho_{a}': float((rf == a).mean()) for a in ACTIONS}
            assert abs(sum(shares.values()) - 1.0) < 1e-9, f'{p}: action shares do not sum to 1'
            out[(split, b)] = {**shares, 'n': int(len(rf))}
    return out


# ------------------------------------------------------------------ item 3
def frame_bler(bler_cw, n_cw):
    return 1.0 - (1.0 - bler_cw) ** n_cw


def onsets(df, col, threshold):
    """Lowest Es/N0 at which the frame BLER first falls below the feasibility threshold."""
    rows = []
    for (ch, q), g in df.groupby(['channel', 'qam']):
        g = g.sort_values('esno_db')
        ok = g[g[col] < threshold]
        rows.append({
            'channel': ch, 'qam': q,
            'onset_esno_db': float(ok.esno_db.iloc[0]) if len(ok) else None,
            'in_evaluated_window': (bool(0 <= ok.esno_db.iloc[0] <= 20) if len(ok) else False),
            'onset_is_upper_bound_point': (bool(ok.n_err.iloc[0] == 0) if len(ok) else False),
        })
    return pd.DataFrame(rows)


def main() -> int:
    b_c_mbit = declared_source_budget_mbit()
    elems_declared, dims = declared_element_count()
    bit_per_elem = b_c_mbit * 1e6 / elems_declared
    k_info, n_code = ldpc_params()
    code_rate = k_info / n_code
    bps = bits_per_symbol_from_paper()

    print(f'declared source budget  B_C = {b_c_mbit} Mbit           (main.tex)')
    print(f'declared element count      = {elems_declared:,}  ({dims[0]}x{dims[1]}x{dims[2]}, '
          f'JSCC config dims)')
    print(f'DERIVED bits/element        = {bit_per_elem:.6f}   (paper prints this rounded to 0.92)')
    print(f'LDPC K={k_info}, N={n_code}, rate={code_rate}')

    rows = []
    for key in ('pointpillar', 'second'):
        probe, tot = probe_totals(key)
        for conv, elements in (('pre_compression', tot['pre_compression_elements']),
                               ('transmitted_bottleneck', tot['transmitted_elements'])):
            ch = payload_chain(elements, bit_per_elem, code_rate, bps[16], k_info)
            rounded = payload_chain(elements, round(bit_per_elem, 2), code_rate, bps[16], k_info)
            row = {
                'backbone': key,
                'core_method': probe['model_core_method'],
                'branches_total': probe['branches_total'],
                'branches_uncompressed': probe['branches_uncompressed'],
                'convention': conv,
                'elements_per_cav': elements,
                'bit_per_element_derived': bit_per_elem,
                'info_mbit': ch['info_mbit'],
                'coded_mbit': ch['coded_mbit'],
                'B_F_msym_16qam': ch['msym'],
                'N_cw': ch['n_cw'],
                'info_mbit_at_rounded_0p92': rounded['info_mbit'],
                'B_F_msym_at_rounded_0p92': rounded['msym'],
                'rounding_gap_pct': 100 * (rounded['msym'] - ch['msym']) / ch['msym'],
            }
            for f in BUDGET_FRACTIONS:
                row[f'B_max_{int(f * 100)}pct_msym'] = f * ch['msym']
            rows.append(row)

    table = pd.DataFrame(rows)
    os.makedirs(OUT_DIR, exist_ok=True)
    table.to_csv(os.path.join(OUT_DIR, 'payload_conventions.csv'), index=False)

    print('\n=== 2 backbones x 2 conventions (16-QAM, rate-1/2) ===')
    print(table[['backbone', 'convention', 'elements_per_cav', 'info_mbit', 'B_F_msym_16qam',
                 'N_cw', 'rounding_gap_pct']].to_string(index=False))

    # what re-anchoring actually does: pure-F costs rescale, an L/F MIX does not
    sec = table[(table.backbone == 'second') & (table.convention == 'pre_compression')].iloc[0]
    pp_pre = table[(table.backbone == 'pointpillar') & (table.convention == 'pre_compression')].iloc[0]
    pp_bottleneck = table[(table.backbone == 'pointpillar')
                          & (table.convention == 'transmitted_bottleneck')].iloc[0]
    pp_declared_msym = payload_chain(elems_declared, bit_per_elem, code_rate, bps[16], k_info)
    print(f"\nmainline declared anchor  {elems_declared:,} elem -> "
          f"{pp_declared_msym['msym']:.4f} Msym, N_cw={pp_declared_msym['n_cw']}")
    print(f"mainline DEPLOYED tensor  {pp_pre.elements_per_cav:,} elem -> "
          f"{pp_pre.B_F_msym_16qam:.4f} Msym, N_cw={pp_pre.N_cw}   "
          f"(x{pp_pre.elements_per_cav / elems_declared:.4f} vs the declared anchor)")

    rho = rho_L_from_frozen_logs()
    b_l = float(re.search(r'B_L\s*=\s*([0-9.]+)', read(MAIN)).group(1))
    # the alternative budget the paper itself names, parsed from the same sentence
    # R47-2: this used to parse "re-anchoring to $2.16$~Mbit" out of main.tex. R45 retired that
    # sentence (the insensitivity claim went with it), so the parse crashed -- a generator coupled to
    # a sentence the paper no longer contains. The counterfactual it named is simply ONE bit per
    # element of the reference geometry, so it is derived from the geometry instead of from prose.
    reanchor_mbit = elems_declared * 1.0 / 1e6
    reanchor_factor = reanchor_mbit / b_c_mbit
    mix_rows = []
    for (split, b), r in sorted(rho.items()):
        # R47-2: three DEPLOYED-side conventions are now carried, not one. "deployed_tensor" was
        # ambiguous -- it meant the pre-compression pyramid -- and the convention that actually
        # describes what goes on the wire (the autoencoder bottlenecks) was missing entirely.
        for label, bf in (('declared_anchor', pp_declared_msym['msym']),
                          # the counterfactual the paper used to name: 1 bit per reference element
                          ('reanchor_1bit_per_element', pp_declared_msym['msym'] * reanchor_factor),
                          ('deployed_precompression_tensor', pp_pre.B_F_msym_16qam),
                          ('transmitted_bottleneck', pp_bottleneck.B_F_msym_16qam)):
            pay = r['rho_L'] * b_l + r['rho_F'] * bf          # E costs nothing
            mix_rows.append({'split': split, 'budget': b, 'anchor': label,
                             'rho_E': r['rho_E'], 'rho_L': r['rho_L'], 'rho_F': r['rho_F'],
                             'B_F_msym': bf,
                             'policy_msym': pay, 'policy_over_fixedF': pay / bf})
    mix = pd.DataFrame(mix_rows)
    mix.to_csv(os.path.join(OUT_DIR, 'payload_anchor_sensitivity.csv'), index=False)
    if len(mix):
        piv = mix.pivot_table(index=['split', 'budget'], columns='anchor',
                              values='policy_over_fixedF')
        piv['shift_reanchor_1bit_pct'] = 100 * (piv['reanchor_1bit_per_element']
                                                 / piv['declared_anchor'] - 1)
        piv['shift_precompression_pct'] = 100 * (piv['deployed_precompression_tensor']
                                                 / piv['declared_anchor'] - 1)
        piv['shift_bottleneck_pct'] = 100 * (piv['transmitted_bottleneck']
                                             / piv['declared_anchor'] - 1)
        print(f'\n=== is the conclusion really insensitive to the anchor? '
              f'(frozen action mix, CA-TOSG payload as a fraction of Fixed-F; '
              f'paper re-anchor {b_c_mbit} -> {reanchor_mbit} Mbit = x{reanchor_factor:.4f}) ===')
        print(piv.to_string())

    # ---- item 3: frame BLER + mask at N_cw^SECOND ----
    n_cw_second = int(sec.N_cw)
    n_cw_mainline = int(pp_declared_msym['n_cw'])
    assert n_cw_second != n_cw_mainline, (
        'N_cw^SECOND equals the mainline count -- the SECOND payload was inherited, not re-derived'
    )
    tbl = pd.read_csv(BLER)
    tbl['bler_frame_second'] = frame_bler(tbl['bler_cw'], n_cw_second)
    tbl['bler_frame_mainline_recomputed'] = frame_bler(tbl['bler_cw'], n_cw_mainline)
    tbl['n_cw_second'] = n_cw_second
    tbl['bler_cw_is_upper_bound'] = tbl['n_err'] == 0
    tbl.to_csv(os.path.join(OUT_DIR, 'bler_frame_second.csv'), index=False)

    # the committed mainline frame column must be reproducible from bler_cw at N_cw=3960
    err = (tbl['bler_frame_mainline_recomputed'] - tbl['bler_frame']).abs().max()
    print(f'\nsanity: committed bler_frame reproduced from bler_cw at N_cw={n_cw_mainline} '
          f'to {err:.2e}')

    thr = 0.999                       # BLER_INFEASIBLE, the mask constant
    on_main = onsets(tbl, 'bler_frame', thr).rename(columns={'onset_esno_db': 'onset_mainline'})
    on_sec = onsets(tbl, 'bler_frame_second', thr).rename(columns={'onset_esno_db': 'onset_second'})
    on = on_main.merge(on_sec, on=['channel', 'qam'], suffixes=('_main', '_second'))
    on['moved_db'] = on['onset_second'] - on['onset_mainline']
    on.to_csv(os.path.join(OUT_DIR, 'bler_onset_second.csv'), index=False)
    print(f'\n=== feasibility-mask onset (frame BLER first < {thr}), '
          f'N_cw {n_cw_mainline} -> {n_cw_second} ===')
    print(on[['channel', 'qam', 'onset_mainline', 'onset_second', 'moved_db',
              'in_evaluated_window_second', 'onset_is_upper_bound_point_second']].to_string(index=False))
    never = on[on['onset_second'].isna()]
    moved_out = on[on['onset_mainline'].notna() & (on['onset_second'].isna()
                                                   | ~on['in_evaluated_window_second'].astype(bool))]
    if len(never):
        print('\n** no onset anywhere in the committed table (frame BLER never falls below the '
              'mask threshold) -- unchanged from the mainline, reported as-is, no grid extension:')
        print(never[['channel', 'qam', 'onset_mainline', 'onset_second']].to_string(index=False))
    if len(moved_out):
        print('\n** onset(s) that HAD one at N_cw=%d and lost it (or left [0,20] dB) at N_cw=%d:'
              % (n_cw_mainline, n_cw_second))
        print(moved_out[['channel', 'qam', 'onset_mainline', 'onset_second']].to_string(index=False))
    else:
        print('\nno onset moved out of the evaluated [0,20] dB window.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
