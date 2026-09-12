#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R10 C — candidates for a "no cooperation needed -> E" criterion. CPU, no fitting, no training.

  C-1  what P1 already recorded: a monotone threshold rule never reaches E, and what the oracle does
       on the current grid, per channel type
  C-2  how the frames the oracle sends to E differ, cue by cue, from the frames it sends to L or F --
       means and quantiles only. NO model is fitted
  C-3  two or three candidate rules built from C-2, using only what the ego has BEFORE it asks, each
       threshold traced to where it comes from, with the share of frames it would trigger on. Their
       effect is NOT evaluated here
  C-4  the two different situations that both end in E, kept apart

The P1 sentences quoted in C-1 are located in the changelog by exact substring; if the wording has
moved, this tool fails rather than paraphrasing from memory.

    python projects/ca_tosg_p2/protocol/e_criterion.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
OUT_JSON = os.path.join(HERE, 'e_criterion.json')
OUT_MD = os.path.join(HERE, 'e_criterion.md')
V2 = os.path.join(ROOT, 'results', 'v2')
GRID = os.path.join(V2, 'v2_grid_validate_ideal.csv')
CUES = os.path.join(V2, 'wp6_cues_validate.csv')
SCHEMA = os.path.join(ROOT, 'results', 'manifests', 'V2_CUE_SCHEMA.json')
CHANGELOG = os.path.join(ROOT, 'docs', 'history', 'protocol_changelog.md')
TIE = 1e-12
QUANTILE_FOR_RULES = 0.75          # C-3: the threshold source, fixed here and stated in the output


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def quote(text, needle, label):
    """Locate a P1 sentence verbatim. The changelog hard-wraps its lines, so a sentence that reads as
    one runs across a newline and an indent; the search therefore runs on a whitespace-collapsed copy.
    That is a fix to the matcher, not a loosening of the check: the wording must still be present."""
    flat = ' '.join(text.split())
    if needle not in flat:
        raise SystemExit(f'C-1: the P1 sentence for {label} is not in the changelog as quoted -- refusing '
                         f'to paraphrase. Missing: {needle!r}')
    i = flat.index(needle)
    a = flat.rfind('. ', 0, i)
    a = 0 if a < 0 else a + 2
    b = flat.find('. ', i + len(needle))
    return flat[a:(b + 1) if b > 0 else None].strip()


def build():
    g = pd.read_csv(GRID, usecols=['sample_id', 'scene', 'snr_db', 'channel', 'eff_E', 'eff_L', 'eff_F',
                                   'has_collaborator', 'p_cw'])
    cues = pd.read_csv(CUES)
    fields = json.load(open(SCHEMA))['fields']
    log = open(CHANGELOG, encoding='utf-8').read()
    p12 = json.load(open(os.path.join(V2, 'v2_p12_comparison.json')))
    rf = p12['arms']['frozen_RF_cand67']

    # --- oracle on the current grid: budget-blind argmax, ties to the smaller payload (E > L > F) ----
    eff = g[['eff_E', 'eff_L', 'eff_F']].to_numpy()
    best = eff.max(axis=1)
    lab = np.where(eff[:, 0] >= best - TIE, 'E', np.where(eff[:, 1] >= best - TIE, 'L', 'F'))
    g['oracle'] = lab
    per_channel = {}
    for ch, t in g.groupby('channel'):
        per_channel[ch] = {a: float((t.oracle == a).mean()) for a in ('E', 'L', 'F')}
        per_channel[ch]['rows'] = int(len(t))
    per_cell = [{'channel': ch, 'snr_db': int(s), 'rho_E': float((t.oracle == 'E').mean()),
                 'rho_L': float((t.oracle == 'L').mean()), 'rho_F': float((t.oracle == 'F').mean())}
                for (ch, s), t in g.groupby(['channel', 'snr_db'])]
    per_cell.sort(key=lambda r: (r['channel'], r['snr_db']))

    # three claims are taken from P1; two of them live in one sentence, so quotes are collapsed by
    # sentence and each records which claims it carries
    needles = [('a monotone rule never reaches E', 'E is not reachable by a monotone threshold on these cues'),
               ("the two-gate rule's rho_E", '`rho_E = 0.00000` in every split x budget cell'),
               ("the frozen forest's rho_E on validate", '0.0107 / 0.0112 / 0.0120')]
    quotes = []
    for label, needle in needles:
        q = quote(log, needle, label)
        hit = next((x for x in quotes if x['quote'] == q), None)
        if hit:
            hit['covers'].append(label)
        else:
            quotes.append({'quote': q, 'covers': [label]})
    # B-2: the oracle depends on WHICH utility it maximises. The grid's eff_F is P1's partial-recovery
    # column; under the locked all-or-nothing accounting F is a different quantity, so both are reported
    # and the second is marked as constructed.
    w5 = pd.read_csv(os.path.join(V2, 'wp5_final_validate.csv'), usecols=['frame', 'f1_clean', 'f1_ego']).set_index('frame')
    n_cw_F = json.load(open(os.path.join(V2, 'payload_chain.json')))['F']['n_cw']
    q_F = (1.0 - g.p_cw.to_numpy()) ** n_cw_F
    eff_F_msg = q_F * w5.f1_clean.loc[g.sample_id].to_numpy() + (1 - q_F) * w5.f1_ego.loc[g.sample_id].to_numpy()
    eff_msg = np.column_stack([g.eff_E.to_numpy(), g.eff_L.to_numpy(), eff_F_msg])
    best_msg = eff_msg.max(axis=1)
    lab_msg = np.where(eff_msg[:, 0] >= best_msg - TIE, 'E',
                       np.where(eff_msg[:, 1] >= best_msg - TIE, 'L', 'F'))
    oracle_msg = {ch: {a: float((lab_msg[(g.channel == ch).to_numpy()] == a).mean()) for a in ('E', 'L', 'F')}
                  for ch in ('awgn', 'rayleigh')}

    c1 = {'p1_record': {
              'quotes': quotes,
              'source': 'docs/history/protocol_changelog.md, change-log R21-A-run (2026-08-17)',
              'correction_P2R11_B1': {
                  'what_was_wrong': 'the 0.0107 / 0.0112 / 0.0120 figures quoted above are the v1-era forest of the '
                                    'R21 change-log. They do NOT describe the current frozen selector, and citing '
                                    'them for it understated its E share by a factor of about 40',
                  'current_frozen_forest': {
                      'rho_E': rf['mix']['E'], 'rho_L': rf['mix']['L'], 'rho_F': rf['mix']['F'],
                      'scene_equal_f1': rf['scene_equal_f1'], 'mean_payload_msym': rf['mean_payload_msym'],
                      'split': p12['split'], 'regime': p12['regime'], 'lambda': p12['lambda'],
                      'source': 'results/v2/v2_p12_comparison.json, arms.frozen_RF_cand67 (also printed as the '
                                'CA-TOSG (frozen RF) row of paper/tables/tbl_baselines.tex)'},
                  'status_of_the_old_numbers': 'kept above as a historical record of the v1 forest, not withdrawn '
                                               'from the changelog, and not to be read as the current selector'}},
          'oracle_on_the_current_grid': {
              'definition': 'budget-blind argmax of eff over {E, L, F} per (frame, cell); ties within 1e-12 go to '
                            'the smaller payload, i.e. E before L before F',
              'product': 'results/v2/v2_grid_validate_ideal.csv', 'sha256': sha(GRID),
              'utility_accounting': "P1's PARTIAL-RECOVERY eff_F -- the grid column. This is not the "
                                    'accounting locked in P2-R11 A',
              'overall': {a: float((g.oracle == a).mean()) for a in ('E', 'L', 'F')},
              'per_channel': per_channel, 'per_cell': per_cell},
          'oracle_under_the_locked_all_or_nothing_accounting': {
              'status': 'CONSTRUCTED: eff_F replaced by q_F * f1_clean + (1 - q_F) * f1_ego, '
                        f'q_F = (1 - p_cw) ** {n_cw_F}; eff_E and eff_L unchanged',
              'per_channel': oracle_msg},
          'what_the_low_SNR_E_cells_mean': 'at low SNR the oracle picks E mostly because L and F have both failed '
                                           'and their fallback IS E, so the three actions tie and the tie goes to '
                                           'the cheapest. That is "the channel removed the benefit of cooperating", '
                                           'not "this frame did not need cooperation". The two are different '
                                           'questions and are not pooled: the second is examined on RELIABLE cells '
                                           'only, in the E phase, which is deferred'}

    # --- C-2: how the oracle-E frames differ, cue by cue -------------------------------------------
    cue_by_frame = cues.set_index('frame')
    c2 = {}
    for ch in ('rayleigh', 'awgn'):
        t = g[g.channel == ch]
        share = t.groupby('sample_id').oracle.apply(lambda s: float((s == 'E').mean()))
        sometimes = share[share > 0].index.to_numpy()
        never = share[share == 0].index.to_numpy()
        dims = []
        for f in fields:
            if f not in cue_by_frame.columns:
                continue
            a, b = cue_by_frame[f].loc[sometimes].to_numpy(float), cue_by_frame[f].loc[never].to_numpy(float)
            if len(a) == 0 or len(b) == 0:
                continue
            sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2) if len(a) > 1 and len(b) > 1 else np.nan
            dims.append({'cue': f, 'mean_E_frames': float(a.mean()), 'mean_other_frames': float(b.mean()),
                         'q25_q50_q75_E': [float(x) for x in np.percentile(a, [25, 50, 75])],
                         'q25_q50_q75_other': [float(x) for x in np.percentile(b, [25, 50, 75])],
                         'standardised_difference': float((a.mean() - b.mean()) / sd) if sd and sd > 0 else 0.0})
        dims.sort(key=lambda d: -abs(d['standardised_difference']))
        c2[ch] = {'frames_with_any_E_cell': int(len(sometimes)), 'frames_with_no_E_cell': int(len(never)),
                  'cells_per_frame': int(len(t) / max(cues.shape[0], 1)), 'dimensions': dims}
    c2['note'] = ('means, quantiles and a standardised difference only. Nothing is fitted, no threshold is '
                  'optimised against these labels, and the ordering by standardised difference is a way of '
                  'reading the table, not a selection')

    # --- C-3: candidate rules ----------------------------------------------------------------------
    ref = c2['rayleigh']['dimensions']
    picks, seen_family = [], set()
    for d in ref:
        fam = d['cue'].replace('ego_pcd_', '').split('_')[0]
        if d['cue'] in ('has_collaborator',) or fam in seen_family:
            continue
        seen_family.add(fam)
        picks.append(d)
        if len(picks) == 3:
            break
    rules = []
    for d in picks:
        f = d['cue']
        v = cue_by_frame[f].to_numpy(float)
        up = d['standardised_difference'] > 0
        q = QUANTILE_FOR_RULES if up else 1 - QUANTILE_FOR_RULES
        thr = float(np.quantile(v, q))
        trig = float((v >= thr).mean() if up else (v <= thr).mean())
        rules.append({
            'rule': f"E if {f} {'>=' if up else '<='} {thr:.6g}",
            'cue': f, 'direction': 'high values -> E' if up else 'low values -> E', 'threshold': thr,
            'threshold_source': f'the {q:.0%} quantile of {f} over all 1,980 validate frames -- a quantile of the '
                                f'cue distribution itself, NOT a value fitted against the oracle labels',
            'direction_source': 'the sign of the standardised difference in C-2 (Rayleigh)',
            'available_before_the_request': True,
            'expected_trigger_share': trig,
            'effect_not_evaluated': 'this reports how often the rule would fire, and nothing about what it costs '
                                    'or gains'})
    for r in rules:
        r['status'] = ('WITHDRAWN (P2-R11 B-4): exploratory, derived by reading development results, NOT adopted. '
                       'It is kept visible rather than deleted so that the reasoning can be audited')
    c3 = {'status': 'WITHDRAWN as a set (P2-R11 B-4). The rules below are recorded, not proposed: their directions '
                    'were read off development-split oracle labels, which is exactly the dependence an E criterion '
                    'must not have. The E phase is deferred and will start from reliable cells',
          'rules': rules, 'quantile_used': QUANTILE_FOR_RULES,
          'why_rayleigh': 'the candidates are read off the Rayleigh side because that is where the oracle sends '
                          'anything to E at all; the AWGN table is reported beside it',
          'all_cues_are_pre_request': 'every cue used is ego-local and exists before the request is issued, by the '
                                      'frozen cue schema'}

    # --- C-4 ---------------------------------------------------------------------------------------
    no_collab_rows = int((g.has_collaborator == 0).sum())
    c4 = {'structural_E': {'meaning': 'no collaborator is available, so E is forced and nothing is transmitted',
                           'rows_on_validate': no_collab_rows,
                           'status': 'already handled: it is a feasibility condition, not a decision'},
          'discretionary_E': {'meaning': 'a collaborator IS available and could send, but the frame does not need '
                                         'it; E is chosen rather than forced',
                              'status': 'the subject of this section -- no rule for it exists yet'},
          'why_they_must_not_be_pooled': 'a share of E that mixes the two measures availability, not judgement; on '
                                         'this split the structural case is absent, so every E here is discretionary'}

    return {'schema': 'catosg-p2-e-criterion/1',
            'what': 'P1 products read on CPU. No model is fitted, no selector is trained, no threshold is '
                    'optimised against an outcome',
            'C1': c1, 'C2_cue_differences': c2, 'C3_candidate_rules': c3, 'C4_two_situations': c4,
            'command': 'python projects/ca_tosg_p2/protocol/e_criterion.py'}


def markdown(m):
    c1, c2, c3, c4 = m['C1'], m['C2_cue_differences'], m['C3_candidate_rules'], m['C4_two_situations']
    o = c1['oracle_on_the_current_grid']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/e_criterion.py -- do not edit by hand -->',
         '# A "no cooperation needed" criterion: candidates only (P2-R10 C)', '', f"**{m['what']}.**", '',
         '## C-1 What is already on the record', '', f"From {c1['p1_record']['source']}:", '']
    for q in c1['p1_record']['quotes']:
        L += [f"> {q['quote']}", '', f"*(carries: {'; '.join(q['covers'])})*", '']
    corr = c1['p1_record']['correction_P2R11_B1']
    cf = corr['current_frozen_forest']
    L += ['**Correction (P2-R11 B-1).** ' + corr['what_was_wrong'] + '. The current frozen selector, on '
          f"{cf['split']} under the {cf['regime']} regime at λ = {cf['lambda']}, takes **E on "
          f"{cf['rho_E'] * 100:.1f} %** of rows (L {cf['rho_L'] * 100:.1f} %, F {cf['rho_F'] * 100:.1f} %), at "
          f"scene-equal F1 {cf['scene_equal_f1']:.5f} and {cf['mean_payload_msym']:.5f} Msym. Source: "
          f"{cf['source']}. {corr['status_of_the_old_numbers']}.", '',
          f"On the current grid ({o['product']}), with the oracle defined as {o['definition']}:", '',
          '| channel | ρ_E | ρ_L | ρ_F | rows |', '|---|---:|---:|---:|---:|']
    for ch, v in o['per_channel'].items():
        L.append(f"| {ch} | {v['E'] * 100:.2f} % | {v['L'] * 100:.2f} % | {v['F'] * 100:.2f} % | {v['rows']:,} |")
    L += ['', '| channel | SNR | ρ_E | ρ_L | ρ_F |', '|---|---:|---:|---:|---:|']
    for r in o['per_cell']:
        L.append(f"| {r['channel']} | {r['snr_db']} | {r['rho_E'] * 100:.2f} % | {r['rho_L'] * 100:.2f} % | {r['rho_F'] * 100:.2f} % |")
    L += ['', f"*Utility accounting behind that table: {o['utility_accounting']}.*", '',
          '**Under the locked all-or-nothing accounting** (constructed: '
          + m['C1']['oracle_under_the_locked_all_or_nothing_accounting']['status'] + '):', '',
          '| channel | ρ_E | ρ_L | ρ_F |', '|---|---:|---:|---:|']
    for ch, v in m['C1']['oracle_under_the_locked_all_or_nothing_accounting']['per_channel'].items():
        L.append(f"| {ch} | {v['E'] * 100:.2f} % | {v['L'] * 100:.2f} % | {v['F'] * 100:.2f} % |")
    L += ['', f"**What the low-SNR E cells mean.** {m['C1']['what_the_low_SNR_E_cells_mean']}.", '',
          '## C-2 How the oracle-E frames differ, cue by cue', '', f"{c2['note']}.", '']
    for ch in ('rayleigh', 'awgn'):
        d = c2[ch]
        L += [f"### {ch}: {d['frames_with_any_E_cell']:,} frames with at least one E cell, "
              f"{d['frames_with_no_E_cell']:,} with none", '',
              '| cue | mean, E frames | mean, other frames | standardised diff | q25/q50/q75 E | q25/q50/q75 other |',
              '|---|---:|---:|---:|---|---|']
        for x in d['dimensions'][:8]:
            L.append(f"| {x['cue']} | {x['mean_E_frames']:.4g} | {x['mean_other_frames']:.4g} | "
                     f"{x['standardised_difference']:+.3f} | "
                     f"{' / '.join(f'{y:.4g}' for y in x['q25_q50_q75_E'])} | "
                     f"{' / '.join(f'{y:.4g}' for y in x['q25_q50_q75_other'])} |")
        L += ['', f"(top 8 of {len(d['dimensions'])} cues by absolute standardised difference; the full list is in "
              'the JSON)', '']
    L += ['## C-3 Candidate rules — WITHDRAWN', '', f"**{c3['status']}.**", '',
          f"{c3['why_rayleigh']}. {c3['all_cues_are_pre_request']}.", '',
          '| candidate | direction | threshold | where the threshold comes from | would fire on |',
          '|---|---|---:|---|---:|']
    for r in c3['rules']:
        L.append(f"| `{r['rule']}` | {r['direction']} | {r['threshold']:.6g} | {r['threshold_source']} | "
                 f"{r['expected_trigger_share'] * 100:.1f} % of frames |")
    L += ['', '**No effect is evaluated here.** These are candidates and trigger rates only.', '',
          '## C-4 Two situations that both end in E', '',
          f"* **Structural E** — {c4['structural_E']['meaning']}. Rows on validate: "
          f"{c4['structural_E']['rows_on_validate']:,}. {c4['structural_E']['status']}.",
          f"* **Discretionary E** — {c4['discretionary_E']['meaning']}. {c4['discretionary_E']['status']}.",
          '', f"*{c4['why_they_must_not_be_pooled']}.*"]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js and os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print('e criterion:', 'reproduced' if ok else 'FAIL -- not what the generator writes'); return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md); print(md); return 0


if __name__ == '__main__':
    sys.exit(main())
