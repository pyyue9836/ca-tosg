# `results/latency/`

* **`selector_latency_candidate67.json`** — the current measurement (schema `/2`, V2-R69 D).
  Frozen selector candidate 67 (model sha256 `87d990f6…`), batch-1 inference and cue-statistics
  timing on CPU, with the hardware, the thread configuration and the input conditions recorded.
  This is what the manuscript quotes.

  The schema `/1` version of this file reported **55.4 ms**. That number was measured with the
  forest's pickled `n_jobs=-1` left in place, so `predict` dispatched a batch of one row across
  every core and paid the thread-pool cost each call; the process was not pinned, the channel half
  of the input was held at 10 dB AWGN, and the cue timing used a synthetic Gaussian cloud rather
  than a real sweep. Forcing `n_jobs=1` and pinning to one core gives **7.2 ms** — the old figure
  was wrong in the pessimistic direction, and it was wrong about its own conditions, which is the
  part that mattered.

* **`selector_latency.csv`** — **v1 candidates only** (`selector_B010`/`B020`/`B030`, candidates 2,
  1 and 56). These are *different models* from the frozen v2 selector and **are not cited by the
  manuscript**. Kept as a record of the v1 measurement; quoting them for candidate 67 would be a
  cross-version substitution.

  These carry the same defect: the v1 claim of "52.1 ms per frame on a single CPU core" was
  measured through `tools/benchmark_latency.py`, which also never forced `n_jobs` or pinned the
  process. The v1 numbers are frozen as claimed at their commit and are not restated here; they
  should not be reused for any new claim without re-measuring under a stated thread configuration.

* `system_timing.csv` — v1 end-to-end stage timings, same status.
