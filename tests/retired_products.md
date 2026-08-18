# Retired products — present in the tree, NOT valid binding sources (R28-2)

A committed result file is not automatically evidence. These were produced under a superseded
convention or engine; they are kept because change-log entries and the corrigendum refer to them, but
a number in the delivered text may **not** be justified by them. `p6_numbers_vs_csv.canonical_corpus`
excludes every path listed here, so a claim bound to one of them reports as unlocated rather than
passing.

| product | why it is retired | what replaced it |
|---|---|---|
| `results/sensitivity/c256_dominance_verify.csv` | produced 2026-08-12, before the P0 single-collaborator corrigendum: its `frac_comp_ge_ego` / `frac_comp_lt_ego_and_tie` columns are full-collaborator fractions. They were still passing the C256 paragraph's `99.0 / 94.2 / 99.1%` and `0.7 / 4.2 / 0.9%` through the literal gate by percent-form matching (0.9899 ≈ 99.0%), which is how three retired families survived in one paragraph (R28-1). | nothing: the paragraph's argument is now physical-layer ordering plus the structurally-zero deployment count, and needs no fractions. The convention-independent columns (`n`, `n_selector_predictions`, `selector_C256_requests`) are re-derived as frames x 200 realisations. |
