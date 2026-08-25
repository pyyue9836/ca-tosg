#self+ Verify the C256 dominance IDENTITY programmatically from the per-frame CSVs. Writes nothing.
# The algebraic claim eff_C256 - eff_C16 = (comp - ego)(b16 - b256) is held to the SAME provenance bar as
# a numeric claim (verification-derive-not-hardcode): recompute both sides from the dataset columns, and
# derive the dominated-frame fraction from data (no literal). Symbol binding: eff = effective F1 =
# comp*(1-b)+ego*b ; b = frame BLER (probability, Sionna table) ; comp = compressed-model F1 (delivered) ;
# ego = ego-only F1 (fallback) ; all at the frame's frozen drawn SNR+channel.
"""R69-2: this script kept two things that had to go, and one that had to stay.

REMOVED -- the CSV write. Its output `results/sensitivity/c256_dominance_verify.csv` is a RETIRED
product: pre-corrigendum full-collaborator fractions, registered in `tests/retired_products.md` and
deleted from the tree in R67 (c). A live script able to rewrite a deleted retired product is a
resurrection hazard, and R67 (c) had already removed its regeneration job for the same reason.
`tests/test_no_retired_writes.py` now enforces that repo-wide.

REMOVED -- the 200-realisation deployed-selector C256 count. It loaded `data/selector_rf.pkl`, the
**v3** selector the P2 freeze superseded, so its "measured zero" was a v3-engine quantity. Under the
frozen protocol the deployed action set is {E, L, F}: C256 is not a class the frozen selectors can
predict at all, so the count is structurally zero by construction rather than by measurement, and
the frozen action mix is `results/main/action_distribution.csv`. Never blend engines.

KEPT -- the algebra. The identity and the dominance decomposition are convention-independent: they
follow from the effective-F1 definition and the per-frame columns, and hold under any collaborator
convention or selector. The delivered C256 paragraph states that identity, so it is live evidence for
a delivered sentence, which is why this file survives as a verifier rather than being archived.

Exits non-zero if any check fails. Artefact tier: needs `data/dataset_{split}_v3.csv`.

    python projects/ca_tosg/evaluation/verifiers/verify_c256_dominance.py
"""
import os
import sys

import numpy as np
import pandas as pd

D = os.path.join(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              '..', '..', '..', '..')), 'data')
SPLITS = ('validate', 'test', 'culver')


def main():
    missing = [sp for sp in SPLITS if not os.path.exists(f'{D}/dataset_{sp}_v3.csv')]
    if missing:
        # a gate that cannot verify must never report success
        print(f'CANNOT VERIFY: per-frame CSVs absent for {", ".join(missing)} -> {D}')
        return 1
    rows, bad = [], []
    for sp in SPLITS:
        d = pd.read_csv(f'{D}/dataset_{sp}_v3.csv')
        comp, ego = d.compressed_f1.to_numpy(), d.ego_f1.to_numpy()
        b16, b256 = d.bler_C16.to_numpy(), d.bler_C256.to_numpy()
        lhs = d.eff_f1_C256.to_numpy() - d.eff_f1_C16.to_numpy()      # from stored eff columns
        rhs = (comp - ego) * (b16 - b256)                             # algebraic identity
        id_max_err = float(np.abs(lhs - rhs).max())                   # identity holds if ~0
        frac_dom = float((d.eff_f1_C256.to_numpy() <= d.eff_f1_C16.to_numpy() + 1e-12).mean())
        frac_comp_ge_ego = float((comp >= ego).mean())                # dominance mechanism condition
        frac_comp_lt_ego = float((comp < ego).mean())
        tie = np.abs(b16 - b256) <= 1e-12                             # b16 == b256 (flat-dead / both delivered)
        frac_gap = float(((comp < ego) & tie).mean())                 # the EXACT dominated-minus-comp_ge_ego gap
        # internal consistency: dominated set = {comp>=ego} U {tie}; disjoint decomposition
        # frac_dom = frac_comp_ge_ego + frac(comp<ego & tie). Checked, never hand-arithmetic.
        if abs(frac_dom - (frac_comp_ge_ego + frac_gap)) >= 1e-9:
            bad.append(f'{sp}: decomposition {frac_dom} != {frac_comp_ge_ego} + {frac_gap}')
        if id_max_err >= 1e-9:
            bad.append(f'{sp}: identity max|err| = {id_max_err:g}, expected ~0')
        b256_ge_b16 = bool((b256 >= b16 - 1e-12).all())
        if not b256_ge_b16:
            bad.append(f'{sp}: b256 >= b16 does not hold everywhere -- the sign argument fails')
        rows.append(dict(split=sp, n=len(d), identity_max_abs_err=round(id_max_err, 12),
                         frac_C256_dominated=round(frac_dom, 4),
                         frac_comp_ge_ego=round(frac_comp_ge_ego, 4),
                         frac_comp_lt_ego=round(frac_comp_lt_ego, 4),
                         frac_comp_lt_ego_and_tie=round(frac_gap, 4),
                         b256_ge_b16_everywhere=b256_ge_b16))
    print(pd.DataFrame(rows).to_string(index=False))
    print('\nidentity eff_C256-eff_C16 == (comp-ego)(b16-b256): max|err| ~0 across splits confirms '
          'the symbol binding.')
    print('frac_C256_dominated == frac_comp_ge_ego (given b256>=b16 everywhere): dominance IS '
          'conditional on comp>=ego.')
    print('\nNOTE (R69-2): the fractions above are PRINTED, never written to a file. The CSV this '
          'script used to write is a retired product (tests/retired_products.md) and its fractions '
          'were full-collaborator; the delivered paragraph rests on the physical-layer ordering plus '
          'C256 not being a class of the frozen action set {E, L, F}.')
    for b in bad:
        print(f'  FAIL {b}')
    print('C256 DOMINANCE VERIFIER: ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
