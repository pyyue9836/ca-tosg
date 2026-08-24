# SComCP baseline — inventory and evaluation plan (PLAN ONLY, awaiting Peiyi)

**Nothing has been trained, evaluated or run on the GPU for this document.** It is a static
inventory of `baselines/scomcp/` plus a pre-registration proposal. Phase-1 item 3 (producing
`results/baselines/scomcp.csv`) begins only after this plan is approved.

---

## 1. Inventory — what exists, what is missing

### Present (code-only, 72 KB, 11 files)

| file | role |
|---|---|
| `train_scomcp.py` | 3-stage trainer; `--warm_start` loads weights `strict=False`; freezing driven by the config's `freeze:` list |
| `configs/scomcp_stage{1,2,3}_*.yaml` | stage 1 selector / stage 2 codec / stage 3 joint |
| `eval_sweep_scomcp.py` | per-SNR sweep → CSV `scheme, channel, snr_db, ap50, ap70, com_rate` |
| `run_scomcp.sh`, `run_smoke.py`, `smoke_test.py`, `diagnose_selector.py`, `plot_figures.py` | drivers / smoke / plots |

The two model modules the scaffold needs **do exist** in the OpenCOOD tree:
`opencood/models/fuse_modules/scomcp_fuse.py` (13.4 KB) and
`opencood/models/point_pillar_importance_map_jscc.py`, which dispatches on `variant: scomcp`.
`SComCPFuse` subclasses `ImportanceMapJSCC` and swaps only the selector and the codec.

### Missing — this is what blocks real numbers

1. **No checkpoint. No stage has ever been trained to completion.** The README states this outright,
   and there is no `scomcp*` directory under `/mnt/h/opencood_project/outputs/experiment_logs/`
   (only `importance_map_jscc`, `where2comm_train`, `where2comm_eval`).
2. **No output.** `results/baselines/scomcp.csv` does not exist; the folder is deliberately listed
   `NOT-CREATED` in `RESTRUCTURE_MAP.csv` rather than stubbed.
3. **No official weights exist to download.** SComCP is TVT 2026; the authors publish no
   checkpoint, so there is nothing to hash and record as an EXTERNAL INPUT. **Training is the only
   route to a real number** — unlike SECOND, where the zoo supplied weights.
4. **`run_scomcp.sh` paths are stale** (`peiyi_work/02_scomcp_reproduction/...`, pre-restructure) and
   `BASE_CKPT` is an unedited placeholder.

### Dependencies

No new dependency: `scomcp_fuse.py` needs only torch, and the channel helper is the JSCC arm's
`build_channel`, already in use.

---

## 2. Three decisions that must be settled before training (they change the numbers)

**(a) Training split — a deliberate deviation from the source paper.**
The configs train on `opv2v_data_dumping/train` (6,764 frames), which is what the paper does. The
standing constraint for this repository is **training may use `validate` only**; `test` and
Culver-City are held out. Proposal: **train on `validate` (1,980 frames)** and disclose the
deviation explicitly — the baseline is then trained on 3.4× less data than the paper's, so its
absolute AP is expected to sit **below** the published ≈0.88, and the arm must be read as a
*controlled in-repository reproduction*, never as a reproduction of the paper's absolute numbers.
*Alternative if you prefer paper fidelity:* train on `train`, and drop the arm's claim to sharing
the mainline's training-data discipline. **These cannot both be had; I need your ruling.**

**(b) Step budget — match the JSCC arm, not the configs.**
The configs ask for 30 + 30 + 20 epochs at batch 1 = **158,400 steps on validate** (≈17 h). The
JSCC arm in this repository — the thing SComCP must be comparable to — was trained for
**4,000 steps** (`stage2_whole_map_4000steps.pth`, registered in `docs/data_manifest.md`).
Proposal: **4,000 / 4,000 / 2,000 steps** for stages 1/2/3 (10,000 total), which keeps the two
learned baselines on a comparable training budget and is the honest way to compare them. Pre-register
the exact numbers; no tuning-by-peeking afterwards.

**(c) Warm start.** `SComCPFuse` subclasses `ImportanceMapJSCC`, so the natural warm start is the
registered JSCC stage-2 checkpoint for the matching channel
(`stage2_{awgn,rayleigh}_learned_v3/stage2_whole_map_4000steps.pth`, md5 `74c1319ab562` /
`c5a02fd77154`). Proposal: **warm-start stage 1 from the Rayleigh JSCC stage-2 checkpoint** (the
paper trains under Rayleigh), record its md5, and state that SComCP therefore starts from the
baseline it is meant to improve on — which is the fairest reading and also the cheapest.

---

## 3. Proposed evaluation scope — isomorphic to the Appendix-A JSCC arm

The JSCC arm's shape, which this mirrors exactly:

> per-SNR config template → inference with `--save_npy` → per-frame F1 via the shared
> `f1_from_boxes` at IoU 0.5 → a column directly comparable to `late_f1` / `compressed_f1`.

**Proposed pipeline** (`baselines/scomcp/perframe/`, mirroring `baselines/importance_map_jscc/perframe/`):

1. Template the SComCP config per (channel, SNR) — the pre-registered 11-point grid
   {0,2,…,20} dB, channels **AWGN** and **Rayleigh**.
2. Run inference with `--save_npy`, dumping per-frame boxes/scores/gts.
3. Score per-frame F1 with the **same scorer, same canonical union GT, same IoU-0.5 unit-score
   convention** as `late_f1` / `compressed_f1` / `jscc_f1`.
4. Emit `results/baselines/scomcp.csv` in the JSCC arm's schema
   (`channel, split, snr_db, n, scomcp_f1, ap30, ap50, ap70`) + `PROVENANCE_scomcp.txt`.
5. The **200-realisation replay is CPU-only** and costs no GPU: it draws (SNR, channel) over the
   already-computed per-frame table, exactly as the JSCC selector comparison does.

**Open item to flag now, not discover later.** A same-table comparison against `L` and `F` needs a
**payload convention for SComCP**. `eval_sweep_scomcp.py` reports a `com_rate`, but the mainline's
axis is Msym/frame under rate-1/2 + 16-QAM. This is the same question the SECOND arm hit; the
equal-budget answer used there (`B ≡ 0.99 Msym`, mainline `N_cw`) is available and would keep the
figure honest, but it is **your call** and I will not pick it silently.

### GPU estimate

Anchored on measured cost in this repository, not guessed: the JSCC per-frame sweep was
**~10 GPU-hours for 36 runs** (`docs/data_manifest.md`) ⇒ **≈0.28 h per (channel, SNR, split)**.

| option | runs | eval GPU | + training | total |
|---|---|---|---|---|
| **A — full**: 2 ch × 11 SNR × 3 splits | 66 | ≈18 h | ≈1.5 h | **≈20 h** |
| **B — recommended**: 2 ch × 11 SNR × {validate, test} | 44 | ≈12 h | ≈1.5 h | **≈14 h** |
| **C — JSCC-parity**: 2 ch × 6 SNR × {validate, test} | 24 | ≈7 h | ≈1.5 h | **≈8.5 h** |

**Recommendation: B.** It covers the full pre-registered SNR grid on the two splits every other
table in the paper reports, and Culver-City can be added later without redoing anything. Option C
matches the JSCC arm's own SNR sampling exactly if you would rather the two arms be identical in
coverage as well as in method.

---

## 4. What phase-1 item 3 will produce once approved

`results/baselines/scomcp.csv` + `results/provenance/PROVENANCE_scomcp.txt`, both labelled
**descriptive baseline, no decision**, with the training split, step budget, warm-start md5, SNR
grid and payload convention recorded. No adjudication, no δ, no change to any frozen product.

**Fuse conditions to pre-register with the run:** if the trained SComCP's AP@0.5 on validate at
20 dB AWGN falls below the `Fixed L` reference, or if its per-frame F1 is flat in SNR (no codec
response at all), the run stops and reports — that would mean the scaffold does not train, not that
SComCP is bad, and the two must not be confused in the write-up.
