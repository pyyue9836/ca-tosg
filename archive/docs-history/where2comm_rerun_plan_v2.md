# Where2comm budget-matched rerun — PLAN v2 (R50)

**Status: PLAN ONLY. Nothing in this file has been run. No GPU time has been spent.**
The original plan (R21-B) was written before the P0 corrigendum, the frozen-selector protocol and
the four-convention payload accounting. This version supersedes it; R21-B is history.

Read with: `docs/experiment_protocol.md` (the normative record), `docs/canonical_quantities.md`
(the four payload conventions), `results/README.md` (which command writes which product).

---

## 0 · Why this exists, and what it may and may not settle

The paper currently has **no unified external baseline trained and scored under its own transport**
— limitation (iv) of `sec:boundaries`. Where2comm appears only as an *adjacent-technology
reference*: our 50-epoch reproduction, AP@0.5 `0.871` on validate, scored by the **retired**
global-sort scorer, under a **perfect** channel, fusing **every** collaborator
(`results/baselines/where2comm.csv`). Three axes of incomparability at once, which is why R45-4
forbids it from entering any comparison sentence.

This rerun is the one experiment that could remove that limitation. It can settle: *at a matched
per-frame channel-use budget, and under the same LDPC + QAM transport and the same scoring chain,
does spatial selection within the feature level beat, match, or lose to granularity selection
across levels?*

It cannot settle: whether Where2comm as published is better or worse than CA-TOSG. We train it
ourselves on this repository's data discipline; the SComCP arm (SC-2, ruling (c)) is the standing
precedent for how a reproduction that does not converge must be reported.

---

## a · Collaborator convention: N = 1, matching the main experiment

**The rerun uses the nearest single collaborator**, the convention every mainline number uses since
the P0 corrigendum. Concretely:

* inference fuses the ego and **one** collaborator, selected by the same nearest-neighbour rule as
  the mainline caches (`projects/ca_tosg/datasets/`), not every CAV in the frame;
* the existing full-collaborator reproduction stays in `results/baselines/where2comm.csv` and is
  **relabelled historical**, kept for provenance and never ranked;
* the plan produces a *new* product tree (`results/baselines/where2comm_v2/`) so that no committed
  file changes meaning under a reader who has the old one cached.

Rationale for stating this first: the direction of the old comparison already flipped once when the
convention changed (validate Fixed-L `0.7819` is *below* the reproduction's `0.871`). A comparison
whose sign depends on the collaborator count is not a comparison.

## b · Sparsity grid, and inference stored per sparsity

Where2comm's communication cost is set by how much of the confidence map it transmits. The grid is
**eight points**, chosen to bracket all three budget points under all four payload conventions
rather than to look symmetric:

| # | spatial sparsity `s` (fraction of BEV cells transmitted) | why this point |
|---|---|---|
| 1 | 0.005 | below the tightest cap under the bottleneck convention |
| 2 | 0.01 | ≈ the `B_max = 0.10` cap, bottleneck convention |
| 3 | 0.02 | between the tight caps |
| 4 | 0.05 | ≈ the `B_max = 0.20` cap, declared convention |
| 5 | 0.10 | ≈ the `B_max = 0.30` cap, declared convention |
| 6 | 0.20 | above every cap under the declared convention |
| 7 | 0.50 | above every cap under the pre-compression convention |
| 8 | 1.00 | dense reference (no spatial selection) — the ceiling the method's own curve approaches |

**Inference is stored per sparsity, and budget matching is pure post-processing.** Each grid point
writes cached per-frame detection outputs (boxes + scores + GT), exactly as
`projects/ca_tosg/datasets/regen_preds_with_scores.py` does for the mainline arms. Every later
question — which sparsity meets `B_max` under which convention, what the payload-matched AP is,
what happens if the accounting changes again — is then a table join over cached outputs, with **no
re-inference**. This is the single most important design decision in the plan: the payload
convention has already changed twice (R47, R48), and a rerun that welds accounting into inference
would have to be re-run each time.

Storage estimate: 8 sparsities × 3 splits × ~4,700 frames × (boxes+scores+GT) ≈ the same order as
`gs_rerun/` (a few GB), which is why the products go under `results/baselines/where2comm_v2/` with
the caches git-excluded and the summaries committed.

## c · Sparse payload → Msym: the accounting convention, pre-registered

Where2comm transmits a *sparse* feature selection plus the indices needed to place it. The billing
convention below is registered **before** any number exists, and takes its place beside the four
conventions in `docs/canonical_quantities.md`:

```
elements_tx(s)   = s * H * W * C            # transmitted feature elements at sparsity s
index_bits(s)    = s * H * W * ceil(log2(H*W))   # position of each selected cell
info_bits(s)     = elements_tx(s) * 0.9155 + index_bits(s)
coded_bits(s)    = info_bits(s) / R,   R = 1/2      # same LDPC rate as every arm here
B_W2C(s)         = coded_bits(s) / 4 bit-per-symbol  # same 16-QAM as the deployed F branch
```

Assumptions, stated rather than buried:

1. **The 0.9155 bit/element figure is the declared convention**, the same one the paper applies to
   its own feature tensor. Using it here is what makes the two methods comparable at all; it is not
   a measurement of a Where2comm bitstream, and the resulting numbers are counterfactual payloads in
   exactly the sense R48-1 defines.
2. **Index cost is charged.** A sparse method that pays nothing for saying *where* its elements go
   is being flattered. `ceil(log2(H*W))` bits per selected cell is the cheapest honest encoding
   (a dense bitmap `H*W` bits is charged instead whenever it is smaller — the plan takes the min).
3. **The confidence map itself is charged** at the same convention if the implementation transmits
   it; if the variant used computes it ego-side, that is recorded and the cost is zero. This is
   decided by reading the code before the run, per the R46-3 paper-vs-code discipline, and written
   into the change-log entry.
4. **Same transport for both methods**: rate-1/2 LDPC, 16-QAM, the committed BLER table, the same
   all-or-nothing frame model and the same 0.999 feasibility mask. A delivery failure falls back to
   the ego-only output, as in `eff_matrix_blerL`.
5. The whole table is reported under **all four payload conventions**, since the sparsity that meets
   a cap under the declared anchor does not meet it under the bottleneck one.

## d · Scoring: the current frozen chain, not the retired one

* AP and frame F1 come from the **same** chain as every mainline number:
  `tools/evaluate_ap.py` / `projects/ca_tosg/evaluation/end_to_end_ap_snr.py`, not the retired
  global-sort scorer `true_e2e_global.py`.
* **GT-count assertion**: the rerun must reproduce the same per-split ground-truth object counts as
  `results/sensitivity/gt_audit.csv` / `gt_object_stats.csv` before any AP is reported. A scorer
  that sees a different GT set produces numbers that cannot be compared, and this exact check is
  what caught the earlier own-GT defect.
* 200 paired CSI realisations, `CSI_SEED = 20260809`, 11-point SNR grid, 50/50 AWGN/Rayleigh — the
  frozen replay draw, so the comparison is paired at the frame and realisation level.
* Paired bootstrap, `N_BOOT = 10000`, `BOOT_SEED = 12345`.

## e · Verdict templates, pre-registered — the direction is the data's to choose

The comparison cell is fixed in advance: **test split, `B_max = 0.20`, declared convention**, with
the other budgets and conventions reported descriptively. `B_W2C(s*)` is the largest grid sparsity
whose mean payload does not exceed the cap; CA-TOSG's cell is `0.14141` Msym at `0.89691` F1.

Let `d = F1_W2C − F1_CA-TOSG`, with 95% paired-bootstrap CI `[l, u]`, and margin `δ = 0.005`.

* **Where2comm wins** (`l > +δ`):
  *"At a matched per-frame budget and under the same transport and scoring chain, spatial selection
  within the feature level attains higher realised F1 than granularity selection across levels
  (d = +X, 95% CI [l, u]). The granularity claim of this paper does not hold against a
  budget-matched spatial-selection baseline, and Section ... is revised accordingly."*
* **CA-TOSG wins** (`u < −δ`):
  *"At a matched per-frame budget, granularity selection attains higher realised F1 than
  budget-matched spatial selection (d = −X, 95% CI [l, u])."*
* **Non-inferior / indistinguishable** (`[l, u] ⊂ [−δ, +δ]`):
  *"At a matched per-frame budget the two are indistinguishable within the pre-registered margin
  (d = X, 95% CI [l, u]); the methods are complementary rather than competing, and the composition
  argument of the supplementary material stands."*
* **Inconclusive** (`[l, u]` straddles a margin edge):
  *"The interval does not resolve the comparison at the pre-registered margin (d = X, 95% CI
  [l, u]); reported as an interval, no verdict attached."*

Forbidden in every branch: reporting only the favourable budget, only the favourable convention, or
promoting a descriptive cell to the confirmatory one. The confirmatory cell is named above and does
not move after the first number exists.

## f · GPU cost, three tiers, and the stop rule

Cost anchor, measured in this repository: the JSCC sweep ran ~10 GPU-h for 36 inference runs
(≈0.28 h per channel×SNR×split). Training anchor: the existing Where2comm reproduction is a 50-epoch
OPV2V run.

| tier | scope | training | inference | total |
|---|---|---|---|---|
| **Conservative** | validate + test, 8 sparsities, retrain at N=1 | 1 × 50-epoch (~10 h) | 8 × 2 splits × 0.28 h ≈ 4.5 h | **≈ 15 GPU-h** |
| **Typical** | + Culver-City, one restart allowed for a diverging run | 1.5 × 50-epoch (~15 h) | 8 × 3 splits × 0.28 h ≈ 7 h | **≈ 22 GPU-h** |
| **Worst case** | + a second sparsity refinement pass around the cap, + a full re-inference if the checkpoint is re-trained | 2.5 × 50-epoch (~25 h) | ~14 h | **≈ 40 GPU-h** |

Assumptions behind the numbers: single RTX 5070 (sm_120, the machine that produced every other
result here), batch-1 inference, no hyper-parameter search, and no re-inference for accounting
changes (which is what (b) buys).

**Stop rule — the SComCP lesson, applied in advance.** SC-1/SC-2 spent a training budget and
produced a scaffold that never converged; the saving grace was that fuses had been registered
*before* the run, so the outcome was reportable as a negative reproduction result rather than as a
claim about the method. The same applies here:

* **Fuse 1 (training):** if validate AP@0.5 at the dense point `s = 1.0` under a perfect channel
  falls below the ego-only floor after 50 epochs, stop. That is a scaffold finding, not a
  Where2comm finding.
* **Fuse 2 (sanity):** if AP is flat in the sparsity grid (no monotone trend between `s = 0.005` and
  `s = 1.0`), stop — the sparsity control is not doing anything and the comparison is meaningless.
* **Fuse 3 (budget):** if no grid point lands within ±20 % of the `B_max = 0.20` cap under the
  declared convention, add **one** refinement pass (worst-case tier) and no more; if it still
  misses, report the bracketing pair and say the cap was not matched.
* On any fuse: write the negative result into the change-log with the same wording discipline as
  SC-2 ruling (c) — *"our Where2comm reproduction did not …; reported as a negative reproduction
  result, not as a measurement of the method"* — and the paper's limitation (iv) stays as it is.

---

## 2 · Self-audit against the protocol, the accounting and the 18 gates

| what it must agree with | status of this plan |
|---|---|
| `PROTOCOL` single-collaborator convention (P0 corrigendum) | **agrees** — §a; old arm relabelled historical, not deleted |
| Frozen replay draw (`CSI_SEED=20260809`, 200 realisations, 11-point grid) | **agrees** — §d |
| Pre-registered margin δ = 0.005 and one confirmatory cell (R9) | **agrees** — §e; secondary cells are descriptive only |
| `payload_conventions.csv` (four conventions) | **extends** — §c adds a fifth, sparse-transmission convention; it must be added to the CSV and to `canonical_quantities.md` when the run starts |
| Scoring chain = frozen, retired global-sort forbidden | **agrees** — §d |
| GT-count discipline | **agrees** — §d, as a pre-condition on reporting |
| R45-4 "adjacent-technology reference, never a baseline" | **conflicts by design** — a budget-matched arm *is* a baseline. The TERMINOLOGY row and the reconciliation pair must be amended in the same commit that lands the first number, or the two gates will (correctly) block it |
| R46-2 "branches do not share weights" | **unaffected** — Where2comm is a third pipeline; the limitation stands and is not repaired by this rerun |
| R48-1 evidence grade | **agrees** — §c calls its outputs counterfactual payloads |

### Gates this plan requires (to be added when the run starts, not now)

1. **Provenance binding for the new products.** Every file under `results/baselines/where2comm_v2/`
   needs a `results/README.md` row naming the command that wrote it, and the numeric-literal gate
   needs the new claims bound in `docs/claims.md`. Without this the arm's numbers enter the paper
   unbound — the exact failure the ledger exists to prevent.
2. **Direction probe for the verdict sentence.** A row in `tests/comparison_claims.md`
   (`W2C` vs `RF`, direction from the data, metric F1, split test, budget 0.20) so the verdict
   sentence cannot drift from the CSV it came from — the same mechanism that caught three reversed
   directions in R25.
3. **TERMINOLOGY amendment.** The `Where2comm status` row currently forbids the word *baseline*.
   When the arm becomes budget-matched, the row must change from "never a baseline" to "baseline
   only for the budget-matched N=1 arm; the historical full-collaborator reproduction remains a
   reference", with the retired form still blocked.
4. **Reconciliation pair.** `where2comm-baseline` in `tests/protocol_claims.md` must be re-pointed at
   the new protocol anchor, or it will keep asserting a verdict the record has superseded.
5. **Sparse-payload convention check.** An extension of `tools/check_anchor_sensitivity.py` (or a
   sibling) that re-derives `B_W2C(s)` from the grid definition and the committed sparsity, so the
   fifth convention is machine-checked like the other four.
6. **A GT-count assertion in the arm's own pipeline**, failing loudly rather than skipping — the
   R48-5 lesson about checks that silently cross-check nothing.

---

## 3 · What is being asked of Josh

Approve one of: **Conservative ≈ 15 GPU-h**, **Typical ≈ 22 GPU-h** (recommended: it includes
Culver-City, which is where the generalisation claim lives, and one restart), or **Worst case
≈ 40 GPU-h**. Nothing starts without that.

Until then the paper's position is unchanged and self-consistent: Where2comm is an
adjacent-technology reference, limitation (iv) says plainly that no unified external baseline exists
under this transport, and no claim in the paper depends on this rerun.
