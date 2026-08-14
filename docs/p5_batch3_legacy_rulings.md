# P5 batch 3 — legacy-engine inventory and per-section rulings (PROPOSAL, awaiting Peiyi)

**`main.tex` is not edited by this document, and was not edited in this batch — not one character.**
This is the clean-up list for `sec:difficulty` and everything else in the paper that still rests on a
retired engine, plus a recommendation per section. Every ruling below needs Peiyi's decision before
any prose moves.

Machine inventory: `docs/claims_evidence_audit.md`, regenerate with
`python tools/audit_claims_evidence.py`. It attributes each of the 107 ledger claims to its section
and classifies its evidence by *the generator's own intra-repo import closure*, so `LEGACY-ENGINE` is
derived from the code, not asserted.

## What "legacy engine" turned out to mean — three different things

The audit's single `LEGACY-ENGINE` tag covers three materially different dependencies. The rulings
depend on which one applies, so they are separated here.

| kind | marker the closure hits | what it means | reproducible under the frozen protocol? |
|---|---|---|---|
| **L1 — v3 policy engine** | `policy_200seed` | numbers produced by the retired P1-v3 200-realisation policy engine driving the v3 RF selector | only if the quantity is engine-independent |
| **L2 — v3 scorer** | `true_e2e_global` | AP scored by the P1-v3 global-sort scorer, outside the frozen replay | needs a new frozen-protocol run |
| **L3 — v3 utilities + 200-seed convention** | `v3_eval` | the script trains/evaluates **its own** selector and borrows `v3_eval`'s BLER lookup, `N_SEED=200` CSI convention and bootstrap helper; it reads **neither** the v3 selector nor the frozen selectors | it is a self-contained prior-protocol arm, not a frozen-protocol quantity |

Evidence for L3: `baselines/importance_map_jscc/perframe/build_two_regime_edge_clean.py` uses only
`V._bler`, `V.N_SEED` and `V.paired_ci_frames_from` — a table lookup, a seed count and a bootstrap.
`projects/ca_tosg/evaluation/ablations/a2_difficulty.py` and `a7_ablation.py` import `v3_eval`
directly and run their whole evaluation through it (`V.eval_series`, `V.frame_means`, `V.eff_of`,
`N_SEED = 200`). `a2_difficulty.py` additionally loads the **retired v3 deployed selector** —
`C.load_rf()` → `data/selector_rf.pkl`, described in `ablations/_common.py` as "the v3-retrained
deployed selector" — **not** `data/p2/selector_B0XX.pkl`. So `a2_difficulty` is L1 outright;
`a7_ablation` trains its own RF per feature subset but scores it on the retired engine, which is L1
in effect.

## The 14 legacy claims, by section

| § | claim IDs | kind | generator |
|---|---|---|---|
| `sec:channel` | `c351473` | L1 | `policy_200seed.py` → `threshold_vs_rf.csv` |
| Communication Cost | `c43ecae` | L1 | same |
| Message Branches | `c262629` | L1 | same |
| Payload Accounting | `c94d26a` | L1 | same |
| `sec:headline` | `c1a099a` | L1 (weak match) | `policy_200seed.py` → `threshold_vs_rf.csv` |
| `sec:ablation` | `c75df0f` | L1 | `ablations/a7_ablation.py` |
| `sec:generalisation` | `c274409`, `ce03afe`, `caf41ce` | **L2** | `true_e2e_global.py` |
| `sec:difficulty` | `c21021c` | L1 | `ablations/a2_difficulty.py` |
| `sec:harm` | `c2f3e1b` | L1 | `ablations/a2_difficulty.py` |
| `sec:jscc_aware` | `ce386fe`, `c14c429` | **L3** | `build_two_regime_edge_clean.py` |
| Conclusion | `ccf7f57` | L1 | `ablations/a2_difficulty.py` |

**Two of these were not previously known to be legacy-engine.** The handoff listed `sec:difficulty`
as the one outstanding legacy subsection. It is not the only one:

* **`sec:generalisation` carries three L2 claims** — the whole per-SNR AP-knee narrative on test and
  Culver-City (`0.919 → 0.921` at 12 dB; `0.783 → 0.857` at 12–14 dB; the 16 dB peak/20 dB dip) is
  scored by the **v3 global-sort scorer**, not by the frozen `end_to_end_ap.py`. This is the largest
  and most expensive item in the batch.
* **`sec:harm` and the Conclusion each carry an `a2_difficulty` claim.** P5 batch 2 recorded deleting
  the `+0.090` restatements; the Conclusion sentence *"The granularity policy's gain over
  object-level communication is itself frame-selective, reaching $+0.090$ F1 (95\% CI
  $[+0.083,+0.096]$) on hard frames under a reliable channel"* (`main.tex` line 904) survived, as did
  `sec:harm`'s easy-stratum `-0.0147` sentence. The `+0.090` family therefore lives in **three**
  places, not one: `main.tex:662` (prose), `main.tex:678` (figure caption) and `main.tex:904`.

## Rulings — one per section

### 1. `sec:channel`, Communication Cost, Message Branches, Payload Accounting — `B_L ≈ 0.024` family

**(a) recompute — really, re-attribute.** The quantity is a *dataset* statistic (mean detected
objects per frame × 110 B ETSI-CPM × 8 bit), not a policy output; `threshold_vs_rf.csv` merely
happens to carry it. `tests/test_payload.py` check `(0b)` **already re-derives it from the dataset**
(`late_num_pred`), not from the v3 CSV — so the number is engine-independent and only the ledger's
CSV citation is legacy.

* **Cost:** none. No run. Edit four ledger cells to cite the dataset + `tests/test_payload.py (0b)`
  instead of `threshold_vs_rf.csv`.
* **Dependency:** `tests/test_payload.py (0b)` currently **skips** when the OpenCOOD runtime dataset
  is absent. If the citation is to be load-bearing, that check must become a hard requirement in the
  artefact tier (it already fails loudly rather than passing silently).
* **Prose:** unchanged.

### 2. `sec:headline` — `c1a099a`, "on test that headroom is 0.0027 AP"

**(a) re-attribute.** The `LEGACY` hit is weak (2 of 3 literals, in a large CSV). The same headroom
is carried by the **frozen** `results/main/true_e2e_ap.csv`, which is the source the neighbouring
claim `c5930a4` resolves to (`0.9216 − 0.9189 = 0.0027`).

* **Cost:** none. One ledger cell.
* **Dependency:** none.
* **Prose:** unchanged.

### 3. `sec:ablation` — `c75df0f`, the `c_t` channel-conditional payload pair (`0.240` / `0.271`)

**(a) recompute from FA-1.** The frozen replacement already exists: `feature_ablation.py` (FROZEN
closure) → `results/sensitivity/feature_ablation.csv` and the `fa_walk_*` runs. P5 batch 2 already
replaced the *neighbouring* "cues add no F1" reading with the FA-1 policy-shape result; this sentence
was left on the v3 arm.

* **Cost:** no new run — read the committed FA-1 CSVs. Expect the two payload numbers to **move**,
  so this is a prose edit, not a citation edit.
* **Dependency:** `results/sensitivity/feature_ablation.csv`, `feature_ablation_runs/` (both
  committed).
* **Risk:** if FA-1 does not report a channel-conditional payload split by channel type, the
  sentence has no frozen counterpart and drops to ruling (c).

### 4. `sec:difficulty` — `c21021c`, and its dependants `sec:harm` `c2f3e1b` + Conclusion `ccf7f57`

**(a) recompute, but only the reliable-channel view; the channel-averaged view must be (c) deleted.**

`a2_difficulty.py` produces two views. They are not equally recoverable:

* **Reliable-channel conditional (AWGN, 16 dB, C deliverable) — RECOVERABLE.** Difficulty is defined
  as tertiles of the per-frame object-level F1 (`df['late_f1'].quantile([1/3, 2/3])`). The frozen
  grid `data/p2/p2_grid_{split}.csv` carries exactly what is needed per frame × SNR × channel:
  `eff_E, eff_L, eff_F, bler_F, oracle_ELF` (47,740 rows on test = 2,170 frames × 11 SNR × 2
  channels). Condition on `channel=awgn, snr_db=16`, stratify on `eff_L` tertiles, and replay the
  frozen `selector_B0XX.pkl` — a frozen-protocol difficulty stratification with no new inference.
* **All-channel 200-realisation view — NOT RECOVERABLE, and must not be.** That is the retired
  engine's own quantity (v3 selector, 200-realisation CSI draw). Recomputing "the same" number under
  the frozen replay would be a different quantity wearing the old number's clothes. Per the "never
  blend engines" rule it is deleted, not reproduced.

* **Cost:** one new script (~150 lines) under `projects/ca_tosg/evaluation/`, plus a change-log
  pre-registration. **No new LiDAR inference.** Minutes of compute.
* **Dependency:** `data/p2/p2_grid_{validate,test,culver}.csv` and `data/p2/selector_B0XX.pkl` —
  both present. Note these are **git-excluded**, so the recomputation is artefact-tier: the gate
  must fail loudly, not skip, when they are absent.
* **Figure:** `fig_difficulty.pdf` is a product of the same script and shows the all-channel view.
  It must be **regenerated from the frozen recomputation or deleted** — leaving it while editing the
  prose is the exact failure that stalled this subsection in batch 2.
* **Conclusion (`ccf7f57`) and `sec:harm` (`c2f3e1b`) follow whatever `sec:difficulty` gets.** They
  are restatements of the same stratification; they may not survive their source.

### 5. `sec:generalisation` — `c274409`, `ce03afe`, `caf41ce`, the per-SNR AP knee (**L2**)

**(a) recompute, at real cost — or (b) if the cost is refused.**

The frozen AP engine `end_to_end_ap.py` **cannot** produce these numbers as written: it draws
`snr_2d = rng.uniform(0, 20, ...)` and marginalises over SNR, emitting `split × budget × policy`
(`true_e2e_ap.csv`). There is no per-SNR AP curve in the frozen protocol at all. The published knee
comes from `true_e2e_global.py`, the v3 scorer.

* **Cost — the heaviest item in the batch.** A new SNR-pinned variant of `end_to_end_ap.py` that
  fixes SNR to each of the 11 pre-registered grid points × 2 channels instead of drawing it, then
  runs the global-sort AP scorer over per-frame box sets for test and Culver-City. That is
  11 × 2 × 2 = 44 scored conditions, each a 200-realisation Bernoulli coin draw over the cached
  detections.
* **Dependency:** the `ego/late/comp_{split}.npz` caches (git-excluded), `bler_sionna.csv`, the
  frozen selectors. No new LiDAR inference — the detections are cached.
* **Fallback (b):** demote the per-SNR knee paragraph to an appendix labelled *"prior-protocol
  diagnostic, not re-evaluated under the frozen protocol"*, and keep in the main text only the
  split-level frozen AP that `true_e2e_ap.csv` already supports. This is the cheap option and costs
  the paper its most legible generalisation figure.
* **Recommendation:** (a). This is the transfer evidence a Transactions reviewer will look for, and
  it is recomputable without new inference — the cost is engineering, not data.

### 6. `sec:jscc_aware` — `ce386fe`, `c14c429` (**L3**)

**(b) keep, but label it explicitly as a prior-protocol arm.**

This is not the same defect as the others. The JSCC comparison trains and evaluates **its own**
selector inside `build_two_regime_edge_clean.py`; it reads neither the v3 selector nor the frozen
selectors. What it borrows from `v3_eval` is a BLER table lookup, the `N_SEED = 200` CSI convention
and a bootstrap helper. Re-running it "under the frozen protocol" would mean training a *new*
frozen-protocol selector on JSCC `eff` values — a **new experiment**, not a recomputation, and one
that answers a question the paper does not need answered (the section's point is the *codec's*
channel response, not the deployed selector's performance).

* **Cost of (a):** a full new selector-freeze cycle on JSCC effs — LOSO, candidate walk, freeze,
  manifest. Weeks-scale, and out of scope for a migration batch.
* **Cost of (b):** a one-sentence protocol note in the section plus a ledger annotation. Near zero.
* **Dependency:** none.
* **Caveat to record:** the section's numbers share the 200-seed CSI convention with the retired
  engine, so they still may not appear in the same sentence as a frozen-replay number.

## Summary of proposed rulings

| § | ruling | new compute | blocks on |
|---|---|---|---|
| `B_L` family (4 claims, 4 §) | (a) re-attribute | none | making `test_payload.py (0b)` non-skippable |
| `sec:headline` `c1a099a` | (a) re-attribute | none | — |
| `sec:ablation` `c75df0f` | (a) recompute from FA-1 | none (committed CSVs) | numbers may move → prose edit |
| `sec:difficulty` + `sec:harm` + Conclusion | (a) reliable-channel view; **(c) delete** the channel-averaged view | minutes | `data/p2` grids; figure must be rebuilt or deleted |
| `sec:generalisation` (3 claims) | (a) recompute — **or (b)** if cost refused | 44 scored conditions | new SNR-pinned AP script |
| `sec:jscc_aware` (2 claims) | (b) label as prior-protocol | none | — |

**Nothing above has been executed.** No result was regenerated, no figure rebuilt, no ledger cell
edited, `main.tex` untouched. Awaiting the ruling.

## Also surfaced by the audit, not legacy-engine — for a later batch

The audit classifies the remaining 93 claims too. Two counts are worth recording now:

* **55 claims still have blank ledger evidence**, of which **36 carry no distinctive number to
  locate** (structural/definitional constants: `2`-bit request, `802.11bd`, `16`-QAM, IoU `0.5`) and
  **19 carry distinctive numbers that no committed result file holds**. The second group is the one
  to work through next — e.g. `c556938` (feature importance `34.9` / `27.5` / `62.4`%), `c2aa3e2`
  (`55`–`70`% of oracle headroom, `+0.031` F1), `ce065fb` (transfer shares `99.4` / `99.3` / `99.8` /
  `25.3` / `16.0`%), and the recurring `6.9`–`18.9`% channel-use headline, which appears twice
  (abstract and Conclusion) and is located by **no** committed result file.
  An unlocated number is not yet an error — the file may be git-excluded or the value derived — but
  each needs an explicit citation before the ledger can close. The `6.9`–`18.9`% pair is the one to
  check first: it is a headline number in both the abstract and the Conclusion.
* **16 claims resolve to a FROZEN generator by value search but still have blank ledger cells.**
  Those are pure back-fill: the evidence exists and only needs writing down.
