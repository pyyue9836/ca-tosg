# V2 HANDOFF — read this first, then `docs/unified_branch_protocol_v2.md`

> ## ▶ CURRENT STATE (V2-R48) — the manuscript is written; read this block before the history below
>
> **The perception experiment is closed** (`results/manifests/V2_CLOSEOUT.json`). No further
> held-out evaluation or tuning exists, and none may be added.
>
> **There is exactly one manuscript**, at `paper/main.tex` + `paper/supplementary.tex`, with
> `paper/figures/`, `paper/tables/` and `paper/references.bib`. No `v2_draft/`, no version suffixes
> (Josh's ruling, V2-R47 A-3, written into `docs/STOP_WORK_v1_freeze.md`).
>
> **The superseded documents are archived, not deleted**, under `paper/archive/`: the v1 manuscript
> and supplementary, the 4-page results brief, both v1 PDFs, the 15 v1 figures, `refs.bib` and the
> old drafting notes. Three `.tex` and two `.pdf` are pinned by their ORIGINAL hashes in
> `V1_FREEZE_WITNESS.json`; a one-byte change to any of them fails the gate, whose `--self-test`
> injects both a changed byte and a deletion.
>
> **Every number in both documents comes from `tools/build_v2_paper_numbers.py`** — 150 macros and
> 7 generated table bodies — and gate 34 (`paper numbers macros`) enforces that the manuscript uses
> them, with `tests/paper_literal_registry.md` listing the constants that are legitimately literal.
>
> **The gates stand at 35** (19 runnable on a clean clone). The two newest are 34
> `paper numbers macros` (every result number in the manuscript comes from a generator) and
> 35 `fingerprint coverage` (the retired-value sweep must cover every delivered document, and
> its withdrawal exemption is injection-tested).
>
> Still awaiting Josh: the level-2 position-effect threshold (§3.1), whether Tier B starts, and
> whether the sibling OpenCOOD checkout gets a fork (§3.9).


Written at the end of the V2-R22 session. Everything below is checkable from the repository; nothing
here is memory.

---

## 0. The one thing that is NOT in this repository — now registered (V2-R20 D)

The v2 products need files that live in the **sibling OpenCOOD checkout**
(`~/cooperative_semantic_perception/OpenCOOD`), a different git repository:

| file | change |
|---|---|
| `opencood/utils/catosg_eval_rng.py` | **new**, `#self+` — per-sample deterministic RNG |
| `opencood/utils/pcd_utils.py` | `shuffle_points(points, rng=None)` — `None` keeps the old global behaviour exactly |
| `opencood/data_utils/datasets/intermediate_fusion_dataset.py` | threads a per-sample RNG in, gated on `CATOSG_EVAL_RNG` |
| `opencood/utils/catosg_collab_subset.py` | the §2 single-collaborator rule |

**On a fresh machine:**

```bash
git clone https://github.com/DerrickXuNu/OpenCOOD.git && git -C OpenCOOD checkout 31ba1602
python tools/apply_opencood_patches.py --apply        # 18 patches
python tools/build_sibling_dependency_manifest.py --check
```

`results/manifests/V2_SIBLING_DEPENDENCY.json` pins the upstream URL, the base commit and every
file's SHA-256; `patches/opencood/` carries the portable form.
`results/manifests/V2_RUNTIME_MANIFEST.json` records the run-time switches.

**Known limit, stated rather than glossed:** the modifications travel as **patches, not as pushed
history** — the sibling's only remote is upstream `DerrickXuNu/OpenCOOD`, which this account cannot
push to. Content, apply order and verification are covered; a signed, dated provenance trail outside
this repository is not. Creating a fork would close that and is Josh's call.

---

## 1. Where the work stands

**v1 is frozen** (`docs/STOP_WORK_v1_freeze.md`, from `400bfb6d`): the manuscript, both PDFs and
every `results/main/**` product take zero changes. Running the compile gate rewrites the PDFs as a
side effect — `git restore paper/*.pdf` after any full gate run.

**v2 protocol is fully locked**: `docs/unified_branch_protocol_v2.md`, 15/15 sections, hashed into
`results/manifests/V2_PROTOCOL_MANIFEST.json`.

### Work packages

| WP | state |
|---|---|
| 1 forward invariants | **done** — `v2_wp1_invariants.py`, a precondition call, self-test fires on all three perturbations |
| 2 per-agent inference | **done, all three splits**, deterministic. validate 1980, test 2170 (2051 with a collaborator), culver 550 (478) — the collaborator counts match v1's P4-C exactly |
| 3 E products | **done (validate)** — AP@0.5 0.72055, F1 0.78929 |
| 4 L products | **done (validate)** — AP@0.5 0.88851, F1 0.88918; `B_L` 0.00253 Msym = 0.80 % of the β=0.10 budget |
| 5 F products | **done (validate)** — three regimes × 8 loss rates × R=4 + endpoints; both bridges pass bit-exactly |
| — identity alignment audit (V2-R19 A) | **done, all three splits — 100.00 % on all four parts.** `v2_alignment_audit.py`; the A-3 precondition on `N_box,t → B_L,t` is discharged |
| — WP3/WP4 **test** (sealed) | **done, V2-R29 C-1** — 2170 frames into `results/v2/sealed/wp34_e_l_test.csv`; structural counts only, no accuracy printed (C-6) |
| 6 cue regeneration | **schema frozen and validate cues generated; STOPPED before the refit (V2-R22, H-3).** §9 amendment registered; `v2_ego_local_23d` = 21 ego-local + 2 channel; `results/v2/wp6_cues_validate.csv` (1980 frames) and the D-1 comparison exist. **One ruling open — see the boxed question in §3.** |
| 7–10 | not started |
| 11 held-out evaluation | not started; test/Culver accuracy is **sealed** |
| 12 external baseline | not started; Tier C unapproved |

---

## 2. The next task

**Work package 6 is past its audit and its schema freeze; what remains is E-1 — the refit.** See the
boxed question in §3 first: it is the only thing blocking.

The §9.1 acceptance criteria are discharged as follows: all 23 v1 dimensions were tabulated with a
**code location per row** (`results/v2/wp6_cue_audit.json`, `--verify-locations` re-checks the
citations at run time); 0 turned out to depend on detection output; **1 was ground truth and stopped
the batch** as criterion 5 requires; the replacement schema `v2_ego_local_23d` is frozen in §9.2 and
generated for validate. The D-1 distribution comparison was produced **before** any refit, which is
what caught the error recorded at §3.8.

**What E-1 covers** (zero GPU): regenerate oracle / feasibility, refit RF + SNR threshold + hand
rules on the new schema, then WP9–WP10 products and the freeze. **What it does not touch:** WP2
predictions, E/L products, payload, WP5 transport — all confirmed unaffected (V2-R21 E-2).

---

## 3. Open rulings — these need Josh, not work

0. ~~M1 (mean budget vs. per-frame cap) and M3 (the preregistered comparator's relation to the
   matched-payload comparison)~~ — **CLOSED at V2-R60, and they must not be reopened.** Both were
   raised against `8583c18`, which already answers them: §VII-A carries the three-way distinction
   (Fixed F infeasible as an always-on policy / occasional F not excluded by a mean budget / the
   frozen policy selects only E and L), and §VI-B states that the preregistered comparator belongs
   to the original L/F-capable formulation and is retained for protocol integrity. Josh's own
   ruling: the questions were duplicates of text already in the manuscript, not defects.

   **Also ruled at V2-R60:** the size of the learned selector's gain is **not** grounds for
   rejection. The Test result is a valid positive ($+0.00080$, LCB95 $+0.00028$), Culver-City
   establishes no statistical advantage and the paper does not claim one, and the contribution does
   not rest on that gain alone. Whether it affects competitiveness at a particular venue is a
   submission-strategy decision for the supervisor, not a defect in the work.

   **No experiment reopens.** No re-freezing, no channel-only RF arm, no forcing F to appear, no
   further use of the held-out data. `8583c18` was reviewed and no new factual error was found; the
   frozen experiments stand as they are.

1. ~~The level-2 position-effect threshold~~ — **CLOSED, V2-R50 B-1. Josh declined to rule, and
   that is the ruling.** Level 1 ("loss position affects task performance") is supported, reported
   and strengthened to the equal-codeword-count form. Level 2 ("position matters *more* than
   amount") is **not claimed** — the threshold it would need was never pre-registered, and setting
   one now would be setting it with the data on screen. **Closed, not carried as future work**: it
   is not on any backlog, because leaving it open would keep inviting the claim it forbids.
2. ~~WP3/WP4 on test and Culver~~ — **EXPIRED AND RESOLVED, V2-R29 D.** The two options
   ("boxes and counts only" vs "wait for WP11") collapsed into one once the Test primary needed the
   accuracy side: **generate the accuracy, but seal it strictly and unseal once at the end.**
   WP3/WP4 on **test** are done and written straight into `results/v2/sealed/` (V2-R29 C-1);
   **Culver is untouched** and stays independent. Logged as expired rather than left hanging.
3. **Tier B — NOT STARTING (V2-R50 B-2).** The paper is a closed loop as it stands, and nothing is
   added to the experiment before the supervisor sees it. Registered as an **optional follow-up
   with no schedule**; the earlier "≈10 h typical, after Tier A" estimate stands if it is ever
   revived. **Tier C** remains unapproved, pending the ML-Cooper / SmartCooper selection report.
4. **NEW (V2-R19) — should the alignment audit become gate 24?** `v2_alignment_audit.py` is
   currently a script that must be run, not a registered check. Making it a gate would catch a
   future misindexing automatically; the stop-work order forbids new gates *for v1 results* and this
   governs v2 products, so it is permitted — but adding a gate is Josh's call, not the executor's,
   and part B costs ~10 min of CPU per split, which is heavy for the standard suite. **Proposal:
   register it as an artefact-tier gate that verifies the stored `alignment_audit_*.json` rather
   than re-walking the dataset.**
5. ~~The 73.6 % ruling~~ — **CLOSED, V2-R20 A.** Josh withdrew the "correct it to 100 %"
   instruction. The number, the name and the failure-direction note all stand; no
   collaborator-unique detection is discarded. V2-R19 A-3 released.
6. ~~The `intra-repo imports` gate~~ — **CLOSED, V2-R20 D**, and the diagnosis was corrected: it was
   a **real** finding, not a false positive. Registered rather than exempted; see §0 and §5.
7. ~~`ego_num_objects` is ground truth~~ — **CLOSED, V2-R22.** The §9 amendment is registered
   (§9.0, 2026-08-28T10:34:12Z, parent `7f643296`, before WP11 and before any held-out number). The
   field is out of the schema, replaced by `ego_detected_box_count`; the v1 RF/selector results are
   **demoted to diagnostic**.
8. ~~"19 of 21 cues are computed over the all-CAV cloud"~~ — **WITHDRAWN, V2-R22 C. That claim was
   WRONG; this line is kept struck through so nobody acts on it.** Recomputing from the ego's own
   sweep at the v1 range returns the v1 values **exactly (×1.000 on all 17 `pcd_*`)** — the v1 cues
   were already ego-only. The v1 extractor loads the **late-fusion** config, so it ran
   `LateFusionDataset.get_item_test()`, whose dict is per-CAV with each CAV's own `origin_lidar`
   (`late_fusion_dataset.py:85`); the `vstack` at `:251` is inside `collate_batch_test`, never
   called. What actually changed is the **field of view** (±70.4 → ±140.8 m), plus a real
   *prospective* hazard: v2 runs `IntermediateFusionDataset`, where `origin_lidar` **is** the
   all-CAV stack. **The amendment stands; one of its two stated grounds does not.**

> ### ▶ NOTHING IS BLOCKING (V2-R50)
>
> The question that stood here — proceed to E-1 or revisit the schema — was answered by proceeding.
> E-1 ran, candidate 67 was frozen with the comparator at $\lambda = 0.2$, both held-out splits were opened once,
> and the experiment is closed (`results/manifests/V2_CLOSEOUT.json`). The manuscript is written and
> all 35 gates pass.
>
> **Of the items below, none blocks work.** 1 and 3 are closed; 9 is deferred with a stated trigger.

9. **Should the sibling live in a fork? — DEFERRED to the pre-submission reproducibility pass
   (V2-R50 B-3).** The modifications travel as patches because there is no writable OpenCOOD remote
   (§0); a fork under Josh's account would give them pushed, dated history. It **does not block the
   paper or the supervisor review**, so it stays open here with an explicit trigger: decide it when
   the reproducibility material is assembled for submission. Creating one is an outward-facing act
   and remains Josh's to authorise.

---

## 4. What V2-R19 found (this session)

**The 73.6 % was never an alignment rate.** It is a **coordinate-frame** diagnostic — the fraction of
collaborator boxes overlapping some ego box at IoU > 0.1 — printed under the label
`FRAME-ALIGNMENT CHECK`, which is why it read as one. It **fails downward only**, and 100 % would be
a failure: measured, **92.6 % of L's AP@0.5 gain over E and 91.9 % of its F1 gain are carried by the
11,534 collaborator boxes that do *not* overlap an ego box**, of which **8,630 (74.8 %) match a real
GT object**. Forcing it to 100 % collapses L from AP@0.5 0.88851 to 0.73292 — a hair above ego-only
0.72055. Label fixed; `results/v2/coordinate_frame_check_validate.json` holds the decomposition.

**The identity check that really must be 100 % did not exist, and now does.**
`v2_alignment_audit.py`: index integrity; collaborator identity re-derived independently from poses
and compared to `subset_of` frame by frame; a bit-comparison binding row 1 of the voxel tensor to
that CAV; and the payload binding. **100.00 % on all four parts on all three splits**, 0 mismatches
in 4,700 frames. Its part-B by-product — collaborators beyond `COM_RANGE` — reproduces §10.3's
no-collaborator counts (0 / 119 / 72) exactly, from a different route.

**Level 1 of the position effect is now strict.** Conditioning on *exactly equal* codeword-loss
counts across R = 4 replicates still leaves ΔF1 ≠ 0 on 28.48 % (ideal, 1,731 pairs / 1,201 frames)
and 25.57 % (packet, 704 / 583), present at every one of the eight loss rates. The sufficiency rule
was pre-registered before the selection ran. **Level 2 remains unadjudicated** — see §3.1.

**The Monte-Carlo survival count had never been taken.** At `p = 0.001`, `q = 3.463e-6` and the
expectation over the whole Monte Carlo is **1.3715**, not zero; observed survivors **0**, so
`P(0) ≈ e^−1.3715 ≈ 0.254` — an ordinary draw. And `ap50_mc_std = 1.11e-16` appears at **every**
rate including `p = 0.0`, where survival is certain: it is float noise and was never evidence about
the draw. Wordings registered in protocol §5.1(b).

---

## 4.1 What V2-R18 found, and what it cost

**`shuffle_points()` drew from the global unseeded numpy RNG**, once per CAV per frame. With
`max_points_per_voxel = 32` the surviving points depended on that order, so two runs of the same
frame disagreed: **~1.5 % of frames by one box, AP by 1e-5 to 1e-4**. Every v1 product went through
this path too.

It was found because a **reconstruction-consistency bridge** compared two runs bit for bit —
something this repository had never done. **v1's "reproducible on re-run" was never tested, not
passed.**

Diagnosis, four steps: same-process forwards were already exact (`max|Δ| = 0` on 1980 frames);
two processes disagreed; disabling cuDNN TF32 and forcing deterministic algorithms changed nothing
(the GPU was never the cause); seeding numpy made two processes bit-identical.

Fix: per-sample `RandomState` keyed on `(split, scene, frame, cav)`, `CATOSG_EVAL_RNG=1`. After it,
the same bridge passes with **0 differing frames and AP difference exactly 0.000e+00**.

---

## 5. Gates — 25 checks

Two pre-existing failures were found at `ddd72622` (verified in a throwaway worktree, not assumed)
and **both are now closed by fixing the underlying problem, not by exempting the check**:

* `intra-repo imports` flagged `catosg_eval_rng`. **That was a real finding, not a false positive**
  (V2-R20 D-1): the module was unregistered *and* missing from `patches/opencood/`, so a fresh clone
  could not reproduce any v2 product. `--export` then showed the patch set had been stale since
  V2-R16 — one CONFLICT and two files absent. Fixed, and the gate **narrowed** to allow exactly one
  registered external dependency, pinned by base commit and content hash.
* `numeric literals` flagged a stale `results/README.md` (V2-R16..R18 added result files without
  re-running `results_index.py`). Regenerated.

New in V2-R20: **24 sibling dependency**, **25 alignment audit**. Both carry `--self-test`
injections (3 and 5 respectively), because a gate that cannot fail is worse than none.

Added in V2-R18: **22 sealed held-out**, **23 eval determinism**.

### Closing checklist for every batch (V2-R20 E-2)

Two failures this round had the same cause — a regeneration step that existed but was on no
checklist, so it could be skipped for a whole session:

* anything added, removed or renamed under `results/` → `python projects/ca_tosg/utils/results_index.py --write`
* anything touched in the sibling OpenCOOD checkout → `python tools/apply_opencood_patches.py --export`
  **and** `python tools/build_sibling_dependency_manifest.py`
* any `results/v2/wp2_*` or `wp34_*` product regenerated → re-run `v2_alignment_audit.py`, or gate 25
  will fail on the recorded input hashes (by design)
* **anything added under `results/` also moves the p6 report** → `python tools/p6_numbers_vs_csv.py`
  (V2-R25: adding the grid moved the located-cell count 297 → 300 and the gate caught the stale
  report. Third member of the same family as `results_index.py` and `apply_opencood_patches --export`
  — a generated artefact whose generator nobody re-ran.)

**A fourth member, and it fails differently (V2-R47 E-1 / V2-R50 C-3).** `results/README.md`
enumerates **git-tracked** files. Running `results_index.py --write` on a *new, untracked* product
therefore produces no change at all — the generator runs, reports success, and the index stays
stale until that product is committed. It failed the numeric-literals gate one run later.

**The distinction matters because the fix does.** The first three are *"nobody re-ran it"*, and a
checklist repairs that. This one is *"it was re-run at the wrong moment"*, and a checklist does
**not** repair it — an ordering rule does: **re-run the index AFTER the commit that adds the file,
not before.** Putting an ordering fault on a checklist produces a step that gets ticked while
doing nothing, which is how it hid in the first place.

`tests/test_eval_determinism.py` enumerates **all 17,905 identities** for seed collisions on every
run — 0 collisions now, but that is a property of *this* identity set, not of the derivation, and the
birthday probability at 32 bits is ~3.7 %. The remedy if it ever fires is pre-recorded in
`results/v2/seed_collision_scan.json`.

```bash
cd ~/cooperative_semantic_perception/ca-tosg && conda activate sionna310
python tools/verify_results.py          # 23; slow, ~10 min (p6 + determinism gates)
git restore paper/main.pdf paper/supplementary.pdf   # the compile gate rewrites them
```

---

## 6. Working rules that bit these sessions

**Gate design has its own file now:** `docs/gate_design_principles.md` — four rules, each bought with
a real failure. The fourth, added V2-R21, is **a gate that cannot fail**, and it is the worst because
it is indistinguishable from a working one until you watch it fail on purpose.


* **A label is what the reader has to go on.** `FRAME-ALIGNMENT CHECK` computed a coordinate-frame
  overlap. Nobody misread the number; they read the name. Same family as V2-R16's "a gate whose name
  overstates what it checks is worse than none, because it is trusted".
* **A diagnostic quoted without its failure direction cannot be checked.** The 73.6 % would have
  read identically at 5 % or 99 %. Every reported diagnostic now carries what "good" looks like and
  which way it fails.
* **"Displays as zero" ≠ "has no variance."** One is about precision, the other about the process.
* **A cache over a function whose result gets mutated is a silent corruption**, not a speedup —
  `load_yaml` needed a deepcopy, and the poses had to be checked against the uncached path first.
* **A gate with a false positive is worse than no gate** — it teaches people to skip it. Gate 22
  needed three narrowings; gate 24's serialisation had to be pinned for the same reason. V2-R19's
  own new check reproduced the fault in miniature: a `None` digest counted as "differs", so the
  negative control passed **without ever running**.
* **Verify before asserting.** Three times this session an inference was raised as a challenge when
  one `grep` would have settled it (IoU thresholds already stored separately; forward count; the
  13-row list). The cost of checking was always seconds.
* **A numeric coincidence is not an identity of objects.** 144+32+8 landing back on 184; two 13-row
  lists sharing a length and matching on 0 rows.
* **Placeholders are fabrications.** A `GOLDEN_HEAD` I invented sat in a file for minutes before
  `--record` produced the real value. Short-lived does not mean not-invented.
* **Never report an unstarted run as started**, and never a projected ETA as a measured one — the
  84-minute projection became 194 minutes because validate is ordered by scene and the dense scenes
  are last.

---

## 7. Reproduce the current state

```bash
cd ~/cooperative_semantic_perception/ca-tosg && conda activate sionna310
export PYTHONPATH=~/cooperative_semantic_perception/OpenCOOD
python tests/test_eval_determinism.py --self-test        # RNG chain + collisions + injection
python tools/v2_payload_chain.py                         # B_F = 3.14175 Msym via N_cw = 12,567
python projects/ca_tosg/evaluation/v2_wp1_invariants.py  # checkpoint / FOV / thresholds

# V2-R19, all zero GPU:
python projects/ca_tosg/evaluation/v2_alignment_audit.py --split all      # 100 %; ~32 min total
python projects/ca_tosg/evaluation/v2_mc_survival_audit.py                # seconds
python projects/ca_tosg/evaluation/v2_position_effect_level1.py           # seconds
python projects/ca_tosg/evaluation/v2_coordinate_frame_check.py           # ~13 min
```

Regenerating WP5 costs ~3.3 h for the sweep plus ~35 min for the addendum.
