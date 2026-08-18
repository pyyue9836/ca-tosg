# Uncovered numeric literals -- the R23-15 debt register

`tests/test_numeric_literals.py` requires every decimal literal in the delivered text to be covered
by a verified binding: a claim literal confirmed inside the CSV its own ledger row names, a located
or declared-derived table cell, a registry-derived quantity, or a structural entry in
`tests/structural_literals.md`.

The literals below are **not** covered. The gate ratchets on this file: anything NEW fails, and the
register may only get shorter.

| batch | entries | what changed |
|---|---|---|
| R23-15 (opened) | 101 | first enumeration |
| R24-3 | 12 | sign normalisation in the verified set; README + `docs/model_zoo.md` cleared by the named-source rule and by rebuilding the README model-zoo table from the frozen manifest; protocol constants and two EXTERNAL REFERENCE values moved to `structural_literals.md`; three "analytic -- no result file" rows bound to real products |
| R26-1/2 | 10 | the two FINDINGS discharged, not excused: the easy-stratum sentence was re-read from `difficulty_frozen.csv` (the mis-bound `0.0040` is retired and fingerprinted) and the delivery-semantics sentence now binds to its own product `delivery_semantics_bracket.csv` (the SComCP report mis-binding is gone, and the frame count was wrong too: 964, not 690) |

Every remaining entry is a **floor effect**, not a finding: `distinctive()` skips literals with
fewer than 3 decimals and fewer than 3 significant digits, so `p6_numbers_vs_csv` never checks them.
Their claim rows are bound; the literals themselves are not individually verified.

- `paper/main.tex:440` `0.67` -- below the verification floor: `distinctive()` skips literals with <3 decimals and <3 significant digits, so p6 never checks them. Bound at the CLAIM level to `PROVENANCE_qualitative.json`; the literal itself is unverified.
- `paper/main.tex:440` `0.95` -- below the verification floor (see 0.67); same claim row, same binding.
- `paper/main.tex:470` `0.58` -- below the verification floor; the claim row is bound to `r10c_missed_e_cost.csv` and the value is a DERIVED cost/delta ratio.
- `paper/main.tex:470` `0.61` -- below the verification floor; same row as 0.58.
- `paper/main.tex:470` `0.44` -- below the verification floor; same row as 0.58.
- `paper/main.tex:470` `0.47` -- below the verification floor; same row as 0.58.
- `paper/main.tex:880` `0.12` -- below the verification floor; rho_F=0.12 is the 2-decimal rounding of 0.1216 in `action_distribution.csv`.
- `paper/main.tex:949` `0.89` -- below the verification floor; the "flat at ~0.89" JSCC level is a rounded summary of a column in `two_regime_edge_clean.csv`.
- `paper/main.tex:991` `0.14` -- below the verification floor; JSCC C-request rate, prior-protocol arm.
- `paper/main.tex:991` `0.42` -- below the verification floor; JSCC C-request rate, prior-protocol arm.
- `paper/main.tex:1013` `0.89` -- below the verification floor; the "flat at ~0.89" JSCC level is a rounded summary of a column in `two_regime_edge_clean.csv`.
