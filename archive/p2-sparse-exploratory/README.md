# `p2-sparse-exploratory` — closed 2026-09-12

An **exploratory side branch** of paper 2, stopped by P2-R9 item 1. Everything it produced is kept
here unchanged: nothing was deleted and nothing was re-run.

## What it was

Budgeted F: instead of the complete bottleneck, send **K_F = 23 of 55 spatial blocks** — the largest
number that fits the 802.11bd 20 MHz, 100 ms **zero-overhead upper bound** — choosing blocks by one of
three rankings (the collaborator's own detection confidence, the feature norm, or at random) at
identical payload, with everything in the perception model frozen and unsent blocks zero-filled.

## Conclusion

On all 1,980 validate frames, clean condition, scene-equal F1:

* **the pre-registered benefit condition was not met.** Sparse F did not beat the object-level
  message: confidence − L = **−0.00280**, 95 % interval [−0.01235, +0.00718]. On the locked hard-frame
  subset it was −0.00100.
* **the complete F did beat L** in the same comparison: +0.01444, [+0.00578, +0.02439]. The sparse
  scheme recovered none of that advantage.
* **the ranking itself worked:** confidence − random = **+0.06349**, [+0.04871, +0.08261], and
  confidence − norm = +0.01541, [+0.00889, +0.02218].
* against L the trade was recall for precision: 630 more missed objects, 1,387 fewer false positives.

So the limit was not which blocks to send. It was sending 42 % of them.

## Why it stopped

P2-R9 item 1: the sparse route is closed and the batch returns to the complete F / L / E question. No
further block-selection, recovery-network or sparse-selector experiment is to be started.

## Commits, if this has to be reproduced

| stage | commit |
|---|---|
| round-1 protocol locked | `bd27cbb` |
| Amendment 1 | `f6f603e` |
| Amendment 2 | `b74d1d1` |
| stage 1 (60 frames) | `4b5d3a8` |
| stage 2 (1,980 frames, clean) | `767b637` |

**These generators are a record, not runnable tools in this location.** Each computes its paths
relative to its original home under `projects/ca_tosg_p2/`, so `--check` will not resolve from here;
check out one of the commits above to run them.

## Inventory (29 files)

* `archive/p2-sparse-exploratory/evaluation/p2_f_block_eval.py`
* `archive/p2-sparse-exploratory/evaluation/p2_stage1_report.py`
* `archive/p2-sparse-exploratory/evaluation/p2_stage2_report.py`
* `archive/p2-sparse-exploratory/protocol/amendment1.json`
* `archive/p2-sparse-exploratory/protocol/amendment1.md`
* `archive/p2-sparse-exploratory/protocol/amendment1.py`
* `archive/p2-sparse-exploratory/protocol/amendment2.json`
* `archive/p2-sparse-exploratory/protocol/amendment2.md`
* `archive/p2-sparse-exploratory/protocol/amendment2.py`
* `archive/p2-sparse-exploratory/protocol/f_block_budget.json`
* `archive/p2-sparse-exploratory/protocol/f_block_budget.md`
* `archive/p2-sparse-exploratory/protocol/f_block_budget.py`
* `archive/p2-sparse-exploratory/protocol/f_block_selection.md`
* `archive/p2-sparse-exploratory/protocol/gpu_estimate_round1.json`
* `archive/p2-sparse-exploratory/protocol/gpu_estimate_round1.md`
* `archive/p2-sparse-exploratory/protocol/gpu_estimate_round1.py`
* `archive/p2-sparse-exploratory/protocol/round1_lock.json`
* `archive/p2-sparse-exploratory/protocol/round1_lock.md`
* `archive/p2-sparse-exploratory/protocol/round1_lock.py`
* `archive/p2-sparse-exploratory/results/probe/f_block_eval_validate.json`
* `archive/p2-sparse-exploratory/results/probe/f_block_rows_validate.csv`
* `archive/p2-sparse-exploratory/results/stage1/f_block_eval_validate.json`
* `archive/p2-sparse-exploratory/results/stage1/f_block_rows_validate.csv`
* `archive/p2-sparse-exploratory/results/stage1/stage1_report.json`
* `archive/p2-sparse-exploratory/results/stage1/stage1_report.md`
* `archive/p2-sparse-exploratory/results/stage2_clean/f_block_eval_validate.json`
* `archive/p2-sparse-exploratory/results/stage2_clean/f_block_rows_validate.csv`
* `archive/p2-sparse-exploratory/results/stage2_clean/stage2_report.json`
* `archive/p2-sparse-exploratory/results/stage2_clean/stage2_report.md`
