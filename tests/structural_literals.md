# Structural numeric literals (R23-15)

Literals in the delivered text that are NOT measurements: standard constants, protocol parameters,
units, hyperparameters, years. `tests/test_numeric_literals.py` reads this table; every row needs a
reason, so adding one is a reviewable diff rather than a code change.

| literal | why it is structural |
|---|---|
| `1.98` | the declared feature-message source budget in Mbit (PROTOCOL Eq.(7)); re-derived end-to-end by `tests/test_payload.py` link (0a), not by this gate |
| `3.96` | coded bits = 1.98 / rate-1/2, the same payload chain; `tests/test_payload.py` checks it against Eq.(7) as printed |
| `0.999` | the feasibility-mask constant (PROTOCOL sec 4); a protocol parameter, identical in `grid_builder`, `fixed_references` and the R23-C sensitivities |
| `0.01` | a swept SETTING, not a measurement: the smallest point of the pre-registered `BLER_L` grid {0.01, 0.05, 0.10} (Change-log R23-C item 2) |
| `0.775` | EXTERNAL REFERENCE: OpenCOOD model-zoo published AP@0.7 for the SECOND late-fusion checkpoint, quoted from the upstream repository's model zoo table; recorded 2026-08-18. Our reproduction (0.7752) is bound to `results/manifests/P4B_VERIFICATION_late.json` |
| `0.682` | EXTERNAL REFERENCE: the same zoo table's AP@0.5 for that checkpoint; recorded 2026-08-18. Our reproduction (0.6822) is bound to the same manifest |
