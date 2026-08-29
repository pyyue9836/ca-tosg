# Tier C — external baseline selection report (V2-R31 C)

**Zero GPU.** Protocol §13 requires this report *before* any GPU is spent, and V2-R29 E-3 made it a
hard deadline: it must be settled **before the test unseal**, because §13 fixes the baseline's
method, checkpoint and configuration ahead of held-out evaluation.

## Verdict

> **Neither ML-Cooper nor SmartCooper is reproducible under the seven unified elements.**
> Both fail at the first gate — **no public code and no public weights** — and that failure is
> disqualifying rather than laborious: §13 asks for "a runnable release, with weights, at a stated
> commit", and neither has one.
>
> **P0-7 is registered as UNMET**, and the fallback is the Where2comm arm this repository already
> has. **No candidate is chosen to fill the slot** (C-6).

## Search scope, stated because this is a negative-existence claim

Web search, 2026-08-29, for each candidate paired with `github` / `code release` / `channel-aware`,
plus the two collaborative-perception paper-digest repositories that track this field
([Little-Podi/Collaborative_Perception](https://github.com/Little-Podi/Collaborative_Perception),
[frankwnb/Collaborative-Perception-Datasets](https://github.com/frankwnb/Collaborative-Perception-Datasets-for-Autonomous-Driving)).
**No repository was found for either candidate.** This is "not found in that scope", not "proven not
to exist" — if Josh has a link, the conclusion below is reopened, not defended.

## Per candidate

### SmartCooper (arXiv 2402.00321, ICC 2024)

Channel-aware compression-ratio adaptation from CSI, plus a "judger" that drops unhelpful CAVs.

| criterion | finding |
|---|---|
| code availability | **none found** |
| weights | **none found** |
| dataset | OPV2V is used in the paper, so the split is not the obstacle |
| licence / last update | n/a — no repository |

**Seven-element alignment, if it were reimplemented:** checkpoint/backbone — would have to be trained
here, so it could not share ours; FOV, split, collaborator count, budget, AP/F1 convention — all
alignable; **channel and payload — not alignable in principle.** SmartCooper's contribution *is* a
learnable CSI-conditioned compression ratio, so its payload is an output of its own encoder. Forcing
it onto our fixed `w = 8` / `N_cw` chain would delete the mechanism being compared; leaving it free
means the two arms are not budget-matched. **Principled misalignment, not an engineering cost.**

### ML-Cooper

Switches between raw / feature / object level by channel condition and region density — the closest
published rival to this paper's selection layer.

| criterion | finding |
|---|---|
| code availability | **none found** |
| weights | **none found** |
| dataset | not established from the sources located |

**Seven-element alignment:** the *action space* is alignable and is in fact close to ours
(raw/feature/object ≈ our E/L/F). But a from-scratch reimplementation of an unreleased method,
evaluated against our own protocol, is **our** implementation of their idea — and if it loses, that
is uninformative. Memory of the 2026-07 supervisor meeting already recorded the correct handling:
**cite as the closest rival, do not reimplement.** This report reaches the same conclusion from the
reproducibility criteria rather than from that recollection.

## Recommendation

1. **Register P0-7 as UNMET** with this report as the evidence, rather than running a weak arm.
2. **Reposition the existing Where2comm arm** as the external comparator. It is already in this
   repository, already under the unified GT/FOV track, and already gated — the R60-2 wording rules
   restrict it to a post-hoc budget-matched mixture analysis with no adjudication verbs, and those
   rules stay exactly as they are.
3. **Cite ML-Cooper and SmartCooper** as related work, stating plainly that neither has a public
   release, so no like-for-like comparison was possible.

**GPU cost of the recommendation: zero.** The Where2comm products exist. That is a consequence of the
finding, not a reason for it.

## What must be frozen before the test unseal (C-5)

If Josh accepts the recommendation, the item to freeze is the **Where2comm** arm's method,
checkpoint, configuration, FOV, payload algorithm and evaluation convention — not a Tier C candidate.
That freeze is a precondition of B-8 either way.
