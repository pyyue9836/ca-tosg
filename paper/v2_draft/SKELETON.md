# v2 manuscript — P5 skeleton (V2-R36 D)

**Status: framework only.** Every Where2comm cell is `<PENDING F-2>` and stays that way until the
deterministic regeneration lands. The v1 manuscript remains frozen; the stop-work order is lifted
**for this draft only** (D-6).

**No directional statement about Where2comm may be written here in advance (D-3).** Not "better
than", not "comparable to", not "competitive with" — the cells are empty because the numbers do not
exist yet, and a sentence written before them would be a conclusion looking for data.

---

## 1. Main conclusion — FIXED WORDING (V2-R35 C-2), not to be paraphrased

> CA-TOSG achieves approximately **99.7 %–99.9 %** communication saving on both Test and
> Culver-City, but on **both** datasets the bootstrap lower confidence bound fails the pre-registered
> accuracy non-inferiority margin. **Communication saving, and its cross-domain transfer, are
> supported; accuracy preservation, and its cross-domain transfer, are not statistically confirmed.**

Both halves appear together, always. The criterion is joint (R9), so the saving may not be presented
as an overall success (gate: `tracked_terms.md`, "payload saving presented as overall success").

## 2. Results table — primary cell β = 0.20

| split | arm | scene-equal F1 | payload (Msym) | ΔF1 point | ΔF1 LCB95 | rel. saving |
|---|---|---|---|---|---|---|
| Test | frozen RF (cand 67) | 0.87679 | 0.00081 | — | — | — |
| Test | frozen τ = 16.5 | 0.88178 | 0.54102 | −0.00499 | **−0.00738** | **99.85 %** |
| Culver | frozen RF (cand 67) | 0.87352 | 0.00147 | — | — | — |
| Culver | frozen τ = 16.5 | 0.87813 | 0.49850 | −0.00461 | **−0.00541** | **99.70 %** |
| Test | Where2comm | `<PENDING F-2>` | `<PENDING F-2>` | — | — | — |
| Culver | Where2comm | `<PENDING F-2>` | `<PENDING F-2>` | — | — | — |

δ = 0.005. **Both LCBs fall outside it.** Non-inferiority is NOT established on either split.

**Dual accounting, reported together and never mixed (V2-R6 B-3):**

| split | no-collaborator share | full-frame saving | collaborator-available saving | difference |
|---|---|---|---|---|
| Test | 5.48 % | 99.85 % | 99.85 % | +0.000 pp |
| Culver | 13.09 % | 99.70 % | 99.70 % | +0.000 pp |

## 3. Contributions — three, at Case B/C (V2-R33 C)

1. a unified, reproducible E/L/F granularity-control framework with **measured** communication
   accounting (per-frame `B_L,t`, `B_F` derived from the codeword count);
2. mechanism findings: partial recovery is necessary; loss **position** affects the outcome at equal
   loss **amount** (level 1, strict); zero-tensor fusion ≠ ego-only;
3. an empirical finding: the frozen selector cuts communication by ~99.8 % **and** the evidence for
   accuracy preservation is insufficient under a strict scene-level bootstrap.

## 4. Limitations — written before the discussion, so they are not softened into it

* **The primary criterion was not met.** Point estimates sit inside δ on both splits; the confidence
  bounds do not. The criterion is defined on the bound.
* **The Culver bootstrap resamples 4 scenes.** Coarse interval; the same shape as Test on far less
  scene diversity — a limitation, not corroboration.
* **ρ_F = 0.000.** The expensive feature action is never selected by the frozen selector. Reported
  as D-3's two questions — a learning question and a design question — never merged.
* **No three distinct budget points.** All three β select the same candidate; the budget never binds
  (P1-2 fired).
* **The λ grid was too coarse** to sample the interval where a mixed E/L/F policy is selectable
  (break-even λ = 0.01556 conditional on F-best rows, against a smallest non-zero grid point of
  0.02). Registered for a future design, **not** used to revise this freeze.
* **P0-7 is UNMET.** No external channel-adaptive granularity baseline was reproducible; Where2comm
  serves as a feature-content / communication-efficient comparator only.
* **Selector-only latency**; total system latency is not measured (P1-7).

## 5. P2 rewrite checklist (V2-R36 D-5)

| id | item | state |
|---|---|---|
| P2-1 | abstract: problem, method, E/L/F, core payload–performance result, mechanism conclusion | framework |
| P2-2 | contributions compressed to three | §3 above |
| P2-3 | remove internal-audit language from the main text | pending |
| P2-4 | rewrite the Conclusion: what was done, what was shown, under what conditions | framework |
| P2-5 | baselines layered: fixed policy / internal rule / feature-content / adaptive / oracle | pending |
| P2-6 | document fixes: supplementary title+authors, CSV lists moved, duplicate commands, citations | pending |

## 6. Where2comm — the sentence that may be written once F-2 lands

**Permitted form only:** an external feature-content / communication-efficient baseline, compared
post-hoc at a matched budget under the evaluated transport, **with no adjudication verb and no
margin** (R60-2, unchanged). It answers "how does this compare with an existing
communication-efficient cooperative method" and **may not be used to reinterpret or rescue the
primary criterion** (V2-R35 C-3).
