# Canonical quantity registry

Quantities the paper prints that are **derived** — a ratio, a percentage, a difference — rather than
read straight out of a cell. The literal value search in `tools/audit_claims_evidence.py` cannot see
them (nothing in any CSV contains the string `1.54`), so each one is registered here with the exact
route from a committed product, and `tests/test_canonical_quantities.py` **re-derives every one of
them at gate time**.

Nothing in the checker hardcodes a reference number. A hardcoded literal would turn a change in the
underlying data into a silent PASS, which is the failure this registry exists to prevent.

| quantity | printed as | source | derivation |
|---|---|---|---|
| channel-side importance | `24.8\%`, `22.3\%`, `47.1\%` | `results/main/feature_importance_frozen.csv` | the two `side=channel` rows, individually and summed, ×100 |
| perception-side importance | `52.9\%`, `3.9\%` | `results/main/feature_importance_frozen.csv` | the 21 `side=perception` rows summed, and their maximum, ×100 |
| selector latency | `59.9\pm5.3`~ms, `P95=66.6`~ms | `results/latency/selector_latency.csv` | **one row**: `selector_B030`, `mean_ms` / `std_ms` / `p95_ms`. The three numbers must come from the SAME row and that row must be the largest-`mean_ms` one (the paper claims the slowest of the three selectors) |
| FA-1 channel-only payload ratio | `1.54\times` | `results/sensitivity/feature_ablation.csv` | `test`, `B_max=0.30`: `channel_only.payload / combined.payload` = 0.28843 / 0.18703 |
| payload share of Fixed-F | `6.9`--`18.9\%` (test), `2.9`--`16.2\%` (Culver) | `results/main/replay_summary.csv` + `results/main/fixed_references.csv` | `B_RF` / Fixed-F `payload_msym` (0.99 Msym) × 100, per budget |
| F1 share of the masked oracle | `98.6`--`99.0\%` (test), `98.1`--`99.3\%` (Culver) | `results/main/replay_summary.csv` + `results/main/fixed_references.csv` | `F1_RF` / oracle `F1` × 100, per budget |
| JSCC oracle-headroom recovery | `56`--`62\%`; per channel `0.0291`/`+0.0181` (AWGN), `0.0275`/`+0.0158` (Rayleigh), `0.0281`/`+0.0158` (OFDM) | `results/baselines/importance_map_jscc/jscc_selector_{awgn,rayleigh,ofdm}.csv` | headroom = `or_f1` − `L_f1`; recovered = `rf_f1` − `L_f1`; share = recovered / headroom. **200-realisation held-out estimator on validate frames** — not the k-fold estimator used two sentences earlier, and the two are never mixed inside one sentence |
| payload reduction | `56.3\%` | `results/main/replay_summary.csv` | `test`, `B_max=0.20`: `payload_reduction` × 100 |

## Why the latency entry is same-row

The paper once printed `selector_B030`'s mean and standard deviation next to `selector_B010`'s P95.
Both numbers existed in the CSV, so any check that asked only "does this value appear somewhere in
the file?" passed. The registry check asserts that a **single row** carries all three, which is the
only form of the check that could have caught it.

## Why the importance entry carries a partition assertion

The two channel-side features are the two individually strongest cues (24.8% and 22.3%), but the 21
perception-side cues carry **52.9%** between them — the larger share. The gate therefore also
refuses the wording "dominating all 21 cues", which the paper used until R17-C and which the data
does not support. Concentration is the true reading: the channel side puts its mass in two decisive
splits, the task side spreads comparable total mass across many weak ones.

## Why the JSCC recovery entry names its estimator

Three estimators exist for this appendix and they disagree, which is the point: the 200-realisation held-out comparison gives 56--62%, the in-distribution k-fold diagnostic gives 36.7--74.9% (71.6% on the AWGN/test row), and the frozen cross-split evaluation is **negative** on test. The retired sentence quoted "55--70%" -- reproducible from none of them -- and used the *headroom* 0.031 as though it were the recovered gain, which is +0.0224 on that row. The registry therefore pins the estimator, the split and both quantities separately.
