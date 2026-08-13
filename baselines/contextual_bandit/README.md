# Contextual bandit (internal learned-policy comparator, P4-A)

An external **learned-policy** comparator for the same decision the CA-TOSG selector makes:
one action per frame from {E, L, F}, under the same budget, from the same features.

| | |
|---|---|
| **Source paper** | None — this is not a reproduction. It is a standard single-step contextual bandit (ε-greedy DQN, immediate reward) constructed here as an RL-flavoured comparator, pre-registered in `docs/experiment_protocol.md` Appendix C / Change-log P4-A before it was run. |
| **Modifications** | n/a. The specification is the `CATOSG-P4A` block in the protocol: 2×64 ReLU, 4000 steps, batch 512, Adam lr 1e-3, ε 1.0→0.05 over 3000 steps, reward `eff_a − λ·B_a`, z-scored features, seed 0. |
| **Erratum** | **P4A-1 (2026-08-12): the earlier results are WITHDRAWN.** The z-score statistics were fitted on the whole validate grid before LOSO, leaking each held-out scene into its own fold and into λ selection. Fixed to fold-local scaling, retrained and re-evaluated; see the change-log and Appendix C. |
| **Checkpoint** | `data/p2/p4a_bandit_B0{10,20,30}.pt` (git-excluded); freeze record `results/manifests/P4A_MANIFEST.json`. |
| **Data split** | Identical to the mainline: fitted on **validate** only, scene-level 9-fold LOSO for λ selection, frozen, then evaluated once on test and Culver-City. |
| **Run command** | `python tools/run_baselines.py contextual_bandit --train` then `--evaluate` |
| **Output** | `results/baselines/contextual_bandit.csv` (summary) and `results/baselines/contextual_bandit_runs/` (per-split replays, LOSO OOF, walk). Provenance: `results/provenance/PROVENANCE_p4a.txt`. |

**Labelled "internal learned-policy comparator, not deployed" everywhere it appears** — it is our own
construction trained to our protocol, not an external method's reported number.

## What this result is, and is not

After the P4A-1 leak fix, all three budgets select the **same** conservative policy (λ\*=0.05,
walk depth 0 everywhere), so the budget is not binding on it. On the held-out splits it is **not
better than the deployed RF** — F1 below RF in every test and Culver-City cell, CI entirely < 0 —
and at B_max = 0.10 it spends 0.156 Msym/frame on test, **above the 0.10
average budget it was frozen under**, where the RF stays at 0.068.

Treat it as an **internal diagnostic**, not as evidence that CA-TOSG beats reinforcement learning:
it is not a published baseline and it is not tuned as an opponent would tune it. On **validate**
(in-sample) it does edge past the τ rule at B_max 0.10 and 0.30, CIs excluding 0 — recorded in
Appendix C for completeness, and carrying no weight against the held-out splits.

The evaluation is descriptive plus paired bootstrap CIs only: the confirmatory primary was spent
once at R9 and is not re-created here.
