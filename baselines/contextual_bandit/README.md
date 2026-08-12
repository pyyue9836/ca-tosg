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
construction trained to our protocol, not an external method's reported number. Its evaluation is
descriptive plus paired bootstrap CIs only: the confirmatory primary was spent once at R9 and is
not re-created here.
