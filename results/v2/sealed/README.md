# `results/v2/sealed/` — held-out accuracy, sealed until work package 11

**Nothing in this directory may be read by a tuning, selection, or model-choice step.** Protocol §10
and V2-R5 E-2: validate is the only split anything is fitted or selected on; test and Culver-City are
one-shot frozen evaluations.

## Why these files exist at all

Work package 2 generates per-agent products for **all three splits** — that is its job, stated in its
own scope line. The first version of the generator also computed an ego AP and a per-frame F1 for
whichever split it ran, which on `test` and `culver` is **accuracy on a held-out split, produced
before the selector was frozen**. That is not a protocol breach in itself — nothing tuned on it — but
a number sitting in a file people read is a number that can inform a decision whether or not anyone
meant it to.

So it was moved here rather than deleted. **Deleting it would be theatre**: the values were computed,
and a record that pretends otherwise is worse than one that says what happened.

## What was done about it

1. The values were moved out of the ordinary summaries and per-frame tables into this directory.
2. The generator was changed: on a held-out split it now computes **no** accuracy unless
   `--held-out-eval` is passed, which **work package 11 and nothing else** may pass.
3. Box counts were **not** sealed. They feed payload accounting (`N_box,t` → `B_L,t`), which is not
   accuracy, and the transport products need them.

| file | contents |
|---|---|
| `wp2_held_out_{test,culver}.json` | ego AP@0.5 and mean per-frame F1, aggregate |
| `wp2_f1_ego_{test,culver}.csv` | per-frame ego F1 — *more* informative than the aggregate, so sealed at the same standard |

## When it unseals, and the check that runs when it does

Work package 11, the frozen held-out evaluation, after the selector freeze is recorded in the
manifest. Not before, and not by anything else.

**Unseal condition:** the selector freeze is recorded in `FROZEN_MANIFEST.json`, **and** work package
11 is the caller. `--held-out-eval` exists for that call and no other.

**Integrity check at unseal (A-2).** Every file here has its sha256 recorded in
`results/manifests/V2_SEALED_HASHES.json`. Work package 11 **recomputes them and compares**. A
mismatch means something changed between sealing and unsealing: **stop and report** — do not
proceed, do not re-seal, do not assume it was benign. The check costs nothing and is not optional.

**Enforced, not promised.** `tests/test_sealed_heldout.py` (gate 22) fails if any live script can
read this directory, if anything but work package 11 passes `--held-out-eval`, if held-out accuracy
appears outside this directory, or if a recorded hash no longer matches. Its self-test plants a
reader (must FIRE), a docstring-only mention (must stay silent) and a flag-passing caller (must
FIRE).
