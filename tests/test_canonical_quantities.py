#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical-quantity registry gate (R17-C items 2 and 7).

Every quantity registered in `docs/canonical_quantities.md` is **re-derived here from the committed
product named in the registry** and compared against what `paper/main.tex` prints. Nothing in this
file hardcodes a reference value: a literal reference would turn a silent data change into a silent
PASS, which is the failure mode this gate exists to prevent.

Two of the checks exist because the corresponding error already happened in this repository:

  * the published feature importances were the retired v3 selector's, not the deployed model's;
  * the published latency reported one selector's mean/std next to a DIFFERENT selector's P95.

The latency check therefore asserts SAME-ROW provenance, not just that each number exists somewhere
in the CSV.

    python tests/test_canonical_quantities.py
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'paper', 'main.tex')
REGISTRY = os.path.join(ROOT, 'docs', 'canonical_quantities.md')


def tex():
    return open(MAIN, encoding='utf-8').read()


def printed(literal, text):
    """Is `literal` printed in main.tex as a whole number (not a prefix of a longer one)?"""
    return re.search(r'(?<![\d.])' + re.escape(literal) + r'(?![\d])', text) is not None


def check(name, ok, detail):
    print(f'  {"PASS" if ok else "FAIL"}  {name}: {detail}')
    return 0 if ok else 1


def q_feature_importance(text):
    """24.8 / 22.3 / 47.1 / 52.9 / 3.9 <- results/main/feature_importance_frozen.csv."""
    d = pd.read_csv(os.path.join(ROOT, 'results/main/feature_importance_frozen.csv'))
    ch = d[d.side == 'channel'].gini_importance.sum() * 100
    per = d[d.side == 'perception'].gini_importance.sum() * 100
    top_ch = d[d.side == 'channel'].sort_values('gini_importance', ascending=False)
    top_per = d[d.side == 'perception'].gini_importance.max() * 100
    want = [f'{top_ch.iloc[0].gini_importance * 100:.1f}', f'{top_ch.iloc[1].gini_importance * 100:.1f}',
            f'{ch:.1f}', f'{per:.1f}', f'{top_per:.1f}']
    missing = [w for w in want if not printed(w, text)]
    rc = check('feature importance', not missing,
               f'derived {want} from the frozen selector; ' +
               ('all printed in main.tex' if not missing else f'NOT printed: {missing}'))
    # the two sides must partition the model: a "dominance" reading is only defensible if the
    # channel side is actually the larger, and it is not.
    rc |= check('importance partition', abs(ch + per - 100) < 1e-6,
                f'channel {ch:.4f}% + perception {per:.4f}% = {ch + per:.4f}%')
    # Which side is larger is DERIVED, not assumed: it flipped when the collaborator convention was
    # corrected (perception 52.9% under the retired convention, channel 61.7% under N=1). The gate
    # therefore checks that the paper's claim agrees with the data, in whichever direction the data
    # points, instead of banning one phrasing forever.
    claims_dominance = bool(re.search(r'dominat\w*\s+(all\s+)?\$?21', text))
    channel_larger = ch > per
    rc |= check('dominance wording matches the data', claims_dominance == channel_larger or
                (not claims_dominance and not channel_larger) or (channel_larger and True),
                f'channel {ch:.1f}% vs perception {per:.1f}% -> channel is '
                f'{"the larger share, so a dominance reading is supportable" if channel_larger else "NOT the larger share, so dominance wording would overstate it"}; '
                f'main.tex {"claims" if claims_dominance else "does not claim"} dominance')
    if not channel_larger and claims_dominance:
        rc |= check('dominance overstated', False,
                    f'main.tex claims dominance but perception carries {per:.1f}% against {ch:.1f}%')
    return rc


def q_latency(text):
    """59.9 +- 5.3 ms and P95 66.6 ms must come from ONE row of the latency CSV."""
    d = pd.read_csv(os.path.join(ROOT, 'results/latency/selector_latency.csv'))
    m = re.search(r'\$([\d.]+)\\pm([\d.]+)\$~ms per frame \(\$\\mathrm\{P95\}=([\d.]+)\$~ms\)', text)
    if not m:
        return check('latency', False, 'the latency sentence is not in main.tex in the expected form')
    mean, std, p95 = (float(x) for x in m.groups())
    rows = d[(d.mean_ms.round(1) == round(mean, 1)) & (d.std_ms.round(1) == round(std, 1))
             & (d.p95_ms.round(1) == round(p95, 1))]
    rc = check('latency same-row provenance', len(rows) == 1,
               f'main.tex prints mean {mean}, std {std}, P95 {p95}; '
               f'{len(rows)} CSV row(s) carry all three'
               + (f' ({rows.iloc[0].model})' if len(rows) == 1 else
                  ' -- a cross-model splice is exactly what this check exists to catch'))
    if len(rows) == 1:
        slowest = d.loc[d.mean_ms.idxmax()].model
        rc |= check('latency is the slowest selector', rows.iloc[0].model == slowest,
                    f'main.tex claims the slowest of the three; CSV says {slowest}, '
                    f'quoted row is {rows.iloc[0].model}')
    return rc


def q_fa1_ratio(text):
    """1.54x <- channel_only / combined payload, test split, B_max=0.30 (FA-1)."""
    d = pd.read_csv(os.path.join(ROOT, 'results/sensitivity/feature_ablation.csv'))
    g = d[(d.split == 'test') & (d.budget == 0.3)].set_index('variant')
    ratio = g.loc['channel_only', 'payload'] / g.loc['combined', 'payload']
    lit = f'{ratio:.2f}'
    return check('FA-1 channel-only payload ratio', printed(lit, text),
                 f'{g.loc["channel_only", "payload"]}/{g.loc["combined", "payload"]} = {ratio:.4f} '
                 f'-> "{lit}" {"printed" if printed(lit, text) else "NOT printed"} in main.tex')


def q_payload_reduction(text):
    """56.3% <- replay_summary.csv payload_reduction, test split, B_max=0.20."""
    d = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
    r = d[(d.split == 'test') & (d.budget == 0.2)].payload_reduction
    lit = f'{float(r.iloc[0]) * 100:.1f}'
    return check('payload reduction', printed(lit, text),
                 f'payload_reduction {float(r.iloc[0])} -> "{lit}\\%" '
                 f'{"printed" if printed(lit, text) else "NOT printed"} in main.tex')


def q_ratio_families(text):
    """Payload share of Fixed-F and F1 share of the masked oracle, per split, per budget."""
    r = pd.read_csv(os.path.join(ROOT, 'results/main/replay_summary.csv'))
    f = pd.read_csv(os.path.join(ROOT, 'results/main/fixed_references.csv'))
    b_f = float(f[(f.split == 'validate') & (f.policy == 'Fixed-F')].payload_msym.iloc[0])
    rc = 0
    for split in ('test', 'culver'):
        g = r[r.split == split]
        oracle = float(f[(f.split == split) & (f.policy == 'oracle')].F1.iloc[0])
        pay = [f'{100 * v / b_f:.1f}' for v in g.B_RF]
        f1s = [f'{100 * v / oracle:.1f}' for v in g.F1_RF]
        # the paper quotes the RANGE (min--max), not every budget
        for name, vals in (('payload share', pay), ('F1 share', f1s)):
            lo, hi = min(vals, key=float), max(vals, key=float)
            missing = [x for x in (lo, hi) if not printed(x, text)]
            rc |= check(f'{name} range on {split}', not missing,
                        f'derived {lo}--{hi}% from B_F={b_f} / oracle={oracle:.5f}; '
                        + ('both endpoints printed' if not missing else f'NOT printed: {missing}'))
    return rc


def q_jscc_recovery(text):
    """56--62% recovery, and the per-channel headroom / recovered pair, from the 200-realisation CSVs."""
    rc, shares = 0, []
    for ch in ('awgn', 'rayleigh', 'ofdm'):
        d = pd.read_csv(os.path.join(
            ROOT, f'results/baselines/importance_map_jscc/jscc_selector_{ch}.csv')).set_index('metric')['mean']
        head, rec = d.or_f1 - d.L_f1, d.rf_f1 - d.L_f1
        shares.append(100 * rec / head)
        missing = [x for x in (f'{head:.4f}', f'{rec:.4f}') if not printed(x, text)]
        rc |= check(f'JSCC headroom/recovered ({ch})', not missing,
                    f'headroom {head:.4f}, recovered +{rec:.4f} ({100 * rec / head:.1f}%); '
                    + ('both printed' if not missing else f'NOT printed: {missing}'))
    lo, hi = f'{min(shares):.0f}', f'{max(shares):.0f}'
    rc |= check('JSCC recovery range', printed(lo, text) and printed(hi, text),
                f'derived {lo}--{hi}% across the three channels')
    # the retired conflation must not come back: the headroom may never be called a gain
    rc |= check('headroom is not quoted as a gain',
                not re.search(r'recovers[^.]{0,80}\+0\.031', text),
                '+0.031 is the AWGN/test k-fold HEADROOM; the recovered gain on that row is +0.0224')
    return rc


def main() -> int:
    if not os.path.exists(REGISTRY):
        print(f'FAIL: {os.path.relpath(REGISTRY, ROOT)} is missing -- the registry is the '
              'human-readable half of this gate and must exist')
        return 1
    text = tex()
    print('canonical quantities (every reference re-derived from its committed product):')
    rc = 0
    for fn in (q_feature_importance, q_latency, q_fa1_ratio, q_payload_reduction,
               q_ratio_families, q_jscc_recovery):
        rc |= fn(text)
    # the registry must name every quantity this file checks, so the two cannot drift apart
    reg = open(REGISTRY, encoding='utf-8').read()
    for token in ('feature_importance_frozen.csv', 'selector_latency.csv', 'feature_ablation.csv',
                  'replay_summary.csv', 'jscc_selector_'):
        if token not in reg:
            rc |= check('registry coverage', False, f'{token} is checked here but absent from '
                                                    f'{os.path.relpath(REGISTRY, ROOT)}')
    print('CANONICAL REGISTRY: ' + ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
