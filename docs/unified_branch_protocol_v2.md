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

**Decision: the v1 23-column cue set carries over unchanged** — 21 ego-side perception cues, the
estimated SNR, and the channel-type flag (`projects/ca_tosg/models/feature_encoder.py`).

**Reason, one sentence:** the cues describe the *ego's own scene and channel*, not the branch
architecture, so nothing that plan A changes invalidates them — and holding them fixed keeps the v1
and v2 selectors comparable, which is the only way to attribute a change in the result to the branch
unification rather than to a different input set.

If the sanity check or the unified branch makes a cue meaningless (for example, a cue defined by a
branch that no longer exists), adding or removing one is permitted **only as a written amendment,
registered before any test or Culver-City number is seen.**

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

## 11. Regeneration — twelve work packages, mapped to thirteen product rows (E)

### 11.1 The twelve work packages

Titles recorded verbatim from the V2-R3 instruction. **Their bodies are not in this repository** —
the instruction gave titles only — so each carries the scope this executor infers, clearly marked as
inferred. **The supervisor's package bodies replace the inferred column when pasted in.**

| # | work package (verbatim title) | inferred scope — replace with the supervisor's text |
|---|---|---|
| 1 | Checkpoint and forward invariants | hashes of §1 asserted at run time; `record_len` semantics; the AttFusion identity at `record_len=[1]` |
| 2 | Per-agent single-vehicle inference | ego and the selected collaborator, each alone, all three splits |
| 3 | E action products | boxes, F1, AP from the ego-alone forward; `B_E = 0` |
| 4 | L action products | collaborator boxes, transform, box-level fusion, per-frame `N_box,t` |
| 5 | F action products | int8 quantise → transmit → dequantise → attentive fusion; clean-delivery AP/F1 and the quantisation loss line |
| 6 | Cue regeneration and verification | the 23-column cue set recomputed on the unified branch and verified against §9 |
| 7 | Payload products | `B_F` from `N_cw`; per-frame `B_L,t`; β tiers; the identity self-check |
| 8 | Transport products | fragmentation + partial recovery per §5; BLER per codeword; the all-or-nothing sensitivity |
| 9 | Oracle and feasibility products | E/L/F argmax under the feasibility mask, on the new payload axis |
| 10 | Validate-only model selection and freeze | LOSO, λ\*, per-β selector freeze, manifest |
| 11 | Frozen held-out evaluation | test and Culver-City, one shot, scene-level bootstrap |
| 12 | External baseline and publication products | §13 arm, then tables and figures |

### 11.2 The thirteen product rows

**Provenance correction, and it matters (E).** The instruction calls these "P0-3 的 13 行 verbatim
产物清单". **They are not verbatim P0-3.** These thirteen rows were written by *this executor* in
V2-R1 as a derived dependency order, and V2-R1 said so in the same breath. They are kept here because
E asks for them to be kept, and because a dependency order is genuinely useful — but they must not be
cited as the supervisor's text. **If P0-3's actual thirteen lines differ, paste them and this table
is replaced.**

| # | product | why it must be re-derived |
|---|---|---|
| 1 | per-vehicle detections, all splits | each vehicle through the unified checkpoint |
| 2 | E boxes/F1/AP | new network for this action |
| 3 | L boxes after box-level fusion | new detector + new fusion rule |
| 4 | F boxes/F1/AP | same mechanism, re-scored on the unified GT, now with real int8 |
| 5 | per-frame `N_box,t` | the input to the L payload |
| 6 | `B_L,t` per frame | §4 |
| 7 | `B_F` | §3.2, measured tensor, via `N_cw` |
| 8 | BLER table / `N_cw` per message | `N_cw` changes with the payloads above |
| 9 | oracle labels (E/L/F argmax under the mask) | every input to the argmax moved |
| 10 | selector training + LOSO + freeze, per budget | new labels, new payload axis |
| 11 | replay + `tau_feasible` + fixed references | new products |
| 12 | figures and tables | last, from the above |
| 13 | Where2comm arm | must move to the same GT and FOV, or the comparison re-acquires the confound |

### 11.3 Bidirectional mapping — no row unmatched

| work package | product rows |
|---|---|
| 1 Checkpoint and forward invariants | — (an invariant, not a product; it gates rows 1–4) |
| 2 Per-agent single-vehicle inference | 1 |
| 3 E action products | 2 |
| 4 L action products | 3, 5 |
| 5 F action products | 4 |
| 6 Cue regeneration and verification | **— no product row exists** |
| 7 Payload products | 6, 7 |
| 8 Transport products | 8 |
| 9 Oracle and feasibility products | 9 |
| 10 Validate-only model selection and freeze | 10 |
| 11 Frozen held-out evaluation | 11 |
| 12 External baseline and publication products | 12, 13 |

| product row | work package |
|---|---|
| 1 | 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 4 |
| 6 | 7 |
| 7 | 7 |
| 8 | 8 |
| 9 | 9 |
| 10 | 10 |
| 11 | 11 |
| 12 | 12 |
| 13 | 12 |

**Every one of the thirteen product rows maps to a work package. One work package — 6, cue
regeneration and verification — maps to nothing**, because the thirteen-row list omitted it. That
omission is the mapping's finding, and it is why the two lists cannot replace each other: the work
packages are an implementation decomposition, the product rows are a dependency order, and each
catches something the other misses.

**Package 1 deliberately has no product row**: it is an invariant asserted at run time, not a file.

---

## 12. Conditional branches P1-1 … P1-8, and stage-5 rewrite items P2-1 … P2-6

**BLOCKED — the two tables are not in this repository.** F instructs that the supervisor's two tables
be entered *verbatim, row by row*. The V2-R3 message names them but does not contain them, and no
earlier message did either. **Transcribing tables I have not been given would be fabrication**, which
is the one thing a pre-registration must never contain. The tables below therefore carry the correct
shape and no invented content.

**This section stays NOT LOCKED, and per §16 that blocks mainline GPU.** It is the only thing
blocking it.

| id | trigger condition | pre-specified handling |
|---|---|---|
| P1-1 | **TEXT REQUIRED** — but see the D-3 strengthening below, which applies to it whatever the row says | **TEXT REQUIRED** |
| P1-2 … P1-5 | **TEXT REQUIRED** | **TEXT REQUIRED** |
| P1-6 | **TEXT REQUIRED** | **TEXT REQUIRED**, plus the standing addition below |
| P1-7, P1-8 | **TEXT REQUIRED** | **TEXT REQUIRED** |

**P1-6, standing addition (F).** The v2 main protocol already gives L a **real physical-layer
delivery** derived from its codeword count (§4.3, D-2), rather than an assumed `BLER_L`. **This
trigger condition is therefore expected not to hold under v2. If it does hold anyway, that is
reported as measured** — the expectation does not license ignoring it.

| id | stage-5 rewrite item (not executed now) |
|---|---|
| P2-1 … P2-6 | **TEXT REQUIRED** |

**Superseded prose (F).** V2-R1's paragraph-form placeholder for this section is retired to the
history track: not deleted, not quoted.

### 12.1 D-3 — the E-collapse diagnostic, strengthened before any result

Under v2's accounting `B_L` is about **0.75 %** of the β = 0.10 budget (§4.4). E saves only that
remaining fraction relative to L. **So `ρ_E ≈ 0` has an economic explanation and is not, by itself,
evidence that the selector failed to learn E.**

The P1-1 diagnostic is therefore **split into two questions, whose wording is fixed now**, and whose
conclusions are **reported separately**:

* **(i) A learning question.** *On the subset of frames where L is actually harmful — where the
  realised ego-only outcome exceeds the realised object-level outcome — does the selector choose E?*
  Reported as: "On the N frames where L is harmful, the frozen selector chose E on X %."
* **(ii) A design question.** *On the remaining frames, is `ρ_E ≈ 0` simply the consequence of E's
  saving being negligible?* Reported as: "Elsewhere, E saves at most `B_L,t` — a mean of Y % of the
  β budget — so its non-selection is a cost-scale consequence rather than a learning outcome."

**Merging these into one sentence such as "the selector did not learn to use E" is forbidden.** They
are different findings with different remedies, and v1 conflated exactly this kind of pair once
already (the R63/R64 feasible-set correction).

### 12.2 D-4 — what β means physically, to be verified before it is written

**Observation, recorded now for possible use in the stage-5 rewrite:** L is nearly free and F is
expensive, so to first order **β is the allowed F-request rate** — a budget of β × `B_F` buys about β
frames' worth of feature requests per frame.

**This is an interpretive statement and it is not yet evidence.** It may enter the manuscript **only
after** it is checked against the frozen products, by comparing realised `ρ_F` against β. **Writing
it first and verifying afterwards is forbidden**; this paragraph exists so that the claim is on
record as *unverified* rather than arriving later as if it had always been known.

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
| 5 transport | **LOCKED** | partial recovery specified rule by rule |
| 6 statistics | **LOCKED** | scene-level |
| 7 success criteria | **LOCKED** | C-3 primary criterion verbatim; endpoint change registered |
| 8 sanity | **LOCKED** | fuse held; all-CAV caveat recorded |
| 9 cue set | **LOCKED** | v1 set carried over |
| 10 budgets and criterion | **LOCKED** | B-3 β tiers; C-3 re-based ≥ 10 % |
| 11 regeneration | **LOCKED** | twelve packages, thirteen rows, mapping complete; package bodies marked inferred |
| 12 P1/P2 | **NOT LOCKED** | the supervisor's two tables are not in this repository |
| 13 external arm | **LOCKED as a placeholder** | report before GPU |
| 14 v1 disposition | **LOCKED** | |
| 15 wording audit | **LOCKED as a rule**, not yet executed | |

**No mainline GPU runs while any section above reads NOT LOCKED.** §12 is the only one, and the only
thing it needs is text.
