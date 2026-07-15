# DEPRECATED artifacts -- uncoded (pre rate-1/2) payload units. DO NOT read these.
Unit-convention change (payload = info/coderate/bits_per_sym; C16=0.99, C256=0.495 Msym) propagated to the
policy_v3/ outputs but left these older siblings carrying the WRONG uncoded units (C16=0.495, C256=0.2475).
Found by `grep -rn '0\.2475\|0\.495' results/` (whole-repo sweep, not a single-point reconciliation).

STALE (superseded by the policy_v3/ equivalent with corrected 0.99/0.495):
- results/pareto_points.csv                      -> use results/policy_v3/pareto_points.csv
- results/generalisation_{validate,test,culver}.csv -> use results/policy_v3/generalisation_*.csv
  (also older F1 accounting, not only payload)
- code/extra_experiments/out/a1_pareto_points.csv   -> regenerate from a1_pareto.py (corrected PAYLOAD)

Rule (elevated 2026-07-15): after a unit-convention change, EVERY CSV/figure artifact carrying that unit is
either regenerated or marked DEPRECATED here; a single-point reconciliation (e.g. frontier lam=0 payload
0.1565 = 0.863*0.024 + 0.137*0.99) proves the live file, it does NOT sweep the repo -- grep the old literal
to find all sibling orphans at once. [[verification-derive-not-hardcode]] family.
