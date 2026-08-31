# CA-TOSG v2 — P5 rewrite (V2-R41)

**The experiment is closed** (`V2_CLOSEOUT.json`). Nothing here may change an experimental result;
if a sentence is hard to write, the sentence is wrong, not the experiment (A-1). v1 stays frozen.

---

## P2-1 · Abstract

Cooperative perception must choose *what* to transmit, not only how much to compress. We formalise
per-frame **semantic granularity selection** over three actions — ego-only (E), object-level (L) and
feature-level (F) — and evaluate it under a single detector, a single field of view and a single
ground truth, with communication charged through a measured LDPC/QAM chain rather than a declared
budget.

> **CA-TOSG reduced realised communication payload by 99.85 % on Test and 99.70 % on Culver-City
> relative to the frozen comparator. However, the preregistered scene-level non-inferiority criterion
> was not met on either split, indicating that substantial communication reduction was achieved
> without statistically establishing accuracy preservation.**

Three mechanism results follow from the unified branch: partial recovery is necessary, since
all-or-nothing delivery of a 12,567-codeword message is effectively dead at realistic loss rates;
**where** a loss falls changes the task outcome even when **how much** is lost is held exactly fixed;
and fusing a zeroed feature tensor is not equivalent to ego-only inference. In the frozen policy the
expensive feature action is never selected, and we report why that is a cost-structure result rather
than a learning failure.

## P2-2 · Contributions (three)

1. **Problem formalisation.** Per-frame granularity selection as a budget-constrained action choice
   over {E, L, F}, with payload charged per frame through the transport chain the messages actually
   traverse.
2. **A receiver-driven method.** The ego evaluates its own scene and channel and requests a
   granularity; the selector's inputs are strictly ego-local and available *before* the request.
3. **Experimental findings under a unified protocol.** One checkpoint, one FOV, one GT; a
   deterministic evaluation pipeline; and the result stated above, with its mechanism findings.

## P2-3 · Internal-audit language removed

`retired`, `withdrawn`, `committed product`, `in the record`, `pre-registered`, `correction`,
`prior version` do not appear in the main text. Where a decision's timing matters, the manuscript
says *"fixed and frozen before the held-out evaluation"* (§15's rule) and cites the supplementary.
The change log keeps the audit trail; the paper keeps the science.

## P2-4 · Conclusion — what was done, what was shown, under what conditions

**Done.** Three transmission granularities were placed under one detector, one FOV and one GT, and
charged through one measured transport chain. A selector was fitted on the development split only
and frozen before either held-out set was opened.

**Shown.** Communication can be cut by roughly two orders of magnitude relative to a budget-matched
threshold policy, on both held-out sets. **Accuracy non-inferiority was not established on either**:
the point differences are −0.00499 (Test) and −0.00461 (Culver), inside the δ = 0.005 margin, while
the scene-level bootstrap lower bounds are −0.00738 and −0.00541, outside it. The criterion is
defined on the bound.

**Under what conditions.** One dataset family (OPV2V), one detector, a single ego–collaborator pair,
a flat block-fading channel with a measured BLER table, and — for the cross-domain claim — four
Culver-City scenes.

## P2-5 · Baselines, layered

| layer | arm | role |
|---|---|---|
| fixed policy | Fixed-E, Fixed-L, Fixed-F | end points of the action space |
| internal decision rule | SNR threshold τ; two-/three-scalar hand rules | **the primary comparator is the frozen τ = 16.5** — the only arm sharing CA-TOSG's complete payload definition |
| feature-content / codec | **Where2comm** | external spatial feature selection; **payload N/A**, see below |
| adaptive policy | — | P0-7 **unmet**: no candidate met the reproducibility bar |
| oracle | budget-blind argmax | upper reference, not a rival |

**Where2comm.** *Evaluated under the same data splits, field of view, ground truth and detection
metrics. We report its native communication rate because the evaluated implementation transmits
floating-point selected features and does not execute the locked v2 int8 quantisation path.
Consequently, it is excluded from bit-level budget-matched claims.*

At threshold 0.02 it reaches AP@0.5 0.91708 (Test) and 0.83195 (Culver) while retaining 5.2 % and
9.1 % of features. It answers what an external feature-selection method achieves under a unified
perception convention — not how it trades bits against accuracy on our axis.

**P0-7 unmet.** Neither ML-Cooper nor SmartCooper has a public runnable release with weights.
SmartCooper is additionally misaligned in principle: its contribution *is* a learnable
CSI-conditioned compression ratio, so its payload is its own encoder's output.

---

## Limitations

**Accuracy non-inferiority was not established.** On both splits the point estimate lies inside the
margin and the confidence bound does not. Reported as measured; the margin was fixed in advance and
the bound is what it tests.

**Proportion matters here.** The saving is overwhelming — 99.85 % and 99.70 %. The shortfall is
small — 0.0024 (Test) and 0.0004 (Culver) on the lower bound. **Neither fact may be reported without
the other:** stating only the saving packages a failed criterion as success; stating only the
shortfall discards a two-orders-of-magnitude result.

**Culver-City rests on four scenes.** The bootstrap resamples them, so its interval is coarse. The
result has the same shape as Test on far less scene diversity — a limitation, not corroboration.

### Why this remains a three-action method although ρ_F = 0

The frozen selector never requests F. Four measurements, which belong together:

1. **F is genuinely the best action on 56.2 % of grid rows** (24,502 of 43,560): its realised utility
   exceeds both E and L there. This is not a case of an action that never helps.
2. **The break-even λ falls in a hole in the pre-registered grid.** Conditional on the rows where F
   is best, it is **0.01556**; averaged over the whole grid it is **0.0048**. *(Each value carries its
   conditioning set; neither is meaningful bare — they differ because F's benefit is concentrated on
   particular rows, which is itself informative.)* The grid samples λ ∈ {0, 0.02, 0.05, …}, so **no
   candidate could ever have been selected in the region where a mixed policy exists.**
3. **A fine λ scan, registered before it produced any number, shows a real three-action trade-off
   across that entire interval:** ρ_F falls smoothly 0.534 → 0.152 and ρ_L rises 0.202 → 0.453 as λ
   goes 0.001 → 0.019, with 4 of 19 points budget-feasible at β = 0.20 and 10 of 19 at β = 0.30.
4. **All of the above is an exploratory diagnostic on the development split.** It enters no primary
   criterion, and candidate 67 was **not** replaced on the strength of it.

Taken together: **ρ_F = 0 is a property of where the pre-registered grid sampled, not evidence that
the feature action is worthless.** Reported here as one argument because the four facts are
individually misleading — (1) alone overstates F, (2) alone reads as an excuse, and (3) without (4)
looks like post-hoc rescue.

**No three distinct budget points.** All three β select the same candidate; the budget never binds.
The contribution is therefore a granularity-control framework, not a demonstration that a learned
selector beats simple rules — **it does not**: at equal budget the frozen RF is behind the
budget-matched threshold on F1 at every β.

**Other limits.** Selector-only latency is measured; total system latency is not. One
ego–collaborator pair. A flat block-fading channel. OPV2V Culver-City is a **simulated** domain
shift, not a real-world one.

---

## P2-6 · Document fixes

| item | action |
|---|---|
| supplementary title and authors | add, matching the main file |
| CSV path lists in the main text | move to supplementary |
| duplicated `\noindent` | remove |
| lower-case sentence starts | fix |
| "safety certification", "lightweight real-time" | delete — evidence does not support them |
| OPV2V Culver-City | describe as a **simulated** domain shift throughout |
| NR LDPC / 802.11bd citations | one consistent form |
| "matched-budget" phrasing near Where2comm | forbidden (gate); it carries no Msym |

## Emphasis (V2-R41 C-3)

The **method and protocol** sections carry the weight: the measured per-frame payload chain
(`B_L,t`, `B_F` from the codeword count, header and packetisation), the deterministic evaluation
pipeline, the ego-local cue schema with its leak removed, and the three delivery regimes with partial
recovery. These were background in v1 and are the most solid contribution now. The **results**
section converges on the three findings above and does not expand beyond them.
