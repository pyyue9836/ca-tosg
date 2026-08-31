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
| Test | Where2comm (thr 0.02) | AP@0.5 0.91708 / AP@0.7 0.82989 | **N/A** (§6) | — | — | comm_rate 0.0521 |
| Culver | Where2comm (thr 0.02) | AP@0.5 0.83195 / AP@0.7 0.71588 | **N/A** (§6) | — | — | comm_rate 0.0908 |

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

**The paragraph, verbatim (V2-R40 B-8):**

> Where2comm is evaluated under the same data splits, field of view, ground truth and detection
> metrics. We report its native communication rate because the evaluated implementation transmits
> floating-point selected features and does not execute the locked v2 int8 quantisation path.
> Consequently, it is excluded from bit-level budget-matched claims.

**It carries NO Msym value.** Assigning one under `w = 8` would charge one pipeline and run another
— the billing≠pipeline ban (V2-R3 B-2), whose naming origin was this very arm's transport. Second
occurrence on the same arm.

**This is not "no external baseline" (B-9).** The arm answers a real question: *what AP does an
external spatial feature-selection method reach under a unified perception convention, and what
fraction of the features must it keep?* What it cannot do is pose as a strict Msym-matched
comparison.

**The primary comparator remains the frozen τ = 16.5** — the only arm sharing CA-TOSG's complete v2
payload definition (B-5). R60-2's limits are unchanged: no adjudication verb, no margin.

**Future work, not scheduled (B-10):** putting Where2comm on the unified Msym axis needs a real int8
quantise/dequantise path and a re-run — a new experiment version, not part of this close-out.

**Provenance:** OpenCOOD `31ba1602`, locally-trained epoch-50 checkpoint `4928071f…`,
`CATOSG_EVAL_RNG=1`, `CATOSG_MAX_COLLAB=1`, v2 corner-filter GT. The pre-deterministic **validate**
sweep is excluded from every number here (gate 30) and its `B_w2c_msym` column is retired outright.

| split | thr | comm_rate | AP@0.5 | AP@0.7 | payload |
|---|---|---|---|---|---|
| culver | 0.0 | 1.0000 | 0.84139 | 0.71694 | N/A |
| culver | 0.01 | 0.4851 | 0.84118 | 0.71832 | N/A |
| culver | 0.011 | 0.4331 | 0.84035 | 0.71761 | N/A |
| culver | 0.012 | 0.3825 | 0.83927 | 0.71770 | N/A |
| culver | 0.013 | 0.3117 | 0.83764 | 0.71664 | N/A |
| culver | 0.015 | 0.1264 | 0.83419 | 0.71643 | N/A |
| culver | 0.02 | 0.0908 | 0.83195 | 0.71588 | N/A |
| culver | 0.025 | 0.0730 | 0.83116 | 0.71523 | N/A |
| culver | 0.03 | 0.0608 | 0.82918 | 0.71432 | N/A |
| culver | 0.04 | 0.0463 | 0.82578 | 0.71057 | N/A |
| culver | 0.05 | 0.0379 | 0.82119 | 0.70771 | N/A |
| culver | 1.1 | 0.0000 | 0.69374 | 0.58007 | N/A |
| test | 0.0 | 1.0000 | 0.92095 | 0.83020 | N/A |
| test | 0.01 | 0.4648 | 0.92004 | 0.83170 | N/A |
| test | 0.011 | 0.4222 | 0.91954 | 0.83177 | N/A |
| test | 0.012 | 0.3786 | 0.91936 | 0.83162 | N/A |
| test | 0.013 | 0.3130 | 0.91877 | 0.83116 | N/A |
| test | 0.015 | 0.0802 | 0.91808 | 0.83076 | N/A |
| test | 0.02 | 0.0521 | 0.91708 | 0.82989 | N/A |
| test | 0.025 | 0.0392 | 0.91511 | 0.82861 | N/A |
| test | 0.03 | 0.0314 | 0.91405 | 0.82904 | N/A |
| test | 0.04 | 0.0227 | 0.91121 | 0.82588 | N/A |
| test | 0.05 | 0.0179 | 0.90799 | 0.82360 | N/A |
| test | 1.1 | 0.0000 | 0.79757 | 0.68224 | N/A |
