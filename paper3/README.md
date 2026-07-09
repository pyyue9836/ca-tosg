# Paper 3 — Multi-Vehicle Channel-Aware Semantic Scheduling for Cooperative Perception

**Status: confirmed direction, not started.** Network-level capstone of the PhD arc.

## Scope — "who transmits what?"
Extends the single-link selector of Paper 1 to a multi-vehicle setting: several
collaborators share a limited communication budget, so per-frame granularity selection
becomes a joint *selection-and-scheduling* problem — which collaborators transmit, at
which semantic granularity, under a total payload cap.

## Primitives (reused from earlier papers)
- Paper 1's per-link CA-TOSG selector → per-collaborator scoring / decision module.
- Paper 2's feature coding/transmission → the feature-level branch (optional).

## Planned evaluation
- Baselines: all-object, all-feature, top-k distance/confidence collaborator selection,
  and per-CAV CA-TOSG without a global budget.
- Metrics: ego detection AP, total channel-use payload, over-budget rate, robustness
  under channel variation.
- Data: OPV2V multi-CAV scenes; later V2X-Sim / real V2V4Real subject to availability.

## Position in the PhD arc
Paper 1 (*what to transmit*) → Paper 2 (*how to transmit*) → **Paper 3 (*who transmits what*)**.
Intended as the final journal manuscript of the three-paper arc.

_No code/data/results yet — to be added when the work begins._
