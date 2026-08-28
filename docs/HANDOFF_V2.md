# V2 HANDOFF — read this first, then `docs/unified_branch_protocol_v2.md`

Written at the end of the V2-R21 session. Everything below is checkable from the repository; nothing
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
| 6 cue regeneration | **STARTED, then STOPPED as criterion 5 requires.** Audit done: 23 dims classified with code locations, 0 depend on detections, **1 forbidden (GT)**, 20 of 23 move under v2. Two rulings needed before it can continue — see §3.8 |
| 7–10 | not started |
| 11 held-out evaluation | not started; test/Culver accuracy is **sealed** |
| 12 external baseline | not started; Tier C unapproved |

---

## 2. The next task, and why it is not bookkeeping

**Work package 6 — cue regeneration.** `docs/unified_branch_protocol_v2.md` §9.1 carries six
acceptance criteria, all preconditions of the selector freeze.

Carrying the v1 cue *values* over unregenerated would feed **v1 detections into a v2 selector**. That
is leakage, and **no gate in this repository would catch it**: the values are plausible, the column
names unchanged, every existing check passes. P0-3's invalidation list does not mention the cue
vector at all — the only list that does is work package 6.

The six criteria, in short: all 23 dimensions tabulated `depends` / `independent`; **a code location
as the basis of each classification, with a verbal assertion explicitly not acceptable**; `depends`
rows recomputed with old and new distributions printed; `independent` rows given an invariance
demonstration ("it looks like a channel quantity" is not one); **an unclassifiable dimension stops
the batch**; the table enters the manifest.

---

## 3. Open rulings — these need Josh, not work

1. **The level-2 position-effect threshold.** V2-R11 B-2 asked for a proportion threshold to be
   written into the protocol *before* the data was seen. It never was. Level 1 ("loss position
   affects task performance") is **supported and reported**, and V2-R19 B strengthened it to the
   equal-codeword-count form; level 2 ("position matters more than amount") is **still not
   adjudicable**, and defining the threshold now would be choosing it after seeing the numbers.
   Either pre-register one for a future run or drop the claim. **Reaffirmed unchanged in V2-R19
   B-4.**
2. **WP3/WP4 on test and Culver.** Not run. They would produce held-out accuracy, which is sealed.
   Decide: generate boxes and box counts only (feeding payload accounting, no accuracy), or wait for
   WP11.
3. **Tier B** is approved at ≈10 h typical, to start after Tier A is accepted. **Tier C** is not
   approved, pending the ML-Cooper / SmartCooper selection report.
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
7. **NEW (V2-R21) — `ego_num_objects` is ground truth and must leave the cue set.** It is
   `len(ego['object_ids'])` from `params['vehicles']`; rank 5 of 23 by Gini importance (2.54 %). C-5
   forbids GT in the cue vector. Removing it is a **§9 amendment**, which §9 requires to be
   registered *before any test/Culver number is seen* — that window is open now and closes at WP11.
8. **NEW (V2-R21) — §9's reason for carrying the cue set over is factually wrong.** It says the cues
   describe "the ego's own scene"; 19 of 21 are computed over `np.vstack(projected_lidar_stack)`,
   the **all-CAV** cloud (v1 up to 7 vehicles, v2 at most 2). Redefining them as genuinely ego-only
   versus keeping fused-cloud statistics with corrected wording is a design decision, not a repair.
9. **NEW (V2-R20) — should the sibling live in a fork?** The modifications travel as patches
   because there is no writable OpenCOOD remote (§0). A fork under Josh's account would give them
   pushed, dated history. Creating one is an outward-facing act and is Josh's to authorise.

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
