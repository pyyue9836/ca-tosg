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
