# R9 RF-vs-threshold result — LOCKED claim wording (P2-B)

Durable record of the R9 decision result and its **verbatim allowed wording**. `CLAIMS.md` is
auto-generated from `main.tex`, so this file (not a hand-added `CLAIMS.md` row) is the authority for
the wording; when the sentence lands in `main.tex` at P5 it must use the locked text below and its
`CLAIMS.md` row's *Allowed wording* column points here. Source data:
`results/p2_deploy/replay_summary.csv` + `replay_test_B020.csv` (paired bootstrap, 10,000 resamples,
percentile). Metric = frame-level realised F1 / channel-use payload. Margin δ = 0.005 (PROTOCOL R9).

## PRIMARY — test @ B_max = 0.20 (the sole confirmatory comparison)

| Field | Value |
|---|---|
| ΔF = F1_RF − F1_τ | −0.0028 (mean); 95% CI = [−0.0029, −0.0027] (entirely below zero) |
| Non-inferiority | LCB95(ΔF) = −0.0029 > −δ (= −0.005) → **non-inferior** |
| Payload | B_RF = 0.095 vs B_τ = 0.217 Msym; reduction **56.3%**; UCB95(ΔB) < 0 |
| Verdict | RF is F1 **non-inferior** (within the pre-registered 0.005 margin) AND communication-superior |

**Allowed wording (verbatim, locked):**

> RF's F1 is significantly lower than the threshold rule by ≈0.0028 (95% CI entirely below zero) yet
> within the pre-registered non-inferiority margin of 0.005, while reducing communication payload by
> 56.3%.

**BANNED wording** (misrepresents a small-but-significant F1 loss as no loss): "same F1", "no accuracy
loss", "matches F1", or any phrasing implying RF's F1 equals or is not below the threshold rule's.

## SECONDARY (CI only — no non-inferiority decision; multiple-comparison protection, R9e)

| Comparison | ΔF mean | ΔF 95% CI | Note |
|---|---|---|---|
| **Culver-City @ B_max=0.20** | **−0.0099** | ≈ [−0.0100, −0.0097] | **exceeds the δ = 0.005 margin** — reported honestly as secondary, not adjudicated |
| test @ B_max=0.10 | +0.0005 | small positive difference; the 95% CI [+0.00046, +0.00065] is entirely above zero | secondary — CI only, not adjudicated |
| test @ B_max=0.30 | −0.0021 | below 0, within δ | secondary |
| validate (all budgets) | — | — | in-sample reference only, not a generalisation claim |

_The Culver-City ΔF exceeds the non-inferiority margin; because Culver is secondary, this is stated
as an observed CI, not a non-inferiority conclusion. Do not aggregate it into the primary claim._
