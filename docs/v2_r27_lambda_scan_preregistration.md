# Pre-registration — exploratory fine λ scan (V2-R27 D)

| field | value |
|---|---|
| registered at | **2026-08-29T08:47:38Z** |
| parent commit | **342fc35c2ed5b38696b965900a36d52edf407170** |
| status | **EXPLORATORY DIAGNOSTIC — outside the main analysis** |

Written and committed **before the scan produced any number** (D-4). The main freeze — candidate 67,
λ = 0.2, all three budgets — is already committed at the parent above and is **not** revisited by
anything in this document.

## The single question

**Is the F-collapse a property of the cost structure, or of the resolution of the pre-registered λ
grid?**

The main grid samples λ ∈ {0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50}. The measured break-even value —
the λ at which F's mean net utility gain equals its payload cost — is **0.01556**, which lies in the
**unsampled** interval (0, 0.02). So the grid never had a point where a mixed E/L/F policy could be
selected, and the question cannot be answered from the main grid at all.

## What will be run

λ = 0.001, 0.002, …, 0.019 (19 points), **validate only**, `ideal` regime, everything else
identical to the main run: same features (`v2_ego_local_23d`), same scene-level 9-fold LOSO, same
tie-break, same seed.

## Binding constraints, fixed now

1. **Candidate 67 is not replaced**, whatever the scan shows (D-3).
2. **No number from this scan enters** the primary success criterion, the abstract, the contribution
   list, or the claim portion of the conclusion.
3. If a genuine E/L/F trade-off point exists in the scanned interval, it is reported as
   **"the pre-registered grid was too coarse to sample this interval"** — a statement about
   resolution — and registered as a pre-registered item for a revision or for future work. **It does
   not retroactively modify this freeze** (D-5).
4. If no such point exists, that is reported as measured, and it does *not* license the phrase
   "F is economically unviable" either: the scan bounds the resolution question, not the cost
   question.

## Forbidden wording, carried from V2-R27 B-4

**"F is economically unviable" and its variants are forbidden.** The permitted statement is: *on the
pre-registered λ grid, F was not selected by any budget-feasible candidate*; whether that is caused
by the cost structure or by grid resolution is what this scan exists to separate, and the scan is
diagnostic only.
