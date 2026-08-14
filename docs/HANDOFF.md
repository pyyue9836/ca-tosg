# HANDOFF — read this first in a new session

Written 2026-08-14. Everything below is checkable from the repo; nothing here is memory.

```
repo    /home/josh/cooperative_semantic_perception/ca-tosg   (remote: github.com/pyyue9836/ca-tosg)
branch  p1-phy-rebuild        HEAD 6136c3d        working tree clean
tag     pre-bevformer-style-restructure = 59a3d1c  (pre-restructure snapshot, keep)
env     conda activate sionna310   (python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2.2.2
                                    -- these exact versions are pinned by FROZEN_MANIFEST.json)
gates   python tools/verify_results.py              all 9, needs data/p2/ + ../OpenCOOD/
        python tools/verify_results.py --content-only   the 7 a clean clone can run
```

**Everything is currently green: `ALL GATES PASS` (9/9).** If that is not true when you start,
stop and find out why before doing anything else.

## The two things actually blocked, waiting on Josh

1. **P4-B (second backbone) — the SECOND checkpoint will not load.** All 160 keys match (0 missing,
   0 unexpected); 12 `backbone_3d` sparse-conv kernels have the wrong axis order, because the
   weights were saved under spconv 1.x `(kD,kH,kW,C_in,C_out)` and the environment has spconv 2.3.8,
   which wants `(C_out,kD,kH,kW,C_in)`. `model_shape == permute(ckpt_shape,(4,0,1,2,3))` exactly.
   **Nothing was patched, deliberately.** The ruling needed: is a layout-converted checkpoint
   acceptable for a generality arm whose point is that the weights are the official ones? Until
   that is answered, the dummy forward and the payload_audit extension items cannot be produced.
   Full record: `results/manifests/P4B_MANIFEST.json`, change-log `P4-B-b`.
   *Settled already:* main variant = `second_attentive_fusion_compression` (its
   `base_bev_backbone.compression: 2` matches the deployed mainline F branch).
2. **`sec:difficulty` is still legacy-engine.** It reports `+0.090` on hard frames with its own
   figure, produced by `ablations/a2_difficulty.py` (the v3 200-realisation engine), not by the
   frozen selectors. P5 batch 2 deleted the *restatements* of that number elsewhere but left the
   subsection standing, because editing its prose alone would leave the figure contradicting the
   text. It needs its own migration round.

## Where the work stands

- **Repository layout**: BEVFormer-style, per `RESTRUCTURE_PLAN.md` (the supervisor's text,
  verbatim). Per-file map: `RESTRUCTURE_MAP.csv`. `paper1/` no longer exists.
- **Two scientific errata are closed**: P4A-1 (standardisation leak — results withdrawn and re-run;
  it changed two conclusions) and P3-1 (SNR sampled off the pre-registered grid — regenerated, no
  conclusion changed). Both have guards in `tests/`.
- **Experiments finished**: FA-1 feature ablation; P4-C collaborator scale N∈{1,2,3} semantics A
  (all splits) and semantics B (validate bracket, N=2 — the bracket is tight, ~4th decimal).
- **P5 main-text migration**: batches 1 and 2 done. `main.tex` is unfrozen and edited; the claims
  ledger is regenerated (107 rows, 0 STALE, 17 filled / 90 pending, 0 dangling).
- **Deferred, not forgotten**: the `sec:difficulty` round above; re-verifying the remaining 24
  modulation-context `C_{16}` mentions if the notation table is not judged sufficient; the
  evidence back-fill for the 90 pending ledger rows.

## Working rules that are not obvious from the code

- **Pre-register before running.** Every experiment above has a change-log entry written *before*
  the first forward pass, with its expectations. When an expectation misses, the miss is the
  finding — see P4-C, where a buggy first run *confirmed* an expectation and the corrected run
  refuted it, and the thing that separated them was a machine-checkable invariant written in
  advance.
- **A gate that cannot verify must never report success.** The artefact-tier gates fail loudly on
  missing data rather than skipping.
- **Never blend engines.** The legacy v3 200-realisation engine and the P2 frozen-selector replay
  are different quantities; a sentence may not mix them. This is why two v2 numbers were deleted
  rather than "recomputed".
- **Frozen means frozen.** Deployed models, δ, τ\*, `FROZEN_MANIFEST.json`, the mainline replay and
  every committed result CSV are read-only unless a change-log entry says otherwise. Variant
  artefacts get their own manifest (`P4B_`, `P4C_`, `FEATURE_ABLATION_`) and are labelled
  "not deployed".
- **`main.tex` is read byte-exactly by three gates** (stale-fingerprint block-exit, `docs/claims.md`,
  paragraph insertion). Edit it, then regenerate the ledger with
  `python tests/test_result_consistency.py`.
- Josh writes in Chinese; reply in Chinese. Lead any reply about committed work with the
  `git ls-remote` hash.

## The authoritative documents

| file | what it is |
|---|---|
| `docs/experiment_protocol.md` | THE normative source: protocol, change-log, errata register, appendices A–F |
| `docs/p5_migration_list.md` | the P5 inventory (what still has to move in `main.tex`) |
| `docs/p4c_plan.md` | the P4-C plan as greenlit |
| `RESTRUCTURE_MAP.csv` | old path → new path for every file, plus 887 literal rewrite points |
| `results/README.md` | which command generates which result file (140 files, 0 unattributed) |
