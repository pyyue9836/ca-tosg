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

## Protocol rule (elevated) + the PUBLICATION TEST (supervisor 2026-07-12)
Every number that appears ANYWHERE in the paper = the FULL canonical protocol: 200 channel
realisations + v3 GT + Sionna frame-level BLER + ego fallback. Single-frozen-draw computations are for
never-published internal diagnostics ONLY, and such scripts + their output CSVs MUST carry the header
`DIAGNOSTIC - single frozen realisation - NOT FOR PUBLICATION`.
Evidence the single-draw is TOXIC (tighter in v3, not looser): a7 single-frozen-draw RF test payload
0.0461 vs the 200-realisation 0.1346 -- a 3x drift (v3's higher C-active amplifies the single
channel-mix variance; worse than the P0.2-era drift).

### Ablation disposition (by the publication test)
UPGRADE to 200-realisation (cited in main.tex):
- a2 difficulty strata -- 4.4.2 hard-frame gains (+0.039/+0.045 in v2) re-emit under v3.
- a7 feature ablation -- 4.4.4 "cues add <X over channel state alone"; the number likely CHANGES under
  v3 (ego floor widened the feasible window -> cue marginal value may rise, same mechanism as the edge).
- a8 F1 column -- 4.4.4 "lighter models reach the same accuracy" must hold under the same protocol.
  a8 LATENCY column is channel-protocol-independent -> kept as-is.
- robustness triple (csi_noise / csi_aging / request_staleness) -- 4.4.4 numbers 0.003/0.015/0.057 are
  published; after the old-codeword-BLER->v3 port they must ALSO run under 200 realisations (porting is
  necessary but NOT sufficient -- a single-draw run of the ported script still fails the publication test).
DIAGNOSTIC / DEPRECATED (not cited):
- a3 scene subsets -> DIAGNOSTIC header (single frozen draw, not for publication).
- multiseed_hardening -> DEPRECATED: its role is absorbed by the 200-realisation engine itself; keeping
  it only manufactures a second, conflicting set of "hardening" numbers.

## Interpolation error path (JSCC side ONLY) -- do not cross-apply
The JSCC two-regime edge carries a systematic term from the 6-point SNR interpolation: aggregate bias
<= 0.0012 (mid-grid probe at SNR 10), an order below the measured edge (~0.015). Paper wording:
"interpolation-induced aggregate bias <=0.0012 (mid-grid probe), an order below the measured edge."
**This 0.0012 belongs to the JSCC side ONLY** -- it must NOT be set against the LDPC-side +0.0005 edge.
The LDPC side is evaluated through the Sionna BLER table and never touches JSCC interpolation; the paper
must state which error path attaches to which regime so a reviewer does not wrongly divide 0.0012 into
the LDPC edge.
