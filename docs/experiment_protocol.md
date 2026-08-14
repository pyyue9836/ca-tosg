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

## 5. Prespecified average communication budget B_max

- **B_max ∈ {0.10, 0.20, 0.30} Msym/frame** — the operating budgets swept for the constrained
  problem (§6).
- **One model per budget** (Change-log R5): a **separate** selector is frozen for each B_max —
  `selector_B010` / `selector_B020` / `selector_B030` — because λ\*(B_max) differs; the manifest
  records all three model hashes.
- **Intended derivation:** available channel-uses/s ÷ LiDAR frame rate (802.11bd parameters).
- **Status: NOT physically derived — frozen as *prespecified average communication budgets***
  (Change-log R3, term updated by WORDING-1; the earlier "normalized resource budget" wording is retired — "normalized" wrongly implied a
  unit-normalisation). The repo commits an 802.11bd 10 MHz OFDM numerology only for the *channel
  BLER model* (`projects/ca_tosg/communication/channel.py`: N_FFT=64, N_SC=52 data subcarriers,
  Δf=156.25 kHz); it commits **no** channel-uses/s → per-frame-symbol-budget mapping, and none is
  derived here (a physical mapping requires guard-interval / occupied-bandwidth assumptions not
  committed, and fabricating them would put a memory-sourced number into a frozen contract). The
  three B_max values are therefore **prespecified operating points (in Msym/frame) on the
  payload–accuracy frontier**, not physical link capacities. A physical-capacity mapping is deferred
  (P2+); until then all B_max-referenced text must say **"prespecified average communication
  budget"** — never a Mbit/s link rate, and never a per-frame cap.

- **What B_max constrains — the average, not the frame (WORDING-1).** B_max bounds the **mean
  per-frame payload over a split**, not the payload of any single frame. The frozen model must
  satisfy `mean over ALL 1980 validate frames of B(a_t) ≤ B_max`, checked strictly and without
  tolerance at freeze time (§6 FINAL-CHECK IRON RULE) and re-checked by `tests/test_data_leakage.py`;
  during selection, feasibility is the frame-weighted **OOF mean** payload. Individual frames
  routinely exceed B_max by construction — a frame that selects F spends B_F = 0.99 Msym, which is
  above all three budgets — and that is **not** a violation. The *check* is hard; the *quantity*
  it checks is a mean. Text that calls B_max a "per-frame hard budget" is wrong and is corrected
  wherever it appears; `main.tex` still carries it and is listed under P2-PENDING-MIGRATION.
- **Compliance is a validate-side property.** The freeze proves the average on validate. Whether it
  transfers to test/Culver is an empirical question per model, answered in the results — the P4-A
  comparator's does not (Appendix C), the deployed selectors' does.

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

**Errata register.** An erratum is a defect found *after* the fact: the affected results are
withdrawn and regenerated, the corrected rule is written into this file, and a test is added that
fails if the defect returns. Nothing is annotated-and-kept.

| # | date | defect | corrected rule | guard |
|---|---|---|---|---|
| **P4A-1** | 2026-08-12 | P4-A fitted the z-score μ/σ on the whole validate grid before LOSO, so every fold judged its held-out scene on a scale that scene helped set — and those OOF numbers select λ | fold-local μ/σ inside LOSO (training scenes only, applied to train *and* held-out); full-validate μ/σ for the frozen model; validate statistics reused unchanged at test/Culver, refit banned | `tests/test_bandit_fold_scaling.py` |
| **P3-1** | 2026-08-12 | P3 drew SNR from the continuum while §3 pre-registers the 11-point grid; the cached `eff` substrate exists only at the grid points, so declared ≠ effective | every P3 item draws from the 11 points: `uniform` = 1/11 each, shaped laws binned at the midpoints and normalised; mainline continuous protocol untouched | `tests/test_p3_snr_support.py` |
| **LAYOUT-3** | 2026-08-12 | the restructure renamed modules and left two files importing the old names, and pointed a generator at a directory the committed artefact had left; its checks validated path constants only | every intra-repo import must resolve to exactly one existing module; frozen manifests are written where the committed copy lives (`results/manifests/`) | `tests/test_intra_repo_imports.py` |

Both scientific errata were re-run end to end. **P4A-1 changed two conclusions** (RL is no longer
below τ on validate; the comparator's budget compliance does not transfer to test) — those are
changed in Appendix C, not defended. **P3-1 changed no conclusion**: all five expectations still
read as before, with 4th–5th decimal shifts.

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
- **R3 (2026-08-08) — §5: "normalized resource budget" → "prespecified channel-use budget".**
  *(Term superseded by WORDING-1, 2026-08-13: "prespecified average communication budget".)* The
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
- **P4-A (2026-08-11, pre-registered before training) — match-adaptive internal learned-policy comparator.** An
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
    results + PROVENANCE under `results/baselines/contextual_bandit_runs/`, all labelled **"internal learned-policy comparator, not deployed"**.

```json CATOSG-P4A
{
  "problem_form": "contextual_bandit_single_step",
  "algorithm": "dqn_bandit_single_step_epsilon_greedy",
  "seed": 0,
  "network": {"hidden": [64, 64], "activation": "relu"},
  "train": {"steps": 4000, "batch": 512, "lr": 0.001, "optimizer": "adam",
            "epsilon_start": 1.0, "epsilon_end": 0.05, "epsilon_decay_steps": 3000, "target_is_immediate_reward": true},
  "reward": "eff_a - lambda*B_a",
  "feature_standardisation": {"loso": "fold_local_train_scenes_only",
                              "final": "zscore_on_full_validate_grid",
                              "deployment": "validate_statistics_reused_no_refit"},
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

- **ERRATUM P4A-1 (2026-08-12) — the P4-A comparator had a standardisation leak; its results are
  WITHDRAWN and re-run.** `baselines/contextual_bandit/train.py` fitted the z-score statistics
  (`mu = X.mean(0); sd = X.std(0)`) **once on the whole validate grid, before LOSO**, and every fold
  then trained and scored on those statistics. The held-out scene therefore helped set the scale on
  which its own features were judged, in all 9 folds, and the LOSO OOF numbers are the substrate λ is
  selected on — so the leak reached selection. It never touched the deployed CA-TOSG RF (which uses
  trees, no scaling) nor FROZEN_MANIFEST.json.
  **Corrected rule (now also pre-registered in the `CATOSG-P4A` block).** Inside LOSO, μ/σ are fitted
  on the fold's TRAINING scenes only and applied to both the training rows and the held-out scene.
  After LOSO and λ selection are finished, the final model refits μ/σ on the whole validate grid and
  retrains — legitimate, because validate is the only split any fitting may touch. test/Culver reuse
  the validate statistics unchanged; refitting there is banned and the evaluator reads μ/σ out of the
  checkpoint, never from the evaluation split.
  **Re-run:** three budgets retrained → `results/manifests/P4A_MANIFEST.json` replaced in place
  (single-version rule; no v1/v2 pair), re-evaluated on the SAME 200 paired CSI draws (seed unchanged)
  with the CIs recomputed. Appendix C now reports the new numbers.
  **What changed.** λ\* moved 0.2 → 0.05 and the OOF surface flattened (the old λ=0.05 OOF collapse to
  0.872 was the leak, not the objective: it is now 0.90644). Direction of the headline comparison is
  unchanged — **RL below RF on F1 in all 9 split×budget cells, CI entirely < 0** — with the magnitudes
  roughly halved (validate B0.10 ΔF −0.0043 → −0.0020; test B0.20 −0.0072 → −0.0036).
  **Two conclusions did change, and are changed here rather than defended:**
  (i) the old blanket "RL is below τ everywhere" is FALSE under the corrected protocol — RL is now
  above τ on validate at B_max 0.10 and 0.30 (CIs exclude 0), and below τ on test and Culver-City at
  every budget, so the claim is narrowed to the held-out splits;
  (ii) the comparator's budget compliance does not transfer: frozen payload 0.05146 ≤ 0.10 on validate,
  but 0.15568 on test at the same B_max = 0.10, where the RF stays at 0.06798.
  Guard against recurrence: `tests/test_bandit_fold_scaling.py`.
  **Wording.** "external baseline" is replaced everywhere by "internal learned-policy comparator" —
  it is our own construction trained to our protocol, not an external method's reported result, and
  calling it external overstated its independence. The directory name `baselines/contextual_bandit/`
  is unchanged.
  **Also fixed in the same commit** (defects introduced by the LAYOUT restructure and missed by its
  checks, which validated path constants but never import resolution or generator output paths):
  `evaluate.py` still did `import train_p4a_bandit` and `p3_variants.py` still did
  `import eval_p3_sensitivity` — both modules had been renamed, so neither file could run; and the
  P4-A manifest was being written to `results/baselines/contextual_bandit_runs/` while the committed
  copy had moved to `results/manifests/`, which would have produced two diverging manifests.

- **ERRATUM P3-1 (2026-08-12) — P3 sampled SNR off the pre-registered grid; all P3 results
  regenerated.** `projects/ca_tosg/evaluation/sensitivity.py` drew SNR from the CONTINUUM
  (`rng.uniform(0, 20)`, `rng.beta(2,5)*20`, `truncnorm.ppf`) while §3 pre-registers the support as
  the 11-point grid {0,2,…,20} dB. Root cause: the cached `eff` substrate the selector was fitted on
  exists only at those 11 points, so the distribution that reached the model was never the
  distribution the protocol declared — **declared ≠ effective**.
  **Corrected rule (now stated in §3's grid and in the Appendix B preamble).** Every P3 item draws
  from the 11 points. `uniform` = equal probability 1/11 per point. The two shaped laws are binned
  onto the grid with edges at the midpoints (±1 dB, clipped to [0,20]), CDF-differenced and
  normalised — the probabilities are recomputed and written into `PROVENANCE_p3.txt` on every run:

  | point (dB) | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20 |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | uniform | .0909 | .0909 | .0909 | .0909 | .0909 | .0909 | .0909 | .0909 | .0909 | .0909 | .0909 |
  | Beta(2,5)×20 | .0328 | .1907 | .2426 | .2149 | .1555 | .0944 | .0469 | .0177 | .0042 | .0004 | .0000 |
  | trunc-N(10,5) | .0138 | .0470 | .0816 | .1211 | .1535 | .1661 | .1535 | .1211 | .0816 | .0470 | .0138 |

  All five items use the grid, RF and τ replay the SAME samples (identical seed and call), and
  `CSI_SEED` is unchanged. The P3-C Rician bracket (`rician_bracket.py`) uses the same grid draw.
  **NOT changed:** the mainline continuous deployment protocol (SNR ~ U[0,20], §3) and therefore
  `baseline_sanity.csv`, which must keep reproducing `replay_summary.csv` exactly — it does, byte for
  byte, after the regeneration.
  **Effect: none of the pre-registered expectations changed.** All five items still read "met"
  (item 5 still "partial: physics met, selector limitation surfaced"); the shifts are in the 4th–5th
  decimal (test @ B_max 0.20, RF: item-1 ρ_F 0.1103→0.1092 / 0.0732→0.0725 / 0.0370→0.0366; item-2
  Beta(2,5) F1 0.90213→0.90220; item-4 F1 0.89707→0.89714 at BLER_L=0.10). Appendix B's Observed
  cells are regenerated from the new CSVs rather than retyped. Guard against recurrence:
  `tests/test_p3_snr_support.py`.

- **WORDING-1 (2026-08-13) — B_max is a *prespecified average communication budget*, not a
  per-frame hard budget.** The constraint has always been on the mean per-frame payload over a
  split — that is what §6's FINAL-CHECK IRON RULE freezes and what `tests/test_data_leakage.py`
  re-checks — but the prose called it a "per-frame hard budget", which asserts something the method
  does not do and could not do: B_F = 0.99 Msym exceeds every one of the three budgets, so any frame
  that selects F is over B_max by construction. §5 now states the constraint object explicitly.
  Replaced across `README.md`, `docs/`, and the results prose; **no number, model or result changes
  — this is a naming correction only.**

  **P2-PENDING-MIGRATION.** `main.tex` is deliberately NOT edited (three gates read it byte-exactly:
  the stale-fingerprint block-exit, `docs/claims.md`, and the paragraph-insertion check). The
  pending edits are registered here and land at P5:

  | file | line | current wording | wording at P5 |
  |---|---|---|---|
  | `paper/main.tex` | 207 | "where $\bar B_{\max}$ is the per-frame bandwidth budget." | "where $\bar B_{\max}$ is the prespecified average communication budget (a bound on the mean per-frame payload, not a per-frame cap)." |

  The symbol already carries the bar for a mean, so the sentence contradicts its own notation today.
  Out of scope on purpose: "per-frame payload" (L173) and "per-frame channel use" (L146) are correct
  as written — they describe a *frame's* payload, not the constraint — and the "$100$~ms budget"
  (L849) is the LiDAR-cycle **time** budget, unrelated to communication. `results/latency/
  system_timing.csv` carries that same time budget and is likewise untouched.

- **FA-1 (2026-08-13, PRE-REGISTERED; nothing run at the time of this entry) — feature ablation:
  channel-only / task-only / combined.** Asks what each half of the selector's input actually buys.
  Three variants, specified in Appendix E's machine-readable block:

  | variant | features | source |
  |---|---|---|
  | `channel_only` | 2: `est_snr_db`, `channel_is_rayleigh` | trained here |
  | `task_only` | the 21 ego-side cues | trained here |
  | `combined` | all 23 | **the deployed frozen models — referenced from `FROZEN_MANIFEST.json`, NOT retrained** |

  **The two new variants run the mainline pipeline, unmodified in every respect that could flatter
  them:** the same validate grid, the same scene-level 9-fold LOSO, the same 112-candidate table
  parsed from the `CATOSG-CANDIDATES` block, the same frame-weighted OOF feasibility, the same
  frozen walk with the hard check `B̄_frozen ≤ B_max`, and one model per B_max. Only the feature
  columns differ. Everything they produce is labelled **"labeled variant, not deployed"**.

  **Evaluation:** the same 200 paired CSI draws (`CSI_SEED` unchanged) across all three splits;
  F1, mean payload and action distribution per variant; paired bootstrap CIs against the deployed
  combined model. **Descriptive + CI only — NO decision of any kind.** The confirmatory primary was
  spent once at R9 and is not re-created here.

  **Outputs:** `results/sensitivity/feature_ablation.csv`, `results/provenance/PROVENANCE_fa.txt`,
  and a SEPARATE `results/manifests/FEATURE_ABLATION_MANIFEST.json` recording each variant model's
  sha256. It is kept apart from `FROZEN_MANIFEST.json` on purpose: variant models must never be
  mistakable for the deployed product.

  **Pre-registered expectations (§8 anti-forcing applies — these are checks, not targets; a miss is
  reported, not fixed):**
  1. `channel_only` should behave approximately like the τ rule — it has exactly the information τ
     has, so if the deployed selector's channel-side behaviour is really just a threshold, this
     variant should land near τ's F1/payload points.
  2. `task_only` cannot see channel feasibility at all, so it should collapse toward the
     conservative side (high ρ_L, payload near B_L): asking for F without knowing whether F can be
     delivered is punished by the ego-only fallback.
  3. If either expectation misses, the miss is reported as the finding.

  **RUN 2026-08-13 — outcome (full table + mechanism in Appendix E).** Expectation 2 **met, harder
  than predicted**: `task_only` picks λ\*=0 at all three budgets and never requests F (ρ_F = 0.000 in
  every split × budget cell), sitting on the Fixed-L floor. Expectation 1 **partially met**: at
  B_max=0.30 `channel_only` tracks τ closely (ρ_F 0.274 vs 0.299, test F1 0.90944 vs 0.90937 at 92%
  of τ's payload), but at 0.10/0.20 it collapses to all-L instead — τ\* is budget-matched by
  construction while the ablation ranks λ by OOF F1 among feasible candidates. The finding that
  matters: **neither feature group alone yields a graded policy** — only the combined model reaches
  intermediate payloads. Reported against the deployed model rather than for it: at B_max=0.30 on
  test `channel_only` has the higher F1 (CI [+0.0020, +0.0022]) at 1.54× the payload, so the
  combined model's advantage is payload at comparable F1, not F1 at comparable payload.

  **Untouched by this entry and by the run that follows it:** `main.tex`, the deployed frozen
  selectors, δ, τ\*, `FROZEN_MANIFEST.json`, and the mainline replay.

- **P4-C (2026-08-13, PLAN pre-registered as a DRAFT; NOTHING RUN — awaiting Peiyi's greenlight)
  — collaborator scale N ∈ {1,2,3}.** Full plan: `docs/p4c_plan.md`. Summary of what is fixed by
  this entry, and what is deliberately still open:

  **Fixed now.** (i) Subset rule, deterministic: the N nearest collaborators by Euclidean distance
  between `lidar_pose[0:2]` of collaborator and ego — the same distance OpenCOOD's `COM_RANGE = 70` m
  filter uses — ties broken by ascending CAV id; `|C| ≤ N` marks the frame `subset_is_full`. Enforced
  by an explicit mask, NOT by `max_cav`, whose ordering is loader-internal and unpinned.
  (ii) Payload: N collaborators = N messages, so B_L(N) = N·0.024 and B_F(N) = N·0.99 Msym, derived
  from the committed chain. Budget semantics unchanged (§5, WORDING-1): B_max bounds the MEAN.
  (iii) One decision per frame, broadcast to all N — the frozen selector has no per-collaborator
  action and none is invented. (iv) Descriptive + paired CI only, no decision of any kind.
  (v) Deployed models, δ, τ\*, `FROZEN_MANIFEST.json`, the mainline replay and `main.tex` untouched;
  new caches go to `gs_rerun/p4c_*` and never overwrite the registered ones.

  **Counted now (from the committed dataset index, not estimated):** frames with ≥1 / ≥2 / ≥3
  collaborators are validate 1980 / 1247 / 899, test 2051 / 1081 / 212, culver 478 / 123 / **0**.
  Culver-City therefore **cannot support N=3 at all** and supports N=2 on 123 of 550 frames; 119 test
  and 72 Culver frames have **zero** collaborators and are ego-only whatever the selector decides.
  Both facts are design constraints, and any N=3 claim about Culver would be a claim about "≤2".

  **CLOSED AT GREENLIGHT (2026-08-13), before any forward pass — delivery semantics across N links.**
  The frozen protocol defines delivery for ONE link; with N links partial delivery was undefined.
  Fixed now:
  - **Primary — semantics A, all-or-nothing, all three splits.** If any of the N requested links
    fails its frame-level BLER draw, the frame falls back to ego-only, exactly as the single-link
    protocol does. eff_F(N) therefore needs the full N-subset fusion only. 4409 new forwards.
    A is a **conservative** reading of the feature branch: it can only understate F's value, never
    overstate it.
  - **Bracket — semantics B, partial fusion, `validate` ONLY.** Fuse whichever subset arrived;
    eff is needed for every non-empty delivered subset (2^N − 1 per frame), 8070 forwards. Labelled
    **"bracketing variant, not deployed"**, reported beside A and never merged into it. It bounds A
    from above on the one split where fitting is permitted.
  - Under both, the N links draw independent channel realisations from the same CSI stream as the
    mainline replay, and the per-link BLER is the existing Sionna frame-level table.

  **Also fixed at greenlight:**
  - **Culver N=3 is annotated `identical to N=2 by construction`** — no Culver frame has 3
    collaborators — and is **not reported as an independent data point**. If the two columns ever
    differ numerically, that is a subset-mask bug, not a result.
  - **Zero-collaborator frames stay in the denominator** (test 119, culver 72) and are reported as
    their own row; they are ego-only whatever the selector decides, and removing them would
    silently redefine the split.
  - **N>1 budget overshoot is a TRANSFER PROPERTY, pre-declared, and is not patched.** The deployed
    selectors were frozen under N=1 semantics; at N=2/3 the same policy costs N× per requested
    message, so its mean payload will exceed B_max. No model is retrained, no threshold retuned, no
    δ or τ\* touched — the overshoot is reported, in the same way τ's and P4-A's non-transfer are.
  - **The late-branch re-merge is treated as UNVERIFIED until proven.** Before it is relied on,
    re-merging the FULL CAV set must reproduce the committed `late_{split}.npz` bit-for-bit; if it
    does not, the run falls back to a per-CAV re-run and both the outcome and the extra cost are
    recorded in `PROVENANCE_p4c.txt`.
  - **The 0.303 s/frame estimate is replaced by a 20-frame micro-timing** as the first action of the
    run, before the full sweep is launched; the measured rate goes into the provenance.

  **Expected (§8 anti-forcing; finalised at greenlight):** payload scales ≈ linearly in N, so the
  frozen selectors overshoot B_max at N=2/3 on every split — a property of the transfer, not a
  violation to patch, and the same class of non-transfer already recorded for τ and for P4-A; F1
  rises with N where the feature branch is delivered, with diminishing returns; on Culver the N=3
  column must be identical to N=2, and a difference there is a mask bug rather than a result.

  **RUN 2026-08-13, semantics A on all three splits — outcome (full table: Appendix F).** 8818
  forwards in 73.5 min. Expectation on F1 **met** (rises with N, steeply diminishing: at B_max=0.20
  the second collaborator buys 5–30× less than the first; every ΔF1-vs-N=1 CI excludes 0). Culver
  invariant **met, and it did its job** — it fired on the first run and forced ruling k_eff =
  min(N, collaborators), because a frame cannot message collaborators it does not have.
  Payload expectation **MISSED**: realised scaling is **sub-linear** (1.65×/2.15× validate,
  1.39×/1.44× test, 1.41×/1.41× Culver at B_max=0.20) because the collaborator supply saturates —
  mean availability is 2.90 / 1.59 / 1.09 per split — so overshoot occurs in **5 of 27 cells**, not
  on every split. **The first, buggy run confirmed the expectation; the corrected run refutes it.**
  What separated them was the machine-checkable Culver invariant, written down before either run,
  not judgement after the fact.
  **Semantics B (validate-only partial-fusion bracket) is NOT yet run.** Measured cost at the
  realised validate rate (~0.6 s/frame): 8070 subsets × 2 branches ≈ 2.7 GPU-hours. Command and
  design are fixed; it is a separate run, not a pending edit to this one.

- **P4-C-b (2026-08-14) — (a) the "N>1 always overshoots" expectation is marked WRONG; (b) the
  semantics-B bracket is scope-reduced by an EXACT equivalence and pre-registered before running.**

  **(a) Expectation 1 of P4-C was WRONG.** Its original text stays in this change-log unedited —
  *"payload scales ≈ linearly in N, so the frozen selectors overshoot B_max at N=2/3 on every
  split"* — and is hereby marked **WRONG**. Measured mechanism: payload scales with the collaborators
  a frame actually **has**, not with the nominal N, and the supply saturates (mean availability
  2.90 / 1.59 / 1.09 per split). Realised scaling at B_max=0.20 is 1.65×/2.15× on validate,
  1.39×/1.44× on test, 1.41×/1.41× on Culver, and overshoot occurs in **5 of 27 cells** — never on
  Culver. The reasoning behind the expectation ("near-arithmetic; a non-linear result is visibly a
  bug") was itself the error: non-linearity here is the collaborator supply, not a bug.

  **(b) Semantics B — scope reduction, EXACT, not an approximation.** B is computed only for frames
  that are **in scope**, where in scope means:

  > a frame is in scope iff **some frozen selector chooses F for it at some cell of the
  > deterministic validate grid** (frame × 11 SNR × 2 channels) **and** the frame has **≥2
  > collaborators**. B is run at **N=2 only**.

  Why the frames left out are *identical* under A and B, by construction rather than by
  approximation:
  - **E frames**: no message is sent, so there is nothing to deliver partially.
  - **L frames**: BLER_L = 0 in the mainline, so every object-level message is delivered; "partial"
    and "all-or-nothing" coincide.
  - **frames with ≤1 collaborator**: one link (or none) — partial delivery of a single link *is*
    all-or-nothing.
  Only a frame that both requests F and has ≥2 links can distinguish the two semantics.

  **Counted before running** (and the scope rule verified, not assumed): on validate, 984 frames
  ever have F chosen on the grid; the set of frames that ever have F chosen in the 200-realisation
  **replay** is also 984 and is a **subset of the grid set with 0 frames outside it**, so the
  grid-based rule cannot exclude a frame the replay would have needed. Intersecting with ≥2
  collaborators gives **690 in-scope frames**.

  **Only ONE new subset per in-scope frame.** At N=2 the non-empty delivered subsets are
  {nearest}, {second}, {both}; {nearest} is already the cached N=1 arm and {both} is already the
  cached N=2 arm, so only **{second-nearest alone}** is new. 690 frames × 2 branches =
  **1380 forwards ≈ 0.23–0.27 GPU-hours** at the realised validate rate — against the 8070-subset,
  2.7-hour figure the original plan carried, an 11.7× reduction with no approximation.

  **RUN 2026-08-14 — outcome (table in Appendix F).** 1380 forwards in 11.9 min (0.20 GPU-hours,
  inside the 0.23–0.27 estimate). B ≥ A at all three budgets with every CI excluding 0, but the gap is
  **+0.00010 / +0.00018 / +0.00032 F1** — the fourth decimal. The conservative all-or-nothing reading
  therefore costs essentially nothing at N=2, and the delivery-semantics ambiguity that blocked the
  P4-C run is **immaterial at this operating point** rather than an open degree of freedom. Mechanism:
  the partial-delivery mass is 2·b(1−b) and the selector requests F almost only where b is small.
  Payload is identical under A and B by construction (channel use is charged on request, not on
  delivery); the CSV agreeing on it is an implementation check, not a result. B at N=3 and B on
  test/Culver were not pre-registered and were not run.

  **Delivery expression under B (N=2, independent links, per-link frame BLER b):**
  `eff_F^B = (1−b)²·c_both + b(1−b)·(c_nearest + c_second) + b²·ego`, against
  `eff_F^A = (1−b)²·c_both + (1−(1−b)²)·ego`. B ≥ A whenever a partial fusion beats ego-only, which
  is the expected direction; the two coincide exactly where the scope rule says they must.

  **Labelling and outputs:** rows join the existing `results/sensitivity/collaborator_scale.csv`
  under `semantics=B`, labelled **"bracketing variant, validate only, N=2, not deployed"**.
  Descriptive + paired CI against the A row at the same (split, B_max, N); **no decision**. Deployed
  models, δ, τ\*, `FROZEN_MANIFEST.json`, the mainline replay and `main.tex` remain untouched.

- **P5-1 (2026-08-14) — migration INVENTORY for the main-text unfreeze. Nothing edited.**
  Full list: `docs/p5_migration_list.md`. `main.tex` is not touched by this round, so the three
  gates that read it byte-exactly still pass unchanged.

  **Counted, with the search scope stated:** 9 `P2-PENDING-MIGRATION` rows in `docs/claims.md`
  (2 further occurrences are the register itself in this file, not edits); 97 claim rows, of which
  27 evidence-filled and 70 evidence-empty; **0 STALE**; **0 dangling** evidence citations (every
  cited CSV/generator was resolved against the tree); `C_{16}` 52 occurrences on 42 lines,
  `C_{256}` 21 on 18 lines.

  **The 9 rows are three families, and two of them change a headline, not a wording:**
  - *Latency* (4 rows): 52.8 ± 5.7 ms / P95 59.1 / 2000 trials is the **retired v2** selector; the
    P2 frozen selectors measure 59.9 ± 5.3 / P95 69.3 / 1000 trials. Conclusion survives (still
    inside 100 ms) with a narrower margin; the "10× lower latency" variant claim is not re-measured
    on P2 products and must be re-measured or dropped.
  - *True end-to-end AP* (3 rows): the paper's "+0.074 (Culver) / +0.026 (validate) / +0.001 (test)"
    becomes, under the 200-realisation descriptive AP, **+0.0173 / +0.0069 / −0.0002…−0.0008** —
    roughly 4× smaller on both positive splits and **sign-flipped on test**. "Lifts AP by up to
    +0.074" cannot survive in that form; the surviving claim is about payload, not AP lift.
  - *Policy engine* (2 rows): the single operating point "F1 0.909 at 0.251 Msym, 25% of C₁₆" becomes
    three budget-indexed frozen points (test: 0.90326/0.06798, 0.90463/0.09472, 0.90734/0.18703);
    "25% of C₁₆" becomes 9.6% of B_F at B_max=0.20. **τ now beats RF on F1 at B_max 0.20 and 0.30 on
    test**, at 2.3× and 1.7× the payload — the paper currently frames τ as weaker on both axes.

  **Two further pending edits registered outside `claims.md`:** WORDING-1 (`main.tex:207`,
  per-frame → prespecified average communication budget) and **FA-1 supersedes the paper's
  channel-only/full ablation table** (`main.tex:494–512`) — a chain the brief did not list.

  **Terminology `C_{16}` → F is three migrations, not one rename:** the *action* (which must also
  gain **E**, absent from the paper's action set today — a structural edit, not a symbol swap), the
  *payload constant* `B_{C_{16}}` → `B_F` (value unchanged, pinned by `tests/test_payload.py`), and
  the *256-QAM comparator*, which keeps its symbol but must stop reading as a deployed action (§4
  already fixes that wording). A blanket substitution would silently promote C₂₅₆ to an action.

  **Second backbone:** `main.tex` has no such section; P5 creates an **empty placeholder** at
  `sec:second_backbone` between the Where2comm comparison and Deployment Robustness, marked
  **pending P4-B**, and nothing may be written in it or cited from it until P4-B has run.

- **P5-2 (2026-08-14) — migration batch 1 EXECUTED in `main.tex`.** No frozen product, model, δ,
  τ\*, manifest or result CSV was touched; only `paper/main.tex`, the regenerated `docs/claims.md`
  and one fingerprint pattern changed.
  - **A (latency, 4 sites):** 52.8 ± 5.7 ms / P95 59.1 / 2000 trials (retired v2) → **59.9 ± 5.3 ms /
    P95 69.3 / 1000 batch-1 trials**, quoted for the **slowest of the three frozen selectors** with
    that reason stated in the text, margin now 40 ms. The "decision tree or logistic regression
    reaches the same F1 at >10× lower latency" sentence is **deleted** in both places; it was never
    re-measured on the P2 products.
  - **B (AP, 3 sites):** the +0.074 / +0.026 / +0.001 family is **gone**. Replaced by the descriptive
    AP@0.5 grid (3 splits × 3 budgets, read from `results/main/true_e2e_ap.csv`) plus the
    space-normalisation sentence: headroom = Feature-ceiling − Fixed-L = **0.0267 / 0.0027 / 0.0892**
    (validate / test / Culver), with the text stating outright that test has effectively no headroom
    and that **no AP advantage is claimed on any split**.
  - **C (policy, 2 sites):** one operating point → **three budget-indexed frozen points** (test
    0.90326/0.068, 0.90463/0.095, 0.90734/0.187); "25% of C₁₆" → **9.6% of B_F at B_max=0.20**; τ
    rewritten to the **locked R9 wording** ("significantly lower by ≈0.0028, CI entirely below zero,
    within the 0.005 non-inferiority margin, payload −56.3%") plus the explicit statement that τ
    attains the higher F1 at B_max 0.20 and 0.30 (0.90740 / 0.90937) at 2.3× and 1.7× the payload.
    The BANNED wordings from `r9_result_claims.md` ("same F1", "matches F1", …) are absent — checked.
  - **W1:** `main.tex:207` per-frame bandwidth budget → prespecified average communication budget.
  - **W2:** the feature-ablation table and its findings paragraph are replaced by **FA-1**: both
    single-half variants collapse to always-L at B_max=0.20 (ρ_F = 0.000, F1 at the fixed-L floor
    0.9011) and only the full 23-feature selector reaches an intermediate point (0.9046 at 0.095).
    The not-re-run cues+γ̂ cut is dropped and said to be dropped.
  - **C₁₆ → F, three usage classes, no blanket substitution:** the ACTION (`\mathcal{S} = \{L, F\}`
    and its definition; **E is deliberately NOT added here** — its formal definition paragraph is
    batch 2, and a symbol without a definition would be worse than the current omission); the
    PAYLOAD CONSTANT (`B_{C_{16}}` → `B_F`, value unchanged and still pinned by
    `tests/test_payload.py`); the FIXED-POLICY baseline name (9 sites, `Fixed $C_{16}$` → `Fixed $F$`).
    C₂₅₆ keeps its symbol and is repositioned with the §4 locked wording as a **physical-layer
    comparator, not a deployed action**. 30 `C_{16}` mentions remain in modulation-comparison
    contexts, where the symbol is correct; the glossary that retires the dual naming is batch 2.
  - **Second backbone:** a `TODO(P4-B)` comment token only, at the intended position between the
    Where2comm comparison and Deployment Robustness. **No empty section was created.**
  - **Fingerprint precision fix, not a weakening:** `RX 0\.895` → `RX 0\.895[^9]`, following this
    file's own `0\.888[^6]` convention. Bare `0.895` and `0.8950` are still caught; the legitimate
    new value `0.8959` (validate AP@0.5 at B_max=0.20) is allowed. Without it the block-exit gate
    would have failed on a *correct* number.
  - **Ledger regenerated after the edits:** 97 → **104** claim rows, evidence 27 → **18 filled**,
    70 → **86 pending**, **0 STALE**. The drop in filled rows is not evidence loss: the edited
    sentences are new claims with new stable IDs, so their hand-filled evidence does not carry over
    and must be re-attached in the back-fill pass. One edit had to be reworded because two of the new
    sentences produced the same letters-only skeleton and collided on stable ID — caught by the
    generator, fixed in the prose rather than in the ID machinery.
  - **Flagged, NOT edited (out of scope for this batch):** the headline "the learned selector
    Pareto-dominates the re-tuned threshold at matched channel use" (~line 390) is not contradicted
    by the new τ rows — those compare at *different* payloads — but it has not been re-verified
    against the frozen replay and should be, in batch 2.

- **P4-B-a (2026-08-14) — the SECOND intermediate-fusion checkpoint is on disk and recorded.
  NO inference has been run; P4-B remains PLAN-only.**
  Source: OpenCOOD official model zoo, row *"Attentive | 1.2.1 | SECOND | Intermediate"*, Box file
  **1621121166914**, archive `second_attentive_fusion.zip`. **Programmatic download from the official
  share is disabled server-side** — HTTP 403 *"This user is not allowed to use direct links"* on the
  Box shared-file download endpoint (with and without browser headers), HTTP 401 on
  `api.box.com/2.0/shared_items` without a token — so the archive was **fetched manually by the
  author**. No alternative or mirror source was used, and none may be: a second-backbone claim must
  rest on the official weights.
  Installed at `pretrained_models/second_attentive_fusion/`, **51.0 MB** across four files, sha256 of
  each recorded in `results/manifests/P4B_MANIFEST.json`:
  `second_attentive_fusion/latest.pth` 21 274 703 B (`59a9df09…`),
  `second_attentive_fusion_compression/latest.pth` 29 753 905 B (`a37e1df2…`), plus the two
  `config.yaml` (2 400 B `7f34e9f9…`, 2 505 B `d36b8e7b…`).
  Both configs confirm the backbone: `model.core_method: second_intermediate`,
  `name: second_intermediate_fusion`, `IntermediateFusionDataset`; the `_compression` variant differs
  only by `base_bev_backbone.compression = 2`.
  Dependency check: `import spconv` → **2.3.8** (clean). SECOND uses sparse convolutions, so this is
  the dependency that would gate a P4-B run.
  The manifest is labelled **"EXTERNAL INPUT, not a product of this repository"** and kept separate
  from every product manifest. `inference_status: NOT RUN`.

- **P4-B-b (2026-08-14) — the SECOND checkpoint does NOT load in this environment. P4-B stays
  blocked; no inference, no dummy forward, no code changed.**
  - **Load test: FAILED, both variants.** It is **not** a key-name incompatibility: all 160 tensors
    match by name (**0 missing, 0 unexpected**). The blocker is **12 shape mismatches**, every one a
    `backbone_3d` sparse-convolution kernel. spconv 1.x stores kernels as `(kD,kH,kW,C_in,C_out)`;
    spconv 2.x expects `(C_out,kD,kH,kW,C_in)`. Element counts are identical and
    `model_shape == permute(ckpt_shape, (4,0,1,2,3))` holds exactly — the right weights in the wrong
    axis order. Example: `backbone_3d.conv1.0.0.weight` ckpt `(3,3,3,16,16)` vs model `(16,3,3,3,16)`.
    (`load_state_dict` raises on a size mismatch even with `strict=False`, so the missing/unexpected
    counts were obtained by comparing key sets separately.) **Nothing was fixed:** no permutation
    shim, no spconv downgrade, no edit to OpenCOOD — a ruling is needed on whether converting the
    layout is acceptable for a generality arm, since a converted checkpoint is no longer bit-wise the
    published one.
  - **Variant ruling (independent of the load failure).** The **`_compression` variant is the P4-B
    main variant**, by the rule "match the deployed mainline feature branch":
    `pointpillar_attentive_fusion_compression/config.yaml` → `base_bev_backbone.compression: 2`, and
    that is the directory the mainline F caches are built from; `second_attentive_fusion_compression`
    → `compression: 2` **matches**, while `second_attentive_fusion` has no such key (uncompressed).
    Recorded caution: both SECOND configs carry a `height_compression` block, which is SECOND's
    3D→BEV height squeeze and **not** the feature-compression knob — using it to pick the variant
    would select the wrong model.
  - **Dummy forward: NOT RUN**, gated on the load test passing.

- **P5-3 (2026-08-14) — migration batch 2 executed in `main.tex`.** Frozen products, models, δ,
  τ\*, manifests and result CSVs untouched; only `main.tex`, the regenerated `docs/claims.md` and
  `tests/stale_fingerprints.md` changed.
  - **P0, the Pareto-dominance family: every dominance expression is gone** (`Pareto-dominates`,
    `Pareto-optimal`, and the caption's "at matched channel use its realised F1 is higher"), replaced
    by a budget-indexed account: **ahead at B_max=0.10** (+0.00055, CI [+0.00046, +0.00065], reported
    as a **secondary CI with no decision attached**), **behind at 0.20 and 0.30** (τ 0.90740 / 0.90937
    vs 0.90463 / 0.90734) **at 2.3× and 1.7× the payload**; the only surviving claim is the R9 locked
    one — non-inferior within 0.005 at a 56.3% payload reduction. `RX Pareto-dominat` and
    `RX Pareto-optimal` are now **retired fingerprints**, so the phrasing cannot come back.
  - **v2 leftovers in the same paragraph, both deleted rather than restated.** "+0.090 F1 on hard
    frames" and "≈12% lower channel use at matched F1" **cannot be recomputed against the frozen
    replay**: the difficulty stratification and the τ sweep are both products of the legacy
    200-realisation engine (`policy_200seed.py`, `ablations/a2_difficulty.py`), not of the frozen
    selectors, so a "matched-F1" recomputation would splice two engines. Deleted from the abstract,
    the contribution list, the headline paragraph, the threshold section and the conclusion. The
    "cues add no significant F1 over channel state" reading is replaced by the FA-1 policy-shape
    result: channel-only collapses to always-L at B_max 0.10/0.20, and at 0.30 reaches a higher F1
    than the full selector only by spending **1.54×** the channel use.
    *(Left standing, out of this batch's scope: §sec:difficulty still reports +0.090 as its own
    result with its own figure — that whole subsection is legacy-engine and needs its own round.)*
  - **E is now a defined action.** `\mathcal{S} = \{E, L, F\}`, with a paragraph stating that $E$ is
    a first-class action (B_E = 0, chosen *before* transmission when the ego is already sufficient or
    the channel is hopeless) **and** the delivery-failure fallback (what remains *after* a lost F),
    and that the two roles share a quantity but are decided at different times. A notation table
    (`tab:notation`) fixes $F \equiv C_{16}$ and marks $C_{256}$ a physical-layer comparator, not a
    deployed action.
  - **C₁₆ residue:** 14 policy-context occurrences migrated to $F$; **24 remain on 20 lines**, all
    modulation-context or the glossary itself, where the $C_q$ form is the correct symbol.
  - **§VI-N unanchored sentence deleted.** The "ImportanceMapJSCC reference of $0.801/0.688$ (learned
    importance-map identity ceiling)" is anchored to **nothing** in `results/`: the committed JSCC
    tables top out at AP@0.5 $0.7328$ / AP@0.7 $0.6181$ on validate, and no identity-channel row
    exists. Recomputing it would need new inference, so the clause is removed rather than re-derived
    from memory.
  - **Ledger regenerated:** 104 → **107** rows, **0 STALE**, evidence 18 → **17 filled**, 86 → **90
    pending**, 0 dangling.

- **P4-B-c (2026-08-14, PRE-REGISTERED before the conversion was written and before the first
  forward pass) — convert the SECOND checkpoint's sparse-conv kernel layout, then *prove* the
  conversion by reproducing the model zoo's own published AP. No cache batch is run.**
  Scope: the layout blocker of P4-B-b only. Deployed CA-TOSG models, δ, τ\*, `FROZEN_MANIFEST.json`,
  the mainline replay, every committed result CSV and `main.tex` are untouched.
  - **The conversion.** One-off script `tools/convert_second_checkpoint.py`: for every 5-D
    `backbone_3d` sparse-conv kernel, `permute(4,0,1,2,3)`; every other tensor byte-identical. This
    is spconv's **own** documented spconv-1.x→2.x migration, `RSCK`→`KRSC`
    (`spconv.pytorch.conv.SparseConvolution._load_weight_different_layout`, selected by
    `SPCONV_SAVED_WEIGHT_LAYOUT=RSCK`). The library's convenience hook is **not** used because in
    spconv 2.3.8 it applies that permutation **twice** — verified, not read: with the env var set,
    `conv_input.0.weight` arrives as `[4,16,3,3,3]` instead of `[16,3,3,3,4]` and the load still
    raises. The script applies it exactly once, which is that hook's intended single conversion.
  - **Pre-registered expectations (a miss is the finding; nothing is tuned to hit them).**
    - **E1** Exactly **12** tensors disagree in shape; all are `backbone_3d` sparse-conv kernels; all
      are 5-D; all are reconciled by `permute(4,0,1,2,3)`; **0 unexplained** mismatches.
    - **E2** After conversion, `load_state_dict(strict=True)` returns *all keys matched* — 0 missing,
      0 unexpected, 0 shape mismatch — for **both** variants.
    - **E3** The conversion is **lossless**: identical key set, identical per-tensor element
      multiset, identical dtype, and `permute` is invertible (round-trip is bit-identical to the
      original file's tensors).
    - **E4 (decisive).** Official OpenCOOD `intermediate` inference with the converted
      `_compression` weights reproduces the zoo row *"Attentive | 1.2.1 | SECOND | Intermediate"*,
      **compression column**: **AP@0.7 = 0.783 on Default Towns (`test`)** and **0.760 on Culver
      City (`test_culver_city`)**, tolerance **±0.005**. The zoo's convention is
      `global_sort_detections=False` (README: *"OPV2V paper does not perform the global sort"*), so
      the pass/fail number is the no-global-sort AP. The global-sort AP is recorded alongside as a
      **separate quantity** — CA-TOSG's own AP pipeline is global-sort (Change-log, global-sort
      unification) and the two may not be blended in one sentence.
    - **E5 (stop rule).** If E4 misses on either split, the run **stops** and reports the numbers as
      they came out. No retuning of NMS/score thresholds, no substitution of a different IoU or a
      different AP convention, no switch to the uncompressed variant to make a number fit. A miss
      means the conversion is not established and P4-B stays blocked.
  - **Why the reproduction is required at all.** The whole force of a second-backbone arm is that the
    weights are the *published* ones. A layout-converted file is no longer bit-wise the published
    file, so the claim has to be re-earned empirically: matching the zoo's own AP to ±0.005 is what
    licenses the label *"official weights, lossless axis reorder, verified"*.
  - **Artefacts.** Converted checkpoints are written **outside** this repo, beside the originals
    (`pretrained_models/second_attentive_fusion_spconv2/`), and are recorded in a **new product
    manifest** `results/manifests/P4B_CONVERSION_MANIFEST.json` (original sha256, converted sha256,
    per-key permutation rule, reason, and the verification result). `P4B_MANIFEST.json` stays an
    **input-only** record and is not rewritten.
  - **Only after E4 passes:** a dummy forward records the transmitted BEV tensor's exact shape
    before and after `base_bev_backbone.compression = 2`. Then the batch **stops** — the eff-cache
    /grid-expansion batch of P4-B(1)–(3) is *not* run in this round, and `B_F^SECOND` stays open
    pending the `bits_per_element` ruling.

- **P4-B-c RESULT (2026-08-14) — the conversion is established. The SECOND checkpoint loads, and
  with it OpenCOOD reproduces the model zoo's own published AP. P4-B's load blocker is closed; the
  cache batch was NOT run and `B_F^SECOND` is still open.**
  - **E1 met.** Exactly **12** tensors disagreed, all `backbone_3d` sparse-conv kernels, all 5-D,
    all reconciled by `permute(4,0,1,2,3)`, **0 unexplained**. (Tensor counts: the `_compression`
    variant has **232** state-dict entries, the uncompressed one **160** — P4-B-b's "160 keys" was
    the uncompressed variant's count. Both have the same 12 mismatches.)
  - **E2 met.** After conversion, `load_state_dict(strict=True)` returns *all keys matched* —
    0 missing, 0 unexpected, 0 shape mismatch — for both variants.
  - **E3 met.** Per tensor: key set unchanged, element multiset unchanged, dtype unchanged, and the
    permutation round-trips bit-identically. 12 permuted, 220 (resp. 148) copied unchanged.
  - **E4 met — the decisive one.** Official `intermediate` inference with the converted
    `_compression` weights, no-global-sort AP (the zoo's convention):
    **test (Default Towns) AP@0.7 = 0.78384 vs the published 0.783 (Δ +0.00084)**;
    **Culver City AP@0.7 = 0.76188 vs the published 0.760 (Δ +0.00188)**. Both an order of
    magnitude inside the ±0.005 tolerance. Targets are parsed out of OpenCOOD's own README table at
    run time, not hard-coded. Global-sort AP is recorded separately (0.9118 / 0.8250) and is **not**
    comparable to the zoo row. Record: `results/manifests/P4B_VERIFICATION_compression.json`.
  - **Two defects found and fixed while doing this, both of the silent-wrong-number kind.**
    (i) spconv 2.3.8's own `SPCONV_SAVED_WEIGHT_LAYOUT=RSCK` migration hook applies the permutation
    **twice** (`ALL_WEIGHT_IS_KRSC` re-enters the same branch), producing `[4,16,3,3,3]` where
    `[16,3,3,3,4]` is wanted — the load still raises. Demonstrated from the library, not asserted;
    the script applies the permutation once. (ii) `opencood.utils.eval_utils.calculate_ap` cumsums
    `result_stat`'s `tp`/`fp` lists **in place**, so it is not idempotent: the first verification
    run scored both AP conventions off one `result_stat` and the global-sort column came out as
    ~16,000. The pass/fail column was computed first and was correct, but the run was **re-done
    from scratch with a deep copy** rather than patched in the manifest.
  - **Run-to-run drift.** The two independent runs differ by ~1e-4 in AP (GPU non-determinism);
    both PASS by a wide margin. Both figures are recorded in the conversion manifest.
  - **Step 4 (dummy forward) — the pre-registered payload estimate was WRONG, and this is the
    finding.** P4-B item (2) assumed the transmitted tensor is the HeightCompression BEV output,
    C×H×W = 256×100×352 = **9,011,200** elements/CAV. That element count is confirmed exactly by the
    forward — but it is **not what the `_compression` variant transmits**. `AttBEVBackbone` has
    **two** branches, each with its own `AutoEncoder`, and each branch is fused across CAVs after
    its own compression, so **both bottlenecks** go on the wire:
    | branch | pre-compression | transmitted bottleneck | ratio |
    |---|---|---|---|
    | 0 | 128 × 100 × 352 = 4,505,600 | **32 × 25 × 88 = 70,400** | 64× |
    | 1 | 256 × 50 × 176 = 2,252,800 | **128 × 25 × 88 = 281,600** | 8× |
    Transmitted total **352,000 elements/CAV/frame**, i.e. **25.6× smaller** than the plan's
    9.01 M. The bottleneck is not a named tensor anywhere — `AutoEncoder.forward` runs encoder and
    decoder back to back and returns only the reconstruction — so it was captured with a forward
    hook on the last encoder stage, not inferred from the config.
    **Consequence for `B_F^SECOND`, still NOT decided here:** the plan's illustrative 36.0 Msym
    (INT8) / 72.1 Msym (FP16) were computed off the wrong element count. On the transmitted count
    they would be ≈1.41 / 2.82 Msym. But the *mainline* accounting does not use a bottleneck count
    at all — it applies a fixed 1.98 Mbit source budget (≈0.92 bit/element) to the **uncompressed**
    2.16e6-element PointPillar tensor. Two self-consistent accountings are therefore available and
    they differ by more than an order of magnitude. **The choice is Peiyi's; nothing is fixed here,
    and no number is aligned to the PointPillar figure by coincidence.**
    Record: `results/manifests/P4B_DUMMY_FORWARD_compression.json`.
  - **Scope kept.** Converted checkpoints live outside the repo
    (`pretrained_models/second_attentive_fusion_spconv2/`, sha256 both sides in
    `P4B_CONVERSION_MANIFEST.json`); `P4B_MANIFEST.json` was left as the input-only record. **No
    eff cache, no grid expansion, no frozen-walk evaluation was run** — P4-B items (1) and (3)
    remain unstarted, and only the `_compression` variant carries a verified label.
  - **Caution recorded for the results index.** `projects/ca_tosg/utils/results_index.py` enumerates
    with `git ls-files results`, so an **untracked** result file is invisible to it and its
    "N files indexed, 0 unattributed" line is a statement about *tracked* files only. Regenerating
    it before `git add` silently under-reports; the three new P4-B manifests had to be staged first.

- **P4-B-d (2026-08-14, PRE-REGISTERED before the probe was generalised and before any number was
  computed) — fix `B_F^SECOND` on the mainline's own declared convention; measure both backbones
  under both accounting conventions; re-derive `N_CW` and the feasibility mask from the new payload.
  The INT8/FP16 bit-depth option of P4-B item (2) is WITHDRAWN.**
  Ruling taken (Peiyi, 2026-08-14): `B_F^SECOND` follows `main.tex` §"Message Construction and
  Payload Accounting" — a **declared bits-per-element budget applied to the pre-compression
  cross-link BEV tensor** — not a bit-depth on the transmitted bottleneck. The P4-B-c dummy forward
  stands as measurement; only its *interpretation* as an INT8/FP16 wire format is withdrawn.
  - **(1) `B_F^SECOND`, whole chain in the payload audit, no hand-written constant.**
    `elements_SECOND` = Σ over branches of the **pre-compression** cross-link tensor, per CAV, read
    from the probe manifest (branch 0 4,505,600 + branch 1 2,252,800 = 6,758,400). Bits-per-element
    is **derived from the mainline pair**, `B_C / elements_mainline_declared`, not typed in; the
    paper prints it rounded as ≈0.92. `K` (LDPC info bits/codeword), the code rate and the
    bits/symbol come from the existing sources, not from new literals. Chain:
    elements → info Mbit → ÷ rate-1/2 → ÷4 (16-QAM) → Msym. Added as a `payload_audit` extension in
    `tests/test_payload.py` that recomputes and bit-compares every link.
    - **Pre-registered expectation E1.** Peiyi's ruling quotes ≈6.22 Mbit → ≈3.11 Msym, which is the
      rounded 0.92 bit/element. The **derived** ratio is `1.98e6 / 2,162,688 = 0.91553`, which gives
      ≈6.19 Mbit → ≈3.09 Msym. Both are reported; the derived one is primary because the constant
      may not be typed in. A ~0.5 % gap between them is expected and is *itself* a datum for the
      paper's "conclusions are insensitive to this constant" claim. If the gap is larger than 1 %,
      stop — it means the mainline anchor is not what the audit thinks it is.
  - **(2) Same hook, both backbones, both conventions.** The P4-B-c probe is generalised to any
    OpenCOOD model with an `AttBEVBackbone`, and run on the deployed mainline
    `pointpillar_attentive_fusion_compression` as well. Per branch it records the **pre-compression**
    block output and the **transmitted** tensor (the AutoEncoder *encoder* output where a branch is
    compressed, the block output itself where it is not). Output: a 2 backbones × 2 conventions
    table, so "the conclusions are insensitive to the source-budget constant" stops being an
    assertion and becomes a measurement.
    - **Pre-registered expectation E2, stated before the run.** `AttBEVBackbone` compresses branch
      `idx` only while `compression - idx > 0`. The mainline has **three** branches
      (`layer_nums 3/5/8`, `num_filters 64/128/256`) with `compression: 2`, so its **third branch is
      transmitted UNCOMPRESSED**, whereas SECOND has two branches and compresses both. The two
      backbones are therefore *not* structurally comparable at the bottleneck, and I expect the
      mainline's pre-compression sum to differ from the paper's declared 2,162,688
      (`256×48×176`) — the declared figure describes one 256-channel tensor at y ∈ [-38.4, 38.4] m,
      while the deployed checkpoint's config has y ∈ [-40, 40] m. **If the declared anchor and the
      deployed tensor disagree, that disagreement is the finding and is reported, not reconciled.**
  - **(3) Budgets, `N_CW`, frame BLER and mask re-derived from the new `B_F^SECOND`.**
    `B_max^SECOND ∈ {10, 20, 30}% × B_F^SECOND`. `N_CW^SECOND = ceil(B_F^SECOND_bits / K)` with `K`
    read from `projects/ca_tosg/communication/ldpc_qam.py`; **inheriting the mainline's 3,960 is
    forbidden** and the audit asserts the two differ. Frame BLER is recomputed as
    `1-(1-bler_cw)^N_CW^SECOND` from the **committed codeword-BLER column** of
    `results/channel/bler_sionna.csv` — no new Sionna run — into a **new** file; the mainline table
    is not touched. The feasibility mask (`BLER_INFEASIBLE = 0.999`) is re-evaluated and the onset
    (lowest Es/N0 at which frame BLER first falls below it) reported per (modulation, channel).
    - **Pre-registered expectation E3.** A larger `N_CW` can only move an onset **right** or leave
      it unchanged. **If an onset leaves the evaluated [0, 20] dB window, it is reported as such —
      no grid extension, no re-fit, no substitution.** Where the committed table reports a
      codeword BLER as an upper bound (deep-tail points with 0 errors in `MAX_CW`), the derived
      frame BLER is a bound too and is labelled as one rather than printed as a value.
  - **(4) Stop.** The eff-cache / grid-expansion / frozen-walk batch stays unstarted. Nothing in
    `main.tex`, no frozen artefact, no deployed model is touched by this entry.

- **P4-B-d RESULT (2026-08-14) — `B_F^SECOND` fixed on the declared convention; both pre-registered
  expectations met, and the paper's insensitivity claim is now measured rather than asserted — and
  as literally worded it does not hold.**
  - **E1 met. `B_F^SECOND = 3.09375 Msym/frame`** (16-QAM, rate-1/2). Chain, every link derived:
    6,758,400 pre-compression elements/CAV × **0.915527** bit/element (= 1.98 Mbit ÷ 2,162,688, the
    declared pair) = **6.1875 Mbit** info → 12.375 Mbit coded → ÷4 → **3.09375 Msym**.
    `N_CW^SECOND = ceil(6,187,500 / 500) = 12,375`. Budgets
    `B_max^SECOND = 0.309375 / 0.61875 / 0.928125 Msym` at 10/20/30 %.
    Peiyi's quoted ≈6.22 Mbit → ≈3.11 Msym is the same chain with bits/element rounded to 0.92; the
    gap is **0.4885 %**, inside the pre-registered 1 % stop. Audited as `tests/test_payload.py`
    section (5), **25/25 links match**.
  - **E2 confirmed, exactly as pre-registered.** `AttBEVBackbone` compresses branch `idx` only while
    `compression - idx > 0`:

    | backbone | branches | pre-compression /CAV | transmitted /CAV | note |
    |---|---|---|---|---|
    | PointPillar (mainline) | 3 (2 compressed) | 2,252,800 + 1,126,400 + 563,200 = **3,942,400** | 35,200 + 140,800 + **563,200** = 739,200 | branch 2 is **NOT compressed** and is 76.2 % of everything it sends |
    | SECOND | 2 (both compressed) | 4,505,600 + 2,252,800 = **6,758,400** | 70,400 + 281,600 = **352,000** | |

    **The two backbones invert under the two conventions**: SECOND's pre-compression tensor is
    1.71× the mainline's, but its transmitted bottleneck is 0.48× — so which backbone is "cheaper"
    is decided entirely by the accounting choice, not by the model. That is the concrete reason a
    bottleneck-based `B_F^SECOND` was the wrong call.
  - **The declared anchor does not describe the deployed model.** `main.tex` anchors the budget to a
    "$256\times48\times176 \approx 2.16\times10^{6}$" tensor, which is the **JSCC baseline's**
    geometry (y ∈ [-38.4, 38.4] m, stride 4, 256 ch). The deployed
    `pointpillar_attentive_fusion_compression` checkpoint has y ∈ [-40, 40] m and a three-branch
    pyramid totalling **3,942,400** pre-compression elements — **1.8229×** the declared anchor.
    Reported, not reconciled, per the pre-registration.
  - **"Conclusions are insensitive to this constant" — measured, and false as written.** The paper
    says re-anchoring "would rescale the feature cost of all policies equally". It does not: a
    deployed policy pays `ρ_L·B_L + ρ_F·B_F`, and `B_L` is anchored **independently**, so only the
    pure-F term rescales. Using the frozen decision logs' own action mix, the headline quantity
    (CA-TOSG channel use as a fraction of Fixed-F) moves by **−0.90 % to −7.75 %** under the paper's
    own named counterfactual (1.98 → 2.16 Mbit) and by **−4.86 % to −41.99 %** under the
    declared→deployed re-anchor, worst on Culver at B_max = 0.10. The *ordering* survives; the
    *fraction* does not. `results/channel/payload_anchor_sensitivity.csv`.
  - **E3 met. Frame BLER and mask re-derived at `N_CW = 12,375`,** from the committed `bler_cw`
    column — no new Sionna run, the mainline table untouched. Sanity: the committed `bler_frame`
    column is reproduced from `bler_cw` at `N_CW = 3,960` to **2.1e-15**, which is what licenses
    re-deriving it at the new count. Onsets (frame BLER first < 0.999):

    | channel | QAM | onset @3,960 | onset @12,375 | move |
    |---|---|---|---|---|
    | AWGN | 16 | 8.0 dB | **8.0 dB** | unchanged |
    | AWGN | 256 | 16.5 dB | **17.0 dB** | +0.5 dB |
    | Rayleigh | 16 / 256 | none in table | none in table | unchanged — the frame BLER never falls below the mask threshold at either count |

    No onset left the evaluated [0, 20] dB window, and no onset landed on a point whose codeword
    BLER is only an upper bound. Outputs: `results/channel/bler_frame_second.csv`,
    `bler_onset_second.csv`, `payload_conventions.csv`, `payload_anchor_sensitivity.csv`.
  - **Two audit defects found and fixed en route.** (i) `tests/test_payload.py`'s Eq.(7) `C16`
    pattern stopped matching when P5 batch 2 renamed `C_{16}` → `F`, so that link had been
    **silently dropped** from the audit rather than failing; both spellings are now accepted and the
    link is back (24 → 25 links). (ii) The frozen decision logs store the action as the **label**
    `'E'/'L'/'F'`, not an index; comparing against `0/1/2` returned all-zero shares silently. The
    label set is now asserted, so a future encoding change fails loudly.
  - **Stop.** No eff cache, no grid expansion, no frozen walk; `main.tex` untouched by this entry;
    the mainline BLER table, the frozen selectors and every deployed artefact unchanged.

- **P5-4 (2026-08-14) — migration batch 3, part 1: the legacy-engine inventory. `main.tex` NOT
  edited, not one character; no result regenerated, no figure rebuilt, no ledger cell changed.**
  Batch 2 left `sec:difficulty` standing as "the" remaining legacy subsection. Before editing it,
  the whole paper was swept for the same defect, mechanically rather than from memory.
  - **New tool `tools/audit_claims_evidence.py`.** Re-walks `main.tex` with the ledger generator's
    own sentence splitter while tracking `\section`/`\subsection` headers (the ledger is flat and has
    no section column), joins the result to `docs/claims.md` and to `results/README.md`, and
    classifies each claim's evidence by the **generator's intra-repo import closure** — so
    `LEGACY-ENGINE` is *derived* from what the code reads, never asserted. Rows whose ledger cell is
    blank are attributed by searching every committed result file for the claim's distinctive
    numeric literals, ranked by literals-matched and then by file size (a 20-row verifier CSV
    matching 3/3 is evidence; a 200k-value replay dump matching 3/3 is mostly chance). Output:
    `docs/claims_evidence_audit.md`, regenerable, with `--check` for staleness.
  - **Three classifier defects were found and fixed while building it, each of which would have
    produced a wrong verdict silently:** (i) marker matching over raw source text tagged
    `end_to_end_ap.py` LEGACY because a *docstring* says "identical to true_e2e_global.py" — now
    matched against module names and non-docstring string literals only (`ast.get_docstring(...,
    clean=False)`, since the cleaned form does not compare equal to the raw constant); (ii) a memo
    on the import closure returned a cached set without merging it into the caller's, truncating
    `tools/evaluate_selector.py` to 1 module and mislabelling the **frozen replay generator**
    ANALYTIC — the memo is gone; (iii) `results/README.md` rows whose generator cell contains a
    literal `|` (`--train|--evaluate`) over-split, so the whole `contextual_bandit_runs/` family
    read as "not indexed".
  - **Result: 14 of 107 claims rest on a retired engine, across 10 sections — not 1.** Two were not
    previously known. **`sec:generalisation` carries three claims** scored by the v3 global-sort
    scorer `true_e2e_global.py` (the entire per-SNR AP-knee narrative on test and Culver-City), and
    the `+0.090` hard-frame family survives in **three** places, not one: `main.tex` 662 (prose),
    678 (figure caption) and **904 (the Conclusion)** — batch 2 recorded deleting the Conclusion
    restatement, but the surviving sentence is worded differently and was missed.
  - **"Legacy engine" resolved into three distinct dependencies**, which the rulings must not treat
    alike: **L1** the v3 policy engine / v3 deployed selector (`policy_200seed`, and
    `a2_difficulty.py` → `C.load_rf()` → `data/selector_rf.pkl`); **L2** the v3 global-sort scorer;
    **L3** a self-contained prior-protocol arm that borrows only `v3_eval`'s BLER lookup, its
    `N_SEED = 200` CSI convention and its bootstrap helper, and reads neither the v3 nor the frozen
    selector (the JSCC two-regime comparison).
  - **Per-section rulings are PROPOSED, not applied:** `docs/p5_batch3_legacy_rulings.md`, one of
    recompute / demote-to-appendix / delete per section, each with its compute cost and its
    dependency. Headlines: the `B_L = 0.024` family is engine-independent and needs only
    re-attribution (`tests/test_payload.py (0b)` already re-derives it from the dataset);
    `sec:difficulty`'s **reliable-channel** view is fully recomputable from `data/p2/p2_grid_*.csv`
    + the frozen selectors with no new inference, while its **channel-averaged 200-realisation**
    view must be deleted rather than reproduced; `sec:generalisation` needs a new SNR-pinned variant
    of `end_to_end_ap.py` (the frozen engine draws SNR ~ U[0,20] and has no per-SNR mode at all).
    **Awaiting Peiyi's ruling before any prose moves.**

- **P5-5 (2026-08-14, PRE-REGISTERED before any prose was edited and before any new number was
  produced) — migration batch 4: execute the batch-3 rulings in `main.tex`.**
  Peiyi's rulings on `docs/p5_batch3_legacy_rulings.md` are taken as given. This entry records what
  each item is allowed to change and what would stop it. Frozen selectors, δ, τ\*,
  `FROZEN_MANIFEST.json`, the mainline replay and every committed result CSV stay read-only; new
  products get new files.
  - **(5) `B_L` family — re-attribution only, no number moves.** The four ledger rows citing the v3
    `threshold_vs_rf.csv` are re-pointed at the quantity's real source (the dataset's own
    `late_num_pred` + the ETSI-CPM container size), which `tests/test_payload.py (0b)` already
    derives. **`(0b)` stops being skippable**: it currently prints `SKIP` and passes when the
    OpenCOOD runtime dataset is absent, which is precisely the "a gate that cannot verify must never
    report success" failure. It becomes a hard failure in the artefact tier. No prose change.
  - **(6) `sec:headline` re-attribution; `sec:ablation` recomputed from FA-1.** `c1a099a`'s headroom
    is re-pointed at the frozen `true_e2e_ap.csv`. `sec:ablation`'s channel-conditional payload pair
    is recomputed from the frozen FA-1 artefacts. **Expectation E-6: the FA-1 numbers will differ
    from the retired arm's `0.240 / 0.271`** — they are different engines — so the prose changes with
    them. If FA-1 carries no channel-split payload at all, the sentence drops to ruling (c) and is
    deleted rather than approximated.
  - **(7) `sec:difficulty` / `sec:harm` / Conclusion.** The **reliable-channel conditional** view is
    recomputed under the frozen protocol: difficulty = tertiles of the frame's own object-level
    effective F1 (`eff_L`), conditioned on one (channel, SNR) grid point, with the frozen selectors
    replayed on `data/p2/p2_grid_{split}.csv`. The **channel-averaged 200-realisation** view is
    **deleted, not reproduced** — it is the retired engine's own quantity. `fig_difficulty.pdf` is
    rebuilt in the same batch from the same recomputation, so the figure and the text are never
    momentarily inconsistent. The `+0.090` at `main.tex` 904 (the family's third site) goes.
    **Expectation E-7: the recomputed hard-frame gain will NOT be +0.090.** Whatever it is, is what
    is printed; if the gain does not rise with difficulty at all, that is the result and the
    subsection is rewritten to say so rather than dropped.
  - **(8) `sec:generalisation` — a reproduction gate BEFORE any new number.** A new SNR-pinned
    variant of the frozen `end_to_end_ap.py` is written with the SNR draw as the *only* difference.
    **Expectation E-8, and the batch's hardest stop: run in its `uniform` mode the variant must
    reproduce every committed row of `results/main/true_e2e_ap.csv` exactly.** Until that passes,
    **no pinned-SNR number may be produced, quoted or written into `main.tex`.** If it fails, the
    variant is wrong and `sec:generalisation` falls back to ruling (b) — appendix, labelled
    prior-protocol. Scope (splits, channels, budgets) is fixed by a **measured** per-condition cost
    and whatever is not covered is stated in the prose, never silently dropped.
  - **(9) `sec:jscc_aware` → appendix**, with an explicit sentence marking it a prior-protocol arm
    (its own selector, `v3_eval`'s BLER lookup and 200-seed CSI convention, neither the v3 nor the
    frozen selector). No number changes.
  - **(10) Ledger back-fill, LAST.** Only after every prose edit lands, so no cell is written against
    a number that then moves. `docs/claims.md` is regenerated and the STALE / blank / dangling counts
    are reported as they come out.
  - **(11) Push, then stop for verification.**

- **P5-5 RESULT (2026-08-14) — migration batch 4 executed. `main.tex` edited. Both pre-registered
  expectations that could fail did fail in the predicted direction, and one section's *content*,
  not just its numbers, did not survive the frozen protocol.**
  - **(5) `B_L` family + the skippable gate.** `tests/test_payload.py (0b)` no longer prints `SKIP`
    and passes when the dataset is absent; it records a hard failure. No prose changed. The four
    `B_L` rows were re-attributed by the mechanical back-fill of item 10.
  - **(6) `sec:ablation` — FA-1 *reverses* the retired arm's sentence.** The old text claimed the
    full selector "spends $0.240$ Msym versus $0.271$ for channel state alone". Under FA-1 the
    direction is budget-dependent and at the two tighter budgets it is the other way round: at
    $B_{\max}=0.10/0.20$ channel-only collapses to always-$L$ (payload $0.024$), and only at
    $B_{\max}=0.30$ does it activate $F$ — reaching a **higher** F1 than the full selector
    (0.90944 vs 0.90734 on test) at **1.54×** the channel use (0.28843 vs 0.18703). Rewritten to
    that reading. **Also deleted:** two sentences discussing a cues-plus-$\hat\gamma$ variant
    ("the same $0.07\!\to\!0.16$ request share on every channel") that the table's own caption says
    "was not re-run under the corrected protocol and is therefore not listed" — prose was still
    analysing a variant that no longer exists.
  - **(7) `sec:difficulty` / `sec:harm` / Conclusion — E-7 confirmed, and the effect is 2.3× smaller
    than published.** Recomputed from `data/p2/p2_grid_{split}.csv` + the frozen selectors at AWGN
    16 dB, $B_{\max}=0.20$ (`difficulty_frozen.py` → `results/sensitivity/difficulty_frozen.csv`):
    hard-frame gain **+0.0400** (95% CI [+0.0339, +0.0465]) on test, not +0.090; validate +0.0402;
    **Culver +0.0136**, not +0.106. The shape survives (gain rises monotonically with difficulty);
    the magnitude does not. `sec:harm`'s easy-stratum footnote: **−0.0040** [−0.0064, −0.0018], not
    −0.0147 — same stratum, same **n = 713**, same Fixed-$L$ baseline 0.9866, so *only* the
    selector's realised F1 moved, which is exactly the engine difference and nothing else. The
    channel-averaged view is deleted, not reproduced. `fig_difficulty.pdf` rebuilt in the same
    commit from the same CSV (now single-panel — the deleted view was its left panel). `+0.090` is
    gone from all three sites (prose, caption, Conclusion): `grep -c` on `main.tex` returns **0**.
    The `sec:harm` footnote edit is declared to the paragraph-insertion gate as ruling **P5-5-7**
    rather than absorbed silently; that gate caught the edit and now passes with the ruling recorded.
  - **(8) `sec:generalisation` — E-8 gate PASSED, and then the section's story did not survive.**
    `end_to_end_ap_snr.py --verify` reproduced **27/27** committed rows of `true_e2e_ap.csv`
    exactly, which is what licensed producing any pinned number. Coverage produced: test +
    Culver-City × AWGN + Rayleigh × 11 SNR points × all three frozen budgets, 200 paired
    realisations (264 rows). At $B_{\max}=0.20$:
    - the knee is at **10 dB**, not 12–14 dB, and it is a **policy** knee, not an AP knee
      ($\rho_F$ 0 → 0.256 test, 0 → 0.064 Culver) sitting exactly where the 16-QAM frame-error
      cliff clears;
    - AP is flat across it and on test slightly **negative**: AP@0.5 0.9189 → 0.9168, AP@0.7
      0.8687 → 0.8636. The published "lifting 0.919 → 0.921" does not reproduce;
    - Culver-City gains **+0.7** AP@0.5 points (0.7828 → 0.7897), not **+7.4**;
    - the "mild non-monotonic dip at the 20 dB training-grid edge" **does not exist** under the
      frozen selector — AP is flat above 10 dB — so that explanation is withdrawn;
    - the flat Rayleigh curve is the one part of the earlier account that reproduces unchanged.
    Both per-SNR tables and the paragraph were rewritten from the frozen data.
    **NOT fixed, out of this batch's scope, needs a ruling:** `tab:true_e2e` in `sec:true_e2e` is
    the *validate* per-SNR table and has the identical provenance defect (v3 scorer). The engine to
    redo it now exists; validate was deliberately not re-run because the ruling covered
    `sec:generalisation`.
  - **(9) `sec:jscc_aware` → Appendix A**, with a protocol note marking it a prior-protocol arm
    whose selector is neither the frozen nor the retired one. 107 lines moved under `\appendices`;
    8 `Section~\ref` cross-references rewritten to `Appendix~\ref`. No number changed.
  - **(10) Ledger, last.** `docs/claims.md`: **108 rows** (11 claims removed and 12 added by this
    batch's edits), **0 STALE**, **39 filled / 69 pending**, 0 dangling. The mechanical back-fill
    (`tools/backfill_claims_evidence.py`) writes only `CSV` and `Generator`, and only where every
    distinctive literal of a claim is carried by one committed file resolving to one generator:
    22 rows newly filled, **14 left blank as partial matches** and **55 as unlocated**, because a
    2-of-4 literal hit is a hint, not an attribution. **Defect found while doing it:** a generator
    command containing a literal `|` (`--train|--evaluate`) breaks the row's 9-cell parse, and the
    ledger generator *silently drops* an unparseable row's evidence on the next rebuild — the cell
    reads as filled and comes back blank. A backslash escape does not help (the parser does a plain
    `str.split('|')`); the entity `&#124;` does.
  - **Not verified here:** there is no LaTeX toolchain on this host, so `main.tex` has **not been
    compiled**. The appendix move, the `\appendices` placement and the table rewrites are checked by
    the repository's three main.tex gates only.

- **P5-6 (2026-08-14) — migration batch 5: the cross-section contradictions batch 4 left behind.
  No frozen artefact touched.**
  - **(1) `tab:true_e2e` (validate per-SNR) rebuilt on the frozen engine.** The E-8 reproduction
    gate was re-run on the *current* code first — `end_to_end_ap_snr.py --verify` again reproduced
    **27/27** committed rows of `true_e2e_ap.csv` exactly — before any validate number was produced.
    Coverage is now all three splits × AWGN + Rayleigh × 11 SNR points × three budgets
    (`true_e2e_ap_by_snr.csv`, 396 rows).
  - **(2) The regime boundary is now derived, and the stipulated `≥14 dB` is gone.** Reading the
    frozen selector's `ρ_F` off the pre-registered grid at `B_max=0.20`, AWGN: `ρ_F = 0` at every
    point up to 8 dB and steps to its plateau at **10 dB on all three splits** — **0.286** validate,
    **0.256** test, **0.064** Culver-City — which is exactly where the 16-QAM frame-error cliff
    clears. Validate shows a **0.4 % toe at 8 dB**, the one grid point where the frame BLER is
    neither ≈0 nor ≈1 (0.402); it is reported, not smoothed away. `≥14 dB` was never derived from a
    measurement and is withdrawn; the only surviving mention is the sentence recording the
    withdrawal.
    **This exposed a third stale table.** `tab:headline`'s feature-active rows were v3-scored too,
    and its payload column was badly wrong because the retired selector requested `F` far more
    often. Rebuilt from the frozen engine (mean over the six grid points at and above the knee;
    payload = `ρ_L·B_L + ρ_F·B_F` from Eq.(7)):
    | split | AP@0.5 | AP@0.7 | payload (Msym) |
    |---|---|---|---|
    | validate | 0.916 → **0.9140** | 0.857 → **0.8534** | 0.632 → **0.300** |
    | test | 0.920 → **0.9169** | 0.865 → **0.8637** | 0.874 → **0.283** |
    | Culver-City | 0.855 → **0.7901** | 0.754 → **0.7020** | 0.565 → **0.089** |
    The fallback (`L`) rows already matched the frozen data to 3 dp — they are deterministic
    Fixed-`L`, so nothing there depended on the engine. Two claims in §true_e2e were also overstated
    and are now corrected: the selector recovers only *part* of the perfect-channel reference on
    validate (0.9140 vs 0.917), not "essentially all of the benefit".
  - **(3) Action-context `C_{16}` cleared from every caption and table title** — 5 rewrites:
    `fig:overview` (`s_t ∈ {L,F}`), `tab:headline` ("requests `F`"), `tab:headline_agg`
    (`B_F = 0.990`), `fig:payload_snr` (the L457 one named in the ruling), `fig:decision_ratio`
    (action set + legend). `tab:notation` keeps `C_{16}` — it is the glossary that *defines*
    `F ≡ C_{16}`. 16 `C_{16}` remain in the file, all prose in modulation or `C_{16}`-vs-`C_{256}`
    comparison context. **Two prose borderlines flagged, not edited** (outside the ruling's
    caption/table-title scope): line 117 "the instance evaluated here uses two ($L$ and $C_{16}$)"
    and line 246 "if $s_t=C_{16}$" are action-context but sit in prose.
  - **(4) Ledger parsing hardened — this was a gate-level hazard, now closed at both ends.**
    `parse_existing` **aborts** on any row that does not split into exactly 9 cells, naming the line
    and cell count, instead of `continue`-ing past it; a new `assert_round_trips` refuses to *write*
    a ledger containing such a row. The writer (`clean_claim`, `exact_values`, and the back-fill
    tool) now emits `&#124;` for a literal pipe: a backslash escape does **not** work because the
    parser does a plain `str.split('|')`. Verified by negative test: injecting a raw `|` into one
    Generator cell makes the run exit 1 with `line 9: 10 cells: ...`, and the ledger is restored
    byte-identical afterwards.
  - **Ledger after this batch:** 109 rows, **0 STALE**, **47 filled / 62 pending**, 0 dangling
    (9 newly back-filled; 7 partial and 55 unlocated deliberately left blank).
  - **Still not verified:** no LaTeX toolchain on this host, so `main.tex` has **not been compiled**.

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

Operationalises the §8 anti-forcing clause for the P3 batch (Change-log P3). **SNR support (erratum P3-1): every P3 item draws SNR from the 11-point pre-registered grid of §3, not from the continuum — `uniform` is 1/11 per point, and Beta(2,5)×20 and trunc-N(10,5) are binned onto the grid at the midpoints (±1 dB, clipped) and normalised; the exact probabilities are written into `results/provenance/PROVENANCE_p3.txt` on every run.** Each row is a
**falsifiable prediction**; the *Observed* column is descriptive, read from the committed CSVs in
`results/sensitivity/` (baseline reproduces `replay_summary.csv` exactly, `baseline_sanity.csv`);
a miss is **reported, not fixed**. Anchor numbers below are test @ B_max=0.20, RF.

| Item | Condition | Pre-registered expectation | Observed (descriptive) | Check |
|---|---|---|---|---|
| 1 | channel ratio (`channel_ratio.csv`) | more Rayleigh → feature-selection rate + payload ↓ toward B_L, F1 → Fixed-L | ρ_F 0.109→0.072→0.037 and payload 0.130→0.094→0.059 as AWGN:Rayleigh goes 75/25→50/50→25/75; F1 0.9065→0.9047→0.9029 | met |
| 2 | non-uniform SNR (`nonuniform_snr.csv`) | low-skew shifts toward L (payload↓, F1→Fixed-L); trunc-Gaussian intermediate | Beta(2,5): ρ_F 0.021, payload 0.045, F1 0.9022 (sharp drop); N(10,5): ρ_F 0.077, payload 0.099, F1 0.9049 (≈uniform) | met |
| 3 | channel-type flip (`channel_misclassification.csv`) | graceful F1 degradation with p; fallback keeps L safe | F1 0.9047→0.9041→0.9035→0.9024 for p=0/.05/.10/.20; payload ~flat (0.0940) | met |
| 3-var | labelled variants (`item3_variants.csv`, validate-only, NOT deployed) | cues + a channel signal needed; a monotone re-encoding ≈ binary | snr_only collapses to L (ρ_F=0, payload 0.024); cont_obs (delay/Doppler map) ≈ full_ref (F1 0.9122 vs 0.9122) | met |
| 4 | BLER_L grid (`object_message_bler.csv`) | small monotone F1 drop where L selected; payload unchanged | F1 0.9047→0.9040→0.9009→0.8971 for BLER_L=0/.01/.05/.10; payload 0.0940 flat | met |
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

## Appendix C — P4-A internal learned-policy comparator (Change-log P4-A)

**"internal learned-policy comparator, not deployed."** A contextual-bandit RL selector (`train.py`,
`evaluate.py`) trained to the matched protocol, compared to the deployed RF and the τ rule.
Frozen CA-TOSG models / δ / τ\* / oracle / mainline replay unchanged; `main.tex` untouched. Manifest
`results/manifests/P4A_MANIFEST.json` (3 bandit sha256 / hyperparams / seed / per-budget frozen payload).
Sanity: the eval's `F1_RF` / `B_RF` reproduce `replay_summary.csv` exactly (0 mismatches).

**Selection outcome (validate LOSO, `p4a_loso_oof.csv` / `p4a_walk.csv`; RE-RUN under erratum P4A-1).**
Ordered by frame-weighted OOF F1 the best λ is **λ\*=0.05** (OOF F1 0.90644, OOF payload
0.03591); it is feasible for all three budgets, so the walk freezes it at depth 0 for
**every** B_max and the three budgets share one policy (frozen validate F1 0.90911, payload
0.05146). The OOF surface is nearly flat in λ (0.90177–0.90644
over the seven values); the sharp λ=0.05 collapse to 0.872 reported before the erratum was an artefact of
the standardisation leak, not a property of the objective. (The three per-budget model files carry
different sha256 — the same policy re-trained per budget; GPU training is not bit-reproducible, a recorded
limitation of this comparator. Their frozen F1/payload are identical.)

**Comparison (descriptive, paired bootstrap CI only — NO new decision; `contextual_bandit.csv`).**
Anchors test @ B_max=0.20: RL F1 0.9010 / payload 0.1557; RF 0.9046 / 0.0947;
τ 0.9074 / 0.2168.
- **RL-vs-RF: RL is below RF on F1 in every split × budget cell**, CI entirely < 0 in all 9
  (test B020 ΔF CI [-0.0037, -0.0035]; ΔF means range
  -0.00198 … -0.02352). Same direction as before the
  erratum; the magnitudes roughly halved on validate and test.
- **RL-vs-τ: the previous blanket claim does NOT survive the re-run.** RL is now *above* τ on
  **validate** at B_max=0.10 (ΔF CI [+0.0017, +0.0018])
  and at B_max=0.30 (CI [+0.0003, +0.0005]), and below τ
  on test and Culver-City at every budget. The claim is therefore narrowed to the held-out splits:
  **on data it did not see, the learned policy beats neither the RF nor the τ rule.**
- **Budget compliance does not transfer (new; reported, not fixed).** The frozen payload meets the
  budget on validate (0.05146 ≤ 0.10) but the same policy spends 0.1557
  Msym/frame on test — **above B_max = 0.10** — where the RF stays at 0.0680. Feasibility is a
  validate-side check by construction (§6); the RF's compliance happens to transfer, this comparator's
  does not.

**Positioning (what this comparator is and is not evidence for).** After the P4A-1 fix the three
budgets all select the SAME conservative policy — λ\*=0.05 at walk depth 0 for every B_max — so
B_max is not actually binding on it; there is one learned policy, reported three times. On the
held-out splits it is **not better than the deployed RF**: F1 below RF in every test and Culver-City
cell, CI entirely < 0. And its budget compliance does not transfer: at B_max = 0.10 it spends
0.156 Msym/frame on test — **above the 0.10 average budget it was frozen
under** — where the RF stays at 0.068 and complies.

This is therefore an **internal diagnostic result, not primary evidence of any advantage of the
deployed method**. It says something narrow and useful: on this problem, a reward-trained bandit
over the same features, the same substrate and the same protocol converges to a near-object-level
policy and does not recover the RF's channel-aware F-selection. It is not a published baseline, it
is not tuned as an opponent would tune it, and it must not be cited as showing that CA-TOSG beats
reinforcement learning.

**In-distribution record, kept for completeness.** On **validate** — the split it was fitted on, so
in-sample and not a generalisation claim — it does edge past the τ rule at two operating points:
B_max=0.10 ΔF CI [+0.0017, +0.0018] and B_max=0.30
CI [+0.0003, +0.0005], both excluding 0. Recorded
because it is what the numbers say; it carries no weight against test/Culver, where it is below τ
at every budget.

**§8 anti-forcing.** Pre-registered expectation was that RL and RF land in the same F1/payload
neighbourhood. Observed: same F1 band on validate, below RF everywhere, drifting further below on
test/Culver, and over budget on test. Reported as found — a negative comparison, and the erratum
re-run did not overturn it.

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

## Appendix E — feature ablation variants (Change-log FA-1, pre-registered)

The variant definition is machine-readable and is parsed by
`projects/ca_tosg/evaluation/feature_ablation.py`; nothing about the variants is hard-coded there.
`base_feature_names` is read from `FROZEN_MANIFEST.json`, so the ablation cannot silently drift
from the deployed feature vector.

```json CATOSG-FEATURE-ABLATION
{
  "seed_source": "CATOSG-CANDIDATES.seed",
  "candidates_source": "CATOSG-CANDIDATES",
  "base_feature_names": "FROZEN_MANIFEST.json:feature_names",
  "channel_features": ["est_snr_db", "channel_is_rayleigh"],
  "variants": {
    "channel_only": {"keep": "channel_features", "train": true},
    "task_only": {"keep": "complement_of_channel_features", "train": true},
    "combined": {"keep": "all", "train": false, "reference": "FROZEN_MANIFEST.json"}
  },
  "pipeline": "identical_to_mainline: validate grid, scene-level 9-fold LOSO, 112 candidates, frame-weighted OOF feasibility, frozen walk with Bbar_frozen <= B_max, one model per B_max",
  "label": "labeled variant, not deployed",
  "evaluation": "same 200 paired CSI draws (CSI_SEED), 3 splits, descriptive + paired bootstrap CI only",
  "manifest": "results/manifests/FEATURE_ABLATION_MANIFEST.json"
}
```

**Status: RUN 2026-08-13.** Results `results/sensitivity/feature_ablation.csv`, provenance
`results/provenance/PROVENANCE_fa.txt`, variant models `results/manifests/FEATURE_ABLATION_MANIFEST.json` (kept apart from `FROZEN_MANIFEST.json`, which this run did not
touch). Table below is the **test** split; all three splits are in the CSV. ρ = action share.

| B_max | variant | F1 | payload | ρ_E / ρ_L / ρ_F | ΔF1 vs combined [95% CI] |
|---|---|---|---|---|---|
| 0.10 | `channel_only` | 0.90113 | 0.02400 | 0.000 / 1.000 / 0.000 | -0.00213 [-0.0022, -0.0020] |
| 0.10 | `task_only` | 0.90113 | 0.02400 | 0.000 / 1.000 / 0.000 | -0.00213 [-0.0022, -0.0020] |
| 0.10 | **combined** (deployed) | 0.90326 | 0.06798 | 0.005 / 0.950 / 0.046 | — |
| 0.10 | τ (reference) | 0.90271 | 0.07240 | 0.000 / 0.950 / 0.050 | -0.00055 [-0.0006, -0.0005] |
| 0.20 | `channel_only` | 0.90113 | 0.02400 | 0.000 / 1.000 / 0.000 | -0.00349 [-0.0036, -0.0034] |
| 0.20 | `task_only` | 0.90113 | 0.02400 | 0.000 / 1.000 / 0.000 | -0.00349 [-0.0036, -0.0034] |
| 0.20 | **combined** (deployed) | 0.90463 | 0.09472 | 0.001 / 0.926 / 0.073 | — |
| 0.20 | τ (reference) | 0.90740 | 0.21679 | 0.000 / 0.800 / 0.200 | +0.00277 [+0.0027, +0.0029] |
| 0.30 | `channel_only` | 0.90944 | 0.28843 | 0.000 / 0.726 / 0.274 | +0.00209 [+0.0020, +0.0022] |
| 0.30 | `task_only` | 0.90113 | 0.02400 | 0.000 / 1.000 / 0.000 | -0.00621 [-0.0063, -0.0061] |
| 0.30 | **combined** (deployed) | 0.90734 | 0.18703 | 0.001 / 0.830 / 0.169 | — |
| 0.30 | τ (reference) | 0.90937 | 0.31250 | 0.000 / 0.701 / 0.299 | +0.00203 [+0.0020, +0.0021] |

**Frozen variants** (validate, one model per budget, hard check `B̄_frozen ≤ B_max` passed in
all six cases):

| variant | B_max | λ\* | walk depth | frozen validate F1 | frozen validate payload |
|---|---|---|---|---|---|
| `channel_only` | 0.10 | 0.0 | 0 | 0.90670 | 0.02400 |
| `channel_only` | 0.20 | 0.0 | 0 | 0.90670 | 0.02400 |
| `channel_only` | 0.30 | 0.1 | 0 | 0.91020 | 0.28746 |
| `task_only` | 0.10 | 0.0 | 0 | 0.90710 | 0.02376 |
| `task_only` | 0.20 | 0.0 | 0 | 0.90710 | 0.02376 |
| `task_only` | 0.30 | 0.0 | 0 | 0.90710 | 0.02376 |

### Against the pre-registered expectations (§8: checks, not targets)

**Expectation 2 — `task_only` collapses conservative: MET, and harder than predicted.** It selects
λ\*=0.0 at *all three* budgets and never requests F at all: ρ_F = 0.000 in every split × budget cell,
payload pinned at B_L. It sits exactly on the Fixed-L F1 floor (test 0.90113). Without a channel
signal the selector does not merely become cautious — it stops using the feature branch entirely, and
B_max stops being binding on it.

**Expectation 1 — `channel_only` ≈ τ: PARTIALLY MET. Met at B_max=0.30, missed at 0.10 and 0.20.**
At 0.30 it is very close to τ: ρ_F 0.274 vs 0.299, F1 0.90944 vs 0.90937 (equal to 4 dp), at 92% of τ's
payload. At 0.10 and 0.20 it does **not** track τ — it collapses to all-L (ρ_F 0.000, payload 0.02400)
while τ still requests F (ρ_F 0.050 and 0.200). Mechanism, stated rather than smoothed over: τ\* is
**budget-matched by construction** on the validate grid, whereas the ablation picks λ by OOF F1 among
the budget-feasible candidates — the higher-F1 F-requesting candidate (index 10, λ=0.1, OOF payload
≈0.29) is infeasible at 0.10/0.20 and only enters the walk at 0.30. Reported as a partial miss.

**Neither half alone reproduces the combined operating points.** The deployed 23-feature model is the
only policy here that reaches an *intermediate* payload (test 0.06798 / 0.09472 / 0.18703 across the three
budgets). Both ablations are bimodal: all-L, or — for `channel_only` at 0.30 — τ-like heavy F. The two
feature groups are jointly necessary to obtain a *graded* policy, which is the ablation's actual finding.

**Counter-observation, reported not buried.** At B_max=0.30 on test, `channel_only` has HIGHER F1 than
the deployed model: 0.90944 vs 0.90734, CI [+0.0020, +0.0022], at 0.29 vs 0.19 payload (1.54×). τ shows the same
pattern. So "the combined model wins on F1" is **false at the loosest budget** — its advantage is
payload at comparable F1, not F1 at comparable payload, and the table is left showing that.

**Surfaced by the `over_budget` column (not a new measurement).** τ's realised replay payload exceeds
B_max at 0.20 and 0.30 on all three splits (test 0.21679 > 0.20, 0.31250 > 0.30). τ\* is chosen on the
deterministic validate grid, while the replay draws SNR continuously, so the grid-side guarantee does
not transfer. These payloads are bit-identical to the already-committed `results/main/replay_summary.csv`
— the flag only makes the property visible. The trained variants and the deployed models are all within
budget on every split.

**No decision is taken from any of this.** Descriptive + paired CI only; the confirmatory primary was
spent once at R9. Every trained product is "labeled variant, not deployed".

## Appendix F — P4-C collaborator scale, semantics A (Change-log P4-C)

**Status: RUN 2026-08-13, semantics A (all-or-nothing) on all three splits. Semantics B (the
validate-only partial-fusion bracket) is pre-registered but NOT yet run** — see the change-log.
Results `results/sensitivity/collaborator_scale.csv`, provenance `PROVENANCE_p4c.txt`, arm caches
`results/manifests/P4C_MANIFEST.json`. The deployed selectors were READ, never rewritten.

The selector's features carry nothing about N, so its per-frame **action is N-independent**;
what N changes is what an action costs and what it delivers.

| split | B_max | N | F1 | payload | ρ_F | over budget | ΔF1 vs N=1 [95% CI] |
|---|---|---|---|---|---|---|---|
| validate | 0.10 | 1 | 0.85914 | 0.06857 | 0.046 | no | — |
| validate | 0.10 | 2 | 0.89330 | 0.10748 | 0.046 | **yes** | +0.03417 [+0.0341, +0.0342] |
| validate | 0.10 | 3 | 0.89955 | 0.13283 | 0.046 | **yes** | +0.04042 [+0.0404, +0.0404] |
| validate | 0.20 | 1 | 0.86112 | 0.09986 | 0.079 | no | — |
| validate | 0.20 | 2 | 0.89395 | 0.16517 | 0.079 | no | +0.03283 [+0.0328, +0.0329] |
| validate | 0.20 | 3 | 0.90050 | 0.21509 | 0.079 | **yes** | +0.03938 [+0.0394, +0.0394] |
| validate | 0.30 | 1 | 0.86357 | 0.15781 | 0.139 | no | — |
| validate | 0.30 | 2 | 0.89577 | 0.26557 | 0.139 | no | +0.03220 [+0.0321, +0.0322] |
| validate | 0.30 | 3 | 0.90238 | 0.34957 | 0.139 | **yes** | +0.03880 [+0.0388, +0.0389] |
| test | 0.10 | 1 | 0.89304 | 0.06666 | 0.046 | no | — |
| test | 0.10 | 2 | 0.90262 | 0.08935 | 0.046 | no | +0.00958 [+0.0096, +0.0096] |
| test | 0.10 | 3 | 0.90343 | 0.09174 | 0.046 | no | +0.01039 [+0.0104, +0.0104] |
| test | 0.20 | 1 | 0.89429 | 0.09328 | 0.073 | no | — |
| test | 0.20 | 2 | 0.90395 | 0.12926 | 0.073 | no | +0.00966 [+0.0096, +0.0097] |
| test | 0.20 | 3 | 0.90477 | 0.13433 | 0.073 | no | +0.01048 [+0.0105, +0.0105] |
| test | 0.30 | 1 | 0.89727 | 0.18074 | 0.169 | no | — |
| test | 0.30 | 2 | 0.90658 | 0.27656 | 0.169 | no | +0.00931 [+0.0093, +0.0094] |
| test | 0.30 | 3 | 0.90744 | 0.30129 | 0.169 | **yes** | +0.01017 [+0.0101, +0.0102] |
| culver | 0.10 | 1 | 0.84684 | 0.02518 | 0.004 | no | — |
| culver | 0.10 | 2 | 0.87229 | 0.03456 | 0.004 | no | +0.02545 [+0.0254, +0.0255] |
| culver | 0.10 | 3 *(≡ N=2)* | 0.87229 | 0.03456 | 0.004 | no | +0.02545 [+0.0254, +0.0255] |
| culver | 0.20 | 1 | 0.84816 | 0.02835 | 0.019 | no | — |
| culver | 0.20 | 2 | 0.87355 | 0.03984 | 0.019 | no | +0.02539 [+0.0254, +0.0254] |
| culver | 0.20 | 3 *(≡ N=2)* | 0.87355 | 0.03984 | 0.019 | no | +0.02539 [+0.0254, +0.0254] |
| culver | 0.30 | 1 | 0.85755 | 0.12221 | 0.141 | no | — |
| culver | 0.30 | 2 | 0.88284 | 0.15592 | 0.141 | no | +0.02530 [+0.0253, +0.0253] |
| culver | 0.30 | 3 *(≡ N=2)* | 0.88284 | 0.15592 | 0.141 | no | +0.02530 [+0.0253, +0.0253] |

### Against the pre-registered expectations (§8: checks, not targets)

**Expectation 2 — F1 rises with N, with diminishing returns: MET, and the diminution is steep.**
At B_max=0.20 the second collaborator buys between 5× and 30× less than the first: validate
+0.0328 then +0.0065; test +0.0097 then +0.0008; Culver +0.0254 then +0.0000 (it has no third collaborator).
All ΔF1-vs-N=1 CIs exclude 0.

**Expectation 3 — Culver N=3 ≡ N=2 by construction: MET, and it did its job.** It FIRED on the
first run (F1 identical, payload not) and forced ruling 4 below. This is the invariant catching a
bug in the evaluator, which is what it was written for.

**Expectation 1 — payload scales ≈ linearly in N so the frozen selectors overshoot everywhere:
MISSED, and the pre-registered reasoning was wrong.** Realised scaling at B_max=0.20 is
1.65× / 2.15× on validate, 1.39× / 1.44× on test, 1.41× / 1.41× on Culver — sub-linear, because
**the collaborator supply saturates**: a frame cannot message collaborators it does not have, and
mean availability is 2.90 / 1.59 / 1.09 per split. Overshoot therefore happens in **5 of 27 cells**
(validate B0.10 at N=2 and N=3, validate B0.20 and B0.30 at N=3, test B0.30 at N=3) and **never on
Culver**, not "on every split" as pre-registered.

**The uncomfortable part, recorded rather than tidied away.** The FIRST run — which charged the
nominal N instead of the available collaborators — produced exactly-linear scaling and overshoot in
almost every cell, i.e. it *confirmed* expectation 1. The expectation was confirmed by a bug and
refuted once the bug was fixed. What separated the two was not judgement but the Culver invariant,
which is machine-checkable and was written down before either run.

### Rulings taken during the run (all recorded in PROVENANCE_p4c.txt)

1. **One canonical GT for every N.** Restricting the CAV set also shrinks the post-processor union
   GT; per-N GT would score each arm on a different ruler. The GT is held at the full-set canonical
   union GT — the rule `true_e2e_global.py` already applies across branches.
2. **Delivery (semantics A):** eff_F = comp_N·(1−b)^k + ego·(1−(1−b)^k), reducing to the mainline
   expression at k=1. BLER_L = 0 as in the mainline.
3. **Payload:** one message per collaborator actually addressed.
4. **k_eff = min(N, collaborators in the frame)** — forced by the Culver invariant, see above.

### Cost

The 0.303 s/frame plan estimate was replaced by a 20-frame two-point micro-timing before the sweep
(0.387 s/frame late, 0.359 intermediate, after separating ~10 s of process startup). Realised:
**8818 forwards in 73.5 min**, 0.21–0.71 s/frame — the validate cells are the slow ones because they
carry the most CAVs per frame. The planned late-branch per-CAV re-merge optimisation was **not**
used: with frame filtering, a direct re-run of only the frames whose subset differs (4409) is
cheaper than one full per-CAV pass over all 4700 frames, and it avoids the re-merge verification
risk entirely. Recorded as a plan deviation with its measured justification.

### Semantics B — partial-fusion bracket (validate, N=2; Change-log P4-C-b)

Labelled **"bracketing variant, validate only, N=2, not deployed"**. Scope-reduced by an exact
equivalence: only the **690** validate frames that both request F somewhere on the grid and have
≥2 collaborators can distinguish A from B (E frames send nothing; L frames have BLER_L = 0 so
every message is delivered; a single link cannot deliver "partially"). Verified before running:
the frames that ever choose F in the 200-realisation replay are a subset of the grid-based scope
with **0 frames outside it**. Only the {second-nearest alone} subset was new — {nearest} and
{both} are the cached N=1 and N=2 arms — so the bracket cost **1380 forwards, 11.9 min**, against
the 8070 subsets / 2.7 GPU-hours the original plan carried.

| B_max | A (all-or-nothing) | B (partial fusion) | ΔF1 [95% CI] | payload A / B |
|---|---|---|---|---|
| 0.10 | 0.89330 | 0.89340 | +0.00010 [+0.00009, +0.00010] | 0.10748 / 0.10748 (identical) |
| 0.20 | 0.89395 | 0.89413 | +0.00018 [+0.00017, +0.00019] | 0.16517 / 0.16517 (identical) |
| 0.30 | 0.89577 | 0.89609 | +0.00032 [+0.00031, +0.00034] | 0.26557 / 0.26557 (identical) |

**The bracket is tight, and that is the finding.** B ≥ A everywhere, as the algebra requires (a
partial fusion can only beat the ego-only collapse), and every CI excludes 0 — but the gap is
**+0.0001 to +0.0003 F1**, i.e. the fourth decimal. Choosing the conservative all-or-nothing
reading costs essentially nothing at N=2, so the delivery-semantics ambiguity that blocked the run
is **immaterial at this operating point** rather than a live degree of freedom.

**Why it is so small, mechanically:** the partial-delivery mass is 2·b(1−b) per frame, and the
selector requests F almost only where the channel is good (small b). The frames that could benefit
are exactly the frames where the benefit is least likely to be needed.

**Payload is identical under A and B by construction** — channel use is charged when the request is
made, not when it lands, so a failed link is not refunded. The CSV shows the two payload columns
agreeing to all printed digits, which is a check on the implementation rather than a result.

**Not run:** B at N=3, and B on test/Culver. Neither is needed to read the A column now that the
bracket is known to be this tight at N=2, and neither was pre-registered.
