# CA-TOSG — FROZEN EXPERIMENTAL PROTOCOL (P1.5)

**Status:** frozen protocol contract for the P2 rebuild. This file fixes the evaluation
protocol *before* any number is regenerated. It does **not** report results — every number
below is either a protocol parameter (an input we choose) or a payload constant derived from
the rate/modulation chain and cited to its generator. Reported results live in `results/` and
are indexed by `CLAIMS.md`.

**Authority.** This file **defines the experiment's intent**: the protocol, the candidate set, and
the selection rules are specified here and nowhere else. If a generator (training/eval script)
disagrees with this file, that is a **code bug** — stop immediately and fix the code to match the
protocol; do not "reconcile" by editing the protocol to match the code. Where a value is derivable,
this file cites the script that derives it rather than restating a literal (e.g. payload constants →
`code/payload_audit.py`, which re-derives them from first principles and bit-compares against
`main.tex`); a citation is a pointer to a derivation, not a delegation of authority.

---

## 1. Split roles (HARD bans)

Four data partitions, three distinct roles. The bans are **hard**: a violation is a protocol
breach, not a judgement call, and `code/p2_dataprep/check_leakage.py` is the resident gate that
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
scene-dir order; reconstructed by `code/p2_dataprep/_scene_map.py`, asserted to sum to the dataset
length, and independently
cross-checked by `check_leakage.py` against an independent loader-order scene manifest
(`export_scene_manifest.py`, a different code path)). Model/hyper-parameter and λ
selection use **scene-level 9-fold LOSO** over these 9 scenes rather than a single 70/30 dev split
(Change-log R1): a single split leaves the dev set at only 2 scenes, whose F1 is too high-variance
to select on.

## 3. Channel grid

- **SNR grid:** {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20} dB (11 points), read as Es/N0, identical
  axis to the BLER table and to `code/true_e2e_global.py`.
- **Channels:** {AWGN, Rayleigh}.
- **P2 training substrate** = the full deterministic product **frame × 11 SNR × 2 channel**
  (uniform over grid cells), built by `code/p2_dataprep/expand_grid_clean.py`. This is a dense, deterministic
  expansion — NOT the per-frame single random draw frozen into `dataset_*_v3.csv`, and NOT the
  200-realisation Monte-Carlo deployment eval.
- **BLER source:** Sionna 5G-LDPC (k=500, n=1000) rate-1/2 + 16/256-QAM frame-level table
  `results/bler_sionna/bler_sionna.csv` (`bler_frame` column). Rayleigh frame BLER = 1 across
  0–20 dB (direct table lookup, no numerical averaging).
- **Deployment eval distribution** (reported policy numbers, separate from the training substrate):
  per-frame SNR ~ U[0,20] dB × channel ~ Bernoulli(0.5 Rayleigh), 200 realisations, produced by the
  **P2-B new deployment script (to be built)** reading only `FROZEN_MANIFEST.json` (the legacy
  `recompute_policy_200seed.py` is fused off). The two distributions must not be conflated.

## 4. Action set S = {E, L, F}

| Action | Meaning | Channel-use cost | BLER | Source of the cost |
|---|---|---|---|---|
| **E** | ego-only (no message) | B_E = 0 | n/a (always delivered) | by definition |
| **L** | object-level message | B_L = 0.024 Msym | BLER_L = 0 (mainline: assumed reliably delivered) | `code/payload_audit.py` link (0.024 Mbit info, rate-1/2 QPSK ≈1 b/ch-use) |
| **F** | feature-level message | B_F = 0.99 Msym | BLER_F(SNR, channel) from the Sionna table | `code/payload_audit.py` link (1.98 Mbit info → /0.5 LDPC → 3.96 Mbit → /4 for 16-QAM) |

- **Main experiment transports F with rate-1/2 LDPC + 16-QAM.**
- **Effective utility** per cell: `eff_E = ego_f1`; `eff_L = late_f1` (BLER_L = 0 mainline);
  `eff_F = compressed_f1·(1 − BLER_F) + ego_f1·BLER_F` (ego-only failure fallback).
- **Oracle label** = argmax over {E, L, F} of the effective utility, computed on a **feasibility-
  masked** utility vector: where BLER_F ≥ 0.999 (certain failure), F's oracle target is set to
  −∞ so an undeliverable feature request can never be labelled (it would spend channel-use for zero
  information; masking, not preference — same semantics as `make_dataset.py`, Change-log R2). The
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
  BLER model* (`analysis_tools/build_bler_sionna_ofdm.py`: N_FFT=64, N_SC=52 data subcarriers,
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

**Candidate set — SINGLE SOURCE OF TRUTH.** `code/p2_dataprep/train_p2_loso.py` **parses the JSON
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
is written to `results/p2_dataprep/validate_loso_folds.csv`, so both aggregates below are recomputable
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
candidate index; (3) write this order to `results/p2_dataprep/candidate_walk_B0XX.csv` **before any
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
`code/p2_dataprep/check_leakage.py` asserts: (1) every budget's `frozen_validate_payload ≤ B_max`;
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
PROTOCOL.md". All revisions are pre-registered in the **Change-log** at the foot of this file, each
with a reason and a date, *before* any P2 training.

## 8. Post-P2 anomaly review — expectations + handling rules

After P2 regenerates the numbers, run the full anomaly checklist (`P2 submit-B step f`) and produce
a report. Every item below is an **expectation to test, not a target to hit**.

Expectations (each must hold on the regenerated results, else halt — see handling rules):
- **Provenance / plumbing (original checklist):** every reported number resolves to a regenerated
  source CSV + generator (CLAIMS.md rows closed); no v1/v2/v3/_old/_bak naming survives in the
  pipeline or in main.tex/results (P2 submit-D assertion); `FROZEN_MANIFEST.json` exists and its
  md5s match the data actually used; payload chain still bit-audits (`code/payload_audit.py`).
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
  `CLAIMS.md` and must be recomputed under this rule or the sentence dropped (P5).

## 10. Pre-freeze data-generation constraint (Change-log R4)

Before `FROZEN_MANIFEST.json` exists (the **pre-freeze** stage), the ONLY data that may be
generated is the **validate** grid (`expand_grid_clean.py --split validate`, the default).

- **test / Culver grids and their oracle labels MUST NOT exist pre-freeze.** They are generated by a
  **separate command, run only AFTER** the manifest is written (P2 submit-B step d).
- `code/p2_dataprep/check_leakage.py` enforces this: with no manifest present it asserts the
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
  (`make_dataset.py`); it is now stated in the protocol and implemented in `expand_grid_clean.py`.
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
  -parseable `CATOSG-CANDIDATES` JSON block that `train_p2_loso.py` parses (no candidate values are
  hard-coded in code). IRON RULE: expanding the candidates after training needs a new Change-log entry
  and a full retrain. (iii) The Authority clause now states PROTOCOL defines intent and a
  generator that disagrees is a code bug (the earlier "generator wins" sentence is removed). Legacy
  selectors `train_rf.py` and `recompute_policy_200seed.py` are fused off (hard error at entry;
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
  this entry governs. The corrected diagnostic (`r10c_diagnostic.py`) recomputes on the **feasible**
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
  `make_r10_report.py` (no hand-written numbers → `R10_REPORT.md` + `PROVENANCE_r10c.txt`).**
  `cost-induced` is **non-empty for λ>0** (test B010 4809 / B020 2121 cells; the λ=0 budget B030 = 0)
  and its F1 cost (small **positive**) is included in the TOTAL. **Two different numbers (do not
  conflate), test three budgets:** strict-benefit missed-E F1 cost /frame = 0.002658 / 0.002658 /
  0.002705; total E-collapse F1 cost /frame = 0.003021 / 0.002888 / 0.003030 (≈0.53·δ at B020); both
  negligible on Culver (≈0.00003). Record hygiene (single-version, no `retracted_r10/`): the flawed
  `r10_diagnostic.py` + its `r10_*.csv` are removed via the reference gate; `anomaly_check.py` no
  longer prints the retracted conclusion and `anomaly_report.txt` is regenerated in place. 6d AP and
  P2-C/D stay frozen pending review.

**Diagnostic note (Change-log R6/R7).** The gap between a candidate's OOF payload and its full-retrain
(frozen) payload is a **training→freeze diagnostic** of the selection procedure. It must **not** be
written into the paper's conclusions; the paper reports only the frozen selectors' evaluated numbers.
