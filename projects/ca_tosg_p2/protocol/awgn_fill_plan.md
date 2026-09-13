# Filling AWGN 8.5 / 9.0 / 9.5 dB — pre-registered plan (P2-R12 B)

**Status: plan only. Nothing has been run.** The stopping rule below is fixed *before* the measurement,
which is the whole point of writing it down first. It runs on approval.

## Why these three points

`four_arm_eval.md` A-5 inverts the accounting: on AWGN at 10 dB and above, F overtakes L at
**q_F > 0.8415**, i.e. **p_cw < 1.37 × 10⁻⁵**. The committed table measures 1.3 × 10⁻⁴ at 8 dB — an
order of magnitude above that threshold — and nothing at all between 8 and 10 dB. The crossing
therefore sits in an unsampled interval, and no interpolation may invent it.

## B-1 The configuration is P1's, unchanged

The fill imports `bler_point` from `projects/ca_tosg/communication/ldpc_qam.py` and does not
re-implement it: 5G-LDPC K = 500 / n = 1000 rate 1/2, `num_iter = 20`, 16-QAM, AWGN, batch 2000, the
Es/N0 axis, **CPU only** (that module disables the GPU because TensorFlow ships no sm_120 kernels for
this card). Only `MAX_CW` and `TARGET_ERR` are overridden, per B-2.

**The reproduction check cannot be bit-exact, and saying so is part of the plan.** The module sets no
random seed, so a re-run of an existing point cannot return the identical count. The check is therefore
**statistical and fixed here in advance**:

* re-measure **8.0 dB** at 100,000 codewords: the Wilson 95 % interval of the new estimate must contain
  the recorded 1.3 × 10⁻⁴, and the recorded point's Wilson interval must contain the new estimate;
* re-measure **10.0 dB** at 100,000 codewords: it must again produce **zero** errors;
* if either fails, **stop and report**. Nothing is adjusted to make it pass.

## B-2 The stopping rule, fixed before the run

* **N_min = 1,000,000 codewords per point.** Derivation: with zero errors the rule of three gives a 95 %
  upper bound of 3/N, so resolving the threshold p_cw < 1.37 × 10⁻⁵ needs N ≥ 3 / 1.37 × 10⁻⁵ =
  218,978, rounded up to the next power of ten. This is ten times the `MAX_CW` of the committed table,
  which is exactly why that table cannot answer the question.
* **Early stop at ≥ 30 block errors.** Thirty errors put the Wilson interval well clear of the
  threshold, so the extra codewords would buy nothing.
* Each point reports **codewords, errors, the p_cw point estimate and its Wilson 95 % interval**.

## B-3 Zero errors is an upper bound, never a zero

A point that reaches N_min with no error is reported as **p_cw < 3/N at 95 %**, with the codeword count
beside it. It is not written as `p_cw = 0`, and no sentence anywhere may read "the message always
arrives". *This flaw is already in the committed table:* 10, 12, 16 and 20 dB are stored as `0.00000`
though each is 0 errors in 100,000 codewords, and the grid consumes them as exact zeros, which is what
makes q_F exactly 1 at those cells today.

## B-4 What is recomputed afterwards

Only expectations — **no perception inference of any kind**. With the new p_cw values: q_F, `eff_F`, the
four-arm per-cell table and the τ sweep. The report then says which two sampled points the crossing
falls between, or states that **the interval could not be determined under this stopping rule** — that
outcome is a permitted result, not a reason to relax N_min.

**One further correction to carry:** the `bler_frame` column of the committed table is computed with
N_CW = 3960, the old 1.98 Mbit budget. Our message is 12,567 codewords, so `bler_frame` must not be
used; q_F is computed from `bler_cw` here and always has been.

## B-5 Where the outputs go

New files, never edits to P1's:

* `projects/ca_tosg_p2/results/channel/bler_awgn_fill.csv` — the three new points plus the two
  reproduction checks, with counts and intervals;
* `projects/ca_tosg_p2/results/grid/v2_grid_validate_ideal_fill.csv` — a **new version** of the grid
  carrying the added SNR points, registered with its inputs' hashes.

`results/channel/bler_sionna.csv` and `results/v2/v2_grid_validate_ideal.csv` are not modified.

## B-6 Expected cost

Grounded in the committed run rather than guessed: `results/logs/bler_sionna_run.log` records the
16-QAM AWGN block as **518,000 codewords in 13.9 minutes ≈ 621 codewords/second** on this CPU.

| item | codewords | time at 621 cw/s |
|---|---:|---:|
| 8.5, 9.0, 9.5 dB at N_min (worst case, no early stop) | 3,000,000 | ≈ 80 min |
| reproduction checks at 8.0 and 10.0 dB | 200,000 | ≈ 5 min |
| **total** | **3,200,000** | **≈ 86 min, CPU** |

Early stopping can only shorten this: a point that reaches 30 errors before N_min stops there. The GPU
is not used and cannot be — the card has no TensorFlow kernels for this build.

**Waiting for approval before running.**
