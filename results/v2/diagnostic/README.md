# `results/v2/diagnostic/` — pre-determinism WP5 products, kept and not usable

**Generated before the `shuffle_points` fix (V2-R16).** Every file here came out of a pipeline whose
point ordering was drawn from the global unseeded numpy RNG, so it is **not reproducible**: a re-run
in a new process disagrees on ~1.5 % of frames by one box, and on AP by 1e-5 to 1e-4.

**Diagnostic-only, per V2-R16 D-7.** These may not enter the frozen manifest, the paper, or any
work package downstream of WP5. They are kept because deleting them would erase the evidence for the
finding — `wp5_message_validate_BRIDGE_FAIL.json` is the record of the bridge catching it.

| file | what it was |
|---|---|
| `wp5_f_products_validate.*` | the R=0 sweep (V2-R11 A-1 kept it as the replicate-0 product) |
| `wp5_final_validate.*` | R=4, three regimes, endpoints — the 194-minute run |
| `wp5_message_validate.csv` | the partial reconstruction that failed the bridge |
| `wp5_message_validate_BRIDGE_FAIL.json` | the three tolerance comparisons that stopped it |

The determinism-era replacements sit one directory up, under the same names.
