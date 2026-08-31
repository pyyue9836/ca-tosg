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

TEX = os.path.join(ROOT, 'paper/archive/manuscript_frozen.tex')
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


def gen_headline_policy_rows(tex):
    """R40: the CA-TOSG and tau rows of tab:gen_headline, per split, from replay_summary.csv.

    Only the FIXED rows of this table were generator-owned. The test block happened to be current;
    the Culver block was not -- its selector and tau F1 values (0.87230/0.87491, 0.87355/0.88340,
    0.88286/0.88740) match no committed product and came from the retired 200-realisation engine.
    Nothing caught it because the table sat in the supplementary, which no numeric gate scanned
    until this batch.
    """
    r = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
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
    out, last = [], 0
    for a, b, split in spans:
        out.append(block[last:a])
        seg = block[a:b]
        g = r[r.split == split]
        for _, row in g.iterrows():
            pat = (r'(\\quad \\method\{\} \$B_\{\\max\}\{=\}'
                   + f'{row.budget:.2f}' + r'\$ / \$\\tau\^\\star\$\s*&\s*)'
                   r'[\d.]+ / [\d.]+(\s*&\s*)[\d.]+ / [\d.]+\s*&\s*\$[\d.]+\\%'
                   r'(?:\$ / \$| / )[\d.]+\\%\$')
            def rep(mm, row=row):
                # canonical form, so a second run matches what the first wrote
                return (f'{mm.group(1)}{row.F1_RF:.5f} / {row.F1_tau:.5f}{mm.group(2)}'
                        f'{row.B_RF:.4f} / {row.B_tau:.4f} & '
                        f'${100 * row.B_RF / B_F:.1f}\\% / {100 * row.B_tau / B_F:.1f}\\%$')
            seg, n = re.subn(pat, rep, seg, count=1)
            if n != 1:
                raise SystemExit(f'tab:gen_headline: the {split} B_max={row.budget:.2f} policy row '
                                 f'did not match ({n} hits) -- the generator is not writing what it '
                                 'claims to write (R40-4)')
        out.append(seg)
        last = b
    out.append(block[last:])
    return tex[:m.start(1)] + ''.join(out) + tex[m.end(1):]


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
    pay = (f'${seg[0][0]:.5f}$--${seg[0][1]:.5f}$~Msym/frame on validate, '
           f'${seg[1][0]:.5f}$--${seg[1][1]:.5f}$ on test and '
           f'${seg[2][0]:.5f}$--${seg[2][1]:.5f}$ on Culver-City')
    sh = ', '.join(f'${100 * lo / B_F:.1f}$--${100 * hi / B_F:.1f}\\%$' for lo, hi, _ in seg[:2])
    sh += f' and ${100 * seg[2][0] / B_F:.1f}$--${100 * seg[2][1] / B_F:.1f}\\%$'
    return sub_once(
        tex,
        r"\(iii\) Channel-averaged, the selector spends .*?of Fixed \$F\$---",
        lambda _m: ('(iii) Channel-averaged, the selector spends '
                    f'{pay}---{sh} of Fixed $F$---'),
        'observation (iii)')


def feature_object_ratios(tex):
    """R48-3: the feature/object payload ratio, stated for all four conventions, never typed.

    The paper said "the feature-level message is therefore ~82x the object-level payload", one number
    with no convention attached -- and 82 is the SOURCE ratio, while the channel-use ratio the rest of
    the paper spends is 41.25. Once three deployed-side conventions exist (R47-2), a single ratio is
    not a fact about the system, it is a fact about an unstated accounting choice.
    """
    conv = pd.read_csv(os.path.join(ROOT, 'results/channel/payload_conventions.csv'))
    pp = conv[conv.backbone == 'pointpillar'].set_index('convention')
    tex_src = open(TEX, encoding='utf-8').read()
    b_l_mbit = float(re.search(r'B_L \\approx 27 \\times 110 \\times 8 \\approx ([0-9.]+)', tex_src).group(1))
    b_l_msym = float(re.search(r'B_L = ([0-9.]+)\$~Msym', tex_src).group(1))
    b_c_mbit = float(re.search(r'fixed source budget of \$B_C \\approx ([0-9.]+)\$~Mbit', tex_src).group(1))
    b_f_msym = float(re.search(r'B_\{C_\{16\}\} \\approx ([0-9.]+)\$~Msym', tex_src).group(1))
    src = b_c_mbit / b_l_mbit
    declared = b_f_msym / b_l_msym
    pre = float(pp.loc['pre_compression', 'B_F_msym_16qam']) / b_l_msym
    bott = float(pp.loc['transmitted_bottleneck', 'B_F_msym_16qam']) / b_l_msym
    return sub_once(
        tex,
        # the pattern must match the generator's OWN output too, or the second run rewrites
        # nothing and --check reports a dead pattern (R23-8's failure mode, caught by R43-4).
        r'The feature-level message is therefore .*?(?:the object-level payload\.|conventions respectively\.)',
        lambda _m: (f'The feature-level message is therefore ${src:.1f}\\times$ the object-level '
                    f'payload at the source, and ${declared:.2f}\\times$, ${pre:.1f}\\times$ or '
                    f'${bott:.1f}\\times$ in channel uses under the declared, pre-compression and '
                    f'bottleneck conventions respectively.'),
        'feature/object ratios')


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


def transform():
    """Run every substitution in memory and return (main_tex, supplementary_tex, derived_cells).

    R43-4: `--check` used to print the two table bodies and return BEFORE any splice() or sub_once()
    ran, so the one failure mode these helpers exist to catch -- a pattern that stopped matching the
    delivered text -- was invisible until someone re-ran the generator for real. That is exactly how
    R41's compression of observation (iii) went unnoticed for a batch. The transform is therefore
    factored out: `--check` now runs it and compares against what is on disk, and every non-1 match
    raises through splice()/sub_once() in check mode too.
    """
    tex = open(TEX, encoding='utf-8').read()
    supp_p = os.path.join(ROOT, 'paper/archive/supplementary_frozen.tex')
    # V2-R47 B: the archived supplementary is frozen and always present. The old
    # `if os.path.exists(...) else None` silently degraded to 'nothing to check' if the file
    # moved -- a gate that cannot fail. A missing frozen document is now a failure.
    supp = open(supp_p, encoding='utf-8').read()
    hb, ab = headline_body(), agg_body()
    tex = splice(tex, 'tab:headline', hb)
    # R42-1: tab:headline_agg moved to the supplementary; splice it wherever it now lives, the same
    # rule tab:ablation has had since R40. A generator that silently writes nothing is worse than a
    # missing one, so the else-branch raises through splice() if the label is in neither document.
    if 'tab:headline_agg' in tex:
        tex = splice(tex, 'tab:headline_agg', ab)
    else:
        supp = splice(supp, 'tab:headline_agg', ab)
    # R40: tab:ablation moved to the supplementary in R35; splice it wherever it now lives
    if 'tab:ablation' in tex:
        tex = splice(tex, 'tab:ablation', ablation_body())
    elif supp is not None:
        supp = splice(supp, 'tab:ablation', ablation_body())
    tex = observation_iii(tex)
    tex = feature_object_ratios(tex)
    # R40: tab:gen_headline moved to the supplementary document, so its generator runs there
    if supp is not None:
        supp = gen_headline_baselines(supp)
        supp = gen_headline_policy_rows(supp)
    else:
        tex = gen_headline_baselines(tex)
    # cells this generator DERIVED (regime means): they are not stored anywhere, so the table-cell
    # gate consults this list instead of failing on them.
    derived = sorted({c for row in hb.split('\n') for c in re.findall(r'(?<![\d.])\d+\.\d{2,6}(?![\d])', row)})
    # R23-15: the share-of-B_F column is a DERIVED ratio (payload / 0.99 x 100) that appears in no
    # CSV cell, and so is every cell this generator computes for tab:gen_headline and tab:ablation.
    # Declaring them is what makes the literal-coverage gate able to distinguish a derived cell from
    # an unverified one; they were previously indistinguishable.
    # R40: the share-of-B_F column is derived wherever its table lives -- tab:headline_agg in the
    # main file, tab:gen_headline in the supplementary since R36.
    shares = set()
    for doc, lab in ((tex, 'tab:headline_agg'), (supp or '', 'tab:headline_agg'),
                     (tex, 'tab:gen_headline'), (supp or '', 'tab:gen_headline')):
        m = re.search(r'\\label\{' + lab + r'\}(.*?)\\end\{tabular\}', doc, re.S)
        if m:
            shares |= set(re.findall(r'\$?(\d+\.\d+)\\%', m.group(1)))
    cells = {'schema': 'catosg-derived-table-cells/1',
             'note': 'regime means over the AWGN SNR points below / at-and-above the measured '
                     'knee; and the share-of-B_F ratio column (payload / 0.99 x 100)',
             'tab:headline': derived,
             'tab:gen_headline_shares': sorted(shares)}
    return tex, supp, cells


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true',
                    help='run every substitution and FAIL if any of them would change the delivered '
                         'text (or no longer matches it); write nothing')
    a = ap.parse_args()
    tex, supp, cells = transform()                  # splice()/sub_once() raise on a non-1 match
    supp_p = os.path.join(ROOT, 'paper/archive/supplementary_frozen.tex')
    cells_p = os.path.join(ROOT, 'results/provenance/DERIVED_TABLE_CELLS.json')
    if a.check:
        stale = [p for p, want in ((TEX, tex), (supp_p, supp),
                                   (cells_p, json.dumps(cells, indent=2) + '\n'))
                 if want is not None and open(p, encoding='utf-8').read() != want]
        if stale:
            print('GENERATOR CHECK FAIL [build_paper_tables]: would rewrite '
                  + ', '.join(os.path.relpath(p, ROOT) for p in stale)
                  + ' -- the delivered text is not what the frozen CSVs produce')
            return 1
        print('GENERATOR CHECK PASS [build_paper_tables]: every pattern matched exactly once and '
              'the delivered text already equals the generated text')
        return 0
    # V2-R47 B: TEX and supp_p are FROZEN archived documents. `--check` (what the gate runs)
    # stays exactly as strict as before; the write path is closed, because the only thing it
    # could now do is edit a document the stop-work amendment forbids editing.
    print('REFUSING TO WRITE: %s and %s are frozen archived documents (see\n'
          '  docs/STOP_WORK_v1_freeze.md, amendment V2-R47 A-2). Run with --check.'
          % (os.path.relpath(TEX, ROOT), os.path.relpath(supp_p, ROOT)))
    return 1


if __name__ == '__main__':
    sys.exit(main())
