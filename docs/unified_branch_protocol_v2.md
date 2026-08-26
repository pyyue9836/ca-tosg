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

**Open decision, to be ruled before locking:** the compression AutoEncoder currently stays in the
path in single-vehicle mode. Physically a vehicle does not encode a message to itself; but bypassing
the codec changes the network the weights were trained for. The sanity check (§8) reports the as-is
number. **Ruling required — one line, with the reason, before §2 locks.**

### L — object-level, per-vehicle detection plus box-level late fusion

Each CAV in the frame runs the **same** checkpoint independently (`record_len = [1]` per vehicle, its
own voxels), producing boxes in its own frame; boxes are transformed into the ego frame and fused at
box level. Nothing about the *network* differs from E — only how many vehicles are run and what is
combined afterwards.

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

The status quo: each collaborator's post-encoder bottleneck tensor is transmitted, and the ego fuses
with `AttFusion` over `record_len = [N]`. Unchanged from v1 in mechanism; what changes is that L and
E now come from the same network, and that `B_F` is charged from the real tensor (§3).

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

### 3.2 F payload — measured, not declared (P0-4)

v1 declared a 1.98 Mbit/frame source budget and derived `B_F = 0.99` Msym. **v2 charges the tensor
that actually crosses the link.** From `results/manifests/P4B_PROBE_pointpillar_compression.json`
(forward-hook probe of this checkpoint, per CAV):

| branch | pre-compression shape | transmitted shape | transmitted elements |
|---|---|---|---|
| 0 | 64 × 100 × 352 | 16 × 25 × 88 | 35,200 |
| 1 | 128 × 50 × 176 | 64 × 25 × 88 | 140,800 |
| 2 | 256 × 25 × 88 | 256 × 25 × 88 (uncompressed) | 563,200 |
| **total per CAV** | 3,942,400 | — | **739,200** |

The chain, fully specified so `B_F` is uniquely determined:

```
info_bits   = 739,200 elements  ×  w bits/element        (w = quantisation width, §3.3)
+ header    = H_F bits per packet × ceil(info_bits / P)  (P = payload bits per packet, §3.3)
coded_bits  = (info_bits + header) / R                   (R = 1/2, 5G-LDPC K=500 N=1000)
N_cw        = ceil((info_bits + header) / K)             (K = 500)
B_F [Msym]  = coded_bits / bits_per_symbol / 1e6         (16-QAM: 4)
```

### 3.3 Quantisation and packetisation — the values that must be chosen before locking

| parameter | proposed | reason |
|---|---|---|
| `w`, bits per feature element | **8** (int8, per-tensor affine scale) | the standard deployable choice for BEV feature transport; 16-bit is the conservative alternative and 32-bit float is not a transmission format anyone would use |
| `P`, payload bits per packet | **8,000** (1000 B) | a plain MTU-scale packet; keeps the header fraction visible without inventing a stack |
| `H_F`, header bits per packet | **320** (40 B: 20 B IP + 8 B UDP + 12 B application) | a stated, ordinary header, so the accounting cannot be accused of ignoring overhead |

**`w` is the single most consequential choice in this file** — it scales `B_F` linearly. It is chosen
here, before any result, and it is an amendment-level event afterwards. The v1 declared convention
(1.98 Mbit ⇒ 0.9155 bit/element) becomes a **historical reference only** and may not be quoted as a
v2 payload.

---

## 4. L payload — per frame, from the boxes actually sent (P0-5)

v1 charged a fixed `B_L = 0.024` Msym/frame from a 27-object mean. **v2 charges each frame for the
boxes that frame actually transmits.**

```
B_L,t [Msym] = ( N_box,t × B_box + H_L × ceil(N_box,t × B_box / P) ) / R / bits_per_symbol / 1e6
```

`N_box,t` = the number of boxes the collaborator's detector emits at the frozen score threshold
(§2), after intra-vehicle NMS, before cross-vehicle de-duplication.

`B_box`, the per-object container, itemised so it is auditable:

| field | bits | note |
|---|---|---|
| position x, y, z | 3 × 16 = 48 | 16-bit fixed point over the stated range |
| dimensions h, w, l | 3 × 12 = 36 | |
| heading (yaw) | 12 | |
| class | 4 | |
| confidence | 8 | |
| position covariance (3 terms) | 3 × 12 = 36 | the ETSI-CPM-style uncertainty the v1 container also carried |
| **`B_box` total** | **184 bits = 23 B** | |

`H_L` = 320 bits, `P` = 8,000 bits, `R` = 1/2, as in §3.3.

**The 27-object mean and the 110 B ETSI-CPM container of v1 become historical references.** They are
not deleted from the record; they are simply not the v2 accounting.

**The selector's budget uses the per-frame value**, not a split mean: `B_max` is compared against
`B_L,t` for the frame in question. This is the point of the change — a per-frame selector charged a
split-mean price cannot express the thing it is selecting on.

---

## 5. Transport model (P0-6)

**Main experiment:** fragmentation with partial recovery. A message is split into `N_cw` LDPC
codewords; each codeword succeeds or fails independently at the frame's SNR/channel per the Sionna
BLER table; the receiver reconstructs from the codewords that arrive. What a partial feature tensor
means for the detector is defined explicitly: **missing codewords are zero-filled before decoding**,
which is the honest degradation for a linear autoencoder bottleneck, and the resulting detection is
scored normally.

**Demoted to a sensitivity arm:** all-or-nothing delivery (v1's mainline), where any codeword failure
loses the whole message and the receiver falls back to ego-only. It stays as the pessimistic bound.

**Optional enhancement, costed separately and not in the mainline:** OFDM with a vehicular TDL
channel model in place of the flat block-fading table. Priced in §9 as its own tier.

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
   Verified by asserting range equality across the three arms' configs and GT identity per frame.
3. **Codec and architecture no longer differ across actions.** E and L run the same network as F,
   with the same weights; the only difference is `record_len` and what is transmitted. Verified by
   asserting that the three arms differ in exactly those inputs and in nothing else.

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

## 10. Split discipline (unchanged from v1)

* **validate** is the only split anything is fitted, tuned or selected on.
* **test** and **Culver-City** are one-shot frozen evaluations.
* `δ = 0.005` — unchanged.
* **Primary cell = test @ B_max = 0.20** — unchanged.
* **The ≥10 % payload-reduction criterion: RULING REQUIRED, one line.** It was written against v1's
  fixed `B_L = 0.024` Msym. Under §4 the L payload is per-frame and its scale may differ, so a
  threshold calibrated to the old constant may be either trivial or unreachable. *Proposed:* retain
  the criterion but re-express it as a fraction of the **measured** `B_F` of §3.2 rather than of the
  declared 0.99 Msym, and state the equivalent v1 fraction alongside it for continuity. **Josh
  decides; nothing runs against this criterion until he does.**

---

## 11. Regeneration list — every product the unification touches

Ordered so that nothing downstream runs before its input is re-derived.

| # | product | why it must be re-derived |
|---|---|---|
| 1 | per-vehicle detections, all splits | new: each CAV through the unified checkpoint |
| 2 | E boxes/F1/AP | new network for this action |
| 3 | L boxes after box-level fusion | new detector + new fusion rule |
| 4 | F boxes/F1/AP | unchanged mechanism, but re-scored on the unified GT |
| 5 | per-frame `N_box,t` | the input to the L payload |
| 6 | `B_L,t` per frame | §4 |
| 7 | `B_F` | §3.2, measured tensor |
| 8 | BLER table / `N_cw` per message | `N_cw` changes with the payloads above |
| 9 | oracle labels (E/L/F argmax under the mask) | every input to the argmax moved |
| 10 | selector training + LOSO + freeze, per budget | new labels, new payload axis |
| 11 | replay + `tau_feasible` + fixed references | new products |
| 12 | figures and tables | last, from the above |
| 13 | **Where2comm arm** | must move to the same GT and the same FOV, or the comparison re-acquires the confound plan A removes |

**The supervisor's own 12-item list is not in this repository.** The table above is *my* derivation
of the dependency order. Before this section locks, the supervisor's list must be pasted in and
reconciled line by line with it; where the two differ, **his list wins** and the difference is
recorded. Nothing in §11 is treated as complete until that reconciliation happens.

---

## 12. Conditional branches P1-1 … P1-8, and stage-5 rewrite items P2-1 … P2-6

**Their text is not in this repository.** They were named in the V2-R1 instruction by label only.
Fabricating them would be worse than leaving them empty, so the tables below are placeholders with
the right shape and no invented content.

| id | trigger condition | pre-registered wording per branch |
|---|---|---|
| P1-1 … P1-8 | **TEXT REQUIRED — paste before this section locks** | **TEXT REQUIRED** |

| id | stage-5 rewrite item (not executed now) |
|---|---|
| P2-1 … P2-6 | **TEXT REQUIRED — paste before this section locks** |

Sections 12 is therefore **NOT LOCKED**. Its hash is recorded as `PENDING` in the manifest and the
manifest gate must treat a `PENDING` section as an open item, not as a satisfied one.

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
| 2 actions | **LOCKED except the E-codec ruling** | §2 E open decision |
| 3 FOV/GT/`B_F` | **LOCKED except `w`, `P`, `H_F`** | proposals stated; Josh confirms |
| 4 `B_L` | **LOCKED** | container itemised |
| 5 transport | **LOCKED** | main = fragmentation + partial recovery |
| 6 statistics | **LOCKED** | scene-level |
| 7 success criteria | **LOCKED** | including the three wording templates |
| 8 sanity | **LOCKED** | fuse stated |
| 9 cue set | **LOCKED** | v1 set carried over |
| 10 split discipline | **LOCKED except the ≥10 % ruling** | |
| 11 regeneration list | **NOT LOCKED** | awaits the supervisor's 12-item list |
| 12 P1/P2 | **NOT LOCKED** | text required |
| 13 external arm | **LOCKED as a placeholder** | report before GPU |
| 14 v1 disposition | **LOCKED** | |
| 15 wording audit | **LOCKED as a rule**, not yet executed | |

**No mainline GPU runs while any section above reads NOT LOCKED.**
