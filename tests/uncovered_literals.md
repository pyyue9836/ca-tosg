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
| R24-3 | 12 | sign normalisation in the verified set (-30); README + `docs/model_zoo.md` cleared by the named-source rule and by rebuilding the README model-zoo table from the frozen manifest (-58); protocol constants and two EXTERNAL REFERENCE values moved to `structural_literals.md`; three "analytic -- no result file" rows bound to real products |

**Two of the remaining entries are findings, not floor effects** -- `0.0040` is bound to a CSV that
does not contain it, and `0.0003`'s evidence is a Markdown report. Both are flagged below and need a
ruling; neither is quietly retained.

- `paper/main.tex:436` `0.67` -- below the verification floor: `distinctive()` skips literals with <3 decimals and <3 significant digits, so p6 never checks them. Bound at the CLAIM level to `PROVENANCE_qualitative.json`; the literal itself is unverified.
- `paper/main.tex:436` `0.95` -- below the verification floor (see 0.67); same claim row, same binding.
- `paper/main.tex:466` `0.58` -- below the verification floor; the claim row is bound to `r10c_missed_e_cost.csv` and the value is a DERIVED cost/delta ratio.
- `paper/main.tex:466` `0.61` -- below the verification floor; same row as 0.58.
- `paper/main.tex:466` `0.44` -- below the verification floor; same row as 0.58.
- `paper/main.tex:466` `0.47` -- below the verification floor; same row as 0.58.
- `paper/main.tex:664` `0.0040` -- **MIS-BOUND, found by this gate (R24-3).** The claim row cites `results/sensitivity/robustness_frozen.csv`, which does NOT carry 0.0040. It escaped p6 because p6 never reached the row: its sentence walk and the ledger builder disagree on the id for this sentence. Needs a re-derivation or a sentence downgrade -- flagged, not silently kept.
- `paper/main.tex:829` `0.0003` -- evidence is `results/baselines/SCOMCP_FUSE_REPORT.md`, a narrative report, not a data product; p6 only follows .csv/.json, so the row is skipped. The value is absent from `scomcp.csv`. Needs a product emission or a sentence downgrade.
- `paper/main.tex:860` `0.12` -- below the verification floor; rho_F=0.12 is the 2-decimal rounding of 0.1216 in `action_distribution.csv`.
- `paper/main.tex:929` `0.89` -- below the verification floor; the "flat at ~0.89" JSCC level is a rounded summary of a column in `two_regime_edge_clean.csv`.
- `paper/main.tex:971` `0.14` -- below the verification floor; JSCC C-request rate, prior-protocol arm.
- `paper/main.tex:971` `0.42` -- below the verification floor; JSCC C-request rate, prior-protocol arm.
- `paper/main.tex:993` `0.89` -- below the verification floor; the "flat at ~0.89" JSCC level is a rounded summary of a column in `two_regime_edge_clean.csv`.
