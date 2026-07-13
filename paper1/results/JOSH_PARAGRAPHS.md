# Josh's 4 hand-written paragraphs (the agent does NOT write these — you do)

Supervisor: the agent swaps numbers, but the muscle memory for these arguments is yours; you defend at
the viva. Due before the full-manuscript diff. Evidence + a finalised draft where one exists are below;
write the prose yourself.

ORDER (supervisor, start TODAY): 1. C256 dominance -> 2. collaboration-harm (both ride today's frozen
numbers -- write while hot) -> 3. CoDS positioning LAST (outward-facing, highest wording risk; BEFORE
writing, pull arXiv 2512.22513's CURRENT version -- positioning against a stale competitor version is a
submission liability). The agent reviews your drafts for the ledger discipline (forbidden notations; the
CI-wording rule -- e.g. "comparable" not "improves" for a per-mille gain without a CI -- applies to your
paragraphs too). Writing is not gated; only entry into the manuscript is. Paste drafts into the thread.

## 1. C256 dominance argument (Method / message candidates)
Two-pronged; both halves required:
- lambda=0 DOMINANCE THEOREM: eff_C256 <= eff_C16 pointwise -- identical 1.98 Mbit content at strictly
  higher BLER (256-QAM's weaker protection at every SNR), and ego < comp on the failure fallback, so a
  payload-blind argmax can never strictly prefer C256. "Never selected by the oracle" is a theorem, not an
  observation. Write this as the reason C256 is a dominated action a priori.
- lambda>0 EMPIRICAL: on the 200-realisation Lagrangian frontier, C256 activation is a minority foothold
  (<=5%) spread across the low-payload region of the frontier, never approaching a majority share
  (max frac_C256 = 0.025/0.032/0.046 val/test/culver). src results/a1_c256_frontier_v3.csv,
  results/policy_v3/c256_frontier_band.csv. => the rate-matched 3rd action earns almost no place even when
  its lower payload is allowed to compete.

## 2. CoDS positioning (Related Work, near ML-Cooper)
Place CoDS relative to \method: where CoDS sits in the compression-vs-selection landscape, what it shares
with and differs from a channel-conditioned granularity selector. (Evidence = the CoDS paper; this is a
positioning argument, your call on framing.)

## 3. Collaboration-is-sometimes-harmful (Discussion)
Evidence: a2 Easy-stratum gain is significantly NEGATIVE (test -0.0147, frame CI excludes 0) -- on
near-perfect-late frames the collaborator's feature message net-adds false positives and single-vehicle
ego-only beats fusion. Quantified by frac(ego_f1 > late_f1) = 0.9% / 7.4% / 0.2% (validate/test/culver;
test is the sparsest split, mean GT 15 vs 28/43). src results/ablation_v3/a2_difficulty*.csv,
results/step4_collaboration_harm_v3.csv. Point to the fix: an explicit "do-not-request" ego-only 4th action
is free in the 2-bit codebook ('11' reserved) -- fold into the 5.1.1 action-space review (not this paper).

## 4. HARQ motivation (Discussion / future work / Paper C hook) -- FINALISED DRAFT, write prose around it
The OFDM result makes this quantitative and it comes from your own table:

  "Frequency diversity is not the only lever. Under the TR 37.885 Urban NLOSv profile, OFDM's frequency
   diversity (empirical order approx 2, from a BLER slope fit) pulls the feature-transmission feasibility
   threshold from unbounded (flat, no-diversity Rayleigh) back to approx 24 dB, but that still sits above
   the vehicular operating SNR range. Time diversity via HARQ is the next lever, pulling the threshold
   further down into the operating range -- at the cost of added latency, which the selector must weigh,
   since the frame airtime already consumes approx 99 ms of the 100 ms cycle."

Diversity order is the controlled variable (freq -> ~24 dB; time/HARQ -> lower). Stating the latency
trade-off yourself pre-empts the obvious reviewer question. src results/bler_sionna/PROVENANCE_ofdm.txt
(diversity-order slope fit + feasibility monotone 8 / ~24 / unbounded dB).
