# Evidence: Culver late-F1 is saturation, not cache contamination

**Question closed (P0.1):** the near-identical Fixed-L / Oracle frame-F1 between the OPV2V
*test* and *Culver-City* splits (0.8867 both, to 4 dp) is a genuine property of the
operating-point frame-F1 metric, **not** a contaminated cache. Companion data:
`f1_ap_decoupling_culver.csv`.

## Decisive recompute (the check that settles it)

Recompute the 550/2170-frame late-fusion frame-F1 from the **score-bearing predictions
that produce the AP below** (this differs in provenance from the weeks-old F1 cache),
under the *same* convention as the F1 pipeline (IoU 0.5, uniform per-box score,
`eval_utils.caluclate_tp_fp`), and compare to the old cached value:

| split | AP@0.5 | AP@0.7 | late-F1 (new preds) | late-F1 (old cache) | Δ |
|---|---|---|---|---|---|
| test   | 0.9055 | 0.8560 | 0.886709 | 0.886709 | **0.00** |
| culver | 0.8114 | 0.7240 | 0.886685 | 0.886685 | **0.00** |

The recompute matches the old cache to 6 dp (Δ=0), as expected for deterministic
inference: the regenerated prediction-box set is identical to the original, so same-convention
F1 reproduces bit-for-bit. This simultaneously (a) proves the old cache is genuine Culver, and
(b) refutes the "old cache buggy, new preds clean" alternative — a buggy cache could not match
the new predictions exactly.

## The observation (worth stating in the paper)

On the *same* genuine-Culver predictions, **AP@0.7 separates test↔Culver by 0.132 but
frame-F1 by only 2.5e-5.** The loose operating point (score≥0.2, IoU 0.5) frame-F1 measures
*whether objects are detected* and saturates across both splits; the domain-shift penalty lives
in *ranking and tight localisation*, which **AP** carries. This supports the L-floor argument:
the object-level (late) branch is cross-domain reliable at the deployed operating point.
→ one sentence for annual-review §4.4 and the paper (P2 batch).

## Secondary (independent protocol flaw, GAP-2)

`fixed_C16` effective F1 in `generalisation_{test,culver}.csv` separates by 0.0417 with
**Culver higher** — but the clean (perfect-channel) comp-F1 separates by only 0.0046 with
**Culver lower** (sign-flipped). A single random SNR draw per frame gives the `fixed_C16` eff a
sampling SE of **0.0155** over 550 frames (≈0.022 on a cross-split difference), so the observed
0.0417 is ~1.9×SE and sign-flipped → **channel-sampling noise, not a domain effect.** Fixed /
deployed policy rows must be averaged over many channel realisations, not one draw per frame
(fixed in the P0.2 unified-protocol recompute).

## Provenance

- Predictions: `gs_rerun/{late,comp}_{test,culver}.npz` (score-bearing per-frame boxes/scores/GT
  from `code/regen_preds_with_scores.py`; late = PointPillar-Late, comp = attentive-compression).
- Scoring: `opencood.utils.eval_utils` — F1 via `caluclate_tp_fp` (IoU 0.5, uniform score);
  AP via `calculate_ap(..., global_sort=True)`.
- Old cache: committed `results/generalisation_{test,culver}.csv` (weeks-old 02-pipeline).
- No RF / channel realisation involved in this artifact (it is pre-selector, per-branch F1/AP).
