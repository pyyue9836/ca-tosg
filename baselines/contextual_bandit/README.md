# Contextual bandit (baseline, P4-A)

An external **learned-policy** comparator for the same decision the CA-TOSG selector makes:
one action per frame from {E, L, F}, under the same budget, from the same features.

| | |
|---|---|
| **Source paper** | None — this is not a reproduction. It is a standard single-step contextual bandit (ε-greedy DQN, immediate reward) constructed here as an RL-flavoured comparator, pre-registered in `docs/experiment_protocol.md` Appendix C / Change-log P4-A before it was run. |
| **Modifications** | n/a. The specification is the `CATOSG-P4A` block in the protocol: 2×64 ReLU, 4000 steps, batch 512, Adam lr 1e-3, ε 1.0→0.05 over 3000 steps, reward `eff_a − λ·B_a`, z-scored features, seed 0. |
| **Checkpoint** | `data/p2/p4a_bandit_B0{10,20,30}.pt` (git-excluded); freeze record `results/manifests/P4A_MANIFEST.json`. |
| **Data split** | Identical to the mainline: fitted on **validate** only, scene-level 9-fold LOSO for λ selection, frozen, then evaluated once on test and Culver-City. |
| **Run command** | `python tools/run_baselines.py contextual_bandit --train` then `--evaluate` |
| **Output** | `results/baselines/contextual_bandit.csv` (summary) and `results/baselines/contextual_bandit_runs/` (per-split replays, LOSO OOF, walk). Provenance: `results/provenance/PROVENANCE_p4a.txt`. |

**Labelled "external baseline, not deployed" everywhere it appears.** Its evaluation is
descriptive plus paired bootstrap CIs only: the confirmatory primary was spent once at R9 and is
not re-created here.
