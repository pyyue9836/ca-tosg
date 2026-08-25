# Retired products — present in the tree, NOT valid binding sources (R28-2)

A committed result file is not automatically evidence. These were produced under a superseded
convention or engine; they are kept because change-log entries and the corrigendum refer to them, but
a number in the delivered text may **not** be justified by them. `p6_numbers_vs_csv.canonical_corpus`
excludes every path listed here, so a claim bound to one of them reports as unlocated rather than
passing.

Rows stay in this table after the product is deleted from the tree. The exclusion is then a no-op,
but the row is the record of *why* the number may not come back, and the entry costs nothing.

| product | why it is retired | what replaced it |
|---|---|---|
| `results/sensitivity/c256_dominance_verify.csv` | **Deleted from the tree in R67 (c).** Produced 2026-08-12, before the P0 single-collaborator corrigendum: its `frac_comp_ge_ego` / `frac_comp_lt_ego_and_tie` columns are full-collaborator fractions. They were still passing the C256 paragraph's `99.0 / 94.2 / 99.1%` and `0.7 / 4.2 / 0.9%` through the literal gate by percent-form matching (0.9899 ≈ 99.0%), which is how three retired families survived in one paragraph (R28-1). | nothing: the paragraph's argument is now physical-layer ordering plus the structurally-zero deployment count, and needs no fractions. The convention-independent columns (`n`, `n_selector_predictions`, `selector_C256_requests`) are re-derived as frames x 200 realisations. |

## Deleted in R67 (c), not merely retired

These carried no live reader and no bound number (`tools/p6_numbers_vs_csv.py` located nothing in
any of them). They are recorded here so a future run does not read their absence as an omission.

| product | engine | why it went |
|---|---|---|
| `results/main/threshold_vs_rf.csv` | v3 200-realisation policy engine | superseded by the frozen replay (`results/main/replay_summary.csv`); last reader removed in R67 (b) |
| `results/main/pareto_points.csv` | v3 200-realisation policy engine | its only readers were the v3 pareto ablation and the retired pareto figure script, both deleted here |
| `results/main/true_e2e_global_{test,validate}.csv` | v3 global-sort scorer | Figs. 4/5/6/8 come from `results/main/frozen_curves.csv` through one generator (P5-7 D) |
| `results/main/step4_oracle_action_dist.csv` | v3 oracle action mix | its only reader was the retired decision figure; the frozen action mix is `results/main/action_distribution.csv` |
| `results/main/feature_importance.csv` | non-frozen deployed selector | the delivered figure and every bound number read `results/main/feature_importance_frozen.csv` |
| `results/sensitivity/ablation/a2_difficulty{,_reliable}.csv` | v3 selector + `v3_eval` | superseded in the paper by `results/sensitivity/difficulty_frozen.csv` (R66-1/2) |
