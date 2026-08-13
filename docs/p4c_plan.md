# P4-C — collaborator scale N ∈ {1, 2, 3}: PLAN

**Status: PLAN ONLY. No inference has been run. No GPU has been touched by this commit.**
Every number below is counted from the committed dataset index and the OpenCOOD loader source; none
of it is a result. The plan is pushed for review, and the run is blocked until it is greenlit.

Untouched by this plan and by the run that would follow: `paper/main.tex`, the deployed frozen
selectors, δ, τ\*, `FROZEN_MANIFEST.json`, and the mainline replay.

---

## a. Collaborator-subset rule (deterministic), and how many frames can support it

### The rule

For a frame with ego *e* and available collaborator set *C*, the **N-arm** uses

> the **N nearest** members of *C* by Euclidean distance between `lidar_pose[0:2]` (x, y) of the
> collaborator and of the ego at that timestamp — the same distance OpenCOOD already computes for
> its `COM_RANGE = 70` m filter (`late_fusion_dataset.py:141`) — **ties broken by ascending CAV id**.
> If |C| ≤ N the arm uses all of *C* and the frame is marked `subset_is_full = true`.

Ties are exact-float ties, which are near-impossible on continuous poses; the id rule exists so the
selection is *total* and reproducible rather than dependent on dict ordering. The rule is enforced
by an explicit mask computed from `lidar_pose`, **not** by OpenCOOD's `max_cav`: `max_cav`'s
selection order is a loader-internal detail and relying on it would make the arm depend on
behaviour we have not pinned. The mask is a `#self+` edit to be listed in
`docs/opencood_modifications.md` when it is written.

`COM_RANGE` is left at its current value. The N-arm is a subset *of what the loader already
admits*, so N-arm ⊆ baseline arm by construction.

### How many frames can support each N

Counted now from `num_cavs` / `cav_keys` in the committed per-frame datasets. **`num_cavs` counts
the ego** (`cav_keys` = `ego|2158|2167|2176` → `num_cavs` = 4), so collaborators = `num_cavs` − 1.

| split | frames | collaborators min / mean / max | ≥1 | ≥2 | ≥3 |
|---|---|---|---|---|---|
| validate | 1980 | 1 / 2.90 / 6 | 1980 (100%) | 1247 (63.0%) | 899 (45.4%) |
| test | 2170 | 0 / 1.59 / 4 | 2051 (94.5%) | 1081 (49.8%) | 212 (9.8%) |
| culver | 550 | 0 / 1.09 / 2 | 478 (86.9%) | 123 (22.4%) | **0** |

Full distributions (collaborators → frames):
`validate {1:733, 2:348, 3:153, 4:297, 5:21, 6:428}`,
`test {0:119, 1:970, 2:869, 3:111, 4:101}`,
`culver {0:72, 1:355, 2:123}`.

**Two consequences that constrain the design, not footnotes:**

1. **Culver-City cannot support N=3 at all** (max 2 collaborators) and supports N=2 on only 123 of
   550 frames. The N=3 arm is meaningfully distinct only on validate (899 frames) and test (212).
   Any N=3 statement about Culver would be a statement about "≤2 collaborators", and must be
   labelled that way or not made.
2. **119 test frames and 72 Culver frames have ZERO collaborators.** No N-arm changes them; they
   are ego-only whatever the selector decides. They stay in the denominator — dropping them would
   silently redefine the split — and are reported as a separate row.

---

## b. Inference requirements and the GPU bill

### What actually needs a new forward pass

| branch | N-dependent? | why |
|---|---|---|
| **ego** | **no** | no message is received; the ego-only detection is identical for every N. **Reuse `gs_rerun/ego_{split}.npz` unchanged.** |
| **late** | yes, but **not on the GPU** — see below | `inference_late_fusion` runs `model(cav_content)` **per CAV** and then merges via `dataset.post_process` (`opencood/tools/inference_utils.py`). Restricting to a subset changes only *which* per-CAV outputs enter the merge. |
| **intermediate** | **yes, on the GPU** | fusion happens *inside* the network across CAV features, so each (frame, subset) is its own forward. |

**Late-branch plan: one pass, then CPU re-merges.** Run the per-CAV detector once over all CAVs of
all frames, cache the per-CAV outputs, and obtain every N by re-running `post_process` on the chosen
subset. **This is an optimisation to be verified before it is relied on**, by the check: re-merging
the *full* CAV set must reproduce the committed `gs_rerun/late_{split}.npz` bit-for-bit. If it does
not, fall back to a forward per (frame, N) and the bill below rises accordingly — that fallback cost
is quantified in the table.

### Frames needing a new forward

A frame needs one only when its subset differs from the cached full set, i.e. collaborators > N:

| split | N=1 | N=2 | N=3 | reuse N=1 / N=2 / N=3 |
|---|---|---|---|---|
| validate | 1247 | 899 | 746 | 733 / 1081 / 1234 |
| test | 1081 | 212 | 101 | 1089 / 1958 / 2069 |
| culver | 123 | 0 | 0 | 427 / 550 / 550 |
| **total** | **2451** | **1111** | **847** | — |

### GPU estimate

Per-frame cost **0.303 s**, derived from the registered figure in `docs/data_manifest.md`
(~10 GPU-min per ~1980-frame split per branch) — not from a guess, and **to be replaced by a
20-frame micro-timing calibration as the first action of the run**, before the full sweep is
launched.

| item | passes | estimate |
|---|---|---|
| intermediate, all three N (option A below) | 4409 frames | **≈ 22 GPU-min** |
| late, one per-CAV pass over all frames | ≈ 1 × the registered late cost | **≈ 30 GPU-min** |
| late fallback if the re-merge check fails | 4409 frames × per-CAV | ≈ 60–90 GPU-min |
| ego | 0 | 0 |
| **planned total (option A, re-merge works)** | | **≈ 1 GPU-hour** |

### Cache layout

New directory, nothing overwritten:

```
gs_rerun/p4c_N{1,2,3}/{late,intermediate}_{validate,test,culver}.npz
gs_rerun/p4c_percav/late_{split}.npz          # per-CAV outputs for the re-merge
```

The existing `gs_rerun/{late,comp,ego}_*.npz` are **inputs, opened read-only**. They are registered
in `docs/data_manifest.md`, which forbids deleting them; the new caches get their own manifest rows
with md5 + regeneration command when they exist.

---

## c. Payload accounting for N collaborators

Derived from the committed chain (`tests/test_payload.py`), not restated: 1.98 Mbit information →
÷0.5 rate-1/2 LDPC → 3.96 Mbit coded → ÷4 bit/sym (16-QAM) = **0.99 Msym** per feature message;
0.024 Mbit at rate-1/2 QPSK ≈ **0.024 Msym** per object message.

**N collaborators means N messages.** One granularity decision, broadcast (see d), so

| action | N=1 | N=2 | N=3 |
|---|---|---|---|
| E | 0 | 0 | 0 |
| L | 0.024 | 0.048 | 0.072 |
| F | 0.99 | 1.98 | 2.97 |

Budget semantics follow **§5 unchanged**: B_max bounds the **mean** per-frame payload over a split,
not any single frame. What changes with N is only how expensive the mean is:

- B_F(N) exceeds every B_max ∈ {0.10, 0.20, 0.30} already at N=1, so feasibility has always been
  carried by a small ρ_F, not by any frame being cheap.
- At fixed ρ, mean payload scales linearly in N. The budget-feasible ρ_F therefore shrinks by ≈1/N:
  a policy spending B̄ = 0.187 at N=1 spends 0.561 at N=3 and is no longer feasible at any of the
  three budgets.
- Consequence to state plainly in the results, not to engineer around: **the frozen selectors were
  frozen at N=1 semantics.** Replaying them at N=2/3 will show budget overshoot; that is a property
  of the transfer, not a violation to be patched, and it is exactly the kind of non-transfer already
  recorded for τ and for the P4-A comparator.

`tests/test_payload.py` gains three derived links per N (B_L(N) = N·B_L, B_F(N) = N·B_F, and the
deployed mean payload = Σ_a ρ_a·B_a(N)), computed from the same rate/modulation parameters so no
constant is retyped.

---

## d. Evaluation design — and the one semantics gap that must be closed before running

### What the current protocol actually says

The frozen selector emits **one action per frame** from {E, L, F}. It has no per-collaborator
action, and the 23 features contain no per-collaborator field. The faithful multi-collaborator
reading, which changes no protocol text and retrains nothing, is:

> the ego makes **one** granularity decision per frame and **broadcasts the same request to all N**
> selected collaborators; payload = N × B(action).

Per-collaborator decisions would be a different action space ({E,L,F}^N) and a different selector.
That is **out of scope** here and is not to be smuggled in.

### The gap: what "delivered" means with N links

The frozen protocol defines delivery for **one** link: the feature message arrives or the frame
falls back to ego-only. With N independent links, partial delivery is undefined. Two candidate
semantics, neither implied by the current protocol:

| | semantics | eff_F | inference cost |
|---|---|---|---|
| **A** | **all-or-nothing**: any of the N links fails → ego-only fallback for that frame | needs eff for the full N-subset only | **4409 forwards ≈ 22 GPU-min** |
| **B** | **partial fusion**: fuse whichever subset arrived | needs eff for **every non-empty delivered subset** (2^N − 1 per frame) | **27 775 forwards ≈ 2.3 GPU-hours** |

Option B is 6.3× the bill and is the more realistic receiver. Option A is a conservative bound on
the feature branch (it can only understate F's value). **This must be pre-registered before the run,
not chosen after seeing numbers.** Recommendation, for the greenlight decision: pre-register **A as
primary** (cheap, conservative, and it brackets B from below) **and B as a bracket on validate only**
(8070 forwards ≈ 41 GPU-min), giving a two-sided reading on the split where fitting is permitted,
without paying 2.3 GPU-hours across all three splits. Either way the choice is recorded in the
change-log entry before any forward is run.

Under both options the per-link BLER is the existing Sionna frame-level table; the N links draw
independent channel realisations from the same CSI stream as the mainline replay.

### Outputs and statistics

Same 200 paired CSI draws (`CSI_SEED` unchanged), all three splits, one row per
(split, B_max, N, policy):

- F1, mean payload, action distribution (ρ_E/ρ_L/ρ_F), `over_budget` flag;
- paired bootstrap CI of every N ∈ {2,3} arm **against the same policy at N=1** (the frozen
  operating point), plus the τ rule replayed at each N as the reference;
- a `subset_is_full` share and a zero-collaborator share per split, so any cell where the arm was
  not actually distinct is visible;
- `results/sensitivity/collaborator_scale.csv` + `results/provenance/PROVENANCE_p4c.txt`, and a
  separate `results/manifests/P4C_MANIFEST.json` for any variant artefact — never mixed into
  `FROZEN_MANIFEST.json`.

**No decision, no threshold, no selection.** Descriptive + paired CI only; the confirmatory primary
was spent once at R9. §8 anti-forcing applies: expectations below are checks, and a miss is reported.

### Pre-registered expectations (to be finalised in the change-log at greenlight)

1. Mean payload scales ≈ linearly in N at fixed policy, so the frozen selectors overshoot B_max at
   N=2 and N=3 on every split. (Near-arithmetic; it is listed so that a *non*-linear result is
   visibly a bug, not a finding.)
2. F1 rises with N where the feature branch is actually delivered, with diminishing returns — the
   second collaborator adds less than the first.
3. On Culver the N=3 arm is identical to N=2 (no frame has 3 collaborators); if the two columns ever
   differ, that is a bug in the subset mask, not a result.

---

## Open decision blocking the run

**Delivery semantics: option A only, or A + B-on-validate?** The bill differs by ~40 GPU-min for the
recommended split, or by 2 GPU-hours if B is run everywhere. Nothing else in this plan is blocked.
