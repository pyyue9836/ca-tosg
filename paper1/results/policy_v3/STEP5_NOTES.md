# Step-5 v3 notes — wording, statistics, corrections (CA-TOSG paper1)

Companion to `PROVENANCE.txt` (auto-generated). These are the frozen wording/statistics decisions
the paper rewrite MUST carry, plus the supervisor's on-record prediction corrections.

## Central finding — Pareto-dominance (NOT a bare-F1 chain)
The bare-F1 chain "RF >= tau" is FALSE (test: best-F1 tau 0.9096 > RF 0.9088; culver 0.8874 > 0.8831).
Report the ordering as **clairvoyant >= oracle >= RF** in bare F1; report **RF vs tau ONLY in Pareto
language** (equal-bandwidth). Never write a bare-F1 RF-vs-tau chain.

At MATCHED payload (tau tuned to RF's bandwidth on a 0.5 dB grid), RF beats tau on all three splits;
paired bootstrap 95% CI (FRAME-level — scene is the generalisation unit; realisation-level is a
diagnostic only, gives a spuriously tight interval):
  validate +0.00194 [0.00170, 0.00217]  (frames 54.7% win / 25.7% lose)
  test     +0.00049 [0.00023, 0.00076]  (frames 43.5% win / 36.4% lose)  <- significant but SMALL
  culver   +0.00325 [0.00246, 0.00409]  (frames 56.7% win / 35.8% lose)
Pre-registered TIER-1 wording HOLDS: "RF Pareto-dominates the retuned SNR-threshold frontier on all
three splits (frame-level paired bootstrap, 95% CI excludes zero)." **The test effect-size caveat
(43.5% win / 36.4% lose, significant but marginal) is PART OF the wording and must not be dropped.**
best-F1 tau only "matches" RF by over-transmitting 46-86% payload for <=0.004 F1.

## Supervisor prediction correction (on record — value of pre-registration)
Predicted "test not significant (~1 SE)". REFUTED. Mechanism (a TOOL-CHOICE error, not luck): an
UNPAIRED SE (~0.0004, the SE of the mean F1 itself) was used to judge a PAIRED difference. The paired
design cancels the common frame-difficulty variance; the difference's SE is only the disagreement
component, ~0.00013, so +0.00049 = 3.7 SE. Third data-driven correction of a direction/significance
prediction this rebuild; supervisor down-weights his own direction predictions going forward and fixes
only the acceptance STRUCTURE.

## C256 wording (rate-matched 3rd action)
Two-pronged, both halves required:
  (i) lambda=0 DOMINANCE THEOREM: eff_C256 <= eff_C16 pointwise (identical 1.98 Mbit content at higher
      BLER, and ego < comp), so the payload-blind argmax can never strictly prefer C256 — "never
      selected by the oracle" is a THEOREM, not an observation.
  (ii) lambda>0 EMPIRICAL: on the 200-realisation Lagrangian frontier, C256 activation is
      **a minority foothold (<=5%) spread across the low-payload region of the frontier
      (0.024-0.13 Mbit), never approaching a majority share** (max frac_C256 = 0.0255/0.0319/0.0456
      for validate/test/culver; see c256_frontier_band.csv). Low-and-WIDE, not low-and-narrow
      (supersedes the earlier "narrow lambda band" wording, which was a single-frozen-draw artifact).

## Protocol rule (elevated)
Every number that appears ANYWHERE in the paper = 200 channel realisations. Single-frozen-draw
computations are for never-published internal diagnostics ONLY. (The Pareto figure is now 200-real;
the single-draw a1 CSVs were deleted.)
