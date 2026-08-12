# CA-TOSG — FROZEN EXPERIMENTAL PROTOCOL (P1.5)

**Status:** frozen protocol contract for the P2 rebuild. This file fixes the evaluation
protocol *before* any number is regenerated. It does **not** report results — every number
below is either a protocol parameter (an input we choose) or a payload constant derived from
the rate/modulation chain and cited to its generator. Reported results live in `results/` and
are indexed by `docs/claims.md`.

**Authority.** This file **defines the experiment's intent**: the protocol, the candidate set, and
the selection rules are specified here and nowhere else. If a generator (training/eval script)
disagrees with this file, that is a **code bug** — stop immediately and fix the code to match the
protocol; do not "reconcile" by editing the protocol to match the code. Where a value is derivable,
this file cites the script that derives it rather than restating a literal (e.g. payload constants →
`tests/test_payload.py`, which re-derives them from first principles and bit-compares against
`main.tex`); a citation is a pointer to a derivation, not a delegation of authority.

---

## 1. Split roles (HARD bans)

Four data partitions, three distinct roles. The bans are **hard**: a violation is a protocol
breach, not a judgement call, and `tests/test_data_leakage.py` is the resident gate that
enforces them.

| Split | Role | Permitted operations | BANNED operations |
|---|---|---|---|
| **validate** (1980 frames, 9 OPV2V scenes) | training + development + λ / threshold selection | fit selector; scene-level LOSO (9-fold) for hyper-parameter + λ selection; sweep λ; tune SNR threshold τ; model selection | — |
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
- **Canonical framing sentence** (use this wording; do not write "never inspected" or similar):
  *All parameters were frozen on the validate split before the reported P2 evaluation on test and
  Culver-City.*

## 2. Split construction rule: scene-first, then channel-copy expansion

**Rule (fixed order):**
1. Partition by **scene** first. A scene is one OPV2V recording directory
   (`opv2v_data_dumping/<split>/<scene>/`). All frames of a scene, and later all of its channel
   copies, stay on the same side of every split boundary.
2. **Then** expand each side across the channel grid (§3). Channel copies are created *after* the
   scene partition, never before.

**BANNED: expand-then-split.** Creating the frame×SNR×channel grid first and then splitting rows
is forbidden — it places channel copies of the same scene on both sides and leaks. The within-
validate cross-validation (§6, scene-level LOSO) obeys the same scene-first order: folds are cut by
scene, and channel copies inherit the scene's fold.

*OPV2V validate has 9 scenes* (frame counts 112/157/135/202/64/48/57/459/746 = 1980, sorted
scene-dir order; reconstructed by `projects/ca_tosg/datasets/scene_split.py`, asserted to sum to the dataset
length, and independently
cross-checked by `test_data_leakage.py` against an independent loader-order scene manifest
(`scene_split.py`, a different code path)). Model/hyper-parameter and λ
selection use **scene-level 9-fold LOSO** over these 9 scenes rather than a single 70/30 dev split
(Change-log R1): a single split leaves the dev set at only 2 scenes, whose F1 is too high-variance
to select on.

## 3. Channel grid

- **SNR grid:** {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20} dB (11 points), read as Es/N0, identical
  axis to the BLER table and to `projects/ca_tosg/evaluation/true_e2e_global.py`.
- **Channels:** {AWGN, Rayleigh}.
- **P2 training substrate** = the full deterministic product **frame × 11 SNR × 2 channel**
  (uniform over grid cells), built by `projects/ca_tosg/datasets/grid_builder.py`. This is a dense, deterministic
  expansion — NOT the per-frame single random draw frozen into `dataset_*_v3.csv`, and NOT the
  200-realisation Monte-Carlo deployment eval.
- **BLER source:** Sionna 5G-LDPC (k=500, n=1000) rate-1/2 + 16/256-QAM frame-level table
  `results/channel/bler_sionna.csv` (`bler_frame` column). Rayleigh frame BLER = 1 across
  0–20 dB (direct table lookup, no numerical averaging).
- **Deployment eval distribution** (reported policy numbers, separate from the training substrate):
  per-frame SNR ~ U[0,20] dB × channel ~ Bernoulli(0.5 Rayleigh), 200 realisations, produced by the
  **P2-B new deployment script (to be built)** reading only `FROZEN_MANIFEST.json` (the legacy
  `policy_200seed.py` is fused off). The two distributions must not be conflated.

## 4. Action set S = {E, L, F}

| Action | Meaning | Channel-use cost | BLER | Source of the cost |
|---|---|---|---|---|
| **E** | ego-only (no message) | B_E = 0 | n/a (always delivered) | by definition |
| **L** | object-level message | B_L = 0.024 Msym | BLER_L = 0 (mainline: assumed reliably delivered) | `tests/test_payload.py` link (0.024 Mbit info, rate-1/2 QPSK ≈1 b/ch-use) |
| **F** | feature-level message | B_F = 0.99 Msym | BLER_F(SNR, channel) from the Sionna table | `tests/test_payload.py` link (1.98 Mbit info → /0.5 LDPC → 3.96 Mbit → /4 for 16-QAM) |

- **Main experiment transports F with rate-1/2 LDPC + 16-QAM.**
- **Effective utility** per cell: `eff_E = ego_f1`; `eff_L = late_f1` (BLER_L = 0 mainline);
  `eff_F = compressed_f1·(1 − BLER_F) + ego_f1·BLER_F` (ego-only failure fallback).
- **Oracle label** = argmax over {E, L, F} of the effective utility, computed on a **feasibility-
  masked** utility vector: where BLER_F ≥ 0.999 (certain failure), F's oracle target is set to
  −∞ so an undeliverable feature request can never be labelled (it would spend channel-use for zero
  information; masking, not preference — same semantics as `opv2v.py`, Change-log R2). The
  `eff_F` COLUMN keeps the true effective utility (used by every policy evaluation); only the oracle
  LABEL argmax is masked. E is a first-class action, so E/L still win naturally where F is feasible
  but weak. This is the P2 formalism and **differs** from the legacy `oracle_3way` over
  {L, C16, C256} in the v3 datasets — the legacy label folds ego only into the failure fallback,
  not as an action.
- **C256 (256-QAM feature variant), positioning — frozen wording (do not paraphrase):**

  > The same feature-level message is additionally evaluated with 256-QAM as a physical-layer
  > comparator, but it is not included in the deployed semantic action set.

## 5. Bandwidth budget B_max

- **B_max ∈ {0.10, 0.20, 0.30} Msym/frame** — the operating budgets swept for the constrained
  problem (§6).
- **One model per budget** (Change-log R5): a **separate** selector is frozen for each B_max —
  `selector_B010` / `selector_B020` / `selector_B030` — because λ\*(B_max) differs; the manifest
  records all three model hashes.
- **Intended derivation:** available channel-uses/s ÷ LiDAR frame rate (802.11bd parameters).
- **Status: NOT physically derived — frozen as *prespecified channel-use budgets*** (Change-log
  R3; the earlier "normalized resource budget" wording is retired — "normalized" wrongly implied a
  unit-normalisation). The repo commits an 802.11bd 10 MHz OFDM numerology only for the *channel
  BLER model* (`projects/ca_tosg/communication/channel.py`: N_FFT=64, N_SC=52 data subcarriers,
  Δf=156.25 kHz); it commits **no** channel-uses/s → per-frame-symbol-budget mapping, and none is
  derived here (a physical mapping requires guard-interval / occupied-bandwidth assumptions not
  committed, and fabricating them would put a memory-sourced number into a frozen contract). The
  three B_max values are therefore **prespecified operating points (in Msym/frame) on the
  payload–accuracy frontier**, not physical link capacities. A physical-capacity mapping is deferred
  (P2+); until then all B_max-referenced text must say "prespecified channel-use budget", not a
  Mbit/s link rate.

## 6. Selection candidates + LOSO procedure + freeze rule (ONE MODEL PER BUDGET)

The constrained objective is `max_g E[F_t^{s_t}]  s.t.  E[B_{s_t}] ≤ B̄_max`, relaxed with a
Lagrange multiplier λ ≥ 0 (`main.tex` Eq. around L204). For **each** budget B_max ∈ {0.10, 0.20, 0.30}
a **separate** selector is frozen — `selector_B010`, `selector_B020`, `selector_B030` (§5, Change-log
R5) — because λ\*(B_max) differs; all three model hashes are recorded in `FROZEN_MANIFEST.json`.

**Candidate set — SINGLE SOURCE OF TRUTH.** `projects/ca_tosg/models/selector.py` **parses the JSON
block below** and must not hard-code these values anywhere else. A *candidate* is one
(RF hyper-parameters, `class_weight`, λ) tuple; τ is a separate SNR-threshold baseline, not an RF
candidate. **IRON RULE:** any expansion of these candidates *after* training requires a new Change-log
entry **and a full retrain** — the frozen models must always correspond to exactly this block.

```json CATOSG-CANDIDATES
{
  "seed": 0,
  "hyperparameters": {
    "n_estimators": [400],
    "max_depth": [10, null],
    "min_samples_leaf": [2, 4],
    "max_features": ["sqrt", 0.5]
  },
  "class_weight": [null, "balanced"],
  "lambda_grid": [0.0, 0.02, 0.05, 0.1, 0.2, 0.35, 0.5],
  "tau_grid": {"start": 0.0, "stop": 20.0, "step": 0.5},
  "budgets": [0.10, 0.20, 0.30],
  "loso": {"scheme": "scene-level", "folds": 9, "each_scene_heldout_once": true},
  "aggregation": {"performance": "frame_weighted_oof_f1",
                  "robustness": "scene_mean_realised_f1",
                  "feasibility": "frame_weighted_oof_payload"},
  "selection": "frozen_walk",
  "tie_break": ["max_f1", "min_payload", "shallower_model", "min_candidate_index"]
}
```

**LOSO procedure (Change-log R1, R6).** Scene-level 9-fold LOSO on validate: each of the 9 scenes is
held out **exactly once**. For each candidate, train the RF on the 8 non-held-out scenes' λ-oracle
labels (feasibility-masked argmax of `eff_a − λ·B_a`, §4) and, on the held-out scene, record the
out-of-fold (OOF) **realised** F1 and payload (mean `eff` / mean payload of the selector's OWN picks)
together with that scene's frame count `N_k`. Every (fold × candidate) row — including `n_frames` —
is written to `results/manifests/validate_loso_folds.csv`, so both aggregates below are recomputable
from the deliverable itself.

**Aggregations (Change-log R7).** All from `validate_loso_folds.csv`:
- **Performance criterion (PRIMARY)** = **frame-weighted OOF realised F1**
  `Σ_k N_k·F1_k / Σ_k N_k` (`N_k` = fold-k scene frame count). This matches the paper's `E[F]` and the
  deployment report, and it ranks candidates.
- **Scene-mean realised F1** (mean over the 9 folds, scenes equal) is demoted to a **robustness
  supplement** — recorded in the manifest and the results table, but not the ranking key.
- **Budget feasibility** = **frame-weighted OOF payload** `B_OOF = Σ_k N_k·B̄_k / Σ_k N_k`.

**Frozen walk, per B_max (Change-log R7 — treats OOF under-estimating the retrain payload).**
(1) Take the OOF-feasible set `{candidate : B_OOF ≤ B_max}`; (2) order it by frame-weighted OOF F1
**descending**, tie-break lower `B_OOF` → shallower model (`null` max_depth ranked last) → smallest
candidate index; (3) write this order to `results/manifests/candidate_walk_B0XX.csv` **before any
retrain** (pre-registration of the walk); (4) walk down the order — retrain each candidate on **all
1980** validate frames and hard-check `B̄_frozen ≤ B_max` (strict, NO tolerance) — and **take the first
candidate that passes**, recording its `walk_depth`. If the walk is exhausted with none passing,
**fuse and report**; the only permitted fix is a new Change-log entry that expands the λ grid, after
which the whole run is redone. This guarantees each frozen model actually meets its budget.

**τ\*(B_max) — same performance + budget aggregation as the selector (R7a).** On the FULL validate
grid (each frame contributes its 22 cells equally, so the grid mean *is* frame-weighted), sweep the
SNR-threshold baseline (awgn & snr>τ → F else L; Rayleigh → L) over the τ grid; τ\*(B_max) = the
threshold with the highest frame-weighted realised F1 whose payload ≤ B_max. Per-split threshold
search is banned from here on.

**Manifest (R7).** Only when **all three** budgets pass the walk is `FROZEN_MANIFEST.json` written.
Its per-budget record carries `loso_frame_weighted_f1` (primary), `loso_scene_mean_f1` (supplement),
`loso_frame_weighted_payload`, `frozen_validate_payload`, `walk_depth`, and `budget_satisfied`,
alongside the three model sha256, the **folds CSV sha256** and grid/cue input hashes, the candidate
signature, the cue path as `os.path.relpath(cues, paper1)`, the environment
(python/sklearn/numpy/pandas), and the timestamp. Nothing after may look at test/Culver labels.

**Rule-freeze clause (Change-log R7d).** The selection rules above are **frozen from R7 onward**. Any
later change is permitted **only** when triggered by a fuse and accompanied by its own new Change-log
entry — no silent re-tuning of the criterion, the walk, or the tie-break.

**Frozen-state gate checks (Change-log R6 + R7; all FAIL, never skip).** With a manifest present,
`tests/test_data_leakage.py` asserts: (1) every budget's `frozen_validate_payload ≤ B_max`;
(2) every budget's frame-weighted OOF payload is on record AND `≤ B_max`; (3) every referenced model
file exists (missing = FAIL); (4) any missing input (grid / cues / manifest / folds) = FAIL; (5)
`schema` is exactly `catosg-frozen-manifest/1`; (6) `candidate_block_md5` equals the md5 of the current
PROTOCOL `CATOSG-CANDIDATES` block; (7) `validate_loso_folds.csv` has exactly 112 × 9 = 1008 rows.
**R7 additions:** (8) the folds CSV **sha256** matches the manifest, and the per-row candidate params
match the PROTOCOL candidate block (asserted **even with no manifest**); (9) the OOF metrics are
**recomputed from the folds** and cross-checked against the manifest values (mismatch = FAIL); (10)
the manifest cue path resolves via `os.path.join(paper1, relpath)` (any path-resolution failure =
FAIL).

**Apply to test/Culver (P2 submit-B).** Evaluate the three frozen selectors at their frozen λ\*/τ\*
on test and Culver **once**, reading only `FROZEN_MANIFEST.json`, with no re-tuning.

## 7. Single authoritative version

This is the ONE formal version of the CA-TOSG evaluation protocol. It supersedes any protocol
description embedded elsewhere (README / REPRODUCE / PROVENANCE / handoff notes / main.tex prose);
where another file disagrees, this file governs and the other is to be annotated "superseded by
docs/experiment_protocol.md". All revisions are pre-registered in the **Change-log** at the foot of this file, each
with a reason and a date, *before* any P2 training.

## 8. Post-P2 anomaly review — expectations + handling rules

After P2 regenerates the numbers, run the full anomaly checklist (`P2 submit-B step f`) and produce
a report. Every item below is an **expectation to test, not a target to hit**.

Expectations (each must hold on the regenerated results, else halt — see handling rules):
- **Provenance / plumbing (original checklist):** every reported number resolves to a regenerated
  source CSV + generator (docs/claims.md rows closed); no v1/v2/v3/_old/_bak naming survives in the
  pipeline or in main.tex/results (P2 submit-D assertion); `FROZEN_MANIFEST.json` exists and its
  md5s match the data actually used; payload chain still bit-audits (`tests/test_payload.py`).
- **Rayleigh:** BLER_F ≈ 1 so F ≈ ego, but the oracle/selector should still show **both E and L**
  (not necessarily 100 % L) — E wins where ego ≥ late, L where the object message helps.
- **AWGN low SNR:** the mix is **E/L-dominated** (F mostly infeasible or beaten).
- **High SNR:** the **F share increases** monotonically-ish as BLER_F falls.
- **No deployed action-distribution curve contains C256** (it is a physical-layer comparator only, §4).
- **validate budget points:** each B_max ∈ {0.10, 0.20, 0.30} operating point has validate mean
  payload ≤ its B_max.
- **test / Culver:** produced with **exactly one** frozen model + {λ\*} + {τ\*} from
  `FROZEN_MANIFEST.json`; no per-split refit anywhere.

Handling rules (binding):
1. **Expectation not met → STOP and diagnose.** Do not continue the pipeline; report the anomaly
   as-is with the numbers that produced it.
2. **No "artefact" hand-waves.** An unexpected result may NOT be annotated away as an "artefact"
   / "rounding" / "known quirk" without a diagnosed, written root cause.
3. **Never adjust the data to meet an expectation.** Expectations are falsifiable predictions; if
   the data disagrees, the finding changes, not the data.

## 9. JSCC edge — pre-registration

The graceful-channel (importance-map JSCC) two-regime edge is reported as an **in-distribution
analysis**, pre-registered here before P2/P5 recomputation (see the leakage history):
- Report **both** the k-fold **in-distribution** edge (the graceful-channel signal lives in the
  perception cues) **and** the cross-split **deployed** number (the honest transfer gap). The
  in-distribution qualifier is mandatory wherever the JSCC edge appears.
- **No headline JSCC number in the abstract.** The abstract carries no JSCC edge figure.
- The JSCC selector is fit/evaluated by **k-fold in-distribution** on the same split, explicitly
  distinct from the main deployed selector (§6), and this distinction must be stated at every use.
- Any JSCC edge value whose source was deleted in the P1/P1.5 cleanup is **evidence-orphaned** in
  `docs/claims.md` and must be recomputed under this rule or the sentence dropped (P5).

## 10. Pre-freeze data-generation constraint (Change-log R4)

Before `FROZEN_MANIFEST.json` exists (the **pre-freeze** stage), the ONLY data that may be
generated is the **validate** grid (`grid_builder.py --split validate`, the default).

- **test / Culver grids and their oracle labels MUST NOT exist pre-freeze.** They are generated by a
  **separate command, run only AFTER** the manifest is written (P2 submit-B step d).
- `tests/test_data_leakage.py` enforces this: with no manifest present it asserts the
  test/Culver grids are **absent**; with a manifest present they are optional (regenerated by the
  separate post-manifest command of P2 submit-B) and any that are present must be column-pure and
  built after the manifest timestamp.
- Rationale: generating the final-test substrate before the model is frozen is the first step of an
  accidental leak; forbidding it structurally removes the temptation.

---

## Change-log — pre-registered protocol revisions

All entries are pre-registered **before P2 training** (legitimate: a protocol may be revised until
the model is frozen, provided each change is logged with a reason and a date up front).

- **R1 (2026-08-08) — §2/§6: selection by scene-level 9-fold LOSO, replacing the single 70/30 dev
  split.** Reason: a single scene-first 70/30 split leaves the dev set at only 2 of the 9 validate
  scenes, whose realised F1 is too high-variance to select hyper-parameters or λ\* on. LOSO uses all
  9 scenes as held-out folds (each held out exactly once). The 70/30 mechanism
  (`make_scene_split.py`, `validate_scene_split.csv`, `PROVENANCE_split.txt`) is **removed entirely**
  (P2 submit-A); the leakage gate's disjointness check is replaced by the LOSO fold-structure
  assertion (each scene held out exactly once) against `validate_loso_folds.csv`.
- **R2 (2026-08-08) — §4: oracle label definition made explicit about the feasibility mask**
  (BLER_F ≥ 0.999 → F's oracle target = −∞). This was always the intended semantics
  (`opv2v.py`); it is now stated in the protocol and implemented in `grid_builder.py`.
- **R3 (2026-08-08) — §5: "normalized resource budget" → "prespecified channel-use budget".** The
  budgets are still not physically mapped to a link rate; the rename drops the misleading
  "normalized" (which implied a unit-normalisation that was never performed).
- **R4 (2026-08-08) — §10: pre-freeze stage restricted to validate-grid generation;** test/Culver
  grids + labels generated by a separate post-manifest command.
- **R5 (2026-08-08, P2 submit-A) — §5/§6: one model per budget + full candidate set as single source
  of truth + authority clause.** (i) A separate selector is frozen per B_max
  (`selector_B010/B020/B030`), all three hashes in the manifest, because λ\*(B_max) differs. (ii) §6
  now carries the complete candidate set — RF hyper-parameters (`n_estimators/max_depth/
  min_samples_leaf/max_features`), `class_weight ∈ {null, balanced}`, an explicit λ grid, a
  0–20 dB/0.5 dB τ grid, seed, scene-mean aggregation, and a fully-specified tie-break — as a machine
  -parseable `CATOSG-CANDIDATES` JSON block that `selector.py` parses (no candidate values are
  hard-coded in code). IRON RULE: expanding the candidates after training needs a new Change-log entry
  and a full retrain. (iii) The Authority clause now states PROTOCOL defines intent and a
  generator that disagrees is a code bug (the earlier "generator wins" sentence is removed). Legacy
  selectors `train_rf_v3.py` and `policy_200seed.py` are fused off (hard error at entry;
  removed at P2 submit-D).
- **R6 (2026-08-09, P2 submit-A correction) — §6: performance/feasibility semantic split + final-check
  iron rule + manifest/gate hardening.** (a) Model-selection *performance* is scene-mean realised F1;
  budget *feasibility* is the frame-weighted OOF payload `B_OOF = Σ N_k·B̄_k / Σ N_k` (not the
  scene-mean payload). (b) Per-budget ranking: feasibility gate `B_OOF ≤ B_max` → max scene-mean F1 →
  tie-break payload / shallower / index. (c) After the full-1980 retrain, a **hard** `B̄_frozen ≤ B_max`
  check (strict, no tolerance; a tolerance needs its own pre-registered entry) — on failure no manifest
  is written, no test/Culver grid is built, and the run fuses. (d) The manifest gains
  `loso_scene_mean_f1 / loso_frame_weighted_f1 / loso_frame_weighted_payload / frozen_validate_payload
  / budget_satisfied` and an environment block (python/sklearn/numpy/pandas versions);
  `validate_loso_folds.csv` gains `n_frames`; the gate runs seven frozen-state checks. The 1008 LOSO
  fits from R5 are **reused** (only the selection + feasibility are recomputed), then the three models
  are retrained on full validate and hard-checked.
- **R7 (2026-08-09, P2 submit-A 2nd correction) — §6: performance criterion unified + frozen-walk
  selection + rule-freeze.** (a) The PRIMARY criterion becomes **frame-weighted OOF realised F1**
  (matching the paper's `E[F]` and the deployment report); scene-mean F1 is demoted to a robustness
  supplement (both recorded). `τ*` uses the same frame-weighted + budget-matched aggregation. (b)
  Selection becomes a **frozen walk**: order the OOF-feasible candidates by frame-weighted OOF F1
  descending (walk order written to `candidate_walk_B0XX.csv` before any retrain), retrain each on
  full validate, and take the first whose `B̄_frozen ≤ B_max`; walk-exhaustion fuses (fix = a new
  entry expanding the λ grid, then a full redo). This resolves the R6 fuse, where the OOF-feasible
  max-F1 candidate could violate the budget once frozen. (c) Tie-break unchanged (payload → shallower
  → index). (d) **Rule-freeze:** the selection rules are frozen from R7; later changes only via a
  fuse-triggered new Change-log entry. Plus: manifest gains folds sha256 + candidate signature + cue
  relpath; the gate recomputes OOF metrics from the folds and cross-checks; CLAIMS stable IDs fold in
  only *explicit* mode markers (C16/C_16/16-QAM/C256/C_256/256-QAM), not plain "16 dB"/"16 %".

- **R8 (2026-08-09) — RF-vs-threshold decision rule. SUPERSEDED by R9** (the "95% CI containing zero"
  wording conflated absence-of-evidence with a non-inferiority claim). The walk-evidence-chain audit it
  also registered (re-execute the walk, log every attempted candidate's frozen outcome, assert winners
  match `FROZEN_MANIFEST.json`, mismatch fuses without overwriting) remains in force under R9.
- **R9 (2026-08-09, pre-registered before P2-B) — Non-inferiority margin and primary comparison
  (replaces the R8 rule). The following paragraph is the normative contract text (verbatim):**

  > R9 — Non-inferiority margin and primary comparison. Before any test or Culver-City evaluation, the
  > absolute non-inferiority margin is fixed as δ = 0.005 F1, corresponding to a maximum tolerable loss
  > of 0.5 percentage points in mean frame-level F1. Define ΔF = F1_RF − F1_τ and ΔB = B_RF − B_τ. RF is
  > declared non-inferior in perception performance only if the lower bound of the paired 95% CI for ΔF
  > is greater than −0.005. RF is declared communication-superior only if the upper bound of the paired
  > 95% CI for ΔB is below zero, with a point-estimate payload reduction of at least 10%. The primary
  > comparison is the test split at Bmax = 0.20; Bmax = 0.10/0.30 and all Culver-City comparisons are
  > secondary. Confidence intervals are calculated from the 200 paired replay-level differences under
  > identical channel draws.

  Precision clauses:
  - **(a) CI method:** paired bootstrap over the 200 replay-level differences, 10,000 resamples,
    percentile interval.
  - **(b) 10% definition:** `(B_τ − B_RF) / B_τ ≥ 0.10` (point estimate).
  - **(c) Sign-off:** δ = 0.005 proposed 2026-08-09; justification = engineering tolerance (≤0.5 pp
    overall F1 loss given substantive communication reduction); confirmed and fixed by Peiyi Yue on
    2026-08-09, prior to any test/Culver-City evaluation; subsequent supervisor review will not change
    the margin after evaluation begins.
  - **P2-B requirement:** P2-B must persist the 200 replay-level difference series (ΔF, ΔB) per budget
    and split as CSV artifacts — the CI computation must be reproducible from repository contents alone.
- **R10 (2026-08-09, post-unblinding diagnostic) — E-usage diagnosis after the sec-8 fuse.**
  **This is a post-unblinding diagnostic; nothing computed here is confirmatory.** No training, no
  model/δ/τ change, no replay re-run. It only swaps the reference oracle: per budget it recomputes a
  **frozen-λ clairvoyant oracle** (renamed from "budget-specific oracle"; R10d note: it is NOT
  budget-constrained) `s*_b = argmax_s (F_s − λ_b·B_s)` at that budget's frozen λ\*
  (B010→0.05, B020→0.02, B030→0), masking F where BLER_F ≥ 0.999. Each frozen-λ-clairvoyant E cell is
  classified (R10 taxonomy, **later corrected in R10d**), and the cost of the RF selector NOT picking E
  is split into an F1 loss and an extra payload.
  The per-class table and the sec-8 selector-E check are re-adjudicated against the frozen-λ clairvoyant
  oracle (B030 unchanged at λ=0; B010/B020 recomputed). **Root-cause correction:** B010/B020's `cw=balanced`
  candidates were attempted and walked past for exceeding the frozen budget; **B030's `cw=balanced` was
  never tested** — its `cw=None` winner (cand#56) passed at walk rank 0, so the walk stopped first.
  Any decision rule proposed from this diagnostic is explicitly post-unblinding and takes effect only
  after Peiyi Yue + supervisor confirmation.
- **R10-corrigendum (2026-08-09) — RETRACTS the R10 conclusion "the E-collapse costs payload, not F1".**
  That conclusion was WRONG: R10's taxonomy required `eff_E > eff_F` for strict-benefit, but on
  Rayleigh (and any BLER_F ≥ 0.999 cell) F is infeasible and `eff_F = ego = eff_E`, so genuine
  strict-benefit E cells (E beats the only feasible alternative L) failed that test and were mis-bucketed
  as "lambda-induced" (claimed to cost no F1). The git history of commit 0e7446b is **not rewritten**;
  this entry governs. The corrected diagnostic (`decision_log.py`) recomputes on the **feasible**
  utility (F masked to −∞ where BLER_F ≥ 0.999), separates the **raw** oracle (no penalty) from the
  **budget** oracle (λ penalty), and uses three mutually-exclusive raw-feasible classes with an explicit
  error on any residual: **strict** (E is the unique feasible argmax), **tie** (E is a feasible argmax,
  tied), **cost-induced** (E is not raw-optimal but wins only under the λ penalty). Every missed-E cell
  (all three classes) is charged `ΔF1 = F1_E − F1_{RF's actual action}` **and** a Δpayload. Hard
  assertions (fail = fuse): at λ=0 the cost-induced count is 0; every cost-induced row has raw
  ΔF1(E vs L) ≤ 0; and the recomputed per-realisation F1_RF/B_RF reproduce the existing replay CSVs
  (a determinism/integrity check of the original P2-B run, which **passed**). **Corrected finding:** the
  strict-benefit missed-E F1 cost is **substantive on test** and negligible on Culver — i.e. the
  E-collapse **does** cost F1; the earlier "payload not F1" reading is void. (R10c's class definitions
  are themselves superseded by **R10d** below, which fixes the taxonomy to the supervisor's pseudocode;
  use the R10d numbers.) The vs-oracle account and the R9 vs-τ account are reported in **separate**
  tables.
- **R10d (2026-08-09) — classification fixed to the supervisor pseudocode (TOL = 1e-9, pre-registered),
  reference renamed, record hygiene.** Retraction chain: **R10 → R10c → R10d**. Taxonomy of the
  frozen-λ-clairvoyant E cells, on the **raw feasible** utility (`raw_max` = max feasible action
  utility; F = −∞ where BLER_F ≥ 0.999): **strict** = `isE & (eff_E > feas_L + TOL) & (eff_E > feas_F +
  TOL)`; **tie** = `isE & (|eff_E − raw_max| ≤ TOL) & ~strict`; **cost_induced** = `isE & (eff_E <
  raw_max − TOL)`. Every missed-E cell (all classes) is charged both `ΔF1 = eff_E − F1_{RF action}` and
  a Δpayload; **"strict-benefit missed-E cost" and "total E-collapse F1 cost" are two different numbers
  and must not be conflated** (CLAIMS rule). Four hard assertions (fail = fuse, all **passed**):
  (a) `ΔF1[strict & missed] ≥ −TOL` (on the mask-consistent utility: a masked-infeasible F selected by
  RF delivers ego, matching the oracle mask, so the BLER=0.999 boundary does not spuriously beat E);
  (b) `strict ∪ tie ∪ cost_induced == isE` (mutually exclusive + complete, zero residual);
  (c) λ = 0 ⇒ `cost_induced` count 0; (d) each `cost_induced` row has `eff_E − raw_max ≤ 0`. The
  reference oracle is renamed **"budget oracle" → "frozen-λ clairvoyant oracle"** and, at its
  definition, is flagged **NOT budget-constrained**: on test/Culver its mean payload can exceed B_max
  (test B010 0.112, Culver B010 0.155, Culver B020 0.223) — it is a post-hoc reference only; a true
  budget-constrained oracle is not built this round. **Report numbers are regenerated from the CSV by
  `report.py` (no hand-written numbers → `R10_REPORT.md` + `PROVENANCE_r10c.txt`).**
  `cost-induced` is **non-empty for λ>0** (test B010 4809 / B020 2121 cells; the λ=0 budget B030 = 0)
  and its F1 cost (small **positive**) is included in the TOTAL. **Two different numbers (do not
  conflate), test three budgets:** strict-benefit missed-E F1 cost /frame = 0.002658 / 0.002658 /
  0.002705; total E-collapse F1 cost /frame = 0.003021 / 0.002888 / 0.003030 (≈0.53·δ at B020); both
  negligible on Culver (≈0.00003). Record hygiene (single-version, no `retracted_r10/`): the flawed
  `r10_diagnostic.py` + its `r10_*.csv` are removed via the reference gate; `anomaly_check.py` no
  longer prints the retracted conclusion and `anomaly_report.txt` is regenerated in place. 6d AP and
  P2-C/D stay frozen pending review.
- **R11 (2026-08-09, post-unblinding route decision) — E-collapse resolution + unfreeze.** Resolves the
  route question left open by R10d. The normative decision text (verbatim):

  > Route C adopted: frozen models retained; E-collapse reported as a quantified limitation
  > (strict-benefit 0.00266/frame ≈0.53δ, all-class ≈0.6δ on test; negligible on Culver-City) with the
  > E-scarcity fix pre-registered as future work requiring a new independent dataset. Decided by Peiyi
  > Yue, 2026-08-09, based on the corrected R10d accounting; supervisor review deferred to the milestone
  > (P6-gates-green draft); reversible until submission.

  Consequences (no training / model / δ / τ / replay change): the three frozen selectors and
  `FROZEN_MANIFEST.json` stand unchanged; the quantified limitation is sourced only from the R10d
  numbers regenerated by `report.py` from `r10c_missed_e_cost.csv`. This entry **unfreezes**
  6d (true end-to-end AP — descriptive only, no confirmatory language; the R9 decision was made once and
  is not revisited) and P2-C/D (latency remeasure, CLAIMS backfill, freeze summary). The E-scarcity fix
  itself (e.g. `cw=balanced` under a revised budget rule, or E re-weighting) remains **future work** and
  would require its own new Change-log entry plus an independent dataset before any retrain.
- **P3 (2026-08-10, pre-registered before running) — descriptive sensitivity batch.** No change to the
  frozen selectors, δ, τ\*, the oracle definition, or the mainline replay; `main.tex` untouched. Every
  item is a **descriptive** re-weighting/replay of the cached per-(frame, SNR, channel) grid
  (`data/p2/p2_grid_{split}.csv`: `eff_E/eff_L/eff_F/bler_F/oracle_ELF`) with the frozen `predict()`; no
  new detection inference. The §8 anti-forcing clause applies verbatim: the expected behaviours below
  are **checks, not targets** — a miss is reported, never fixed by touching data. All params are frozen
  here before any run.
  - **(1) Channel-ratio sensitivity.** AWGN:Rayleigh ∈ {25/75, 50/50, 75/25}, i.e. weight the grid's
    channel marginal at `p_rayleigh ∈ {0.75, 0.50, 0.25}` (SNR uniform over the 11-point grid). 3 split
    × 3 budget F1/payload. *Expected:* more Rayleigh → lower feature-selection rate → payload ↓ toward
    B_L and F1 → the Fixed-L floor (feature infeasible under Rayleigh).
  - **(2) Non-uniform SNR (2 forms, params frozen).** Re-weight the SNR marginal (channel 50/50) by two
    hard-coded densities discretised onto the grid points {0,2,…,20} dB (each point gets its ±1 dB bin
    mass, renormalised): **(2a) low-skew** `Beta(2,5)` scaled to [0,20] (mean ≈ 5.71 dB, a poor-channel
    regime); **(2b) truncated Gaussian** `N(μ=10, σ=5)` truncated to [0,20] (mid-centred). *Expected:*
    (2a) shifts toward L (payload ↓, F1 → Fixed-L); (2b) intermediate.
  - **(3) Channel-type misclassification + 2 labelled variants.** The selector's `channel_is_rayleigh`
    feature is flipped with probability `p ∈ {0, 0.05, 0.10, 0.20}` (eval-time; the **true** channel used
    for BLER is unchanged), scored analytically as `(1−p)·eff[rf_true] + p·eff[rf_flipped]` per cell,
    frozen model, same-seed system. *Expected:* graceful F1 degradation with p; the fallback keeps L safe
    under flips. **Two labelled comparison variants (validate-only, `labeled variant, not deployed`;
    they do NOT touch `FROZEN_MANIFEST.json`):** **(3a) SNR-only** — a selector trained on validate over
    `{est_snr_db}` alone; **(3b) continuous-observation** — the binary `channel_is_rayleigh` replaced by
    two continuous observables from a frozen deterministic map: `delay_spread_ns = {awgn:30, rayleigh:300}`,
    `doppler_hz = {awgn:20, rayleigh:600}` (a monotone re-encoding of the channel type; no new physics).
    Both use the same RF candidate family as the deployed selector, are evaluated on validate only, and
    are reported strictly as comparisons.
  - **(4) BLER_L grid.** `BLER_L ∈ {0, 0.01, 0.05, 0.10}` (mainline stays `BLER_L = 0`). Eval-time only:
    the realised L utility becomes `eff_L' = eff_L·(1−BLER_L) + eff_E·BLER_L`; the frozen selector's
    actions and the oracle definition are **unchanged** (BLER_L is not a selector input). *Expected:*
    small monotone F1 drop where L is selected; payload unchanged.
  - **(5) Rician regeneration.** `K ∈ {0, 3, 10}` (K=0 ≡ Rayleigh, K→∞ → AWGN) via the existing Sionna
    pipeline (`projects/ca_tosg/communication/ldpc_qam.py`, extended with a Rician block-fading branch: per-
    codeword `|h|²` non-central with the same rate-1/2 5G-LDPC, 16/256-QAM, `N_CW=3960`, adaptive MC).
    The frozen selector is fed `channel_is_rayleigh = 1` (Rician is a fading channel; K changes only the
    true BLER); descriptive replay recomputes `eff_F` under the Rician frame-BLER. *Expected:* larger K →
    the feature branch becomes feasible at lower SNR → feature-selection rate ↑ toward the AWGN case.
- **P3-C (2026-08-11, pre-registered before running) — Rician bracketing variant.** Same frozen selector,
  same 200-realisation replay system and seed as item 5, `main.tex` untouched; the ONLY change is the
  selector is fed `channel_is_rayleigh = 0` (all other features unchanged), so it treats the Rician link
  as AWGN-like and *is willing to request F* on SNR/cue grounds; delivery success/failure is then
  adjudicated by the TRUE Rician frame-BLER (the existing `K ∈ {0,3,10}` table). This is the
  **opportunistic bound**; item 5 (`channel_is_rayleigh = 1`, always-defer) is the **conservative bound**.
  *Expected (checks, not targets; §8 anti-forcing):* **(a) K=10** — above the ~16 dB onset, requested F
  is delivered → ρ_F and the hard-frame gain partially recover; **(b) K=0/3** — below onset the requested
  F fails and falls back to ego → wasted payload, and an F1 loss relative to L on L-dominant frames;
  **(c)** the `rayleigh=1` and `rayleigh=0` results together **bracket** the potential gain of a
  K-aware selector. Output: same columns as item 5 (F1 / payload / ρ_F) resolved by K × SNR, labelled
  **"bracketing variant, not deployed behavior"**. No change to the frozen models / oracle / δ / τ\*.
- **P4-A (2026-08-11, pre-registered before training) — match-adaptive external RL baseline.** An
  **external comparison baseline** trained to the SAME matched protocol as the deployed RF selector, to
  answer "does a learned RL policy beat the imitation-trained RF / the τ rule?". It does **not** touch
  the deployed CA-TOSG models, `FROZEN_MANIFEST.json`, δ, τ\*, or the mainline replay; `main.tex` is
  untouched. Its params come from the machine-parseable `CATOSG-P4A` block below, which
  `baselines/contextual_bandit/train.py` **parses** (no values hard-coded elsewhere; IRON RULE — any
  change to the block after training needs a new Change-log entry + full retrain).
  - **(a) Problem form (stated honestly).** Each frame's granularity choice is an **independent**
    decision, so this is a **contextual bandit** (a single-step decision from context to action with an
    immediate reward), **not** sequential RL — there is no state transition, discounting, or credit
    assignment across frames. The algorithm is fixed to **DQN-style single-step Q(s,a) + ε-greedy**
    (target = the immediate reward, no bootstrap); network, steps, lr, ε schedule, and seed are frozen
    in the block. State = the 23 deployed features (z-scored on the validate grid); actions {E,L,F};
    reward `r(s,a) = eff_a − λ·B_a` (the same Lagrangian-relaxed constrained objective as §6).
  - **(b) Matched-protocol checklist (each binding).** Same validate grid + scene split (§2); same
    cached per-frame `eff` (`data/p2/p2_grid_*.csv`; **zero new perception inference**); same three
    `B_max ∈ {0.10,0.20,0.30}`; same **frame-weighted** budget aggregation; same **frozen-walk** hard
    check `B̄_frozen ≤ B_max` (strict, temp-then-atomic-swap); same **one set of 200 paired CSI
    samplings** replay (`CSI_SEED`, identical draws to the RF/τ replay); same metric definitions.
    Selection/tuning happens **only on validate**, by the same **scene-level 9-fold LOSO** (each scene
    held out once); the walk orders λ by frame-weighted OOF F1 descending and freezes the first λ whose
    full-validate `B̄_frozen ≤ B_max`.
  - **(c) Evaluation = descriptive + paired CI only.** Report RL-vs-RF and RL-vs-τ as paired bootstrap
    CIs over the 200 replay-level differences (same machinery as R9's CI), **with no new decision** —
    the confirmatory primary was spent once at R9 and is **not** re-created here. Freeze three models →
    `results/manifests/P4A_MANIFEST.json` (3 sha256 / hyperparams / seed / per-budget frozen payload check);
    results + PROVENANCE under `results/baselines/contextual_bandit_runs/`, all labelled **"external baseline, not deployed"**.

```json CATOSG-P4A
{
  "problem_form": "contextual_bandit_single_step",
  "algorithm": "dqn_bandit_single_step_epsilon_greedy",
  "seed": 0,
  "network": {"hidden": [64, 64], "activation": "relu"},
  "train": {"steps": 4000, "batch": 512, "lr": 0.001, "optimizer": "adam",
            "epsilon_start": 1.0, "epsilon_end": 0.05, "epsilon_decay_steps": 3000, "target_is_immediate_reward": true},
  "reward": "eff_a - lambda*B_a",
  "feature_standardisation": "zscore_on_validate_grid",
  "lambda_grid": [0.0, 0.02, 0.05, 0.1, 0.2, 0.35, 0.5],
  "budgets": [0.10, 0.20, 0.30],
  "loso": {"scheme": "scene-level", "folds": 9, "each_scene_heldout_once": true},
  "aggregation": {"performance": "frame_weighted_oof_f1", "feasibility": "frame_weighted_oof_payload"},
  "selection": "frozen_walk",
  "tie_break": ["max_f1", "min_payload", "min_lambda_index"],
  "eval": "descriptive_paired_ci_only"
}
```
- **P4-B (2026-08-11, PLAN pre-registered; inference NOT yet run — awaiting Peiyi's verification).**
  Second-backbone (SECOND / VoxelNet intermediate fusion) generality arm. The **cache protocol is the
  mainline method** (clean per-frame eff cache → grid expansion → frozen-walk evaluation), applied to a
  second detector backbone so the CA-TOSG selector's generality is tested off the PointPillar features.
  Nothing here changes the deployed CA-TOSG models / δ / τ\* / oracle / mainline replay; `main.tex`
  untouched. **This entry pre-registers the PLAN only; no inference runs until the plan is verified.**
  - **(1) Checkpoint + inference config.** Backbone config `opencood/hypes_yaml/second_intermediate_fusion.yaml`
    (SECOND: MeanVFE → VoxelBackBone8x (8× down) → HeightCompression(256) → AttBEVBackbone → heads; voxel
    0.1 m, range 281.6×80×4 m, feature_stride 8). The checkpoint is **NOT on disk** (296 local `.pth` are
    all the PointPillar family) → step-1 downloads it and records its **sha256** before any use (cannot be
    hashed now). Three per-frame inference passes, mirroring the mainline caches: **late** (`second_late_
    fusion.yaml`), **intermediate / compressed-F** (`second_intermediate_fusion.yaml`, the F branch), and
    **ego** (single-CAV pass). Frames per split (OPV2V, same as mainline): validate 1980 / test 2170 /
    Culver 550 = 4700 frames × 3 passes = **14,100 forward passes**. GPU-time estimate (RTX 5070,
    sparse-voxel SECOND ≈ a few Hz/frame): **~1.5–3 h total** (to be refined by a 20-frame micro-timing at
    execution). Output: `ego/late/comp_{split}.npz` under a **new** dir (e.g. `gs_rerun_second/`), never
    overwriting the PointPillar caches.
  - **(2) Payload derivation B_F^SECOND — from THIS backbone's own tensor, first-principles, NO borrowed
    numbers.** The transmitted intermediate feature = the HeightCompression BEV tensor fused inside
    AttBEVBackbone: **C × H × W** with C = 256, H = round(80/0.1)/8 = 100, W = round(281.6/0.1)/8 = 352 →
    **≈ 9.01 M elements** (config-derived; the **exact** C×H×W is confirmed by a dummy forward of the
    architecture — no ckpt needed — at execution). Coding chain identical to the mainline transport
    (rate-1/2 LDPC + QAM): `B_F^SECOND [Msym] = elements × bits_per_element / 0.5 / bits_per_QAM_symbol`.
    **OPEN DECISION for Peiyi (materially changes B_F^SECOND; not fixed here, no coincidence alignment to
    the PointPillar 1.98 Mbit / 0.99 Msym):** `bits_per_element` — SECOND has **no learned feature codec**
    in its graph, so the F message is a **quantised raw BEV tensor**; candidate quantisations to pre-fix:
    (i) INT8 = 8 b/elem, (ii) FP16 = 16 b/elem. Under 16-QAM (4 b/sym), INT8 → ≈ 9.01e6·8/0.5/4 = **36.0
    Msym**; FP16 → **72.1 Msym** (illustrative, pending the exact element count + the chosen bit-depth).
    A new `payload_audit` extension will re-derive this from the config dims + chosen bit-depth and bit-
    compare (no literal hard-coded), added at execution — **not** referencing any existing payload number.
  - **(3) Cache protocol = mainline (settled).** clean per-frame eff cache (ego/late/compressed F1 vs the
    canonical union GT, same scorer) → grid expansion (frame × 11 SNR × 2 channel, same BLER table) →
    frozen-walk selector evaluation, all reusing the existing pipeline scripts pointed at the SECOND
    caches. **Greenlight gate:** inference + the payload_audit extension run **only after** Peiyi verifies
    this plan (the ckpt source/sha, the transmitted-feature layer, and the `bits_per_element` decision).

**Diagnostic note (Change-log R6/R7).** The gap between a candidate's OOF payload and its full-retrain
(frozen) payload is a **training→freeze diagnostic** of the selection procedure. It must **not** be
written into the paper's conclusions; the paper reports only the frozen selectors' evaluated numbers.

- **LAYOUT (2026-08-12) — repository restructured to the BEVFormer-style layout; NO experimental
  content changed.** `paper1/` is dissolved into the root layout of `RESTRUCTURE_PLAN.md`
  (`docs/ figs/ projects/ tools/ baselines/ results/ tests/ paper/`), per `RESTRUCTURE_MAP.csv`.
  This file is `PROTOCOL.md` moved; it remains the single normative source, and `configs/*.yaml` are
  now generated FROM it into `projects/ca_tosg/configs/` by `projects/ca_tosg/utils/configs.py` and byte-compared by
  `tests/test_manifest.py` — a config can never become a second source.
  **Manifest migration (the only edit to a frozen product).** Manifest-internal paths are, and were,
  relative to the tree root; the tree root moved up one level, so six strings in
  `FROZEN_MANIFEST.json` were relabelled:
  `../../OpenCOOD/…` → `../OpenCOOD/…`, `results/bler_sionna/…` → `results/channel/…`, and the
  folds/walk files → `results/manifests/…`; plus the `protocol` label, to match what
  `models/selector.py` now writes. **No hash, timestamp, or selection field was touched**, and all
  7 recorded md5/sha256 were re-verified against the files at their new locations before the write
  (`docs/restructure/migrate_manifests.py`). `P4A_MANIFEST.json` needed no path change.
  The manifest's mtime was restored from its own `freeze_timestamp` after the rewrite, because §10's
  post-freeze check (4) then still compared grid mtime against manifest mtime and a pure relabel must
  not be able to manufacture an ordering violation. **That limitation is now eliminated, not merely
  recorded** (LAYOUT-2 below): check (4) no longer reads mtime at all.
  Gates after the migration: all five green + the new configs/manifest gate
  (`python tools/verify_results.py`).

- **LAYOUT-2 (2026-08-12) — §10 post-freeze check (4) re-anchored from filesystem mtime to recorded
  content; `configs/` moved to its planned location.** Three changes, no experimental content touched.
  1. **The ordering anchor.** Check (4) proved "the test/Culver grid was built after the freeze" by
     comparing `os.path.getmtime(grid)` with `os.path.getmtime(FROZEN_MANIFEST.json)`. Git does not
     carry mtime, so in a fresh clone that comparison could only pass or fail by accident of checkout
     order — and any rewrite of the manifest, however cosmetic, faked a violation. It now reads two
     fields the grid's own provenance records: `frozen_manifest_freeze_timestamp` (which must equal
     the manifest's current `freeze_timestamp`) and `grid_build_timestamp` (which must be later than
     it), and it ties those stamps to the artifact by re-checking the grid md5 the provenance
     recorded. A missing provenance, a missing field, or a provenance describing a different grid is
     a FAIL, never a skip. `grid_builder.py` stamps both fields at build time from now on; the three
     existing provenance files were migrated on 2026-08-12, each stamped value labelled with where it
     came from (the artifact's mtime in the working tree that produced it).
  2. **`configs/` → `projects/ca_tosg/configs/`**, the position RESTRUCTURE_PLAN.md specifies.
  3. **The configs↔protocol assertion is now explicit and per-block.** `tests/test_manifest.py`
     recomputes the md5 of each protocol block a config claims to derive from — CATOSG-CANDIDATES,
     §3 Channel grid, §4 Action set, Appendix B — and names the block that drifted, in addition to
     the byte-comparison of the regenerated files. A config pinning no protocol md5, or one this
     repository does not generate, fails as an ungoverned second source. **This file remains the
     single normative source; `projects/ca_tosg/configs/*.yaml` are a view of it and nothing else.**

## Appendix A — P2 freeze summary (P2-D)

Snapshot of the frozen P2 state at R11. The authoritative source for every value is
`results/manifests/FROZEN_MANIFEST.json` (schema `catosg-frozen-manifest/1`, freeze
`2026-08-09T15:12:53Z`, seed 0; env python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2.2.2);
the numbers below are copied from it and from the committed result CSVs — not hand-derived.

**Frozen selectors (one per budget, §5/§6; sha256 in the manifest).** Selection = frozen walk over the
112-candidate block (`candidate_block_md5 05d8e424`), 9-scene LOSO (1008 fold rows), 23 features.

| B_max | model | cand# | cw | λ\* | walk depth | frozen validate payload | LOSO frame-weighted F1 | τ\* |
|---|---|---|---|---|---|---|---|---|
| 0.10 | `data/p2/selector_B010.pkl` | 58 | None | 0.05 | 6 | 0.067887 | 0.9070 | 18.0 |
| 0.20 | `data/p2/selector_B020.pkl` | 1 | None | 0.02 | 2 | 0.099231 | 0.9087 | 12.0 |
| 0.30 | `data/p2/selector_B030.pkl` | 56 | None | 0.00 | 0 | 0.156962 | 0.9094 | 8.0 |

All three `cw=None` (the top-OOF-F1 `cw=balanced` candidates were walked past for exceeding the frozen
budget — the root cause of the E-collapse, Change-log R10/R11).

**Resident gates (all must pass on the committed tree).** `tests/test_payload.py` (17/17 links);
`tests/test_paragraph_insert.py 1 2 3` (3/3); `tests/test_result_consistency.py --check` (CLAIMS ≡ main.tex);
block-exit grep over `tests/stale_fingerprints.md` (0 hits); `tests/test_data_leakage.py`
(LOSO fold-structure + 15 frozen-state manifest checks + freeze-aware test/Culver + scene anchor).

**P2 deployment deliverables (all in `results/main/` unless noted).**
- **R9 decision (P2-B, confirmatory, decided once).** `deployment.py` → `replay_{split}_B0XX.csv`
  (200 paired replay-level ΔF/ΔB, CI reproducible), `replay_summary.csv`, `r9_decision.csv`. Locked
  result wording: `r9_result_claims.md` (PRIMARY test@B020: non-inferior in F1 within δ=0.005 AND
  communication-superior, payload −56.3%; secondary = CI only). That file is the authority for the
  sentence wording when it lands in main.tex at P5.
- **6d true end-to-end AP (descriptive, Change-log R11).** `end_to_end_ap.py` → `true_e2e_ap.csv`
  (split × budget × policy, global-sort AP@.3/.5/.7) + `PROVENANCE_ap.txt`. Descriptive only; the R9
  decision is not revisited.
- **R10 E-collapse account (post-unblinding diagnostic).** `decision_log.py` → `r10c_*.csv`;
  `report.py` → `R10_REPORT.md` + `PROVENANCE_r10c.txt`. Two-number rule (do not conflate):
  strict-benefit missed-E F1 cost /frame (test) 0.002658 / 0.002658 / 0.002705; total E-collapse F1
  cost /frame (test) 0.003021 / 0.002888 / 0.003030; both ≈0 on Culver. vs-clairvoyant account is
  separate from the R9 vs-τ account.
- **P2-C latency (frozen selectors).** `projects/ca_tosg/evaluation/latency.py` → `results/latency/`
  `selector_latency.csv` (batch-1, WARMUP=100, 1000 trials: ≈59.7–59.9 ms mean, P95 ≈66–69 ms on this
  host) + `system_timing.csv` (per-stage measured/calculated/assumed/not-included tags).

**Route (Change-log R11).** Route C: frozen models retained; the E-collapse is reported as a quantified
limitation; the E-scarcity fix is future work needing a new independent dataset.

**Open P5 items (require a main.tex edit; main.tex is frozen through P2, so deferred).**
- main.tex still carries the **legacy-pipeline** numbers (`tab:headline_agg` from
  `results/main/threshold_vs_rf.csv` via `policy_200seed.py`; true-e2e-AP figures from
  `results/true_e2e_global_*.csv` via `true_e2e_global.py`). The P2 artifacts above **supersede** these
  at P5; until the prose is migrated, those legacy generators remain the provenance-of-record and are
  **not** removable.
- Latency sentence (main.tex §5.x, `52.8 ± 5.7` ms / P95 `59.1` ms, 2,000 trials) was measured on the
  **retired v2** selector; the P2-frozen remeasure is ≈59.9 ms / P95 ≈67 ms (`selector_latency.csv`).
  Update at P5.
- The R9 / R10 / E-limitation sentences are **not yet in main.tex**; their CLAIMS rows will be created
  by `test_result_consistency.py` only once the prose lands (P5), at which point the *Allowed wording* columns
  point to `r9_result_claims.md` / `R10_REPORT.md`.

## Appendix B — P3 sensitivity expected behaviours (checks, not targets)

Operationalises the §8 anti-forcing clause for the P3 batch (Change-log P3). Each row is a
**falsifiable prediction**; the *Observed* column is descriptive, read from the committed CSVs in
`results/sensitivity/` (baseline reproduces `replay_summary.csv` exactly, `baseline_sanity.csv`);
a miss is **reported, not fixed**. Anchor numbers below are test @ B_max=0.20, RF.

| Item | Condition | Pre-registered expectation | Observed (descriptive) | Check |
|---|---|---|---|---|
| 1 | channel ratio (`channel_ratio.csv`) | more Rayleigh → feature-selection rate + payload ↓ toward B_L, F1 → Fixed-L | ρ_F 0.110→0.073→0.037 and payload 0.131→0.095→0.060 as AWGN:Rayleigh goes 75/25→50/50→25/75; F1 0.9064→0.9046→0.9029 | met |
| 2 | non-uniform SNR (`nonuniform_snr.csv`) | low-skew shifts toward L (payload↓, F1→Fixed-L); trunc-Gaussian intermediate | Beta(2,5): ρ_F 0.021, payload 0.044, F1 0.9021 (sharp drop); N(10,5): ρ_F 0.078, payload 0.099, F1 0.9048 (≈uniform) | met |
| 3 | channel-type flip (`channel_misclassification.csv`) | graceful F1 degradation with p; fallback keeps L safe | F1 0.9046→0.9040→0.9035→0.9023 for p=0/.05/.10/.20; payload ~flat (0.0947) | met |
| 3-var | labelled variants (`item3_variants.csv`, validate-only, NOT deployed) | cues + a channel signal needed; a monotone re-encoding ≈ binary | snr_only collapses to L (ρ_F=0, payload 0.024); cont_obs (delay/Doppler map) ≈ full_ref (F1 0.9122 vs 0.9122) | met |
| 4 | BLER_L grid (`object_message_bler.csv`) | small monotone F1 drop where L selected; payload unchanged | F1 0.9046→0.9039→0.9009→0.8971 for BLER_L=0/.01/.05/.10; payload 0.0947 flat | met |
| 5 | Rician K (`rician_proxy.csv`, table `bler_sionna_rician.csv`) | larger K → feature branch feasible at lower SNR → feature-selection rate ↑ | **PHYSICAL LAYER, as expected:** 16-QAM frame-BLER<0.999 onset K=0 none / K=3 ≈27.5 dB / K=10 ≈16 dB (only K=10 opens inside [0,20]). **SELECTOR, expectation NOT met (reported, not fixed):** fed `channel_is_rayleigh=1` per the pre-registration, the frozen selector defaults to L for every K (ρ_F=0, payload=B_L, F1 flat at the Fixed-L floor) — the binary channel feature cannot represent Rician K, so the K=10 feasibility is left unexploited. A limitation of the frozen binary-channel selector, not a selector success. | **partial: physics met, selector limitation surfaced** |

### Appendix B.1 — Rician two-bound bracket (Change-log P3-C)

Item 5 fed the frozen selector `channel_is_rayleigh=1` (always-defer → **conservative** bound); P3-C
feeds `channel_is_rayleigh=0` (willing to request F → **opportunistic** bound), with delivery adjudicated
by the TRUE Rician frame-BLER. Both are **"bracketing variant, not deployed behavior"**; sources
`rician_proxy.csv` (rayleigh=1) and `item5c_rician_rayleigh0.csv` / `item5c_rician_by_snr.csv`
(rayleigh=0). Anchors: test @ B_max=0.20, RF.

| Bound | feed | K | F1 | payload | ρ_F | reading |
|---|---|---|---|---|---|---|
| conservative | rayleigh=1 | 0 / 3 / 10 | 0.9011 (flat) | 0.024 (=B_L) | 0.000 | never requests F; K=10 feasibility unused |
| opportunistic | rayleigh=0 | 0 | 0.8850 | 0.166 | 0.147 | F requested (from ~10 dB) but always fails (BLER_F=1) → ego fallback → **wasted payload + F1 loss** |
| opportunistic | rayleigh=0 | 3 | 0.8850 | 0.166 | 0.147 | same as K=0 (onset ≈27.5 dB is outside [0,20]) |
| opportunistic | rayleigh=0 | 10 | 0.8878 | 0.166 | 0.147 | slightly higher than K=0/3: above the ~16 dB onset F is delivered |

Per-SNR onset (rayleigh=0, K=10, `item5c_rician_by_snr.csv`): as SNR crosses the onset the true
frame-BLER falls (16 dB→0.958, 18 dB→0.707, 20 dB→0.353) and realised F1 climbs back (0.873→0.884→0.899)
while below 16 dB the requested F fails (F1 flat ≈0.871, payload ≈0.285 wasted). For K=0/3 the frame-BLER
is 1 across [0,20], so every request above ~10 dB is wasted.

**Checks (§8 anti-forcing).** (a) **met** — K=10 above onset: F delivered, F1 recovers toward 0.90 at
high SNR. (b) **met** — K=0/3 below onset: failed F → ego fallback → wasted payload (0.166 vs 0.024) and
F1 loss (0.885 < the conservative 0.901). (c) **met** — the two feeds bracket the potential of a K-aware
selector: neither blind extreme wins, because the opportunistic feed pays for F across the whole SNR
range while only the K=10 high-SNR slice returns it; the value of a genuine K-aware policy (request F
only above the K-dependent onset) lies **between** these bounds.

## Appendix C — P4-A external RL baseline (Change-log P4-A)

**"external baseline, not deployed."** A contextual-bandit RL selector (`train.py`,
`evaluate.py`) trained to the matched protocol, compared to the deployed RF and the τ rule.
Frozen CA-TOSG models / δ / τ\* / oracle / mainline replay unchanged; `main.tex` untouched. Manifest
`results/manifests/P4A_MANIFEST.json` (3 bandit sha256 / hyperparams / seed / per-budget frozen payload).
Sanity: the eval's `F1_RF` / `B_RF` reproduce `replay_summary.csv` exactly (0 mismatches).

**Selection outcome (validate LOSO, `p4a_loso_oof.csv` / `p4a_walk.csv`).** Ordered by frame-weighted
OOF F1, the best λ is **λ\*=0.2** (OOF F1 0.9055, payload 0.0245) — feasible for all three budgets, so the
walk freezes it at depth 0 for **every** B_max. The bandit therefore converges to a **conservative
near-object-level policy** (payload ≈ B_L ≈ 0.024) at all budgets: lower-λ models that request more F
have HIGHER in-sample F1 (λ=0 full-grid 0.9114) but LOWER held-out F1 (λ=0 OOF 0.9027; λ=0.05 collapses
to 0.872) — reward-based F-selection **overfits** the F-vs-L boundary, so the model-selected policy
plays L safe. (The three per-budget model files carry different sha256 — same policy, re-trained per
budget; GPU training is not bit-reproducible, a recorded limitation for this external baseline; the
frozen F1/payload are identical.)

**Comparison (descriptive, paired bootstrap CI only — NO new decision; `contextual_bandit.csv`).** Anchors
test @ B_max=0.20: RL F1 0.8974 / payload 0.0216; RF 0.9046 / 0.0947; τ 0.9074 / 0.2168.
- RL-vs-RF: ΔF CI [−0.0073, −0.0071] (RL F1 **below** RF, CI entirely < 0) at ΔB CI [−0.0738, −0.0725]
  (RL much lower payload). Range over splits/budgets: ΔF from −0.004 (validate B010) to −0.026 (Culver B030).
- RL-vs-τ: ΔF CI [−0.0101, −0.0099] (RL **below** τ) at ΔB CI [−0.196, −0.194] (RL far lower payload).

**Expected behaviour (§8 anti-forcing — check, not target).** Pre-registered expectation: RL and RF in
the same F1/payload neighbourhood. **Observed:** RL is in a similar F1 *band* on validate (0.907 vs 0.911)
but drifts further below on test/Culver, and sits at the **Fixed-L payload corner** rather than matching
the RF's operating points — i.e. it is **not** better than the RF; the RF's imitation of the exact
λ-oracle labels generalises the channel-aware F-selection better than reward RL here. Reported as-is: a
valuable **negative** comparison (a learned RL policy does not beat the interpretable imitation selector).

## Appendix D — KEEP-UNTIL-P5 register (Change-log LAYOUT)

Produced by the reference sweep of the 2026-08-12 restructure (`RESTRUCTURE_GATE_SWEEP.md`,
which keeps the delete list and the method). Every file below is kept although nothing a
live root reaches names it; each carries why it is alive and what would kill it. "P5" = paper 1
accepted / camera-ready and its result tree archived. A file whose death trigger has passed is
a candidate for the NEXT sweep, not a silent deletion.

89 files are named by nothing that a live root reaches, yet are kept. "P5" below = the state in
which paper 1 is accepted / camera-ready and its result tree is archived. A file whose 死期 has
passed is a delete candidate for the *next* sweep, not this one.

### D.1 Infrastructure — outside the sweep's remit `[tool-miss]`

| 文件 | 活因 | 死期 |
|---|---|---|
| `.gitignore` | build infrastructure; the matcher only follows content references | never (rewritten in commit 2) |
| `paper/refs.bib` | `main.tex` cites it as `\bibliography{refs}` — no extension, so the glob matcher cannot see it | 论文接收 |
| `env_setup/requirements_py310_safe.txt` → `requirements.txt` | the environment contract (`python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2.2.2`) that `FROZEN_MANIFEST.json` pins | never |
| `env_setup/requirements_no_torch_spconv.txt` | analysis-only install path (no torch/spconv) | 当 environment.yml 覆盖两条安装路径 |

### D.2 Figure assets — become README/paper assets in commit 4 `[tool-miss]`

| 文件 | 活因 | 死期 |
|---|---|---|
| `paper/figures/ca_tosg_method_overview.svg` → `figs/ca_tosg_overview.svg` | PLAN names it the overview **source**; the `.pdf` beside `main.tex` is its export | 论文接收 |
| `fig_ap50_{awgn,rayleigh}.svg` → `figs/results/` | SVG sources of the AP@0.5 panels | 论文接收 |
| `fig_{pareto_test,payload_awgn,channel_bler_frame}.png` → `figs/results/` | the README display assets (PLAN `figs/results/`) | 论文接收 |
| `results/bler_sionna/bler_old_vs_new.svg` → `results/channel/` | evidence for the old-vs-new BLER table ruling recorded in `docs/experiment_protocol.md` | 论文接收 |

### D.3 Ablation + verifier code — generates cited numbers, invoked by hand

活因 for all: each writes a CSV that `CLAIMS.md` / `main.tex` / `PARAGRAPH_DRAFTS.md` cites, but
none is wired into one of the 6 headline commands. 死期 for all: **论文接收**.

| 文件 | 活因 (produces) |
|---|---|
| `extra_experiments/_common.py` | shared loader for a1–a9 |
| `extra_experiments/a3_subsets.py` | `results/sensitivity/scene_subsets.csv` |
| `extra_experiments/a4_jscc_aware.py` | JSCC-aware arm of the two-regime analysis |
| `extra_experiments/a5_causality.py` | cue-causality check (appendix) |
| `extra_experiments/a6_l_reliability.py` | `results/sensitivity/l_channel_reliability.csv` |
| `extra_experiments/a9_hardening.py` | `results/sensitivity/multiseed_hardening.csv` |
| `extra_experiments/c_channels.py` | per-channel breakdown |
| `extra_experiments/robustness.py` | `results/sensitivity/ablation/robustness_{aging,staleness,csi_noise}.csv` |
| `code/verify_gamma_mechanism.py` | `results/sensitivity/gamma_mechanism.csv` |
| `code/verify_harm_stratum_structural.py` | `results/sensitivity/harm_stratum_structural.csv` |
| `code/verify_frontier_payload_invariance.py` | `results/sensitivity/frontier_payload_invariance.csv` |
| `code/step4_collab_harm.py` | `results/sensitivity/step4_collaboration_harm.csv` |
| `code/step4_oracle_action_dist.py` | `results/main/step4_oracle_action_dist.csv` |
| `code/gt_audit.py` | `results/sensitivity/gt_audit.csv`, `gt_object_stats.csv` |
| `code/canonical_rescore.py` | `results/sensitivity/canonical_rescore.csv` (canonical-union-GT ruler) |
| `code/true_e2e_ap_inference.py` | GPU-side true-e2e AP inference |
| `code/plot_oracle_action_dist.py` | oracle action-distribution figure |
| `code/paper_style.py` | IEEE figure style imported by every `plot_*` `[tool-miss: imported, not path-referenced]` |
| `p2_dataprep/train_p3_variants.py` | `results/sensitivity/item3_variants.csv` |
| `p2_dataprep/eval_p3c_rician_bracket.py` | `results/sensitivity/item5c_rician_*.csv` |
| `analysis_tools/plot_bler_compare.py`, `plot_paper_figures.py` | old/new BLER comparison + batch figure driver |
| `analysis_tools/ldpc_qam_physical_sanity_n1000_ebn0.py` | becomes `tests/test_channel.py` — **promoted to a gate in commit 2**, so its 死期 is never |

### D.4 Upstream data producers — the P2 cue source depends on them

死期 for all: **当 `dataset_{split}.csv` 被冻结并登记进 `docs/data_manifest.md` 之后** (they are the
only way to rebuild the cue CSVs the frozen manifest md5-pins).

| 文件 | 活因 |
|---|---|
| `code/test_split_pipeline/{01..05,extract_test_data,run_all}.py` | produces `OpenCOOD/peiyi_work/paper1/data/dataset_test.csv` — the cue source the P2 test grid is built from |
| `code/regen_preds_with_scores.py`, `code/run_ego_only.py` | DATA_MANIFEST-registered regen commands for `gs_rerun/{late,comp,ego}_*.npz` (~10 GPU-min/split) — **protected by the DATA_MANIFEST rule** |

### D.5 Baseline code — alive because the baselines are unfinished

| 文件 | 活因 | 死期 |
|---|---|---|
| `scomcp_reproduction/*` (10 files) → `baselines/scomcp/` | the SComCP reproduction has **not** yet produced a result table; `results/baselines/scomcp.csv` does not exist | 当 SComCP 行进 Table III 且结果表冻结 |
| `extra_experiments/jscc_perframe/{build_channel_codec_ap,jscc_selector_compare,plot_channel_codec_ap,score_jscc_perframe}.py` | per-frame JSCC scoring behind fig:two_regime + the JSCC selector edge | 论文接收 |
| `analysis_tools/{stage1_*,stage2_*,run_jscc_eval,inference_subset,run_separate_coding_sweep}.py` + 8 `*.sh` | the WCSP2023 ImportanceMapJSCC reproduction: the *only* record of how the learned checkpoints on `H:` were produced | 论文接收 (checkpoints 无法重建) |
| `analysis_tools/MAP_REPRODUCTION_CHANGELOG.md` | that reproduction's change log | 论文接收 |

### D.6 Result CSVs named only in prose

死期 for all: **论文接收后随 `results/` 归档**. 活因: each is the source of a number quoted in
`CLAIMS.md` / `PARAGRAPH_DRAFTS.md` / `main.tex`, but no *script* reads it back.

`canonical_rescore.csv`, `f1_ap_decoupling_culver.{csv,md}`, `gamma_mechanism.csv`,
`gt_audit.csv`, `gt_object_stats.csv`, `harm_stratum_structural.csv`,
`step4_collaboration_harm.csv`, `true_e2e_global_test.csv` `[tool-miss: named in
paper/figures/README.md]`, `jscc_selector_{awgn,rayleigh}.csv`,
`ablation/robustness_{aging,staleness}.csv`, `step4_PROVENANCE.txt`,
`canonical_gt_PROVENANCE.txt`, `bler_sionna/PROVENANCE_rician.txt`, `policy/STEP5_NOTES.md`,
`DATA_MANIFEST.md`, `INVARIANCE_NOTE.md`.

**Two true orphans** — no reference anywhere in the tree, kept because deleting *measured* data is
worse than carrying it: `results/ego_only_acceptance.csv`,
`results/jscc/channel_codec_ap_test.csv`. 死期: next sweep, if still unreferenced at P5.
