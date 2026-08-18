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
| R26-1/2 | 10 | the two FINDINGS discharged (easy-stratum re-read, delivery-semantics product) |
| R33 | 4 | four subsections moved to the supplementary document, so their literals left the scanned text; and the new `bound_in_own_csv()` category verifies below-floor literals against the CSV their own ledger row names, which retired most of the register |

Every remaining entry is a floor effect, not a finding.

- `paper/main.tex:423` `0.58` -- below the verification floor; the claim row is bound to `r10c_missed_e_cost.csv` and the value is a DERIVED cost/delta ratio.
- `paper/main.tex:423` `0.61` -- below the verification floor; same row as 0.58.
- `paper/main.tex:423` `0.44` -- below the verification floor; same row as 0.58.
- `paper/main.tex:423` `0.47` -- below the verification floor; same row as 0.58.
