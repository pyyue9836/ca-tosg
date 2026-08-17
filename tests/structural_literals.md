# Structural numeric literals (R23-15)

Literals in the delivered text that are NOT measurements: standard constants, protocol parameters,
units, hyperparameters, years. `tests/test_numeric_literals.py` reads this table; every row needs a
reason, so adding one is a reviewable diff rather than a code change.

| literal | why it is structural |
|---|---|
