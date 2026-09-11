# F spatial-block selection within budget — round-1 development experiment protocol

**Status: LOCKED** (P2-R4). Sections A–D below are the rules of the first development experiment.
Every number in them is derived by `round1_lock.py` and recorded in `round1_lock.md`; `round1_lock.py
--check` re-derives them and fails if this text states a different K_F. Changing a locked rule is a
dated amendment in `docs/history/protocol_changelog.md` of this project, never an edit.

**What this lock does not cover.** Selector training (none in this round), V2V4Real (not started), and
the final policy-evaluation protocol (stage 2 of the earlier draft's C-8, locked after round-1 results
exist and before any confirmatory data is opened). Confirmatory splits (`test`, Culver-City) stay
closed throughout round 1.

---

## A. Budget, computed before the lock

### A-1 Block

On the shared 25 × 88 transmitted grid, one block is **5 × 8 cells** (16.0 m × 25.6 m of BEV);
**55 blocks**. A block carries the corresponding cells of all three scales at once — branch 0
(16 channels), branch 1 (64) and branch 2 (256): **13,440 elements per block**. Recovery and billing
treat a block as one unit. Block index is raster order (row-major, 0-based). One block maps to
20 × 32 cells of the 100 × 352 detection-head grid, the same region on ego and collaborator because
both clouds are projected into the ego frame before voxelisation (as in P1).

### A-2 Symbols per block and overhead

Per frame the collaborator sends one bitstream: **[55-bit block mask][K selected blocks in ascending
block index; within a block branch 0, 1, 2; within a branch channel-major]**, each element 8 bits, then
P1's chain unchanged — 8,000-bit packets with 320-bit headers, LDPC K = 500 / n = 1,000, 16-QAM.
Overhead, item by item:

| item | bits per frame |
|---|---:|
| block mask (bitmap) | 55 |
| block index list | 0 — raster order plus the bitmap restores the layout |
| quantisation parameters | 0 — per-branch int8 scales pre-shared (P1 §3.3) |
| packet headers | 320 per packet, charged inside `N_sym` by the P1 chain |
| LDPC codeword padding | charged inside `N_sym` by the P1 chain |
| the request | not charged — identical for every action (P1) |

Bits per block: 107,520. **Mask loss is not modelled**: the receiver is assumed to know the layout,
as P1 assumes for packet-header contents; the mask bits are nonetheless charged as payload.

### A-3 Link scenario and K_F

**IEEE 802.11bd, 20 MHz, D_comm = 100 ms**, parameters as verified in `link_scenarios.md` (B-1 of
P2-R3): **B_available = 1.3500 Msym**. This is a **zero-overhead upper bound** — the whole channel to
one link, every data resource element, continuously; preamble, midambles, MAC framing, contention,
queueing and the request are all excluded — so a real link carries less, and K_F is an upper bound on
the blocks a real link would carry. It is used because a representation that fails under the upper
bound fails everywhere, and one that succeeds is then tested against tighter budgets.

```
K_F = max{ K : N_sym,F(K) ≤ B_available }
```

**K_F = 23** of 55 blocks (41.8 %): 2,473,015 bits → 5,256 codewords → N_sym,F(23) = 1.3140 Msym
(K = 24 gives 1.3710 Msym and does not fit). 5,255 elements of this message straddle two codewords.
The draft's reference value (23) is kept as reference only; the locked value is the one derived here.

### A-4 L bound

The observed validate maximum is **51 collaborator boxes → N_sym,L = 0.00525 Msym ≤ B_available**, so
**L is not truncated** in round 1. Under this budget the cap would be 13,810 boxes; the 99th
percentile of the observed count is 49, so the expected truncation share is 0.0 %. Rule, recorded for
any scenario where the maximum does not fit: the collaborator sends the top `min(N_box, K_max)` boxes
by confidence, and every policy that uses L follows the same rule.

---

## B. Ranking rules — three, at the same payload

All three send exactly K_F = 23 blocks per frame, so the three F variants have identical payload and
identical codeword count. Each uses only what the collaborator has before it sends.

### B-1 Confidence ranking

* **Source.** The collaborator's own detection head run on its own features — the single-vehicle
  forward P1 already runs for the L message — giving the classification map `psm` on the 100 × 352 head
  grid with 2 anchors per cell.
* **Anchor merge.** `sigmoid(psm)` then **max over the anchor dimension** → one confidence per head cell.
* **Head grid → blocks.** Block `(i, j)` is head rows `[20i, 20i + 20)`, columns `[32j, 32j + 32)`; that
  is exactly its 5 × 8 cells on the transmitted grid of every branch (A-1).
* **Block score = max** over the block's 640 head cells. Chosen over mean because a block is worth
  sending if any part of it is confident, and a mean over 16 m × 25.6 m dilutes a single vehicle.
* **Ties:** block index ascending.

### B-2 Norm ranking

* **Score = Σ over the three branches of the L2 norm** of the block's elements on that branch, computed
  on the float bottleneck before quantisation (what the sender holds); branches are summed as they are,
  without rescaling.
* **Ties:** block index ascending.

### B-3 Random ranking

* **R_rand = 20** repeats. Repeat `r` on frame `t` draws K_F blocks without replacement from
  `numpy.random.default_rng([20260809, 2, t, r])` (`BASE_SEED` is P1's), independently per frame.
* Reported as the mean over repeats and the scene-level bootstrap interval of that mean.

### B-4 Cost of the confidence map

The confidence map costs one single-vehicle forward at the collaborator. Its per-frame time is measured
in the timing probe on this machine, **GPU and CPU separately**, and reported with the round-1 results.
It is additional only if the collaborator would not otherwise run its own detector.

---

## C. Frozen scope

### C-1

Pillar encoder, backbone blocks, AutoEncoder encoders and decoders, fusion module, upsampling blocks and
detection heads: **all frozen, inference mode, the P1 checkpoint unchanged** (its sha256 is in
`round1_lock.json`). Only the transmitted content changes: which blocks are sent.

### C-2

Checked, not assumed: `AttFusion` has **0 trainable parameters** at every feature dimension used
(16, 64, 256), and the checkpoint's 214 state-dict keys contain none for the fusion module. Recorded as
fact; C-1 does not rest on it.

### C-3 Receiver

The receiver rebuilds each branch on the transmitted grid from the mask. **Unsent blocks and elements
lost to failed codewords are both zero-filled** — the dequantised zero code point — then the
AutoEncoder decoders, AttFusion, upsampling and heads run unchanged. This is P1's partial-recovery rule
applied to unsent blocks as well as to failed codewords. A consequence P1 measured carries over: a
zeroed collaborator region still takes softmax weight in AttFusion, and the decoders are
convolutional, so a zero-filled block also changes decoded cells just inside its received neighbours.

---

## D. Evaluation — development split `validate`, scene-equal

### D-1 Regeneration

For **each F variant** (confidence, norm, and every one of the 20 random repeats) the effective
utility is **regenerated in full** with P1's WP5 procedure and P1's §9.3 interpolation, never scaled
from P1's `eff_F`:

* conditions per variant: clean (all K_F blocks arrive), the **8 codeword-loss rates × 4 replicates ×
  2 regimes** (fragment-aware `ideal`, `packet`), and p = 1; P1's C-1 identity control (empty mask
  equals clean) once per frame;
* the codeword draw for (frame `t`, rate index `i`, replicate `r`) is
  `numpy.random.default_rng([20260809, 3, t, i, r]).random(N_cw) < p`, **shared by every variant**, so
  the three rankings and all random repeats see the same channel realisation — a paired design;
  N_cw = 5,256 for every variant (same K_F);
* the `packet` regime uses P1's rule: a failed header codeword loses its whole packet;
* element loss uses P1's straddle rule on the new message's element→codeword map;
* per-frame F1 at IoU 0.5 against the canonical union ground truth, as P1 (`f1_from_boxes`);
* `eff_F` on the **22-cell channel grid** (11 SNR × 2 channel types) by `v2_eff_f.load_nodes` /
  `eff_f` applied to the new CSV — equal-weight replicate means, piecewise linear in raw p, locked
  endpoints, no monotone correction;
* `eff_E` and `eff_L` are P1's, reused unchanged (C-1 leaves E and L untouched).

One unmasked full-F forward per frame supplies the bottlenecks for B-2; its F1 is compared with P1's
`f1_clean` as an identity check of the pipeline.

Outputs go to `projects/ca_tosg_p2/results/`; the tool is `projects/ca_tosg_p2/evaluation/`. Nothing is
written under P1's `results/`.

### D-2 Success — three conditions, all required, pre-registered

* **(i) Budget.** `N_sym,F(K_F)` including all overhead of A-2 ≤ B_available. (Holds by construction
  at K_F = 23; recorded per frame anyway.)
* **(ii) A reproducible gain of F over L where the channel is clean.** Cells: **AWGN at 8, 10, 12,
  14, 16, 18 and 20 dB** (p_cw = 0.00013 at 8 dB, 0 above; `round1_lock.md`). Frames: the **hard-frame
  subset** of `p2_protocol.md` C-5 — the frozen E branch misses ≥ 1 ground-truth object at IoU 0.5 —
  which on validate is **1,889 of 1,980 frames (95.4 %)**, 9 of 9 scenes. Statistic: per frame, the
  mean over the seven cells of `eff_F(conf) − eff_L`; scene-equal mean; **scene-level bootstrap
  (10,000 resamples of the 9 scenes)**, computed as P1 computes its intervals
  (`v2_wp11_heldout_eval._boot_diff`); the condition holds when the **lower end of the 95 % interval
  is above 0**.
* **(iii) Confidence beats random at the same payload.** Same cells, **all frames**: per frame, the
  mean over cells of `eff_F(conf) − mean_r eff_F(random_r)`; same bootstrap; holds when the lower end
  of the 95 % interval is above 0.

The subset in (ii) is nearly the whole split, because the union ground truth contains objects only the
collaborator sees. That is a property of the rule as defined, recorded here before the experiment;
a stricter subset (E misses ≥ 3, ≥ 5, ≥ 8: 74.6 %, 58.8 %, 43.0 % of frames) is **pre-declared as
exploratory only** and cannot become confirmatory in this round. With nine scenes the bootstrap is
coarse; the interval width is reported alongside the bound.

### D-3

F is **not** required to beat L on the full-split average. Any favourable condition found during
development that is not (ii) or (iii) is reported as **exploratory**.

### D-4 Pre-registered wording if round 1 fails

> The combination of the current frozen model and the current sparse-selection scheme did not show a
> benefit under the pre-registered conditions.

It does not say, and may not be read to say, that F cannot be transmitted.

---

## E. Execution record

* **E-1** This file is the lock; the lock commit is recorded in `../README.md`.
* **E-2** After the lock: a 60-frame timing probe of the exact per-frame workload, extrapolated per
  split with the direction of bias stated, reported before D-1 runs; D-1 runs on approval.
* **E-3** No selector training; V2V4Real not started; stop and report when results exist.

---

## Amendment 1 (P2-R5)

**The LOCKED text above is unchanged.** This amendment adds rules and qualifies wording; where it
supersedes a sentence above, it says which. Every number below is derived by `amendment1.py` and
recorded in `amendment1.md`; `amendment1.py --check` fails if this text states different numbers.
The commit that introduces this amendment is recorded in `../README.md`.

**Why an amendment.** The locked design runs 1,453 masked forwards per frame on all 1,980 frames
before anything about the representation is known. P2-R5 asks for a small development diagnostic
first, with the number of random repetitions for the full run set by that diagnostic's timing and
random variability — and set by a rule fixed now, so that it cannot follow whether confidence ranking
wins.

### Am1-A What the locked design repeats

Per frame, each mask runs 1 clean forward, **64 damaged** forwards (8 codeword-loss rates × 4
realisations × 2 regimes, fragment-aware and packet) and 1 forward at p = 1:

| ranking | masks | forwards per frame |
|---|---:|---:|
| confidence | 1 | 66 + 1 identity control = 67 |
| norm | 1 | 66 |
| random | 20 | 20 × 66 = 1,320 |
| **masked total** | | **1,453** |

plus one full-F recording forward and one collaborator single-vehicle forward. The count is checked
against the probe, which executed exactly the derived number for its four variants.

* **Paired damage.** Every ranking and every random mask sees the same number of damaged repetitions
  and the **same codeword-erasure draws**: one draw per (frame, rate, realisation), seeded
  `[20260809, 3, frame, rate, realisation]`, computed once per frame and reused by every variant.
  Every variant sends K_F blocks, so every variant has the same codeword count. What is paired is the
  channel realisation; because codeword *k* carries the *k*-th chunk of each variant's own message, the
  same draw erases different BEV regions under different selections.
* **Random masks are an independent layer**, seeded `[20260809, 2, frame, mask]`, crossed with the
  shared draws.
* **Computed once and reused:** the collaborator's float bottleneck, its confidence map, the codeword
  draws, each variant's clean result (which is also the value at every p_cw = 0 cell), and the E and L
  branches (P1 products, no forward). **Not cached:** the pre-wire features (pillar encoder to
  AutoEncoder encoders) are recomputed in every masked forward; caching them would cut time per
  condition, not the forward count, and would first need an identity check against the full path.
* **Withdrawn:** running the loss sweep on only 4 of the 20 random masks and the clean condition on the
  other 16. It improves the random baseline's precision under a clean channel only and does not replace
  repetitions under a damaged channel.

### Am1-B1 The development experiment runs in two stages

**Stage 1 — development diagnostic.**

* **Frames:** the 60 probe frames (every 33rd validate frame), spanning all 9 scenes but unevenly —
  14 and 22 frames in two scenes, 1 or 2 in three. The scene-equal mean gives a scene with one frame
  weight 1/9; stage 1 is read with that in mind.
* **Rankings:** confidence, norm, and random with **n1 = 8** masks.
* **Cells:** the seven locked cells, AWGN 8–20 dB. Under the locked §9.3 interpolation they depend on
  two nodes only: at 10–20 dB p_cw is exactly 0, so `eff_F` equals the clean F1; at 8 dB p_cw = 0.00013,
  a weight of 0.13 on the p = 0.001 node. Stage 1 therefore runs, per mask, **clean plus p = 0.001 × 4
  realisations × 2 regimes**, 9 conditions — **91 masked forwards per frame** with the identity
  control, 93 executed. Estimated 4.3–6.8 GPU-minutes (`amendment1.md`, bias stated there).
* **F1 is read.** All three rankings are reported. Stage 1 is a development diagnostic, **not a
  significance test**; its intervals are descriptive.
* **Outputs:** for each ranking, clean F1 and F1 at each of the seven cells, beside E and L on the same
  frames; the paired differences confidence − random and norm − random with scene-level bootstrap
  intervals; the width of those intervals and the across-mask standard deviation at n = 2, 4 and 8
  masks (nested: the first 2, the first 4, all 8); and the stage-2 mask count by the rule below.
* **Determinism check:** stage 1 reuses the probe's frames and seeds, so its confidence, norm, random 0
  and random 1 values must reproduce the probe file exactly; this is checked programmatically.

**Stage 2 — full development run.** All 1,980 frames with the locked conditions (66 per mask), and
`n2` random masks, where

> **n2 = the smallest n in {4, 8, 12, 16, 20} with SD_mask / √n ≤ 0.1 × HW_scene; if none, n2 = 20.**

`SD_mask` is the standard deviation (ddof = 1) across the stage-1 random masks of the scene-equal F1 of
random ranking over the seven cells; `HW_scene` is the half-width of the scene-level bootstrap 95 %
interval (10,000 resamples) of that F1 averaged over the stage-1 masks. A Monte Carlo error of at most
0.1 of the scene half-width widens the combined half-width by at most 0.5 %. **The rule uses the random
baseline only; it cannot depend on whether confidence ranking wins.** The GPU cost at each candidate is
in `amendment1.md`; stage 2 runs only on approval.

**Stage-1 results may not change** the ranking rules, the block count, the block size or the
aggregation. A problem found in stage 1 stops the work and is reported.

### Am1-B2 What K_F = 23 shows, and what it does not

K_F = 23 fits the zero-overhead upper bound with a margin of **0.0360 Msym (2.7 %)**. This round
evaluates the value of a sparse representation under an idealised resource upper bound; **it does not
show that a real 802.11bd link meets a 100 ms deadline.** If the representation is effective, the next
stage must re-evaluate it under the smaller budget left after real overhead is deducted. *Supersedes the
last sentence of A-3 above.*

### Am1-B3 The mask assumption

The receiver is assumed to obtain the 55-bit block mask correctly. **Results are conditional on that
assumption; corruption of this metadata is not evaluated.** A deployment analysis must account for how
the mask is protected and what that costs. *Supersedes the justification given in A-2 above* — the
earlier text grounded the assumption in P1's treatment of packet headers, which is not a reason.
`round1_lock.py`'s description of the mask was reworded accordingly and `round1_lock.md` regenerated; no
number changed.

### Am1-B4 L is not truncated — on this data

The observed validate maximum is 51 boxes. **That is not a guarantee on new data**: the detection
post-processing has no cap on predicted boxes (`link_scenarios.md` [S13]), so the bound must be checked
on any new data before the no-truncation statement is reused.

### Am1-B5 The hard-frame subset discriminates little

The C-5 definition stands. At 95.4 % of validate, the subset is close to the whole split and its power
to separate frames is limited. The ≥ 3, ≥ 5 and ≥ 8 missed-object subsets remain exploratory.

### Am1-B6 The 8 ms figure

The per-frame GPU time of the collaborator's additional local detection forward, measured on this
machine (median 7.3 ms; 2.1 s on CPU over 3 frames). **It is not system latency and not full-run
throughput.**

### Am1-B7 Checks

`amendment1.py --check` re-derives every number of this amendment and fails if this text differs;
`round1_lock.py --check` still asserts K_F and the LOCKED status.

### Am1-C Estimate correction

The earlier estimate for the locked design (46.6 GPU-hours on validate) omitted per-condition CPU work —
mask construction and F1 scoring — that the probe residual shows. The corrected range at 20 masks is in
`amendment1.md`; `gpu_estimate_round1.md` is marked superseded.
