#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R20 items 1-2: emit the headline table bodies into paper/main.tex from the frozen CSVs.

Both tables were hand-maintained, which is how `tab:headline` kept an entirely pre-corrigendum body
and `tab:headline_agg` ended up **mixed** -- the CA-TOSG rows renumbered while the fixed baselines and
the tau rows stayed retired. Neither table is transcribed here: every cell is computed from a
committed product and written in place, so re-running this is the only way the numbers change.

  tab:headline       true_e2e_ap_by_snr.csv  -- per split, the fallback regime (all AWGN points below
                     the measured knee) and the feature-active regime (knee and above), AP@0.5/0.7,
                     with the payload reconstructed from the per-point action mix and PAYVEC.
  tab:headline_agg   fixed_references.csv    -- ALL FOUR fixed rows (Fixed-L / F / C256 / oracle)
                     replay_summary.csv      -- the per-budget selector and tau rows
                     FROZEN_MANIFEST.json    -- the tau* values in the row labels

    python tools/build_paper_tables.py [--check]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/utils'))
sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/models'))
sys.path.insert(0, ROOT)

TEX = os.path.join(ROOT, 'paper/main.tex')
KNEE_DB = 10.0                       # the measured rho_F knee (Section true_e2e)
PAY = {'E': 0.0, 'L': 0.024, 'F': 0.99}
B_F = 0.99
SPLIT_LABEL = {'validate': 'Validate', 'test': 'Test', 'culver': 'Culver-City'}


def _payload(row):
    return row.rho_E * PAY['E'] + row.rho_L * PAY['L'] + row.rho_F * PAY['F']


def headline_body():
    d = pd.read_csv(os.path.join(ROOT, 'results/main/true_e2e_ap_by_snr.csv'))
    d = d[(d.budget == 0.2) & (d.policy == 'CA-TOSG-RF') & (d.channel == 'awgn')]
    out, n = [], {}
    for sp in ('validate', 'test', 'culver'):
        g = d[d.split == sp]
        n[sp] = len(g)
        lo, hi = g[g.snr_db < KNEE_DB], g[g.snr_db >= KNEE_DB]
        rows = []
        for lab, seg in (('Fallback ($L$)  ', lo), ('AWGN $\\ge10$~dB', hi)):
            ap50, ap70 = seg.ap50_mean.mean(), seg.ap70_mean.mean()
            pay = seg.apply(_payload, axis=1).mean()
            rows.append((lab, ap50, ap70, pay))
        best = max(rows, key=lambda r: r[1])
        frames = {'validate': '1{,}980', 'test': '2{,}170', 'culver': '550'}[sp]
        out.append(f'\\multirow{{2}}{{*}}{{{SPLIT_LABEL[sp]} (${frames}$)}}')
        for r in rows:
            f50 = f'\\textbf{{{r[1]:.4f}}}' if r is best else f'{r[1]:.4f}'
            f70 = f'\\textbf{{{r[2]:.4f}}}' if r is best else f'{r[2]:.4f}'
            out.append(f'  & {r[0]} & {f50} & {f70} & {r[3]:.3f} \\\\')
        if sp != 'culver':
            out.append('\\midrule')
    return '\n'.join(out) + '\n'


def headline_caption_numbers():
    """The channel-averaged payload range at B_max=0.20 (R23-8: no longer spliced into the paper --
    the sentence it targeted does not exist; observation_iii() owns the per-split ranges instead).
    Kept as a derivation, not called by main()."""
    r = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
    r = r[r.budget == 0.2]
    lo, hi = r.B_RF.min(), r.B_RF.max()
    return lo, hi, 100 * lo / B_F, 100 * hi / B_F


def agg_body():
    fx = pd.read_csv(os.path.join(ROOT, 'results/main/fixed_references.csv'))
    fx = fx[fx.split == 'test'].set_index('policy')
    rep = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
    rep = rep[rep.split == 'test'].set_index('budget')
    frozen = json.load(open(os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')))['budgets']
    out = []
    for pol, label in (('Fixed-L', 'Fixed $L$ (object-level)      '),
                       ('Fixed-F', 'Fixed $F$ (LDPC+16-QAM)       '),
                       ('Fixed-C256', 'Fixed $C_{256}$ (LDPC+256-QAM)'),
                       ('oracle', 'Masked oracle (upper bound)   ')):
        f1 = float(fx.loc[pol, 'F1'])
        pay = float(fx.loc[pol, 'payload_msym'])
        out.append(f'{label} & {f1:.4f} & {pay:.3f} & ${100 * pay / B_F:.1f}\\%$ \\\\')
    out.append('\\midrule')
    for tag in sorted(frozen):
        b = float(tag)
        r = rep.loc[b]
        tau = frozen[tag]['tau_star']
        out.append(f'\\multicolumn{{4}}{{l}}{{\\emph{{$B_{{\\max}}={b:.2f}$}}}} \\\\')
        # bold the better F1 and the smaller channel use, per budget
        rf_better = r.F1_RF >= r.F1_tau
        f1_tau = f'\\textbf{{{r.F1_tau:.5f}}}' if not rf_better else f'{r.F1_tau:.5f}'
        f1_rf = f'\\textbf{{{r.F1_RF:.5f}}}' if rf_better else f'{r.F1_RF:.5f}'
        out.append(f'\\quad SNR-threshold ($\\tau^\\star{{=}}{tau:.0f}$)   & {f1_tau} & '
                   f'{r.B_tau:.4f} & ${100 * r.B_tau / B_F:.1f}\\%$ \\\\')
        out.append(f'\\quad \\method{{}} (RF, frozen)              & {f1_rf} & '
                   f'\\textbf{{{r.B_RF:.4f}}} & $\\mathbf{{{100 * r.B_RF / B_F:.1f}\\%}}$ \\\\')
    return '\n'.join(out) + '\n'


def gen_headline_baselines(tex):
    """tab:gen_headline carries per-split fixed baselines; regenerate each inside ITS OWN section.

    9b caught this table still holding retired Fixed-F / C256 values while its selector rows had been
    renumbered. A first attempt used re.sub(count=1) per split, which always rewrote the FIRST
    occurrence in the document -- so the Culver pass overwrote the test rows with Culver numbers. The
    replacement is therefore scoped to the span between one split header and the next.
    """
    fx = pd.read_csv(os.path.join(ROOT, 'results/main/fixed_references.csv'))
    m = re.search(r'\\label\{tab:gen_headline\}(.*?)\\end\{tabular\}', tex, re.S)
    if not m:
        return tex
    block = m.group(1)
    marks = [(mm.start(), 'culver' if 'Culver' in mm.group(0) else 'test')
             for mm in re.finditer(r'\\emph\{[^}]*(?:test|Culver-City)[^}]*\}', block)]
    if not marks:
        return tex
    spans = [(marks[i][0], marks[i + 1][0] if i + 1 < len(marks) else len(block), marks[i][1])
             for i in range(len(marks))]
    # R23-8: the masked-oracle row was NOT in this list although the module docstring claimed all
    # four fixed rows were generated. It had kept its retired values (test 0.9165 / 0.1706) through
    # every batch since the corrigendum.
    TAIL = r'(\s*&\s*\$)[\d.]+(\\%\$)'          # the share-of-B_F cell, regenerated as well
    ROWS = (('Fixed-L', r'(Fixed \$L\$\s*&\s*)[\d.]+(\s*&\s*)[\d.]+' + TAIL),
            ('Fixed-F', r'(Fixed \$F\$ \(LDPC \+ 16-QAM\)\s*&\s*)[\d.]+(\s*&\s*)[\d.]+' + TAIL),
            ('Fixed-C256', r'(Fixed \$C_\{256\}\$ \(LDPC \+ 256-QAM\)\s*&\s*)[\d.]+(\s*&\s*)[\d.]+' + TAIL),
            ('oracle', r'(Channel-aware oracle \(masked\)\s*&\s*)[\d.]+(\s*&\s*)[\d.]+' + TAIL))
    out, last = [], 0
    for a, b, split in spans:
        out.append(block[last:a])
        seg = block[a:b]
        g = fx[fx.split == split].set_index('policy')
        for pol, pat in ROWS:
            if pol in g.index:
                f1, pay = float(g.loc[pol, 'F1']), float(g.loc[pol, 'payload_msym'])
                seg, n = re.subn(pat, lambda mm: (f'{mm.group(1)}{f1:.4f}{mm.group(2)}{pay:.3f}'
                                                  f'{mm.group(3)}{100 * pay / B_F:.1f}'
                                                  f'{mm.group(4)}'), seg, count=1)
                if n != 1:
                    raise SystemExit(f'tab:gen_headline: the {pol} row of the {split} block did '
                                     'not match -- a generator that silently rewrites nothing is '
                                     'how the oracle row stayed retired (R23-8)')
        out.append(seg)
        last = b
    out.append(block[last:])
    return tex[:m.start(1)] + ''.join(out) + tex[m.end(1):]


def sub_once(tex, pattern, repl, what):
    """re.sub that REFUSES to match nothing.

    R23-8: the caption substitution below targeted a sentence form that no longer existed in
    main.tex, so it had been rewriting nothing on every run while reporting success -- which is how
    the retired 0.158--0.251 Msym / 16--25% range survived in observation (iii).
    """
    out, n = re.subn(pattern, repl, tex)
    if n != 1:
        raise SystemExit(f'{what}: pattern matched {n} times, expected exactly 1 -- '
                         'the generator is not writing what it claims to write (R23-8)')
    return out


def observation_iii(tex):
    """Observation (iii) of sec:true_e2e: per-split channel-use range and share of Fixed F."""
    r = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
    seg = []
    for split, label in (('validate', 'on validate'), ('test', 'on the scene-disjoint test split'),
                         ('culver', 'on Culver-City')):
        g = r[r.split == split]
        seg.append((float(g.B_RF.min()), float(g.B_RF.max()), label))
    pay = (f'${seg[0][0]:.5f}$--${seg[0][1]:.5f}$~Msym/frame {seg[0][2]}, '
           f'${seg[1][0]:.5f}$--${seg[1][1]:.5f}$ {seg[1][2]} and '
           f'${seg[2][0]:.5f}$--${seg[2][1]:.5f}$ {seg[2][2]} across the three budgets')
    sh = ', '.join(f'${100 * lo / B_F:.1f}$--${100 * hi / B_F:.1f}\\%$' for lo, hi, _ in seg[:2])
    sh += f' and ${100 * seg[2][0] / B_F:.1f}$--${100 * seg[2][1] / B_F:.1f}\\%$'
    return sub_once(
        tex,
        r"\(iii\) Averaged over all channel states the selector's channel use is .*?of Fixed \$F\$,",
        lambda _m: ("(iii) Averaged over all channel states the selector's channel use is "
                    f'{pay}, i.e.\\ {sh} of Fixed $F$,'),
        'observation (iii)')


def ablation_body():
    """tab:ablation: the feature-ablation variants on test at B_max=0.20, from the CSVs."""
    d = pd.read_csv(os.path.join(ROOT, 'results/sensitivity/feature_ablation.csv'))
    fx = pd.read_csv(os.path.join(ROOT, 'results/main/fixed_references.csv'))
    g = d[(d.split == 'test') & (d.budget == 0.2)].set_index('variant')
    fl = fx[(fx.split == 'test') & (fx.policy == 'Fixed-L')].iloc[0]
    best = max(float(g.loc[v, 'F1']) for v in ('channel_only', 'task_only', 'combined'))
    def cell(v):
        f1 = float(g.loc[v, 'F1'])
        return f'\\textbf{{{f1:.5f}}}' if abs(f1 - best) < 1e-12 else f'{f1:.5f}'
    rows = [
        f"Channel only ($\\hat\\gamma,c$)        & 2  & {cell('channel_only')} & "
        f"{float(g.loc['channel_only', 'payload']):.5f} \\\\",
        f"Perception cues only                 & 21 & {cell('task_only')} & "
        f"{float(g.loc['task_only', 'payload']):.5f} \\\\",
        f"Full (all features)                  & 23 & {cell('combined')} & "
        f"{float(g.loc['combined', 'payload']):.5f} \\\\",
        f"SNR-threshold ($\\tau^\\star$)          & -- & "
        f"{float(g.loc['tau_reference', 'F1']):.5f} & "
        f"{float(g.loc['tau_reference', 'payload']):.5f} \\\\",
        '\\midrule',
        f"Fixed $L$                            & -- & {float(fl.F1):.5f} & "
        f"{float(fl.payload_msym):.5f} \\\\",
    ]
    return '\n'.join(rows) + '\n'


def splice(tex, label, body):
    m = re.search(r'(\\label\{' + re.escape(label) + r'\}.*?\\midrule\n)(.*?)(\\bottomrule)',
                  tex, re.S)
    if not m:
        raise SystemExit(f'{label}: table body not found')
    return tex[:m.start(2)] + body + tex[m.end(2):]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='print the bodies, write nothing')
    a = ap.parse_args()
    tex = open(TEX, encoding='utf-8').read()
    hb, ab = headline_body(), agg_body()
    if a.check:
        print('=== tab:headline ===');     print(hb)
        print('=== tab:headline_agg ==='); print(ab)
        return 0
    tex = splice(tex, 'tab:headline', hb)
    tex = splice(tex, 'tab:headline_agg', ab)
    tex = splice(tex, 'tab:ablation', ablation_body())
    tex = gen_headline_baselines(tex)
    tex = observation_iii(tex)
    # R23-8: this substitution targeted a sentence form main.tex no longer contains, so it rewrote
    # nothing on every run. The sentence it was meant to own is observation (iii), which is now
    # generated by observation_iii() above through sub_once(), and the dead pattern is removed.
    open(TEX, 'w', encoding='utf-8').write(tex)
    # cells this generator DERIVED (regime means): they are not stored anywhere, so the table-cell
    # gate consults this list instead of failing on them.
    derived = sorted({c for row in hb.split('\n') for c in re.findall(r'(?<![\d.])\d+\.\d{2,6}(?![\d])', row)})
    json.dump({'schema': 'catosg-derived-table-cells/1',
               'note': 'regime means over the AWGN SNR points below / at-and-above the measured knee',
               'tab:headline': derived},
              open(os.path.join(ROOT, 'results/provenance/DERIVED_TABLE_CELLS.json'), 'w'), indent=2)
    print('tab:headline, tab:headline_agg (incl. the masked-oracle row) and tab:ablation written '
          'from the frozen CSVs; observation (iii) regenerated through sub_once()')
    return 0


if __name__ == '__main__':
    sys.exit(main())
