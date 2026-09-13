# P2 protocol — DRAFT, NOT LOCKED

**Status.** Draft under P2-R1 (section C) as revised by P2-R3. **Zero experiments before lock.** No
selector training, no GPU, no feature experiment, and nothing in `selector/`, `gates/` or `metrics/`
until this document is locked.

**Provenance of this revision.** P2-R3 refers to P2-R2 and to a "Finding 0". **P2-R2 was not received
in the session that wrote this file.** The C-6 result paragraph of the P2-R1 draft is therefore
relabelled **Finding 0** and replaced by P2-R3 A-1's text. P2-R3 D-1 asks for an ego-box-count proxy
to be deleted; no such text existed in this draft, so there was nothing to delete.

**What exists before lock, and why none of it is an experiment.** Each file below is generated, reads no
perception output, and has a `--check` mode that fails if the recorded output is not what the generator
writes.

| file | generator | what it holds |
|---|---|---|
| `p2_reuse_manifest.json` | `build_reuse_manifest.py` | P1 artefacts P2 reuses, by path and sha256; chain and C-7 verification (payload columns only) |
| `link_scenarios.md` / `.json` | `link_scenarios.py` | C-6 resource table, A-2 facts, B-3 reference column, D-1 L bound |
| `gpu_estimate.md` / `.json` | `gpu_estimate.py` | GPU-time estimate for `data_plan.md` (an estimate; nothing run) |

Beside it: `data_plan.md` (P2-R3 E, reported only) and `full_f_feasibility.md` (P2-R9, the complete-F transmission audit). The sparse-selection line is closed and archived under `archive/p2-sparse-exploratory/`.

---

## A, B, D, E of P2-R1 — placeholders

P2-R1 revision C states that its sections A, B, D and E are unchanged. **Their text was not received**,
so it is not reproduced or reconstructed here. Josh inserts them verbatim before lock.

---

## Finding 0 — conditional accounting, not a general conclusion

> Under P1's payload and PHY accounting (B_F = 3.14175 Msym per frame), complete transmission of the F
> message within a 50/100 ms window is infeasible in every examined resource configuration
> (zero-overhead upper bound). The closest configuration exceeds the window by ≈1%. Parameters marked
> unverified in link_scenarios.md remain so.

**What F already is** (P2-R3 A-2; `docs/unified_branch_protocol_v2.md` §3.2 and §3.3, and the checkpoint
probe `results/manifests/P4B_PROBE_pointpillar_compression.json`; the generated figures are in
`link_scenarios.md`):

* F already includes the checkpoint's **in-network compression** — 3,942,400 elements before
  compression, 739,200 transmitted, 5.33× — **and 8-bit quantisation**.
* **Branch 2 (563,200 elements) is not compressed** and is 76.2 % of the transmitted elements.
* To meet a 20 MHz, 100 ms window **under the zero-overhead upper bound**, F would still have to shrink
  by about 2.1–2.3× (per-row values in `link_scenarios.md`); on a real link, with sharing and overhead,
  by more.

**Scope of the finding.** It is a statement about **this checkpoint's F message under P1's accounting
and the configurations examined**. It is not a statement about V2V links in general, and no sentence in
this protocol or derived from it may say that F cannot be transmitted on V2V links.

**P1 Limitations sentence (P2-R3 A-3) — wording only, not applied here.** Adding it to P1 is a P1
change and is outside this batch (P2-R3 F-2). When it is added, it reads conditionally:

> Under the payload and PHY accounting used in this paper, the feature message of this checkpoint could
> not be delivered in full within a 50 or 100 ms window in any resource configuration we examined, even
> at a zero-overhead upper bound; this concerns this message and these configurations, not V2V links in
> general.

---

## C. Protocol

### C-1 Research objective

> 在明确的通信资源与时限约束下，最大化接收端预期感知效果；效果相同时选通信开销更小的动作。

Maximise the receiver's expected perception outcome under explicit communication-resource and time
constraints; between actions with equal outcome, choose the one with the smaller communication cost.

* no `F1 − λ × payload` objective;
* no prescribed share of F;
* **"prefer F, degrade when necessary" must emerge from the objective**, not be written into the labels.

### C-2 Main objective and the offline reference decision

Action set `A = {E, L, F}`. For frame `t` with channel state `c_t`:

```
Q_t(a) = E_{ω | c_t} [ F1( Ŷ_t^{a,ω}, Y_t ) ]
a*_t   ∈ argmax_{a ∈ A_feas,t} Q_t(a)
```

Ties — `|Q_t(a) − Q_t(a')| ≤ TOL`, **`TOL = 1e-9`, preregistered** — go to the smallest payload.

**Reuse of P1.** `Q_t(E)`, `Q_t(L)`, `Q_t(F)` are P1's `eff_E`, `eff_L`, `eff_F` under P1 §9.3 (a)–(g),
pinned in `p2_reuse_manifest.json`. For any **new** F representation they would **not** be reused: its `eff_F` would be regenerated in
full. No new F representation is in scope (P2-R9 item 2). Whether P1's replicate average and
closed form are the estimator of the expectation over `ω` that P2 locks is a C-10 item.

**Tie order.** On every validate frame `B_E = 0 < B_L,t < B_F`, so "smallest payload" is the fixed order
**E ≻ L ≻ F**, P1's Eq. (7) order.

**Offline only.** `a*_t` uses realised outcomes. The deployable selector predicts from ego-side cues and
the estimated channel alone.

### C-3 Admissibility — the communication time-window constraint

No BLER threshold. P2-R3 D-3 adds collaborator availability:

```
A_feas,t = {E} ∪ { a ∈ {L, F} : avail_t = 1  and  N_sym,t(a) ≤ R_sym,t · D_comm }
```

* **`avail_t`** is decided from neighbour and connection state **known before the decision** — as in P1,
  from vehicle identities, relative poses and the fixed communication range, obtainable in deployment
  from periodic awareness messages. **Information that exists only after reception must not be used.**
* **`N_sym`** is P1's billing chain, verified (`p2_reuse_manifest.json`).
* Decoding failure, L's fallback and F's partial recovery are **inside `Q_t`**, not in `A_feas,t`.
* Named the **communication time-window constraint**; not an end-to-end real-time guarantee.

**The L bound (P2-R3 D-1, D-2).** D-1 asks for L's maximum payload from the existing cap on detected
boxes. **The pipeline has no such cap:** post-processing applies a score threshold, box-validity
filters, rotated NMS and a range mask, and never limits the number of predicted boxes;
`postprocess.max_num` sizes the ground-truth array only (`link_scenarios.md` [S13]). The only structural
bound is the anchor count, and whether L at that bound fits every row is in `link_scenarios.md`.

**So feasibility cannot rest on an existing cap, and D-2's second branch applies:**

* an **L payload cap** `N_L,max` (boxes per message) and a **target-filtering rule** for frames above it
  (which boxes are kept) are to be designed;
* the **impact of truncation** on `Q_t(L)` is a **development-experiment item**;
* once the cap exists, feasibility for L uses `N_sym(N_L,max)`, and the collaborator's current box count
  is not needed at decision time.

Until then the offline reference can evaluate `N_sym,t(L)` from the realised count; a deployable
selector cannot.

### C-4 Benefit gate

Threshold **0**: `Δ_F,t = Q_t(F) − max{Q_t(E), Q_t(L)}` over feasible actions, already inside C-2's
maximisation. Any threshold above 0 is a new hypothesis. With C-2's tolerance, F is chosen exactly when
`Δ_F,t > TOL`; that is numerical tie handling, not a margin.

### C-5 Metrics

**Primary: scene-equal F1.** **Hard-frame subset:** under a fixed detection range and IoU rule, frames
where the fixed E branch misses at least one ground-truth object — set by the fixed E branch and the
annotations, not by any policy, and not a deployment input. P1's candidate rules (F1 at IoU 0.5,
`projects/ca_tosg/evaluation/canonical_f1.py`; union ground truth; `cav_lidar_range`) are pointed to, not
locked. Under a union ground truth including collaborator-only objects the subset may be large; its size
is not computed.

Subset: recall and missed-object count; each policy's F1; misses F recovers relative to L; false
positives F introduces. Overall: payload; E/L/F shares; time-window satisfaction rate.

> This is perception evidence. It is not a proof of driving safety.

### C-6 Link scenarios

`link_scenarios.md` is the table; Finding 0 above is its reading. 802.11bd at 20 MHz; NR sidelink over
every n47 bandwidth and FR1 SCS (all verified valid for n47 in TS 38.101-1 Table 5.3.5-1); one and half
a LiDAR period; zero-overhead upper bound primary. **No parameter may be revised to change a column.**
**Scenarios are selected by Josh and the supervisor and written in afterwards.**

### C-7 Fixed MCS

> 固定 MCS 下 N_sym 不随 SNR 变化；差信道通过 Q_t(F) 下降促使降级，不得解释为发送时间变长。

P2 as drafted has neither rate adaptation nor retransmission, so the sentence stands unchanged. Verified
on the reused P1 grid (`p2_reuse_manifest.json`).

### C-8 Data

* **Development:** OPV2V `validate`. **Confirmatory evaluation: `test` and Culver-City are prohibited.**
* **OPV2V `train` is not confirmatory data** — its scenes trained the perception checkpoint (P2-R3 E-2).
* **The data plan** is `data_plan.md` (P2-R3 E): OPV2V for the F-representation question; a unified
  checkpoint trained on V2V4Real for the final system, shared by every action and baseline. **Decision
  pending.**

Candidate new data — facts from each source; the checkpoint row is an assessment, **not a test**:

| | V2V4Real | V2X-Real | DAIR-V2X |
|---|---|---|---|
| **Cooperation** | vehicle–vehicle, two vehicles | two vehicles + two infrastructure units; a V2V-only subset ("V2X-Real-V2V") | **vehicle–infrastructure**; not V2V |
| **LiDAR** | "Both vehicles are equipped with a Velodyne VLP-32 LiDAR sensor"; 200 m; 10 Hz | vehicles: 128 beams, 10 Hz; infrastructure: 128 / 64 beams | vehicle: 40 beams, 10 Hz; infrastructure: 300 beams, 100° horizontal FOV |
| **Classes** | five vehicle types | ten, including pedestrians and cyclists | ten, including pedestrians and cyclists |
| **Size / splits** | 20K LiDAR frames; 14,210 / 2,000 / 3,986 | 33K LiDAR frames; 23,379 / 2,770 / 6,850 | DAIR-V2X-C 39K frames; VIC3D 9,311 pairs, 5:2:3 |
| **Format** | OPV2V format; KITTI also released | OPV2V format | its own |
| **Availability** | direct downloads; **no data licence stated** on the page; code under an academic licence | direct downloads; **no data licence stated** on the page | download links in the README; **data terms not verified** (portal unreachable) |
| **Difference from OPV2V** | real, 32-channel vs simulated 64-channel | real, 128-channel, infrastructure agents, non-vehicle classes | real, V2I, limited infrastructure FOV |
| **P1 checkpoint directly usable?** | loads through the same format with classes merged, but is a **simulation-to-real shift**; under P2-R3 E-3 zero-shot use is **optional**, not the main confirmation, and **the degradation reported in the dataset paper is not quoted as an expectation for this checkpoint** | same format with a vehicle filter and the V2V subset; same shift concern, not quantified | **no** for a V2V protocol |

No data licence was established from the pages consulted; each must be confirmed with its provider.

### C-9 Statistics

* **Scene-level bootstrap**; the scene is the confirmatory unit.
* **Success criterion in form:** against the τ rule on scene-equal F1, with a non-inferiority margin
  `δ_NI` and a superiority criterion on the bootstrap bound. **Neither value is given in P2-R1 or P2-R3;
  this draft does not choose them** (C-10).
* **The τ comparator.** P1's rule requests F when the estimated SNR is at least τ and L otherwise
  (`projects/ca_tosg/evaluation/v2_p12_comparison.py`). Its definition under `A_feas,t` must be locked
  before the comparison means anything.

**Preregistered wording for the three outcomes:**

* **(a) Superiority established** — "Under [scenario], the selector achieved higher scene-equal F1 than the
  τ rule, with the scene-level 95 % lower bound on the difference above [criterion]."
* **(b) Non-inferiority established, superiority not** — "The selector was non-inferior to the τ rule
  within `δ_NI`; superiority was not established." Not rounded up to (a).
* **(c) Non-inferiority not established** — "Non-inferiority to the τ rule within `δ_NI` was not
  established." Reported with the payload result, never with the payload result alone.

No outcome may reopen the objective, the admissibility rule or the data rules.

### C-10 Items not yet locked

**From P2-R1, verbatim:**

* `D_comm` 数值与依据
* `R_sym` 与资源分配假设
* 是否含排队 / 请求 / 重传时间
* `ω` 的采样与期望估计办法
* 最终评价数据
* F1 匹配规则与难帧细则

**Closed by P2-R9:** the block-ranking question and the sparse line as a whole are closed; the
result is in `archive/p2-sparse-exploratory/README.md`. **Still pending:** the **data plan**
(`data_plan.md`).

**Raised by the drafts — listed so they are decided rather than defaulted:**

1. The mapping of **one P1 channel use to one data resource element** when comparing with a standard's `R_sym`.
2. **L has no payload cap** in the pipeline: `N_L,max` and the target-filtering rule are to be designed,
   and truncation evaluated in development (C-3).
3. **`δ_NI` and the superiority criterion** have no values (C-9).
4. **The τ comparator's definition under `A_feas,t`** (C-9).
5. ~~Receiver rule, block granularity and fusion adaptation for a sparse F~~ — closed with the sparse
   line (P2-R9); see `archive/p2-sparse-exploratory/README.md`.
6. **Unverified facts:** 802.11bd tone count rests on patent text (IEEE 802.11bd-2022 paywalled; no public
   secondary source located for 20 MHz); DAIR-V2X data terms; V2V4Real and V2X-Real data licences;
   V2V4Real scenes per split.

**Resolved since the P2-R1 draft:** n47 bandwidth and SCS validity (TS 38.101-1 V17.0.0 Table 5.3.5-1,
NOTE 10); N_RB now from the primary table (TS 38.101-1 Table 5.3.2-1); collaborator availability now in
`A_feas,t` (D-3).

**Until this document is locked, no implementation code is written in `selector/`, `gates/` or
`metrics/`.**

---

## Sources for C-8

* OPV2V — Xu et al., arXiv:2109.07644.
* V2V4Real — Xu et al., CVPR 2023, arXiv:2303.07601; https://github.com/ucla-mobility/V2V4Real;
  https://mobility-lab.seas.ucla.edu/v2v4real/.
* V2X-Real — Xiang et al., ECCV 2024, arXiv:2403.16034; https://github.com/ucla-mobility/V2X-Real;
  https://mobility-lab.seas.ucla.edu/v2x-real/.
* DAIR-V2X — Yu et al., CVPR 2022, arXiv:2204.05575; https://github.com/AIR-THU/DAIR-V2X; portal
  https://thudair.baai.ac.cn/index (unreachable at the time of writing).

C-6 sources are quoted in `link_scenarios.md`.


---

## P2-R9 — the sparse line is closed, and the subject of this batch is fixed

**Item 1. Closed.** The sparse-selection line (K_F = 23 of 55 blocks, three rankings) is stopped. Its
commits and every product are preserved unchanged in `archive/p2-sparse-exploratory/`, which records the
conclusion: the pre-registered benefit condition was not met (confidence − L = −0.00280, interval
spanning zero) while the complete F did beat L (+0.01444), and the ranking itself worked
(confidence − random = +0.06349). It is an exploratory side branch. **No new block-selection, recovery-network
or sparse-selector experiment is started.**

**Item 2. The subject of this batch is fixed.**

* **F** is the **complete bottleneck of the current model — all 55 blocks** — with the existing
  compression and int8 quantisation unchanged.
* **L** is the object-level message.
* **E** is ego-only perception.

**The content, precision and detection range of F do not change without an explicit decision.** No
sparse F, no transmission spread across frames and no lower sending rate is adopted or proposed here.

**Items 3–5** are answered in `full_f_feasibility.md`: the payload chain re-derived and checked, the
time to send the complete F on every configuration already listed in `link_scenarios.md`, and the
verdict — **no examined configuration delivers the complete F inside a 100 ms frame period**, so there
is no candidate for a degradation experiment yet, and the deficit sits in the message size.


---

## P2-R10 A — how the 100 ms result is used from here

**A-1. The 100 ms period is no longer a threshold that excludes F.** `full_f_feasibility.md` stands as
an independent record of the transmission-time audit; it is not a gate on the study object. The
limitation, in the wording to be quoted in the paper:

> 在所检 27 个配置下,完整 F 均不能在一个 10 Hz 帧周期内发完;本文以分析信道研究信道驱动的降级,
> 通信开销按 QAM 数据符号报告,逐帧时延可行性为独立限制。

In English, for the manuscript: *In all 27 configurations examined, the complete F message cannot be
delivered within one 10 Hz frame period. This paper studies channel-driven degradation over an
analytical channel; communication cost is reported in QAM data symbols, and per-frame latency
feasibility is a separate limitation.*

Two things follow, and neither is optional. Communication cost is reported in **QAM data symbols**
throughout, never as a delivery time, unless the audit is being quoted. And the latency limitation is
stated wherever a deployment reading could be taken from a result, rather than being left to the
reader to find in the appendix.

**A-2. The study object is unchanged:** the complete F (all 55 blocks, existing compression and int8),
L, and E — as fixed in the P2-R9 section above.


---

## P2-R11 A — the accounting, LOCKED

This section is **locked**. It replaces the open question of `message_regime.md` B-5; that document
stays as the costing that informed the choice.

**A-1 F is all-or-nothing.** The feature message is usable only if the whole message decodes:

```
q_F      = (1 - p_cw) ** 12567
eff_F    = q_F * F1_clean + (1 - q_F) * F1_ego
```

A failure falls back to **E**. **L is not sent instead after a failure** — there is no automatic
second attempt at another granularity. The form of this rule is P1's own message-level rule for L,
applied to F; the column it produces is constructed, not a stored P1 product, and is labelled so
wherever it appears.

**A-2 L is all-or-nothing on the same terms.** `q_L,t = (1 - p_cw) ** N_cw,L,t`, and a failure falls
back to E. This is P1's existing `eff_L`, unchanged.

**A-3 Communication is charged for the attempt, never multiplied by the success probability.** F costs
**3.14175 Msym** per request; L costs its own frame's `N_cw,L,t`; E costs nothing. A message that fails
has still occupied the channel.

**A-4 Partial recovery and packet-level accounting are removed from the candidate set.** P1's
partial-recovery results remain in the record as P1 results and **enter no table in this line of
work**.

**A-5 The scope sentence** (superseding the B-5 wording of `message_regime.md`):

> 不同信道模型下完整 F 的适用区间可能不同,甚至在所考察范围内不存在。

*The range of channel conditions in which the complete F is useful may differ under a different
channel model, and may not exist at all within the range examined.*


## P2-R12 B — pre-registered stopping rule for the AWGN fill

> **Superseded in part by Amendment 3 (P2-R13) at the end of this file.** B-2b (early stop)
> is withdrawn, B-2a's sample sizes are fixed rather than capped, and the reproduction criterion is
> replaced. B-3 and B-5 stand unchanged. The original text is kept below as the record of what was
> registered first.

**Registered before the measurement is run; nothing has been run under it.** The full plan, its
derivation and its cost are in `awgn_fill_plan.md`. The binding clauses are repeated here so the
protocol itself carries them:

**B-2a Minimum sample.** Each new SNR point runs **N_min = 1,000,000 codewords**. This follows from
the A-5 threshold: F overtakes L only at `p_cw < 1.37e-05`, and with zero errors the rule of three
resolves a rate only down to 3/N, so N ≥ 3 / 1.37e-05 = 218,978, rounded up to the next power of ten.

**B-2b Early stop.** A point that reaches **30 block errors** stops there.

**B-2c Reporting.** Every point reports codewords, errors, the `p_cw` point estimate and its **Wilson
95 % interval**.

**B-3 Zero errors is an upper bound.** A point with no errors at N_min is reported as `p_cw < 3/N at
95 %` with its codeword count. **It is never written as `p_cw = 0`**, and no sentence may state that
the message always arrives.

**B-5 New files only.** New points go to a new versioned grid file under
`projects/ca_tosg_p2/results/`. `results/channel/bler_sionna.csv` and `results/v2/v2_grid_validate_ideal.csv`
are not modified.

**The reproduction check is statistical, not bit-exact.** `ldpc_qam.py` sets no random seed, so a re-run
of 8.0 dB cannot return the recorded count. The criterion, fixed here in advance: the new and recorded
Wilson intervals must each contain the other's point estimate, and 10.0 dB must again give zero errors.
If either fails, the run stops and is reported.

**Permitted outcome.** If the crossing cannot be bracketed under this rule, that is reported as an
undetermined interval. N_min is not lowered and no tolerance is relaxed to obtain a crossing.

## Amendment 3 (P2-R13, 2026-09-13) — the fill runs under these rules

Supervisor-directed amendment to the P2-R12 B pre-registration, **made before any measurement was
run**. The superseded text is retained above. Reason recorded: an early stop at a fixed error count
makes the sample size a function of the observed data, and the reproduction criterion of P2-R12 tested
agreement of intervals rather than agreement of implementations.

**A-1 Fixed sample sizes; no early stop.** 8.5, 9.0 and 9.5 dB run **exactly 1,000,000 codewords
each**; 8.0 and 10.0 dB run **exactly 100,000 each** as reproduction checks. The "stop at 30 errors"
clause is **withdrawn**: every point runs to its full N whatever it observes.

**A-2 Two interval kinds, kept apart.** Each point records errors `k`, sample size `N`, the empirical
estimate `k/N`, and a **two-sided Wilson 95 % interval**. A point with `k = 0` additionally records a
**one-sided 95 % upper limit** `p_upper = 1 − 0.05^(1/N) ≈ 3/N`. The two are labelled distinctly and
are never presented as the same quantity.

**B-1 The check is an implementation check.** Coding parameters, modulation, the SNR definition, the
noise normalisation and the decoder iteration count are verified item by item against
`projects/ca_tosg/communication/ldpc_qam.py` inside `--check`.

**B-2 Randomness.** The seed and the software versions are fixed and recorded. **No claim of
bit-identical reproduction across environments is made.**

**B-3 Statistical re-check, reported not gated.** 8.0 and 10.0 dB are re-measured at 100,000 codewords
and the difference from the committed values is reported in full. **A small number of errors at 10 dB
is ordinary sampling variation, is not treated as an anomaly, and does not stop the run.**

**C-1 Both sides are recomputed.** `Q_F = q_F·F1_clean + (1−q_F)·F1_ego` and
`Q_L = q_L·L1_clean + (1−q_L)·F1_ego` are recomputed from the same new `p_cw` and compared as
`Q_F − Q_L`. L is **not** held at its old value while only F is updated.

**C-2 What 0.8415 is.** It is an **average-performance crossing estimate under the current data, scene
weights and message model** — not a per-frame reliability rule and not a link-layer requirement.

**D-1 Per-point verdict.** Each point is reported as supporting **L**, supporting **complete F**, or
**not distinguishable** given the uncertainty carried through from the measurement.

**D-2 No forced threshold.** If the crossing cannot be bracketed, the interval is reported as
undetermined. N is not changed after seeing the data.

## C-6 Migration list (P2-R14) — what comes over from P1, and what does not

Every path below is registered with its sha256 in `protocol/p2_reuse_manifest.json`, and
`build_reuse_manifest.py --check` fails if any path here is missing from that manifest or any manifest
path is missing from this section. The two cannot drift apart.

### Migrated

| what | path |
|---|---|
| cue extractor (`v2_ego_local_23d`, 21 ego-local fields) | `projects/ca_tosg/evaluation/v2_wp6_generate_cues.py` |
| cue schema | `results/manifests/V2_CUE_SCHEMA.json` |
| frozen cue set for validate | `results/v2/wp6_cues_validate.json` |
| random-forest structure and training scaffolding | `projects/ca_tosg/models/v2_selector.py` |
| training entry point | `tools/train_selector.py` |
| evaluation harness | `tools/evaluate_selector.py` |
| scene identity, shared by folds and leakage gate | `projects/ca_tosg/datasets/scene_split.py` |
| scene-level LOSO folds | `results/manifests/v2_validate_loso_folds.csv` |
| freeze mechanism | `results/manifests/FROZEN_MANIFEST.json` |
| primary freeze record and its hash discipline | `results/manifests/V2_PRIMARY_FREEZE.json` |
| normative candidate block the entry point parses | `docs/experiment_protocol.md` |

The scaffolding is migrated; the objective inside it is not. That distinction is the whole point of
the next table.

### Not migrated

| what | where it lives | why not |
|---|---|---|
| the λ payload-penalty objective `U = eff − λ·B` | `projects/ca_tosg/models/v2_selector.py` (the utility function it defines) | P2-R14 C-1 keeps payload out of the objective. Payload is measured and reported beside F1, never optimised against it |
| candidate 67's weights and the labels it was fitted to | `data/p2/v2_selector_cand67.pkl` | fitted under the λ objective on the old label definition. P2 labels are C-7's argmax, so the weights answer a different question |
| packet-level utility grid | `results/v2/v2_grid_validate_packet.csv`, `results/v2/v2_grid_validate_packet.json` | P2-R11 A-4 removed packet and partial-recovery accounting from the candidate set. These files stay in P1's record and are read only by `projects/ca_tosg_p2/protocol/message_regime.py`, the pre-lock comparison whose result produced the lock. They enter no P2 table |
| the sparse-F line, in full | `archive/p2-sparse-exploratory/` | closed in P2-R9 |
| the 100 ms reachability gate | measured by `projects/ca_tosg_p2/protocol/full_f_feasibility.py` | the finding is kept — 0 of 27 link configurations deliver a complete F inside 100 ms — but it is **not applied as a gate** in the training or evaluation line, per C-4. Deleting the finding and dropping the gate are different acts and only the second is intended |

## P2-R15 result, registered (P2-R16 A)

**A-1 The negative result, as it came out.** The first joint forest **does not beat the channel-only
rule**: scene-equal F1 0.85740 against 0.86248, a difference of **−0.00508 [−0.00949, −0.00166]**,
negative in **8 of 9 scenes**; on AWGN alone −0.01009 [−0.01881, −0.00330]. The pre-registered C-5
criterion 1 asked for an interval entirely above zero; it is entirely below. The forest is also
indistinguishable from always sending L (−0.00114 [−0.00566, +0.00184]). The channel inputs do carry
information — joint beats the task-only forest by +0.00952 [+0.00357, +0.01664] — but the forest turns
that into a policy no better than Fixed L.

**Grid caveat.** This round uses the **original 22-cell grid**. The measured 8.5, 9.0 and 9.5 dB points
are not in it, so nothing in this result depends on them and nothing in it speaks to that SNR range.

**A-2 The C-8 reading, by the rule registered before training.** The offline reference requests F on
**10.7 %** of rows over all cells and **37.8 %** on every one of the high-reliability AWGN cells; the
forest requests it on **2.7 %** overall and **7.7 % to 10.9 %** across those same cells. That is
**reading 2: the inputs or the fitting are insufficient, and the selector is what to examine.** It is
not written as "F is useless", and it is not grounds for reverting to an E/L-only design. The
diagnosis is in `rf_diagnostics.md`.
