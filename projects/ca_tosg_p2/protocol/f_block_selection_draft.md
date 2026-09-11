# F spatial-block selection within budget — draft

**Status: UNLOCKED.** Written under P2-R3 C. No block-selection experiment has been run, and none may
run until C-1 to C-7 are locked (C-8). Numbers in this draft come from `f_block_budget.md`, generated
by `f_block_budget.py` from the checkpoint probe, the link capacities and P1's payload chain; they are
not retyped here.

**Decision pending (P2-R3 F-3):** the ranking basis in C-3 is chosen by Josh and the supervisor.

---

## C-1 Where the selection sits

At the collaborator, **after the bottleneck and before packetisation**:

```
branch blocks → AutoEncoder encoder (branches 0, 1) ─┐
                                                    ├→ [select blocks] → int8 (per-branch scales) → packetise → LDPC/QAM
branch 2 block output (uncompressed) ───────────────┘
```

The bottleneck is exactly the tensor P1 transmits: the AutoEncoder encoder output for branches 0 and 1
and the block output for branch 2 (`projects/ca_tosg/evaluation/v2_int8_calibrate.py`,
`TransmitQuant.patched()`). Selection only removes elements; because the int8 code is element-wise
with pre-shared per-branch scales, selecting before or after quantisation gives the same bits.

**Unchanged:** the pillar encoder, the backbone blocks, the AutoEncoder weights, the fusion module, the
upsampling blocks and the detection heads. At the receiver the AutoEncoder decoder, AttFusion,
upsampling and heads run as in P1 (`opencood/models/sub_modules/att_bev_backbone.py`, `forward`).

## C-2 Blocks, and how the three scales map onto one BEV region

**The mapping is derived from the checkpoint, not chosen.** All three transmitted branches have the
same spatial grid (probe: branch 0 is transmitted at 16 channels, branch 1 at 64, branch 2 at 256, all
on one grid), because the layer strides and the AutoEncoder encoder strides bring every branch to the
same resolution. `f_block_budget.py` refuses to run if that ever stops being true.

* **Transmitted grid.** One cell of the shared grid covers the same square of BEV ground on every
  branch (cell size in `f_block_budget.md`).
* **A block** is `r × c` cells of that grid. Block `(i, j)` covers rows `[r·i, r·(i+1))` and columns
  `[c·j, c·(j+1))` **on all three branches at once**: selecting a block transmits its elements on
  every branch, and a branch cannot be sent for a block without the others.
* **After decoding at the receiver**, the same block occupies `4r × 4c` cells of branch 0,
  `2r × 2c` of branch 1 and `r × c` of branch 2, and `4r × 4c` cells of the head grid — the exact
  factors are written per row in `f_block_budget.md` and follow from the decoder and upsampling strides.
* **Exact tiling is required**: `r` divides the grid height and `c` its width. No block straddles the
  edge.
* **Across agents.** P1's pipeline projects each agent's cloud into the ego frame before voxelisation
  (`get_item_single_car(..., ego_pose)`), so a block index names the same ego-frame region on ego and
  collaborator. In deployment this inherits P1's assumption that poses are shared; it is not new here.

**Block size.** Primary: **5 × 8 cells**. Two finer sizes, **5 × 4** and **1 × 1**, are pre-declared
as the only other granularities a development experiment may use. Their block counts, elements per
block per branch and BEV sizes are in `f_block_budget.md`.

## C-3 Ranking basis — candidates (decision pending)

Each candidate uses only what the collaborator has **before it sends**; none uses ego information or
ground truth.

| candidate | what it is | extra network? | training? |
|---|---|---|---|
| **(a) own detection confidence** | the collaborator's single-agent forward already produces its classification map (P1 runs this forward for the L message, `v2_wp2_per_agent.py`); block score = an aggregate of `sigmoid` max-over-anchors over the block's head cells | no | no |
| **(b) feature norm** | norm of the block's bottleneck elements; branches differ in scale, so the combination across branches (e.g. each branch divided by its pre-shared quantisation scale) must be fixed before use | no | no |
| **(c-i) Where2comm-style confidence, fixed** | Where2comm's communication module applied to (a): `sigmoid().max(dim=1)`, optional **fixed** Gaussian smoothing, then top-k (`opencood/models/fuse_modules/where2comm_fuse.py`, `Communication.forward`) | no (the smoothing kernel is fixed, not learned) | no |
| **(c-ii) Where2comm confidence, as trained in Where2comm** | the confidence produced by a Where2comm model trained end-to-end with its communication module | **yes** — a different checkpoint | **yes** |

The aggregate for (a) and (c-i) (max or mean over the block) is fixed together with the choice.

## C-4 Budget per frame

The number of blocks sent is the largest `k` such that

```
N_sym( 8 · k · E_block + mask bits ) ≤ R_sym · D_comm
```

where `N_sym(·)` is P1's billing chain and `E_block` the elements per block. Overhead, item by item:

| item | bits per frame | source |
|---|---|---|
| block mask (bitmap, one bit per block) | number of blocks | this draft; fixed per frame |
| block order | 0 | selected blocks are written in raster order; the mask restores the layout |
| quantisation parameters | 0 | per-branch scales pre-shared (`docs/unified_branch_protocol_v2.md` §3.3) |
| packet headers | 320 per packet | P1 chain, charged inside `N_sym` |
| LDPC codeword padding | as it falls | P1 chain, charged inside `N_sym` |
| the request | not charged | identical for every action (P1) |

An index list costs `⌈log₂(blocks)⌉` bits per selected block and is cheaper than the bitmap only when
few blocks are sent; the bitmap is the draft's choice because its cost does not depend on `k`.
`f_block_budget.md` gives `k_max` for the 20 MHz rows — at the zero-overhead upper bound, so a real link
sends fewer.

## C-5 Receiver

The receiver rebuilds each branch's transmitted-grid tensor from the mask. Two kinds of missing block
must each have a rule:

* **unsent** — known from the mask;
* **failed** — codewords that did not decode, known per codeword (P1's straddling rule still applies:
  an element carried by two codewords is lost if either fails).

Candidates:

| rule | what happens | relation to P1 |
|---|---|---|
| **(i) zero-fill** | missing bottleneck elements take the dequantised zero code point, then decoder and AttFusion run as usual | **identical to P1's partial-recovery rule** for failed codewords. P1 measured that a zeroed collaborator tensor still takes softmax weight and dilutes the ego feature — so (i) keeps that effect for unsent blocks too |
| **(ii) exclude the collaborator at those cells** | AttFusion attends over the ego alone at the decoded cells of missing blocks | **new.** AttFusion has no learnable parameters (`opencood/models/fuse_modules/self_attn.py`), so this changes the forward computation, not any weight |
| **(iii) duplicate the ego feature into the collaborator slot** | at those cells both attention inputs are the ego feature | output equals the ego feature, so for AttFusion (iii) is **equivalent to (ii)**; listed so the equivalence is recorded rather than rediscovered |

**Two consequences to carry into the choice.** Unsent and failed blocks may take different rules; the
draft does not assume they are the same. The decoder and upsampling are convolutional, so under (i) a
zero-filled block also changes decoded cells just inside its received neighbours; under (ii) and (iii)
the exclusion is applied at the mapped decoded cells, but received cells next to a missing block still
carry that spill-over from the decoder.

## C-6 Training

**AttFusion has no learnable parameters** (`ScaledDotProductAttention` holds only `sqrt(dim)`), so
"adapting the fusion network" can only mean adapting weights around it: the AutoEncoder decoders
(branches 0 and 1), the upsampling blocks and the detection heads. In P1 **one checkpoint serves E, L
and F**, so these weights are shared by all three actions.

| option | trainable | frozen | consequence |
|---|---|---|---|
| **(A) no adaptation** | nothing | everything | P1's `eff_E` and `eff_L` stay valid through `p2_reuse_manifest.json`. **Stage-1 default.** |
| **(B) F-path copy** | a copy of decoder, upsampling and heads, used only when F is received, trained on block-masked inputs | pillar encoder, backbone blocks, AutoEncoder encoders, and the original decoder / upsampling / heads used by E, L and the ego path | E and L unchanged; F now runs through weights E and L do not use, so "one checkpoint for all actions" no longer holds and must be reported |
| **(C) whole-model fine-tune** | everything | nothing | E and L outputs change; **every reused P1 product is invalid** and all actions are regenerated |

(B) and (C) need GPU training and are not authorised in this batch.

## C-7 Development evaluation

On OPV2V `validate`:

* the new F's `eff_F` is **regenerated in full** — clean channel and every damaged condition, both
  delivery regimes, the same replicate and interpolation rules as P1 WP5 and §9.3;
* **scaling P1's `eff_F` by any ratio is forbidden**, including by the share of elements sent;
* the new F's payload is recomputed through P1's chain for the elements actually sent, plus the mask;
* `eff_E` and `eff_L` are reused from P1 **only under C-6 option (A)**.

## C-8 Two-stage lock

* **Stage 1 — development rules.** C-1 to C-7, with the C-3 ranking basis chosen, are locked **before
  any block-selection experiment runs**. Development experiments may choose only among candidates
  pre-declared here (C-2 block sizes, C-3 aggregate, C-5 rules, C-6 options); a new candidate is a
  dated amendment, not an edit.
* **Stage 2 — final policy evaluation.** The evaluation protocol for the final policy (confirmatory
  data per `data_plan.md`, success criteria per `p2_protocol.md` C-9) is locked **after** stage-1 results
  exist and **before** any confirmatory data is opened.
* **The boundary.** Stage-1 results inform stage 2; they do not rewrite stage-1 rules retroactively. No
  confirmatory split is read in stage 1.
