# Canonical quantity registry

Quantities the paper prints that are **derived** — a ratio, a percentage, a difference — rather than
read straight out of a cell. The literal value search in `tools/audit_claims_evidence.py` cannot see
them (nothing in any CSV contains the ratio as a literal), so each one is registered here with the exact
route from a committed product, and `tests/test_canonical_quantities.py` **re-derives every one of
them at gate time**.

Nothing in the checker hardcodes a reference number. A hardcoded literal would turn a change in the
underlying data into a silent PASS, which is the failure this registry exists to prevent.

| quantity | printed as | source | derivation |
|---|---|---|---|
| channel-side importance | `34.2\%`, `27.5\%`, `61.7\%` | `results/main/feature_importance_frozen.csv` | the two `side=channel` rows, individually and summed, ×100 |
| perception-side importance | `38.3\%`, `3.0\%` | `results/main/feature_importance_frozen.csv` | the 21 `side=perception` rows summed, and their maximum, ×100 |
| selector latency | `52.1\pm5.6`~ms, `P95=58.3`~ms | `results/latency/selector_latency.csv` | **one row**: `selector_B020` (`mean_ms` 52.062 / `std_ms` 5.629 / `p95_ms` 58.295). The three numbers must come from the SAME row and that row must be the largest-`mean_ms` one -- which is `selector_B020`, not `B030` as this cell said until R23-6 (the checker had always derived the slowest row itself, so the prose drifted while the gate passed) |
| FA-1 channel-only payload ratio | `1.36\times` | `results/sensitivity/feature_ablation.csv` | `test`, `B_max=0.30`: `channel_only.payload / combined.payload` = 0.28722 / 0.21197 = 1.3550 |
| payload share of Fixed-F | `8.2`--`20.6\%` (validate), `3.7`--`21.4\%` (test), `2.5`--`18.4\%` (Culver) | `results/main/replay_summary.csv` + `results/main/fixed_references.csv` | `B_RF` / Fixed-F `payload_msym` (0.99 Msym) × 100, per budget |
| F1 share of the masked oracle | `98.4`--`99.1\%` (test), `98.0`--`99.4\%` (Culver) | `results/main/replay_summary.csv` + `results/main/fixed_references.csv` | `F1_RF` / oracle `F1` × 100, per budget |
| JSCC oracle-headroom recovery | `56`--`62\%`; per channel `0.0291`/`+0.0181` (AWGN), `0.0275`/`+0.0158` (Rayleigh), `0.0281`/`+0.0158` (OFDM) | `results/baselines/importance_map_jscc/jscc_selector_{awgn,rayleigh,ofdm}.csv` | headroom = `or_f1` − `L_f1`; recovered = `rf_f1` − `L_f1`; share = recovered / headroom. **200-realisation held-out estimator on validate frames** — not the k-fold estimator used two sentences earlier, and the two are never mixed inside one sentence |
| payload reduction | `34.8\%` vs nominal, `26.6\%` vs budget-matched | `results/main/replay_summary.csv` | `test`, `B_max=0.20`: `payload_reduction` × 100 |

## Why the derivations are now arithmetic-checked (R23-6)

Every `A / B = C` written in the derivation column is re-evaluated by
`tests/test_canonical_quantities.py`: `A` and `B` must each occur as a value in the CSV the row
names, and `A / B` must equal `C` to the precision `C` is written at. Two of the entries above had
drifted from their own sources without the gate noticing — the FA-1 ratio still quoted the retired
`0.28843 / 0.18703`, and the latency row named `selector_B030` when the slowest selector is
`selector_B020` — because the checker re-derived the numbers from the CSV and never read this file's
prose. A registry whose text can disagree with its own check is a second source of truth.

## Why the latency entry is same-row

The paper once printed `selector_B030`'s mean and standard deviation next to `selector_B010`'s P95.
Both numbers existed in the CSV, so any check that asked only "does this value appear somewhere in
the file?" passed. The registry check asserts that a **single row** carries all three, which is the
only form of the check that could have caught it.

## Why the importance entry carries a partition assertion

Which side is larger **flipped** when the collaborator convention was corrected: under the retired
full-collaborator accounting the 21 perception cues carried the larger share, and R17-C rewrote the
section away from "dominance" for that reason. Under the single-collaborator protocol the two
channel-side features carry the larger share, so a dominance reading is supportable again. The gate
therefore **derives** which side is larger and checks the paper agrees, instead of banning one
phrasing forever — and the paper pairs the claim with an explicit *importance is not sufficiency*
guardrail, since the feature ablation shows the channel features alone cannot reach the full
selector's operating point.

## Why the JSCC recovery entry names its estimator

Three estimators exist for this appendix and they disagree, which is the point: the 200-realisation held-out comparison gives 56--62%, the in-distribution k-fold diagnostic gives 36.7--74.9% (71.6% on the AWGN/test row), and the frozen cross-split evaluation is **negative** on test. The retired sentence quoted "55--70%" -- reproducible from none of them -- and used the *headroom* 0.031 as though it were the recovered gain, which is +0.0224 on that row. The registry therefore pins the estimator, the split and both quantities separately.

## The payload anchor: a declared convention next to two measurements (R45-1)

| quantity | how it is re-derived at gate time | product |
|---|---|---|
| declared anchor element count, `2.16e6` | `256 x 48 x 176 = 2,162,688`, the geometry stated in the same sentence | none — it is a **declared convention**, which is exactly why it has no CSV |
| declared bit/element, `0.92` | `1.98 Mbit / 2,162,688 elements = 0.9155` | the source budget, declared |
| deployed pre-compression count, `3,942,400` | read from the row `pointpillar / pre_compression` | `results/channel/payload_conventions.csv`, from `tools/bev_tensor_probe.py` (`P4B_PROBE_pointpillar_compression.json`) |
| deployed transmitted count, `739,200` | read from the row `pointpillar / transmitted_bottleneck` | same |

The distinction is the entry's whole purpose. `p6_numbers_vs_csv` reported `2.16` as a MISS against
the products the claim is bound to, and it was **right to**: those products carry the *deployed*
counts and deliberately not the declared anchor. A declared constant still has to be re-derivable, so
the gate derives it from the geometry the paper itself states, and separately asserts that the two
measured counts are printed exactly as the probe recorded them.

What is retired here: "the conclusions are insensitive to this constant". The measured counterfactual
(`results/channel/payload_anchor_sensitivity.csv`) moves the headline channel-use fraction by
−0.90 % to −7.75 % under the paper's own 1.98 → 2.16 Mbit re-anchor and by −4.86 % to −41.99 % under
the declared→deployed one. The **ordering** survives; the fraction does not, and the paper now says
so — a claim the R45-6 reconciliation gate holds to the protocol's verdict.
