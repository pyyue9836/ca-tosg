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
    """The channel-averaged payload range quoted in tab:headline's caption."""
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
    ROWS = (('Fixed-L', r'(Fixed \$L\$\s*&\s*)[\d.]+(\s*&\s*)[\d.]+'),
            ('Fixed-F', r'(Fixed \$F\$ \(LDPC \+ 16-QAM\)\s*&\s*)[\d.]+(\s*&\s*)[\d.]+'),
            ('Fixed-C256', r'(Fixed \$C_\{256\}\$ \(LDPC \+ 256-QAM\)\s*&\s*)[\d.]+(\s*&\s*)[\d.]+'))
    out, last = [], 0
    for a, b, split in spans:
        out.append(block[last:a])
        seg = block[a:b]
        g = fx[fx.split == split].set_index('policy')
        for pol, pat in ROWS:
            if pol in g.index:
                f1, pay = float(g.loc[pol, 'F1']), float(g.loc[pol, 'payload_msym'])
                seg = re.sub(pat, lambda mm: f'{mm.group(1)}{f1:.4f}{mm.group(2)}{pay:.3f}', seg,
                             count=1)
        out.append(seg)
        last = b
    out.append(block[last:])
    return tex[:m.start(1)] + ''.join(out) + tex[m.end(1):]


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
    tex = gen_headline_baselines(tex)
    # caption: the channel-averaged payload range, from the same replay
    lo, hi, plo, phi = headline_caption_numbers()
    tex = re.sub(r'channel-\\emph\{averaged\} \\method\{\} payload is \$[\d.]+\$--\$[\d.]+\$~Msym/frame '
                 r'across splits, i\.e\.\\ \$\d+\$--\$\d+\\%\$ of Fixed \$F\$',
                 f'channel-\\\\emph{{averaged}} \\\\method{{}} payload is ${lo:.3f}$--${hi:.3f}$~Msym/frame '
                 f'across splits, i.e.\\\\ ${plo:.0f}$--${phi:.0f}\\\\%$ of Fixed $F$', tex)
    open(TEX, 'w', encoding='utf-8').write(tex)
    # cells this generator DERIVED (regime means): they are not stored anywhere, so the table-cell
    # gate consults this list instead of failing on them.
    derived = sorted({c for row in hb.split('\n') for c in re.findall(r'(?<![\d.])\d+\.\d{2,6}(?![\d])', row)})
    json.dump({'schema': 'catosg-derived-table-cells/1',
               'note': 'regime means over the AWGN SNR points below / at-and-above the measured knee',
               'tab:headline': derived},
              open(os.path.join(ROOT, 'results/provenance/DERIVED_TABLE_CELLS.json'), 'w'), indent=2)
    print('tab:headline and tab:headline_agg written from the frozen CSVs; '
          f'caption payload range {lo:.3f}-{hi:.3f} Msym ({plo:.0f}-{phi:.0f}% of B_F)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
