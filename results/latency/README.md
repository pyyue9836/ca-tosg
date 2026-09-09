# `results/latency/`

* **`selector_latency_candidate67.json`** — the current measurement. Frozen selector candidate 67
  (model sha256 `87d990f6…`), batch-1 inference and cue-statistics timing on CPU, with the hardware
  and the command recorded. This is what the manuscript quotes.

* **`selector_latency.csv`** — **v1 candidates only** (`selector_B010`/`B020`/`B030`, candidates 2,
  1 and 56). These are *different models* from the frozen v2 selector and **are not cited by the
  manuscript**. Kept as a record of the v1 measurement; quoting them for candidate 67 would be a
  cross-version substitution.

* `system_timing.csv` — v1 end-to-end stage timings, same status.
