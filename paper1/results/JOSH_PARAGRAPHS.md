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

## 1. C256 dominance argument (Method / message candidates) -- REVIEW STANDARD: 3 required elements (a,b,c)
### (a) Precise dominance definition (metric / SNR range / channels; numbers CSV-direct)
Metric = effective F1. eff_C256 - eff_C16 = (comp - ego)(b16 - b256). Since b256 >= b16 at EVERY SNR and on
EVERY channel (256-QAM's weaker protection), the sign is set by (comp - ego): where comp >= ego (the normal
case), eff_C256 <= eff_C16 -- C256 is dominated at all SNR and all channels; a payload-blind (lambda=0)
argmax never strictly prefers it. CAVEAT YOU MUST STATE (a reviewer will find it otherwise): dominance is
NOT unconditional -- it reverses on the frames where ego > comp (the collaboration-harm frames of para 3),
where both C variants already underperform L. Measured: frac(eff_C256 <= eff_C16) per frame (frozen draw) =
0.997 / 0.985 / 1.000 (validate/test/culver). So write "dominated wherever the collaborator helps (>=98.5%
of frames)", NOT "always dominated". src data/dataset_{split}_v3.csv.
### (b) Physics mechanism (one sentence)
256-QAM right-shifts the AWGN frame-error cliff from 8 dB (16-QAM) to 16.5 dB; under Rayleigh (and OFDM
within 0-20 dB) both are flat-dead; so there is NO SNR window in which C256 opens before C16. src
results/bler_sionna/bler_sionna.csv.
### (c) Pre-answer the design question ("why keep a dominated action in the set?")
Reviewers WILL ask. Answer in the paragraph, not in rebuttal: the action set is the complete 2-bit request
space; C256 is retained for completeness, and the negative result -- a rate-matched (same-payload-class,
lower-channel-use) action earns no place even on the lambda>0 frontier -- is itself a contribution.
Support: on the 200-realisation Lagrangian frontier C256 activation peaks at a minority 2.5/3.2/4.5%
(val/test/culver), only in a narrow lambda band over the low-payload region (0.024-0.16/0.18/0.24 Msym),
never a majority. src results/policy_v3/c256_frontier_band.csv, results/a1_c256_frontier_v3.csv.

## 2. CoDS positioning (Related Work, near ML-Cooper)
Place CoDS relative to \method: where CoDS sits in the compression-vs-selection landscape, what it shares
with and differs from a channel-conditioned granularity selector. (Evidence = the CoDS paper; this is a
positioning argument, your call on framing.)

## 3. Collaboration-is-sometimes-harmful (Discussion) -- REVIEW STANDARD: highest directional-wording risk
WORDING RULE (strict): every worse/degrades/harms/hurts either carries a CI or is rewritten descriptively.
This paragraph's FUNCTION is to motivate the mechanism (feasibility mask + ego-only fallback), NOT to claim
a measured harm magnitude -- do not headline a per-mille harm number as if it were the result.
CORE MECHANISM CHAIN (write this): requesting a feature message when the channel cannot deliver it spends
the collaborator's transmission budget for nothing and collapses the output to the ego-only floor -- this
is exactly why the oracle carries a feasibility mask and the failure fallback is ego-only, not a phantom
feature. That is the paragraph's job.
Evidence (with CIs where a claim is made): a2 Easy-stratum gain is significantly NEGATIVE on test
(-0.0147, frame-level paired 95% CI excludes 0) -- on near-perfect-late frames the collaborator's message
net-adds false positives and single-vehicle ego-only beats fusion. Structural quantifier (descriptive, no
claim): frac(ego_f1 > late_f1) = 0.9% / 7.4% / 0.2% (validate/test/culver; test sparsest, mean GT 15 vs
28/43). src results/ablation_v3/a2_difficulty*.csv, results/step4_collaboration_harm_v3.csv.
Fix pointer (future work, not this paper): an explicit "do-not-request" ego-only 4th action is free in the
2-bit codebook ('11' reserved) -- fold into the 5.1.1 action-space review.

## 2. CoDS positioning (Related Work, near ML-Cooper) -- REVIEW STANDARD: verify-before-write, no strawman
BEFORE writing, do ONE thing: pull arXiv 2512.22513's CURRENT version number + date and record it in the
paragraph's source note (positioning against a stale competitor version is a submission liability). Then:
- Positioning axis uses ONLY what \method actually has (all real, all in this thread): receiver-driven
  2-bit request; channel-state-conditioned oracle; frame-level (Sionna) BLER physics; feasibility mask.
- Write only CITABLE claims about CoDS's content -- no strawman, no "unlike CoDS which cannot..." unless
  the cited version actually cannot. Your call on framing; the constraint is verifiability.

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
