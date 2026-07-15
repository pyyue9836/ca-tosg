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
### FINAL PROSE LANDED (agent-drafted per Josh 2026-07-15, 9 revisions + hard-error fix, no re-review): results/PARAGRAPH_DRAFTS.md #1. This block stays as the review standard.
### (a) Precise dominance definition (metric / SNR range / channels; numbers CSV-direct + verified)
SYMBOL BINDING + IDENTITY DOMAIN (source note, put in the paragraph -- supervisor: "nail the domain of
validity, or max|err|=0 looks suspicious"): eff = effective F1 $= \mathrm{comp}(1-b) + \mathrm{ego}\,b$, the
expected utility of "fail back to ego with probability $b$". BINDINGS: comp = compressed-model F1 and ego =
ego-only F1 are that FRAME's own measured values; $b$ = the frame's grid-point frame-level BLER -- the
Sionna table value at that frame's (SNR, channel) grid point, a per-grid CONSTANT shared by all frames at
that grid point, NOT a per-frame draw. GIVEN THIS BINDING, the identity
    eff\_C256 $-$ eff\_C16 $= (\mathrm{comp}-\mathrm{ego})(b_{16}-b_{256})$
is an ALGEBRAIC identity in $b$ (both sides expand from eff $=\mathrm{comp}(1-b)+\mathrm{ego}\,b$); it holds
by construction, NOT empirically. So max|err| $=0.0$ is NECESSARY, not a discovered regularity -- the
verification (code/verify_c256_dominance.py, results/c256_dominance_verify.csv) confirms the IMPLEMENTATION
carries no transcription/indexing error; it is not evidence about the world. STATE THIS: a perfect check of
an algebraic identity verifies the code, not a phenomenon (else a reviewer reads max|err|=0 as either too
good or a tautology). b256 $\ge$ b16 everywhere (also verified). Since $b_{256}\ge b_{16}$ at every grid
point, the sign of eff\_C256 $-$ eff\_C16 is set by $(\mathrm{comp}-\mathrm{ego})$.
### DOMINANCE DEFINITION SENTENCE (supervisor: elevate from source note to a written definition, with the
### tie parenthetical AT the claim -- a reviewer recomputing frac(comp>=ego) from the CSV gets a DIFFERENT
### number and will call it an error unless the explanation waits for them here; 3rd application of the
### clairvoyant/ceiling-footnote + Figure-A-near-overlap rule -- explain a recomputable gap where it is doubted):
Write the definition explicitly: C256 is DOMINATED means eff\_C256 $\le$ eff\_C16 (WEAK dominance -- ties
count). This holds on 99.7\% / 98.5\% / 100.0\% of frames (validate/test/culver). Then the parenthetical,
in-line and WORDED EXACTLY (supervisor: the gap is NOT all tie frames -- comp$\ge$ego ties are already
inside frac(comp$\ge$ego); the gap is the INTERSECTION, else a reviewer recomputing frac(tie) gets a larger
number and doubts a second time): "(the dominated fraction exceeds frac(comp $\ge$ ego) $=$ 99.0\% / 94.2\% /
99.1\% by the frames where comp $<$ ego BUT $b_{16}=b_{256}$ -- Rayleigh double-flatline or high-SNR
both-delivered -- which give eff\_C256 $=$ eff\_C16 and so count as (weakly) dominated: 0.7\% / 4.2\% / 0.9\%
of frames)". CAVEAT (still state): dominance is CONDITIONAL -- it reverses (eff\_C256 $>$ eff\_C16) on the
frames where comp $<$ ego AND $b_{16}<b_{256}$ (partial delivery), a SUBSET of the collaboration-harm frames
of para 3. Write "dominated wherever the collaborator helps", never "always dominated".
### PROVENANCE (source note, one line): all four fractions -- frac\_dominated 99.7/98.5/100.0,
### frac(comp$\ge$ego) 99.0/94.2/99.1, frac(comp$<$ego $\wedge$ tie) 0.7/4.2/0.9, and the para-3 anchor
### frac(comp$<$ego) 1.0/5.8/0.9 -- come from ONE run of code/verify_c256_dominance.py written to
### results/c256_dominance_verify.csv (same commit); the disjoint decomposition frac\_dominated $=$
### frac(comp$\ge$ego) $+$ frac(comp$<$ego $\wedge$ tie) is asserted in-script, NOT hand-computed.
### WELD TO PARA 3 (supervisor: the two paragraphs share one mathematical foundation, cross-reference it):
the sign of $(\mathrm{comp}-\mathrm{ego})$ SIMULTANEOUSLY sets the C256 dominance direction (here) AND
whether collaboration is harmful (para 3). Write the C256 and collaboration-harm paragraphs as mutually
supporting -- one causal chain, not two parallel observations.
### (b) Physics mechanism (one sentence) -- NOTATION MUST MATCH Figure A + body (see checklist)
256-QAM right-shifts the AWGN frame-error cliff from 8.0 dB (16-QAM) to 16.5 dB [both = the Sionna
frame-BLER onset, the first Es/N0 at which frame BLER $<0.999$; results/bler_sionna/bler_sionna.csv]; under
Rayleigh (and OFDM within 0-20 dB) both are flat-dead; so there is NO SNR window in which C256 opens before
C16. NOTATION ALIGNMENT: Figure A's coarse 6-point grid renders this same 256-QAM cliff as the 16$\to$20 dB
AP transition; the paragraph, the Figure A caption, and any body table must all use ONE convention (the
16.5 dB fine BLER-onset, with the coarse-grid correspondence noted) -- 16.5 vs 17-20 in different places =
a reviewer-flagged inconsistency (checklist item).
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
Evidence (with CI): Easy-stratum gain is significantly NEGATIVE on test = -0.0147 (frame-level paired 95% CI
[-0.0179,-0.0115], gain_significant=True, n=713; reliable AWGN 16 dB; code/extra_experiments/out/
a2_difficulty_reliable_v3.csv). [History: on 2026-07-15 the agent briefly "corrected" this to -0.0134 after
grepping only results/ and missing code/extra_experiments/out/ -- a negative-existence-search-scope error;
-0.0147 is correct and sourced. -0.0134 is the STALE v2 est_snr>=14/n=108 number.] The FP-mechanism gloss is
dropped (no ego/compressed confusion columns to verify "adds false positives"); the -0.0147 is an aggregate
realised-F1 gain, not an FP decomposition. Structural quantifier (descriptive, no
claim): frac(ego_f1 > late_f1) = 0.9% / 7.4% / 0.2% (validate/test/culver; test sparsest, mean GT 15 vs
28/43). src results/ablation_v3/a2_difficulty*.csv, results/step4_collaboration_harm_v3.csv.
QUANTITATIVE ANCHOR + WELD (supervisor: this paragraph's anchor already lies in the C256 CSV -- write the
two paragraphs off ONE number source, not just a cross-reference). Descriptive, no directional verb: "on
frac(comp $<$ ego) $=$ 1.0\% / 5.8\% / 0.9\% of frames the compressed-feature message's delivered utility is
below the ego-only fallback" -- this is the $(\mathrm{comp}-\mathrm{ego})<0$ set whose sign SIMULTANEOUSLY
drives the C256 dominance reversal (para 1); the two paragraphs share one CSV and one identity. src
results/c256_dominance_verify.csv (column frac_comp_lt_ego; same run/commit as the C256 fractions). This is
the compressed-feature-side counterpart to the object-level-side frac(ego $>$ late) above; each hand-written
paragraph now carries one source-anchored number (C256, collaboration-harm, HARQ) -- isomorphic anchors.
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
