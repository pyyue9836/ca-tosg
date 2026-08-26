# v2 GPU cost — three tiers, calibrated on the V2-R1 sanity run

**Nothing here is approved.** These are estimates for Josh to price against. No mainline GPU runs
until he approves a tier *and* `docs/unified_branch_protocol_v2.md` has no NOT-LOCKED section.

## Calibration basis — and the finding that changes the shape of the answer

Measured on the V2-R1 sanity run plus a direct micro-benchmark. RTX 5070, `sionna310`, batch 1, the
unified attentive-compression checkpoint.

| quantity | measured |
|---|---|
| frames scored | 220 (every 9th validate frame, all 9 scenes) |
| forwards per scored frame | 2 (cooperative + single-vehicle) |
| wall clock | 3,361 s |
| aggregate s per scored frame | 15.28 s |
| **cooperative forward + post-process** | **0.0505 s** |
| **single-vehicle forward + post-process** | **0.0293 s** |
| **per-frame data load** (OPV2V yaml + LiDAR, `/mnt/h`) | **1.89 s** |
| dataset build | 0.93 s, once |

**This workload is I/O-bound, not GPU-bound, by roughly forty to one.** A forward costs 0.03–0.05 s;
loading the frame it needs costs 1.89 s from the Windows mount, and four DataLoader workers bought
almost nothing (the 220-frame run's effective cost was ~1.70 s per *loaded* frame). The whole of
tier A is about **0.2 GPU-h of actual computation**; everything else in the numbers below is waiting
for data.

Three consequences worth acting on before spending anything:

1. **"GPU-hours" is the wrong unit here.** The tiers are quoted in wall-clock hours on this machine,
   because that is what a run will actually take. A faster GPU would change almost nothing.
2. **Cache locality dominates.** Re-scoring 30 already-touched frames ran at 0.78 s/frame against
   1.70 s/frame cold — a 2.2× spread that is entirely page cache. Copying the split off `/mnt/h` onto
   the Linux filesystem is likely the single largest speed-up available, and costs no GPU.
3. **The sample was stratified, so it is not flattering.** Scenes 7 and 8 (dense, up to 7 CAVs,
   50 GT objects) supply 133 of the 220 frames, which is why the aggregate is high.

Data volume, all three splits: **validate 1980 + test 2170 + Culver-City 550 = 4700 frames**, mean
3.89 CAVs/frame, max 7.

---

## Tier A — mainline re-freeze (the minimum plan A needs)

Every action from the unified checkpoint, ideal delivery, all three splits.

| work | forwards |
|---|---|
| per-vehicle independent forward (feeds **E** and **L**) | 4700 × 3.89 ≈ 18,300 |
| cooperative forward (**F**) | 4700 |
| **total** | **≈ 23,000** |

Pure GPU computation: 4700 x 0.0505 + 18,300 x 0.0293 = **773 s = 0.21 h**. The rest is loading.

| | assumption | wall-clock h |
|---|---|---|
| conservative | warm cache (0.78 s/frame), one pass | **1.1** |
| **typical** | cold-ish (1.2 s/frame), one re-run after an amendment, +25 % slack | **4** |
| worst | cold (1.70 s/frame), two re-runs, +25 % | 8.5 |

Everything downstream of the detections — payload accounting, oracle labels, selector training, LOSO,
the freeze, the replay, tables and figures — is **CPU-only** and is not in this budget. In v1 that
whole chain ran in minutes.

---

## Tier B — transport as the main protocol (§5, partial recovery)

This is the expensive tier, and the estimate hinges on one engineering decision.

Under all-or-nothing delivery (v1) the effective score is an expectation over two known outcomes, so
no extra forward is needed. Under **partial recovery** the detector output depends on *which*
codewords survived, so a decode is required per (frame, condition, erasure draw).

**The decision that sets the price: re-run the whole network, or only the tail.** The per-CAV
bottleneck tensor is computed once; zero-filling lost codewords perturbs only the *transmitted*
tensor, after which just the AutoEncoder decoder, `AttFusion` and the two heads need to re-run. That
tail is a small fraction of a full forward.

| variant | work | note |
|---|---|---|
| full forward per condition | 4700 × 22 × `R` | 22 = 11 SNR × 2 channels |
| **tail-only re-decode** | same count, but a fraction `f_tail` of a forward | requires caching bottlenecks to disk |

| | `R` draws/condition | assumption | wall-clock h |
|---|---|---|---|
| conservative | 1 | tail-only, `f_tail ≈ 0.15` | 0.3 + a Tier-A pass |
| **typical** | 20 | tail-only | **5** |
| worst | 20 | full forward per condition | 30 |

**`f_tail` is a guess until measured.** Before Josh prices this tier, a ~10-minute micro-benchmark
should measure the tail fraction directly. **Recommendation: do not approve tier B on this
estimate** — approve the micro-benchmark, then price it.

Storage: caching per-CAV bottlenecks for 4700 frames × 3.89 CAVs × 739,200 elements at int8 is
on the order of **8 GB**; at float16, 16 GB. Not free, not prohibitive.

---

## Tier C — external baseline arm (§13)

**GPU: zero in this batch.** The gate is the selection report — reproducibility, code availability,
and whether the candidate can be brought onto all seven unified elements. A baseline that cannot be
re-scored on the same GT, FOV and transport re-creates the confound plan A exists to remove, so it
would cost GPU and buy nothing.

| | scope | wall-clock h |
|---|---|---|
| conservative | one candidate, inference only on the unified GT/FOV | 1.5 |
| **typical** | one candidate, inference + one re-run after alignment fixes | **4** |
| worst | two candidates, one needing retraining | 40+ |

Retraining is the tail risk: if a candidate ships no usable weights, the arm becomes a training job
and the estimate stops being an inference estimate. **That is a separate decision, not a slice of
this one.**

---

## Summary

| tier | conservative | typical | worst |
|---|---|---|---|
| A — mainline re-freeze | **1.0** | **4** | 8.5 |
| B — transport main-protocol | 0.3 + a Tier-A pass | **5** | 30 |
| C — external arm | 1.5 | **4** | 40+ |
| **A+B+C typical** | | **≈ 13 h wall-clock (A 4 + B 5 + C 4)** | |

Actual spend in V2-R1: **0.96 h** — 3,361 s for the 220-frame sanity run, 34 s for the
production-regime calibration, ~30 s for the micro-benchmark. Inside the `<1 GPU-h` estimate, with
almost none of it GPU.

**Recommended order:** A alone first — it is what makes the paper's central claim honest, and it is
the cheapest of the three. B and C are improvements on top of a corrected result, and neither is
worth spending before A has landed.
