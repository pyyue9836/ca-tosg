# V2 HANDOFF — read this first, then `docs/unified_branch_protocol_v2.md`

Written at the end of the V2-R18 session. Everything below is checkable from the repository; nothing
here is memory.

---

## 0. The one thing that is NOT in this repository

Three edits live in the **sibling OpenCOOD checkout**
(`~/cooperative_semantic_perception/OpenCOOD`), which is a different git repository and is **not
pushed anywhere**. Without them the v2 products cannot be reproduced:

| file | change |
|---|---|
| `opencood/utils/catosg_eval_rng.py` | **new**, `#self+` — per-sample deterministic RNG |
| `opencood/utils/pcd_utils.py` | `shuffle_points(points, rng=None)` — `None` keeps the old global behaviour exactly |
| `opencood/data_utils/datasets/intermediate_fusion_dataset.py` | threads a per-sample RNG in, gated on `CATOSG_EVAL_RNG` |

They are uncommitted in that checkout. **On a fresh machine, restore these first.**
`results/manifests/V2_RUNTIME_MANIFEST.json` records exactly what they are.

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
| 6 cue regeneration | **NOT STARTED — this is the next task, and it is a leakage defence** |
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
   affects task performance") is **supported and reported**; level 2 ("position matters more than
   amount") is **not adjudicable**, and defining the threshold now would be choosing it after seeing
   the numbers. Either pre-register one for a future run or drop the claim.
2. **WP3/WP4 on test and Culver.** Not run. They would produce held-out accuracy, which is sealed.
   Decide: generate boxes and box counts only (feeding payload accounting, no accuracy), or wait for
   WP11.
3. **Tier B** is approved at ≈10 h typical, to start after Tier A is accepted. **Tier C** is not
   approved, pending the ML-Cooper / SmartCooper selection report.

---

## 4. What was found this session, and what it cost

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

## 5. Gates — 23 checks

New this session: **22 sealed held-out**, **23 eval determinism** (the fourth number in the runner
output is the fingerprint sweep, so the suite prints 23 lines).

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

## 6. Working rules that bit this session

* **A gate with a false positive is worse than no gate** — it teaches people to skip it. Gate 22
  needed three narrowings; gate 24's serialisation had to be pinned for the same reason.
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
```

Regenerating WP5 costs ~3.3 h for the sweep plus ~35 min for the addendum.
