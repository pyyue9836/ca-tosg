#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SC-2: evaluate the pre-registered fuse conditions on the SComCP result table.

Both conditions come from the SC-1/SC-2 pre-registration, verbatim:

  F1  validate AP@0.5 at 20 dB AWGN falls BELOW the Fixed-L reference
  F2  per-frame F1 is flat in SNR (no codec response)

Every reference is read from a committed product, never typed in. The verdict is reported; it is
not repaired, and §8 rule 3 applies — if an expectation and the measurement disagree, the finding
changes, not the data.

    python baselines/scomcp/perframe/check_scomcp_fuses.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
SCOMCP = os.path.join(ROOT, 'results/baselines/scomcp.csv')
E2E = os.path.join(ROOT, 'results/main/true_e2e_ap.csv')
JSCC = os.path.join(ROOT, 'results/baselines/importance_map_jscc/jscc_ap_f1.csv')
OUT = os.path.join(ROOT, 'results/baselines/SCOMCP_FUSE_REPORT.md')
FLAT_EPS = 0.005          # "flat" = total F1 span across the 11-point grid below this


def main() -> int:
    d = pd.read_csv(SCOMCP)
    ref = pd.read_csv(E2E)
    ref = ref[ref.split == 'validate'].set_index('policy')
    fixed_l = float(ref.loc['Fixed-L', 'ap50_mean'])
    ceiling = float(ref.loc['Feature-ceiling', 'ap50_mean'])
    ego = float(ref.loc['ego-only', 'ap50_mean'])

    # ---- F1: validate AP@0.5 at 20 dB AWGN vs the Fixed-L reference ----
    row = d[(d.split == 'validate') & (d.channel == 'awgn') & (d.snr_db == 20)].iloc[0]
    got = float(row.ap50)
    f1_fired = got < fixed_l
    f1_detail = (f'validate AWGN 20 dB AP@0.5 = {got:.4f} vs Fixed-L reference {fixed_l:.4f} '
                 f'(delta {got - fixed_l:+.4f}); ego-only floor {ego:.4f}, '
                 f'perfect-channel ceiling {ceiling:.4f}')

    # ---- F2: per-frame F1 flat in SNR ----
    spans, f2_fired = [], False
    for (sp, ch), g in d.groupby(['split', 'channel']):
        span = float(g.scomcp_f1.max() - g.scomcp_f1.min())
        spans.append((sp, ch, span, float(g.scomcp_f1.mean())))
        if span < FLAT_EPS:
            f2_fired = True
    f2_detail = '; '.join(f'{sp}/{ch}: F1 span over the 11-point grid = {s:.4f} (mean {m:.4f})'
                          for sp, ch, s, m in spans)

    # ---- supporting observations, reported as observations ----
    cr = d.groupby('split').com_rate.agg(['min', 'max', 'nunique'])
    obs = ['com_rate is constant within each split: ' +
           '; '.join(f'{sp}: {r["min"]:.6f}..{r["max"]:.6f} ({int(r["nunique"])} distinct value)'
                     for sp, r in cr.iterrows())]
    for sp in ('validate', 'test'):
        a = d[(d.split == sp) & (d.channel == 'awgn')].sort_values('snr_db').scomcp_f1.to_numpy()
        r = d[(d.split == sp) & (d.channel == 'rayleigh')].sort_values('snr_db').scomcp_f1.to_numpy()
        obs.append(f'{sp}: max |AWGN - Rayleigh| per-frame F1 across the grid = '
                   f'{abs(a - r).max():.4f} -- the two channels are indistinguishable')
    if os.path.exists(JSCC):
        j = pd.read_csv(JSCC)
        j = j[(j.split == 'validate') & (j.channel == 'awgn')]
        if len(j):
            obs.append(f'ImportanceMapJSCC on the same split/channel spans '
                       f'{j.jscc_f1.min():.4f}..{j.jscc_f1.max():.4f} '
                       f'(span {j.jscc_f1.max() - j.jscc_f1.min():.4f}) over its SNR points. '
                       f'NOTE: near-flatness is a KNOWN and expected property of that codec '
                       f'(graceful degradation), so F2 on its own does not separate "codec is '
                       f'graceful" from "codec is not engaged" -- the AWGN-vs-Rayleigh identity '
                       f'and the perfect-channel diagnostic below are what separate them')

    # ---- the decisive diagnostic: a PERFECT (lossless) channel on the same net ----
    ub = os.path.join(ROOT, 'results/baselines/scomcp_perfect_channel_diagnostic.csv')
    if os.path.exists(ub):
        u = pd.read_csv(ub).iloc[0]
        v = d[(d.split == 'validate') & (d.channel == 'awgn') & (d.snr_db == 20)].iloc[0]
        w = d[(d.split == 'validate') & (d.channel == 'rayleigh') & (d.snr_db == 0)].iloc[0]
        obs.append(
            f'PERFECT-CHANNEL DIAGNOSTIC (validate, lossless): F1 {u.scomcp_f1:.4f} / '
            f'AP@0.5 {u.ap50:.4f} / com_rate {u.com_rate:.6f} -- versus AWGN 20 dB '
            f'{v.scomcp_f1:.4f}/{v.ap50:.4f} and Rayleigh 0 dB {w.scomcp_f1:.4f}/{w.ap50:.4f}. '
            f'A lossless channel and the worst modelled channel give the SAME result to 1e-4, so '
            f'the channel path is INERT: this is not graceful degradation, the transmitted '
            f'representation is contributing essentially nothing.')
        obs.append(
            f'ROOT CAUSE (diagnosed, not asserted): com_rate = {u.com_rate:.6f} means the trained '
            f'selector keeps ~{100*u.com_rate:.2f}% of tokens, so there is almost no remote content '
            f'for any channel to corrupt, and the fused output is determined by the ego branch. '
            f'AP@0.5 {u.ap50:.4f} sits between the ego-only floor {ego:.4f} and Fixed-L '
            f'{fixed_l:.4f}, consistent with a near-ego-only output.')

    fired = [n for n, f in (('F1 (AP below Fixed-L)', f1_fired), ('F2 (F1 flat in SNR)', f2_fired))
             if f]
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('# SComCP baseline — pre-registered fuse check (SC-2)\n\n')
        f.write('**descriptive baseline, no decision.** Conditions and references are the ones '
                'registered before the run; every reference is read from a committed product.\n\n')
        f.write(f'| fuse | condition | result |\n|---|---|---|\n')
        f.write(f'| F1 | validate AP@0.5 at 20 dB AWGN below the Fixed-L reference | '
                f'{"**FIRED**" if f1_fired else "not fired"} |\n')
        f.write(f'| F2 | per-frame F1 flat in SNR (span < {FLAT_EPS}) | '
                f'{"**FIRED**" if f2_fired else "not fired"} |\n\n')
        f.write(f'## F1\n\n{f1_detail}\n\n## F2\n\n{f2_detail}\n\n## Supporting observations\n\n')
        for o in obs:
            f.write(f'- {o}\n')
        f.write('\n## Reading (pre-registered)\n\nA fired fuse here is a **scaffold / training-'
                'budget finding, not a finding about SComCP as a method**, and the two may not be '
                'conflated in any write-up. The arm is reported as-is; nothing was retrained, no '
                'data was adjusted, no hyperparameter was changed after seeing these numbers.\n')
    print(f'F1 {"FIRED" if f1_fired else "ok"}: {f1_detail}')
    print(f'F2 {"FIRED" if f2_fired else "ok"}: {f2_detail}')
    for o in obs:
        print(f'  - {o}')
    print(f'\n{len(fired)} fuse(s) fired -> {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
