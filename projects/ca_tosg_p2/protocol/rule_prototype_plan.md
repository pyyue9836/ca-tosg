# Rule-based prototype — evaluation plan (P2-R10 D)

**Status: plan only. Nothing here has been run.** It executes after the accounting is ruled
(`message_regime.md` B-5), on CPU, from the committed P1 grid products. No random forest is trained,
no GPU is used, `test` and Culver-City stay closed, and the content of F does not change.

## D-1 The arms

All on OPV2V `validate`, **all 1,980 frames × 22 channel cells**:

| arm | rule |
|---|---|
| Fixed E | ego-only on every frame |
| Fixed L | object-level message on every frame |
| Fixed F | complete F on every frame |
| **channel-only rule** | `SNR ≥ τ → F, otherwise L`; **τ swept over the whole 11-point SNR grid and the entire curve reported**, not only the chosen point |
| **channel rule + E criterion** | the same, with the E criterion of `e_criterion.md` applied first: a frame that meets it takes E regardless of the channel |

The two rule arms are evaluated under whichever accounting is ruled in B-5; the choice changes
`eff_F` and nothing else in this plan.

## D-2 What is reported

* **Scene-equal F1** — the scene is the unit, as in P1.
* **Communication in QAM data symbols** (per frame and as a mean), never as a delivery time (A-1).
* **The E / L / F share** of each arm.
* **Per cell, and by channel type separately. Rayleigh and AWGN are never averaged together** — the
  message-accounting table already shows the two behave differently enough that a pooled mean would
  describe neither.

## D-3 What is being looked for

* the cells where F and L cross — where the channel is good enough for F to be worth its payload;
* what adding the E criterion changes: which frames move to E, what it costs in F1 and saves in
  payload, and whether the crossing cells move.

Both are observations. Neither is a success criterion, and this plan carries no pre-registered
threshold: it is a prototype evaluation, and any confirmatory claim needs its own pre-registration.

## D-4 How τ is chosen, and why it is not P1's τ

τ is swept on `validate` and the **whole curve** is reported; the chosen point is stated together with
the rule that chose it, before any comparison is drawn from it.

**P1's τ = 16.5 is not carried over.** That value was the budget-feasible optimum under P1's
λ-penalised objective at β = 0.20 — it answers "which threshold maximises utility subject to a mean
payload budget", a question this plan does not ask. Reusing the number would import a budget
constraint that is not part of this arm. The τ used here is derived within this plan and labelled as
such wherever it appears.
