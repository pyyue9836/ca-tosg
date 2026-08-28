# CA-TOSG v2 — UNIFIED-BRANCH PROTOCOL (plan A)

**Status: the normative contract for paper v2.** Written and locked *before* any v2 main result
exists. Nothing in this file reports a result; every number below is a protocol parameter (an input
chosen here), a structural constant read from the checkpoint config, or a formula.

**Authority.** Where a generator disagrees with this file, that is a code bug: fix the code. This
file's sections are hashed into `results/manifests/V2_PROTOCOL_MANIFEST.json`; a section may not
change silently, and an amendment is written as an amendment with a reason and a date.

**Freeze relationship.** `docs/STOP_WORK_v1_freeze.md` freezes the v1 manuscript from `400bfb6d`.
This protocol is what the freeze exists to make room for.

---

## 0. Why v2 exists, in one paragraph

v1's three actions came from **different checkpoints**, so the L-vs-F comparison confounded four
things at once: trained weights, fusion architecture, feature codec, and — measured after the fact —
perception field of view (`c54e362`/`cc41927` in `docs/claims.md`; L's late-fusion checkpoint is
configured x ∈ [−70.4, 70.4] while F's is x ∈ [−140.8, 140.8]). No amount of careful wording removes
a confound. Plan A removes it by construction: **one checkpoint, one FOV, one GT, three actions that
differ only in what is transmitted.** Success is therefore defined as *the confound being gone*, not
as a number improving — see §7.

---

## 1. The single checkpoint

| item | value |
|---|---|
| directory | `/mnt/h/opencood_project/pretrained_models/pointpillar_attentive_fusion/pointpillar_attentive_fusion_compression` |
| weights | `latest.pth`, 28,564,117 B, sha256 `897fd516a3548f0a8250b5aab9a619520fba2bcea709bacccfd5eab1cd732344` |
| config | `config.yaml`, 2,672 B, sha256 `9348a20f236ab17c30e5a28e41f805fb1dc33e0eb06b2615f78f38a15bd84b3c` |
| core method | `point_pillar_intermediate` (PillarVFE → PointPillarScatter → AttBEVBackbone) |
| compression | `base_bev_backbone.compression: 2` (AutoEncoder on branches 0 and 1) |

**This checkpoint is used for all three actions and is not retrained, not fine-tuned and not
re-frozen.** Any change to either hash is an amendment-level event.

---

## 2. The three actions

All three run **this** checkpoint. They differ only in what crosses the link.

### E — ego-only

One forward with `record_len = [1]` carrying the ego's own voxels. `AttFusion` self-attends over a
single element, so `softmax` is over one score and `context == value`: the fusion is an **exact
identity**, not an approximation. No message is transmitted. `B_E = 0`.

**RULED (C-1).** E does **not** bypass the checkpoint's internal AutoEncoder: that module is part of
the network's forward path, and bypassing it would break the control condition this whole protocol
rests on — *the same checkpoint, the same network, for all three actions*. E **does** bypass
everything on the communication side: quantisation, packetisation, LDPC and QAM. E transmits no
cooperative-perception payload, so `B_E = 0`.

The 2-bit request codepoint is a **fixed control overhead identical for E, L and F**, and is
therefore not charged to any action's payload.

### L — object-level, per-vehicle detection plus box-level late fusion

**Exactly one ego and one collaborator per frame (B-2).** The ego and the selected collaborator each
run the **same** checkpoint independently (`record_len = [1]`, its own voxels), producing boxes in
its own frame; the collaborator's boxes are transformed into the ego frame and fused at box level.
Nothing about the *network* differs from E — only that a second vehicle is run and its boxes are
combined afterwards.

**The collaborator selection rule, stated in full rather than by name.** Carried over verbatim from
the v1 P0-corrected protocol (`docs/experiment_protocol.md`, Change-log P4-C, subset rule):

> the N nearest collaborators by Euclidean distance between `lidar_pose[0:2]` of collaborator and
> ego — the same distance OpenCOOD's `COM_RANGE = 70` m filter uses — ties broken by ascending CAV
> id; `|C| ≤ N` marks the frame `subset_is_full`. Enforced by an explicit mask, NOT by `max_cav`,
> whose ordering is loader-internal and unpinned.

with **N = 1**. Frames whose `|C| = 0` carry no collaborator and are handled as the v1 protocol
handles them.

**Multi-collaborator is a separate sensitivity analysis, not the main experiment.** Any statement
about N > 1 is labelled as such and never enters a mainline cell.

**Runtime evidence that the lock is in the data path, not only in this document (V2-R6 C-3).** Work
package 2 reports `n_cav` **max 2** on all three splits (mean 2.000 / 1.945 / 1.869), against the
sanity check's mean 3.89 and **max 7** on the same validate frames before the rule was applied. That
is an observed property of the tensors the model received, not a statement about intent.

**Frozen decision parameters (2b). These are protocol constants, not knobs.**

| parameter | value | source |
|---|---|---|
| detection score threshold | **0.20** | `postprocess.target_args.score_threshold` in the checkpoint config — the checkpoint's own default, adopted unchanged |
| NMS IoU threshold | **0.15** | `postprocess.nms_thresh` in the same config |
| box order | `hwl` | same config |
| max boxes per forward | **100** | `postprocess.max_num` |
| cross-vehicle de-duplication | 3D IoU ≥ **0.15**, keep the higher-scoring box | the same NMS threshold, applied once more across the union of per-vehicle boxes; one rule, chosen for consistency with the intra-vehicle rule, not tuned |

**The score threshold is a frozen parameter and it is load-bearing twice over:** it sets the boxes
that get fused *and*, through the per-frame box count, the L payload (§4). Adjusting it after seeing
any result would tune accuracy and bandwidth simultaneously and is therefore an **amendment-level
event**, recorded with a reason and a date, never a quiet change. The same holds for the two IoU
thresholds. **No result-driven tuning of any value in this table.**

### F — feature-level, attentive fusion

The **one** selected collaborator's post-encoder bottleneck tensor is transmitted, and the ego fuses
with `AttFusion` over `record_len = [2]`.

**The network and the fusion mechanism are unchanged from v1; the transmitted bottleneck is not.**
Under the locked v2 transport protocol the bottleneck is **explicitly quantised and dequantised**
(B-4): the F branch actually executes

```
F_float  ->  Q_int8  ->  F_hat_float  ->  fusion / detection
```

and the quantisation loss is a real loss that appears in the reported numbers, not an accounting
assumption.

**What is quantised, stated so it cannot be read two ways (B-4 disambiguation):**

* **Quantised:** the bottleneck tensor that travels **from the collaborator to the ego**, and only
  that.
* **Not quantised:** the **ego's own** features. They never cross a link, so nothing about the
  transport model touches them.
* **Not applicable:** E and L transmit no tensor at all, so quantisation does not arise for them.

**"Per-branch scale", defined once and unambiguously:** the checkpoint's transmitted bottleneck is
the concatenation of three backbone branches (§3.2). *One symmetric int8 scale is calibrated per
branch* — three scalars in total, `s_0`, `s_1`, `s_2` — each computed as
`max(|x|) / 127` over that branch's transmitted tensor across the calibration set. A scale is **not**
per frame, **not** per channel, and **not** per element.

**Calibration and freezing (C-2).** The three scales are calibrated **on validate only**, frozen
before any held-out evaluation, and recorded in the manifest. **`test` and Culver-City never
re-calibrate.** The scales are pre-shared between transmitter and receiver, so they cost **no
per-frame signalling** and are not charged to the payload.

**int8 clean-delivery AP/F1 must be reported, and the quantisation loss listed on its own line**, so
that a reader can separate "what int8 costs" from "what the channel costs".

**If the int8 loss turns out to be large, it is reported as measured.** It is *not* grounds for
changing `w`: the `w ∈ {4, 16}` sensitivity arm stays exactly as it is — an **evaluation-time**
sweep, labelled as not-a-deployment-claim.

#### How the quantiser is actually inserted, and where that is reconciled (C-3)

This belongs in the protocol rather than in a report, because it is precisely the
**billing ≠ pipeline** failure B-4 exists to prevent: an accounting document can say "int8" while the
pipeline runs float, and nobody would see it.

| protocol requirement | implementation site |
|---|---|
| the bottleneck is what crosses the link, so that is what is quantised | `projects/ca_tosg/evaluation/v2_int8_calibrate.py`, `TransmitQuant.patched()` — `AutoEncoder.forward` runs encoder **and** decoder in one call, so the bottleneck is never exposed; the wrapper splits that call and applies `_apply()` between them |
| only the collaborator→ego tensor is quantised | `TransmitQuant._apply()` — operates on rows `x[1:]`; row 0 is the ego and is returned untouched |
| a frame with no collaborator quantises nothing | `_apply()` returns `x` unchanged when `x.shape[0] < 2` |
| branch 2 is transmitted uncompressed and must still be quantised | `patched()` wraps `fuse_modules[2].forward`, quantising where the fusion consumes the tensor |
| three symmetric per-branch scales, `max\|x\|/127` | `TransmitQuant.maxima` → `scales`, one scalar per branch |
| validate-only calibration, frozen before held-out use | `--calib` pass over validate only; written to `results/manifests/V2_INT8_SCALES.json` |
| no weight, module or fusion rule is altered | `patched()` is a context manager that restores every patched attribute in its `finally` |

**Any change to the left column requires a matching change to the right, and vice versa.** This pair
is checked by reading, and it is the reason the pipeline detail is not allowed to live only in a
commit message.

#### Reporting constraint on the int8 result (C-1, C-2)

**Permitted:** *"under this evaluation setting (220 validate frames, ego + one collaborator) no
distinguishable quantisation loss was observed; two of the three metrics show a negative loss, i.e.
the differences lie within noise."*

**Forbidden:** *"int8 is lossless"*, *"quantisation does not affect performance"*, or any other
universal claim. The measurement covers one split, one sample, one configuration.

**The `w ∈ {4, 16}` sensitivity arm may not be reduced or dropped because this result was small.**

---

## 3. Unified FOV, GT, and the real F payload

### 3.1 FOV and GT

| item | value |
|---|---|
| `cav_lidar_range` | x ∈ [**−140.8, 140.8**], y ∈ [**−40, 40**], z ∈ [−3, 1] m |
| voxel size | 0.4 × 0.4 × 4 m |
| anchor grid | H 200 × W 704, 2 anchors |
| GT | the cooperative GT the dataset produces for this range, **identical for all three actions**, scored frame by frame |

One range for all three actions because it is one network. The v1 "common volume" diagnostic
(`tab:common_volume`) exists precisely because v1 could not do this; under v2 it becomes unnecessary
for the mainline and is retained only as a historical comparison.

### 3.2 F payload — measured, not declared (P0-4), and derived from `N_cw` (D-1)

v1 declared a 1.98 Mbit/frame source budget and derived `B_F = 0.99` Msym. **v2 charges the tensor
that actually crosses the link, once per frame** — one collaborator, one message (B-2). From
`results/manifests/P4B_PROBE_pointpillar_compression.json` (forward-hook probe of this checkpoint):

| branch | pre-compression shape | transmitted shape | transmitted elements |
|---|---|---|---|
| 0 | 64 × 100 × 352 | 16 × 25 × 88 | 35,200 |
| 1 | 128 × 50 × 176 | 64 × 25 × 88 | 140,800 |
| 2 | 256 × 25 × 88 | 256 × 25 × 88 (uncompressed) | 563,200 |
| **total, per transmitted message** | 3,942,400 | — | **739,200** |

**`B_F` is derived from the codeword count, never from `(info + header) / rate / log2 M` (D-1).**
The direct route silently ignores LDPC codeword padding, and `N_cw` is the unit the BLER model acts
on: a payload that disagrees with the number of codewords actually transmitted is a payload for a
different experiment. The chain, in order:

```
info_bits = 739,200 elements x w                                   (w = 8, see 3.3)
packetise at P payload bits: n_full = floor(info/P), plus one tail packet of the remainder
    -- the tail packet is NOT padded up to P; only codeword-level padding applies
per packet: bits = payload + H_F
codewords per packet = ceil(bits / K)                              (K = 500)
N_cw = sum over packets
B_F [Msym] = N_cw x n / log2(M) / 1e6                              (n = 1000, M = 16)
```

**Derived values** (`python tools/v2_payload_chain.py` prints every step and refuses to finish if the
identity fails):

| step | value |
|---|---|
| info bits | 5,913,600 |
| full packets (8,000 payload bits each) | 739, plus one tail packet of 1,600 bits |
| header bits (320 × 740 packets) | 236,800 |
| codewords: 8,320-bit packet → ⌈·/500⌉ | 17, × 739 |
| codewords: 1,920-bit tail → ⌈·/500⌉ | 4, × 1 |
| **`N_cw`** | **12,567** |
| **`B_F`** | **3.14175 Msym/frame** |
| the forbidden direct route, for contrast | 3.07520 Msym |
| **codeword-padding gap** | **+0.06655 Msym (+2.164 %)** |

**Identity self-check, run at generation time:** `B_F ≡ N_cw × n / log2 M / 1e6`. If it does not
hold the tool stops, and nothing downstream runs.

### 3.3 Quantisation and packetisation — ruled (C-2)

| parameter | value |
|---|---|
| `w`, bits per feature element | **8** |
| `P`, payload bits per packet | **8,000** |
| `H_F`, header bits per packet | **320** |

**Definition, as ruled:** quantisation is **symmetric int8, per branch**, **calibrated on validate**,
**frozen before the held-out evaluation**, with the scales **pre-shared**, so there is no per-frame
signalling overhead. The header model represents **IP/UDP/application-layer overhead**; it **does not
claim conformance to any particular V2X protocol stack**, and no such claim may be made from it.

*Provenance note (A-1).* These three values were first written in V2-R1 (commit `2c8378d`) under a
column headed **"proposed"** — this executor's own judgement, an MTU-scale packet and an ordinary
header, **not transcribed from any supervisor text**. C-2 has since ruled the same three values. The
`P = 1500 B` / `H_F = 160 bit` pair that V2-R2 carried **never existed in this repository**: a
full-tree sweep for `1500 B`, `12,000 bit` and `160 bit` returns **zero hits**, and no V2-R2 commit
exists on this branch. The divergence was therefore **executor judgement, not a transcription error**.

**`w` is the single most consequential choice in this file** — it scales `B_F` linearly, and it is
amendment-level from here. The v1 declared convention (1.98 Mbit ⇒ 0.9155 bit/element) is a
**historical reference only** and may not be quoted as a v2 payload.

---

## 4. L payload — per frame, same transport chain as F (P0-5, B-1, D-2)

v1 charged a fixed `B_L = 0.024` Msym/frame from a 27-object mean. **v2 charges each frame for the
boxes that frame actually transmits, through the same packet / header / LDPC / QAM chain as F.**

### 4.1 The object container `B_box` (B-1)

| field | bits | note |
|---|---|---|
| position x, y, z | 3 × 16 = 48 | 16-bit fixed point over the stated range |
| dimensions h, w, l | 3 × 12 = 36 | |
| heading (yaw) | 12 | |
| class | 4 | |
| confidence | 8 | |
| position covariance (3 terms) | 3 × 12 = 36 | |
| **planar velocity `v_x`, `v_y`** | 2 × 16 = 32 | ETSI CPM object containers carry velocity; a perceived-object message without it is not the standard container |
| **object ID** | 8 | likewise required to associate an object across messages |
| **`B_box` total** | **184 bits = 23 B** | |

> **Record discipline, stated because it matters more than the number (B-1).**
> **The value did not change; the basis did.** The V2-R1 table listed six field groups summing to
> **144 bits** and labelled the total 184 — an arithmetic error, not a measurement. The correction
> was made by asking *what an ETSI CPM object container must contain*, which supplied planar velocity
> and an object ID, and 144 + 32 + 8 lands back on 184.
> **That coincidence is a coincidence, not a verification.** The two fields were added because the
> standard container has them, not because 184 needed defending.
> This document therefore does not say 184 has been "verified" or "confirmed", and **no field may
> ever be added or removed in order to preserve a number already written.** If a future correction
> moves the total, the total moves.

### 4.2 The chain (D-2)

**L uses the identical transport chain to F.** `H_L` is the same 320-bit header model, and `N_cw,L`
is derived by the same ceiling, so L is charged and delivered on the same terms as F:

```
info_bits   = N_box,t x B_box
packetise at P = 8,000 payload bits (tail packet unpadded)
per packet: bits = payload + H_L,  H_L = 320
N_cw,L      = sum of ceil(bits / K)
B_L,t [Msym] = N_cw,L x n / log2(M) / 1e6
```

`N_box,t` = the boxes the **collaborator's** detector emits at the frozen score threshold (§2), after
intra-vehicle NMS, before cross-vehicle de-duplication.

### 4.3 L has a real frame BLER, and it is computed rather than assumed (D-2)

Because `N_cw,L` comes from the same ceiling as `N_cw,F`, **L has a genuine physical-layer delivery
probability**, and a failed delivery falls back to ego-only exactly as F's does.

| | codewords per message | order of magnitude |
|---|---|---|
| F | **12,567** | ten thousand |
| L | **≈ 9–12** (2 at one box, 40 at a hundred) | ten |

**L's high reliability is a consequence of its codeword count, not an assumption.** This model is in
the **main protocol**. The v1 treatments — all-or-nothing delivery and the `BLER_L ∈ {0.01,0.05,0.10}`
grid — are **demoted to sensitivity arms**, and **P1-6 is closed by this section** (see §12).

### 4.4 Derived scale

From `tools/v2_payload_chain.py`, over the 220 sanity frames, using the ego's single-vehicle box
counts as a **proxy** for the collaborator's — the collaborator arm does not exist yet, and work
package 4 replaces this proxy with the real distribution:

| | value |
|---|---|
| `N_box` mean / range | 22.41 / 5–47 |
| `N_cw,L` mean / range | 9.41 / 3–19 |
| `B_L,t` mean / range | 0.00235 / 0.00075–0.00475 Msym |
| `B_L` mean as a share of the β = 0.10 budget | **0.75 %** |

**The selector's budget uses the per-frame value**, not a split mean: `B_max` is compared against
`B_L,t` for the frame in question. The v1 27-object mean and 110 B ETSI-CPM container are
**historical references** and are not the v2 accounting.

---

## 5. Transport model (P0-6), with partial recovery specified exactly (C-2)

**Main experiment:** fragmentation with partial recovery. The message is carried in `N_cw` LDPC
codewords; each succeeds or fails at the frame's SNR/channel per the Sionna BLER table; the receiver
reconstructs from what arrives.

**The rules, written so no implementation choice is left to whoever writes the code:**

1. The transmitted tensor is **flattened in a fixed order** — branch 0, then 1, then 2, each in
   C-H-W order — and that order is part of this protocol.
2. The int8 bitstream is **packetised in contiguous order**. No interleaving, no reordering.
3. Each failed LDPC information block **zero-fills the positions it carried**. Zero is the correct
   filler for a symmetric int8 code: it is the dequantised value of the zero code point.
4. **CRC is assumed able to identify a failed block**, so the receiver knows *which* positions to
   zero rather than merely that something was lost.
5. Successfully delivered blocks are **dequantised normally**.
6. **Reordering to a favourable position is not permitted.** No scheme may place important channels
   in earlier codewords, or protect them differently, unless it is pre-registered as its own arm.

**Demoted to a sensitivity arm:** all-or-nothing delivery (v1's mainline), where any codeword failure
loses the whole message and the receiver falls back to ego-only. It stays as the pessimistic bound.

**Optional enhancement, costed separately and not in the mainline:** OFDM with a vehicular TDL
channel model in place of the flat block-fading table.

### 5.1 Registered wordings for two transport findings — AMENDMENT, V2-R19, 2026-08-27

**Why an amendment, and why wordings rather than numbers.** This file reports no results and that
rule is not being broken here: what follows are **permitted and forbidden sentences**, the same
kind of object as §7.1's outcome wordings and §12.3's split diagnostic. The numbers they refer to
live in `results/v2/position_effect_level1_validate.json` and
`results/v2/mc_survival_validate.json`, not here. Registered because in both cases a weaker true
statement and a stronger false one differ by a few words, and the stronger one had already been
written once.

**(a) The position effect, level 1, with the amount of loss held fixed.**

Both wordings were fixed before the selection was run (V2-R19 B-3); which one is active is decided
by a **pre-registered sufficiency criterion** — at least 100 equal-loss replicate pairs spanning at
least 30 distinct frames, with a Wilson 95 % lower bound on `P(ΔF1 ≠ 0)` strictly above 0.

> **Permitted when the criterion is met:** *"At a fixed frame and an identical number of lost
> codewords, different loss locations can produce different task outcomes."*

> **Permitted when it is not met:** level 1 as already reported, plus — as a **separate and
> separately-labelled stratum** — the `|ΔN_cw| ≤ 1` layer, together with the explicit statement that
> the equal-codeword sample is too small to exclude the quantity explanation.

**The two strata may never be merged into an "approximately equal amount" conclusion.** Conditioning
exactly and conditioning approximately are different experiments, and pooling them buys sample size
by giving up the thing that makes the strict sentence strict.

**Level 2 — "position matters *more* than amount" — remains NOT ADJUDICATED**, and no threshold for
it is set here. V2-R11 B-2 required that threshold to be pre-registered and it never was; choosing
one now would be choosing it with the numbers already on screen. Either it is pre-registered for a
future run or the claim is dropped.

**(b) Message-level survival at very low codeword loss.**

> **Forbidden:** *"the draw has no variance"*, *"fallback is certain"*, *"the standard deviation is
> zero"* — at any rate where the expected number of surviving messages over the whole Monte Carlo is
> of order one or greater.

> **Permitted:** *"under the fixed Monte-Carlo seed, no surviving message was observed"*, reported
> **with the survival count and the unrounded standard deviation**.

**The rule this encodes, stated once so it generalises: "the reported value displays as 0.00000" is
a statement about display precision; "the random process has no variance" is a statement about the
process.** The second does not follow from the first, and at `p = 0.001` it is false — `q` is small
but not zero, and `N_replay × N_frames × q` is of order one, so observing nothing is an ordinary
draw rather than a certainty. Where the expectation is genuinely many orders below one, fallback
**may** be called effectively certain, stated as an arithmetic consequence of `q` and still
accompanied by the observed count.

---

## 6. Statistics (P0-8)

**The confirmatory unit is the scene, not the frame and not the CSI realisation.** Frames within an
OPV2V scene are consecutive 10 Hz samples of the same traffic and are nowhere near independent;
treating 1980 of them as 1980 samples overstates precision, and v1's 200-realisation CSI replay
compounded it by resampling the channel rather than the data.

* Primary interval: **scene-level (or scene-clustered) bootstrap** over the split's scenes.
* The 200 CSI realisations are **reduced to an expectation within each scene** before the bootstrap —
  they describe channel variability, which is not the population being generalised over.
* Per-frame numbers may still be reported as descriptive detail, labelled as such.

---

## 7. Success criteria — design correctness, not a better number

**It is explicitly forbidden to declare v2 a success or a failure on whether its numbers beat v1's.**
Plan A is a correctness fix. Its deliverable is a comparison that means what it says.

Success = all three of these verified:

1. **One checkpoint.** Every action's boxes trace to the hashes in §1. Verified by a gate that
   re-reads the manifest, not by inspection.
2. **One FOV and one GT.** Every action scored on the same range and the same GT, frame by frame.
3. **Codec and architecture no longer differ across actions.** E and L run the same network as F,
   with the same weights; the only differences are `record_len` and what is transmitted.

### 7.0 Primary success criterion (C-3), in the ruling's own words

> At Test β = 0.20, CA-TOSG must be non-inferior within δ = 0.005 to the budget-feasible comparator
> and reduce its mean realised payload by at least 10%.

Formally, with both arms charged under the v2 per-frame `B_L,t` and the measured `B_F`:

```
non-inferiority:   F1_CA  >=  F1_comp - 0.005      (LCB95 of the paired difference)
payload:          (B_comp_bar - B_CA_bar) / B_comp_bar  >=  0.10
```

**The comparator is the budget-feasible one at the same β.** An over-budget nominal threshold is
**descriptive only** and may not serve as the confirmatory comparator.

> **Registered as a change of primary endpoint (C-3).** v1's confirmatory track compared against the
> **nominal** τ. v2 compares against the **budget-feasible** comparator at the same β.
> **Why this is legitimate:** no v2 result exists yet — not one number has been generated under this
> protocol — so the endpoint is being chosen before, not after, seeing anything.
> **This change makes the criterion harder to meet**, not easier: the budget-feasible comparator
> spends less than the nominal one, so a 10 % reduction against it is a stricter bar.
> **If it is not met, that is reported as measured. Reverting to the nominal comparison is
> forbidden.**

### 7.1 Pre-registered wording for the three outcome cases

Written now, before any result, so the sentence is chosen by the design and not by the outcome.

**Case A — the gain survives.** "Under a single detector, a single field of view and a single ground
truth, per-frame granularity selection retains *[X]* of the feature-level F1 at *[Y]* of its channel
use. Because all four v1 confounds are removed by construction, this is a comparison between
transmission strategies rather than between detectors."

**Case B — the gain shrinks or disappears.** "Under a single detector, a single field of view and a
single ground truth, the advantage of object-level transmission over feature-level transmission is
*[X]*, materially smaller than the v1 estimate of *[X₁]*. The v1 figure was inflated by the branch
confound; the honest statement is that most of what looked like a granularity effect was a detector
and field-of-view effect. The selection framework remains well-posed, and its value must be argued
from *[the surviving axis]* rather than from the retired figure."

**Case C — the sign flips.** "Under the unified branch, feature-level transmission dominates
object-level transmission on *[splits]*, reversing the v1 ordering. We report this as the corrected
result. The v1 ordering is withdrawn, and the selection problem is reframed as *[choosing when the
cheaper message is sufficient]* rather than as *[a claim that it usually is]*."

**Culver-City gets its own sentence in every case (2g):** "The cross-domain gap on Culver-City may
widen under the unified branch, since a single detector no longer lets a per-branch checkpoint absorb
domain shift. Whatever it does, it is reported as measured — it is not a headline cell and it is not
optimised against."

**No case is preferred.** Case B and Case C are publishable findings about a confound, and the paper
says so.

---

## 8. Sanity check (P0-2) — the fuse, run before anything else

Attentive-compression checkpoint, single-vehicle forward, no feature fusion, ≥200 validate frames
sampled across all nine scenes; report AP/F1, per-frame box-count distribution, and the same-frame
cooperative comparison.

**Fuse:** if the single-vehicle AP@0.5 falls below **half** the frozen v1 ego-only AP@0.5 for that
split (`results/main/ego_only_acceptance.csv`, validate = 0.61350, so the floor is **0.30675**), the
detection head does not survive leaving cooperative fusion. **Stop, report a forward-path diagnostic
and candidate adjustments; do not change the forward logic.**

Result: `results/v2/sanity_single_vehicle_validate.{csv,json}`, generated by
`projects/ca_tosg/evaluation/v2_single_vehicle_sanity.py`.

**Scope caveat (B-2).** The sanity check's *cooperative* arm fuses **all** CAVs in the frame (mean 3.89, max 7), because it was written before the single-collaborator lock. It therefore serves **only** to establish that the detection head still works without fusion. **It is not a v2 main result and no number from its cooperative arm may enter one** — the mainline is one ego and one collaborator.

---

## 9. Selector cue set (2c)

> ## ⚠ SUPERSEDED BY AMENDMENT §9.0 (V2-R22, 2026-08-28)
>
> **The decision and the reason below are WITHDRAWN. The reason is not merely reworded — it is
> recorded as factually wrong.** Read §9.0 first; the text immediately following is kept only so the
> superseded claim remains legible next to its correction.

**Decision: the v1 23-column cue set carries over unchanged** — 21 ego-side perception cues, the
estimated SNR, and the channel-type flag (`projects/ca_tosg/models/feature_encoder.py`).

**Reason, one sentence:** the cues describe the *ego's own scene and channel*, not the branch
architecture, so nothing that plan A changes invalidates them — and holding them fixed keeps the v1
and v2 selectors comparable, which is the only way to attribute a change in the result to the branch
unification rather than to a different input set.

### 9.0 AMENDMENT — the cue set is redefined (V2-R22)

**Registration, so the timing is checkable rather than asserted.**

| field | value |
|---|---|
| registered at | **2026-08-28T10:34:12Z** |
| parent commit | **`7f643296de7cb8ed276ca051d9eb1e78d9247aa4`** |
| position in the plan | **before WP11**, and **before any test or Culver-City number has been seen** |
| evidence that the window is open | held-out accuracy is sealed (`results/v2/sealed/`, gate 22); WP3/WP4 have never been run on test or Culver; no selector has been fitted under v2 |
| basis | work package 6 audit, `results/v2/wp6_cue_audit.json` |

This is the written amendment the paragraph above requires. It is registered **before** the products
it governs exist, which is the only condition under which a cue-set change is legitimate.

#### The two facts that force it — separate, and not to be merged

**(i) A ground-truth field was in the cue vector.** `ego_num_objects` is `len(ego['object_ids'])`,
and `object_ids` is built by `generate_object_center()` from `cav_content['params']['vehicles']` —
the dataset's own vehicle annotation, range-filtered. Chain, all read rather than recalled:
`02_extract_cues_and_f1.py:137` → `intermediate_fusion_dataset.py:235` →
`base_postprocessor.py:125`. **This is label leakage:** the selector was conditioned on the count of
objects that are actually there, which is the quantity the detector exists to estimate and which no
deployed ego can know.

**(ii) — WITHDRAWN AS STATED. See the correction immediately below.** The claim entered here was that
nineteen cues were computed over the all-CAV cloud and so leaked post-decision information. **That is
false for the v1 table**, and the measurement that was supposed to quantify it is what disproved it.

> #### Correction to (ii), before this amendment was acted on
>
> **The v1 perception cues were already ego-only.** The D-1 decomposition (§9.2) recomputed the same
> statistics from the ego's own sweep under the v1 range and got the v1 values back **exactly — a
> ratio of 1.000 on all seventeen `pcd_*` cues**, to the last stored digit.
>
> **Why the original claim was wrong:** `origin_lidar` *is* `np.vstack(projected_lidar_stack)` in
> `intermediate_fusion_dataset.py:198` — but the v1 cue table was not built by that class. Its
> extractor loads the **late-fusion** config, so it ran `LateFusionDataset.get_item_test()`, which
> returns a **per-CAV** dict in which each CAV's `origin_lidar` is *its own* `lidar_np`
> (`late_fusion_dataset.py:85`). The `vstack` in that file is at line 251, inside
> `collate_batch_test`, which the extractor never calls. **The definition was read in the wrong
> file for the code path that produced the data** — `num_cavs` ranging 2–7 was the visible sign, and
> it was read as confirmation instead of as the question it was.
>
> **What remains true, and it is enough:** (i) stands, verified twice over. And the cue set must
> still be regenerated, for two other reasons:
>
> * **the field of view changed.** The v1 extractor used the late-fusion `cav_lidar_range`,
>   x ∈ [−70.4, 70.4]; the v2 unified FOV (§3.1) is x ∈ [−140.8, 140.8]. Measured effect on the
>   ego-only cloud: `pcd_max_range` ×1.54, `pcd_front_far_50m` ×1.29, `pcd_std_range` ×1.14, and
>   `pcd_very_far_80m` ×592 (0.26 → 156 points, a bin that barely existed at the old range). The
>   near-field cues and all three densities are unchanged at ×1.000.
> * **the hazard is real prospectively.** v2 runs `IntermediateFusionDataset`, where `origin_lidar`
>   *is* the all-CAV stack. Regenerating cues under the v2 config with `visualize=True` — the
>   obvious way to do it — would have introduced exactly the contamination that was wrongly reported
>   as already present. The `v2_ego_local_23d` generator forecloses it by never building the stack.
>
> **So the amendment stands and its schema is unchanged; one of its two stated grounds does not.**
> Recorded here rather than silently repaired, because an amendment resting on an unexamined premise
> is the failure this whole work package exists to prevent.

**(i) and (ii) were offered as two independent facts.** (i) is confirmed; (ii) is withdrawn and
replaced by the FOV change and the prospective hazard above.

#### The superseded reason, corrected rather than softened (A-3)

> *"the cues describe the ego's own scene and channel, not the branch architecture, so nothing that
> plan A changes invalidates them"*

**The sentence is wrong, but not in the way first reported.** The perception cues *do* describe the
ego's own scene — the correction above establishes that. What the sentence gets wrong is the
inference: *"so nothing that plan A changes invalidates them."* Plan A changes the **field of view**
(§3.1: x ∈ [−140.8, 140.8] against the late-fusion x ∈ [−70.4, 70.4] the cue table was extracted
under), and a scene statistic is defined over a region. `pcd_max_range` moves ×1.54 and
`pcd_very_far_80m` ×592 on the *same* points.

**`num_cavs` is a separate matter and is retired on its own merits:** it ranged 2–7 in v1, encoding
the size of the fused set, which is not available before the request is made.

**The conclusion that rested on the sentence — that the set may carry over unchanged — falls either
way**, and is replaced by §9.2's schema.

#### What is retained

The *comparability* argument in the withdrawn reason was sound in form: holding the input set fixed
is what would let a change be attributed to branch unification. It cannot be honoured here, because
the v1 input set is not admissible. **Comparability is therefore explicitly sacrificed to
admissibility**, and any v1-vs-v2 selector comparison must say so rather than presenting the two as
like-for-like.

### 9.2 The replacement schema — `v2_ego_local_23d`, LOCKED (V2-R22 B, C)

**Still 23 dimensions.** Every one must be computable by the ego **before** it requests anything, from
its own sensor and its own channel estimate. That is the single admissibility rule, and each field
below is admitted by it rather than by resemblance to a v1 field.

| # | field | source | replaces |
|---|---|---|---|
| 1 | `ego_detected_box_count` | the ego-only detector's own output | `ego_num_objects` (GT) |
| 2 | `has_collaborator` ∈ {0,1} | the §2 collaborator-availability rule | `num_cavs` (2–7) |
| 3–19 | `ego_pcd_*` (17) | the **ego CAV's own** LiDAR only | `pcd_*` (all-CAV stack) |
| 20–21 | `ego_origin_lidar_shape_0/1` | the ego CAV's own LiDAR only | same names, new point set |
| 22 | `est_snr_db` | channel estimate | unchanged |
| 23 | `channel_is_rayleigh` | channel type | unchanged |

**`ego_detected_box_count` — definition locked (B-2).** The number of boxes the **ego-only** forward
emits, from the deterministic WP2 products, at the **frozen** score threshold **0.20** and NMS IoU
**0.15** (§2). It is available before any L or F request. It **must not** read the collaborator's
predictions, the ground truth, the fused result, or any transport outcome.

**`has_collaborator` (C-3).** A binary availability flag from the protocol's deterministic rule, not
a point-cloud statistic — it is *action-feasibility* information. `num_cavs` is retired: its v1 range
of 2–7 encodes the size of the fused set, which is post-decision information.

**`ego_pcd_*` — definition locked (C-1).** Computed from the ego CAV's own point cloud in the ego
frame, under the frozen perception range and filtering, with **no** access to
`projected_lidar_stack`, any collaborator's points, or any fused tensor.

**One configuration source, not two (D-3).** The array the cues are computed from is the *same array*
the ego-only forward voxelises: `get_item_single_car()` produces `projected_lidar` — ego points,
self-hits removed, range-filtered by `params['preprocess']['cav_lidar_range']` — and hands the very
same `lidar_np` to `pre_processor.preprocess()`. The cue set therefore describes exactly the scene
action E sees, by construction rather than by a second range constant kept in step by hand.

**Renaming is mandatory and aliases are forbidden (C-2).** `pcd_*` → `ego_pcd_*`. **No old name is
retained as an alias**, because an alias is how the old semantics survives under the new name.

**Retained outside the schema (B-3).** `ego_num_objects` may be kept as an *evaluation* field,
flagged `evaluation_only_gt`, and **may never enter a selector input, a feasibility rule or an oracle
feature**.

#### Consequence for the v1 selector results, ruled rather than left implicit (B-4)

`ego_num_objects` carried **2.54 % Gini importance, rank 5 of 23** in the frozen v1 selector. **That
is not a reason to keep it — it is evidence that the leaking field participated in the decision.**

> **The v1 RF / selector results are hereby DEMOTED TO DIAGNOSTIC. They may not be cited as final
> evidence for a learned policy.** They stay in the record, labelled, under the same history-track
> mechanism as the v1 headline (§14).

#### Pre-registered wording for the three outcomes of removing the leak (D-2)

Fixed now, before the retrained selector exists, so the sentence is chosen by the design:

* **(a) performance essentially unchanged** → "the leaking field did not materially drive the policy";
  reported as measured.
* **(b) performance clearly worse** → "part of the v1 selector's performance rested on information
  that is not available at deployment time." **That is the value of this amendment, not a
  disappointment. Reported as measured, and the cue definitions are NOT reverted.**
* **(c) performance better** → reported as an unexpected result, **not promoted**, and checked for an
  implementation error first.

**No outcome may reopen the cue definitions.** The definitions are settled by admissibility, which is
not a function of the score.

#### Measure before retraining (D-1)

The input point set for the nineteen cues drops from ~52,580 points to a single vehicle's sweep. That
is **a change of statistical object, not a tuning adjustment.** A per-cue distribution comparison —
old versus new, with means, medians, quantiles and the change in the correlation structure — is
**produced and reported before any selector is refitted**. Without it, a later change in selector
behaviour cannot be attributed: "leak removed" and "less information available" would be
indistinguishable.

### 9.3 The oracle's inputs — `eff_F` on the SNR grid, and the payload contract, LOCKED (V2-R25)

Written **before** the v2 grid was built and before any selector was fitted. Every clause is a
separate sentence so it can be located and checked on its own (E-2).

**(a) Replicates are averaged with equal weight, per frame.**
`F̄_t(p_i) = (1/4) Σ_r F_{t,i,r}`. A replicate is a channel realisation, not a member of the
population being generalised over — the same reasoning as §6's reduction of the 200 CSI realisations
before the bootstrap.

**(b) Interpolation is piecewise linear in raw `p`, never in `log p`.**
For `p_i ≤ p ≤ p_{i+1}`: `eff_F,t(p) = (1−w)·F̄_t(p_i) + w·F̄_t(p_{i+1})`,
`w = (p − p_i)/(p_{i+1} − p_i)`.
*Why raw `p`:* the interpolation coordinate must be the variable the interpolated quantity is
roughly linear in, and the damaged fraction of transmitted elements is `≈ p`, not `log p`. `log p`
also diverges at `p = 0` and would need a special case to include the endpoint — **a coordinate
system that needs a patch to cover its own endpoint is the wrong coordinate system.**

**(c) The endpoints are locked, not extrapolated.**
`p = 0` takes the clean F1; `p = 1` takes the measured all-lost F1. `0 < p < 0.001` interpolates
between clean and the 0.001 node; `0.9 < p < 1` interpolates between the 0.9 and 1.0 nodes.
**Extrapolation outside [0, 1] is forbidden.**

**(d) No monotone correction is applied.**
WP5 showed that some masks *raise* a frame's F1 by removing false positives — the observation §5.1(a)'s
strict result rests on. **Forcing monotonicity would use smoothing to erase a finding that has just
been verified**, so the interpolant follows the measured nodes wherever they go.

**(e) The mainline uses the `ideal` fragment-aware partial-recovery regime only.**

**(f) The `packet` regime is generated by the identical linear rule as a separate sensitivity grid.**
It does **not** train the main selector and does **not** participate in model selection; it is a
post-freeze transport sensitivity.

**(g) The message regime does not enter the main oracle, and AP is never interpolated.**
Only per-frame F1 is interpolated. AP is a global-sort statistic, so interpolating it is the same
error as mixing it linearly — **the fourth application of that one rule** (see §5.1, `v2_wp5_message.py`
B-1/B-2, `v2_coordinate_frame_check.py`, and the `tracked_terms.md` row).

#### The payload contract (V2-R25 C)

**(h) The constant payload vector is retired.** v1's `PAYVEC = {E: 0, L: 0.024, F: 0.99}` is not used
under v2.

**(i) Payload is a per-frame matrix:**

| action | `B_{t,a}`, collaborator present | no collaborator |
|---|---|---|
| E | 0 | 0 |
| L | `B_{L,t}` (§4.2, per frame) | 0 |
| F | 3.14175 Msym (§3.2) | 0 |

**(j) Payload is charged for the message that is ATTEMPTED, and is not multiplied by the success
probability.** A failed delivery does not refund the symbols already spent on the channel. This
sentence and `projects/ca_tosg/models/oracle.py` are a **reconciliation pair**: neither may change
without the other, and the pair is checked by reading — the same device §2's C-3 table uses.

**(k) On a frame with no collaborator the requested action may be recorded, but the executed action
is forced to E.**

**(l) The budget is a mean constraint across frames, not a per-frame hard cap.** Under a per-frame
cap any `β < 1` would make F unselectable on every frame and the problem would degenerate.

**(m) Utility is `U_{t,a}(λ) = eff_{t,a} − λ·B_{t,a}`, and ties are broken E ≻ L ≻ F**, pre-registered
here. This continues v1's E-then-L ordering, which is what removed the Rayleigh F-tie defect.

**(n) The three budgets are unchanged: `B̄ ≤ β·B_F`, `β ∈ {0.10, 0.20, 0.30}`.**

#### Implementation self-check, required before the grid is used (D)

The interpolant is a **new modelling layer**, and a wrong one produces a curve that looks entirely
reasonable. It is therefore asserted, per frame and per node, that:

* its value at each of the 8 WP5 nodes equals that node's replicate mean **exactly** (tolerance 1e-12);
* its value at `p = 0` is the clean F1, and at `p = 1` the all-lost F1;
* perturbing any node by one decimal place makes the check **FIRE**.

If the sanity check or the unified branch makes a cue meaningless (for example, a cue defined by a
branch that no longer exists), adding or removing one is permitted **only as a written amendment,
registered before any test or Culver-City number is seen.**

**Two statements that are easy to collapse into one, and must not be (B-3):**

1. **The cue *definitions* carry over unchanged.** That decision is pre-specified above and stands.
2. **Every cue *value* must be recomputed under the v2 branch.** A definition surviving does not mean
   a number survives.

They do not conflict, and the second is not implied away by the first.

### 9.1 Work package 6 is a leakage defence, not bookkeeping (B-1, B-2)

**Carrying the v1 cue values over unregenerated would feed v1 detections into a v2 selector.** That
is data leakage in the ordinary sense — the selector would be conditioning on outputs of a network
the paper says it is not using — and **no gate in this repository would catch it**: the values are
numerically plausible, the column names are unchanged, and every existing check would pass. It is
invisible by construction, which is why it is written here rather than left to care.

**Acceptance criteria for work package 6. All of them must be met before any v2 selector is frozen.**

1. **A per-dimension table, all 23 rows.** Each row marked **`depends`** (its value derives from ego
   or collaborator detection output) or **`independent`**.
2. **The basis for each classification is a code location** — file and symbol where that cue is
   computed. **A verbal assertion is not acceptable evidence**, including one from me.
3. **`depends` rows are recomputed under the v2 branch**, and the old and new distributions are
   **printed side by side**.
4. **`independent` rows carry an invariance demonstration**: either a per-frame comparison showing
   identical values from identical inputs, or a code-level argument that the computation cannot
   reach a detection output. **"It looks like a channel quantity" is not a demonstration** — the
   channel cues are the *likely* independents, not the *assumed* ones.
5. **A dimension that cannot be classified stops the batch.** It is not carried over by default; the
   default is to stop and report.
6. **The table enters the manifest** and is a **precondition of the selector freeze**.

**Why the strictness is proportionate:** P0-3's invalidation list does not mention the cue vector at
all (§11.3), so nothing upstream of this section would have flagged it. The one list that does — work
package 6 — states it in a single clause. This subsection is that clause made enforceable.

---

## 10. Split discipline, budgets and the payload criterion

* **validate** is the only split anything is fitted, tuned or selected on.
* **test** and **Culver-City** are one-shot frozen evaluations.
* `δ = 0.005` — unchanged from v1.

### 10.1 Budgets are normalised (B-3)

**The three budgets are β = B_max / B_F ∈ {0.10, 0.20, 0.30}**, and the absolute Msym values are
*derived* from the measured `B_F` and printed alongside:

| β | `B_max` = β × `B_F` |
|---|---|
| 0.10 | 0.31418 Msym/frame |
| 0.20 | **0.62835 Msym/frame** |
| 0.30 | 0.94252 Msym/frame |

**The primary cell is named "Test at β = 0.20".** It is never written as a literal `B_max = 0.20`
Msym — under v2 that string denotes nothing. v1's absolute tier values {0.10, 0.20, 0.30} Msym are
**historical references**; they are numerically the same digits as the β values and mean something
different, which is precisely why the naming has to be strict.

### 10.2 The ≥ 10 % payload criterion — retained, re-based (C-3)

Retained at **10 %**, with the comparison against the **budget-feasible comparator at the same β**:

```
(B_comp_bar - B_CA_bar) / B_comp_bar  >=  0.10
```

Both arms are charged with the v2 **per-frame** `B_L,t` and the **measured** `B_F`. An over-budget
nominal threshold is a **descriptive** contrast only and may not act as the confirmatory comparator.
The full primary criterion is §7.0.

---

### 10.3 Frames with no collaborator — ruled (V2-R6 B)

**The fact.** After the single-collaborator rule, some frames have `|C| = 0`: **validate 0/1980
(0 %), test 119/2170 (5.48 %), Culver-City 72/550 (13.09 %)**. On those frames L and F are
*physically unavailable* — there is no one to receive from — and the action space degenerates to
`{E}`.

**v1 already had a convention, and it is adopted rather than re-invented (B-2).** The v1 N=1
per-frame caches keep **every** frame, and on a no-collaborator frame the cooperative outcome
degenerates to the ego-only one. Checked against the data, not inferred: in
`data/p2/dataset_{split}_n1.csv`, `late_f1 == ego_f1` on **all 119** test and **all 72** Culver-City
no-collaborator frames — a perfect correspondence, matched frame by frame against the v2
`has_collab` flag. (On test, 215 frames satisfy `late_f1 == ego_f1` in total; the other 96 are
coincidental equality with a collaborator present, which is why the correspondence had to be checked
per frame and not by counting.)

**RULING: (a) full-frame accounting.** Every frame is included in the frame-weighted mean, on every
split, for every arm. This matches v1, so **no amendment is required for the frame set**.

**What v2 changes, and it is a fix rather than a carry-over.** Under v1's *fixed* `B_L = 0.024`, a
frame with no collaborator that selected L still **paid for a message that could not be sent**. v2's
per-frame accounting removes that artefact without a special case: with `N_box,t = 0` the chain of
§4.2 gives `N_cw,L = 0` and therefore **`B_L,t = 0`**, automatically. For F the same must be stated
explicitly, because `B_F` is a constant: **on a frame with `|C| = 0`, `B_F = 0`.**

So, on a no-collaborator frame:

| | value |
|---|---|
| realised outcome of E, L and F | the **ego-only** outcome — identical, because nothing is received |
| `B_E`, `B_L,t`, `B_F` | **all 0** — nothing is transmitted, so nothing is charged |
| action label | whatever the policy emits; the *physics* is unaffected by the label |

**Both accountings are reported, always (B-3).** The **full-frame** figure is primary; the
**collaborator-available** figure (restricted to `|C| ≥ 1`) is reported alongside it, and **the
difference is stated explicitly**. Neither is allowed to appear without the other.

**One definition, all comparators (B-4).** This applies identically to CA-TOSG, the SNR threshold τ,
the two- and three-scalar hand rules, the oracle, and any external baseline. **No arm may use a
different frame set from another arm it is compared against.** A comparison across different frame
sets is not a comparison.

### 10.4 A cross-domain risk to be checked, written before the numbers exist (B-5)

The no-collaborator share is **5.48 % on test against 13.09 % on Culver-City — a factor of 2.4.**
Under full-frame accounting those frames cost zero for every arm, so **part of Culver-City's apparent
payload saving will come from collaborator unavailability rather than from policy choice.**

This is a **precondition on P1-3's wording**, recorded now so it cannot be discovered later and
described as always having been understood. After the freeze, the check is mechanical: report the
Culver-City payload with and without the `|C| = 0` frames, and if the gap is material, say plainly
that the domain has fewer collaborators rather than that the policy transfers better.

---

## 11. Regeneration — P0-3's invalidation list, the twelve work packages, and the mapping

### 11.1 P0-3 — the authoritative list of what plan A invalidates (supervisor verbatim)

> **P0-3：所有方案A结果必须完整重冻，不能局部替换**
>
> 方案A之后，以下全部旧结果失效：
>
> - E/L/F逐帧F1和AP
> - oracle labels
> - λ
> - RF selector
> - SNR threshold
> - two-/three-scalar rule
> - action ratios
> - payload
> - 200次replay
> - bootstrap CI
> - Test和Culver-City结果
> - 所有headline表格和曲线
> - Where2comm比较
>
> 必须把它们捆在一次完整重冻里完成，不能保留"看起来变化不大"的旧数字。

**Attribution corrected against the delivered text (B-1).** V2-R3 flagged that this repository's
thirteen rows were *not* P0-3 and might or might not match. The original has now been supplied and
**diffed row by row: 0 of 13 rows match.** They are different lists that happened to share a length
— P0-3 enumerates *what is invalidated*, the V2-R1 table enumerated *a dependency order for
re-deriving things*. **P0-3 is authoritative and replaces it.** The superseded table is kept at
§11.4, labelled executor-derived, not deleted and not cited.

**The binding instruction in P0-3 is the last line, not the list:** one complete re-freeze, bundled.
No item may be kept because it "looks like it didn't change much".

### 11.2 The twelve work packages (supervisor verbatim)

| # | work package | scope |
|---|---|---|
| 1 | Checkpoint and forward invariants | 验证三动作使用相同 checkpoint hash、FOV、score threshold 和 NMS。 |
| 2 | Per-agent single-vehicle inference | 为 Validate、Test、Culver 生成每辆车的独立检测和中间 bottleneck。 |
| 3 | E action products | 生成统一 checkpoint 下的 ego-only boxes、F1 和 AP。 |
| 4 | L action products | 对锁定的单个 collaborator 进行 box transformation、cross-vehicle NMS 和 late fusion。 |
| 5 | F action products | 生成 int8 quantise/dequantise、完整投递和部分投递条件下的 feature fusion 结果。 |
| 6 | Cue regeneration and verification | 重新生成或逐项验证 23 维输入。定义保持不变，但所有依赖新 ego 检测输出的 cue 值必须更新。 |
| 7 | Payload products | 生成逐帧 N_box,t、B_L,t、固定 B_F、packet 数量、header 和控制开销说明。 |
| 8 | Transport products | 生成 codeword BLER、fragment mapping、partial recovery、L/F delivery 和 all-or-nothing sensitivity。 |
| 9 | Oracle and feasibility products | 重新生成 E/L/F utility、feasible mask 和 oracle labels。 |
| 10 | Validate-only model selection and freeze | 完成 LOSO、λ、RF、threshold、hand-rule 和 manifest 冻结。 |
| 11 | Frozen held-out evaluation | Test 和 Culver 一次性重放、200 次 CSI 期望、scene-level bootstrap 和所有敏感性。 |
| 12 | External baseline and publication products | 重跑统一 GT/FOV 的 Where2comm 及选定 adaptive baseline，最后生成表格、图片、claims 和 v2 门禁。 |

*The `inferred` scope column V2-R1 carried is superseded by the text above and is retained at §11.4.*

### 11.3 Mapping — and what each list misses that the other catches

**P0-3 row → work package that produces its replacement**

| P0-3 row | work package |
|---|---|
| E/L/F 逐帧 F1 和 AP | 3, 4, 5 |
| oracle labels | 9 |
| λ | 10 |
| RF selector | 10 |
| SNR threshold | 10 |
| two-/three-scalar rule | 10 |
| action ratios | 11 (realised mix from the replay; the *oracle* mix is 9) |
| payload | 7 |
| 200 次 replay | 11 |
| bootstrap CI | 11 |
| Test 和 Culver-City 结果 | 11 |
| 所有 headline 表格和曲线 | 12 |
| Where2comm 比较 | 12 |

**Every one of P0-3's thirteen rows maps to a work package.**

**Work package → P0-3 row**

| work package | P0-3 row |
|---|---|
| 1 Checkpoint and forward invariants | **none** |
| 2 Per-agent single-vehicle inference | **none** |
| 3, 4, 5 E / L / F action products | E/L/F 逐帧 F1 和 AP |
| 6 Cue regeneration and verification | **none** |
| 7 Payload products | payload |
| 8 Transport products | **none** |
| 9 Oracle and feasibility products | oracle labels |
| 10 Validate-only selection and freeze | λ, RF selector, SNR threshold, two-/three-scalar rule |
| 11 Frozen held-out evaluation | action ratios, 200 次 replay, bootstrap CI, Test 和 Culver-City 结果 |
| 12 External baseline and publication | 所有 headline 表格和曲线, Where2comm 比较 |

**Four work packages map to no P0-3 row: 1, 2, 6 and 8.** That is not a defect in either list — it
is the reason both are kept. P0-3 enumerates **old results that die**; the packages enumerate **work
that must happen**. Three of the four unmatched packages produce things v1 never had (per-agent
bottlenecks, transport products under partial recovery, run-time invariants), so they *cannot* appear
on a list of invalidated v1 outputs.

**Package 6, cue regeneration, is the one that matters (E).** It is unmatched for a different reason:
the 23-dimensional cue vector **did** exist in v1 and P0-3 does not list it — yet package 6 states
that every cue value depending on the new ego detections must be updated. **A cue set carried over
unregenerated would silently feed v1 detections into a v2 selector.** V2-R3 predicted this gap
against the derived list; it survives against the verbatim one. Flagged here permanently.

### 11.4 Superseded: the V2-R1 executor-derived dependency order

Kept per B-1. **Not authoritative, not to be cited.** Written by this executor in V2-R1 as a
re-derivation order before P0-3's text was available; 0 of its 13 rows match P0-3.

<details>
<summary>executor-derived order (superseded)</summary>

1 per-vehicle detections, all splits · 2 E boxes/F1/AP · 3 L boxes after box-level fusion ·
4 F boxes/F1/AP · 5 per-frame `N_box,t` · 6 `B_L,t` per frame · 7 `B_F` · 8 BLER table / `N_cw` ·
9 oracle labels · 10 selector training + LOSO + freeze · 11 replay + `tau_feasible` + fixed
references · 12 figures and tables · 13 Where2comm arm

</details>

---

## 12. Conditional branches P1-1 … P1-8, and stage-5 rewrite items P2-1 … P2-6

**Delivered in V2-R4 and entered verbatim.** V2-R3 stopped here because the tables had not been
supplied; the instruction has since acknowledged that as an instruction defect and provided them.

### 12.1 P1 — conditional branches (supervisor verbatim)

| ID | 触发条件 | 预先规定的处理 |
|---|---|---|
| P1-1 | 冻结 selector 的 ρ_E 仍接近 0，而 oracle 显著选择 E | 报告 E-action collapse；检查 label imbalance 和 training objective。若不修改协议则不声称有效学习三动作，只称 E 为可用但很少触发的安全动作。 |
| P1-2 | RF 没有形成三个不同预算点，或不满足非劣效/节省标准 | 不声称 learned selector 优于简单规则；将贡献限定为 granularity-control framework，并按实测结果说明 threshold 或 hand rule 是否已经足够。 |
| P1-3 | Culver-City 未通过 δ=0.005 | 只声称通信节省迁移；不得声称 accuracy preservation 跨域迁移。 |
| P1-4 | 第二 backbone 或 JSCC 只在 in-sample 有效 | 仅作为 boundary/exploratory evidence，不进入摘要和核心贡献。 |
| P1-5 | channel-type indicator 对结果占主导，或误判后明显退化 | 增加 channel-type 误判/去除 channel-type 敏感性；不得把完美 AWGN/Rayleigh 标签描述为天然可部署输入。 |
| P1-6 | L 的实际 BLER 不可忽略 | 使用 L 的真实 packet size 和 PHY 计算 delivery；Fixed L 不得继续被称为绝对可靠。 |
| P1-7 | selector 之外的总延迟未测量 | 只报告 selector-only latency；不得声称完整系统满足实时约束。 |
| P1-8 | 多 collaborator 超出预算 | 第一篇文章明确限定 single ego–single collaborator；多车调度留给下一课题。 |

**P1-6, v2 execution note (not supervisor text).** The v2 main protocol already computes L's delivery
from its **real packet size through the same PHY** (§4.3, D-2) rather than assuming a `BLER_L`, so
this trigger is **expected not to hold** under v2. **If the measurement says otherwise it is reported
as measured** — the expectation does not license skipping the check.

**P1-8 is already discharged by the protocol, not merely planned for:** §2 locks the mainline to one
ego and one collaborator, with the selection rule quoted in full.

### 12.2 P2 — stage-5 rewrite list (supervisor verbatim; archived, not executed now)

| ID | 重写项 |
|---|---|
| P2-1 | 重写摘要，只保留问题、方法、E/L/F、核心 payload–performance 结果和机制结论。 |
| P2-2 | 贡献压缩为三项：问题形式化、receiver-driven 方法、统一协议下的实验发现。 |
| P2-3 | 删除主文中的 retired、withdrawn、committed product、in the record 等内部审计语言，移入 changelog 或 supplementary。 |
| P2-4 | 重写 Conclusion，只回答做了什么、证明了什么、在哪些条件下成立。 |
| P2-5 | 将 baseline 分为 fixed policy、internal decision rule、feature-content/codec baseline、adaptive policy 和 oracle。 |
| P2-6 | 修正文档问题：补齐 supplementary 标题和作者、移走 CSV 清单、修复重复命令/小写开头、统一标准引用，并删除 "safety certification"、"lightweight real-time" 等证据不足的措辞。 |

**Not executed now.** The v1 manuscript is frozen (`docs/STOP_WORK_v1_freeze.md`); P2 is the stage-5
rewrite of the **v2** manuscript and runs after the re-freeze lands.

**Superseded prose.** V2-R1's paragraph-form placeholder for this section is retired to the history
track: not deleted, not quoted.

### 12.3 D-3 — the E-collapse diagnostic, strengthened before any result

This strengthens **P1-1** above; it does not replace it. Under v2's accounting `B_L` is about
**0.75 %** of the β = 0.10 budget (§4.4), so E saves only that remaining fraction relative to L.
**`ρ_E ≈ 0` therefore has an economic explanation and is not by itself evidence that the selector
failed to learn E.**

The diagnostic is **split into two questions whose wording is fixed now**, reported **separately**:

* **(i) A learning question.** *On the subset of frames where L is actually harmful — where the
  realised ego-only outcome exceeds the realised object-level outcome — does the selector choose E?*
  Reported as: "On the N frames where L is harmful, the frozen selector chose E on X %."
* **(ii) A design question.** *On the remaining frames, is `ρ_E ≈ 0` simply the consequence of E's
  saving being negligible?* Reported as: "Elsewhere, E saves at most `B_L,t` — a mean of Y % of the
  β budget — so its non-selection is a cost-scale consequence rather than a learning outcome."

**Merging these into one sentence such as "the selector did not learn to use E" is forbidden.** Note
that P1-1's own pre-specified handling — "只称 E 为可用但很少触发的安全动作" — is the *conclusion*
that follows if (i) shows a learning problem; if only (ii) applies, the finding is different and must
be said differently.

### 12.4 D-4 — what β means physically, to be verified before it is written

**Observation, recorded now for possible use in the stage-5 rewrite:** L is nearly free and F is
expensive, so to first order **β is the allowed F-request rate**.

**This is an interpretive statement and it is not yet evidence.** It may enter the manuscript **only
after** it is checked against the frozen products, by comparing realised `ρ_F` against β. **Writing
it first and verifying afterwards is forbidden**; this paragraph exists so the claim is on record as
*unverified* rather than arriving later as if it had always been known.

---

## 13. External baseline arm (P0-7) — pre-registration placeholder

Candidates: **ML-Cooper**, **SmartCooper**. No GPU is spent on either until a **selection report**
exists covering, per candidate:

1. reproducibility — is there a runnable release, with weights, at a stated commit?
2. code availability and licence;
3. feasibility of the **seven unified elements** — same checkpoint family, same FOV, same GT, same
   score threshold, same fusion rule, same transport model, same statistical unit. A baseline that
   cannot be brought onto all seven re-creates the confound and is not worth running.

The report comes first, the GPU after, in a separate batch and on Josh's approval.

---

## 14. Disposition of the v1 results

v1 is **not withdrawn and not deleted.** Every v1 product, table, figure and change-log entry stays
exactly where it is, and the manuscript is frozen (`docs/STOP_WORK_v1_freeze.md`).

When v2's re-freeze lands, the v1 headline moves to a **history track**: labelled in place as the
pre-unification estimate, with the confound named, and never mixed into a v2 sentence. The mechanism
is the one this repository already uses for retired quantities — `tests/retired_products.md` plus a
NOT-QUOTABLE banner — extended to a `v1-headline` class.

**Gate system follow-through:** the 21 checks stay as they are for the frozen v1 manuscript. v2
products get their own gates as they land; no v1 gate is deleted, and none is added (per the
stop-work order). When the v2 manuscript replaces the v1 one, each gate is re-pointed or retired
explicitly, one at a time, with the reason recorded — not migrated in bulk.

---

## 15. Wording audit: "pre-registered" (P0-9)

**Finding to act on:** the repository uses "pre-registered" throughout, and for most entries the
honest claim is weaker — the decision was fixed and frozen before the final held-out evaluation, but
there is no external timestamped registration.

**Rule:** replace "pre-registered" with **"pre-specified and frozen before the final held-out
evaluation"** everywhere, *except* where a genuine timestamped record exists, in which case the
original word may stand and the record is cited.

**Every retained use must carry this six-tuple**, stored in the manifest:

| field | meaning |
|---|---|
| `manifest_commit` | the commit that froze the decision |
| `freeze_timestamp` | when |
| `primary_cell` | test @ B_max = 0.20 |
| `delta` | 0.005 |
| `success_criterion` | §7, by reference |
| `first_test_run_timestamp` | when a held-out number was first computed |

The audit runs over `paper/`, `docs/`, `tests/` and `projects/`. **It does not run yet**: the v1
manuscript is frozen, so the paper-side rewrite waits for the v2 rewrite. What happens now is the
inventory — count and locate every use — so the rewrite is mechanical later.

---

## 16. Lock status

| section | locked | note |
|---|---|---|
| 1 checkpoint | **LOCKED** | hashes recorded |
| 2 actions | **LOCKED** | C-1 rules E; B-2 locks one collaborator with the rule quoted in full; B-4 locks int8 |
| 3 FOV/GT/`B_F` | **LOCKED** | C-2 rules `w`/`P`/`H_F`; D-1 derives `B_F` from `N_cw` |
| 4 `B_L` | **LOCKED** | B-1 container; D-2 same transport chain, real BLER |
| 5 transport | **LOCKED** | partial recovery specified rule by rule; §5.1 registered wordings added by amendment, V2-R19, 2026-08-27 |
| 6 statistics | **LOCKED** | scene-level |
| 7 success criteria | **LOCKED** | C-3 primary criterion verbatim; endpoint change registered |
| 8 sanity | **LOCKED** | fuse held; all-CAV caveat recorded |
| 9 cue set | **LOCKED** | v1 set carried over |
| 10 budgets and criterion | **LOCKED** | B-3 β tiers; C-3 re-based ≥ 10 % |
| 11 regeneration | **LOCKED** | P0-3 verbatim + twelve packages verbatim + full mapping (V2-R4) |
| 12 P1/P2 | **LOCKED** | both tables entered verbatim (V2-R4) |
| 13 external arm | **LOCKED as a placeholder** | report before GPU |
| 14 v1 disposition | **LOCKED** | |
| 15 wording audit | **LOCKED as a rule**, not yet executed | |

**No mainline GPU runs while any section above reads NOT LOCKED.** As of V2-R4 there are none:
every declared section is LOCKED, and mainline Tier A is released to run.
