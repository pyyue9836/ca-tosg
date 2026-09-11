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
