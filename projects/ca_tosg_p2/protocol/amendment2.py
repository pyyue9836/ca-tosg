#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R7 B, C — the numbers of Amendment 2, derived rather than typed.

  B-1  n2 = 8 random masks, recorded as a precision correction made AFTER stage-1 results were seen
  B-2  the planning basis: the half-width of the confidence - random difference, with norm - random shown
  B-3  n2 = 8 is a cost-planning basis, not a precision guarantee; it is re-checked after stage 2
  C    the cost of a CLEAN-ONLY stage 2 (no loss sweep), extrapolated from stage-1 measured time

Reads the stage-1 report, Amendment 1 and the stage-1 run summary. No new measurement.

    python projects/ca_tosg_p2/protocol/amendment2.py [--check]
"""
from __future__ import annotations
import argparse, json, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
REPORT = os.path.join(P2, 'results', 'stage1', 'stage1_report.json')
RUN = os.path.join(P2, 'results', 'stage1', 'f_block_eval_validate.json')
AM1 = os.path.join(HERE, 'amendment1.json')
PROTOCOL = os.path.join(HERE, 'f_block_selection.md')
OUT_JSON = os.path.join(HERE, 'amendment2.json')
OUT_MD = os.path.join(HERE, 'amendment2.md')

N2_CHOSEN = 8
N_CANDIDATES = (2, 4, 8, 12, 16, 20)
RHO = 0.1
SPLIT_FRAMES = 1980
REGIME = 'ideal'


def n_for(sd, hw, rho=RHO):
    thr = rho * hw
    return next((n for n in N_CANDIDATES if sd / np.sqrt(n) <= thr), None), thr


def build():
    rep = json.load(open(REPORT))
    run = json.load(open(RUN))
    am1 = json.load(open(AM1))
    sd = rep['B4_mask_spread'][REGIME]['sd_mask']
    hw_cr = rep['B2_differences'][f'confidence_minus_random|{REGIME}']['half_width']
    hw_nr = rep['B2_differences'][f'norm_minus_random|{REGIME}']['half_width']
    hw_level = rep['C1_n2_planning']['hw_scene']
    n_cr, thr_cr = n_for(sd, hw_cr)
    n_nr, thr_nr = n_for(sd, hw_nr)
    n_level, thr_level = n_for(sd, hw_level)

    # ---- C: clean-only stage 2 ------------------------------------------------------------
    t = run['timing']
    fixed = t['t_load_s']['mean'] + t['t_record_fwd_s']['mean'] + t['t_collab_fwd_gpu_s']['mean']
    masked_stage1 = am1['C1_stage1']['masked_forwards_per_frame']
    per_cond = (t['t_frame_total_s']['mean'] - fixed) / masked_stage1
    masked_clean = 1 + 1 + N2_CHOSEN                          # confidence, norm, n2 random -- clean only
    shared = 2                                                # full-F recording forward + collaborator forward
    per_frame = fixed + masked_clean * per_cond
    hours = SPLIT_FRAMES * per_frame / 3600
    identity_extra = SPLIT_FRAMES * per_cond / 3600           # if the C-1 identity control is kept

    # what a clean-only run can and cannot compute, in the locked cells
    pc = rep['B1_scene_equal_f1']['per_cell']
    cells = list(pc['E'])
    eight = [c for c in cells if c.endswith('8 dB')][0]
    ten = [c for c in cells if c.endswith('10 dB')][0]
    approx = {arm.split('|')[0]: abs(pc[arm][eight] - pc[arm][ten])
              for arm in pc if arm.endswith(f'|{REGIME}')}

    full_sweep_hours = [r for r in rep['B6_time']['stage2_cost_from_measurement'] if r['n2'] == N2_CHOSEN][0]['gpu_hours']
    return {
        'schema': 'catosg-p2-amendment2/1',
        'reads': 'stage1_report.json, amendment1.json, the stage-1 run summary; no new measurement',
        'B1_n2': {'n2': N2_CHOSEN,
                  'provenance': 'a precision correction chosen AFTER stage-1 results were seen; it is NOT the '
                                'value the pre-registered rule of Amendment 1 produced (that rule gave 4) and it '
                                'is not a pre-registered quantity',
                  'amendment1_rule_value': rep['C1_n2_planning']['n2_planning_value']},
        'B2_basis': {
            'sd_mask': sd, 'rho': RHO,
            'chosen_basis': 'half-width of the confidence - random difference',
            'hw_confidence_minus_random': hw_cr, 'threshold_confidence_minus_random': thr_cr,
            'n_from_confidence_minus_random': n_cr,
            'hw_norm_minus_random': hw_nr, 'threshold_norm_minus_random': thr_nr,
            'n_from_norm_minus_random': n_nr,
            'hw_level_amendment1': hw_level, 'threshold_level': thr_level, 'n_from_level': n_level,
            'why': 'the Monte Carlo error of the random masks enters only comparisons against the random '
                   'baseline; confidence - L and norm - L carry none of it, so the difference against random '
                   'is the quantity the mask count has to be sized for',
            'mc_se_by_n': {str(n): sd / np.sqrt(n) for n in N_CANDIDATES}},
        'B3_status': 'n2 = 8 is a basis for cost planning, not a guarantee of precision: SD_mask is itself '
                     'estimated from 8 masks on 60 frames. After stage 2 the check is repeated with the SD_mask '
                     'measured there, and the result is reported whether or not it meets the threshold',
        'C_clean_only_stage2': {
            'scope': 'validate, 1,980 frames; confidence, norm and random; clean condition only; no loss sweep. '
                     'E, L and full F come from existing P1 products at matched frames',
            'masked_forwards_per_frame': masked_clean, 'shared_forwards_per_frame': shared,
            'forwards_per_frame_total': masked_clean + shared,
            'identity_control_included': False,
            'per_condition_s_measured_stage1': per_cond, 'fixed_s_per_frame': fixed,
            'sec_per_frame': per_frame, 'gpu_hours': hours,
            'gpu_hours_if_identity_control_kept': hours + identity_extra,
            'not_this_number': {'full_loss_sweep_at_n2_gpu_hours': full_sweep_hours,
                                'note': 'the full damaged sweep at the same n2 costs this much and is NOT the cost '
                                        'of the clean-only plan; the two must not be quoted for each other'},
            'cell_coverage': {'exact_cells': [c for c in cells if c != eight],
                              'approximated_cell': eight,
                              'why': 'six of the seven locked cells have p_cw exactly 0, so the clean forward IS '
                                     'their value; the 8 dB cell needs the p = 0.001 node, which a clean-only run '
                                     'does not produce and would have to substitute with the clean value',
                              'substitution_error_measured_in_stage1': approx},
            'bias': ['stage-1 timing included CUDA warm-up and a GPU shared with a desktop session -> the '
                     'per-condition figure is probably HIGH',
                     'stage 1 read every 33rd frame; a full run reads frames consecutively, so caching may make '
                     'data loading cheaper -> the estimate may be HIGH on that count too',
                     'against both: a full run holds 1,980 frames of results in memory and writes a larger file, '
                     'which stage 1 did not exercise -> the estimate may be LOW on that count',
                     'no per-frame cost was measured on a machine free of other load']},
        'command': 'python projects/ca_tosg_p2/protocol/amendment2.py'}


def markdown(m):
    b1, b2, c = m['B1_n2'], m['B2_basis'], m['C_clean_only_stage2']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/amendment2.py -- do not edit by hand -->',
         '# Amendment 2 — derived numbers (P2-R7)', '', f"Reads: {m['reads']}.", '',
         '## B-1 Random masks', '', f"**n2 = {b1['n2']}.** {b1['provenance']}.", '',
         '## B-2 Planning basis', '',
         f"SD_mask = {b2['sd_mask']:.5f}. Basis: {b2['chosen_basis']}. {b2['why']}.", '',
         '| basis | half-width | threshold = ρ × half-width | smallest n meeting it |', '|---|---:|---:|---:|',
         f"| confidence − random (**used**) | {b2['hw_confidence_minus_random']:.5f} | {b2['threshold_confidence_minus_random']:.5f} | {b2['n_from_confidence_minus_random']} |",
         f"| norm − random (comparison) | {b2['hw_norm_minus_random']:.5f} | {b2['threshold_norm_minus_random']:.5f} | {b2['n_from_norm_minus_random']} |",
         f"| absolute level (Amendment 1) | {b2['hw_level_amendment1']:.5f} | {b2['threshold_level']:.5f} | {b2['n_from_level']} |",
         '', '| n | Monte Carlo SE |', '|---:|---:|']
    L += [f"| {n} | {v:.5f} |" for n, v in b2['mc_se_by_n'].items()]
    L += ['', '## B-3 Status', '', m['B3_status'] + '.', '',
          '## C Clean-only stage 2', '', f"Scope: {c['scope']}.", '',
          f"Forwards per frame: **{c['masked_forwards_per_frame']} masked** (confidence, norm, {b1['n2']} random, "
          f"clean only) plus {c['shared_forwards_per_frame']} shared = {c['forwards_per_frame_total']}; the C-1 "
          f"identity control is not included.", '',
          f"At the stage-1 measured cost of {c['per_condition_s_measured_stage1'] * 1e3:.1f} ms per condition and "
          f"{c['fixed_s_per_frame']:.3f} s fixed per frame: **{c['sec_per_frame']:.2f} s/frame → "
          f"{c['gpu_hours']:.1f} GPU-hours** on 1,980 frames "
          f"({c['gpu_hours_if_identity_control_kept']:.1f} with the identity control).", '',
          f"**Not this number:** the full damaged sweep at the same n2 costs "
          f"{c['not_this_number']['full_loss_sweep_at_n2_gpu_hours']:.1f} GPU-hours. {c['not_this_number']['note']}.", '',
          f"**Cell coverage.** {c['cell_coverage']['why']}. Substitution error measured in stage 1: "
          + ', '.join(f"{k} {v:.5f}" for k, v in c['cell_coverage']['substitution_error_measured_in_stage1'].items()) + '.', '',
          '**Direction of bias:**', '']
    L += [f"* {b}." for b in c['bias']]
    return '\n'.join(L) + '\n'


REQUIRED = lambda m: ['Amendment 2', f"n2 = {m['B1_n2']['n2']}",
                      f"{m['B2_basis']['hw_confidence_minus_random']:.5f}",
                      f"{m['C_clean_only_stage2']['gpu_hours']:.1f} GPU-hours",
                      f"{m['C_clean_only_stage2']['masked_forwards_per_frame']} masked forwards"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        miss = [x for x in REQUIRED(m) if x not in open(PROTOCOL).read()]
        print('amendment2:', 'reproduced' if ok else 'FAIL -- not what the generator writes',
              '| protocol carries the numbers:', 'yes' if not miss else f'NO, missing {miss}')
        return 0 if ok and not miss else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md); print(md); return 0


if __name__ == '__main__':
    sys.exit(main())
