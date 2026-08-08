# CA-TOSG — FROZEN EXPERIMENTAL PROTOCOL (P1)

**Status:** frozen protocol contract for the P2 rebuild. This file fixes the evaluation
protocol *before* any number is regenerated. It does **not** report results — every number
below is either a protocol parameter (an input we choose) or a payload constant derived from
the rate/modulation chain and cited to its generator. Reported results live in `results/` and
are indexed by `CLAIMS.md`.

**Authority.** Where a value is derivable, this file cites the script that derives it rather than
restating a literal. Payload constants are cited to `code/payload_audit.py` (which re-derives them
from first principles and bit-compares against `main.tex`). Nothing here supersedes a committed
generator; if this file and a generator disagree, the generator wins and this file is the bug.

---

## 1. Split roles (HARD bans)

Four data partitions, three distinct roles. The bans are **hard**: a violation is a protocol
breach, not a judgement call, and `code/check_leakage.py` is the resident gate that enforces them.

| Split | Role | Permitted operations | BANNED operations |
|---|---|---|---|
| **validate** (1980 frames, 9 OPV2V scenes) | training + development + λ / threshold selection | fit selector; scene-level train/dev sub-split; sweep λ; tune SNR threshold τ; model selection | — |
| **test** (scene-disjoint) | one-shot final test | a single frozen-model evaluation | **any** training, cross-validation, threshold search, λ re-selection, model selection, or hyper-parameter touch |
| **Culver-City** (domain shift) | one-shot final test | a single frozen-model evaluation | same bans as test |

- **validate is the ONLY split any fitting, tuning, or selection touches.** Everything that
  looks at the labels to *choose* something (selector weights, λ, τ, which model) happens here.
- **test / Culver-City are evaluated exactly once, with everything already frozen.** No number
  produced on test/Culver may have been used to pick a knob. If a knob was picked, it was picked
  on validate. This is not negotiable per-experiment.
- validate accuracy reported on the **full** 1980 frames (incl. the selector's own training
  frames) is **in-sample** and must be labelled as such wherever it appears; it is not comparable
  to held-out test/Culver without that note.

## 2. Split construction rule: scene-first, then channel-copy expansion

**Rule (fixed order):**
1. Partition by **scene** first. A scene is one OPV2V recording directory
   (`opv2v_data_dumping/<split>/<scene>/`). All frames of a scene, and later all of its channel
   copies, stay on the same side of every split boundary.
2. **Then** expand each side across the channel grid (§3). Channel copies are created *after* the
   scene partition, never before.

**BANNED: expand-then-split.** Creating the frame×SNR×channel grid first and then splitting rows
is forbidden — it places channel copies of the same scene on both sides and leaks. The within-
validate train/dev sub-split (§6) obeys the same scene-first order.

*OPV2V validate has 9 scenes* (frame counts 112/157/135/202/64/48/57/459/746 = 1980, sorted
scene-dir order; reconstructed by `code/expand_grid_clean.py` / `code/make_scene_split.py` and
asserted to sum to the dataset length). A scene-level 70/30 sub-split is therefore coarse
(≈6–7 train scenes / 2–3 dev scenes); this coarseness is recorded, not hidden.

## 3. Channel grid

- **SNR grid:** {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20} dB (11 points), read as Es/N0, identical
  axis to the BLER table and to `code/true_e2e_global.py`.
- **Channels:** {AWGN, Rayleigh}.
- **P2 training substrate** = the full deterministic product **frame × 11 SNR × 2 channel**
  (uniform over grid cells), built by `code/expand_grid_clean.py`. This is a dense, deterministic
  expansion — NOT the per-frame single random draw frozen into `dataset_*_v3.csv`, and NOT the
  200-realisation Monte-Carlo deployment eval.
- **BLER source:** Sionna 5G-LDPC (k=500, n=1000) rate-1/2 + 16/256-QAM frame-level table
  `results/bler_sionna/bler_sionna.csv` (`bler_frame` column). Rayleigh frame BLER = 1 across
  0–20 dB (direct table lookup, no numerical averaging).
- **Deployment eval distribution** (reported policy numbers, separate from the training substrate):
  per-frame SNR ~ U[0,20] dB × channel ~ Bernoulli(0.5 Rayleigh), 200 realisations
  (`code/recompute_policy_200seed.py`). The two must not be conflated.

## 4. Action set S = {E, L, F}

| Action | Meaning | Channel-use cost | BLER | Source of the cost |
|---|---|---|---|---|
| **E** | ego-only (no message) | B_E = 0 | n/a (always delivered) | by definition |
| **L** | object-level message | B_L = 0.024 Msym | BLER_L = 0 (mainline: assumed reliably delivered) | `code/payload_audit.py` link (0.024 Mbit info, rate-1/2 QPSK ≈1 b/ch-use) |
| **F** | feature-level message | B_F = 0.99 Msym | BLER_F(SNR, channel) from the Sionna table | `code/payload_audit.py` link (1.98 Mbit info → /0.5 LDPC → 3.96 Mbit → /4 for 16-QAM) |

- **Main experiment transports F with rate-1/2 LDPC + 16-QAM.**
- **Effective utility** per cell: `eff_E = ego_f1`; `eff_L = late_f1` (BLER_L = 0 mainline);
  `eff_F = compressed_f1·(1 − BLER_F) + ego_f1·BLER_F` (ego-only failure fallback).
- **Oracle label** = argmax over {E, L, F} of the effective utility (E is a first-class action,
  so an infeasible F simply loses to E/L; the label naturally handles undeliverable requests).
  This is the P2 formalism and **differs** from the legacy `oracle_3way` over {L, C16, C256} in
  the v3 datasets — the legacy label folds ego only into the failure fallback, not as an action.
- **C256 (256-QAM feature variant), positioning — frozen wording (do not paraphrase):**

  > The same feature-level message is additionally evaluated with 256-QAM as a physical-layer
  > comparator, but it is not included in the deployed semantic action set.

## 5. Bandwidth budget B_max

- **B_max ∈ {0.10, 0.20, 0.30} Msym/frame** — the operating budgets swept for the constrained
  problem (§6).
- **Intended derivation:** available channel-uses/s ÷ LiDAR frame rate (802.11bd parameters).
- **Status: NOT physically derived — frozen as *normalized resource budgets*.** The repo commits
  an 802.11bd 10 MHz OFDM numerology only for the *channel BLER model*
  (`analysis_tools/build_bler_sionna_ofdm.py`: N_FFT=64, N_SC=52 data subcarriers, Δf=156.25 kHz);
  it commits **no** channel-uses/s → per-frame-symbol-budget mapping, and none is derived here (a
  physical mapping requires guard-interval / occupied-bandwidth assumptions not committed, and
  fabricating them would put a memory-sourced number into a frozen contract). The three B_max
  values are therefore treated as **relative operating points on the payload–accuracy frontier**,
  not physical link capacities. A physical-capacity mapping is deferred (P2+); until then all
  B_max-referenced text must say "normalized resource budget", not a Mbit/s link rate.

## 6. λ selection (five steps) + freeze rule

The constrained objective is `max_g E[F_t^{s_t}]  s.t.  E[B_{s_t}] ≤ B̄_max`, relaxed with a
Lagrange multiplier λ ≥ 0 (`main.tex` Eq. around L204). λ, the selector, and the SNR-threshold
baseline τ are all chosen on **validate only**, then frozen.

1. **Build the validate substrate.** On validate, compute the per-cell effective utilities over
   the §3 grid (`eff_E/eff_L/eff_F`) and the feasibility mask (F removed where BLER_F ≥ 0.999).
2. **Sweep λ.** Over a fixed λ grid ({0} ∪ geomspace, as in `recompute_policy_200seed.py`),
   compute the feasibility-masked argmax policy `argmax_a (eff_a − λ·B_a)` per λ → the validate
   payload–F1 frontier.
3. **Select λ\*(B_max).** For each target B_max ∈ {0.10, 0.20, 0.30}, pick λ\* as the smallest λ
   whose validate mean payload ≤ B_max (the tightest-utility point meeting the budget). Report
   the mapping B_max → λ\* as part of the frontier, not as a tuned free parameter.
4. **Freeze, then train the deployed selector.** Freeze λ\*. Train the Random-Forest selector to
   imitate the λ\*-oracle labels **on validate only** (scene-level train/dev sub-split per §2/§6;
   model/hyper-parameter selection uses dev, never test/Culver).
5. **Apply frozen everything to test/Culver.** Evaluate the frozen selector at the frozen λ\* on
   test and Culver **once**, with no re-tuning. The SNR-threshold baseline τ is likewise tuned on
   validate (fine grid, argmax mean validate F1) and reused verbatim on test/Culver — the τ from a
   different terrain is never carried over, and τ is never re-fit on the test terrain.

**Freeze rule.** Once step 4 completes, λ\*, the selector checkpoint, and τ are immutable for the
remainder of the evaluation. Any change to any of them invalidates every test/Culver number and
requires re-freezing from validate. `code/check_leakage.py` asserts no fitting/tuning artefact on
test/Culver.
