# HANDOFF — read this first in a new session

Written 2026-08-14. Everything below is checkable from the repo; nothing here is memory.

```
repo    /home/josh/cooperative_semantic_perception/ca-tosg   (remote: github.com/pyyue9836/ca-tosg)
branch  p1-phy-rebuild        working tree clean   (HEAD: see `git log -1`; this file is not the
                                                    place to keep a hash in sync)
tag     pre-bevformer-style-restructure = 59a3d1c  (pre-restructure snapshot, keep)
env     conda activate sionna310   (python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2.2.2
                                    -- these exact versions are pinned by FROZEN_MANIFEST.json)
gates   python tools/verify_results.py              all 9, needs data/p2/ + ../OpenCOOD/
        python tools/verify_results.py --content-only   the 7 a clean clone can run
```

**Everything is currently green: `ALL GATES PASS` (9/9).** If that is not true when you start,
stop and find out why before doing anything else.

## The two things waiting on Josh

1. **P4-B — the load blocker is CLOSED; what is open now is the payload accounting.**
   The checkpoint was converted (`permute(4,0,1,2,3)` on the 12 `backbone_3d` sparse-conv kernels —
   spconv's own RSCK→KRSC migration, applied *once*, because spconv 2.3.8's convenience hook applies
   it twice and still fails to load), and the conversion was then **earned empirically**: official
   `intermediate` inference reproduces the model zoo's own published AP@0.7 —
   **test 0.78384 vs 0.783, Culver 0.76188 vs 0.760**, both far inside ±0.005, on the zoo's own
   no-global-sort convention. Change-log `P4-B-c`; records in
   `results/manifests/P4B_{CONVERSION,VERIFICATION_compression,DUMMY_FORWARD_compression}.json`.
   **Now open, and it needs Josh:** the dummy forward showed the pre-registered payload estimate was
   wrong. The `_compression` variant does **not** transmit the 9.01 M-element HeightCompression
   tensor; `AttBEVBackbone` has two branches, each with its own `AutoEncoder`, and both bottlenecks
   go on the wire — **352,000 elements/CAV/frame** (32×25×88 + 128×25×88), 25.6× smaller. So
   `B_F^SECOND` has two self-consistent derivations differing by more than an order of magnitude:
   bit-depth × the transmitted bottleneck count, or the mainline's fixed 1.98 Mbit source budget
   (≈0.92 bit/element) applied to the uncompressed tensor. **Nothing was chosen.**
   Still unstarted by design: the eff-cache / grid-expansion batch, P4-B items (1) and (3). Only the
   `_compression` variant carries a verified label.
   *Settled earlier:* main variant = `second_attentive_fusion_compression` (its
   `base_bev_backbone.compression: 2` matches the deployed mainline F branch).
2. **The legacy-engine clean-up is inventoried and the rulings are drafted — `main.tex` untouched.**
   `sec:difficulty` was **not** the only legacy subsection. A mechanical sweep
   (`tools/audit_claims_evidence.py` → `docs/claims_evidence_audit.md`) found **14 of 107 claims
   across 10 sections** resting on a retired engine, including two nobody had flagged:
   **`sec:generalisation`'s entire per-SNR AP-knee narrative** (3 claims, scored by the v3
   global-sort scorer `true_e2e_global.py`) and a **`+0.090` survivor in the Conclusion**
   (`main.tex:904`) that batch 2's record says was deleted. The `+0.090` family lives in three
   places: `main.tex` 662 (prose), 678 (figure caption), 904 (Conclusion).
   Per-section rulings — recompute / demote-to-appendix / delete, each with its compute cost and
   dependency — are in **`docs/p5_batch3_legacy_rulings.md`**, **proposed only**.
   **Awaiting Josh's ruling before any prose moves.** Change-log `P5-4`.

## Where the work stands

- **Repository layout**: BEVFormer-style, per `RESTRUCTURE_PLAN.md` (the supervisor's text,
  verbatim). Per-file map: `RESTRUCTURE_MAP.csv`. `paper1/` no longer exists.
- **Two scientific errata are closed**: P4A-1 (standardisation leak — results withdrawn and re-run;
  it changed two conclusions) and P3-1 (SNR sampled off the pre-registered grid — regenerated, no
  conclusion changed). Both have guards in `tests/`.
- **Experiments finished**: FA-1 feature ablation; P4-C collaborator scale N∈{1,2,3} semantics A
  (all splits) and semantics B (validate bracket, N=2 — the bracket is tight, ~4th decimal);
  **P4-B-c**, the SECOND checkpoint conversion + zoo-AP reproduction (item 1 above).
- **P5 main-text migration**: batches 1 and 2 done. `main.tex` is unfrozen and edited; the claims
  ledger is regenerated (107 rows, 0 STALE, 17 filled / 90 pending, 0 dangling). **Batch 3 part 1
  (inventory) is done and `main.tex` was not touched** — see item 2 above.
- **Ledger back-fill, as the audit now measures it**: 14 claims LEGACY-ENGINE, 16 FROZEN,
  23 ANALYTIC, 54 still without a located source (36 of those carry no distinctive number —
  `802.11bd`, `16`-QAM, IoU `0.5` — and 18 carry numbers no committed result file holds; the
  `6.9`–`18.9\%` channel-use headline is in that second group and appears in both the abstract and
  the Conclusion). Read the `[k/n]` match strength before trusting a located row.
- **Deferred, not forgotten**: executing the batch-3 rulings once Josh decides; re-verifying the
  remaining 24 modulation-context `C_{16}` mentions if the notation table is not judged sufficient;
  writing the located evidence into the ledger's own cells.

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
