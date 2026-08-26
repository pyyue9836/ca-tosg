# CA-TOSG — PROTOCOL CHANGE-LOG (history)

> ## NOT QUOTABLE
>
> **Nothing in this file may be quoted as current state.** Every entry below describes the tree as it
> stood on the day it was written: gate counts, page counts, claim counts, file paths, open blockers
> and headline numbers are all *as-of*, and most of them have since moved. Several entries name
> scripts and CSVs that no longer exist (deleted in R65 and R67 c after a reference sweep) — that is
> correct content for a record, and is exactly why the record is not a source.
>
> **Where current state actually lives:**
>
> | question | answer |
> |---|---|
> | what the protocol *is* | `docs/experiment_protocol.md` — §1–§10, the pre-registered revision block and Appendices A–F. That file stayed normative; this one did not. |
> | what a delivered sentence is bound to | `docs/claims.md` |
> | which command produced which file | `results/README.md` |
> | which products are retired or deleted | `tests/retired_products.md` |
> | what is verified, and how | `python tools/verify_results.py` |
> | where the work stands | `docs/HANDOFF.md` |
>
> **What this file is still authoritative for:** *what was decided, when, and why* — the
> pre-registrations, the amendments written as amendments, the rulings, and the errata. A finding
> recorded here as `false-as-written` or `superseded` still binds the delivered text, and
> `tests/test_protocol_reconciliation.py` enforces exactly that by reading **both** this file and the
> live protocol (R67 d). Removing an entry here can therefore turn a reconciliation pair stale and
> fail the gate; entries are appended, never edited away.

Split out of `docs/experiment_protocol.md` in R67 (d). The entries are in the order they were
written, oldest first; read backwards from the end for the most recent state.

---

## Change-log R17 (2026-08-16) — supervisor items, list rulings, and two corrected published numbers

**Nothing was trained, no frozen product was touched, δ / λ\* / τ\* / the selectors are untouched.**
This entry closes R17 items A1–A10, the list-A rulings, list-B family binding, and the D wrap-up.

### Two published numbers were WRONG and are corrected (errata)

1. **Feature importances.** The paper printed `34.9% / 27.5% / 62.4%`. Those are the **retired v3
   selector's** importances (`results/main/feature_importance.csv`). The deployed model is
   `data/p2/selector_B020.pkl`, whose Gini importances are **24.8% (`channel_is_rayleigh`) /
   22.3% (`est_snr_db`) / 47.1% total**, with the leading perception cue `pcd_mean_range` at 3.9%
   (the text said 3.6%). New generator `projects/ca_tosg/evaluation/feature_importance_frozen.py`
   reads them straight from the frozen pickle into `results/main/feature_importance_frozen.csv`;
   body, both captions, the 7-row table and `plot_feature_importance.py` were all repointed. The
   old CSV is now marked RETIRED in `results/README.md`.
2. **Selector latency P95.** The paper reported `59.9 ± 5.3 ms` (mean/std of `selector_B030`, the
   slowest of the three) alongside `P95 = 69.3 ms`, which is **`selector_B010`'s** P95 — a
   cross-model splice. `selector_B030`'s own P95 is **66.6 ms**; all three mentions were repointed.
   The conclusion (fits the 100 ms budget of a 10 Hz cycle) is unchanged.

### Gate and tool defects found while regenerating (all fixed, all negative-tested)

- **Stale fingerprint #9 collided with a real new number.** The bare pattern `0\.248[^0-9]` blocked
  the retired *C_256 channel-use payload*, but `channel_is_rayleigh`'s Gini importance is also
  0.248. The pattern now requires a payload word (`Msym|Mbit|payload|C_{256}`) on the same line.
  Negative-tested against the retired text at `6cc6d3b`: **6/6 retired occurrences still blocked**,
  0 hits on the current text. Coverage was narrowed in CONTEXT, never in VALUE.
- **The audit and the ledger disagreed about four claim IDs.** `audit_claims_evidence.py` derived
  its own ID; for four claims whose ledger text carries a section-name prefix the two hashes
  differ, so those rows were reported PENDING and then value-searched — which is how a claim with
  committed evidence in the ledger came out labelled LEGACY-ENGINE. Lookup now falls back to
  normalised claim text, then to containment on ≥60 characters.
- **`conditions_of()` resolved a two-channel sentence to Rayleigh alone.** "…under Rayleigh and for
  AWGN SNR ≤ 8 dB" pins neither channel; the `elif` chain silently chose one and reported an
  AWGN-drawn payload as a condition mismatch. Channel and split now use the **set semantics the SNR
  axis already used**. Exactly 3 rows moved, all in the "sentence names both → unconstrained"
  direction.
- **`appears()` never looked in the finer direction.** The provenance file stores 4 dp while the
  tables print 5, so 0.9033 read as "nowhere" although the body states 0.90326. A finer literal now
  counts only if it **rounds back** to the stored value at the stored precision — strictly stronger
  than an exact match, never a coarser one.
- **`STANDARD_IDS` was defined in one tool only.** `802.11` / `37.885` are names, not measurements;
  the audit lacked the rule the ruling list already applied, so six citation sentences read as
  "numbers with no evidence". The definition now lives in `audit_claims_evidence.py` and is
  imported by `build_pending_rulings.py`.

### List-A rulings (33 rows) — applied as ruled

both-sides / body-only / caption-only: left as they are. Two active verbs:

- **nowhere → canonical quantities into captions.** The deployed selector's own realised F1 was
  stated nowhere: `fig:ap_snr`'s caption now carries **0.9071** (its level below the cliff, and its
  flat Rayleigh level) and **0.9244** (AWGN 20 dB), against the Fixed-L line at 0.9067.
- **different condition → condition label.** `payload_catosg_awgn_low` (0.0238) is now labelled
  "measured at AWGN 0 dB and identical at every Rayleigh SNR".

**Two rows conflict with the rule and were NOT edited, per "report any item conflicting":**
`pareto_catosg_B010_f1` (0.9033) is already in the body as **0.90326** — same number, printed
finer, so adding it to a caption would duplicate it; the matcher fix now recognises it.
`rho_F_at_knee_culver` (0.0636) is already in the body as **0.064**, which is 2 significant digits
and therefore below the collision floor the matcher refuses to go under. Loosening that floor is
the change that previously made 0.9244 "match" 0.9, so it stays refused and the row stays flagged.

### List-B binding (52 → 5)

The four families the ruling requires bound are bound: the abstract payload range
(`tests/test_payload.py` §3b chain), the feature importances (above), the latency
(`results/latency/selector_latency.csv`) and the payload reduction
(`results/main/replay_summary.csv`). Main-text claims that the value search had mis-attributed to
legacy files were repointed to their mainline sources — the AP headroom triple
(0.0267 / 0.0027 / 0.0892 = Feature-ceiling − Fixed-L in `results/main/true_e2e_ap.csv`), the easy-
stratum effect (−0.004001, n=713, CI [−0.006383, −0.001841] in
`results/sensitivity/difficulty_frozen.csv`), and the four `B_L = 0.024` structural constants
(Eq.(7) + `tab:notation`, gated by `tests/test_payload.py`).

### D wrap-up — where the targets landed

| target | result |
|---|---|
| 0 UNRESOLVED | **met** (was 1) |
| 0 numeric-unlocated | **5 remain** — exactly the deletion candidates, which is the ruling's stop point |
| 0 LEGACY-ENGINE | **0 in the main text** (was 8). **2 remain, both in Appendix `sec:jscc_aware`** — that appendix *is* the declared prior-protocol JSCC arm, so LEGACY-ENGINE is the truthful label and relabelling it would be a lie |
| nine gates | **all PASS** |

Ledger: 121 claims, **109 filled / 12 pending**, 0 STALE.

### A7 / A10

- **A7 — SComCP residue: none as a baseline.** What remains is what ruling (c) preserved: three
  related-work citations, and the §V-C sentence citing SComCP's transmission convention (a
  configuration reference, not a comparison). Artefacts stay under `results/baselines/` as the
  archived negative reproduction, not in the paper.
- **A10 — compaction.** The stale `% TODO(P4-B)` placeholder ("no section is created until it has
  results") was deleted — the arm has results and lives in Appendix `sec:second_backbone`. Two
  orphaned tail paragraphs (§II-C, §IV-G) were joined into the paragraphs they belong to. Main text
  carries mainline frozen results + FA-1 + collaborator scale + limitations; the second-backbone
  arm and the JSCC codec comparison remain appendices.

---

## Change-log R17-C (2026-08-16) — landing batch and the P6 four gates

**Nothing trained, no frozen product touched, δ / λ\* / τ\* / the selectors untouched.** Rulings
B4/B5/B6/B7 landed; **B8 is held** (see below); items 6–9 done.

### Rulings applied

- **B4 delete.** The withdrawal notice ("the single-number *recovers 99.3--99.8% of the oracle* claim
  … is withdrawn") is gone from §VI-F. The interval values it referred to are stated earlier in the
  same paragraph and keep their own evidence; the withdrawal itself lives here, in the change-log.
- **B5 evidence.** The FA-1 core sentence is bound to `results/sensitivity/feature_ablation.csv`:
  `channel_only` ρ_F = 0 at B=0.10/0.20 with payload pinned at B_L, and at B=0.30 F1 0.90944 /
  payload 0.28843 against combined 0.90734 / 0.18703. The `1.54×` is registered as a **derived**
  quantity (0.28843 / 0.18703 = 1.5422) in `docs/canonical_quantities.md`.
- **B6 delete.** The group-wise cue ablation ("dropping range, density or object-count changes F1 by
  <0.001") is a legacy-engine product never re-run under the frozen protocol; FA-1 carries the
  ablation conclusion. The table pointer in the same sentence is not part of the retired claim and
  was kept as "The channel-averaged payloads are in Table~\ref{tab:headline_agg}."
- **B7 delete.** The Rician-interpolation sentence is contradicted by P3-C's frozen result (the
  binary channel feature collapses across all K, so there is no smooth knee to move), and its OFDM
  half leaned on the demoted appendix.

### §VI-E reframed, and a third instance of the retired importance value

The "dominate / dominant signal" framing is replaced by the individually-strongest framing, in the
body, in **both** captions, and — newly found — **in the abstract**, which still printed the retired
v3 selector's value in rounded form: *"jointly account for 62% of the selector's feature importance,
dominating 21 ego-side cues"*. The first errata pass searched for `62.4` and never saw `62`. It now
reads: the two channel-side features are the two individually strongest cues, **47.1%** against
**52.9%** spread over 21 ego-side cues. Retired fingerprint **#17** covers the whole family,
including the rounded form bound to an importance context; negative-tested against the pre-R17
abstract sentence (trips) and the current text (clean).

### Canonical quantity registry (new)

`docs/canonical_quantities.md` + `tests/test_canonical_quantities.py`, registered as the tenth repo
gate. Every entry is **re-derived from its committed product at gate time**; nothing is hardcoded,
because a hardcoded reference turns a data change into a silent PASS. Entries: channel/perception
importance split, selector latency, the FA-1 ratio, the payload-reduction figure, and the two ratio
families (payload share of Fixed-F, F1 share of the masked oracle).

The latency entry asserts **same-row** provenance: mean, std and P95 must come from one row of
`selector_latency.csv`, and that row must be the slowest selector. Both numbers in the old splice
existed in the file, so any "does this value appear somewhere?" check passed it. Negative-tested:
restoring `P95 = 69.3`, restoring the v3 importances, or restoring the dominance wording each makes
the gate fail.

### P6 four gates — results

| gate | result |
|---|---|
| 1. numbers ↔ CSV (`tools/p6_numbers_vs_csv.py`, new) | **MISS 0.** 143 bound literals found in the file they are bound to (8 of them as the percent form of a stored fraction), 17 derived, 71 claims with no bound file or no distinctive literal. Self-test passes. |
| 2. claims ↔ evidence (`tools/audit_claims_evidence.py`) | 74 ANALYTIC / 43 FROZEN / **2 LEGACY-ENGINE, both in Appendix `sec:jscc_aware`** / 1 PENDING = B8. Main text: 0 LEGACY, 0 UNRESOLVED. |
| 3. cross-section entity scan (`tools/p6_cross_section_scan.py`, new) | **0 ENTITY-VALUE, 0 ORDERING, 0 EXISTENCE.** All three positive controls fire. |
| 4. leakage, full (`tests/test_data_leakage.py`) | **0 violations** across all four checks. |
| ten repo gates | all PASS |

**Two things gate 3 cost before it was trustworthy, recorded because "0 conflicts" is worthless
otherwise.** A first version read entities out of the prose (nearest subject / nearest metric): it
held **zero** `(F1, CA-TOSG)` records and attributed the budget literal `0.20` as an F1 value, so
its silence meant nothing — it was deleted, not shipped. The rewrite's ORDERING check then produced
**nine** findings by bounding an AP@0.5 value with F1 numbers from a different table, and after the
first fix still used the perfect-channel ceiling where the paper's sentence says masked oracle. The
metric and both bounds must come from the same table; with that corrected the count is 0 and the
injected-fault control still fires.

**Cross-metric observation (not a conflict, no action taken).** On test the selector's realised
**AP@0.5** (0.9183) sits marginally *below* Fixed-L's (0.9189), while in **F1** it sits above
(0.90326--0.90734 against 0.9011). Both are stated in the paper under their own metrics, and
§`sec:true_e2e` already says the test split is informative about payload rather than AP gain.

### B8 held — not derivable, and the ruling requires confirmation before deleting

`c2aa3e2` (Appendix A): *"The selector recovers 55--70% of the clairvoyant oracle headroom (e.g.
+0.031 F1 on AWGN test)."* Every committed route was checked:

| route | recovery fraction | comment |
|---|---|---|
| 200-realisation `jscc_selector_{awgn,rayleigh,ofdm}.csv` | **56.1 / 57.5 / 62.1%** | point estimates; range is 56--62%, not 55--70% |
| k-fold in-distribution `two_regime_kfold_diag.csv` (JSCC rows) | 36.7--74.9% | AWGN/test row is 71.6%; spread does not give 55--70% either |
| frozen cross-split `two_regime_edge_clean.csv` | **negative on test** (−0.13) | the known clean cross-split negative |
| CI-spanned | 16--151% | not a statable range |

And **+0.031 is not a recovered gain anywhere**: the AWGN/JSCC/test *headroom* is 0.0313 while the
recovered gain on that row is **+0.0224**. The sentence reads the headroom as if it were the gain.
No new GPU inference is needed — the numbers exist — so this is not a "recompute", it is a choice
between two rewrites, which is Peiyi's call:

1. **delete** the sentence, or
2. **restate** it from the committed point estimates: "recovers 56--62% of the oracle headroom
   (AWGN test headroom 0.029, recovered +0.018)".

Nothing was deleted or rewritten pending that ruling; the claim stays the single PENDING row.

### List-A conflicts — original ruling maintained

`pareto_catosg_B010_f1` (0.9033, already in the body as 0.90326) and `rho_F_at_knee_culver` (0.0636,
already in the body as 0.064, below the matcher's 3-significant-digit collision floor) stay flagged
and unedited, as ruled.

---

## Change-log R17-C-2 (2026-08-16) — B8 restated; milestone summary generator

**Zero GPU, text + regeneration only.** No frozen product touched.

### B8 restated (ruling: restate)

`sec:jscc_aware` (a) now reads, with both quantities kept apart and the estimator named:

> In the separate $200$-realisation held-out comparison on validate frames, the cue-based selector
> recovers $56$--$62\%$ of the clairvoyant oracle's headroom over Fixed $L$ across the three
> channels. […] under AWGN the oracle headroom is $0.0291$ F1 and the selector recovers $+0.0181$
> of it, with $0.0275$ / $+0.0158$ under Rayleigh and $0.0281$ / $+0.0158$ under OFDM.
> In-distribution, then, the graceful-channel decision is content-bound and carried by the ego-side
> cues---a gain no SNR threshold reaches on these frames, and one that (b) below shows does not
> survive the cross-split move.

**Two deviations from the instruction as written, both forced by the instruction's own rule 3:**

1. **The example numbers changed.** The instruction gave "AWGN test: headroom 0.0313, recovered
   +0.0224". Those are the **k-fold** row (`two_regime_kfold_diag.csv`, AWGN/JSCC/test) — the
   estimator rule 3 says must stay out of the body sentence. Using them beside a 56--62% figure
   drawn from the 200-realisation CSVs would put two estimators in one sentence, which rule 2
   forbids. The sentence therefore quotes the AWGN numbers **of the same estimator it cites**:
   headroom 0.0291, recovered +0.0181 (62.1%).
2. **The split label changed.** `jscc_selector_{awgn,rayleigh,ofdm}.csv` is generated by
   `jscc_selector_compare.py`, which runs on **validate** frames with a 70/30 held-out split and 200
   Monte-Carlo draws — it is not the test split. Labelling it "AWGN test" would have been wrong, so
   the sentence says "held-out comparison on validate frames".

Rule 3 is also applied to the *neighbouring* sentence, which quoted the k-fold edges (+0.022 /
+0.018 / +0.020 on test) with no estimator named: it now says "measured by the in-distribution
$k$-fold estimator". Two estimators appear in the subsection; neither appears inside one sentence,
and both are labelled. The reach-claim is explicitly limited to in-distribution and points forward
to (b), so it cannot be read against the cross-split negative reported there.

**Registry + ledger.** The recovery family is registered in `docs/canonical_quantities.md`
(headroom = `or_f1` − `L_f1`, recovered = `rf_f1` − `L_f1`, share = recovered / headroom) and
re-derived by `tests/test_canonical_quantities.py`, which also asserts that the retired conflation
cannot return: **the headroom may never again be quoted as a gain** (+0.031 is the AWGN/test k-fold
headroom; the recovered gain on that row is +0.0224). The ledger row moved PENDING → bound.

### Gate state after the batch

| check | result |
|---|---|
| ten repo gates | all PASS |
| P6-1 numbers ↔ CSV | MISS 0 (143 found, 17 derived) |
| P6-2 claims ↔ evidence | 75 ANALYTIC / 43 FROZEN / **0 PENDING, 0 UNRESOLVED**; 2 LEGACY-ENGINE, both in the prior-protocol appendix |
| P6-3 cross-section scan | 0 / 0 / 0, all controls fire |
| P6-4 leakage, full | 0 violations |

### `docs/milestone_summary.md` (new, draft)

Generated by `tools/build_milestone_summary.py`; **every number is read from a committed product at
build time**, from the sources registered in the canonical registry, so the page cannot drift from
the paper or the data. Seven sections: R9's three conditions, the nine-cell main table (F1, payload,
share of $B_F$, edge over the threshold), the E-collapse cost expressed in units of $\delta$
(**0.58--0.61$\delta$ on test** — the largest identified headroom in the method), the FA-1 shape
finding, collaborator scale with its diminishing returns, the SECOND-backbone boundary, and latency.
Draft for Peiyi's check before it goes to Josh.

---

## Change-log P0 (2026-08-16) — MAIN ERRATUM: collaborator convention in the main experiment

**Severity: main experiment.** Every mainline absolute number is withdrawn pending re-derivation.
`paper/main.tex` is untouched in this batch by ruling.

### The inconsistency

The perception side and the communication side of the mainline count different things:

* **Perception side.** The per-frame utility caches (`late_f1`, `compressed_f1` in
  `dataset_{split}*.csv`) come from OpenCOOD inference that fuses **every collaborator present in
  the frame**. On OPV2V that is frequently 2–3 vehicles.
* **Communication side.** The payload model charges **one message**: `B_L = 0.024` or
  `B_F = 0.99` Msym/frame, with a single frame-BLER term `(1-b)` for a single link.

So the mainline credits the frame with N-collaborator perception quality at 1-collaborator cost.
The action set, the budget, the Lagrangian, the oracle labels, the walk, τ\* and the R9 decision all
sit on that mismatch.

**Measured size, not asserted.** P4-C already ran the controlled arm at the *same* delivery and
payload semantics with N held at 1, 2 and 3, and its N=1 column is the consistent-convention
control. On test, N=3 minus N=1 is **+0.01034 F1** (per budget: +0.01039 / +0.01048 / +0.01017 at
B_max = 0.10 / 0.20 / 0.30; N=2 minus N=1 is +0.00952). On validate the same difference is +0.03953
and on Culver-City +0.02538. That is the amount of F1 the mainline was getting for free — between
two and eight times the pre-registered non-inferiority margin δ = 0.005.

### Ruling (a) — the main experiment is the nearest single collaborator

The main experiment is redefined as **N = 1, the nearest collaborator**, so that one message is paid
for and one collaborator's information is received. The alternative (charge k messages on the
perception side) would change the payload axis of every figure and the meaning of B_max, and it is
not what the deployed selector was frozen against.

**Consequence, stated plainly: every mainline absolute number is withdrawn** — F1, payload, the
nine-cell table, the Pareto points, the difficulty strata, the ablations, and the R9 decision
itself. They are not "approximately right pending a correction"; they are products of a convention
that is being replaced, and they are re-derived before they are quoted again.

### What is re-derived, and in what order (P0-2)

The N=1 per-frame caches already exist (`gs_rerun/p4c_N1/{late,intermediate}_{split}.npz`, built for
P4-C), so **no new perception inference is required** — this is a CPU/light-GPU batch.

1. rebuild the per-frame dataset with N=1 utilities (ego cues and `ego_f1` are N-independent),
2. grid expansion → 3 splits,
3. scene-level 9-fold LOSO on validate,
4. the pre-registered candidate walk → freeze one selector per budget,
5. τ\* re-tuned under the same convention and the same procedure,
6. the same 200 paired CSI draws → replay,
7. R9's three conditions re-judged at the original δ by the original procedure (corrigendum).

**Every stage first bit-reproduces its committed old-convention product** before being pointed at
N=1, reusing the E-Lg2 gate built for the SECOND arm. A stage that cannot reproduce its own
committed output is wrong, and no N=1 number is taken from it.

**Stop point (pre-registered here, before any number is seen):** after step 4, λ\*/τ\*/payload are
reported for Peiyi's check, and the replay does not run until that is cleared.

### The risk, recorded before the run

The real risk in this batch is not compute, it is that **R9's decision may not survive the
correction**, and the direction is not predictable: N=1 lowers the feature branch's utility, which
could move the selector either way against a threshold rule that is re-tuned under the same
convention. The decision follows the data. If R9 fails under the corrected convention, it is
recorded as a failed confirmatory decision and the paper's claim changes accordingly — the
conditions, δ and the procedure are not adjusted after seeing the result.

---

## Change-log P0-2b (2026-08-16) — replay-level pre-registration, written BEFORE the replay

**Timing, stated exactly.** The instruction was to enter this after the candidate walk and before the
replay. It is entered **before the walk has finished**: at the time of writing, the N=1 LOSO is still
running and no λ\*, τ\*, frozen payload or replay number exists. That is strictly stronger than
required — less was known when the expectations were fixed, not more. The E-Lg2 self-check (PASS,
`results/p0_n1/elg2_selfcheck.log`), the N=1 dataset and the N=1 grid were complete; nothing else.

### E1 — both sides fall, and for the same reason

The frozen selector's and the τ-rule's absolute F1 are expected to fall relative to the retired
full-collaborator numbers, because **both** now read the same N=1 caches. What is *not* predicted is
the gap between them, which is what R9 actually decides.

Measured inputs already in hand (branch-level means, not policy-level):

| split | `late_f1` | `compressed_f1` |
|---|---|---|
| validate | 0.90673 → 0.85538 (−0.05134) | 0.91930 → 0.88428 (−0.03503) |
| test | 0.90113 → 0.89095 (−0.01018) | 0.93253 → 0.92137 (−0.01116) |
| culver | 0.87216 → 0.84664 (−0.02551) | 0.92791 → 0.90590 (−0.02201) |

### E2 — R9 is re-judged with NO directional expectation

The three conditions, δ = 0.005 and the procedure are exactly as originally pre-registered. This
entry deliberately records **no** expectation about whether they hold. The correction lowers the
feature branch's utility while the threshold rule is re-tuned under the same convention, and those
push in opposite directions; anyone claiming to know the sign in advance would be guessing. The
outcome is a **corrigendum** either way: if R9 fails, that is reported as a failed confirmatory
decision and the paper's claim changes. No condition, margin or procedure is adjusted afterwards.

### E3 — E-collapse: what is already observed, and what is still a prediction

**No longer a prediction — already measured at the grid layer.** The oracle's `E` share rises under
the corrected convention: on validate the N=1 grid labels **529** cells `E` (the full-collaborator
grid essentially never did), and on test **5,696** of 47,740. This is an observation about the
labels and is recorded as such.

**Still a prediction, and the thing to check:** whether the *deployed* selector's ρ_E rises with it,
and whether the **E-collapse limitation is milder** under the new convention. The retired numbers had
ρ_E ≈ 0.001 (test) and 0.000 (Culver) against an oracle spending 0.172 and 0.133, at a cost of
0.58–0.61 δ on test. Both quantities are re-measured from the N=1 replay.

### Anti-goal clause (carried over, restated because this batch has a live incentive to bend it)

These expectations are **checks, not targets**. Nothing is retrained, no threshold is moved, no
budget is re-walked and δ is not touched in response to any of them. An expectation that is not met
is reported as not met, in the same words used here, and the finding changes rather than the data.

---

## Change-log P0-3 (2026-08-16) — the corrigendum replay, and the R9 re-judgement

Pure CPU. Self-check first: the mainline replay reproduces `replay_summary.csv` exactly (9 rows,
no differing cell) before any N=1 replay number was taken. Deployed products untouched — `git status`
is clean under `results/main/`, `results/manifests/` and `data/p2/`. Full tables in
`docs/p0_corrigendum.md`; hashes in `results/p0_n1/manifests/P0_REPLAY_MANIFEST.json`.

### R9 survives the correction

| condition | old | new | met |
|---|---|---|---|
| LCB95(dF) > −0.005 | −0.00286 | **−0.00018** | yes |
| UCB95(dB) < 0 | −0.12099 | **−0.07441** | yes |
| (B_tau − B_RF)/B_tau ≥ 0.10 | +0.56310 | **+0.34773** | yes |

All three hold at the sole primary comparison (test @ B_max = 0.20), at the original δ = 0.005, by
the original procedure, with the original multiple-comparison protection (everything else secondary,
CI only). The non-inferiority margin *tightens* — the selector sits closer to parity with the
re-tuned threshold than before — while the payload advantage shrinks but stays far above its floor.

### E1 — met

F1 falls in all nine cells (−0.008 to −0.050). Nothing was predicted about the gap, and the gap is
what moved in the selector's favour.

### E3 — half met, reported as such

**A correction to P0-2b first.** That entry recorded as measured that "the oracle's E share rises",
citing the N=1 counts alone. The comparison had not been made. Old → new oracle E cells:
validate **335 → 529** (rises), test **6,303 → 5,696** (**falls**), Culver **1,095 → 1,095**
(unchanged). The rise is a validate-only effect; the test claim was wrong and is withdrawn here.

* **ρ_E of the deployed selector does NOT rise.** Rayleigh, mean over the SNR grid, at the primary
  cell: 0.0008 → 0.0018 on test, against an oracle at 0.157; at B=0.10 it *falls*, 0.0064 → 0.0007;
  Culver is 0.0000 both ways. Only validate moves (0.0101 → 0.0125–0.0162).
* **The cost of the collapse does fall**, by roughly a quarter on test: 0.60/0.58/0.61 δ →
  0.44/0.46/0.47 δ.

So the limitation is **cheaper, not milder**: the selector still refuses the ego-only action about
as often as before, and what changed is the price of refusing it. Nothing was retrained or retuned
in response — the anti-goal clause held.

### Headline quantities, recomputed (`paper/main.tex` NOT edited)

* payload reduction at the primary cell: **56.3% → 34.8%**
* share of B_F on test across budgets: **6.9–18.9% → 3.7–21.4%**
* payload **rises** in seven of the nine cells and falls in two (test @ 0.10, Culver @ 0.10)
* F1 falls in all nine

The two families the paper leans on hardest are the two that move most. Every retired absolute
number stays withdrawn; nothing is written into the paper until the rewrite batch (P0-5).

---

## Change-log P0-4 (2026-08-17) — downstream arms on the corrected baseline

All five arms re-run or re-checked; tables in `docs/p0_corrigendum.md` §5. Every stage ran behind
`guarded()`, which hashes all 171 deployed products before and after the stage and aborts on any
change — each arm reports `171 deployed products unchanged`.

**A real incident, recorded because the guard exists because of it.** The first FA-1 run patched
four of the five FA output constants and missed `RUNS`, so the arm's LOSO-fold and candidate-walk
CSVs overwrote four committed products under `results/sensitivity/feature_ablation_runs/`, and the
overwrite reached commit `71d240a`. The files were restored from `9ec8aaa`, `RUNS` was made
arm-private, and the per-constant assertions were supplemented by the whole-tree guard — per-constant
checks only catch what you remember to list. That FA-1 run was killed and produced no numbers; the
arm was re-run from scratch.

| arm | verdict |
|---|---|
| **P3** | shape unchanged: `snr_only` still collapses to always-`L` (ρ_F = 0), `full_ref` and `cont_obs` within 0.0001 of each other |
| **FA-1** | shape conclusion survives and sharpens: `channel_only` and `task_only` both sit at ρ_F = 0 at B = 0.10 / 0.20 on every split; **the 1.54× figure is retired** — on test at B = 0.30 the corrected ratio is 1.36× |
| **P4-A** | direction unchanged: the bandit trails the frozen selector everywhere except test @ B = 0.10, where the interval straddles zero while it spends **4.2×** the channel use |
| **P4-C** | re-anchored, N=1 = main experiment, N=2/3 = incremental arm. Its N=1 column differs from the P0 replay by −0.00156…+0.00328 **by construction** (deployed policy replayed vs re-frozen policy) — that gap is the value of re-freezing, +0.00262 at the primary cell |
| **SECOND** | no re-run needed: `B_F` is a declared constant. The narration changes — on test the arm now sits *below* the mainline share at every budget rather than near it |

No arm fired a fuse condition. Nothing was retrained or retuned in response to any result.

---

## Change-log P0-5a (2026-08-17) — the promotion, and why the rewrite cannot follow in this batch

### The authorised exception

`guarded()` and the frozen-products-are-read-only rule are **waived for the promotion commit only**,
by the P0-5 ruling. Scope of the waiver: `tools/promote_p0_corrigendum.py` overwriting deployed
products under `results/{main,manifests,provenance,sensitivity,baselines}` and `data/p2`, once. It
does not extend to any other script, any later commit, or any re-run. Reason: the corrigendum
products cannot become the paper's products without replacing the ones they retire, and copying
them to a second location would leave two live answers to the same question.

### The four assertions, as executed

| assertion | result |
|---|---|
| (a) `pre-p0-corrigendum` tags the promotion-eve HEAD | tag → `05d45f5` == HEAD; pushed |
| (b) every promoted file byte-identical to its `p0_n1` source | **73/73** sha256 matches, checked per file after copy |
| (c) no `legacy/` or `archive/` directory | none created; retired products live only in git history under the tag |
| (d) sources removed, references repointed | 73 sources deleted (10 logs kept); manifests, index, provenance and code defaults repointed, then re-verified |

**Repointing found three defects that the promotion exposed rather than caused.**

1. `FROZEN_MANIFEST.json` recorded its `train_grid` and `cue_source` from *constants*, not from the
   files the redirected run actually read — so the N=1 freeze carried the retired grid's md5
   (`3314418d…`) and named the retired cue table. Both were re-recorded from the files read.
2. `grid_builder.py` writes grid provenance to `results/manifests/` while the leakage gate reads
   `results/provenance/`. Both sides described the same retired grids, so the split-brain was
   invisible until the grids changed. Provenance now goes where every other `PROVENANCE_*` lives,
   and all three grids were re-derived from the promoted inputs: **byte-identical**, which is the
   check that promotion and repointing agree.
3. `P4A_MANIFEST.json` pins the grid its bandit **trained** on, which is the retired one — true, and
   not fixable by re-recording. Manifest pins may now declare `retired_at: <tag>` and are verified
   against the tagged blob; `data/p2` is git-excluded so no blob exists, so this pin additionally
   declares `unverifiable_reason` and the gate **prints it as UNVERIFIABLE on every run**. An
   unverifiable pin must never look like a passing one.

### Products that changed under the new selectors

* **Feature importance flipped side.** The deployed selector's channel side is now **61.7%**
  (34.2% + 27.5%) against **38.3%** for the 21 perception cues. Under the retired convention it was
  47.1% vs 52.9%, and R17 rewrote §VI-E away from "dominance" for exactly that reason. That
  reframing was right then and is wrong now. The registry assertion no longer bans a phrasing: it
  **derives** which side is larger and checks the paper agrees.
* **Fingerprint #17 lost a literal.** `27\.5` is now a *true* value (est_snr_db = 27.4786%), so it
  was removed from the retired-importance family; `34\.9` and `62\.4` stay, being wrong under every
  convention. Same collision class as the 0.248 episode.
* **Latency re-measured, and the slowest model changed.** 51.7 / 52.1 / 51.9 ms mean for
  B010/B020/B030 — the slowest is now **selector_B020** (52.06 ± 5.63 ms, P95 58.30), not B030.

### Why P0-5 items 3–5 are NOT done, and were not attempted

`results/` still holds **61 CSVs produced under the retired convention**, and the paper's headline
tables and figures are built from them:

| still retired | what depends on it |
|---|---|
| `true_e2e_ap.csv`, `true_e2e_ap_by_snr.csv`, `true_e2e_global_*.csv` | §true-e2e AP table, the AP-headroom triple, Fig. 4's AP panels |
| `fixed_references.csv` | Fixed-L / F / C256 / masked-oracle references — **and every "F1 share of the oracle" figure** |
| `generalisation_*.csv` | the generalisation table |
| `frontier_*.csv`, `pareto_points.csv`, `frozen_curves.csv` | Figs. 4, 5, 6, 8 |
| `threshold_sweep_*.csv`, `threshold_vs_rf.csv` | §threshold comparison |
| `difficulty_frozen.csv` | §difficulty stratification |
| `collaborator_scale.csv` | §collaborator scale (its rows were produced with the *deployed* selectors) |
| `robustness_*.csv` | `tab:robustness` |

Rewriting `main.tex` now would put N=1 replay numbers next to retired-convention AP, oracle and
frontier numbers in the same tables — the exact splice this whole erratum exists to remove. So
**`main.tex` was not touched**, and one derived family already in the registry is flagged as
mixed-convention and must not be quoted: **"F1 share of the masked oracle"** divides new selector F1
by the *retired* oracle F1. ("% of B_F" is safe: B_F is a declared constant.)

**Two gates are therefore red, correctly:** `payload chain` (abstract still says 6.9–18.9%, frozen
says 3.7–21.4%) and `canonical quantities` (importances, latency, payload reduction, FA-1 ratio all
still retired in the text). They stay red until the missing products are regenerated. Turning them
green by editing the text first would be backwards.

---

## Change-log R18-3 (2026-08-17) — τ_feasible: PRE-REGISTRATION, written before implementation

**Nothing is run for this entry.** At the time of writing, `tau_feasible` does not exist in any
script and no number derived from it exists anywhere.

### The defect this addresses

The SNR-threshold comparator is selected by `pick_tau`, which maximises F1 subject to
`pay <= b_max` **on the deterministic grid**. The deployed comparison, however, reports the mean
payload over the **200-realisation replay**, and there the same τ\* is over budget:

| split | B_max | `B_tau` (replay mean) | over budget by |
|---|---|---|---|
| validate | 0.20 | 0.21663 | **+0.01663** |
| validate | 0.30 | 0.31267 | **+0.01267** |
| test | 0.20 | **0.21679** | **+0.01679** |
| test | 0.30 | 0.31250 | **+0.01250** |
| culver | 0.20 | 0.21740 | **+0.01740** |
| culver | 0.30 | 0.31463 | **+0.01463** |

At B_max = 0.10 it is within budget on all three splits. So at two of three budgets, on every split,
the paper's headline payload reduction is measured **against a comparator that violates the budget
constraint the method is held to** — and the reduction is flattered by however much the comparator
overspends. The 34.8% figure at the primary cell is of exactly this kind.

### τ_feasible, defined before it is computed

For each budget, on **validate only**, choose

> τ_feasible(B_max) = the **largest** τ on the existing τ grid such that the **mean payload over the
> 200-realisation replay distribution** satisfies `mean(B_tau) <= B_max`.

"Largest" because payload falls as τ rises (a higher threshold requests F less often), so the largest
feasible τ is the cheapest admissible comparator; taking the F1-maximising τ instead would re-open
the same violation. The τ grid, the 200 draws, `CSI_SEED`, the bootstrap seed and δ are all unchanged.
τ_feasible is fitted on validate and then **applied unchanged** to test and Culver-City, exactly as
the frozen selectors are.

### How it is reported

* τ_feasible is a **secondary, strictly-matched comparator**, reported **beside** nominal τ\*, never
  instead of it. Nominal τ\* stays in the tables: it is what the pre-registered R9 decision used, and
  removing it after seeing this would be rewriting history.
* R9's decision is **not** re-taken against τ_feasible. R9 was pre-registered against nominal τ\* and
  has already been re-judged once under the P0 correction; a second re-judgement against a
  comparator chosen after the fact would not be a confirmatory test.
* **Mandatory disclosure:** wherever the payload reduction against nominal τ\* is quoted (34.8% at
  the primary cell), the sentence must also state that nominal τ\* spends 0.2168 Msym against the
  0.20 budget, i.e. it is over budget. A reduction measured against an over-budget baseline may not
  be quoted bare.

### Expectations, recorded now (checks, not targets)

1. τ_feasible ≥ nominal τ\* at B_max = 0.20 and 0.30 (it must request F less often to fit), and equal
   at 0.10 where nominal τ\* is already feasible.
2. The selector's payload advantage over τ_feasible will be **smaller** than over nominal τ\*, and
   may vanish or reverse. That is the honest comparison and the number will be reported whichever way
   it lands.
3. τ_feasible's F1 will be **lower** than nominal τ\*'s, since it is constrained to spend less.

No condition, margin or procedure is adjusted after seeing any of these. If expectation 2 shows the
selector losing its payload advantage under a strictly matched comparator, that is reported as the
finding.

### R18-3 AMENDMENT (same day, written after the pre-registered rule proved degenerate)

**The pre-registered rule does not work, and this is the record of that.** "The largest τ whose
replay-mean payload fits B_max" is degenerate: payload falls monotonically in τ, so the largest τ is
*always* feasible and spends nothing. Run as specified it selected **τ = 20.5 at all three budgets** —
above the 20 dB draw range, i.e. "never request F" — reproducing Fixed-L exactly (payload 0.024 = B_L,
F1 = Fixed-L's) and producing "payload reductions" of −53% to −783%. My stated reasoning ("the largest
feasible τ is the cheapest admissible comparator") was the error: cheapest is not the same as
comparable, and expectation 1 (τ_feasible ≥ nominal τ*) was trivially true for a rule that never
transmits.

**Amended rule:** the **F1-maximising** τ on the same grid whose replay-mean payload fits B_max. This
keeps `pick_tau`'s own objective and changes only the constraint — from the deterministic grid to the
replay distribution, which is the defect being fixed. It is not tuned toward an outcome: the objective
is the incumbent one and the constraint is strictly tighter. The τ grid is also capped at 20.0, since
20.5 is unreachable by a U[0,20] draw and silently meant "never send F". The degenerate selection is
kept per budget in `TAU_FEASIBLE_MANIFEST.json` (`degenerate_largest_tau`), not discarded.

**Results (secondary comparator; R9 not re-taken).** τ_feasible = 17.0 / 13.0 / 9.0 for
B_max = 0.10 / 0.20 / 0.30, all within budget on validate.

| split | B_max | RF F1 | τ_nom F1 | τ_feas F1 | RF pay | τ_nom pay (over) | τ_feas pay | reduction vs nom → vs feas |
|---|---|---|---|---|---|---|---|---|
| test | **0.20** | 0.89691 | 0.89701 | 0.89624 | 0.14141 | 0.21679 (**+0.0168**) | 0.19270 | **34.8% → 26.6%** |
| test | 0.10 | 0.89148 | 0.89247 | 0.89322 | 0.03680 | 0.07240 (−0.0276) | 0.09663 | 49.2% → 61.9% |
| test | 0.30 | 0.89783 | 0.89900 | 0.89901 | 0.21196 | 0.31250 (+0.0125) | 0.28843 | 32.2% → 26.5% |
| validate | 0.20 | 0.86440 | 0.86119 | 0.86045 | 0.15106 | 0.21663 (+0.0166) | 0.19251 | 30.3% → 21.5% |
| culver | 0.20 | 0.84975 | 0.85858 | 0.85701 | 0.06751 | 0.21740 (+0.0174) | 0.19312 | 68.9% → 65.0% |

**Expectation 2 was that the selector's payload advantage would shrink and might reverse. It shrinks
and does not reverse** — 34.8% → 26.6% at the primary cell, still a real saving. And the F1 comparison
*improves* under the strictly matched comparator: against nominal τ* the selector is behind by
−0.00010, against τ_feasible it is **ahead by +0.00067**. That is a better result than the retired
comparison, arrived at by making the comparison stricter, and it is reported as a **secondary** finding
only: R9 stays as pre-registered against nominal τ*.

---

## Change-log R18-final (2026-08-17) — product back-fill, prose rewrite, full verification

### R18-1 · the two JOBS omissions, and what they turned up

`c256_dominance_verify` and the collaboration-harm family had been on the work list with no job. Both
were added; neither could simply be re-run:

* `collab_harm.py` carried a **hard-coded absolute path** into the OpenCOOD tree and wrote its CSV
  *outside the repository*, which is why re-running it changed nothing under `results/`. Repointed to
  the repo and to the corrected tables: the ego-exceeds-fused fractions move **0.9 / 7.4 / 0.2%** →
  **1.5 / 5.8 / 0.2%**.
* `verify_c256_dominance.py` needs per-frame `bler_C16` / `bler_C256` / `eff_f1_C*` columns that the
  P0-corrected tables do not carry, plus the retired v3 selector. The **identity** it verifies is
  algebraic and convention-independent; the three **frame fractions** are not re-derivable, so they
  remain pre-corrigendum values and `main.tex` now says exactly that in the same sentence.

### R18-2 · bandit retrained → it collapses

λ\* = 0.1 at all three budgets with identical frozen F1/payload (0.85613 / 0.0294 Msym): the budget
never binds, and the comparator settles at a near-$L$ operating point. Written up as a collapse, with
the SECOND-arm guardrail carried over — "beats/outperforms the bandit" is now a blocked phrase
(fingerprint 18), because the outcome is a collapse in the comparator, not a win for the selector.
The §V-D shape conclusion is upgraded accordingly: **four independently constructed variants collapse
the same way** (channel-only, cues-only, bandit, SECOND backbone) and only the full-feature imitation
selector produces three distinct budget-indexed operating points.

### R18-3 · τ_feasible — see the amendment entry above

### R18-5 · prose, and three claims that reversed

* **AP section, all three splits normalised.** Headroom 0.0550 / 0.0240 / 0.0970 with the selector's
  realised share $(\mathrm{AP}_{\text{CA}}-\mathrm{AP}_{\text{Fixed }L})/\text{headroom}$ =
  12.4/19.5/21.3% (validate), 2.5/21.2/21.2% (test), 0.0/4.9/21.1% (Culver). The narrative follows
  the ratio: headroom exists everywhere, the selector converts at most about a fifth, so what it
  reliably delivers is the communication saving. **"On test the headroom is effectively zero" is
  deleted** — it was an artefact of fusing every collaborator into both branches, and the mechanism
  sentence now says so.
* **Feature importance flipped back to dominance** (61.7% vs 38.3%) with an explicit
  *importance ≠ sufficiency* guardrail and a transport-specificity caveat.
* **The three-way footnote ordering reversed sign.** Cue axis $-0.0002 \to +0.0090$
  (CI $[+0.0089,+0.0091]$), matched-payload margin $+0.0005 \to +0.0032$, per-frame edge $+0.002$
  unchanged: all three now positive and the **cue axis is the largest**. Weakening the single message
  widened the gap the cues have to close. The neighbouring "cues do not add accuracy" reading was
  corrected with it.
* Also renumbered: difficulty terciles (test hard $+0.0400 \to +0.0660$), ρ_F knee (0.283 → 0.472
  validate, 0.256 → 0.433 test, 0.064 → 0.160 Culver), ρ_E pair, collaborator increments, latency
  (B020, 52.1 ± 5.6, P95 58.3), and the abstract.

### R18-4 · SECOND appendix

Convention disclosure added: full-collaborator caches, internally consistent, **relative** conclusion
stands, absolute figures not tabulated beside the single-collaborator main experiment. Not re-run.

### Verification state

**Eleven gates: ALL PASS.** P6-2 (claims↔evidence): 0 UNRESOLVED, 2 LEGACY-ENGINE both in the
prior-protocol appendix. P6-3 (cross-section entity scan): **0 / 0 / 0** with all three controls
firing — it earned its keep this batch by catching a retired 0.0027 still in §VI-A and a mislabelled
metric that paired ρ_F with ρ_E. P6-4 (leakage): 0 violations.

**P6-1 reports 1 MISS, left standing deliberately:** `tab:robustness`. Those three rows come from the
retired v3 ablation harness *and* do not reproduce from the committed prior-engine CSVs either
(−0.0021 / −0.0148 / −0.0568 against the paper's −0.0002 / −0.004 / −0.019). The caption now claims
direction and ordering only, and `docs/p0_corrigendum.md` §6 records it as an open item. Forcing that
gate green would have meant either porting an unauthorised harness or quietly restating numbers.

### Tooling defects fixed while doing this

1. `_skeleton` collision (`c6fcc17`) blocked every ledger regeneration: two sentences ending
   "… on validate, … on test and … on Culver-City" hashed alike once numbers were stripped. The
   skeleton now includes the numeric **shape** (count + decimal widths, never values), so a changed
   measurement still keeps its id and flags STALE.
2. `tools/generate_figures.py` regenerated **only the first figure** when run with no arguments — the
   overview script ends in `sys.exit()`, which took the driver down with it, exiting 0. Per-generator
   `SystemExit` is now caught and reported.
3. `gt_audit.py` and `end_to_end_ap.py` have both been **broken since the restructure** (`523f062`):
   the first wrote to a path two levels too shallow, the second used an undefined `PROV_DIR` and
   crashed *after* computing every AP number — which is why the committed AP table was a
   pre-restructure artefact. Both fixed.
4. Three stale-fingerprint patterns collided with values the corrigendum made **true** (`18.4`,
   `0.275`, `budget-matched`); each was narrowed in context with the reason recorded, none dropped.

---

## Change-log R18-終 (2026-08-17) — the last two rulings; all fifteen checks green

### 1 · tab:robustness → rule (c), ported

**(a) What the three rows measure, against P3's coverage.** SNR-estimation noise, Jakes CSI aging,
decision staleness. The P3 suite covers channel mix ratio, SNR distribution, c_t misclassification,
BLER_L and Rician K — **no overlap**, so (b) does not apply. Each row perturbs only the *selector's
inputs* and replays, so no perception-level inference is needed and (d) does not apply either.
**Rule (c):** ported to `projects/ca_tosg/evaluation/robustness_frozen.py`, frozen selectors on the
corrected grid, CSI-noise and Jakes formulae carried over verbatim so only the selector, grid and
utilities changed.

| row | retired | re-derived (B_max = 0.20) |
|---|---|---|
| SNR-estimation noise, σ ≤ 1 dB | −0.0002 | **−0.0002** |
| CSI aging (Jakes, 60 km/h), ~10 ms | −0.004 | **−0.0025** |
| 1-frame-stale decision | −0.019 | **−0.0109** (changes 18.2% of decisions) |

Direction and ordering survive, magnitudes shrink. The "prior-engine / direction only" disclosure I
had added one batch earlier is **deleted** — it would now be false. No source-less table remains.

### 2 · C256 frame fractions → deleted

The three percentages are gone. The exclusion of C256 now rests on the physical-layer ordering with a
Fig. 2 citation: the 256-QAM cliff sits strictly right of the 16-QAM one, so by the time C256 is
reliable the 16-QAM block is already error-free — an algebraic/physical fact, convention-independent.
The "only quantities carried over from the pre-corrigendum tables" exception sentence is deleted with
them, and **`main.tex` now contains no pre-corrigendum number.**

### 3 · Renumbered in this batch, with three more sign changes

Where2comm comparison, easy-stratum harm account (−0.0040 → −0.0047; 184 → 241 of 713 frames),
collaborator budget breach (N=3 at 0.36842 Msym, and N=2 at 0.26937 **already** breaches 0.20), ρ_F
knees, all three per-SNR AP tables (validate/test/Culver, rebuilt from the regenerated product),
Fig. 4's curve levels, the payload step (0.297 → **0.4795** Msym, i.e. 48% not 30% of B_F), the
ablation table, and both latency sites.

Three claims changed sign or direction and are written as they came out:
* **§V-D channel-only at B=0.30** no longer buys F1 for its extra spend: it is now beaten on **both**
  axes (−0.0025 F1 at 1.36× the channel use). The retired accounting showed +0.0021 for that spend.
* **Headline B=0.10 secondary comparison reversed**: the selector is now marginally *below* the
  validate-tuned threshold (−0.00099, CI [−0.00105, −0.00093]) where it was above by +0.00055.
* **Primary-cell F1 gap** shrank from ≈0.0028 to ≈0.0001 (CI upper bound −0.00002).

### 4 · Two more tooling defects, both found by the gates

* **The registry checked only the first latency occurrence.** Two stale copies of `59.9 ± 5.3 / P95
  66.6` survived behind different spacing (`$59.9 \pm 5.3$` vs `$59.9\pm5.3$`) while the check passed
  on the third. It now collects **every** occurrence and fails if they disagree.
* **Fourth stale-fingerprint collision of the same class.** `0\.895[^9]` matched the corrected, true
  0.89529; narrowed to `0\.895(?![0-9])` and negative-tested (bare 3-dp form still trips, 5-dp does
  not). After 0.248, 27.5 and 18.4, the lesson is recorded in the file: a retired-value pattern must
  be anchored to the precision it was written for.

### Final state

**Eleven gates: ALL PASS. P6-1: MISS 0** (68 literals located, 31 derived). **P6-2:** 70 ANALYTIC /
47 FROZEN / 2 LEGACY-ENGINE — both in the prior-protocol appendix, 0 UNRESOLVED. **P6-3:** 0 / 0 / 0
with all three positive controls firing. **P6-4:** 0 violations.

---

## Change-log R20 (2026-08-17) — generator-owned tables, doc sync, gate upgrades

**Zero GPU.** Everything below is a generator re-emission, a text sync, or a gate upgrade.

### 1–2 · The headline tables now belong to a generator

`tools/build_paper_tables.py` writes `tab:headline`, `tab:headline_agg` and the per-split fixed
baselines of `tab:gen_headline` directly from `true_e2e_ap_by_snr.csv`, `fixed_references.csv`,
`replay_summary.csv` and `FROZEN_MANIFEST.json`. Nothing is transcribed, so re-running the generator is
the only way those cells can change. This mattered: `tab:headline` was still **entirely**
pre-corrigendum, and `tab:headline_agg` was **mixed** — CA-TOSG rows renumbered, fixed baselines and
τ rows retired. All four fixed rows (Fixed-L / F / C256 / masked oracle) are emitted together, so a
one-row patch is no longer possible.

### 3 · §IV-E hyperparameters, strictly from the manifest

`leaf = 2`, `class_weight = None` at all three budgets, depth `10 / 10 / None`, `N_T = 400`,
`max_features = sqrt`. The claim that balanced weighting compensates for label imbalance is
**deleted** — the walk selected unweighted candidates. §IV-E and §V-D now agree.

### 4 · Where2comm: no ranking

The numeric conclusion is withdrawn. Our reproduction's 0.871 is not comparable to anything here on
three axes at once — different scorer (retired global-sort), perfect channel, and a different
collaborator convention. And the direction is not stable: the corrected validate Fixed-L reference is
**0.7819 < 0.871**, reversing the ordering the section used to report. The orthogonality and
composability discussion is kept in full; only the ranking goes.

### 5–8 · Text and docs

"averaged over 5 realisations" → the 200 paired draws it actually was. README's results section is
rebuilt from the registry sources with **both** saving tracks (34.8% vs nominal, 26.6% vs
budget-matched, "quote both or neither"), and the PHY sentence now says the physical layer decides
whether the **chosen high-payload message** lands, with the 2-bit request riding the protected
low-rate path. `model_zoo` tables, the registry's display column, `figures/README` and `HANDOFF.md`
(marked historical) are regenerated or annotated from the manifests. Banner, all three copies:
*all mainline results use the single-collaborator protocol; exceptions (SECOND appendix, Where2comm
reference) are labeled where they appear.*

### 9 · Gate upgrades, and what each caught immediately

* **(a) STALE / unbound rows are now failures.** `tests/test_result_consistency.py --check` fails on
  any `⚠ STALE` or evidence-less ledger row; both had been reported as counts for months while the
  gate passed. Cleared this batch: **130 filled / 0 pending / 0 STALE**, no sentence deleted — all 44
  rows the rewrites had orphaned were rebindable, so there is no deletion list to send.
* **(b) P6-1 extended to every table cell.** Claim-level checking walks sentences, so a whole table
  body could stay retired while the prose around it was bound. The new sweep found exactly that:
  `tab:gen_headline`'s Fixed-F / C256 baselines. Now **191/191 cells located, 0 unlocated**;
  generator-derived cells (regime means) are declared in `DERIVED_TABLE_CELLS.json` rather than waved
  through.
* **(c) README and docs/ are in scope.** The fingerprint sweep and the canonical-registry check read
  `paper/main.tex` only, so the registry's own display column had drifted to *every* retired value
  while its derivations passed. Both now cover README, `model_zoo`, the registry and the milestone
  summary. `p0_corrigendum.md` and the registry's explanatory prose are deliberately **excluded**:
  quoting the retired values is their job.

**A structural fix, sixth of its family.** Numeric fingerprints must be written `NUMBER(?![0-9])`,
never `NUMBER[^d]`: the bracket form consumes the next character, so the sweep cannot separate the
retired `0.888` from a fresh `0.8883`, and it defeats the digit-boundary rule. The last such pattern
is converted, the boundary rule is applied once for all targets, and the lesson is recorded in
`tests/stale_fingerprints.md` after 0.248, 27.5, 18.4, 0.895 and 0.081.

### 10 · Pre-registered as future work, NOT run

Three supervisor revision-level checks are registered here before any of them is attempted, so that
whoever runs them cannot choose the analysis after seeing the data:

1. **Scene-level bootstrap.** Re-derive every headline interval by resampling the nine validate
   scenes (and the test/Culver scenes) rather than frames, since frames within a scene are not
   independent. Expected effect: intervals widen; the non-inferiority margin call at the primary cell
   may become inconclusive. Decision rule to fix now: if the scene-level LCB95 crosses −δ, R9 is
   reported as **inconclusive under scene-level resampling**, not as failed, and both intervals are
   published side by side.
2. **L-link reliability.** The object-level message is modelled with `BLER_L = 0`. Re-run the replay
   with `BLER_L ∈ {0.01, 0.05, 0.10}` (the existing `object_message_bler.csv` axis) and report how far
   the payload advantage survives once the cheap message can also fail.
3. **Fragmentation / HARQ sensitivity.** The feature message is charged as one frame with one BLER.
   Re-run with the message split into `k ∈ {2, 4}` fragments (independent per-fragment BLER, all
   required) and with one HARQ retransmission (payload ×(1+p_retx)), reporting the effect on the knee
   position and on the payload advantage.

None of the three is run in this batch, and no number from them appears anywhere.

### R20 addendum — two self-inflicted incidents, both caught by the gates

**1. `git checkout paper/main.tex` silently reverted four completed edits.** While fixing the table
generator I reset `main.tex` twice to re-run it from a clean base, which discarded the *uncommitted*
item-3/4/5 work (hyperparameters, the Where2comm de-ranking, the 5→200 realisation fix) and the
`tab:headline` caption. Nothing warned; the ledger's unbound-row check (9a, added minutes earlier)
is what surfaced it, by reporting rows whose sentences had reappeared in their retired form. All four
were reapplied and re-verified. Lesson recorded: a generator that rewrites a tracked file must not be
debugged by `git checkout`-ing that file while other edits to it are uncommitted.

**2. Five false ENTITY-VALUE conflicts, fixed at the root rather than by relabelling.** P6-3 kept
pairing quantities that share a ledger `(metric, split)` label but not a scale -- an F1 gap of
0.0001 against a payload of 0.2168, the easy stratum against the hard tercile, a validate knee
against test operating points. Each was individually "fixable" by inventing a narrower label, which
is how the fifth one arrived. Instead the scan now requires the two value sets to sit **within one
order of magnitude**, plus a structural-settings filter (budgets, IoU thresholds) so a claim that
merely mentions `B_max=0.20` no longer collides with everything else about that split. Both controls
still fire, and the count is 0 without a single label invented to get there.

---

## Change-log R21-A (2026-08-17) — two-gate heuristic: PRE-REGISTRATION, written before implementation

**Zero GPU.** Everything below reads the committed caches. This entry is written and committed
*before* the arm's code exists; the run and its numbers are a separate entry.

### Why this arm exists

The selector is currently compared against fixed policies, a one-parameter SNR threshold `tau`, and
a learned bandit. The question a reviewer asks next is not answered anywhere: **does a two-parameter
hand rule already recover most of the gain?** There is a second reason. The `tau` baseline has no
`E` action at all — it emits only L or F — so nothing in the record tests whether **E is reachable
by an explicit rule** rather than only by a fitted forest. This arm has an explicit E gate, so its
`rho_E` is the control for that question.

### The policy, fixed before any fit

Per frame `t`:

* `d_t = s * x_t(cue)` — a difficulty proxy read from the committed cue table;
* `r_t = 1 - BLER_F(gamma_hat_t, c_t)` — link reliability, read from the **committed** Sionna table
  through `deployment.bler16`. **Zero new parameters**: no fit, no rescaling, no new constant.

```
a_t = E            if d_t <= tau_E
      F            else if r_t >= tau_F
      L            otherwise
```

Two free scalars per budget, and nothing else.

### Candidate set (closed; no cue may be added later)

`cue in (ego_num_objects, pcd_num_points, pcd_density_0_20)` x `s in (+1, -1)`, enumerated in that
order as candidate index 0..5. The three cues are the difficulty / visibility proxies among the 21
committed cues. Both orientations are carried **because the direction is genuinely unknown a priori**
— more objects is harder, more points is easier sensing — and picking the orientation after seeing
the curve is exactly the freedom this pre-registration removes. Six candidates, no more.

### Threshold grids (closed)

* `tau_E in {-inf} U {quantile_q(d) : q = 0.05, 0.10, ..., 1.00}` — 21 values; `-inf` = **never E**.
* `tau_F in {0.00, 0.05, ..., 1.00} U {+inf}` — 22 values; `+inf` = **never F**, `0.00` = F whenever
  not E.

### Fitting and selection — the mainline walk discipline, with one substitution recorded

* **Fitting surface**: the deterministic validate grid `data/p2/p2_grid_validate.csv` — the same
  surface the frozen selector was trained on, *not* the 200-draw replay. Selection never touches
  test or Culver.
* **Candidate = (cue, sign)**; the two thresholds are its fitted parameters, exactly as the RF's
  hyperparameters are the candidate and its trees are the fit.
* **LOSO**: the nine frozen validate scenes (`results/manifests/validate_loso_folds.csv`). Per fold,
  `(tau_E, tau_F)` is fitted on the eight in-fold scenes by **max frame-weighted F1 subject to
  frame-weighted payload <= B_max**, then applied to the held-out scene -> OOF actions.
* **Candidate score** `frame_weighted_oof_f1`; **feasibility** `frame_weighted_oof_payload <= B_max`;
  **tie-break** `[max_f1, min_payload, min_candidate_index]`. The mainline's third key
  `shallower_model` has no analogue here and is **dropped, not silently substituted**.
* **Refit**: the winning candidate's deployed `(tau_E, tau_F)` is refitted on the **full** validate
  grid under the same hard constraint — the analogue of the mainline's refit on all of validate.
* **Infeasibility is reported, not relaxed.** If no (candidate, threshold) pair meets the payload
  constraint at a budget, that budget is reported infeasible for this arm.
* The result is frozen into `results/manifests/R21A_MANIFEST.json` (inputs md5/sha256, chosen
  candidate, both thresholds, OOF numbers) **before** any replay.

### How it is reported

A main-table-format row per split x budget under the **same** 200 paired CSI draws
(`CSI_SEED = 20260809`), the same `eff` definition, and the same paired bootstrap (10,000 resamples,
`BOOT_SEED = 12345`) as `deployment.py`, plus the action distribution `rho_E / rho_L / rho_F` beside
the RF's on the identical draws. **Descriptive only, CI only — no decision.** R9's confirmatory
primary is spent; this arm may not be converted into a superiority claim in either direction.

### Expectations, recorded now (checks, not targets)

1. **E1** — the two-gate rule lands between `tau` and RF on F1 at matched payload, nearer RF than
   Fixed-F. **If it is at parity with RF, that is the finding and it is reported as a limit on the
   learned selector's advantage.** The anti-goal clause carries over verbatim: no cue may be added,
   no grid widened, and no orientation re-chosen after seeing this comparison.
2. **E2** — `rho_E > 0` at all three budgets for the selected configuration. If every selected
   configuration lands on `tau_E = -inf` (never E), then **E is not reachable by a monotone rule on
   these cues**, and that is reported as the result of the arm, not as a failed run.
3. **E3** — the arm's payload sits below the nominal `tau` payload at `B_max = 0.20` because the
   constraint forces it; payload comparisons against `tau` are therefore uninformative here and only
   the F1-at-matched-budget comparison is reported.

### Also in this batch (item 3): the Fixed-E reference row

`fixed_references.py` gains a **Fixed-E** row — the ego-only floor: `F1 = mean(ego_f1)`,
payload `0.000`, std `0` (it does not depend on the CSI draw). It is a deterministic read of a
committed cache with no free choice, and it is the floor against which `rho_E` is interpreted.
No paper table is edited in this batch.

---

## Change-log R21-A-run (2026-08-17) — the two-gate arm, as fitted and replayed

**Zero GPU.** `tools/run_baselines.py two_gate --train --evaluate`; 1.7 s to fit and freeze, 14 s to
replay. Nothing frozen was touched: the mainline `F1_RF` recomputed inside this arm is asserted equal
to `replay_summary.csv` at every split x budget before any number is written.

### What the walk selected

Candidate **0** (`ego_num_objects`, `s = +1`) at all three budgets, and at all three budgets it
selected **`tau_E = -inf` — never E**. The reliability gate is `tau_F = +inf` (**never F**) at
`B_max = 0.10` and `0.20`, and `tau_F = 0.60` at `0.30`. The arm therefore *is* Fixed-L at the two
tighter budgets, and a channel-only rule at the loosest one.

### The three expectations

* **E1 missed, at both ends.** The rule does not land between `tau` and RF. At `B_max = 0.10/0.20` it
  lands *below* `tau`, on the Fixed-L floor; at `0.30` it lands *on* `tau` — the freely fitted
  reliability gate rediscovers the SNR-threshold baseline almost exactly (`rho_F` 0.29853 vs `tau`'s
  0.29883 on validate; `dF` vs `tau` is 0.00001 / 0.00000 / -0.00000 across the three splits).
* **E2 refuted, unambiguously.** `rho_E = 0.00000` in every split x budget cell. **E is not reachable
  by a monotone threshold on these cues.** The frozen forest reaches it — barely, and only on
  validate (`rho_E` 0.0107 / 0.0112 / 0.0120) and essentially not at all on test (0.0004 / 0.0012 /
  0.0010) or Culver (0.0000).
* **E3 held in the opposite direction from the one written.** The constraint did not force the
  payload below `tau` at `B_max = 0.30`: the fit is feasible on the *grid* (0.28745) but the
  deployment CSI draw puts it at **0.31224 on test, +0.01224 over its own budget** — the same
  nominal-vs-realised gap that `tau_feasible` exists to expose, now reproduced by a second rule.

### Headline cells (descriptive; no decision, in either direction)

| split | B_max | F1 two-gate | payload | F1 RF | payload RF | dF (2G-RF) 95% |
|---|---|---|---|---|---|---|
| test | 0.20 | 0.89095 | 0.02400 | 0.89691 | 0.14141 | [-0.00606, -0.00587] |
| test | 0.30 | 0.89900 | 0.31224 | 0.89783 | 0.21197 | [+0.00112, +0.00122] |
| culver | 0.30 | 0.86316 | 0.31439 | 0.85932 | 0.18226 | [+0.00375, +0.00393] |

At `B_max = 0.30` the hand rule is **better** on F1 than the selector, by 0.0012 (test) and 0.0038
(Culver) — and pays 47% / 72% more to get it, from outside its own budget. That is the honest shape
of the comparison and it is reported as such: at a budget the channel ladder happens to land on, a
two-scalar rule matches or beats the forest; at the budgets between the rungs it cannot compete
because it cannot get there at all.

### Why it cannot get there — a property of the committed BLER table, not of the fit

`results/channel/bler_sionna.csv` frame BLER at 16-QAM is **effectively binary**: 1.0 for Rayleigh at
*every* tabulated SNR, and 1.0 for AWGN below 8 dB, 0.4024 at 8 dB, 0.0 at and above 10 dB. So
`r_t = 1 - BLER_F` takes three values on the fitting surface (0, 0.5976, 1). Any policy whose F
decision depends on the channel **alone** can therefore realise only four mean payloads —
0.024, ~0.27, ~0.33, 0.99 msym — and `B_max = 0.10` and `0.20` fall in the gaps. This was checked
against a fresh continuous CSI draw (SNR ~ U[0,20], 50 realisations, seed 20260817, validate frames
only) before it was written down: the minimum feasible payload with F ever active is **0.267**, so
the gap is a property of the physical table and not an artefact of the 11-point SNR grid.

Reaching an intermediate budget requires deciding **which frames** deserve F among the frames whose
link can carry it — a per-frame content decision. That is the argument the selector exists to make,
and this arm is the first evidence in the record that a channel-only rule cannot make it.

### One implementation detail not fixed by the pre-registration

The pre-registration fixed the *candidate-level* tie-break but not the threshold-level one. It is
implemented as `max_f1 -> min_payload -> first in the pre-registered enumeration order`
(`tau_E` outer, ascending from `-inf`; `tau_F` inner, ascending from 0.00 with `+inf` last). The
order prefers **never-E** and **more-F** among exact ties, which biases the arm *against* the E2
expectation it is testing — the conservative direction, and stated here rather than left implicit.

---

## Change-log R21-A-2 (2026-08-17) — AMENDMENT, written after the pre-registered rule proved structurally infeasible and BEFORE the amended arm exists

This is an amendment, in the R18-3 sense, and it is written as one. The R21-A rule was not merely
beaten — at two of three budgets it was **unable to bid**, because a channel-only F decision has a
four-rung payload ladder and both tight budgets fall between rungs. A comparison an opponent cannot
enter is not a comparison, so the arm is strengthened rather than declared won.

**What is NOT changed:** the R21-A arm stays exactly as frozen and its numbers stay in the record.
Nothing about the mainline, the frozen selectors, `delta`, `tau*` or any deployed product moves.

### The amended policy

```
a_t = E              if d_t <= tau_E
      F              else if d_t >= tau_D and r_t >= tau_F
      L              otherwise
```

**Three scalars, not two**, and it is labelled that way everywhere it is reported. The F gate is now
a conjunction: the link must carry the message *and* the frame must be hard enough to be worth it.
This is the rule a reviewer means by "surely a simple heuristic does this", and it is the strongest
hand rule the committed cues support without fitting anything.

`d_t`, `r_t`, the candidate set (six `(cue, sign)` pairs, same order), the `tau_E` and `tau_F` grids,
the LOSO folds, the fitting surface, the hard payload constraint, the candidate tie-break and the
descriptive-only reporting are all **unchanged** from R21-A. New: `tau_D` on the same 21-value ladder
as `tau_E` (`{-inf} U quantile(d, 0.05..1.00)`), with pairs restricted to `tau_E <= tau_D`; the
threshold enumeration order is `tau_E` outer, `tau_D` middle, `tau_F` inner. Frozen to
`results/manifests/R21A2_MANIFEST.json` before any replay.

### Expectations, recorded now

* **A1** — the amended rule is feasible at all three budgets and beats the Fixed-L floor. The F1 gap
  to RF at the primary cell narrows but does not close. **If it closes** (`|dF| < 0.002` at test
  `B_max = 0.20`), that is the finding, it is reported in the paper as a limit on the learned
  selector's advantage, and **the anti-goal clause applies with full force**: no fourth arm, no cue
  added, no grid widened, no re-fitting to restore a gap.
* **A2** — `rho_E` stays 0. If it does not, R21-A's refutation of E2 is retracted for the
  three-scalar class and the retraction is written next to the original.
* **A3** — no expectation is recorded for the winning sign of `d`; both orientations are in the
  candidate set and the walk decides.

Zero GPU; seconds of compute.

---

## Change-log R21-A-2-run (2026-08-17) — the amended arm, and the expectation that fired

**Zero GPU.** `tools/run_baselines.py two_gate --train --evaluate --arm dgate`; 2 s + 14 s. The
mainline `F1_RF` recomputed inside the arm is asserted equal to `replay_summary.csv` before any
number is written, as in R21-A. The R21-A arm and all frozen products are untouched.

### What the walk selected

| B_max | candidate | `tau_E` | `tau_D` | `tau_F` |
|---|---|---|---|---|
| 0.10 | 2 · `pcd_num_points` `+1` | never E | 54866.75 (q0.75) | 0.60 |
| 0.20 | 3 · `pcd_num_points` `-1` | never E | -54366.40 (q0.60) | 0.60 |
| 0.30 | 0 · `ego_num_objects` `+1` | never E | 7.00 (q0.05) | 0.60 |

`tau_F = 0.60` at every budget — the reliability gate is the same AWGN-above-8-dB partition the
R21-A arm found, and the whole of the new behaviour comes from `tau_D`. The arm is now feasible at
all three budgets: it hits 0.09410 / 0.19900 / 0.25418 msym on test, inside every cap.

### A1 FIRED: at the primary cell the hand rule matches the selector on F1

test @ `B_max = 0.20`: **0.89697 (three-scalar rule) vs 0.89691 (RF)**, `dF = +0.00005`,
95% CI `[-0.00002, +0.00012]`. That is inside the `|dF| < 0.002` trigger written before the run, so
the pre-registered consequence applies and is executed here: **it is reported as a limit on the
learned selector's F1 advantage, and no fourth arm is run.** No cue was added, no grid widened, no
threshold re-fitted after seeing this.

**But the comparison is not F1-only, and on the other axis the selector wins clearly.** At that same
cell the hand rule spends **0.19900 msym against RF's 0.14141** — `dB = +0.05760`,
95% CI `[+0.05663, +0.05853]`, i.e. **+40.7% payload for +0.00005 F1**; read the other way, the
selector reaches the same F1 with **28.9% less channel**. The same shape holds everywhere the hand
rule wins on F1: test @0.10 `+0.00081` F1 for **+155.7%** payload; Culver @0.10 `+0.00461` for
**+253.4%**; Culver @0.20 `+0.00280` for **+161.8%**. Where RF wins on F1 it also pays less
(validate at all three budgets, test @0.30).

**So the honest statement of this arm's result is: a three-scalar hand rule is F1-competitive with
the selector, and payload-inefficient by 19–253%. The selector's advantage lives on the payload
axis, not the F1 axis.** Any sentence in the paper that claims an F1 advantage over simple rules at
the primary cell must go; the payload claim stands and is now better supported than before, because
it survives a comparator that was allowed to tune three scalars against the same budget.

### Why the gap sits on the payload axis — measured, not asserted

Per F-frame selectivity, measured as the mean `compressed_f1 - late_f1` over the cells each policy
actually sends F on (validate / test):

| policy | `rho_F` | mean gain per F-frame |
|---|---|---|
| three-scalar rule | 0.179 / 0.181 | +0.0415 / +0.0366 |
| RF | 0.132 / 0.122 | +0.0679 / +0.0502 |
| every cell (no selection) | 1.0 | +0.0289 / +0.0304 |

The difficulty gate **does** carry signal — `corr(d, gain)` is +0.35 on validate and +0.15 on test,
and its conditional gain beats the unconditional one — but it is a blunter instrument: RF buys more
F1 per transmitted frame and therefore needs fewer of them. That is the whole of the payload gap,
and it is the mechanism the paper should state.

### A2 held; A3 had no expectation, and the outcome is worth recording anyway

* **A2 held.** `rho_E = 0.00000` in all nine cells again. Across both arms — two scalars and three,
  six cue orientations, every budget — **no threshold rule ever selects the ego-only action.**
  R21-A's refutation of E2 stands and is now stronger.
* **A3.** No expectation was recorded for the sign, and the walk chose **opposite orientations of
  the same cue at adjacent budgets** (`pcd_num_points` `+1` at 0.10, `-1` at 0.20). This is recorded
  as a caution against reading `tau_D` as a semantic "difficulty" threshold: the third scalar is
  doing rate control *and* discrimination at once, and at 0.20 the rate-control component evidently
  dominated the choice of orientation.

### Over-budget on the deployment draw, at three cells

The fit is constrained on the validate grid; the realised replay payload can still exceed the cap
when the CSI distribution differs from the grid. It does so only for the R21-A arm at `B_max = 0.30`
(+0.0122 test) and for the amended arm at Culver `B_max = 0.30` (+0.0144). Every other amended-arm
cell is inside its cap. This is the same nominal-vs-realised gap `tau_feasible` exists to expose
(R18-3), now observed in a third policy family, and it is reported rather than corrected away.

---

## Change-log R23-C (2026-08-18) — the three R20-item-10 sensitivities: implementation pre-registration

**Zero GPU; CPU-analytic throughout.** R20 item 10 registered these three checks and their decision
rule before anything was attempted. This entry fixes the remaining implementation choices **before
the code exists**, because each of them could otherwise be made after seeing the numbers. Nothing
frozen moves; all three are DESCRIPTIVE except where R20's own ruling applies.

### 1 · Scene-level bootstrap (R20 item 10.1)

Frames within a scene are not independent, so the published interval — a paired bootstrap over the
**200 CSI realisations** — understates the uncertainty on the frame axis.

* Unit of resampling: the **scene**. The test split has **16 scenes**, from
  `data/p2/p2_grid_test.csv`'s own `scene` column (the same mapping the leakage gate checks).
* Statistic: per frame, `d_i = mean_r (eff_RF - eff_tau)` over the 200 frozen realisations; the
  cluster bootstrap draws 16 scenes with replacement and reports the **frame-weighted** mean of
  `d_i` over the drawn scenes. 10,000 resamples, percentile, seed `12345` (the R9 seed).
* Same procedure for the payload difference `dB`.
* Cell: **test @ B_max = 0.20**, the sole primary cell. Both intervals are published side by side;
  the realisation-level one is not withdrawn.
* **R20's ruling, applied verbatim:** if the scene-level `LCB95(dF)` crosses `-delta = -0.005`, R9 is
  reported as **inconclusive under scene-level resampling** — not as failed — and both intervals
  appear together wherever the claim appears.

### 2 · L-link reliability (R20 item 10.2)

`BLER_L = 0` is an assumption, not a measurement.

* `eff_L' = late * (1 - BLER_L) + ego * BLER_L` for `BLER_L in {0, 0.01, 0.05, 0.10}`; `eff_E` and
  `eff_F` are unchanged — a failed **feature** message still falls back to ego-only, because no
  object-level message was sent in that frame.
* The policies are **frozen and blind to `BLER_L`**: the selector, `tau` and Fixed-L keep their
  actions, so **payload is invariant and the payload advantage cannot move**. What the sweep can
  move is F1, and that is what is reported: `F1_RF`, `F1_tau`, `F1_FixedL` and the paired `dF` CI
  per budget per split, on the **deployment draw** (`CSI_SEED`, continuous SNR), not the
  sensitivity module's grid draw.
* Invariant asserted at run time: the `BLER_L = 0` row must reproduce `replay_summary.csv` exactly.
  (The existing `results/sensitivity/object_message_bler.csv` was produced on the grid draw and
  under the retired convention; it is superseded, not edited.)

### 3 · Fragmentation / HARQ (R20 item 10.3)

* Codeword BLER `b_cw` is read from the committed table; the mainline frame carries
  **`N_cw = 3960`** codewords (`1.98` Mbit / `K = 500`), which is the payload chain's own number.
* **No HARQ, `k` fragments, all required:** `b_frame = 1 - (1 - b_cw)^{N_cw}` — algebraically
  **independent of `k`**. This is asserted, not assumed: if fragmentation alone moved the number the
  implementation would be wrong.
* **One retransmission per fragment:** `q_k = 1 - (1 - b_cw)^{N_cw/k}`, frame success
  `(1 - q_k^2)^k`, and the payload is inflated by the expected transmissions `(1 + q_k)` per
  fragment.
* `k in {2, 4}`; the replay is re-run with the modified `BLER_F` and the inflated payload, and the
  AWGN cliff onset (first SNR with `BLER < 0.999`) is re-derived under each.
* Deliverable: the scope qualifier already in the paper — *under a whole-frame, no-HARQ model* —
  becomes **numerical**: the reported Rayleigh infeasibility is restated with the worst-case
  Rayleigh frame BLER that survives `k in {2,4}` with one retransmission over the evaluated
  `0`--`20` dB range.

### Expectations, recorded now

* **S1** — the scene-level interval is **wider** than the realisation-level one, plausibly by an
  order of magnitude, because 16 clusters is far less information than 200 paired draws. Whether it
  crosses `-delta` is genuinely unknown and the ruling above decides it, not the author.
* **S2** — F1 falls roughly linearly in `BLER_L` for every policy, and **Fixed-L falls fastest**
  because it never has another action; the selector's *relative* position should therefore improve,
  not degrade, as `BLER_L` grows. If instead the selector degrades fastest, that is the finding.
* **S3** — fragmentation alone changes nothing (asserted); HARQ helps AWGN slightly near the cliff
  and **does not make Rayleigh feasible** at `k in {2,4}`, because `b_cw >= 0.04` at 20 dB and
  `990` codewords per fragment already give `q_k ~ 1`. If Rayleigh does become feasible, the
  paper's Rayleigh conclusion is scoped accordingly and the change is reported prominently.

---

## Change-log R23 (2026-08-18) — supervisor corrections, three sensitivities executed, two gate holes closed

**Zero GPU.** Corrections, generator work, three CPU-analytic sensitivities, and two structural
defects in the verification chain itself.

### A · The seven corrections

1. **`0.187` -> `0.21196`** — the `B_max=0.30` test payload in `sec:pareto`. Its ledger row had been
   bound to `true_e2e_ap.csv`, which holds AP, **not** F1 or payload; it is rebound to
   `replay_summary.csv` (`B_RF`), where the number actually lives.
2. **`2.3x` / `1.7x` -> `1.53x` / `1.47x`** — `sec:threshold` still quoted the retired
   threshold-to-selector channel-use ratios while `sec:headline` already carried the corrected pair.
   Both retired forms are fingerprinted (anchored on `\times`, so the bare 2.3 / 1.7 stay usable).
3. **The channel-only sentence is generator-owned and its DIRECTION is derived.** The milestone
   template said the channel-only variant "reaches a higher F1"; under the corrected convention it
   is **lower on both axes** (0.89529 vs 0.89783 at 1.36x the channel use). The generator now
   computes the direction word from the data, so it cannot go stale again.
4. **The C256 footnote** described the deployed classifier as a two-element class set `{L, C16}`.
   It is `S={E,L,F}`; C256's status is exclusion, not membership of a smaller set. Applied through
   the paragraph-insertion gate's ruling mechanism, tagged `R23-4`.
5. **The Conclusion's action set gains `E`**, and a new gate (below) makes the omission catchable.
6. **`docs/canonical_quantities.md`**: the FA-1 ratio still quoted `0.28843 / 0.18703` and the
   latency row named `selector_B030` when the slowest selector is `selector_B020`. Both corrected —
   and the reason they survived is now fixed: the checker re-derived every number from the CSVs and
   **never read the registry's own prose**. It does now (see C-2).
7. **Quote-both-or-neither is enforced in code.** The milestone generator refuses to emit the
   nominal 34.8% saving unless `tau_feasible.csv` supplies the budget-matched 26.6% beside it.

### B · Two generator holes, both structural

8. **`tab:ablation`, the masked-oracle rows and observation (iii) are now generator-owned.** The
   ablation table carried a retired `0.9011` in two rows; the oracle row of `tab:gen_headline` kept
   `0.9165 / 0.1706 / 17.2%` although the module docstring claimed **all four** fixed rows were
   generated — the oracle was simply not in the generator's row list. Observation (iii) still read
   `0.158`--`0.251` Msym / `16`--`25%`: the substitution meant to own it targeted a sentence form
   `main.tex` no longer contains, so **it had been rewriting nothing on every run while reporting
   success**. All substitutions now go through `sub_once()`, which fails when a pattern matches a
   number of times other than one.
9. **The cell locator accepted non-canonical sources.** It searched every `.csv/.json/.md/.txt`
   under `results/`, so a narrative or historical file could satisfy a cell. Restricted to
   generator-written data products. **The hole passed exactly 4 cells** — all four located only in
   `DERIVED_TABLE_CELLS.json`, the table generator's **own declaration file**, i.e. the generator
   was certifying its own output. They are now reported as declared-derived, which is what they are.

### C · Three defects in the verification chain, found while doing the above

1. **The R20-9a unbound-row check could not fail.** `tests/test_result_consistency.py` printed
   `CLAIMS GATE FAIL` and then exited **0**, because `main()` returned 1 and `__main__` discarded it.
   `verify_results.py` reported PASS over it. Wired to `sys.exit(main() or 0)`; eight rows this batch
   left unbound were then found and bound.
2. **The registry's prose could disagree with its own checker** (item 6). Every `A / B = C` in the
   derivation column is now re-evaluated: both inputs must exist in the CSV the row names, and the
   quotient must equal the displayed value. Both branches negative-tested.
3. **The corpus number-reader could not parse scientific notation.** pandas writes small CI bounds as
   `-2e-05`; the pattern read that as the two numbers `-2` and `05`, so **every gate built on the
   corpus was blind to them** — the primary cell's own CI upper bound `0.00002` counted as
   unlocated. Fixed at the root, in `audit_claims_evidence.NUM_IN_FILE`.

### D · The three R20-item-10 sensitivities — see Change-log R23-C for the pre-registration

Run by `projects/ca_tosg/evaluation/r23_sensitivity.py`, 15 s, zero GPU.

* **Scene-level bootstrap.** Resampling the **16 test scenes** instead of the 200 realisations widens
  the primary interval by **18.938x** on F1, to `[-0.001508, +0.001522]`, and by **45.177x** on
  payload, to `[-0.119307, -0.029856]` Msym. The F1 interval **no longer excludes zero**, but it does
  **not** reach `-delta = -0.005`, so R20's inconclusive ruling is **not triggered**; the payload
  advantage stays strictly negative. Both intervals are published together. Expectation **S1 met**.
* **L-link reliability.** At `BLER_L = 0.10` (test, `B_max=0.20`) the cost is `0.00634` F1 to the
  selector, `0.00588` to the threshold rule and `0.00734` to Fixed L. **S2 is half met and half
  refuted, and both halves are reported**: the selector's margin over Fixed L widens as predicted,
  but its gap to the threshold rule widens *against* it (`-0.00010` -> `-0.00056`), because the
  threshold leans harder on the feature action (`rho_F` 0.20 vs 0.12) and is less exposed to an
  unreliable `L`. Payload is invariant by construction, so no payload claim moves.
* **Fragmentation / HARQ.** Fragmentation alone is **algebraically inert** (asserted, not assumed).
  With one retransmission per fragment the marginal AWGN cliff point at 8 dB falls from `0.402400`
  to `0.100363` (`k=2`) and `0.057077` (`k=4`), at `1.226954x` and `1.120770x` the payload — and
  **Rayleigh does not open at all**: its frame BLER stays at `1.0` across the whole evaluated
  0--20 dB range for every `k`, at `2.0x` the payload. **S3 met.** The paper's qualifier is now
  numerical: the Rayleigh infeasibility is a property of the link budget, not of the no-HARQ model.

### E · Wording, and a gate that enumerates instead of grepping

13. "runs in real time" -> the selector's inference fits within the 100 ms frame interval, with an
    explicit statement that the **end-to-end chain is not measured**.
14. "the dominant decision signal is channel state **rather than selector-model complexity**" — the
    model-complexity half rested on a prior-protocol model-comparison table that was never re-run.
    Deleted; the SNR-threshold half, which is supported, stays.
15. **`tests/test_numeric_literals.py`** enumerates every decimal literal in the delivered text and
    requires each to be covered by a **verified binding**. The first implementation asked only
    "does this number exist somewhere under `results/`" — and was measured before being trusted:
    with 202 committed products, **every single retired value this batch removed** (0.187, 2.3, 1.7,
    0.9011, 0.9165, 0.1706, 0.2542, 0.158, 0.251) found a coincidental match and would have passed.
    That version was discarded. The gate now ratchets against `tests/uncovered_literals.md`, which
    opens with **101 registered debt entries (115 occurrences)** — prose CI bounds whose ledger rows
    carry no CSV binding, and `docs/model_zoo.md`'s zoo AP values, which live in no product of this
    repo. New uncovered numbers fail; the register is the burn-down list. Generated documents are
    held to the stronger rule instead: re-running their generator must reproduce them byte for byte.

### R23 addendum — a third self-inflicted incident, caught by re-running the gate twice

The new literal gate's generated-document check **let the generator's write stand**. A stale
`results/README.md` therefore failed the run that found it and passed the next one, because the
failing run had silently repaired the file. `verify_results.py` printed `GATE FAILURE` once and
`ALL GATES PASS` immediately afterwards with no edit in between, which is how it surfaced. The check
now restores the original bytes in a `finally` block, so it reports the state it found and leaves the
working tree untouched; running it twice in a row is now identical. Fourth member of the family whose
lesson is the same: **a check that changes what it is checking cannot report on it.**


---

## Change-log R24 (2026-08-18) — the hand-rule arm enters §V; the literal debt is paid down

**Zero GPU.** Prose, one new generator, binding work. No new experiment and no new adjudication;
the only new product is a selectivity column emitted from the existing R21 replay.

### 1 · R21-A / R21-A-2 written into §V (`sec:handrule`)

The new subsection states, in this order: the pre-registered two-scalar rule **cannot bid** at
`B_max = 0.10` and `0.20` (never-E, never-F; it *is* Fixed L) and at `0.30` rediscovers the SNR
threshold (`rho_F` 0.29853 vs 0.29883); the amendment to a three-scalar rule, **declared as an
amendment and reported as three scalars**; **F1 parity at the primary cell** (0.89697 vs 0.89691,
`+0.00005`, 95% CI `[-0.00002,+0.00012]`), stated plainly rather than around; and the payload gap
that is the actual result (`+0.05760` Msym, 95% CI `[+0.05663,+0.05853]` — 40.7% more channel for
that parity, or 28.9% less channel for the same F1).

The **mechanism sentence** is new evidence, not prose: `gain_per_F_frame` is now emitted by the
replay (mean `compressed_f1 - late_f1` over the cells each policy actually sends F on). On test at
`B_max = 0.20` it is **0.05022** for the selector, **0.03660** for the hand rule and **0.03038** for
the SNR threshold — the last indistinguishable from the **0.03042** unconditional mean, i.e. the
threshold rule's feature frames are no better chosen than average. The selector buys more F1 per
transmitted frame and needs fewer of them; that is the whole payload gap.

**The "beats simple rules" family is now a fingerprint.** Three verb-anchored patterns block any
claim of an F1 win over a hand / simple / threshold rule, while leaving the payload claim sayable.

**E2's refutation is written into the E-collapse discussion**: a hand rule with an explicit `E` gate,
searched over six cue orientations, selects `E` in **no** cell — on these cues `E` is structurally
out of reach of a monotone threshold, and the frozen selector's small `rho_E` is more than any of
them attains.

### 2 · One mechanism, three collapses (`sec:ablation`)

The four-rung payload ladder is stated once and referenced: the committed frame BLER is effectively
binary in the channel state, so a policy whose feature decision depends on the channel **alone** can
realise only `0.024 / ~0.27 / ~0.33 / 0.99` Msym, and the two tighter budgets fall between rungs.
That single fact explains the channel-only ablation pinning to `B_L`, the two-scalar hand rule
degenerating to Fixed L, and the nominal SNR threshold landing **over** budget at `B_max = 0.20`.

### 3 · Literal debt: 101 -> 12 entries, and two findings inside it

* **Sign normalisation** in the verified set (`+0.00005` in the ledger vs `0.00005` printed inside a
  bracket) — 30 occurrences were never debt at all.
* **`README.md` and `docs/model_zoo.md` cleared (58).** Echo documents now bind by the ledger's own
  discipline: the source file must be **named in the document**, and the value must be in that named
  file — not "somewhere under `results/`". While applying it, the README's **model-zoo table turned
  out to be entirely pre-corrigendum** (0.9070/0.0679, 0.9087/0.0992, 0.9094/0.1570 against the
  manifest's 0.8555/0.080803, 0.8606/0.150158, 0.8622/0.201607). Nothing had caught it: no claim row
  covers the README and the fingerprint sweep only greps values already known to be retired. It is
  now written by `tools/build_readme_tables.py` from `FROZEN_MANIFEST.json`.
* **Provenance JSON is canonical again, provenance TXT is not.** The R23-9 exclusion was written for
  narrative transcripts and had also excluded generator-written JSON records, which are the only
  committed home of some figure-caption values. `DERIVED_TABLE_CELLS.json` stays excluded — that one
  is the generator certifying its own output.
* **Six structural entries**, each with a reason: `1.98`, `3.96`, `0.999`, `0.01`, plus **two
  EXTERNAL REFERENCE values** (`0.775`, `0.682` — the OpenCOOD zoo's published AP for the SECOND
  late-fusion checkpoint, recorded 2026-08-18; our reproductions are bound to
  `P4B_VERIFICATION_late.json`).
* **Two of the twelve survivors are findings, not floor effects, and are flagged as such:**
  `0.0040` is bound to `robustness_frozen.csv`, **which does not contain it** — it escaped p6 because
  p6's sentence walk and the ledger builder disagree on that sentence's id; and `0.0003`'s evidence
  is `SCOMCP_FUSE_REPORT.md`, a narrative report, with the value absent from `scomcp.csv`. Both need
  a re-derivation or a sentence downgrade. **Neither is silently retained.** The other ten are
  below `distinctive()`'s precision floor (fewer than 3 decimals and 3 significant digits), so p6
  never checks them; their claim rows are bound, their literals are not verified.

### 4 · The R23 sentences, re-checked in place

Confirmed by locating each verbatim: the scene-level pair beside the realisation-level one
(`sec:headline`), both halves of the `BLER_L` result including the unfavourable one
(`sec:robustness`), and the numerical HARQ qualifier (`sec:channel`). R23's report was accurate.

---

## Change-log R25 (2026-08-18) — three direction errors, the HARQ replay completed, and a gate that reads directions

**Zero GPU.** One CPU-analytic replay (42 s), the rest prose, bindings and one new gate.

### 1 · Three comparisons pointed the wrong way

All three had correct numbers and a wrong direction, which is why every existing gate passed them:

* `sec:threshold` claimed the selector was **ahead** of the tuned threshold at `B_max = 0.10`. On
  test the nominal threshold is ahead **at every budget**: `0.89247 / 0.89701 / 0.89900` against
  `0.89148 / 0.89691 / 0.89783`, at `1.97x / 1.53x / 1.47x` the channel use, and at the two looser
  budgets from outside the cap. Against `tau_feasible` the ordering reverses at **one** budget only
  (`+0.00067` at `B_max = 0.20`; `-0.00174` and `-0.00118` at `0.10` and `0.30`). Rewritten.
* The **Conclusion** repeated the same error ("ahead of it at the tightest budget"). Rewritten to
  the measured direction.
* `sec:threshold` also said the channel-only variant "does reach a higher F1 than the full selector"
  at `B_max = 0.30`, **contradicting `sec:ablation` two sections earlier**, which reports it beaten
  on both axes (`0.89529` vs `0.89783` at `1.36x` the channel use). One fact may have one direction;
  the contradicting half is rewritten to match.

### 2 · Why the "lighter models" claim survived R23-14 — attribution

Not a generator write-back and not a missed edit: R23-14's edit **did** land and is still in place
(the Conclusion's "rather than selector-model complexity" is gone, `git log -S` confirms it at
`986854d`). What survived is a **second home for the same claim** that the R23 inventory never
located: the contribution list's "two \emph{interchangeable} realisations". The failure was an
incomplete inventory of one claim, not a lost edit. Fixed here: the bullet now reads "two policy
realisations with **different payload--F1 operating points**", which is what the data supports.

### 3 · HARQ: an accounting error corrected, and the replay finished

* **`E[N_tx] = 1 + q_first`.** The R23-C summary used the *post-HARQ* failure probability `q_eff`
  in the payload column, understating the expected transmissions. `frag_bler` now returns both, and
  the corrected AWGN means are **1.646338 / 1.632843 / 1.624675** for `k = 1 / 2 / 4`. The per-row
  `payload_factor` was already `1 + q_first` and is unchanged, so the **8 dB single-point values in
  the paper need no change** (`0.402400 -> 0.161926 / 0.100363 / 0.057077` at
  `1.402400 / 1.226954 / 1.120770x`) — checked, not assumed.
* **The replay, as pre-registered.** R23-C promised the modified BLER **and** the inflated payload
  through the deployment replay; R23 delivered only the analytic table. Now complete:
  6 configurations x 3 splits x 3 budgets x {RF, tau, Fixed-L} in
  `results/sensitivity/r25_fragmentation_replay.csv`. One retransmission moves the selector by at
  most `+0.00064` F1 and `+0.00803` Msym, and moves the threshold rule **not at all** at
  `B_max = 0.20` — its feature requests already sit above the cliff. No conclusion changes.
* **A convention mismatch the invariant caught.** The first implementation interpolated the
  *codeword* BLER and exponentiated; the mainline interpolates the *frame* BLER. Off-grid the two
  differ, and the pre-registered `(k=1, no HARQ) == replay_summary.csv` check failed at `2e-5` on
  validate. The modified table is now built at the tabulated points and interpolated by exactly
  `deployment.bler16`'s rule.

### 4 · The hand rules are baselines, in the baselines list

`sec:baselines` now defines the SNR-threshold rule (nominal and budget-matched) and the two- and
three-scalar hand rules. Their results stay in `sec:handrule`; nothing is duplicated.

### 5 · The canonical framing sentence

Settled in `sec:threshold`, and the ledger row carries it as the allowed wording:
*\method{} does not win by raising average F1. A one-line SNR threshold and a three-scalar hand rule
reach comparable F1, but they do so by sending more feature messages. What the task cues buy is
knowing which of the frames the channel can carry are actually worth sending, so that perception
stays non-inferior at lower communication.*

### 6 · New gate: comparison direction

`tests/test_comparison_direction.py` reads `(A, B, direction, metric, split, budget, probe)` tuples
from `tests/comparison_claims.md`, looks both quantities up in the canonical product that owns them,
and fails when the claimed direction disagrees with the data. **14 comparisons are registered.** The
three errors above are the regression cases: the self-test asserts that each, written the wrong way,
**fires**. Each row also carries a verbatim `probe` from the sentence that makes the claim, so the
table cannot drift away from the text — that control fired immediately, on a probe of mine that said
`Fixed L` where the paper writes `Fixed $L$`.

---

## Change-log R26 (2026-08-18) — the two debt findings discharged, and the abstract brought into scope

**Zero GPU.** One derived product, two sentences re-read from their sources, three abstract fixes,
one gate-scope assertion.

### 1 · The easy-stratum sentence, re-read from `difficulty_frozen.csv`

The mis-binding R24 flagged is discharged rather than excused. The frozen product does not say
`-0.0040`; it says **`-0.00471` (95% CI `[-0.00742,-0.00236]`)** at test / `B_max = 0.20`, and the
effect is **monotone in the budget** — `-0.00020`, `-0.00471`, `-0.01129` across `0.10/0.20/0.30`,
as a looser cap lets more easy frames be sent as `F`. It is also **split-dependent, not universal**:
on validate and Culver-City the same tercile *gains* at every budget (`+0.00035`--`+0.01016` and
`0.00000`--`+0.00558`). The narrative follows the data: the over-request cost is now stated as a
property of the test split's easy tercile, where Fixed `L` already reaches `0.97962`. The retired
`-0.0040` is fingerprinted in its easy-stratum context.

### 2 · The delivery-semantics bracket gets a product of its own

The sentence was bound to `results/baselines/SCOMCP_FUSE_REPORT.md` — a narrative report about a
different arm, which does not contain its numbers. `delivery_semantics_bracket.py` now derives
`results/sensitivity/delivery_semantics_bracket.csv` from the committed `collaborator_scale.csv`
(semantics A vs B, validate, `N=2`, per budget). **The old sentence was wrong twice over:** the
bracket is `+0.00016 / +0.00036 / +0.00099`, not "`+0.0001` to `+0.0003`", and the scope is
**964 frames, not 690** (`frames_in_scope` is the count where partial fusion replaces the
all-or-nothing collapse). Payload is identical under both conventions because the **request** is
what is charged — now stated explicitly. The SComCP mis-binding is deleted.

**The debt register is down to 10 entries**, and every survivor is a floor effect (`distinctive()`
skips literals with fewer than 3 decimals and 3 significant digits), not a finding. The ratchet has
only shortened: 101 -> 12 -> 10.

### 3 · Three abstract repairs

* **"On test there is therefore effectively nothing to contest" is deleted.** The abstract now reads
  the headroom the same way `sec:true_e2e` does: the triple `0.0550 / 0.0240 / 0.0970`, the frozen
  selector converting **at most about a fifth** of it (`2.5`--`21.3%` across splits and budgets),
  and no AP advantage claimed on any split.
* **The "currency" sentence is rebuilt on the canonical framing (R25-5):** the result is not an
  accuracy result; a one-line threshold and a three-scalar hand rule reach comparable F1 by sending
  more feature messages; what the cues buy is knowing which of the carriable frames are worth
  sending.
* **The graceful-JSCC half no longer asserts in the abstract's own voice.** "the graceful JSCC
  branch, modelled as analog transmission, survives" is gone; what remains is that whether a
  graceful codec shifts the balance is *exploratory evidence only, reported in an appendix under the
  prior protocol and not re-evaluated under the frozen one*.

### 4 · The abstract is now inside the gates, as an assertion

The literal-coverage gate always scanned it (`paper/main.tex` is a target, and the claim walker
places the abstract in its `(preamble)` chunk) — but the direction gate did not point at it, which is
exactly how a comparative abstract sentence with no numbers survived. `tests/comparison_claims.md`
gains three abstract-probed rows, and `test_comparison_direction.py` now **asserts** that at least
one registered comparison is probed inside `\begin{abstract}...\end{abstract}`: **17 comparisons
registered, 3 of them inside the abstract**. The self-test removes the abstract and confirms the
scope assertion fires.

---

## Change-log R27 (2026-08-18) — signalling direction, the JSCC arm's status, and a terminology class

**Zero GPU.** Four prose corrections, one verification, one new check class.

### 1 · The signalling direction, third recurrence — now tracked

Contribution 1 said "the **sender** adaptively selects the semantic level". The architecture is
receiver-driven (Sec. III-A): the ego evaluates its own perception and channel state and **requests**
a level with a 2-bit codepoint; the collaborator transmits what was requested. Writing it sender-side
inverts the contribution. Rewritten.

Because this is the **third** time the direction has slipped, it is now checked rather than
remembered. `p6_cross_section_scan.py` gains a **TERMINOLOGY** class: entities whose *description*
has gone wrong more than once, curated in `tests/tracked_terms.md` with a forbidden form, the
required framing and the reason. Three forms are tracked (sender-side verb, `sender-driven`, and the
JSCC arm being described as mainline). The positive control injects the exact sentence that recurred;
the self-test asserts it fires and that the live document is clean — and it earned its keep
immediately: a literal `|` inside a regex broke its own markdown row, so the first draft silently
parsed **1 of 3** rows, and the injected fault stopped firing. Alternation is now written `&#124;`.

### 2 · The ImportanceMapJSCC arm is labelled where a reader meets it

The `sec:baselines` entry is retitled **"ImportanceMapJSCC (exploratory; Appendix A)"** and states
that it is a prior-protocol arm, not re-evaluated under the frozen single-collaborator protocol, and
therefore present in **no** mainline table or figure. Contribution 3's baseline list is replaced by
the comparators the mainline actually contains — fixed ego-only / object-level / feature-level with
LDPC + 16/256-QAM, the SNR threshold at **both** its nominal and its budget-matched tuning, the two-
and three-scalar hand rules, and the channel-aware oracle — with the JSCC arm named separately as
the exploratory appendix comparison.

### 3 · Sec. VI-B checked, nothing to clear

Verified rather than assumed: `sec:ap_snr`'s prose carries **no** JSCC curve narrative. There is no
"saturates near 0.71" family anywhere in `main.tex` (the three `saturat*` hits are the
perfect-channel ceiling caption and two collaborator-supply sentences), and the subsection already
routes the codec-comparison baselines to Appendix A explicitly. No change made.

### 4 · The Conclusion's graceful-codec clause

It asserted flatly that "under a graceful codec they become necessary for accuracy". It now carries
the same triple qualifier as the abstract: the graceful-codec half rests on **exploratory** evidence
gathered under the **prior protocol** and reported in **Appendix A**, not re-evaluated under the
frozen one. The cliff-codec half, which is supported by the mainline, is unchanged.

---

## Change-log R28 (2026-08-18) — the C256 paragraph's retired fractions, and the source that was passing them

**Zero GPU.** Prose deletions, one regenerated product, one structural change to what counts as
evidence.

### 1 · Three pre-corrigendum percentage families deleted from the C256 paragraph

`99.0 / 94.2 / 99.1%`, `0.7 / 4.2 / 0.9%` and `2.5 / 3.2 / 4.5%` are gone, together with the orphan
footnote that explained the first two ("Fractions rounded to 0.1 pp. All four come from one run…").
What remains is what does not depend on the collaborator convention: the physical-layer ordering
(`b_256 >= b_16`, the 256-QAM cliff strictly to the right, Fig. 2), the sign argument on
`(comp-ego)(b_16-b_256)`, and the structurally-zero deployment count
(`0` of `396,000 / 434,000 / 110,000`, which is frames x 200 realisations and therefore convention-
independent). The paragraph is self-sufficient without a single fraction.

### 2 · The binding-source audit: how they passed, and what else that source was passing

They were bound to **`results/sensitivity/c256_dominance_verify.csv`**, produced 2026-08-12 —
*before* the P0 corrigendum. Its `frac_comp_ge_ego` / `frac_comp_lt_ego_and_tie` columns are
full-collaborator fractions, and the literal gate accepted them by **percent-form matching**
(`0.9899` satisfies `99.0`), so three retired families were "verified" inside one paragraph.

**A committed file under `results/` is not automatically evidence.** `tests/retired_products.md` now
registers products that are present in the tree but may not serve as binding sources, and
`canonical_corpus()` excludes them, so a claim bound to one reports as unlocated instead of passing.
**The same-source audit found exactly one other passenger:** the collaboration-harm sentence's second
triple, `1.0 / 5.8 / 0.9%`, which came from that file's `frac_comp_lt_ego` column. Re-derived from
the N=1 caches it is **`1.3 / 6.5 / 0.9%`** — corrected in the text, and the retired triple is
fingerprinted.

**A second retired product surfaced while checking it.** `step4_collaboration_harm.csv` existed
**twice**: `results/step4_collaboration_harm.csv` (what the generator actually wrote) and
`results/main/step4_collaboration_harm.csv` (a 2026-08-12 pre-corrigendum copy nothing regenerated),
while the generator *printed* "wrote results/main/…". Both were indexed as products. The generator
now writes where its message says, emits the second harm quantifier as a column
(`frac_comp_lt_ego`), and the stale duplicate is deleted. Its regenerated first triple confirms the
paper's `1.5 / 5.8 / 0.2%` exactly (0.0146 / 0.0576 / 0.0018).

### 3 · The CoDS comparison enumerates the deployed set

"the compact object-level message or one of the feature-level variants" -> "**ego-only operation with
no request at all, the compact object-level message, or the feature-level message**". Singular `F`;
`C_256` does not appear, because it is not in the deployed set.

### 4 · Three verifications

* **§IV-A action-set sentence** — confirmed: it states `s_t \in \mathcal{S} = \{E, L, F\}` and
  defines all three, with `E` first.
* **The `'11'` codepoint future-work sentence** — confirmed deleted; the surviving text says `E` is
  already a deployed action with its own codepoint, so the remedy is a selection-policy question.
* **The harm account** — the first triple `1.5 / 5.8 / 0.2%` is confirmed **current** (regenerated:
  0.0146 / 0.0576 / 0.0018). The second triple was **not** current; see item 2.
* **The Conclusion's graceful clause** — confirmed carrying R27-4's prior-protocol / appendix /
  exploratory qualifier.

### 5 · Three paragraph-gate rulings

All four prose changes fall inside insertion-gated paragraphs, so each is declared: `R28-1a`
(footnote + margin sentence), `R28-1b` (oracle-share clause and the closing sentence), `R28-3`
(CoDS enumeration) and `R28-4` (harm quantifier). Deriving each ruling's source **verbatim from the
post-inlining draft** rather than typing it was necessary: the footnote is inlined before rulings are
applied, and a hand-typed source silently failed to match three times.

---

## Change-log R29 (2026-08-18) — the generalisation claim narrowed to what transferred

**Zero GPU.** One contribution bullet, one fingerprint family, one locator fix. Final batch before
compilation.

### 1 · Contribution 4 said "verify generalisation"; only half of it generalises

The bullet claimed to "verify cross-split and Culver-City domain-shift generalisation with a frozen
selector". Checked against the frozen replay before rewriting: **the communication saving transfers**
— payload reductions against the nominal threshold are `32.2`--`49.2%` on test and `42.1`--`68.9%` on
Culver-City — **but the F1 non-inferiority does not**. On Culver at `B_max = 0.20` the selector is
`0.00883` below the threshold rule (95% CI `[-0.00902, -0.00865]`), **outside** the pre-registered
`0.005` margin. It holds at the other two Culver budgets (`-0.00290`, `-0.00384`) and against
`tau_feasible` the same cell is `-0.00726`, also outside the margin — so the exception is stated with
its budget rather than blanketed. The bullet now says exactly that, matching `sec:generalisation`
("the transfer is in the channel use, not the F1") and the Conclusion.

The **"verify generalisation" family is fingerprinted** in three verb-anchored forms, so a future
edit cannot restore a claim that asserts both halves; the payload-transfer half stays sayable.

### 2 · A locator fix the new sentence exposed

`0.00883` was bound at claim level and **unlocated** at literal level: the paper writes "falls
`0.00883` below", where a minus sign would be wrong, while the CSV stores the signed `-0.00883`. The
verified set had been sign-normalised in R24-3 but `carries_any_unit` had not, so the same number was
simultaneously verified and unverifiable. The locator now tries the negation and reports the match as
`sign`. Sixteen further literals across the document became located as a side effect (`found` 242 ->
257), none of them newly *claimed* — they were always bound, just invisible to this check.

### State at the end of the batch series

Sixteen gates, all passing, twice in a row on a clean tree. The literal debt register stands at
**10 entries**, every one a precision-floor effect rather than a finding. Nothing in this batch
touched a frozen product, a manifest or a result CSV.

---

## Change-log R30 (2026-08-18) — five wording corrections before compilation

**Zero GPU.** Four prose repairs, one section title, one tracked-term addition. No product, manifest
or CSV is touched.

### 1 · The headroom share is one-sided, not an interval

`2.5`--`21.3%` asserted a floor that does not exist: the minimum across splits and budgets is
**`0.0%`** (Culver-City at `B_max = 0.10`, `true_e2e_ap.csv`), and `2.5%` is merely test's tightest
budget. Both the abstract and the Conclusion now read **"up to `21.3%`"**, with the `0.0%` cell named
rather than averaged away. The interval form is fingerprinted; the two claim rows are rebound with
the max/min derivation spelled out.

### 2 · The lighter-models claim, third home

Sec. IV-F closed with "…shows lighter models and even a hand-tuned SNR-threshold rule reach the same
realised F1" — the third instance after the Conclusion (R23-14) and the contribution list (R25-2).
Replaced with the supervisor's wording: *the SNR-threshold and three-scalar hand-rule baselines
achieve comparable F1, but require higher communication payload at the primary operating point.*
The claim family is now a **TERMINOLOGY** row in `tests/tracked_terms.md`, so a fourth home fails a
gate rather than waiting for a reader.

### 3 · C256 exclusion restated as set domination

> **SUPERSEDED BY R31-1 (2026-08-18).** The set-domination argument below was itself withdrawn: under
> the supervisor's option-1 framing `C_256` is a physical-layer comparator excluded from the deployed
> set **by design** (modulation order is a transport parameter, not a semantic granularity), and no
> dominance claim of any form is made about it. The record is kept for the history of the sentence;
> the live wording is R31-1's.

The argument no longer needs frame statistics or a case analysis of strictness:

* when `comp >= ego`, `C_16` delivers the identical payload at a block-error rate that is never
  higher, so it is no worse than `C_256` on every such frame;
* when `comp < ego`, sending any feature message can only lower the expected utility, and `E` is no
  worse than either feature mode.

The two cases are exhaustive, so `C_256` is dominated on every frame by an action already in
`{E, C_16}`. The old concession — "dominance reverses only in the collaboration-harm regime" —
**goes with the case analysis it belonged to**: under set domination there is no reversal to concede.

### 4 · The abstract's non-inferiority claim names its cell and quotes both tracks

It now states the **single pre-registered confirmatory comparison** (test at `B_max = 0.20`), leads
with the **budget-matched** threshold (`26.6%` less channel, inside the `0.005` margin), and reports
the nominal `34.8%` beside it **with its overspend on the face of it** (`0.2168 > 0.20` Msym) —
quote-both-or-neither, satisfied with numbers rather than by dropping them.

### 5 · Title and labelling

`sec:handrule` is retitled **"Hand-Rule Baselines and Their Communication Cost"** — the arm is a
baseline family, not a two-parameter curiosity, and the title now names the axis the result is on.
Every nominal-threshold saving in the document was re-checked for its over-budget label: five
occurrences, four already labelled, and the fifth (the contribution bullet's `32.2`--`49.2%` /
`42.1`--`68.9%`) now carries it. The `sec:threshold` occurrence at L706 was verified to carry the
label inside its own sentence and is left as written.

### 6 · One chained ruling

The C256 rewrite is the second authorised rewrite of the same sentence, so `R30-3` is chained onto
`R28-1a` rather than replacing it: the paragraph gate's ruling list now reads
`B2 -> R23-4 -> R28-1a -> R28-1b -> R30-3 -> Q2`, which is the sentence's full authorised history.

---

## Change-log R31 (2026-08-18) — three corrections, a compile gate, and a page-count shortfall

**Zero GPU.** Prose, one new generator, two new gates, one build toolchain.

### A1 · C256 is a physical-layer comparator, excluded by design

Rewritten to the supervisor's option 1. `C_256` carries the **identical semantic content** as `C_16`
and differs only in modulation order; it is included to isolate the codec's channel response at fixed
semantics (Fig. 2), and it is **not** in `S = {E,L,F}` **by design** — modulation order is a
transport parameter, not a semantic granularity the receiver can request. Every dominance claim is
withdrawn: the paragraph's set-domination argument (R30-3), the Fig. 2 caption's "hence dominated",
and §III-G's *"for non-trivial λ … C16 dominates C256"* — **whose direction was wrong anyway**, since
`C_256` is the *smaller* payload, so a payload penalty biases toward it. The BLER cliff and Fig. 2
stay as motivation. Six patterns fingerprinted; four claim rows rebound as definitional; `R31-1`
chained onto the paragraph's ruling list, which now reads
`B2 → R23-4 → R28-1a → R28-1b → R30-3 → Q2 → R31-1`.

### A2 · The abstract's confirmatory comparison is the nominal one

The pre-registered confirmatory comparison is against the **nominal** threshold (34.8%, comparator
over budget at 0.2168 > 0.20 Msym); the budget-matched `tau_feasible` comparison (+0.00067 at 26.6%
lower payload) is **secondary, with no non-inferiority decision attached**. R30-4 had inverted that
precedence. Ledger rows and the direction gate's abstract probe are synced.

### A3 · The locked-wording file was locking retired numbers

`results/provenance/r9_result_claims.md` — the authority `docs/claims.md` defers to for the R9
sentence — was **entirely pre-corrigendum**: dF −0.0028, payload 0.095 vs 0.217, reduction 56.3%,
Culver −0.0099. It is now generated by `tools/build_r9_claims.py` from `replay_summary.csv` and
`tau_feasible.csv`, and a new gate (`--check`) fails whenever the committed file is not what the
current replay produces. The retired numbers are fingerprinted.

### B4 · The paper now builds inside the gate

`apt` is unavailable without a password here, and the conda `texlive-core` build cannot generate its
own formats (`mktexfmt` looks for a Perl module that ships as a shell script). The gate therefore
uses **tectonic** in a separate `latex` env, leaving the pinned `sionna310` untouched.
`tests/test_compile.py` requires a zero return code, zero LaTeX errors and pages ≤ 17, and writes
`docs/compile_report.md` with the page count and every overfull box.

### C5–C6 · Compression: 25 → 24 pages, and an honest shortfall

Done: six figures removed whose content is carried by tables or text (`fig:qualitative`,
`fig:payload_snr`, `fig:two_regime`, `fig:decision_budgets`, `fig:difficulty`, `fig:feat_imp`, with
every number moved into the surrounding prose and every dangling `\ref` re-pointed); the
payload-versus-SNR subsection folded into §VI-B; related work compressed ~30%; Appendix A's prose
compressed; the hand-rule and robustness prose compressed; ten small tables set `\footnotesize` with
`\tabcolsep 3pt`, three wide tables promoted to `table*`. Overfull boxes fell from 9 to 6.

**The result is 24 pages, not 15–17, and the compile gate reports FAIL.** The instruction was that
claims and numbers must not change, and at that constraint the arithmetic does not close: the
manuscript carries ~150k characters of text, ~6k characters per page at this template density, so
reaching 17 pages needs roughly a third of the text removed. Prose compression returns about
0.15 page per thousand characters rewritten; the passes above removed ~7k characters. The remaining
seven pages require a **scope decision**, which is not mine to take:

* move Appendix A (JSCC, prior-protocol) and Appendix B (second backbone) to supplementary material
  — both are already labelled non-mainline; ≈ 3.5 pages;
* drop `tab:gen_true_e2e` / `tab:gen_true_e2e_culver` and keep the aggregate generalisation table
  — ≈ 0.8 page;
* fold §VI-D (decision ratios) and §VI-E (feature importance) into one subsection — ≈ 0.7 page;
* reduce the remaining five figures to single-column at 0.8\linewidth — ≈ 0.6 page.

Sensitivity-merge (C5's "three sensitivities into one paragraph + one table") is **not done**: it is
a relocation of three bound passages worth ≈ 0.3 page, and it would need a rebinding round that the
page target does not benefit from until the scope decision above is taken.

---

## Change-log R32 (2026-08-18) — the move to supplementary material, and 25 → 21 pages

**Zero GPU.** Relocation and redundancy removal only: no claim, number or locked wording changed,
and nothing moved out of the main file was deleted.

### 1 · What moved, and where it went

`paper/supplementary.tex` is new, standalone and compiles on its own (**3 pages**, tectonic, zero
errors). It carries, verbatim:

* **Appendix A** (JSCC cliff-versus-graceful, prior-protocol arm) and **Appendix B** (second
  detection backbone) — both already labelled non-mainline in the main text;
* **the full 21-cue definition table**. The main text keeps five representative cues
  (ego object count, LiDAR point count, near-range density $0$--$20$~m, mean point range,
  front-sector far count beyond $30$~m) and points to the supplementary list.

All 16 main-text pointers into that material now read "the supplementary material"; no `\ref`
dangles. The ledger rows for the moved sentences leave `docs/claims.md` with them, because that file
is generated from `main.tex` — the **LEGACY** rows among them (the prior-protocol appendix) therefore
now live in the supplementary domain, which is where the audit should look for them.

**Coverage follows the content, in both directions:** `paper/supplementary.tex` is added to the
fingerprint sweep (no retired value may reappear there), and `tests/test_canonical_quantities.py`
now reads main *plus* supplementary — reading only `main.tex` made four correctly printed JSCC
registry numbers report as missing the moment they moved.

### 2 · What was cut from the main file

Two per-SNR generalisation tables (`tab:gen_true_e2e`, `tab:gen_true_e2e_culver`), replaced by a
pointer to `true_e2e_ap_by_snr.csv`, with the aggregate generalisation table kept; six figures whose
content the tables and prose already carry (`fig:qualitative`, `fig:payload_snr`, `fig:two_regime`,
`fig:decision_budgets`, `fig:difficulty`, `fig:feat_imp`), every number moved into the surrounding
sentences; §VI-D and §VI-E merged into one subsection; the payload-versus-SNR subsection folded into
§VI-B; the remaining figures reduced to $0.8\linewidth$ / $0.42\textwidth$; related work, the
introduction, the headline, generalisation, collaborator-scale, hand-rule and robustness prose
compressed by removing restatement — including one genuine duplicate, the per-split headroom triple
that §VI-A stated twice in the same paragraph.

**One self-inflicted error, caught by the compile gate.** A regex that ended a sentence at the first
`.` cut inside `$B_{\max}=0.20$` and spliced two sentences together; the build failed with a missing
`$`, which is exactly what the gate exists for. Repaired in the same pass.

### 3 · Result: 21 pages, still above the 17-page target

| | pages | LaTeX errors | overfull \hbox |
|---|---|---|---|
| R31 start | 25 | 0 | 9 |
| R31 end | 24 | 0 | 6 |
| **R32 end** | **21** | **0** | **4** |
| supplementary | 3 | 0 | — |

Sixteen gates pass; the compile gate fails on page count alone. The remaining four pages cannot come
from redundancy: at ~6k characters per page the main file now holds ~19 pages of text, and the passes
above returned about 0.15 page per thousand characters rewritten. Closing the gap needs another
**scope decision**, and the honest options are:

* move §VI-H (collaboration harm) and §VI-I (collaborator scale) to the supplementary — ≈ 1.2 pages;
* move the deployment-robustness subsection and its table — ≈ 0.9 pages;
* drop `tab:true_e2e` (validate per-SNR) as its held-out twins already went — ≈ 0.4 pages;
* cut the three sensitivity passages to one paragraph with a combined table — ≈ 0.3 pages (the
  merge item of R32-2, deliberately not done: it is the smallest of the four and the only one
  requiring a rebinding round).

None of these is mine to take: each removes a section from the submitted paper rather than removing
redundancy from it.

---

## Change-log R33 (2026-08-18) — four more subsections to the supplementary; 21 → 20 pages

**Zero GPU.** Relocation, one table deletion, one merge, prose compression. No claim, number or
locked wording changed; every moved subsection is reproduced verbatim in `paper/supplementary.tex`,
and each leaves a 2–4 sentence summary in the main text carrying its headline numbers.

### 1 · What moved and what stayed behind

`§VI-H` (collaboration harm), `§VI-I` (collaborator scale), the deployment-robustness subsection and
its table, and the Where2comm reference subsection are now in the supplementary document (**4 pages,
compiles standalone, zero errors**). The main text keeps, in a new `sec:boundaries`:

* harm — `1.5 / 5.8 / 0.2%` ego-above-fused and `1.3 / 6.5 / 0.9%` delivered-feature-below-ego, plus
  both responses (the `0.999` feasibility mask, and `E` already being a deployed codepoint so the
  remainder is a policy question);
* collaborator scale — `+0.0300` F1 for `+0.1183` Msym at the second collaborator, `+0.0061` for
  `+0.0991` at the third, and the budget not transferring (`0.36842` at `N=3`, already breached at
  `N=2` with `0.26937`);
* robustness — the three perturbation directions and magnitudes (`≤0.0002`, `−0.0025`, `−0.0109`)
  and the `52.1 ± 5.6` ms / `P95 = 58.3` ms latency inside the `100` ms frame interval;
* Where2comm — one reference-only pointer, with the three reasons it is not ranked.

`tab:true_e2e` (validate per-SNR) is deleted, pointing at `true_e2e_ap_by_snr.csv`, and the three
sensitivity analyses are merged into one paragraph plus `tab:sensitivity`. §III-G's rate-distortion
passage is compressed to three sentences with the derivation untouched. The fallback rule was
applied: the two largest figures are at `0.75\linewidth` / `0.75\textwidth`.

### 2 · Gate coverage followed the content, in three places

* **The paragraph-insertion gate** now reads main *plus* supplementary: paragraph 2 of that gate
  **is** the collaboration-harm paragraph, which moved. The move also created an anchor collision —
  the main-text summary opened with the same sentence the gate anchors on, so the extractor grabbed
  the summary and ran to the end of the moved copy. The summary was reworded ("Cooperation can
  hurt"), which is my own connective prose, not a locked claim.
* **The registry gate** already read both files after R32.
* **The literal gate gained a category rather than debt.** The summaries quote `1.5 / 5.8 / 0.2%`,
  which sit below `distinctive()`'s floor and so were never *checked*, though their row names the
  CSV that carries them. `bound_in_own_csv()` verifies exactly those against the file the row names,
  reading `docs/claims.md` **directly** — because `claims_by_section` and the ledger builder disagree
  on some sentence ids (the R26-3 finding), and a check resting on that agreement covers nothing
  silently. The debt register fell from **10 to 4**, all floor effects.

### 3 · Two self-inflicted breakages, both caught by the compile gate

A regex that re-pointed table references produced `\texttt{true\_e2e\_ap\_by\_snr.csv}.csv}` (too
many `}`), and the same substitution swallowed a sentence's verb elsewhere. Both were repaired in the
pass; the build is the only thing that would have caught either.

### 4 · Result

| | main | supplementary | errors | overfull |
|---|---|---|---|---|
| R32 end | 21 | 3 | 0 | 4 |
| **R33 end** | **20** | **4** | **0** | **4** |

Sixteen gates pass; the compile gate still fails on page count alone (20 > 17). The four items of
R33-1 and the two of R33-2 are all done, and the fallback of R33-3 is applied. What remains is
listed at the end of R32: on this template the main file still holds ~18 pages of text, and no
further redundancy is left to remove — the next page has to come from a section, not from wording.

---

## Change-log R34 (2026-08-18) — four more subsections moved; 20 → 18 pages, one over the limit

**Zero GPU.** Relocation only. No claim, number or locked wording changed; every number the abstract
or the Conclusion quotes stayed in the main text.

### 1 · What moved, and what each left behind

`§VI-F` (difficulty stratification), `§VI-C` (decisions and feature importance, **table kept in the
main text**), `§VI-G` (Pareto frontier and its figure) and `§IV`'s selector-training detail are now
in `paper/supplementary.tex` (**6 pages, standalone, zero errors**). The main text keeps a new
`sec:decision_ratio` carrying:

* the hard-tercile gain `+0.0660` F1 (`95%` CI `[+0.0591,+0.0730]`), the monotone shape, and the
  easy-tercile `test` exception (`-0.00471`, `[-0.00742,-0.00236]`, Fixed `L` already at `0.97962`);
* the measured `10` dB policy knee, `rho_E = 0.002` against the oracle's `0.157` under Rayleigh, and
  the `61.7% / 38.3%` importance split with the *importance is not sufficiency* guardrail;
* the frontier statement: the three frozen points lie on the attainable frontier between Fixed `L`
  and the oracle, the fixed feature-level policies far below it;
* a manifest-level training sentence: scene-level `9`-fold LOSO, the frozen walk under the hard
  budget constraint, and `lambda* = 0.05/0.02/0.00` with `tau* = 18/12/8` dB.

Cross-document references were resolved **both ways**: the main text names the supplementary where
its material went, and the supplementary names the main paper for labels that live there.

### 2 · Gate coverage followed, and caught two things

The paragraph-insertion gate (already reading both files after R33) failed on paragraph 2 because
the cross-reference rewrite touched a `\S\ref` *inside* the moved paragraph; that rewrite is now the
declared ruling `R34-xref`, and the doubled article it produced ("the the main paper") is fixed. The
literal gate's debt register is now **empty**: the four remaining floor-effect entries were in the
moved subsections and left with them.

### 3 · Result: 18 pages, one over

| | main | supplementary | errors | overfull |
|---|---|---|---|---|
| R33 end | 20 | 4 | 0 | 4 |
| **R34 end** | **18** | **6** | **0** | **4** |

Sixteen gates pass; the compile gate fails on the page count alone. Two further redundancy cuts were
taken on the way (the Conclusion's recap, and the scene-bootstrap sentence that the R33 sensitivity
merge had duplicated in `sec:headline`) and they did not clear the boundary. Per the batch's own
fallback rule, this stops here for a ruling. What is left, all of it a scope decision:

* `tab:feat_imp` to the supplementary — its two numbers (`61.7 / 38.3%`) are already in the summary
  sentence; ≈ 0.35 page. Explicitly kept in the main text by R34-1b, so it needs your word.
* `tab:ablation` to the supplementary, keeping the FA-1 sentence — ≈ 0.35 page.
* `fig:ap_snr` (the two-panel SNR figure) to the supplementary — ≈ 0.4 page.
* the `sec:true_e2e` verification subsection to the supplementary, keeping its two-sentence result —
  ≈ 0.45 page.

Any one of the last three clears 17 pages on its own.

---

## Change-log R35 (2026-08-18) — the last move: 18 → 17 pages, compile gate green

**Zero GPU.** One table relocated, two duplications removed. No claim, number or locked wording
changed.

### 1 · `tab:ablation` to the supplementary; the FA-1 paragraph stays

The feature-ablation comparison table now lives in `paper/supplementary.tex` under its own heading;
the FA-1 paragraph — the four-rung payload ladder and the four-variant collapse, with the numbers
that are the table's conclusion — is untouched in the main text, which is where the reader meets it.
Three references were re-pointed; none dangles.

### 2 · Two duplications the earlier merges had created, now removed

The table move alone did not clear the boundary (18 pages), so two genuine duplications were cut:

* the fragmentation/HARQ figures were stated **both** in `sec:channel` and in `tab:sensitivity`,
  which R33 created. `sec:channel` now keeps the qualifier and points at the table.
* the channel-model introduction restated the three channel types in a paragraph that the
  following sentences already carried.

Neither removes a claim: every number is still printed once, and the qualifier sentence about the
no-HARQ model is intact.

### 3 · Result

| | main | supplementary | errors | overfull |
|---|---|---|---|---|
| R34 end | 18 | 6 | 0 | 4 |
| **R35 end** | **17** | **7** | **0** | **3** |

**All seventeen gates pass, twice in a row on a clean tree, including the compile gate**
(`0` LaTeX errors, `17` pages at the `17`-page limit). The three remaining overfull boxes are
`125.4`, `17.6` and `115.0` pt — two wide table rows and one long inline expression; they are
recorded in `docs/compile_report.md` and do not fail the build.

### The state of the paper at the end of the batch series

`paper/main.tex` is 17 pages and `paper/supplementary.tex` is 7, both compiling from a toolchain
that needs no root. The supplementary carries, verbatim and by relocation only, the two
prior-protocol appendices, the 21-cue definition table, six results subsections and two tables; the
main text carries a 2–4 sentence summary of each, and every number the abstract or the Conclusion
quotes is in the main text. Nothing was deleted to reach the page limit.

---

## Change-log R36 (2026-08-18) — the figures come back; 18 pages, one over

**Zero GPU.** Every figure is remounted from a file the existing generators already produced; no new
data, no new run. Claims and numbers unchanged.

### 1 · Twelve images across seven floats, back in the main text

Restored from the pre-R31 source and remounted: the qualitative BEV frame, the payload-versus-SNR
panel, the difficulty bars, the feature-importance bars, the two decision-ratio panels and the
stacked-area view, alongside the four that never left (overview, BLER, the two AP-SNR panels, and the
Pareto plane). Grouping follows R36-2: **AP-SNR + payload** in one two-column float,
**decision ratios + stacked area** in another, **difficulty + feature importance** in a third, each
panel at `0.32`--`0.48` of the width; **overview and Pareto stay whole**.

### 2 · Compensation, and where it stopped

`tab:sensitivity` and the generalisation summary table moved to the supplementary
(`tab:ablation` went there in R35), each leaving its conclusion sentence in the main text with the
numbers intact; `tab:headline`, `tab:headline_agg`, `tab:notation` and `tab:feat_imp` stay. Three
prose passages that the remounted captions now duplicate were trimmed to the caption
(payload-versus-SNR, the difficulty stratification, the importance split) — the numbers are printed
once, in the caption.

**Result: 18 pages** (from 17 before the figures returned; the figures cost ~2 pages and the tables
gave back ~1). Per R36-4 this stops here, and **no figure was touched after the count came in**.

### 3 · A gate had to learn what a caption is

Restoring the captions produced five literals the literal gate could not cover: a caption is not a
sentence the claims ledger indexes, so those numbers had no claim row to ride. They are not unbound,
though — `plot_frozen_figs.py` writes every value its figures draw into
`results/provenance/PROVENANCE_figures.json`, a generator-written product. The gate gained a
`figure_caption_literals()` category that accepts a caption number verified in that record, and the
debt register stays **empty**. Sixteen gates pass; the compile gate fails on page count alone.

### 4 · Residual candidates, tables versus text

* `tab:headline_agg` to the supplementary, keeping its two-sentence reading — ≈ 0.45 page;
* `tab:notation` to the supplementary — ≈ 0.3 page;
* `sec:true_e2e`'s verification prose compressed to its two result sentences — ≈ 0.4 page;
* the `sec:candidates` message-candidate discussion compressed ~30% — ≈ 0.35 page.

Any one of the first three clears 17 pages; none touches a figure.

---

## Change-log R37 (2026-08-18) — the notation table moves, the symbols stay; 18 pages

**Zero GPU.** One table relocated with a self-sufficiency check, plus the R37-3 fallback.

### 1 · `tab:notation` to the supplementary, and the main text made self-sufficient

Before moving it, every symbol it defined was checked for a textual definition at first use in the
main text. Four were already defined in place ($E$, $L$, $F$ at Eq.~(action\_set); $B_E$ where the
ego-only action is introduced; $B_L$ and $B_F$ in the payload chain; $C_{256}$ in the message-
candidate discussion). Two things the table alone carried are now written into the action-set
sentence: the **channel-use figures** ($B_E = 0$, $B_L = 0.024$, $B_F = 0.99$, $C_{256} = 0.495$
Msym) and the **identity $F \equiv C_{16}$** with the convention that the $C_q$ form is used only
where modulation order is the subject. The main text is therefore readable without the table, which
is now in the supplementary with a one-line pointer.

**A leftover was found while checking**: the overview figure caption still said "the *dominated*
$C_{256}$ mode" — the last survivor of the family R31-1 withdrew. Corrected to the comparator
wording.

### 2 · The R37-3 fallback was needed

The notation table is only ~0.3 page, so the count stayed at 18 and `sec:candidates` was compressed
~30% as the batch's fallback instructs: the `E`-as-action-and-fallback paragraph, the one-of-many
paragraph and the `C_256` comparator paragraph. Every claim survives — `E`'s two roles and their
different decision times, the one-message design, the exclusion-by-design argument and its
transport-parameter reason. The compression falls inside an insertion-gated paragraph, so it is
declared as ruling `R37-compress`.

### 3 · Result: still 18 pages

| | main | supplementary | errors | overfull |
|---|---|---|---|---|
| R36 end | 18 | 8 | 0 | 2 |
| **R37 end** | **18** | **9** | **0** | **1** |

Sixteen gates pass; the compile gate fails on page count alone, and the overfull count is down to
**one** (the `125.4` pt table row; the other two went with the tables that moved). Everything R37
authorised is done: the table moved, the symbols are in the text, and the fallback was executed.

The arithmetic is now explicit: the twelve restored images cost about two pages, and the four tables
moved out since R35 gave back about one. Holding **both** the ten-figure floor of R36-1 and the
17-page limit needs one of:

* `tab:headline_agg` to the supplementary with its two-sentence reading kept — ≈ 0.45 page, the last
  table that can move without leaving a claim unsupported in the main text;
* `sec:true_e2e`'s verification prose to its two result sentences — ≈ 0.4 page;
* dropping one panel from a paired float (e.g. the stacked-area view, whose content the two
  decision-ratio panels already carry) — ≈ 0.25 page, but that touches a figure, which R36-4
  forbids without your word.

---

## Change-log R38 (2026-08-18) — the verification prose compressed; 18 pages, deficit measured

**Zero GPU.** One subsection compressed to two sentences, its prose relocated verbatim.

### 1 · `sec:true_e2e` reduced to its two result sentences

The main text now says (i) what the true end-to-end AP measurement is and that it is reported
descriptively per budget, read against each split's headroom as in `sec:headline`; and (ii) the
verification conclusion — the analytical replay and the true end-to-end AP agree on the budget
ordering and place the feature-active boundary at the same **measured** `10` dB knee, with the
Rayleigh curve flat at Fixed `L` throughout. `tab:headline` stays in the main text.

Everything removed — the four-step protocol, the per-split `rho_F` plateau values, the `8` dB toe
footnote, the boundary AP values and the `70%` payload saving at the boundary — is reproduced
verbatim in `paper/supplementary.tex` under its own heading. No number left the record, and none of
the removed numbers is quoted by the abstract or the Conclusion.

### 2 · Still 18 pages, and the deficit is now measured rather than guessed

The compression removed 1,751 characters (~0.3 page) and did not tip the count. A probe settled how
much is actually missing: deleting **2,261 characters** anywhere in the body takes the build to
**17 pages** (the probe was reverted immediately; the committed state is the full text). So the
deficit is **under ~2,300 characters, about a third of a page** — smaller than either option R38-3
anticipated:

| option | saving | cost |
|---|---|---|
| ~2.3k characters of prose anywhere (e.g. §I, §VI-A) | ≈ 0.35 page | wording only; no figure, no table, no claim |
| `tab:headline_agg` to the supplementary | ≈ 0.45 page | a headline table leaves the main text |
| drop one panel from a paired float | ≈ 0.25 page | touches a figure (R36-4 forbids without a ruling) |

The first row is strictly cheaper than the two R38-3 named, and needs no figure or headline change;
it is offered rather than taken, because R38 authorised exactly one prose cut and it has been made.

| | main | supplementary | errors | overfull |
|---|---|---|---|---|
| R37 end | 18 | 9 | 0 | 1 |
| **R38 end** | **18** | **10** | **0** | **1** |

Sixteen gates pass; the compile gate fails on page count alone.

---

## Change-log R39 (2026-08-18) — 2.5k characters of redundancy out; 17 pages, all gates green

**Zero GPU.** Wording only: no claim, number, locked sentence, figure or table changed.

### 1 · Where the redundancy was

**Introduction (~700 chars).** The channel paragraph restated the bandwidth paragraph's point about
feature messages needing a reliable link; the method paragraph and the complementarity paragraph
carried connective verbosity. **Related work (~590 chars).** The JSCC paragraph and the
"channel dependence matters for vehicular links" paragraph each restated what the paragraph before
them had established. **§VI-A transitions (~680 chars).** The regime definition repeated the
protocol that `sec:true_e2e` states, the "not designed to raise averaged AP" sentence listed three
cross-references where one suffices, and the qualitative-frame sentence described a figure that is
now mounted beside it — it points at the figure instead.

**A last R31-1 leftover was found on the way**: the introduction still called the 256-QAM mode
"excluded as *dominated*". Corrected to the comparator wording, which makes the fourth and final
site of that family.

### 2 · A gate learned that figures have more than one provenance record

Restoring the qualitative figure surfaced two caption literals (`0.67`, `0.95`) that
`figure_caption_literals()` could not see: it read `PROVENANCE_figures.json`, while the qualitative
generator writes `PROVENANCE_qualitative.json`. Both records are now read. The debt register stays
empty.

### 3 · Result

| | main | supplementary | errors | overfull |
|---|---|---|---|---|
| R38 end | 18 | 10 | 0 | 1 |
| **R39 end** | **17** | **8** | **0** | **1** |

**All seventeen gates pass, twice in a row on a clean tree**, including the compile gate: `0` LaTeX
errors, **17 pages** at the 17-page limit, **1** overfull box (the `125.4` pt row of `tab:headline`,
listed in `docs/compile_report.md`).

### Final state of the batch series

`paper/main.tex`: 17 pages, 12 images across 7 floats, 4 tables.
`paper/supplementary.tex`: 8 pages, standalone, carrying by relocation only the two prior-protocol
appendices, six results subsections, five tables and the full cue list. Every number the abstract or
the Conclusion quotes is in the main text; nothing was deleted to meet the page limit; and the
toolchain (tectonic in its own conda env) needs no root.

---

## Change-log R40 (2026-08-18) — cross-document integrity, C256 claim family, gate coverage over both files

**Zero GPU.** Reference repair, wording, gate expansion, abstract compression. The expansion did
what it was expected to: the supplementary had never been scanned, and it was not clean.

### 1 · Five dangling references repaired as named pointers

`main.tex` pointed at `sec:pareto` and `fig:decision_budgets`, both of which had moved; the
supplementary pointed at `eq:eff_C`, `sec:channel` and `sec:headline`, which live in the main paper.
Now: "the $E$-collapse limitation (supplementary material)", "the three-budget version is provided in
the supplementary material", and "Eq. (4) / Section III-C / Section VI-A of the main paper".
**Zero dangling labels in either document, and the compile gate now proves it.**

### 2 · Three C256 survivals replaced with the supervisor's wording

Two figure captions -> "the non-deployed $C_{256}$ physical-layer comparator"; the method sentence
that compared the two constellations' reliability (implying the selector chooses between them) ->
"The deployed feature action $F \equiv C_{16}$ becomes feasible once its frame-error cliff clears.";
the integration sentence -> "These methods can be integrated into the deployed feature-level branch
$F$, while modulation-order adaptation remains outside the present action space." The **empirical**
statement that Fixed-$C_{256}$ sits below Fixed-$L$ on the payload--F1 plane is a different claim and
is kept.

### 3 · TERMINOLOGY is now meaning-level

Three C256 claim shapes joined `tests/tracked_terms.md`: *dominance* (anchored on C256 as the object
of the verb, so the empirical Pareto statement stays sayable), *reliability comparison implying a
choice*, and *branch activation* ("inside the C16 or C256 branches" puts a non-deployed mode in the
action space). The positive control injects **this batch's own three retired sentences**, verbatim,
alongside R27's sender-side probe; the self-test requires all four to fire.

### 4 · Four gates and the compile gate now read both documents — and found three things

`test_result_consistency` (via the paragraph gate), `test_numeric_literals`,
`test_comparison_direction` and `test_action_set_wording` now cover `paper/supplementary.tex`, and
the compile gate builds **both** files, failing on any LaTeX error, undefined reference/citation, or
a rendered `??`. What the first full run turned up:

* **The Culver block of `tab:gen_headline` was pre-corrigendum.** Its selector and $\tau$ rows
  (`0.87230/0.87491`, `0.87355/0.88340`, `0.88286/0.88740`) match **no committed product**; only the
  fixed rows had ever been generator-owned, and the table had sat unscanned in the supplementary
  since R36. `gen_headline_policy_rows()` now writes those rows from `replay_summary.csv`
  (`0.84667/0.84956`, `0.84975/0.85858`, `0.85932/0.86316`), and the generator refuses to run if a
  row does not match.
* **Ten supplementary literals were unbound**, because that document cited no products. It now
  names the twenty-one products its numbers come from, and the echo rule verifies them there.
* **A false-positive in my own new check**: grepping the PDF *byte stream* for `??` fired on both
  files (arbitrary bytes contain `??`). It reads the **rendered text** via `pypdf` instead.

### 5 · Audit and history

Regenerating `docs/claims_evidence_audit.md` dropped the C256 dominance rows with the sentences they
described. R30-3's set-domination entry is now headed **SUPERSEDED BY R31-1**, so the change-log
reads forward correctly.

### 6 · Abstract: 653 -> 270 words, and why not 250

Redundant clauses are gone and every number is kept: the budget set, the headroom triple, the
converted share, the channel-use range, both saving tracks with the over-budget label, the secondary
`+0.00067`/`26.6%` without a non-inferiority decision, the importance split and the latency. A
251-word version existed briefly and is **not** what was committed: it had silently dropped the claim
that a threshold and a three-scalar hand rule reach comparable F1 at higher payload, which R40-6
forbids. Restoring that claim costs 19 words. **270 is the floor with every claim and number intact**;
250 is reachable only by dropping one of them, which is a ruling, not an edit.

### 7 · State

Seventeen gates pass, twice, on a clean tree. Main 17 pages / 1 overfull; supplementary 8 pages /
7 overfull (its wide moved tables, recorded in `docs/compile_report.md`).

## R41 — abstract to 246 words, six prose compressions, two floats relocated

### 1 · Abstract: 270 -> 246 rendered words

R40 recorded 270 as "the floor with every claim and number intact"; R41 ruled that the headroom
triple (`0.0550/0.0240/0.0970`) and the importance split (`61.7%`/`38.3%`) move to the body, which is
what made 250 reachable. Both landed: the triple stays in the Conclusion, and the split is restated in
`sec:ablation` with the per-cue ceiling ("none above 3.0% alone"). Everything else the abstract
carried is still there — budget set, converted share, channel-use range, both saving tracks with the
over-budget label, the secondary `+0.00067`/`26.6%` without a non-inferiority decision, the
comparable-F1-at-higher-payload claim (R40-6) and the latency. Count is measured on the RENDERED page
(pypdf, `Abstract`..`Index Terms`), not on the source: the source-token count read 248 while the
rendered one read 262, and the rendered count is the one a desk editor applies.

### 2 · Six prose compressions

`sec:where_gain` (VI-A) -1244 chars, `sec:intro` -774, `sec:threshold` (VI-J) -2081 — that last one
was mostly internal duplication: the R9 claim and the `0.89701/0.89900`, `34.8%`, `26.6%`,
`1.53x/1.47x` figures were each stated twice inside the same subsection. Then `sec:ap_snr` (VI-B)
-662, `sec:candidates` -437, Conclusion -220. Total ~5.4k chars, no claim and no number removed.

**Where the -30% target on `sec:candidates` stopped**: its C256 paragraph is paragraph #1 of the
insertion gate, whose `start_anchor` is "Of the two feature-level modes, the 256-QAM variant". A
112-char rewrite of it broke the gate; it was REVERTED rather than registered as a ruling, because a
cosmetic rewrite is not worth an entry in a paragraph's authorised-rewrite chain. The section reached
-437 chars (~10%), not -30%.

### 3 · Relocation

`fig:difficulty` (804 chars) and `tab:feat_imp` (946) moved to `paper/supplementary.tex` under
"Figure and table moved from the main paper (R41)". Main is now **10 images**; per R36-4 no figure was
touched otherwise. `tab:headline_agg` stays in the main paper (R41-3).

### 4 · Registry maintenance forced by the rewrites

Three direction-gate probes drifted with their sentences and were re-pointed in
`tests/comparison_claims.md` (claim, direction and cell unchanged in all three):
`attains the marginally higher realised F1 at \emph{every} budget` -> `... higher F1 at ...`;
`ahead by $+0.00067$ at $B_{\max}=0.20$` -> `ahead by $+0.00067$ at $0.20$`;
`but send more feature messages` -> `sending more feature messages, so the cues buy` (the abstract
probe, still inside the abstract span). `docs/claims.md` was regenerated twice and rebound: 18 rows by
number-set match, 3 by claim-similarity, 3 mechanically by `backfill_claims_evidence.py`, 2 by hand
(the framework-definitional row and the confirmatory-cell lead-in), 4 more after the abstract edits.
The abstract's `tau_feasible` row was bound to `replay_summary.csv` alone, which is where its
`+0.00067`/`26.6%` are NOT — `p6_numbers_vs_csv` reported them as MISS; the binding now names
`tau_feasible.csv` as well and the MISS count is 0.

### 5 · Page count: 16, target was 14 — GAP REPORTED

Main is **16 pages** (was 17 at R40; 25 at R31). Body text ends on page 15; page 16 is the tail of the
bibliography. The six compressions removed ~5.4k characters, about one page of text, and the count
moved 17 -> 16. The remaining 2 pages are NOT available in prose: the pages are float-dominated (10
figures + 6 tables across 15 body pages, at ~850-1050 words/page), and every prose compression in this
batch stopped on a claim sentence. The reserve named in R41 — moving `tab:headline_agg` — has NOT been
touched: it needs a further ruling.

### 6 · State

Sixteen gates pass, twice, on a clean tree; `p6_cross_section_scan` 0 conflicts in all four classes;
`p6_numbers_vs_csv` 0 MISS, 0 UNLOCATED table cells. Main 16 pages / 1 overfull; supplementary 9 pages.

## R42 — headline table relocated, float geometry, citation audit (16 -> 15 pages)

Zero GPU. Executed in the given order, recompiling after each step; the batch's stop rule was "stop
at 14 pages", which was not reached.

### 1 · `tab:headline_agg` to the supplementary, two reading sentences kept

The table moved to `sec:moved_r42`; the main paper keeps its reading inline: the three frozen
operating points (F1 `0.89148`/`0.89691`/`0.89783` at `0.0368`/`0.1414`/`0.2120`~Msym, each against
the threshold tuned to its own budget, `tau*=18/12/8`, at `0.0724`/`0.2168`/`0.3125`~Msym) and the
fixed-reference ordering (Fixed L `0.89095`@`0.024`, oracle `0.90559`@`0.17502`, Fixed F
`0.84827`@`0.99`, Fixed C256 `0.82553`@`0.495`). The prose quotes the CSV's own 5-dp values, not the
table's 4-dp rounding, so the literals bind to `fixed_references.csv` directly instead of relying on
the derived-cell declaration. **16 -> 16 pages** (the freed space was absorbed by float placement).

Two silent-failure faults surfaced here and are fixed:

* `tools/build_paper_tables.py` spliced `tab:headline_agg` into `main.tex` unconditionally; after the
  move it would have written nothing. It now splices wherever the label lives (the rule
  `tab:ablation` has had since R40), and raises through `splice()` if the label is in neither file.
* R41's `sec:where_gain` compression had rewritten "(iii) Channel-averaged, the selector spends" to
  "(iii) Channel-averaged it spends", which silently unhooked `observation_iii()`'s `sub_once()`
  pattern — the generator matched 0 times. Detected only because this batch re-ran the generator.
  The generator-owned phrase is restored; **no gate covers "a generator whose pattern stopped
  matching" until the generator is run**, which is worth a future gate.
* `p6_numbers_vs_csv`'s table-cell scan read `main.tex` only, so the move took 17 cells out of
  coverage (29 located -> 12). It now reads both documents: **150 located, 0 UNLOCATED**.

### 2 · Float geometry (no figure removed, count stays 10)

Preamble block, IEEEtran-safe: `\abovecaptionskip` 3pt, `\belowcaptionskip` 0pt,
`\textfloatsep`/`\floatsep`/`\intextsep`/`\dbltextfloatsep`/`\dblfloatsep` 6pt plus 2pt minus 2pt,
`\arraystretch` 0.95. The two single-column figures were already at `0.75\linewidth` (R33);
`fig_pareto_test` was the one at full `\linewidth` and is now `0.85\linewidth`. **16 -> 15 pages.**

### 3 · Citation audit: 25 -> 16 distinct keys in the main paper

Deleted (each cited exactly once, in an enumeration no argument depends on): `han2023collaborative`,
`wang2020v2vnet`, `li2021disconet`, `xu2022cobevt`, `liu2020when2com`, `lu2024heal`,
`hu2024pragmatic`, `xie2021deepsc`, `gunduz2023beyond` — 9 keys. Kept for cause: `hu2022where2comm`
and `sheng2024importance` (compared arms), `gan2026scomcp` and `gan2025cods` (the digital-domain
paragraph, gate-protected), `xie2022mlcooper` (closest rival), `zhang2024smartcooper` / `accbev2025`
(the fixed-granularity channel-adaptive contrast), `liu2024rbh` (the three-way positioning),
`yuan2025multimode` (different-axis contrast), `bourtsoulatze2019deepjscc` (JSCC anchor for the
graceful-codec half), `breiman2001random`, `xu2022opv2v`, `xu2022v2xvit`, `lang2019pointpillars`,
`ieee80211bd`, `3gpp37885`. **15 -> 15 pages**; the saving is inside the bibliography column.

### 4 · Page count: 15, target 14 — GAP REPORTED, remaining scope not taken

Body ends on page 15, which is ~80% full (804 extracted words against a 850-1050 typical page). The
residual is **about 0.9 page**. Nothing further was cut: the batch's own rule was to stop and wait
for a scope ruling. What is left costs a claim or a figure — the untouched levers are (a) the
`sec:ablation` collapse paragraph, which restates the four-rung ladder already given in
`sec:handrule`, (b) `sec:threshold`'s closing italic summary, which repeats the abstract, and (c)
dropping a figure, which R36-4 forbids without a ruling.

### 5 · State

Sixteen gates pass, twice; `p6_cross_section_scan` 0 conflicts; `p6_numbers_vs_csv` 0 MISS, 0
UNLOCATED over both documents. Main **15 pages, 1 overfull (17.6pt)**; supplementary 9 pages, 7
overfull. Abstract **246 rendered words**.

## R43 — single-statement de-duplication, second geometry pass, generator gate (15 pages, 14 not reached)

Zero GPU.

### 1 · The payload ladder is stated once

Full mechanism stays in `sec:ablation`, where the collapse family lives. `sec:handrule`'s restatement
("This is the four-rung ladder ... $0.10$ and $0.20$ fall between rungs") becomes a pointer: "The same
payload-ladder mechanism (Section~\ref{sec:ablation}) explains why the two-scalar rule cannot price
intermediate budgets." The claim keeps one full home and one pointer; it never drops to zero.

### 2 · `sec:threshold`'s closing italic summary deleted

It restated the abstract almost sentence for sentence (`\method{} does not win by raising average
F1 ...`). The subsection now ends on its last factual sentence, that channel-side importance is not
channel-side sufficiency. The direction-gate probe `a three-scalar hand rule reach comparable F1`
survives because its first occurrence — the one `tex.find` resolves — is in the abstract.

### 3 · Second geometry pass (figure count still 10)

`fig_qualitative_bev` `0.9` -> `0.78\textwidth`, `fig_pareto_test` `0.85` -> `0.80\linewidth`, and the
six subfigure panels `0.32` -> `0.31\textwidth`. NOTE: the batch specified "qualitative BEV
0.75->0.65"; the figure was at `0.9\textwidth` (a `figure*`), not 0.75, so the same ratio (x0.867)
was applied to its actual width. **15 -> 15 pages**; the pass bought vertical slack, not a page.

### 4 · New gate: `generators --check` (17 gates)

`tests/test_generators_check.py` runs every generator that owns delivered text in `--check` mode.
`build_paper_tables.py --check` used to print two table bodies and return BEFORE any `splice()` or
`sub_once()` ran, so the one fault those helpers exist to catch — a pattern that no longer matches the
delivered text — was invisible until the generator was next run for real. That is exactly how R41's
compression of observation (iii) went unnoticed for a batch (found in R42). The generator is now
factored into `transform()` (in-memory, both documents plus `DERIVED_TABLE_CELLS.json`), and `--check`
fails if any pattern misses or if the delivered artefact differs from the generated one. Registered:
`build_paper_tables`, `build_r9_claims`, `build_readme_tables`, `claims_ledger`. The self-test injects
the R41 fault into `main.tex`, requires the gate to fire, and restores the file byte-for-byte in
`finally`.

### 5 · Limited de-duplication round (after 1–3 still 15 pages)

Only pairs where the same claim was stated twice in full were touched, each keeping one full statement
plus a pointer:

* the R9 confirmatory claim — full statement kept in `sec:threshold` (with intervals and both payload
  tracks), `sec:headline` reduced to the verdict plus a pointer;
* the channel-only collapse at $B_{\max}=0.30$ — full statement kept in `sec:ablation`,
  `sec:threshold`'s restatement of `0.89529`/`0.89783`/`1.36x` reduced to "beaten on both axes
  (Section~\ref{sec:ablation})".

Saving: 100 characters. **Still 15 pages.**

### 6 · Page count: 15, 14 not reached — the remaining lever is the figure floor

Body text now ends early on page 15; the rest of that page is the bibliography (695 extracted words on
the page, of which the reference list is the bulk). Reaching 14 needs roughly a full page of content
out, and after R42's citation audit and this batch's de-duplication the only remaining lever is the
figure count, which R36-4 reserves for Josh. Not taken.

### 7 · State

Seventeen gates pass, twice; `p6_cross_section_scan` 0 conflicts; `p6_numbers_vs_csv` 0 MISS, 150 table
cells located over both documents, 0 UNLOCATED. Main **15 pages, 1 overfull (17.6pt)**; supplementary
9 pages, 7 overfull. Abstract **246 rendered words**.

## R44 — E defined by what it withholds, CAM scope, generator/figure gate registration

Zero GPU; text, documentation and gate registration only. No figure was touched and no page-count
lever was pulled.

### 1 · The "no request" family is retired

The supervisor's objection is structural, not stylistic: the ego sends the $E$ control codepoint on
every frame, so describing $E$ as "no request at all" contradicts the $2$-bit signalling the same
section defines. What $E$ withholds is the **cooperative perception payload**. Six sites changed
(overview caption, `sec:intro` contribution, `sec:system` mode list, the codepoint sentence,
`sec:candidates` definition and the Conclusion) plus one in the supplementary. The definition
sentence is now the supervisor's: *the ego sends the $E$ control codepoint, and the collaborator
transmits no cooperative perception payload.*

Self-consistency with the $2$-bit/$20$~bps accounting is now stated rather than left implicit: "The
codepoint is sent on every frame, including when the ego selects $E$, so the $20$~bps signalling cost
does not depend on the mode chosen; what $E$ removes is the cooperative perception payload, not the
request." $B_E=0$ therefore refers to the perception payload, which is what the payload model charges.

Two of the six sites sit inside insertion-gate paragraphs (#2 in the supplementary, #3 in related
work), so the change is registered as ruling **R44-1** in both. The first attempt placed the
paragraph-2 ruling BEFORE `P5-7-10`, whose replacement text is what introduces the clause being
rewritten; the gate reported "source not found in draft", which is what a wrong ORDER looks like.
Rulings apply in sequence: a ruling's source is the draft as the earlier rulings left it.

### 2 · CAM claim downgraded, ETSI references added

"piggy-backed on the existing Cooperative Awareness Message (CAM) ... already provisioned in the
standard CAM signalling budget" asserted a standards fact the paper does not establish. It now reads
as an **application-layer extension associated with** the ETSI CAM~(EN 302 637-2) and CPM~(TS 103 324)
services, with standards integration explicitly outside scope. Both references added to `refs.bib`;
the two "CAM-embedded request" mentions elsewhere are now plain "$2$-bit request".

### 3 · The Conclusion's `near-sufficient statistic` sentence is replaced

Replaced by the two-axis reading: the channel state settles which frames a feature message can reach
at all, the task cues settle which of those frames are worth spending on, which is why the cues move
channel use rather than average F1 here. The abstract's "neither half of the input suffices alone" is
untouched.

### 4 · `check_figure_consistency.py --check`, registered

The tool reported and decided nothing, which is right for the one-sided and different-condition rows
(those are readings). "Drawn but never stated" is not a reading: a figure shows a number no caption
and no sentence states. `--check` now fails on exactly two things — a non-empty never-stated set, and
a stale `docs/figure_text_consistency.md` — and is registered in `tests/test_generators_check.py`.

The three never-stated rows are **disposed of individually**, none silently:

| row | value | disposition |
|---|---|---|
| `payload_catosg_awgn_low` | 0.0237 | the caption stated it, but inside a clause pinned to the $10$~dB knee while the value is drawn at $0$~dB. Caption split so the value carries its own condition ("$0.0237$~Msym/frame at $0$~dB"). |
| `payload_catosg_awgn_at_knee` | 0.4795 | same sentence ended "...and holds $L$ throughout under Rayleigh", so the only channel named in the window was Rayleigh and the AWGN-drawn value read as a condition conflict. Split into its own AWGN sentence. |
| `rho_E_catosg_rayleigh_test` | 0.0018 | the caption rounded it to $0.002$, which the checker refuses (a two-significant-digit literal is collision-prone). Caption now quotes the drawn value $0.0018$. |

Result: **0 drawn-but-never-stated**, and the one remaining different-condition row
(`rho_E_oracle_rayleigh_test`) is matched on the body side and recorded in the report.

### 5–6 · `HANDOFF.md` and `reproducibility.md` rewritten

`HANDOFF.md` now opens on the current state (17 gates, 98 claims all bound, 150+4 table cells over
both documents, 0 LEGACY, 15 pages, abstract 248 words), the four gates worth knowing before editing,
and three open items that are all Josh's call — page count (figure floor), R21-B Where2comm rerun
(never executed, awaiting cost approval), and his own figure/bib passes. Everything previous is under
"History (superseded)" with an explicit do-not-quote banner.

`reproducibility.md` now leads with the six-step current chain (grids → freeze → replay → verification
arms → regenerate → verify+compile), each step naming the command that writes the product, plus the
seeds and the two verification tiers. The v3 global-sort pipeline, its table/figure map and its
"compile on Overleaf" instruction are all under "Legacy (v3 engine, superseded)".

### 7 · Compile gate is no longer host-specific

`TECTONIC` was a hard-coded path into one machine's conda env. Resolution order is now
`$TECTONIC_BIN` → `shutil.which('tectonic')` → the local env, and the failure message says how to
override. A gate only one host can run is a gate the next person deletes.

### 8 · Abstract latency sentence

"Inference: $52.1$~ms/frame, one CPU core." → "Selector-only inference: $52.1$~ms/frame on one CPU
core." — the measured quantity is the selector, not the end-to-end chain, and the abstract now says
so. **248 rendered words**, still inside the 250 limit.

### 9 · State

Seventeen gates pass, twice, over both documents; `p6_cross_section_scan` 0/0/0/0;
`p6_numbers_vs_csv` 0 MISS, 150 located + 4 declared-derived, 0 UNLOCATED; figure gate 0
never-stated. Main **15 pages, 1 overfull (17.6pt)**; supplementary 9 pages. Page count unchanged by
design: this batch pulled no page lever.

## R45 — the payload anchor is a convention, Where2comm is not a baseline, and the record is now gated

Zero GPU; wording, documentation and two gates. No experiment was re-run.

### 1 · Payload anchor: declared convention, and the deployed counts stated as such

The paper claimed "the conclusions are insensitive to this constant" and that re-anchoring "would
rescale the feature cost of all policies equally". P4-B-d measured both and recorded them as **false
as written**: a deployed policy pays `ρ_L·B_L + ρ_F·B_F` and `B_L` is anchored independently, so only
the feature term rescales, and the headline channel-use fraction moves by −0.90 % to −7.75 % under
the paper's own 1.98 → 2.16 Mbit counterfactual and by −4.86 % to −41.99 % under the
declared→deployed re-anchor. That measurement sat in the record for four batches while the paper
asserted its negation.

`sec:exp` now states the supervisor's framing: the feature-level source budget is a **declared
source-budget convention**, every feature-level payload is **conditional on that anchor**, and
re-anchoring **changes the absolute and the relative payload values** while the **policy ordering is
unchanged over the anchors recorded** in `payload_anchor_sensitivity.csv`.

The deployed counts are now in the paper, as measurement and explicitly not as the anchor: a dummy
forward through `pointpillar_attentive_fusion_compression` counts **3,942,400** pre-compression
elements per collaborator across three branches, of which **739,200** go on the wire as autoencoder
bottlenecks (`results/manifests/P4B_PROBE_pointpillar_compression.json`,
`results/channel/payload_conventions.csv`). Neither is the declared anchor, and the paper says so
rather than reconciling them silently. The implication that the $2.16\times10^{6}$-element tensor is
what the deployed model transmits is gone.

### 2 · Channel-type misclassification: the arm existed, the paper did not report it

Checked as instructed rather than assumed. The experiment **exists** —
`results/sensitivity/channel_misclassification.csv`, P3 sensitivity arm, flip rates 0/5/10/20 % over
all three splits — but **neither delivered document reported it**: the supplementary's robustness
paragraph listed three imperfections (noisy SNR, CSI aging, stale request) and not this one. So both
halves of the instruction applied: the qualifier is now in the main text with one measured
degradation and a pointer, and the arm itself is written up in the supplementary.

Main text (`sec:cues`): both channel inputs are treated as estimates and the results are conditional
on their availability; flipping $c_t$ on 10 % of frames moves realised F1 to **0.89542** from that
arm's **0.89701** no-flip baseline (test, `B_max` = 0.20), payload unchanged. The supplementary adds
the full ladder (0.89701 / 0.89620 / 0.89542 / 0.89384 at 0/5/10/20 %) with the mechanism — a
wrongly-Rayleigh frame falls back to `L`, a wrongly-AWGN frame is caught by the feasibility mask —
and the standing warning that the arm's no-flip cell is **not** the mainline replay's.

### 3 · The latency family

**Selector-only latency** is what this work measures. Every "fits within the 100 ms budget" form is
gone from both documents. The supervisor's sentence — *Selector-only latency is 52.1 ms; end-to-end
system latency is not measured here.* — is stated **once** in `sec:selector` (main) and once in the
supplementary; the other three sites now point at it rather than repeat it, because three verbatim
copies collide in the claims ledger (identical claim text ⇒ identical stable ID, which the ledger
refuses — the collision is how the duplication was caught).

### 4 · Where2comm is an adjacent-technology reference

Not a baseline, in any sentence, in either document. The supplementary subsection is retitled and
opens by saying so. The main-text pointer no longer calls it a comparison. Tracked as a TERMINOLOGY
family with a negative-lookbehind pattern so the disclaimers themselves ("not a baseline", "is not
ranked") do not trip it, and the retired form is a self-test probe.

### 5 · Three documentation defects

* **The handoff's commit field is now generated** (`tools/build_handoff_header.py`). A hand-typed
  hash is wrong one commit after it is written. `--check` does *not* demand equality with `HEAD` —
  that fails on every commit and is how the previous convention died — it demands that the recorded
  commit be an **ancestor** of `HEAD`, which fails exactly when the file describes a state the branch
  has left. Registered in the generator gate.
* **"No experiment is mid-flight" vs "Where2comm never executed"** is closed by Josh's decision, and
  the handoff now says which: the budget-matched rerun is **closed by decision, archived for
  revision** — scoped, costed, deliberately not run, and nothing in the paper depends on it.
* **`docs/reproducibility.md`'s tier counts were wrong** ("7 of 9"). Content tier is **9 of 17**, the
  other 8 are reported as skipped, and the two-tier claim is now stated plainly: this repository can
  establish that *the committed results are internally consistent and the documents still say what
  those results say*; independent reproduction from raw OPV2V additionally needs `data/p2`, the
  frozen models and the sibling OpenCOOD checkout, **none of which is in this repository**.

### 6 · Gate 18 — paper ↔ protocol reconciliation

`tests/test_protocol_reconciliation.py` + `tests/protocol_claims.md`. Each row pairs a verdict
recorded here (`false-as-written` or `superseded`) with a retired form that must match nothing in
either delivered document and a replacement claim that must appear. The anchor phrase must still
exist in this file, so a row cannot pass by having its record deleted. Four pairs registered: the
payload-anchor insensitivity claim, the Where2comm-as-baseline framing, the C256 set-domination
argument (superseded by R31-1) and the 100 ms latency budget. The self-test injects each retired form
and requires the gate to fire, and injects a deleted anchor and requires the same.

Two faults the self-test caught in the gate's own first draft: the row parser left the markdown
backticks inside every pattern, making all four unmatchable (a gate that cannot fail), and the
injected-fault check counted a stale-anchor failure as the injection firing.

### 7 · A dead positive control, repaired

`p6_cross_section_scan.py --self-test`'s ENTITY-VALUE control had been silently dead: it injected
`max(vals) + 0.5` against `records[0]`, whose own values span 0.0007 to 0.2168, so the injected value
failed the `_same_scale` guard and no conflict was ever raised. A control that depends on which
record happens to sort first is not a control. It now selects a record whose values sit within one
octave and injects a disjoint value on the same scale, and says so loudly if no such record exists.

### 8 · State

Eighteen gates pass, twice, over both documents; `p6_cross_section_scan --self-test` **PASS** (all
four controls fire) with 0/0/0/0 live; `p6_numbers_vs_csv` 0 MISS, 0 UNLOCATED; figure gate 0
never-stated. Main **15 pages, 1 overfull**; supplementary 9 pages; abstract 248 words. No page lever
pulled.

## R46 — reference geometry vs deployed tensor, branch weights, and a paper-vs-code discipline

Zero GPU; wording, documentation, one new discipline and two new reconciliation pairs. No experiment
was re-run.

### 1 · The reference geometry is not the deployed tensor

`sec:exp` now opens the budget derivation with the supervisor's framing: *To define a common
source-budget convention, we use a reference BEV geometry of $256\times48\times176$ …* and, in the
same paragraph, **This reference geometry is not the transmitted tensor of the deployed PointPillar
checkpoint.** The preceding sentence, which called that tensor "the transmitted BEV feature tensor",
is gone — it asserted a measurement that the probe contradicts (3,942,400 pre-compression /
739,200 transmitted per CAV).

The detection range printed in *Dataset and Implementation* was the reference geometry's
($y \in [-38.4, 38.4]$), not the deployed checkpoint's. It now reads $y \in [-40, 40]$, which is what
`pointpillar_attentive_fusion_compression`'s config carries. `y \in [-38.4, 38.4]` is a retired
fingerprint, anchored on the range form so the reference tensor's own arithmetic ($76.8 = 2\times38.4$)
is not caught.

### 2 · The branches do NOT share weights

Retired: "All methods share the same backbone and detection head to ensure a fair comparison." The
late-fusion checkpoint behind $L$ and the attentive-compression checkpoint behind $F$ are **separate
trainings** of PointPillar-based OpenCOOD models. The paper now says so, and says what follows: their
clean-channel performance difference **reflects the complete pipeline of each branch — training,
fusion and codec — rather than the semantic granularity in isolation**, and every $L$ versus $F$
comparison is to be read that way.

Tracked as a TERMINOLOGY family (`shared-backbone claim`) with the retired sentence as a self-test
probe, and registered as a reconciliation pair (§6 below).

**Pre-registered, not run:** a *unified three-branch construction* — one backbone and detection head
trained once, with the object-level, feature-level and ego-only branches derived from it — which is
the only construction that would license attributing the $L$–$F$ gap to granularity alone. Cost:
retraining the shared model plus re-deriving every cached per-frame outcome, i.e. the whole grid
rebuild. Not started; nothing in the current paper depends on it, because the claims it would support
have been withdrawn rather than kept.

### 3 · The $c_t$ mechanism sentence, verified against the source

R45's mechanism sentence was **wrong as written**: it said a wrongly-AWGN frame "is caught by the
feasibility mask". Reading `projects/ca_tosg/evaluation/sensitivity.py`, that is not what the arm
does. `replay()` flips only the selector's `channel_is_rayleigh` feature; the frame BLER is computed
on the **true** channel (`bF = bler16(tbl, snr, is_ray_2d)`), and `eff_matrix_blerL` mixes
`comp·(1−bF) + ego·bF` — so a feature request that the true channel drops falls back to **ego-only**,
not to $L$, and no mask is involved in this path. The supplementary now states the asymmetry the code
implements: misread-Rayleigh biases towards the conservative $L$ (safe, forgoes a gain);
misread-AWGN may request $F$, which is then likely lost on the true channel and falls back to the
ego-only output. "Payload unchanged" became "payload remains nearly unchanged" with all four values
(0.14036 / 0.14033 / 0.14032 / 0.14051 Msym).

**New discipline — paper-vs-code.** A sentence that explains a *mechanism* must be verified against
the source that implements it before it is written, and the verification named in the change-log.
This sits beside the R45-6 paper-vs-protocol gate: that one blocks a claim the record has retired;
this one blocks a claim the code never implemented. Three mechanism sentences have now been wrong at
least once (the E "no request" family in R44, the four-rung ladder's original framing, and this one),
and in each case the source settled it in minutes.

### 4 · Gate counts are computed, not typed

`tools/build_gate_counts.py` writes the counts into `docs/reproducibility.md` (the two-tier block and
the six-step table's last row) and into `verify_results.py`'s usage line, from the runner itself.
Current: **10 content-tier of 18**. Note the count that made this necessary — `len(GATES)` is 17,
because `stale-fingerprint exit` is run inline by `__main__` and printed like the rest; counting the
list rather than the runner is exactly the error the hand-written numbers kept making. Registered in
the generator gate.

### 5 · Introduction

"approaches oracle performance" → "**recovers part of the available oracle headroom** when the channel
supports richer communication", which is what the headroom table shows (at most about a fifth).

### 6 · Two more reconciliation pairs

`reference-tensor` and `shared-backbone`, both `false-as-written`, with the retired forms as
injected self-test faults. The gate now carries six pairs.

### 7 · State

Eighteen gates pass, twice, over both documents; all four `p6_cross_section_scan` controls fire;
`p6_numbers_vs_csv` 0 MISS, 0 UNLOCATED; figure gate 0 never-stated. Main 15 pages, supplementary 9;
abstract 248 words. No page lever pulled.

## R47 — deployment cost of two branches, three payload conventions, and the ordering claim re-verified

Zero GPU. One computation: the anchor counterfactual re-run on CPU from the frozen decision logs and
the committed probe, with a third convention added. Pre-registered outcome: **the ordering claim may
change under the bottleneck convention, and if it does the sentence changes with the data.** It did
not — reported below with the check that establishes it.

### 1 · The deployment cost of not sharing weights

R46 recorded that the $L$ and $F$ branches are separate trainings. The consequence for deployment was
not stated, and it is not free: *Because the two branches do not share weights, per-frame branch
switching implies either keeping both perception pipelines resident or swapping models between
frames; the reported 52.1 ms covers the selector only, not this dual-branch overhead.* The
pre-registered unified three-branch construction is now also named as the fix for this cost — one
resident model would serve all three actions.

### 2 · Three payload conventions, and what the recomputation showed

`payload_anchor_sensitivity.csv` carried one deployed-side convention under the ambiguous label
`deployed_tensor`. It is renamed **`deployed_precompression_tensor`** (1.8047 Msym), and the
convention that describes what actually goes on the wire — **`transmitted_bottleneck`**, 739,200
elements, **0.3384 Msym** — is added, computed through the identical mechanism (frozen action mix,
$\rho_L B_L + \rho_F B_F$, no new replay). The paper's old named counterfactual is kept as
`reanchor_1bit_per_element`.

**A generator was broken and this found it.** The tool parsed `re-anchoring to $2.16$~Mbit` out of
`main.tex` to get its counterfactual. R45 retired that sentence, so the parse returned `None` and the
script crashed on the next run — a generator coupled to prose the paper no longer contains. The
counterfactual is now derived from the reference geometry (one bit per element), which is what
2.16 Mbit always meant.

**The recomputation, on test:** the selector's share of Fixed $F$ is $3.5$–$20.7\%$ under the declared
anchor, $2.4$–$19.8\%$ under the pre-compression count and $8.1$–$24.5\%$ under the transmitted
bottleneck. The bottleneck convention moves the fraction by $+17.6\%$ to $+192.6\%$ relative to the
declared anchor — the largest movement of any convention, and in the opposite direction, because it
shrinks $B_F$ while $B_L$ stays fixed.

**The ordering claim, re-verified rather than re-asserted.** Across all four anchors and every
split/budget cell: the selector spends at least $B_L$, strictly less than $B_F$, and more at a looser
budget than at a tighter one. The claim survives, and now survives *because it was checked under the
new convention*, not because the old sentence was carried forward. The paper states the three
conventions side by side, adds that **both $B_{\max}$ and $\lambda$ are conditional on the
convention** (they are stated in channel uses), and quotes the three share ranges.

### 3 · "Shared PointPillars backbone" disambiguated

Two sentences still said "a shared PointPillars backbone", which after R46 reads as contradicting
"the branches do not share weights". Both now say what is shared with what: the backbone is shared
**between ego and collaborator within each branch, but not between the $L$ and $F$ branches**.

### 4 · The Rayleigh infeasibility statements are conditioned

Both sites now read "under the evaluated retransmission and all-or-nothing delivery settings, the
deep-fade frame BLER never falls low enough …". The statement is about this transport configuration,
not about Rayleigh channels in general.

### 5 · A fourth stale hand-written count

`verify_results.py`'s module docstring said "Nine checks: the five original gates, …". It is now a
generated line (`GATE-COUNT-LINE: 18 checks in total, 10 of which a clean clone can run.`) under
`tools/build_gate_counts.py`, like the other three counts. Fourth occurrence of this failure mode,
same fix.

### 6 · A seventh fingerprint collision

`24.5%` was a retired feature-importance share and is now also a LIVE value — the upper end of the
transmitted-bottleneck share range, $8.1$–$24.5\%$. The bare-number pattern fired on the new sentence.
Re-anchored on the retired quantity's own context (`24.5\% of importance` / `importance … 24.5\%`),
which is the same correction the six earlier collisions needed: a bare number is not a fingerprint.

### 7 · State

Eighteen gates pass, twice, over both documents; `p6_numbers_vs_csv` 0 MISS, 0 UNLOCATED; figure gate
0 never-stated; reconciliation gate 6 pairs. Main is **16 pages** (was 15): this batch adds the
dual-branch limitation, the three-convention paragraph and two qualifiers, all of which are content
the batch required. Supplementary 9 pages; abstract 248 words.

## R48 — evidence grade of the bottleneck convention, four-convention ratios, and a check for the anchor product

Zero GPU. No experiment re-run; one product re-derived cell by cell as a new gate entry.

### 1 · What the bottleneck number is, and is not

"$739{,}200$ elements actually placed on the wire" claimed more than the probe supports. The probe
counts what the encoder hands to the cooperative fusion stage; it does not observe a wire. The paper
now says **bottleneck elements passed from the encoder to the cooperative fusion stage**, and calls
the 0.3384 Msym figure what it is: **a counterfactual payload obtained by applying the declared
0.9155-bit-per-element convention to the measured bottleneck size**. Added in the same paragraph: a
real deployed payload would require a specified quantisation width, entropy coder and packetisation,
none of which is fixed in this work.

### 2 · The scope of the sensitivity analysis, stated in the paper

*This is a payload-accounting sensitivity analysis with the frozen action mix and the original BLER
model held unchanged.* Made explicit alongside it: the bottleneck convention does **not** re-derive
the codeword count ($N_{\mathrm{cw}} = 3{,}960$ declared against ${\approx}1{,}354$ bottleneck), the
frame BLER or $\lambda$, and no selector is re-frozen under it. The three conventions are not a
complete system re-verification, and the paper no longer lets a reader infer that they are.

### 3 · One ratio was an unstated accounting choice

"${\approx}82\times$ the object-level payload" is the **source** ratio, while the rest of the paper
spends channel uses, where the declared ratio is $41.25\times$. With three deployed-side conventions
in play a single ratio is a fact about an unstated choice, not about the system. The sentence is now
generated by `build_paper_tables.feature_object_ratios()` from `payload_conventions.csv` and
Eq.(7): **82.5× source, 41.25× declared channel use, 75.2× pre-compression, 14.1× bottleneck**.

Its first draft was written with a `sub_once` pattern that did not match the generator's own output,
so `--check` reported a dead pattern on the second run — the R23-8 failure mode, caught immediately
by the R43-4 gate rather than a batch later.

### 4 · Absolute infeasibility statements: verified to zero

Two sites replaced ("The Rayleigh infeasibility is therefore a property of the link budget rather
than of the no-HARQ assumption" → *Under the evaluated retransmission and all-or-nothing delivery
settings, the Rayleigh branch remains infeasible over $0$–$20$~dB*; and the contribution list's
unqualified LDPC-branch clause). The check performed is the one this batch asked for — **zero
unqualified absolutes**, not "a qualifier exists somewhere": every sentence in either document
containing `infeasible` / `never becomes reliable` / `property of the link budget` is required to
carry a scope qualifier in the same sentence. Result: 5 such statements, 0 unqualified.

### 5 · The anchor product now has a check

`tools/check_anchor_sensitivity.py`, registered in the generator gate. It re-derives every row of
`payload_anchor_sensitivity.csv`: each anchor's $B_F$ against the product that owns it
(`payload_conventions.csv`, Eq.(7), the reference geometry), `policy_msym` against
$\rho_L B_L + \rho_F B_F$, `policy_over_fixedF` against their ratio, and the action mix against the
frozen decision logs. 36 rows, 4 conventions, 36 mix cross-checks.

Its own first draft **silently skipped every mix check** — the CSV stores the budget as 10/20/30
while the logs are named `B010/B020/B030` — and still printed PASS, with "0 rows cross-checked" in
plain sight. It now raises rather than skipping. Same family as the dead ENTITY-VALUE control
repaired in R45-7.

### 6 · Limitations: four experimental defects, listed as such

New paragraph in `sec:boundaries`: (i) $L$ and $F$ are separate trainings, so their clean-channel
difference carries each branch's whole pipeline — repair: the unified three-branch construction,
which also removes the dual-branch residency cost; (ii) no real quantised bitstream — a deployed
payload figure needs quantisation width, entropy coder and packetisation; (iii) the bottleneck
convention is an accounting counterfactual, with nothing re-frozen or re-derived under it; (iv) no
unified external baseline under this transport — Where2comm is an adjacent-technology reference and
the budget-matched rerun is scoped, costed and not executed. Each names its pre-registered repair,
and the paragraph says plainly that none of them is repaired by rewording.

### 7 · State

Eighteen gates pass, twice, over both documents; generator gate now covers 8 products;
`p6_numbers_vs_csv` 0 MISS, 0 UNLOCATED; figure gate 0 never-stated; reconciliation gate 6 pairs.
Main **16 pages** (unchanged by this batch's net wording), supplementary 9; abstract 248 words.

## R49 — the ordering claim becomes an assertion, and the canonical summary covers four conventions

Zero GPU. No experiment re-run.

### 1 · Three ordering assertions in `check_anchor_sensitivity.py`

The ordering claim was verified once, by hand, in R47, and then written into the paper. Since R49 it
is asserted on every run, per convention and per split/budget cell: the selector spends at least
`B_L`; strictly less than `B_F`; and more at a looser budget than at a tighter one. Twelve assertions
(three per convention, four conventions), each failing the gate red.

The self-test injects the fault that would actually matter — one cell where the policy spends
1.5× `B_F`, i.e. above the fixed feature message it is supposed to undercut — requires the gate to
fire, and restores the CSV byte-for-byte in `finally`. Result: FIRES, then silent.

### 2 · `docs/canonical_quantities.md` now reports four conventions and two directions

R45's entry named a single "declared→deployed re-anchor, −4.86 % to −41.99 %". That label meant the
**pre-compression** convention, and after R47-2 there are two deployed-side conventions whose shifts
run in **opposite directions**. The canonical summary is now a table:

| counterfactual | shift | direction |
|---|---|---|
| declared → 1 bit per reference element | −8.45 % to −0.77 % | down |
| declared → deployed pre-compression | −45.14 % to −4.12 % | down |
| declared → transmitted-bottleneck counterfactual | +17.56 % to +192.57 % | **up** |

The bottleneck case reverses the sign because it shrinks `B_F` while `B_L` is anchored
independently. Note the pre-compression range itself reads −45.14 % to −4.12 % on the present
decision logs against the −4.86 % to −41.99 % recorded in R45; the historical figure stays in the
change-log as written at the time, and the canonical file is the current summary. That is the
division of labour between the two files, and it is why the change-log is never edited in place.

### 3 · State

Eighteen gates pass, twice; generator gate covers 8 products; `p6_numbers_vs_csv` 0 MISS,
0 UNLOCATED; figure gate 0 never-stated. Main 16 pages, supplementary 9; abstract 248 words.

## R50 — Where2comm budget-matched rerun, plan v2 (PLAN ONLY, no GPU spent)

Zero GPU. This entry registers a plan; it registers no result, and no number in the paper changes.

`docs/where2comm_rerun_plan_v2.md` supersedes the archived R21-B plan, which predates the P0
corrigendum, the frozen protocol and the four-convention payload accounting. Its load-bearing
decisions:

* **N = 1**, the mainline single-collaborator convention. The existing full-collaborator
  reproduction (AP@0.5 `0.871`, retired global-sort scorer, perfect channel) is relabelled
  historical and never ranked. The old comparison's sign already depended on this convention —
  validate Fixed-L `0.7819` sits *below* `0.871` — which is the argument for fixing it first.
* **Eight sparsity points with inference cached per point**, so budget matching is a table join and
  not a re-run. The payload convention has changed twice in three batches (R47, R48); an arm that
  welds accounting into inference would have to be re-inferred each time.
* **A pre-registered sparse-payload convention** (transmitted elements at 0.9155 bit/element, plus
  a charged index cost, min of index-list and dense bitmap, rate-1/2 LDPC, 16-QAM), reported under
  all four existing conventions and destined for `payload_conventions.csv` as a fifth.
* **The frozen scoring chain**, not the retired global-sort scorer, with a GT-count assertion as a
  pre-condition on reporting anything.
* **Four verdict templates** — win / loss / non-inferior / inconclusive — with the confirmatory cell
  named in advance (test, `B_max = 0.20`, declared convention) and the direction left to the data.
* **Three cost tiers and three fuses.** Conservative ≈ 15 GPU-h, typical ≈ 22, worst case ≈ 40,
  anchored on this repository's measured JSCC sweep (~0.28 GPU-h per channel×SNR×split) and the
  existing 50-epoch Where2comm training. The fuses are the SComCP lesson applied in advance: a
  reproduction that does not converge is reported as a negative reproduction result, never as a
  measurement of the method.

**Self-audit, and the one deliberate conflict.** The plan agrees with the collaborator convention,
the replay draw, the δ = 0.005 single-confirmatory-cell rule, the scoring chain and the evidence
grading of R48-1. It **conflicts by design** with R45-4's TERMINOLOGY row and the
`where2comm-baseline` reconciliation pair, both of which currently forbid the word *baseline*: a
budget-matched arm is a baseline. Those two registrations must be amended **in the same commit that
lands the first number**, or the gates will correctly block it — which is the intended behaviour and
is recorded here so it is not mistaken for a gate defect later.

Six gate items the run will require are listed in the plan: provenance binding for the new products,
a direction probe for the verdict sentence, the TERMINOLOGY amendment, the reconciliation re-point,
a machine check for the fifth payload convention, and a loudly-failing GT-count assertion in the
arm's own pipeline.

**Waiting on Josh: cost approval.** Nothing starts without it, and nothing in the paper depends on
the outcome — limitation (iv) of `sec:boundaries` states the absence of a unified external baseline
as a limitation rather than resting a claim on one.

## R51 — Where2comm rerun, stage 0: three plan amendments before any sweep, and a cost recalibration

Josh approved the typical tier (≈22 GPU-h). Stage 0 spent **15 seconds of GPU** on a 20-frame
feasibility probe, and that probe plus two code reads invalidate three parts of plan v2. Amendments
are recorded here **before** the sweep, as the protocol requires.

### A · The grid axis is the communication THRESHOLD, not a sparsity `s`

Read `opencood/models/fuse_modules/where2comm_fuse.py`, `Communication.forward`: at eval time the
mask is `confidence_map > threshold` and the sparsity is *measured* afterwards
(`communication_rate = mask.sum() / (L*H*W)`). Only during training is a rate drawn directly
(`K = int(H*W*uniform(0,1))`). Plan v2 §b asked for eight sparsity points `s`; that grid **cannot be
executed as written** — `s` is an output. The grid becomes eight thresholds, with the achieved rate
recorded per frame and the budget match done on the realised mean. Probe: `threshold = 0.01` gives a
mean rate of `0.5515` over the first 20 validate frames, so the useful threshold range is far above
0.01 and will be bracketed by the sweep.

### B · No retraining — and retraining would have been the inconsistent choice

`CATOSG_MAX_COLLAB=1` is an **inference-time** hook (`opencood/utils/catosg_collab_subset.py`,
applied in `intermediate_fusion_dataset.__getitem__` before the CAV loop). Every mainline arm reaches
the single-collaborator convention this way, on public pretrained checkpoints, with **no** retraining.
Plan v2 §a's "retrain at N=1" would therefore have made Where2comm the only arm trained under a
different discipline from the one it is compared against. The existing 50-epoch reproduction
(`point_pillar_where2comm_2026_05_22_17_56_51/net_epoch50.pth`, recovered from
`/mnt/h/wsl_backup/`) is used, with N=1 applied at inference exactly as the mainline arms do.

### C · Confidence-map billing, decided by reading the code (R46-3 discipline)

The threshold is a **constant shared by both vehicles**, so the collaborator can apply the mask
itself and transmit only the selected cells; the single-process implementation computes the mask at
the fusion site from each CAV's `psm_single`, which does not distinguish the two placements. The
billing convention therefore charges **selected feature elements + index cost only, and not the
confidence map** — the cheaper reading, which *favours* Where2comm. This choice, and the fact that it
favours the comparator, is to be stated wherever the arm's payload appears.

### D · Cost recalibration — the approved estimate was wrong in both directions

| item | plan v2 estimate | measured | why |
|---|---|---|---|
| training, 50 epochs | ~10 GPU-h | **~28–38 GPU-h** (33–45 min/epoch in `where2comm_train/train_where2comm.log`) | the estimate was never anchored on this machine's own training log |
| inference, per grid point, 3 splits | 0.28 h × 3 ≈ 0.8 h | **≈ 1.0 h** (0.75 s/frame × 4,700 frames) | close enough |
| **total** | **≈ 22 GPU-h** | **≈ 8 GPU-h** (8 points × 1.0 h, no training) | amendment B removes the training entirely |

So the run costs roughly **8 GPU-h against the 22 approved**, and the training estimate inside that
22 was itself ~3× low. Both errors are reported; neither is used to justify spending more.

### E · Deviation from the batch's own order, stated plainly

R51 item 1 said "prerequisites first, then touch the GPU". The 20-frame probe ran before the six
gates were in place. It cost 15 seconds and it is what produced amendment A — the plan's grid axis
was unexecutable, and no amount of gate-writing would have revealed that. Recorded as a deviation
rather than presented as the plan.

### R51 stage 1 — dense point run, and a BLOCKER the GT assertion caught

**Run.** Dense point (`threshold = 0`, mask all cells, mean communication rate `1.0000`), validate,
N=1, existing 50-epoch checkpoint: 1,980 frames in **1,546 s (0.78 s/frame)**, cached to
`data/where2comm_v2/validate_thr0.000.npz`. The arm's inference path works end to end.

**Blocker, before any AP is reported.** The GT assertion of `baselines/where2comm_v2/score_arm.py`
fails: this arm sees **27.17** ground-truth objects/frame on validate against **27.80** in the
committed audit (`results/sensitivity/gt_object_stats.csv`). Cause, from the configs:

| arm | evaluation volume |
|---|---|
| Where2comm reproduction | x ∈ [−140.8, 140.8], **y ∈ [−38.4, 38.4]** |
| mainline `pointpillar_late_fusion` (the $L$ branch) | **x ∈ [−70.4, 70.4]**, y ∈ [−40, 40] |
| mainline `pointpillar_attentive_fusion_compression` (the $F$ branch, P4B probe) | x ∈ [−140.8, 140.8], y ∈ [−40, 40] |

Three different volumes, therefore three different GT sets, therefore APs that cannot be ordered —
which is precisely what the assertion exists to prevent, and it fired on the first scored point
rather than after a full sweep. **No AP is reported for this point.**

Note the second finding inside the first: the $L$ and $F$ branches of the mainline are themselves
evaluated over **different x-ranges** (±70.4 m against ±140.8 m). That is a question about the
mainline caches, not about Where2comm, and it is recorded here rather than acted on — acting on it
would touch frozen products.

**The sweep is halted at stage 1** pending a ruling, because every later point inherits the same
mismatch. Two repairs, neither taken unilaterally:

* **(R-a) Common-volume post-filter.** Crop predictions and GT of *every* arm to the intersection
  volume (x ∈ [−70.4, 70.4], y ∈ [−38.4, 38.4]) in post-processing, on the cached outputs. No
  re-inference, consistent with the plan's caching design, and it re-scores the mainline arms too —
  which means producing a second, clearly-labelled scoring track beside the frozen one.
* **(R-b) Re-run Where2comm inference under the mainline volume.** One config override, ~1 GPU-h per
  grid point for the affected splits. It evaluates the model outside the range it was trained on,
  which is a distribution change and must be labelled as one.

Cost so far: **~26 GPU-minutes** (20-frame probe + one dense validate point) of the approved ≈22 h.

### R52 stage 2 — the mainline L/F volume diagnostic, measured

Zero GPU (post-processing on committed caches). **Nothing frozen was touched**; outputs go to
`results/diagnostic/`.

**(a) What the frozen chain actually filters on, read from the code.**
`projects/ca_tosg/evaluation/end_to_end_ap.py` line ~148 takes the canonical GT from the
**attentive-compression** cache (`cb, cs, cg = ...comp_{split}.npz...`; `canon = tt(cg[s], ...)`)
and scores all three branches against it. The three branches were produced under different
configured ranges: `pointpillar_late_fusion` x ∈ [−70.4, 70.4], `pointpillar_attentive_fusion_
compression` x ∈ [−140.8, 140.8], Where2comm x ∈ [−140.8, 140.8] with y ∈ [−38.4, 38.4]. Measured in
the caches themselves (validate, first 400 frames): ego predictions reach |x| ≈ 70 m, late ≈ 86 m,
comp ≈ 110 m, canonical GT ≈ 119 m.

**(b) Impact, from the cached outputs, cropped to x ∈ [−70.4, 70.4], y ∈ [−40, 40].**

| split | GT dropped | Fixed-L AP@0.5 frozen → cropped | Ceiling AP@0.5 frozen → cropped | headroom frozen → cropped |
|---|---|---|---|---|
| validate | 18.89 % | 0.7819 → 0.9064 (+0.1245) | 0.8369 → 0.9181 (+0.0812) | **0.0550 → 0.0117** |
| test | 9.94 % | 0.8691 → 0.9429 (+0.0738) | 0.8931 → 0.9368 (+0.0437) | **0.0240 → −0.0061** |
| Culver-City | 20.48 % | 0.7299 → 0.8825 (+0.1526) | 0.8269 → 0.9077 (+0.0808) | **0.0970 → 0.0252** |

CA-TOSG's own AP moves with its branches (validate +0.112 to +0.118, test +0.067 to +0.073,
Culver +0.136 to +0.153 at AP@0.5). The *level* of every arm rises inside the common volume, which
is expected — the removed GT is GT nobody could detect. What matters is the **gap**: the
feature-level headroom the paper reports shrinks by 79 % on validate, by 74 % on Culver-City, and on
test it **changes sign** — inside the common volume the perfect-channel feature ceiling sits
*below* Fixed L.

**(c) No conclusion is drawn here, and no paper text changed.** Read narrowly, this says the
headroom triple `0.0550 / 0.0240 / 0.0970` is measured across branches whose fields of view differ,
so part of it — most of it on validate and Culver-City, all of it and more on test — is a
field-of-view effect rather than a semantic-granularity effect. Whether that warrants a corrigendum,
a re-scoring track, or a caveat is Josh's ruling; it is not taken here.

Caveats on the diagnostic itself, stated: the crop is centre-based; the replay uses 20 of the 200
realisations (the CA-TOSG rows only, the fixed references are deterministic); the frozen chain is
re-used unchanged apart from the crop.

**One defect in the diagnostic, found and fixed:** the first version keyed its output filename on
`(x, y)` only, so the later `test,culver` run silently overwrote the complete `validate` table with
a partial one. The filename now carries the split set, and the full three-split table is being
regenerated in one process.

### R52 stage 2 — sweep status

The 7-threshold × 3-split sweep is running sequentially in the background
(`baselines/where2comm_v2/sweep.sh`). At ~0.8 s/frame it needs ≈8 wall-clock hours; at the time of
this entry the first point (`threshold = 0.01`, validate) is in progress. GPU spent so far:
≈45 minutes of the approved ≈22 h.

## R53 — the F1 chain's GT, checked first; then the common-volume diagnostic written into the paper

### 1 · Does the F1 chain score all three branches against ONE canonical GT? **YES.**

`projects/ca_tosg/evaluation/canonical_f1.py`, lines 30–35:

```
canon = co['gts']                              # comp cache's union GT
lf = np.array([f1(la['boxes'][s], canon[s]) for s in sids])   # late   vs canon
cf = np.array([f1(co['boxes'][s], canon[s]) for s in sids])   # comp   vs canon
ef = np.array([f1(eg['boxes'][s], canon[s]) for s in sids])   # ego    vs canon
```

All three per-frame columns (`late_f1`, `compressed_f1`, `ego_f1`) are computed against the same
canonical GT tensor, at the same IoU 0.5, by the same function. The file's own header records why
this exists: no stale dataset F1 column is reused. **The F1 chain is internally consistent, and the
F1-based claims do not rest on three different GT sets.** No paper editing was blocked.

**But the answer must be read precisely, and the batch's framing invites a mistake.** "Same GT" was
never the defect. The AP chain also uses one canonical GT — that is exactly how the field-of-view
asymmetry becomes visible: the shared GT extends to |x| ≈ 119 m while the $L$ branch's predictions
stop at |x| ≈ 70 m. F1 inherits the same asymmetry, and inherits it identically.

What follows, stated at the level the evidence supports:

* **Policy-vs-policy F1 comparisons are unaffected in kind.** CA-TOSG and the SNR threshold both mix
  the same three branches against the same GT, so the out-of-range GT is a common term. The R9
  confirmatory claim, the payload comparisons and the hand-rule comparisons all live here.
* **Branch-vs-branch comparisons carry the asymmetry.** Any statement of the form "$F$ is worth
  $x$ more than $L$" — the headroom family above all — is measured across branches with different
  fields of view.

That distinction is what the paper now says, and it is why the diagnostic is a companion track
rather than a correction: the frozen track answers *what each deployed branch delivers as
configured*; the common-volume track answers *how much of the gap survives inside a shared field of
view*. Same GT denominator; different questions.

### 2 · The diagnostic, promoted

`results/diagnostics/common_volume_ap.csv` + `PROVENANCE_common_volume.txt` (18 rows: 3 splits ×
{Fixed-L, feature ceiling, ego-only, CA-TOSG at three budgets}), each row carrying the frozen value,
the cropped value and the delta. Crop: box centre inside |x| ≤ 70.4, |y| ≤ 40, applied identically
to predictions and GT. CA-TOSG rows use 20 of 200 realisations; the fixed references are
deterministic.

### 3 · Verdict recorded for the reconciliation gate (R53-4)

**The headroom triple is a field-of-view effect rather than a granularity effect** on test, and
partly so on validate and Culver-City. Measured: inside the common volume the headroom is
`0.0117` / `-0.0061` / `0.0252` against the deployed-configuration `0.0550` / `0.0240` / `0.0970`.
Any sentence in either delivered document that attributes the headroom purely to semantic
granularity contradicts this record and is blocked by the `headroom-fov` pair.

The paper's own numbers do not change: the deployed track remains what is reported, and the
common-volume figures appear beside it as a companion with their caveats.

### 4 · Two binding repairs the gates forced, both worth recording

* **`results/README.md` is generator-owned.** The first attempt hand-added a row for the new
  diagnostic; the numeric-literal gate's generated-document check caught it immediately. The index
  generator now carries patterns for `diagnostics/common_volume_ap.csv`,
  `diagnostics/branch_ranges.csv`, the provenance file and the raw per-run outputs under
  `results/diagnostic/`. Note the generator only writes the file under `--write`, which is how the
  gate invokes it — running it bare looked idempotent and was not.
* **The `70.4` in the paper had no committed home.** `p6_numbers_vs_csv` reported it as a MISS,
  correctly: the late-fusion branch's configured range lived only in a checkpoint config outside this
  repository. `baselines/where2comm_v2/branch_ranges.py` now reads each checkpoint's own config and
  writes `results/diagnostics/branch_ranges.csv` (late fusion x ±70.4 / y ±40; attentive compression
  x ±140.8 / y ±40; Where2comm x ±140.8 / y ±38.4), and the claim binds there.

## R54 — the threshold grid re-pointed: plan v2 fuse 3, fired early

Same GPU budget, different points. No new approval was spent: the 5 remaining thresholds are
replaced, not added to.

**Why.** The measured threshold→sparsity map is far steeper than plan v2 assumed:

| threshold | 0.0 | 0.01 | 0.05 | 0.10 |
|---|---|---|---|---|
| mean rate (validate) | 1.0000 | 0.4839 | 0.0319 | 0.0099 |
| mean rate (test) | — | 0.4648 | 0.0179 | — |
| mean rate (Culver-City) | — | 0.4851 | 0.0379 | — |

Every threshold at or above 0.10 collapses to "send almost nothing", so the original upper points
(0.10 … 0.70) would have produced five near-identical near-$L$ policies. Meanwhile the rates the
budgets actually require — roughly 0.10 / 0.20 / 0.30 of the dense payload for
$B_{\max}=0.10/0.20/0.30$ under the declared convention — sit in the **unsampled gap between
threshold 0.01 and 0.05**.

**What changed.** The remaining five points become **{0.015, 0.02, 0.025, 0.03, 0.04}**. The eight
completed points are kept: 0.0 (dense anchor), 0.01, 0.05 (the bracket ends) and 0.10 (now the
collapse evidence, which is worth having on the curve rather than assumed).

**Registered as fuse 3, fired early.** Plan v2 §f wrote fuse 3 as "if no grid point lands within
±20 % of the cap, add one refinement pass and no more". The condition is already established from
the completed points rather than after the full sweep, so the refinement is taken now instead of
after spending 3.2 GPU-hours on points known in advance to be redundant. It remains **one** pass: if
{0.015 … 0.04} still misses a cap by more than ±20 %, the bracketing pair is reported and the arm
stops, per the fuse's own wording.

Cost unchanged: 5 thresholds × 3 splits ≈ 3.2 h plus the two dense points ≈ 0.25 h. GPU spent before
this entry: ≈2.1 h of the approved ≈22 h.

## R55 — sweep complete; fuse 3 fires on the confirmatory cell; the arm stops there

The re-pointed sweep finished (25 threshold×split products, `data/where2comm_v2/`). GPU spent
≈5.4 h of the approved ≈22 h. Two committed products:
`results/baselines/where2comm_v2/sparsity_payload.csv` and `budget_match.csv`.

### 1 · Measured threshold → sparsity (mean over frames)

| threshold | 0.0 | 0.01 | 0.015 | 0.02 | 0.025 | 0.03 | 0.04 | 0.05 | 0.10 |
|---|---|---|---|---|---|---|---|---|---|
| validate | 1.0000 | 0.4839 | 0.1204 | 0.0831 | 0.0654 | 0.0540 | 0.0402 | 0.0319 | 0.0099 |
| test | 1.0000 | 0.4648 | 0.0802 | 0.0521 | 0.0392 | 0.0314 | 0.0227 | 0.0179 | — |
| Culver-City | 1.0000 | 0.4851 | 0.1264 | 0.0908 | 0.0730 | 0.0608 | 0.0463 | 0.0379 | — |

The map is steeper still than the refinement assumed: between threshold 0.01 and 0.015 the rate
falls from ≈0.48 to ≈0.08–0.13. That interval is a cliff, not a slope, and it is where the two
larger budgets live.

### 2 · The fifth payload convention, applied

`B_{W2C}(s) = [s·N_ref·0.9155 + min(s·H·W·⌈log2 HW⌉, H·W)] / R / 4` Msym, with the reference
geometry `N_ref = 256×48×176`, `H·W = 48×176`, `R = 1/2`, 16-QAM — the convention pre-registered in
plan v2 §c, charging the index cost and **not** charging the confidence map (the reading that favours
the comparator, per R51-C). Required rates to meet each cap under the declared convention:
`B_max = 0.10 → s ≈ 0.0967`, `0.20 → s ≈ 0.1978`, `0.30 → s ≈ 0.2988`.

### 3 · Budget matching — and fuse 3 fires

| split | `B_max` | rate needed | nearest measured | error | matched (±20 %)? |
|---|---|---|---|---|---|
| validate | 0.10 | 0.0967 | 0.0831 (thr 0.02) | −14.1 % | **yes** |
| validate | 0.20 | 0.1978 | 0.1204 (thr 0.015) | −39.1 % | no — bracket [0.1204, 0.4839] |
| validate | 0.30 | 0.2988 | 0.1204 (thr 0.015) | −59.7 % | no — bracket [0.1204, 0.4839] |
| test | 0.10 | 0.0967 | 0.0802 (thr 0.015) | −17.1 % | **yes** |
| **test** | **0.20** | 0.1978 | 0.0802 (thr 0.015) | −59.5 % | **no — bracket [0.0802, 0.4648]** |
| test | 0.30 | 0.2988 | 0.4648 (thr 0.01) | +55.6 % | no — bracket [0.0802, 0.4648] |
| Culver-City | 0.10 | 0.0967 | 0.0908 (thr 0.02) | −6.1 % | **yes** |
| Culver-City | 0.20 | 0.1978 | 0.1264 (thr 0.015) | −36.1 % | no |
| Culver-City | 0.30 | 0.2988 | 0.1264 (thr 0.015) | −57.7 % | no |

**The pre-registered confirmatory cell is test @ `B_max = 0.20`, and it is not matched.** Plan v2
fuse 3 allows exactly one refinement pass; R54 spent it. Its own wording then applies verbatim: *"if
it still misses, report the bracketing pair and say the cap was not matched."* Reported:
`s ∈ [0.0802, 0.4648]` brackets the required `0.1978` on test, and no grid point lies inside ±20 %.

**Therefore no verdict sentence is produced for the confirmatory cell**, and none of the four
templates (win / loss / non-inferior / inconclusive-at-the-margin) is applied: all four presuppose a
budget-matched comparison. The honest statement is the fifth case the plan did not enumerate — *the
comparison was not run at a matched budget, because the comparator's control parameter has no
setting that lands there.*

### 4 · What is still open, and what it would cost

`B_max = 0.10` **is** matched on all three splits (−14.1 %, −17.1 %, −6.1 %), so a descriptive
comparison at the tightest budget is available and needs only a scoring pass over the three cached
points (thr 0.02 / 0.015 / 0.02), in the three-way common volume with the GT assertion, zero GPU.
That is the next step and is not taken in this entry.

Reaching the 0.20 and 0.30 caps would need a *second* refinement inside the cliff — thresholds
between 0.010 and 0.015, where the rate falls from 0.48 to 0.08 — which fuse 3 forbids without a new
ruling. Estimated cost if ruled: 2–3 thresholds × 3 splits ≈ 1.2–1.8 GPU-h.

## R55-1/2 — the descriptive cell is blocked by a GT boundary rule; amendment A1 running

### 1 · `B_max = 0.10` scoring attempt, and why no AP is reported

The three budget-matched points (validate thr 0.02, test thr 0.015, Culver thr 0.02) were scored in
the three-way common volume $|x|\le70.4$, $|y|\le38.4$. **The GT assertion fails on all three**, so
no AP is reported, per the plan's pre-condition:

| split | Where2comm cropped GT | mainline cropped GT | difference |
|---|---|---|---|
| validate | 43,697 | 44,766 | −1,069 (−2.4 %) |
| test | 29,183 | 29,354 | −171 (−0.6 %) |
| Culver-City | 18,389 | 18,650 | −261 (−1.4 %) |

Diagnosed rather than assumed. On validate, **1,450 of 1,980 frames are identical** and the 530 that
differ are all one-sided (difference between −6 and 0; the Where2comm track never sees *more*).
Uncropped totals: 53,789 against 55,190. The signature points at a **boundary rule**, not a different
scene set: the Where2comm config filters ground truth at $|y|\le38.4$ inside the dataset, the
mainline at $|y|\le40$, and OpenCOOD's own in-range test is not the centre-based crop this
diagnostic applies afterwards. Objects near the $y$ boundary are therefore kept by one track and
dropped by the other, and no amount of post-hoc cropping by box centre reconciles two different
in-dataset filters.

**Proposed repair, zero GPU, not taken without a ruling:** score both tracks on the *intersection*
GT set — objects matched between the two canonical sets by centre proximity — which makes "the same
objects" true by construction rather than by hoping two filters agree. It changes the denominator for
both tracks equally and would be a third labelled track, not a change to anything frozen.

### 2 · Amendment A1 (the last refinement round) is running

Thresholds {0.011, 0.012, 0.013} × 3 splits, ≈1.8 GPU-h, launched. Registered in `sweep.sh` with the
pre-registered endpoint in the comment: **after this round there is no further refinement, whether or
not a point lands within ±20 % of a cap.** Fuse 3's single pass was spent in R54; this round exists
only because it was ruled explicitly.

### 3 · The threshold→sparsity cliff, recorded as a finding in its own right

Data, no interpretation: mean sparsity against threshold on validate is
1.0000 / 0.4839 / 0.1204 / 0.0831 / 0.0654 / 0.0540 / 0.0402 / 0.0319 / 0.0099 at
0.0 / 0.01 / 0.015 / 0.02 / 0.025 / 0.03 / 0.04 / 0.05 / 0.10, i.e. **86 % of the control range
collapses between threshold 0.01 and 0.015**, and the two larger budgets fall inside that collapse.
Test and Culver-City behave the same way with a shifted knee. Whether this is the same phenomenon as
the payload ladder of `sec:ablation` — a control parameter whose reachable operating points are
sparse where the budgets live — is a question for the write-up, and is deliberately not answered
here.

## R56 — the intersection-GT track: the descriptive `B_max = 0.10` comparison, on identical objects

Zero GPU. Third labelled track; nothing frozen touched.

### 1 · Construction, as pre-registered

Box-centre matching, one-to-one, tolerance **ε = 0.5 m**, a second claim on either side refused.
**Assertion PASS on all three splits** — matched counts strictly equal: validate 53,789, test 32,248,
Culver-City 22,856; inside the volume $|x|\le70.4$, $|y|\le38.4$: 43,697 / 29,183 / 18,389.

The tolerance turns out not to matter: every matched pair is at distance **0.000 m** and the counts
at ε = 0.01 m are identical to those at 0.5 m, because both sets are the same simulator annotations
filtered differently at the boundary. The script reports both so the insensitivity is visible rather
than asserted. (The first implementation did a full argsort per frame and would have taken hours;
exact-centre hashing with the ε path as fallback does the same job in minutes.)

### 2 · Result, DESCRIPTIVE — not the confirmatory cell

Where2comm at the budget-matched point against the mainline arms, AP@0.5, same objects, same volume,
same scorer:

| split | Where2comm | CA-TOSG @ B0.10 | Δ (W2C − CA-TOSG) | Fixed L | feature ceiling | W2C rate / budget error |
|---|---|---|---|---|---|---|
| validate | **0.91519** | 0.90883 | **+0.00636** | 0.90934 | 0.92084 | 0.0831, −14.1 % under cap |
| test | 0.94358 | **0.94490** | **−0.00132** | 0.94506 | 0.93952 | 0.0802, −17.1 % under cap |
| Culver-City | **0.89572** | 0.89508 | **+0.00064** | 0.89507 | 0.92060 | 0.0908, −6.1 % under cap |

Read with the discipline this record has used throughout:

* **This is not the pre-registered confirmatory cell.** That is test @ `B_max = 0.20`, which fuse 3
  established cannot be matched. No verdict template applies here, and none is applied.
* The budget errors are all **under** the cap, so the comparator is spending less than it is allowed
  — the comparison is not flattering CA-TOSG.
* On validate Where2comm is ahead by `+0.0064` and is also above Fixed $L$; on test it is behind by
  `-0.0013` and both sit essentially at Fixed $L$, which on that split is *above* the feature
  ceiling (the R53 field-of-view finding, reproduced here on a different GT construction); on
  Culver-City the two are within `0.0007` of each other and of Fixed $L$.
* Three splits, one budget, one realisation count (20 of 200 for the CA-TOSG rows), no interval
  estimate. Nothing here is a claim about either method; it is the descriptive cell the plan allows
  at a non-confirmatory budget.

### 3 · Amendment A1, partial

Threshold 0.011 completed on all three splits: rates **0.4349 / 0.4222 / 0.4331** (validate / test /
Culver-City). The cliff is sharper than the refinement assumed — between 0.011 and 0.015 the rate
falls from ≈0.43 to ≈0.08–0.13 — so the required 0.1978 (for `B_max = 0.20`) still has no point near
it. Thresholds 0.012 and 0.013 are running; the pre-registered endpoint stands either way.

## R57 — A1 lands: `B_max = 0.30` matched, the confirmatory cell is not. Fifth case, final.

Amendment A1 completed (thresholds 0.011 / 0.012 / 0.013 × 3 splits, ≈1.9 GPU-h; total for the arm
≈7.3 h of the approved ≈22 h). **The pre-registered endpoint is reached: no further refinement.**

### 1 · The full control curve

Mean sparsity against communication threshold:

| threshold | 0.0 | 0.01 | 0.011 | 0.012 | 0.013 | 0.015 | 0.02 | 0.025 | 0.03 | 0.04 | 0.05 | 0.10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| validate | 1.0000 | 0.4839 | 0.4349 | 0.3875 | 0.3209 | 0.1204 | 0.0831 | 0.0654 | 0.0540 | 0.0402 | 0.0319 | 0.0099 |
| test | 1.0000 | 0.4648 | 0.4222 | 0.3786 | 0.3130 | 0.0802 | 0.0521 | 0.0392 | 0.0314 | 0.0227 | 0.0179 | — |
| Culver-City | 1.0000 | 0.4851 | 0.4331 | 0.3825 | 0.3117 | 0.1264 | 0.0908 | 0.0730 | 0.0608 | 0.0463 | 0.0379 | — |

The step from 0.013 to 0.015 drops the rate by ≈0.23 in one move, and the rate `B_max = 0.20`
requires (0.1978) sits inside that step on every split. **This is not undersampling: it is a control
parameter with no resting point there.** Twelve thresholds, three of them placed inside the step by
two separate refinement rounds, and none lands within ±20 % of the middle budget.

### 2 · Budget matching, final

| split | `B_max = 0.10` | `B_max = 0.20` | `B_max = 0.30` |
|---|---|---|---|
| validate | 0.0831, −14.1 % ✔ | 0.1204, −39.1 % ✘ (bracket 0.1204–0.3209) | 0.3209, +7.4 % ✔ |
| test | 0.0802, −17.1 % ✔ | 0.3130, +58.3 % ✘ (bracket 0.0802–0.3130) | 0.3130, +4.8 % ✔ |
| Culver-City | 0.0908, −6.1 % ✔ | 0.1264, −36.1 % ✘ (bracket 0.1264–0.3117) | 0.3117, +4.3 % ✔ |

### 3 · The confirmatory cell: fifth case, stated as the record requires

The pre-registered confirmatory comparison is **test @ `B_max = 0.20`**. It cannot be run:

> *The budget-matched comparison at the confirmatory cell could not be performed. Where2comm's
> communication threshold has no setting that places its mean payload within ±20 % of the
> `B_max = 0.20` cap: the reachable rates bracket the required 0.1978 as [0.0802, 0.3130] on test,
> and twelve grid points — three of them placed inside the bracket by two refinement rounds — leave
> the interval empty. Reported as a bracketing pair, with no verdict.*

None of the four pre-registered verdict templates applies, because all four presuppose a matched
budget. **No verdict sentence exists for this arm, and none may be written into the paper.**

### 4 · Descriptive cells, both budgets that are matched (intersection-GT track, AP@0.5)

| budget | split | Where2comm | CA-TOSG | Δ | Fixed L | ceiling | W2C rate |
|---|---|---|---|---|---|---|---|
| 0.10 | validate | 0.91519 | 0.90883 | **+0.00636** | 0.90934 | 0.92084 | 0.0831 |
| 0.10 | test | 0.94358 | 0.94490 | **−0.00132** | 0.94506 | 0.93952 | 0.0802 |
| 0.10 | Culver-City | 0.89572 | 0.89508 | **+0.00064** | 0.89507 | 0.92060 | 0.0908 |
| 0.30 | validate | 0.91653 | 0.90930 | **+0.00723** | 0.90934 | 0.92084 | 0.3209 |
| 0.30 | test | 0.94417 | 0.94363 | **+0.00054** | 0.94506 | 0.93952 | 0.3130 |
| 0.30 | Culver-City | 0.89885 | 0.89864 | **+0.00021** | 0.89507 | 0.92060 | 0.3117 |

Read with the same discipline as everything else here:

* **Descriptive. Not confirmatory. No interval, no decision, no margin.** Five of six cells favour
  Where2comm by between `+0.0002` and `+0.0072` AP@0.5; one (test @ 0.10) favours CA-TOSG by
  `-0.0013`. Nobody should read a sign pattern of that size as a result — that is exactly what the
  pre-registered margin and interval exist to prevent, and neither is available here.
* At `B_max = 0.10` the comparator spends **under** its cap on all three splits, so the comparison
  does not flatter CA-TOSG. At `0.30` it spends slightly **over** (+4.3 % to +7.4 %), so there the
  advantage is partly bought.
* On test both arms sit at or below Fixed $L$, which on that split is above the feature ceiling —
  the R53 field-of-view finding, reproduced on a GT set built by a different construction.

### 5 · Cost

Arm total ≈7.3 GPU-h of the approved ≈22 h: 5.4 h for the main sweep, 1.9 h for A1. No training was
run (R51-B). Zero GPU was spent on any of the three scoring tracks.

## R57 — the arm enters the paper; no verdict does

Zero GPU. The paper is now in compile state.

1. **Supplementary**: the non-baseline subsection is replaced by *Budget-Matched External Comparison
   (Where2comm)* — full protocol disclosure (N=1 inference hook, no retraining, intersection-GT
   construction, the billing convention that favours the comparator), the threshold→fraction cliff
   table, the budget-match table, both descriptive tables, the four readings verbatim, and the fifth
   case with its bracketing pair. **No verdict sentence exists anywhere in either document.**
2. **Main text**, four sites: the pointer now says a budget-matched comparison was run and carries no
   adjudication at the confirmatory cell; limitation (iv) is rewritten to *comparison run,
   confirmatory adjudication unreachable, confirmatory external comparison still outstanding*; the
   `B_max = 0.30` reference carries its over-spend disclosure; and the cliff is placed beside the
   payload ladder with an explicit refusal to generalise ("two mechanisms can leave a budget
   unreachable without being the same mechanism").
3. **TERMINOLOGY migrated** as pre-registered: the `never a baseline` family becomes
   `no confirmatory adjudication`. The forbidden set is now verbs of adjudication
   (outperforms / beats / wins / non-inferior / confirmatory), with `baseline` kept under a
   `(?<!not a )` guard so the retired R45-4 form still fires as a self-test probe. Seven injected
   faults, all firing.
4. **Six gate items landed**: products indexed and claims bound; three direction probes over the
   descriptive cells with the reversed one (test @ 0.10) registered separately so a regenerated table
   cannot quietly align the sign pattern; a `w2c-no-verdict` reconciliation pair; the five-convention
   accounting machine-checked by `check_anchor_sensitivity.py`; the cliff table sourced to its CSV;
   and the arm's GT assertion resident in `score_common_volume.py` / `intersection_gt_track.py`.

**An eighth fingerprint collision**, handled the usual way: `three-way` was a retired action-set
form and is now live text (the three-way intersection volume). Re-anchored on the action set.

State: 18 gates pass twice; all four `p6_cross_section_scan` controls fire; `p6_numbers_vs_csv`
0 MISS; reconciliation 7 pairs, 6 injected faults firing; direction gate 21 claims. Main **16 pages**,
supplementary **11 pages**, abstract 248 words.

## R58-1 — CORRECTION, committed alone and first: the arm was never run under the transport

**The R57 text was false.** It said the Where2comm comparison was run "under this paper's own
transport and scoring chain". The scoring chain, the frames, the ground truth and the collaborator
convention are true. **The transport is not**: no channel model was applied to either arm in that
comparison. `run_inference.py` produces detections; `intersection_gt_track.py` scores them; nothing
in that path draws an SNR, looks up a BLER, or falls back on a delivery failure. The AP numbers in
Table~\ref{tab:w2c_descriptive} are **ideal-delivery** numbers for both arms.

How it happened, stated plainly: the plan (v2 §d) specified the frozen replay for this arm, the
implementation scored cached detections directly, and no gate compared the two — every gate here
checks the paper against products or against the record, and this was a claim about a *procedure*
that no product contradicts. The R46-3 paper-vs-code discipline exists for exactly this and was not
applied to my own summary sentence.

Wording downgraded in the same commit, before anything else: the arm is now a **budget-aligned
perception diagnostic under ideal delivery**, said in the supplementary lead, in the descriptive
table's caption, in the main-text pointer and in limitation (iv). Every "under this paper's
transport" form is gone from both documents (0 occurrences).

The transport-aware replay is R58-2 and is not in this commit. Until it lands, nothing in either
document claims a same-transport comparison.

## R58-2/3 — the arm under the modelled transport: every ideal-delivery sign reverses

Zero further GPU beyond the 38.6 min of ego-only forwards (arm total ≈8.0 h of the approved ≈22 h);
the replay itself is CPU. Product: `results/diagnostics/transport_replay.csv` (7 cells).

### 1 · What the replay does, and the invariant that guards it

Same CSI draw as the mainline (`CSI_SEED`, `uniform` then `random`, in that order), the arm's **own**
codeword count (`N_cw(s) = info_bits(s)/500`, e.g. 335–1288 against the mainline's 3960 — its frame
BLER is re-derived from `bler_cw`, never read off the `bler_frame` column), the shared delivery coin
(`BLER_COIN_SEED`), whole-frame all-or-nothing, and a failure falling back to **Where2comm's own
ego-only forward** (threshold 1.1, measured fraction 0.0000). Invariant checked in every run: at
`bF = 0` the replay reproduces that point's ideal-delivery AP exactly.

### 2 · Six descriptive cells, AP@0.5, 200/200 realisations

| `B_max` | split | fraction | delivery rate | W2C ideal | **W2C transport** | **CA-TOSG** | **Δ** |
|---|---|---|---|---|---|---|---|
| 0.10 | validate | 0.0831 | 0.3095 | 0.91519 | 0.82529 | 0.90880 | **−0.08351** |
| 0.10 | test | 0.0802 | 0.3095 | 0.94358 | 0.87437 | 0.94492 | **−0.07055** |
| 0.10 | Culver-City | 0.0908 | 0.3118 | 0.89572 | 0.81679 | 0.89508 | **−0.07830** |
| 0.30 | validate | 0.3209 | 0.3055 | 0.91653 | 0.82507 | 0.90910 | **−0.08403** |
| 0.30 | test | 0.3130 | 0.3056 | 0.94417 | 0.87414 | 0.94332 | **−0.06918** |
| 0.30 | Culver-City | 0.3117 | 0.3081 | 0.89885 | 0.81729 | 0.89878 | **−0.08149** |

**Every sign reverses.** Under ideal delivery five of six cells favoured Where2comm by `+0.0002` to
`+0.0072`; under the transport all six favour \method{} by `0.069` to `0.084` — an order of
magnitude larger, and in the opposite direction. The mechanism is visible in the delivery column:
Where2comm transmits on every frame, so it eats the channel on the ~69 % of frames the link cannot
carry and falls back to its own ego-only output; \method{} at these budgets rarely requests the
feature branch at all, so the transport barely moves it. That is the paper's own thesis measured
against an external arm, and it is precisely what the missing transport had hidden.

### 3 · Amendment A2 — the confirmatory cell, reached by mixture

Registered as an amendment, **not** part of the original pre-registration. The confirmatory cell
(test @ `B_max = 0.20`) is unreachable by any single threshold, so the arm mixes two per frame:
`p = 0.5052` of threshold 0.013 (fraction 0.3130) with 0.015 (fraction 0.0802), giving a mean
fraction of **0.1978** — the cap, exactly. Each frame carries its own source's `N_cw`.

Result, 200/200 realisations: **W2C 0.87427 ± 0.00149, \method{} 0.94492 ± 0.00051,
Δ = −0.07064**, delivery rate 0.3076.

Template applied, **under amendment A2**: this is the *CA-TOSG wins* branch — the difference exceeds
the `δ = 0.005` margin by more than an order of magnitude, in \method{}'s favour. Two deviations from
the template's own terms must be stated with it: the metric is AP@0.5, not the frame F1 the templates
were written for, and the dispersion is the across-realisation standard deviation, not the
pre-registered paired bootstrap interval.

**This verdict is not in the paper and will not be written into it without a ruling.** The delivered
documents still describe the ideal-delivery diagnostic, which is what they contain.

### 4 · One crash, and what it was

The two `test` cells failed first time: a handful of frames in the ego-only forward detect nothing,
`tt()` returns a 0-d array, and `crop()` raised on `.shape[0]`. Only the fallback cache produces such
frames, which is why no earlier scoring pass hit it. Normalised to an empty `(0, 8, 3)` inside the
replay; the shared scorer is untouched.

### 5 · New gate pair

`same-transport-claim`: any sentence claiming the external arm ran under this paper's transport is a
contradiction unless the replay product exists. The R57 text made exactly that claim with no replay
in the repository at all.

## R59 — intervals, then the verdict enters the paper

Zero GPU. CPU: the seven cells were re-run to store per-realisation AP arrays (the R58 products kept
only a mean and a standard deviation, and the pairing lives in the per-draw values), then bootstrapped.

### 1 · Paired bootstrap, and exactly what it is

`N_BOOT = 10000`, `BOOT_SEED = 12345`, percentile, **paired on the CSI realisation** — both arms see
the same 200 draws through the same delivery coin. The ruling is carried verbatim in the tool and in
the paper: *the interval quantifies stability over channel realisations, conditional on the fixed
evaluation set, and does not cover scene-sampling variability; it must not be cited as the same
construction as the frame-level R9 interval.* The parallel frame-F1 metric track was ruled **not
opened**: AP with a stated metric deviation is the final form.

| `B_max` | split | Δ (W2C − CA-TOSG) | 95 % CI |
|---|---|---|---|
| 0.10 | validate | −0.08351 | [−0.08374, −0.08327] |
| 0.10 | test | −0.07055 | [−0.07076, −0.07034] |
| 0.10 | Culver-City | −0.07830 | [−0.07864, −0.07794] |
| **0.20 (A2)** | **test** | **−0.07064** | **[−0.07087, −0.07042]** |
| 0.30 | validate | −0.08403 | [−0.08426, −0.08380] |
| 0.30 | test | −0.06918 | [−0.06941, −0.06895] |
| 0.30 | Culver-City | −0.08149 | [−0.08182, −0.08114] |

Every interval excludes zero and lies beyond `δ = 0.005` by more than an order of magnitude. They are
tight because the pairing removes the shared channel draw — a statement about realisation stability
and nothing else.

### 2–4 · What the documents now say

The supplementary section is a **pair**: an ideal-delivery table (perception-layer diagnostic,
numbers unchanged, caption now says what it isolates) and a transport table (delivered fraction,
200/200 realisations, full replay disclosure, paired CI per cell), with the mechanism paragraph
between them — always-transmit, no cheap rung, cliff channel, ≈69 % of frames lost and reverted to
the comparator's own ego-only output, against a selector that requests the feature branch on a
minority of frames.

The confirmatory sentence carries every fixed element: **under amendment A2 (mixture policy)**, the
metric deviation (AP@0.5, not the frame F1 the margin was registered on), the interval disclosure,
Δ = −0.07064 against δ = 0.005, attribution to **transmission behaviour under this transport rather
than detection quality**, the **evaluated retransmission and all-or-nothing delivery settings**
qualifier, and the comparator's status as a **reproduction-grade checkpoint applied without
retraining**.

Main text: the pointer states both readings in one sentence; limitation (iv) is narrowed to what
remains — one external method, a reproduction-grade checkpoint, an amendment in the confirmatory
path, a metric deviation, and no unified-training controlled comparison.

### 5 · Gates

Direction probes are split by track: three on the ideal-delivery track (directions unchanged,
including the reversed `test @ 0.10` cell) and three on the transport track, a separate registry
entry — a probe must name which track it asserts. 24 registered comparisons. `same-transport-claim`
now passes because the replay product exists.

`0.5052` was unbound: the mixture probability lived only in a command line. It is a stored field of
the A2 product (`mixture_p`, with its derivation), which is where a number a sentence quotes belongs.

State: 18 gates pass, `milestone_summary.md` regenerated. Main **16 pages**, supplementary **12**.

## R60 — per-frame accounting, and the confirmatory framing withdrawn

Zero GPU; the recompute is CPU.

### 1 · Per-frame payload accounting

The replay charged every frame at the split's **mean** transmitted fraction, so one `N_cw` covered a
whole split. That is wrong in both directions at once — a sparse frame billed for codewords it never
sent, a dense one billed for fewer than it did — and the frame BLER is convex in `N_cw`, so the error
does not cancel. Fixed: per-frame `comm_rate[k]` → per-frame `N_cw[k]` → per-frame BLER, with the
codeword BLER interpolated first and the frame BLER formed after (interpolating a frame-BLER curve
built at one `N_cw` and using it at another was itself part of the error). In the A2 mixture each
frame is charged at its own selected point's per-frame count. Spread within a single point is large:
`N_cw` runs 175–543 inside one Culver-City cell whose mean is 376.

Seven cells recomputed, old → new:

| `B_max` | split | Δ old | Δ new | delivery old → new |
|---|---|---|---|---|
| 0.10 | validate | −0.08351 | **−0.08486** | 0.3095 → 0.3001 |
| 0.10 | test | −0.07055 | **−0.07155** | 0.3095 → 0.3002 |
| 0.10 | Culver-City | −0.07830 | **−0.07952** | 0.3118 → 0.3014 |
| 0.20 (mixture) | test | −0.07064 | **−0.07166** | 0.3076 → 0.2977 |
| 0.30 | validate | −0.08403 | **−0.08540** | 0.3055 → 0.2954 |
| 0.30 | test | −0.06918 | **−0.07021** | 0.3056 → 0.2952 |
| 0.30 | Culver-City | −0.08149 | **−0.08280** | 0.3081 → 0.2972 |

Every gap widens by 0.001–0.0014 and every delivery rate falls by about a point. The direction and
the order of magnitude are unchanged; the old values are retired.

### 2 · The confirmatory framing is withdrawn

The mixture policy is **post-hoc**: the budget is met by a policy chosen after seeing the grid, on
the data the analysis runs on. Calling its output a confirmatory verdict — as R59 did, with an
"under amendment A2" label — dressed a post-hoc analysis in pre-registration language. Removed from
both documents: *confirmatory verdict*, *adjudicated at the confirmatory cell*, the *wins branch*
framing, and *beyond the pre-registered δ*. The sentence is now the supervisor's form: *in a post-hoc
budget-matched mixture analysis, CA-TOSG achieved AP@0.5 0.94492 compared with 0.87325 for our
Where2comm reproduction under the evaluated transport*, with its interval, the metric deviation, the
no-retransmission qualifier and the reproduction-grade-checkpoint disclosure attached, and no margin
applied.

The TERMINOLOGY exemption that let adjudication verbs appear inside an A2-labelled sentence is
**withdrawn**; `adjudicat` joins the forbidden set, with no exemption anywhere. The
`w2c-no-verdict` reconciliation pair is back on active duty and now anchors on the post-hoc wording.

**Pre-registered as a future item, in limitation (iv):** a genuine confirmatory external comparison
needs an AP margin fixed *before* the run and an evaluation split that took no part in choosing the
comparator's operating point. Neither exists here.

### 5 · One more wording repair

"under the evaluated retransmission and all-or-nothing delivery settings" → **"under the evaluated
no-retransmission, all-or-nothing delivery setting"**. No retransmission was performed anywhere in
this replay; the earlier phrasing implied one had been.

## R61 — codeword rounding, mixture statistics, and a locked cell manifest

Zero GPU; CPU rerun of all seven cells.

### 1 · `N_cw` is rounded **up**

`round()` → `ceil()`: a partial codeword is still transmitted, so rounding down charged the
comparator for fewer codewords than it sends. **Direction of both corrections, stated together:**
this one can only leave Where2comm's frame BLER equal or higher, and R60's per-frame accounting also
moved against it. Neither correction flatters \method{}; both were applied because they are right,
and both push the same way.

**Effect: negligible.** `info_bits/500` is in the hundreds, so ceil differs from round by at most one
codeword. Across the seven cells exactly one number moved: `test @ B_max = 0.10`, W2C AP@0.5
`0.87337 → 0.87336`. No Δ and no interval changed at five decimals. The seven cells are otherwise
identical to R60, and the paper's numbers stand.

### 2 · Mixture codeword statistics now describe the sequence the simulation used

The A2 cell reported one component's counts. It now rebuilds the realised per-frame counts from the
**same seeded selection the replay drew**, labels them `n_cw_source = mixture-realised`, and asserts
the reconstruction has the replay's shape. Realised span: `42`–`1915` codewords per frame, against
`42`–`820` and `668`–`1915` for the two components separately — neither component's range describes
the mixture, which is why reporting one of them was wrong.

### 3 · `beyond_delta` removed

The column compared a post-hoc AP analysis against a margin pre-registered for a frame-F1
confirmatory comparison. Deleted from `transport_replay_ci.csv` and from every quoting site: keeping
it invited exactly the reading R60 corrected.

### 4 · The cell manifest is explicit

`collect_transport.py` names its seven files. A glob silently absorbs an eighth and silently
tolerates a missing one; either way the summary stops describing what it claims to. Self-test:
inserting an eighth JSON **FIRES**, removing it goes silent.

### 5 · Gate reporting, one wording everywhere

Two tiers, and the honest statement differs by machine: `--content-only` runs **10 of 18** and needs
nothing beyond this repository; the other **8 are artefact-tier**, requiring `data/p2`, the frozen
models and the sibling OpenCOOD checkout. **On this machine those artefacts are present, so all 18
run and pass** — the two-tier language describes what a clean clone can reproduce, not a gate that
went unrun here. Reports and `docs/reproducibility.md` now say it the same way.

## R62 — one manifest, realised values, final reproduction wording

Zero GPU. No result number changes.

1. **One source of truth for the cell set.** `paired_bootstrap.py` imported nothing and globbed the
   directory itself, so the collector's manifest guarded one script and not the other. It now imports
   `EXPECTED` from `collect_transport` and fails on a missing or extra cell. Self-tests: an eighth
   JSON **FIRES** in both scripts, removal goes silent in both.

2. **Realised, not designed.** The replay now accumulates, inside the loop, the fraction and codeword
   counts it actually used, and reports `realised_mean_fraction`, its deviation from the design
   value, and realised mean/min/max codewords. Under a mixture the fraction is a draw, not the design
   value, and a product reporting the design value cannot show how far the draw landed.

   Until those fields exist in regenerated cells, the paper uses the transitional form: the mixture's
   **expected** mean transmitted fraction is `0.1978`, the cap, with the realised fraction described
   as a draw around it. The retired phrasing --- "whose mean transmitted fraction is 0.1978, the cap
   exactly" --- attached *exactly* to an expectation, which is the error being removed.

3. **Reproduction wording, final.** All 18 gates run and pass on the full experiment machine; a clean
   clone reproduces the content, comparison and generator tiers unaided; the artefact tier
   additionally needs `data/p2`, the frozen models, the OpenCOOD checkout, PyTorch and Tectonic.
   `docs/reproducibility.md` and every report now say this identically.

## R63/R64 — realised values fixed at the source, three mechanism sentences corrected

Zero GPU. **The "no result number changes" claim is now an executed verification, not an
expectation**: all seven cells were regenerated after the code change and every AP and every interval
is identical to R61 at five decimals. Products: `results/diagnostics/transport_replay.csv`,
`transport_replay_ci.csv`, and the seven per-cell JSONs.

### 1 · The realised-value accumulation

A single-threshold point transmits the same payload every realisation, so appending it inside the
replay loop stored one vector 200 times to describe one fact. It is now taken once after the loop.
The mixture *is* a draw, so its accumulated sequence is the product — and it now carries a **true
equality assertion** against the seeded reconstruction (`np.array_equal`), not a shape check: a shape
check passes on the wrong numbers.

Realised values for the mixture cell, now reported rather than assumed: fraction **0.19774**,
deviation **−0.00009** from the design value, codewords **42–1915**, mean **798.9**. The paper quotes
these; the retired form quoted the design value as though it were the outcome.

### 2 · Seven cells, regenerated and compared

| `B_max` | split | Δ (R61) | Δ (now) | CI (now) |
|---|---|---|---|---|
| 0.10 | validate | −0.08486 | −0.08486 | [−0.08509, −0.08463] |
| 0.10 | test | −0.07155 | −0.07155 | [−0.07175, −0.07135] |
| 0.10 | Culver-City | −0.07952 | −0.07952 | [−0.07986, −0.07917] |
| 0.20 (mixture) | test | −0.07166 | −0.07166 | [−0.07188, −0.07145] |
| 0.30 | validate | −0.08540 | −0.08540 | [−0.08563, −0.08517] |
| 0.30 | test | −0.07021 | −0.07021 | [−0.07043, −0.06998] |
| 0.30 | Culver-City | −0.08280 | −0.08280 | [−0.08313, −0.08248] |

### 3 · A gate for the products

`tests/test_transport_products.py`: all five `realised_*` fields present in all seven cells; a
single-threshold cell's realised fraction must equal its stored rate (they cannot differ, so a
difference means the fields came from the wrong point); the mixture's realised fraction must lie
between its components and near the design value, with a non-degenerate codeword span. Self-test:
removing a field **FIRES**, drifting a single-threshold cell's fraction **FIRES**, live cells clean.

### 4 · Three mechanism sentences, corrected against the code

* **Deployment gating.** The `0.999` mask shapes **oracle labels**; it is not a deployment-time gate.
  `rf_actions_stacked` predicts over all three actions with no hard exclusion, so the frozen selector
  is not *forbidden* the feature action — over the Rayleigh conditions evaluated here it has learned
  empirically to avoid it. The retired sentence claimed a mechanism the code does not implement.
* **Feasible set.** After masking the set is **{E, L}**, not `L` alone. The oracle does take `E`
  under Rayleigh (0.157 test, 0.133 Culver-City); that the deployed forest almost never does is the
  separate, already-acknowledged E-collapse. Merging the two hid a known limitation behind a
  physics-sounding statement.
* **The margin.** "matched-payload margin" → "margin over the nominal threshold tuned for the same
  target budget". The two arms do not spend the same payload; the retired phrase asserted an equality
  the products contradict.

All three are tracked TERMINOLOGY families with live-match zero.

## R66 (part 1) — the same-name overwrite risk is closed

Zero GPU. The figure-chain audit found the numbers correct; the defect was the *mapping*.

1. **`a2_difficulty.py` can no longer write `fig_difficulty.pdf`.** The delivered figure is built
   from the frozen product (`difficulty_frozen.py` → `results/sensitivity/difficulty_frozen.csv`),
   while the retired v3-era script wrote the **same filename** from v3-era data — one accidental run
   from silently replacing a frozen figure. The write path is removed and the script exits with the
   reason, rather than being renamed: a renamed output still invites use.

2. **The frozen builder is now a first-class entry in `tools/generate_figures.py`.** It had been
   listed as a "known gap", which is precisely how the retired script stayed the only thing anyone
   associated with that figure. Also fixed: `plot_feature_importance.py`'s header still said 65 %,
   the pre-corrigendum channel-side share; it now says 61.7 %.

3. **Two content guardrails, tracked rather than trusted.** A sentence claiming the difficulty figure
   shows improvement across all strata contradicts its own product (the easy tercile is −0.0047 on
   test); a sentence saying the channel features "contribute 61.7 % of performance" turns a Gini
   split statistic into a causal share. Both are TERMINOLOGY families, live-match zero.

**Not in this commit** (R66 items 3–5, 7): the two_regime decoupling, the second deletion round with
its `test_payload.py` migration, the four document rewrites, and the protocol split.

## R67 (a) — the two-regime arms are decoupled, and the leaky script is gone

Zero GPU. `build_two_regime_edge_clean.py` imported its SNR grid, payload constants, interpolation
bias and helpers **from `build_two_regime_edge.py`** — the leaky script it exists to replace. The
clean arm therefore could not be run, or reasoned about, without the arm that leaks, and deleting the
leak would have broken the replacement.

`baselines/importance_map_jscc/perframe/two_regime_common.py` now holds those shared pieces
(`SNR_GRID`, `PAY_L`/`PAY_C`, `TAU_GRID`, `INTERP_BIAS`, `eff_C_of`, `jscc_grid`), moved verbatim —
nothing is recomputed. Both importers (`build_two_regime_edge_clean.py`, `make_two_regime_figure.py`)
now take them from there, and `build_two_regime_edge.py` is **deleted**. Import gate PASS, no dangling
references outside the archived history.

## R67 (b) — `tests/test_payload.py` no longer names the retired policy CSV

Zero GPU. The payload audit's **data path was already frozen-replay-only**: `deployed_averages()` has
read `results/main/replay_summary.csv` since R40-6. What survived was *residue* — a dead constant, a
dead parser and two labels — all still naming `results/main/threshold_vs_rf.csv`, the retired v3
200-realisation engine's output. Residue of that kind is what makes a later deletion look unsafe, and
it was also carrying retired numbers in a docstring nobody executes.

Removed (each swept for live references first; all three were **defined and never used**):

* `THRVRF` — module-level path constant, commented "RETIRED engine; not read". Zero readers.
* `_retired_parse_paper_headline_agg()` — dead parser for `tab:headline_agg`, whose docstring still
  quoted the retired-engine pair **RF 0.251 / best-τ 0.303**. Zero callers.
* Two labels: the module docstring's "per-policy deployed mean payload (… `threshold_vs_rf.csv`)"
  bullet, whose stated share range **16–25 %** is a retired-engine figure (the frozen replay gives
  2.5–21.4 % across splits), and the `=== 3) ===` section header.

The (3) docstring's contrast now names the retired **engine**, not the retired **file**, so the entry
stays true after the file itself is deleted.

**Assertion-level evidence.** The audit prints one row per link. The HEAD version and the migrated
version were both run in place (`tests/`, so `HERE`/`P1` resolve identically) and their assertion
tables diffed: **all 33 rows byte-equal** — link text, derived, expected, result and source columns
alike. The only diff anywhere in the output is the one section header above. No assertion changed
value, tolerance, source or semantics; nothing was added and nothing was dropped. `ALL 33 LINKS
MATCH`, exit 0, before and after.

**Not done here, by design:** `results/main/threshold_vs_rf.csv` is **not** deleted, and its other
live referents (`policy_200seed.py` as generator-of-record, `results_index.py`, `a8_models.py`'s τ
comment, `results/README.md`, `docs/reproducibility.md`) are untouched. Those belong to the second
deletion round (R67 c). 19/19 gates PASS; main 16 pages, supplementary 12.

## R67 (c) — the second deletion round, and four documents rewritten

Zero GPU. Reference sweep first, over `paper/`, `docs/`, `tools/`, `tests/`, `projects/`,
`baselines/` and the READMEs, one candidate at a time; `archive/` excluded by design, since archived
history is allowed to name what it recorded.

### 1 · Deleted (18), after the sweep

Nine products and nine scripts. **No paper number depends on any of them**: `tools/p6_numbers_vs_csv.py`
locates zero literals and zero table cells in any of the nine CSVs.

| deleted | why it could go |
|---|---|
| `results/main/threshold_vs_rf.csv` | last reader removed in R67 (b); the frozen replay is `replay_summary.csv` |
| `results/main/pareto_points.csv` | read only by `a1_pareto.py` and `plot_pareto_payload.py`, both deleted here |
| `results/main/true_e2e_global_{test,validate}.csv` | read only by the four retired figure scripts; Figs. 4/5/6/8 come from `frozen_curves.csv` (P5-7 D) |
| `results/main/step4_oracle_action_dist.csv` | read only by `snr_decision_plot.py`; the frozen action mix is `action_distribution.csv` |
| `results/main/feature_importance.csv` | the non-frozen twin. `plot_feature_importance.py` and every bound number read `feature_importance_frozen.csv` |
| `results/sensitivity/ablation/a2_difficulty{,_reliable}.csv` | superseded by `difficulty_frozen.csv` (R66-1/2) |
| `results/sensitivity/c256_dominance_verify.csv` | retired since R28-2; its row stays in `tests/retired_products.md` |
| `evaluation/policy_200seed.py` | the v3 200-realisation policy engine; its draw survives in `v3_eval.py` |
| `models/train_rf_v3.py` | the v3 single full-validate fit; superseded by the LOSO freeze. No file in `results/` matched its index rule any more |
| `ablations/a1_pareto.py`, `a2_difficulty.py`, `c_channels.py` | v3-scored ablations; see the replacement column in `ablations/README.md` |
| `figures/plot_ap_snr.py`, `plot_pareto_payload.py`, `snr_decision_plot.py`, `plot_stacked_area.py` | **never invoked** by `tools/generate_figures.py`; they were named in a comment only |

`plot_oracle_action_dist.py` was on the list and is not counted: R65 already deleted it.

### 2 · What had to be handled before the deletions

Nothing was deleted while something still pointed at it as if it were live.

* **`results_index.py`** — six rules removed, one narrowed. Checked first that no *surviving* file
  matched any removed rule: the `policy_200seed` rule matched only the two CSVs deleted here, and the
  `train_rf_v3` rule matched **nothing at all**. `results/README.md` was then regenerated from the
  index (not hand-edited): `results/main/` 39 → 33 files, `sensitivity/ablation/` 8 → 6, still
  0 UNATTRIBUTED.
* **`tools/regenerate_p0_products.py`** — the `c256_dominance` job is **removed**. Deleting a retired
  product while leaving a job that rebuilds it would have resurrected it on the next regeneration
  run. The verifier script itself is kept and runnable by hand.
* **Nine narrative references in live code** repointed from the deleted *file* to the retired
  *engine* (`a8_models.py`'s τ comment, `opv2v.py`, `v3_eval.py`, `verify_c256_dominance.py` ×2,
  `verify_harm_stratum_structural.py`, `difficulty_frozen.py` ×2, `generate_figures.py`), plus two
  lines of `projects/ca_tosg/README.md`. Same rule as R67 (b): name the engine, and the sentence
  stays true after the file is gone.
* **Three records banner-marked, not rewritten** — `paper/paragraph_drafts.md` (its `src:` lines are
  dated provenance; the paragraph gate compares only prose bodies and footnotes, and passes),
  `docs/invariance_note.md` (it cites `policy_200seed.py` by *line number*, and the claim it was
  provenance for is in neither document any more), and the `docs/claims.md` row that mentions the
  C256 file — which was already bound to the regenerated product, so the deletion changes nothing.
* **`tests/retired_products.md`** gained a "deleted, not merely retired" table. The registry's
  parse rule (`p6_numbers_vs_csv.retired_products`) was re-run after editing: still 7 paths, C256
  still among them.

### 3 · Four documents rewritten

* **`paper/figures/README.md`** — the old-protocol content is gone entirely: every `../../code/*`
  path, the 2026-07-11 md5 provenance table (whose own rows said "superseded — pending P2 re-freeze")
  and every retired script. Rebuilt from `tools/generate_figures.py`'s registry and from what the two
  documents actually `\includegraphics`, with a "built but not included" section for
  `fig_decisions_budgets.pdf` and `fig_two_regime.pdf`.
* **`docs/reproducibility.md`** — the legacy §0–§5 block is replaced by a current tables map (four
  generator-owned bodies named explicitly, the rest bound through `p6_numbers_vs_csv`), a current
  figures map, and a randomness section that separates the frozen replay (`CSI_SEED=20260809`,
  `N_BOOT=10000`) from `v3_eval` (`default_rng(s)`, s ∈ 0..199) — never blend the two. The legacy
  section shrinks to a record with no runnable-looking commands. One correction landed here: the
  R62-3 status line said "All **18** gates", against the generated block's 19; it now says 19 and
  states the convention.
* **`results/README.md`** — regenerated, never edited.
* **`ablations/README.md`** — the old text described an `extra_experiments/` tree with an `out/`
  directory and an "A1–A8 + C" line-up, none of which exists. Rebuilt around the seven surviving
  scripts, each carrying its own file's PUBLICATION / DIAGNOSTIC marker, plus a deleted-experiments
  table.

### 4 · Exceptions and residue, reported rather than swept

* **Five stray PNGs** in `paper/figures/` (`fig_ap50_*.png`, `fig_ap70_*.png`,
  `fig_channel_bler_frame.png`) now have no writer. No document includes a `.png`. They were not on
  the R67 (c) list and are left in place; flagged in `paper/figures/README.md` for a ruling.
* **`docs/p6_numbers_vs_csv.md` is stale on the committed tree, and this predates R67.** A fresh run
  reports **MISS 1** (claim `cca44e6`, the literal `0.007` in §Boundaries, bound to
  `transport_replay_ci.csv` + `intersection_gt_track.csv`) and 297 table cells, against the committed
  report's MISS 0 / 260. `p6_numbers_vs_csv.py` is **not** one of the 19 gates, which is why the
  suite stayed green through it. Not touched here — it is neither caused by nor in scope for this
  batch — and left for a ruling.

19/19 gates PASS; main 16 pages, supplementary 12.

## R67 (d) — the protocol is split: live protocol vs this change-log

Zero GPU. The file had grown to **6,550 lines**, of which the dated revision batches R17 → R67 were
**4,024** — 61 %. A reader looking for "what the protocol *is*" was reading, by volume, mostly a
record of what it *used to be*, with every entry's gate counts, page counts and file paths frozen at
its own date.

### 1 · The nine anchors, inventoried BEFORE the cut

The 18th gate (`tests/test_protocol_reconciliation.py`) pins each registered verdict to a
`protocol_probe` substring that must still be present in the record. A probe that vanishes makes the
pair **stale**, which is a FAIL by design — so the anchors decide where the gate has to read.

| id | verdict | probe line(s) in the pre-split file | lands in |
|---|---|---|---|
| `anchor-insensitivity` | false-as-written | 1289 | **live protocol** |
| `c256-dominance` | superseded | 4266, 4847 | history |
| `latency-budget` | superseded | 5188, 5189 | history |
| `reference-tensor` | false-as-written | 5252 | history |
| `shared-backbone` | false-as-written | 5267 | history |
| `headroom-fov` | false-as-written | 5755 | history |
| `same-transport-claim` | false-as-written | 6069 | history |
| `per-frame-accounting` | false-as-written | 6226 | history |
| `w2c-no-verdict` | false-as-written | 6247 | history |

**Eight of nine cross the cut.** Splitting without repointing would have failed the gate eight times
over — which is the gate working, not the gate breaking.

### 2 · Where the cut went, and why it is not stylistic

Boundary: the end of Appendix F (line 2523), immediately before `## Change-log R17`.

* **Live** (`docs/experiment_protocol.md`, 2,547 lines): §1–§10, the pre-registered protocol-revision
  block, Appendices A–F.
* **History** (this file, 4,057 lines): the dated batches R17 → R67, under a NOT-QUOTABLE banner.

The rule is **"a block that code parses stays live"**, and the boundary was chosen to satisfy it, not
the other way round. Seven modules open the protocol; the parsed targets are
` ```json CATOSG-CANDIDATES ` (§6, md5-pinned by `tests/test_data_leakage.py` and by every generated
config), ` ```json CATOSG-P4A ` (**line 551 — inside the pre-registered change-log block, which is
precisely why that block stayed live**), ` ```json CATOSG-FEATURE-ABLATION ` (Appendix E), §3, §4 and
Appendix B's prediction table. All six were re-parsed out of the live file after the cut and all six
md5s are unchanged — proven by `manifest relpaths` passing, since it re-hashes each block a committed
config claims to derive from.

### 3 · The repointing, and the control that proves it is load-bearing

`PROTOCOL` became `PROTOCOL_PARTS`: the gate reads **both halves, concatenated**, and a missing half
raises rather than contributing an empty string — a record that cannot be read must not silently
satisfy an anchor check.

Re-run immediately after repointing, then the control, reading each half alone:

| record read | failures | stale anchors |
|---|---|---|
| live protocol only | 8 | `c256-dominance`, `reference-tensor`, `shared-backbone`, `headroom-fov`, `w2c-no-verdict`, `same-transport-claim`, `per-frame-accounting`, `latency-budget` |
| history only | 1 | `anchor-insensitivity` |
| **both (as repointed)** | **0** | — |

### 4 · A pre-existing self-test failure, found by this step and fixed

`python tests/test_protocol_reconciliation.py --self-test` **has been exiting 1**. Its injection dict
carried `where2comm-baseline`, whose row was retired from `tests/protocol_claims.md`; a probe with no
row can never fire, so the self-test reported `DOES NOT FIRE` and failed on every run. `verify_results.py`
invokes the gate *without* `--self-test`, which is why the suite stayed green through it — the same
shape of hole R43-4 closed for generators. The stale key is removed and the self-test now **derives**
the check: any probe key with no matching row is reported and exits 1, so the dict cannot drift from
the table again. Self-test exits 0, with all five injections and the stale-anchor control firing.

**Residue, reported not fixed:** four of the nine rows (`headroom-fov`, `w2c-no-verdict`,
`same-transport-claim`, `per-frame-accounting`) still have no injection probe, so the self-test proves
5 of 9. Writing four new probes was not in this batch's scope; flagged for a ruling.

19/19 gates PASS; main 16 pages, supplementary 12.

## R68 — the three residues closed, and the report that nobody read becomes a gate

Zero GPU. This batch exists to clear the three items R67 left flagged for a ruling. Two of the three
turned out to be worse than "residue", and one turned out not to exist.

### 1 · The five "stray PNGs" were never in the repository

`.gitignore` line 30 is `*.png` — "only the .pdf/.svg ship". The five files R67 (c) reported as stray
and left "in place for a ruling" were **untracked all along**, so there was no repository state to
rule on and the R67 (c) note was wrong to imply one. They are gone from the working tree
(`fig_ap50_{awgn,rayleigh}.png`, `fig_ap70_{awgn,rayleigh}.png`, `fig_channel_bler_frame.png`);
`fig_ap70_*` never had a PDF counterpart at all — the AP@0.7 pair was never a delivered figure. The
one PNG a full figure run still writes, `fig_feature_importance.png`, is ignored and stays ignored.
`paper/figures/README.md`'s PNG section is rewritten to say this instead.

### 2 · The MISS was real, and the sentence was wrong

**Diagnosis: the binding was fine; the number was not.** Claim `cca44e6` printed "Under ideal delivery
the two are within $0.007$ AP@$0.5$ of each other". Both bound products exist and are correct. The
literal is a **derived bound** — no CSV stores a gap column — and re-deriving it from
`results/diagnostics/intersection_gt_track.csv` gives, over the six (split, budget) ideal-delivery
cells:

| split | `B_max` | Where2comm | CA-TOSG-RF | gap |
|---|---|---|---|---|
| culver | 0.10 | 0.89572 | 0.89508 | +0.00064 |
| test | 0.10 | 0.94358 | 0.94490 | −0.00132 |
| validate | 0.10 | 0.91519 | 0.90883 | +0.00636 |
| culver | 0.30 | 0.89885 | 0.89864 | +0.00021 |
| test | 0.30 | 0.94417 | 0.94363 | +0.00054 |
| validate | 0.30 | 0.91653 | 0.90930 | **+0.00723** |

max |gap| = **0.00723 > 0.007**. The printed figure was that bound **rounded DOWN**, which claims
more than the cells support — and the supplementary was already printing `+0.00021`--`+0.00723` twice
plus a `$+0.00723$` table cell, so the two documents disagreed at full precision while every gate
stayed green. `main.tex` now prints `0.00723`.

Registered, not patched: `docs/canonical_quantities.md` gains an *ideal-delivery AP gap bound* row and
`tests/test_canonical_quantities.py` re-derives it at gate time — cell count, the bound, both span
endpoints, and a **context-anchored** ban on the rounded-down form. Context-anchored because `0.007`
also occurs as a legitimate CI endpoint (`$[-0.007,-0.001]$`) in the supplementary for a different
quantity, and a bare fingerprint fires on it — the same narrowing the `0.248` payload family needed.
Negative control: restoring `within $0.007$` makes the gate FAIL; the corrected text passes.

**297 vs 260 table cells, accounted for exactly.** The committed report was last regenerated at
**R57** (`66a6dfb`), ten batches ago. Re-running p6's own tokeniser over both revisions of the two
documents attributes the whole delta to **one table**:

| table | R57 cells | now | delta |
|---|---|---|---|
| `tab:w2c_transport` | 0 | 36 | **+36** |
| every other table | unchanged | unchanged | 0 |
| total scanned | 264 | 300 | +36 |

located went 260 → 297 (+37) and declared-derived 4 → 3, because one `tab:headline` cell — `0.8177` —
stopped being declared-derived and became *located*: `results/diagnostics/transport_replay_culver_thr0.013_B0.30.json`,
a product R58 added, happens to carry that value. `DERIVED_TABLE_CELLS.json` itself is byte-identical
to R57. +36 = +37 − 1.

**The report is now a gate.** `tools/p6_numbers_vs_csv.py` always wrote its report and **always
returned 0**, so `MISS 1` could sit unread for ten batches with a suite that was green by
construction. The build is split out of `main()`; `--check` writes nothing and FAILS on a MISS, on an
unlocated table cell, and on the committed report drifting from a fresh build — the same family as
`check_figure_consistency.py --check`. Registered as the 19th gate (**20** checks with the
fingerprint sweep). It costs ~85 s, which is the price of it being real. Its self-test gained a drift
control: a one-line change to the report must be detected.

### 3 · The reconciliation self-test now proves 9 of 9

The four rows added after R45-6 (`headroom-fov`, `w2c-no-verdict`, `same-transport-claim`,
`per-frame-accounting`) had no injection probe, so R67 (d)'s repair proved 5 of 9. Each now has a
probe written to match its own `retired_regex`, and every one **FIRES** on injection and goes
**silent** on removal — both directions printed per row, because a gate that stays red after the fault
is withdrawn is not discriminating, it is just red. Coverage is asserted in **both** directions: a
probe with no row already failed since R67 (d); a **row with no probe** now fails too, so adding a
pair to `tests/protocol_claims.md` forces adding its injection.

### 4 · A regression from R67 (c), found by this batch and fixed

R67 (c) added a provenance note to the `docs/claims.md` collaboration-harm row saying the second
triple "previously came from the retired c256_dominance_verify.csv". `tools/audit_claims_evidence.py`
extracts `[\w./-]+\.csv` tokens from the evidence cells and treats each as a **cited** file; with that
file's index entry removed in the same batch, the lookup failed and the claim reported **UNRESOLVED**.
It went unnoticed because `docs/claims_evidence_audit.md` was itself stale — the same disease as the
p6 report, one file over. The note now names the product without an extension. Audit: **110 claims,
57 FROZEN / 53 ANALYTIC, 0 UNRESOLVED, 0 PENDING, 0 STALE, 0 LEGACY.**

**Rule this batch adds: a record of a deleted product must not be written in citation form.** Two
tools parse evidence cells for filenames; a historical mention that looks like a citation becomes one.

20/20 gates PASS; main 16 pages, supplementary 12. No cleanup items remain open.

## R69 — the difficulty figure comes off the artefact tier; resurrection becomes a gate

Zero GPU. **No experimental number moved in this batch**, by instruction. Everything below is a
reproducibility, hygiene or status change; the one document edit is a status section, not a result.

### 1 · `fig_difficulty.pdf` is now drawn from the committed CSV alone

`difficulty_frozen.py` both computed `results/sensitivity/difficulty_frozen.csv` **and** drew the
figure, so `tools/generate_figures.py difficulty` opened `data/p2/p2_grid_*.csv`, the frozen
`selector_B0XX.pkl` and `FROZEN_MANIFEST.json` — all git-excluded. A figure whose data is committed
was not redrawable from the committed tree, and it was the only entry in the driver's list like that.

`figures/plot_difficulty_frozen.py` now owns the PDF and reads only the CSV; it imports nothing from
the evaluation package, `deployment` included, because importing the compute side back would quietly
restore the dependency. The driver entry points at the plot script. The condition in the title is read
**from the CSV** rather than passed in, and rows spanning more than one (channel, SNR) are an error —
a caption saying "AWGN 16 dB" over rows computed elsewhere is exactly what the figure-consistency gate
exists for.

**Clean-clone verification, actually run.** A `git clone` of this branch into a scratch directory
(no `data/`, no `.pkl`, no grids) with the three changed files copied in:

* `python tools/generate_figures.py difficulty` → **exit 0**, `fig_difficulty.pdf` written.
* The resulting PDF is **byte-identical** to the one produced in the full tree after normalising the
  PDF `/CreationDate` — 20,472 bytes both sides, 0 residual differing bytes.
* Negative control, same clone: the pre-R69 compute script stops at
  `P2-B FUSE: budget 0.10 model absent: data/p2/selector_B010.pkl`.

### 2 · Resurrection capability removed, then gated

R67 (c)'s sweep asked "does anything **read** this?" and never "can anything **write** it?" — the
wrong half. Two live scripts could still rebuild a deleted product:

* **`action_dist.py` → archived** to `archive/retired-scripts/` (with a README for the directory).
  Three retirements in one file: the v3 action set `{L, C16, C256}` rather than the deployed
  `{E, L, F}`; pre-restructure absolute paths; and an output deleted in R67 (c). No live caller.
* **`verify_c256_dominance.py` → kept, trimmed.** The judgement call, with its reason: the **algebra**
  is convention-independent and is live evidence for a delivered sentence — the C256 paragraph states
  the identity `eff_C256 − eff_C16 = (comp − ego)(b16 − b256)` — so archiving the whole file would
  have removed the only programmatic check on a sentence in the paper. The **CSV write** and the
  **200-realisation deployed-selector count** went: the write rebuilds a retired product, and the
  count loaded `data/selector_rf.pkl`, the v3 selector the P2 freeze superseded. Under the frozen
  action set C256 is not a predictable class at all, so that count is structurally zero rather than
  measured. The file now writes nothing (0 write calls) and exits 1 when it cannot verify.

**New gate (21st): `tests/test_no_retired_writes.py`.** Every path in the *product column* of
`tests/retired_products.md`, against every live `.py` parsed with `ast`: a file fails if it names a
retired product in a non-docstring string **and** contains any write primitive. Docstrings are exempt,
so a script may explain its own history. Deliberately over-approximating — resolving a path through
`os.path.join`, variables and f-strings is not decidable, and a resurrection gate defeatable by a
variable is not a gate. `archive/` is not scanned; that is what archiving is for.

*A first draft of the parser swept every `results/...` path in the register, pulled in the "what
replaced it" column, and reported 20 violations — every one a live generator writing its own product.
The parse is anchored to the first cell of a table row, the same rule
`p6_numbers_vs_csv.retired_products()` uses, and refuses to run if it parses zero rows.*

Controls: self-test plants a script writing a retired path (**FIRES**) and the same name in a
docstring only (**silent**), and removes the planted file. Historical control — restoring the two
pre-R69 scripts makes the gate **FAIL on both**, naming the exact write calls.

### 3 · `docs/experiment_protocol.md` gains a status section, and stops claiming stale status

The file was written as a *contract*, in the future tense, before the rebuild ran. It then kept saying
so. New **`## Current authoritative state`** at the top: splits, action set `{E, L, F}`, the
train → freeze → replay chain with its actual commands, the live result files, verification state,
and which parts of the file are historical. Five stale-status sites corrected, each pointing at it:

| site | was | now |
|---|---|---|
| §3 deployment eval | "**P2-B new deployment script (to be built)**" | names `tools/evaluate_selector.py`; notes the legacy engine it was fused off from no longer exists |
| pre-registered change-log preamble | (nothing) | a "record of decisions, not a status report" banner |
| Appendix A "Open P5 items" | three open items incl. "main.tex still carries the legacy-pipeline numbers" | struck through and marked **CLOSED**, with what replaced each |
| Appendix A latency item | the retired v2 measurement, "update at P5" | closed; the paper quotes the frozen row, re-derived at gate time |
| Appendix D | a keep-register read as current | HISTORICAL INVENTORY banner: pre-restructure paths, superseded by two deletion rounds |

`projects/ca_tosg/configs/` regenerated from the protocol — a §3 edit changes the section hash four
configs derive from, which the `manifest relpaths` gate caught immediately. Only the hash moved; every
derived value is unchanged.

### 4 · Two invalid escapes, and one obstacle written down instead of fixed

`tests/test_paragraph_insert.py` and `tests/test_result_consistency.py` carried LaTeX/regex
backslashes in their module docstrings (`\s`, `\p`) — a `SyntaxWarning` today, a `SyntaxError` from
Python 3.12. Both docstrings are now raw strings; no text changed. Zero invalid-escape sites remain
in the live tree.

**33 scripts hard-code `/home/josh/…/OpenCOOD` or the pre-restructure `peiyi_work/paper1/…` layout**
(19 `projects/`, 12 `baselines/`, 2 gate scripts). Not parameterised: rewriting 33 path constants
touches the code that produced the frozen products, and this batch was scoped to move no experimental
number. Recorded in `docs/reproducibility.md` as what it is — a real obstacle to third-party
reproduction from raw OPV2V, affecting **no delivered result** (every one of them is an artefact-tier
input whose products are committed and re-derived at gate time) and **no content-tier check** (all 13
resolve relative to the repository root).

21/21 gates PASS; main 16 pages, supplementary 12.

## R70 — the last hand-written counts are taken over by their generator

Zero GPU. **No experimental number moved.** Receipt: `results/` 0 files changed, `main.tex` 0,
`supplementary.tex` 0, `docs/claims.md` 0, `docs/p6_numbers_vs_csv.md` 0.

### 1 · The three sites named, and two more the sweep found

| file | was | now |
|---|---|---|
| `docs/reproducibility.md` | "All **20** checks run and pass on the full experiment machine (19 gates plus… R67 (c) corrected this line from 18 to 19; R68 added…, taking it to 20.)" | "All **21** checks run and pass on the full experiment machine." — the running commentary is gone with the hand-editing that produced it |
| `tools/verify_results.py` | "the **two** artefact-tier gates fail loudly" | "the **eight** artefact-tier gates fail loudly" |
| `docs/installation.md` | "its **two** artefact-tier gates fail loudly" | "its **eight** artefact-tier gates fail loudly" |
| `README.md` *(not on the list; found by the sweep)* | "# all **11** gates (--content-only = the **7** a clean clone can run)" | "# all **21** gates (--content-only = the **13** a clean clone can run)" |
| `docs/reproducibility.md` *(R69's own sentence)* | "All 13 content-tier checks run on the committed tree" | same numbers, now generated |

The README line was stale by a factor of two and had been since the suite passed eleven. It is the
same defect as the two named sites, so it is fixed with them rather than left for a sixth round.

### 2 · Root cause closed: nothing states a gate count by hand any more

`tools/build_gate_counts.py` governed **four** sites; **six more were hand-written**. It now governs
**ten sites across five files**, all computed from `verify_results.GATES` plus the one gate the
runner executes inline:

* `docs/reproducibility.md` — the tier block, the six-step table row, the full-run status sentence,
  the content-tier sentence
* `tools/verify_results.py` — the usage line, the `GATE-COUNT-LINE`, the artefact-tier sentence
* `docs/installation.md` — the artefact-tier sentence
* `README.md` — the command comment
* `docs/experiment_protocol.md` — the `**N checks, all passing**` row of *Current authoritative
  state*, which R69-3 had typed in three batches ago. **Found by R70's own sweep of R70's own work**,
  which is the argument for sweeping rather than working from the list of sites someone remembers.

**Every pattern must match exactly once.** Zero matches is now a hard failure with the reason
printed, not a silent no-op: a sentence reworded out of the tool's reach would otherwise become a
hand-written count again, invisibly. That is R43-4's lesson applied to this tool.

The artefact-tier count is stated as a **word** ("eight"), derived from the same arithmetic
(`total − content`), so the two prose sentences stay grammatical without a second source of truth.

**`--self-test`** perturbs each governed file and requires the check to fire on it. The first run
reported `docs/installation.md → DOES NOT FIRE`: the perturbation bumped **digits**, and that file
states its count as a word, so the self-test was not testing the file it claimed to. The perturbation
now corrupts both forms. All five FIRE; a reworded sentence FAILS loudly. `build_gate_counts --check`
is already a member of the `generators --check` gate, so drift is red on every run.

**One more emitter, silenced rather than counted.** `tools/build_pending_rulings.py` wrote "…and
re-runs all nine gates" into every report it generates. The suite has been 11, 18, 19, 20 and 21
since. The sentence now says "the full gate suite" and carries no number. The two R17-C reports it
already wrote keep their text: they are dated records, not status.

Live-tree sweep afterwards: the only remaining `N gates` strings are the generated ones, two dated
R17-C reports, comments quoting the retired wording, and this NOT-QUOTABLE file.

### 3 · The tally this closes

A hand-written gate count went stale five times — R46-4 (which built this tool), R47-5, R67 (c),
R68, and R70. Each fix corrected the sites someone was looking at. This one enumerated them.

21/21 gates PASS; main 16 pages, supplementary 12. Focus returns to the paper and submission.

## R71 — the counting tool miscounted itself

Zero GPU, two comments. **No experimental number moved; no behaviour changed.** The `GOVERNED`
tuple, every regex and every generated string are byte-identical to R70 — this batch edits prose
inside `tools/build_gate_counts.py` and one registry description.

R70's docstring said the tool "governed four sites and **five more were still hand-written**", and
the constant below it said "R70: five more sites". Both were written while the count was five, and
both stayed at five after the sixth site — the protocol's `**N checks, all passing**` row — was
brought in later **in the same batch**. 4 + 6 = the ten sites R70's own list enumerates, so the
docstring contradicted the list six lines under it.

**The tool built to stop hand-written counts going stale carried a hand-written count of its own,
and it was wrong within minutes of being written.** That is the finding, and it generalises:

> A count in a comment is exactly as untrustworthy as a count in prose. The only difference is that
> no gate reads a comment — which makes it worse, not better. If it can be generated, generate it;
> if it cannot, expect it to be wrong and keep it out of anything a reader has to rely on.

The authoritative list has been `GOVERNED` all along — the code builds it, `--check` enforces it,
and `--self-test` proves each entry fires. The prose above it is commentary, checked by reading. It
now says "six more (4 + 6 = the ten listed below)" and records where the five and the sixth came
from: five from sweeping the live tree, the sixth from sweeping R70's own work afterwards.

Also corrected: `tests/test_generators_check.py` described this generator as owning "the gate counts
in reproducibility.md, verify_results.py, installation.md and README.md" — four of the five governed
files, missing `experiment_protocol.md`. The registry description now matches what the tool does.

21/21 gates PASS; main 16 pages, supplementary 12.

## V2-R1 — stop-work on v1, the plan-A protocol locked, and the sanity fuse held

Zero GPU on anything but the sanity check, which spent **0.96 h wall-clock** against a `<1 GPU-h`
estimate. **The v1 manuscript was not touched**: `paper/main.tex`, `paper/supplementary.tex`, both
PDFs and every `results/main/**` product are byte-identical to `400bfb6d`.

### 1 · Stop-work order

`docs/STOP_WORK_v1_freeze.md`, in force from **`400bfb6d`**. The manuscript, abstract, headline
tables, results figures, Conclusion and page count take zero changes until plan A's re-freeze, and
**no new gate may be added for a v1 result** — the suite stops at 21. v1 is *frozen*, not withdrawn:
nothing is deleted, and its disposition is decided in the protocol, not by the freeze.

**An operational trap, found the same day:** `tests/test_compile.py` rewrites both PDFs every run,
and it is one of the 21 gates — so `verify_results.py` mutates two frozen files as a side effect. The
rewritten bytes are not content-identical even after normalising `/CreationDate`. The order now says
to `git restore paper/*.pdf` after any full gate run, and this batch did exactly that.

### 2 · Sanity check — the fuse held, and the result is better than the fuse required

`projects/ca_tosg/evaluation/v2_single_vehicle_sanity.py`, 220 validate frames sampled every 9th so
that **all nine scenes** are covered (the first 200 consecutive frames would have been one scene).

| | cooperative | single-vehicle |
|---|---|---|
| AP@0.5 (global sort) | 0.91434 | **0.69147** |
| AP@0.7 | 0.86487 | 0.57606 |
| mean per-frame F1 | 0.91739 | 0.77555 |
| boxes/frame mean / median / max | 28.23 / 25 / 57 | 22.41 / 16 / 47 |

GT/frame 27.75, CAVs/frame 3.89 (max 7), score threshold 0.20 (the checkpoint's own default).

**Fuse: stop below half the frozen v1 ego-only AP@0.5, i.e. below 0.30675. Measured 0.69147 —
intact, by a factor of 2.25.** And the stronger reading: the single-vehicle arm of the
attentive-compression checkpoint **exceeds v1's frozen ego-only AP@0.5 of 0.61350**, which was
produced by a *different* (late-fusion) checkpoint. The detection head does not depend on cooperative
fusion to work, so plan A's premise holds.

**Why no forward code was touched.** `AttFusion` regroups by `record_len` and self-attends within each
group; with `record_len = [1]` the softmax is over one element, so `attn == 1.0` and
`context == value` — the fusion is an **exact identity**. Single-vehicle mode is therefore obtained
purely by feeding one CAV's voxels, not by editing the model. That was the instruction and it was
also the correct engineering.

### 3 · `docs/unified_branch_protocol_v2.md` — locked before any main result

Sixteen sections, hashed per section into `results/manifests/V2_PROTOCOL_MANIFEST.json` by
`tools/build_v2_protocol_manifest.py`, which reads the lock state **out of the document's own table**
so the manifest cannot claim a section is locked while the document says otherwise. Protocol sha256
`26202ce6ee251602574d7eb4ab86140f1a445e8199a6e70a2304dcde19c79111`.

**10 LOCKED · 3 PARTIAL · 2 NOT LOCKED.** Covered: the single checkpoint by hash; the three actions
with frozen score threshold 0.20, NMS 0.15 and a written cross-vehicle de-duplication rule; unified
FOV and GT; `B_F` from the **measured** 739,200-element bottleneck with stated quantisation width,
packet size and header; per-frame `B_L,t` with the box container itemised to 184 bits; fragmentation
with partial recovery as the main transport and all-or-nothing demoted to a sensitivity; scene-level
bootstrap as the confirmatory unit; the v1 23-cue set carried over with its reason; success defined
as **design correctness with a written ban on judging by whether the numbers improve**, plus
pre-registered wording for all three outcome cases and a Culver-City sentence in each.

**What is deliberately NOT locked, and why that is the honest state:** §11 (the supervisor's 12-item
regeneration list) and §12 (P1-1…P1-8, P2-1…P2-6) exist only as labels in the instruction — their text
is not in this repository. They are recorded as `PENDING` with the right shape and **no invented
content**, because a fabricated pre-registration is worse than an empty one. §2 (the E-codec
question), §3 (`w`, `P`, `H_F`) and §10 (whether the ≥10 % criterion survives a per-frame `B_L`)
carry explicit one-line rulings for Josh.

**No mainline GPU runs while any section reads NOT LOCKED.** That is written into the protocol, the
handoff banner and this entry.

### 4 · Cost — and the unit is wrong

The micro-benchmark changed the shape of the answer: a cooperative forward is **0.0505 s**, a
single-vehicle forward **0.0293 s**, and loading the frame they need is **1.89 s** from `/mnt/h`.
**This workload is I/O-bound by about forty to one.** All of tier A is ~**0.2 h of actual GPU
computation**; everything else is waiting for data, and four DataLoader workers bought almost nothing.

| tier | conservative | typical | worst |
|---|---|---|---|
| A — mainline re-freeze | 1.1 | **4** | 8.5 |
| B — transport main-protocol | 0.3 + a tier-A pass | **5** | 30 |
| C — external arm | 1.5 | **4** | 40+ |

Hours are **wall-clock on this machine**, not GPU-hours, because that is what a run will cost.
Two recommendations follow and neither needs approval: copy the splits off the Windows mount (a 2.2×
spread between warm and cold cache was measured, and it is pure I/O), and **do not price tier B off
this estimate** — measure the tail-only re-decode fraction first, since that one number moves tier B
between 0.3 h and 30 h.

21/21 gates PASS. Main 16 pages, supplementary 12 — unchanged, and the PDFs restored to `400bfb6d`.

## V2-R3 — rulings written in, payload chain derived, and one section that cannot lock

Zero GPU. **The v1 manuscript was not touched**: `paper/*.tex` 0 changes, both PDFs 0,
`results/main` 0.

### A-1 · Packet parameters — single source, and the honest provenance

Full-tree sweep for the retired pair (`1500 B`, `12,000 bit`, `160 bit`): **zero hits**. No V2-R2
commit exists on this branch either.

**Where 8,000 / 320 came from, since A-1 asks:** this executor wrote them in **V2-R1, commit
`2c8378d`**, in a table column headed **"proposed"**, with its own stated reasons — an MTU-scale
packet and an ordinary IP/UDP/application header. **They were never transcribed from a supervisor
text.** So the divergence from V2-R2's 1500 B / 160 bit is **executor judgement, not transcription**,
and C-2 has since ruled the same three values independently. Recorded in §3.3 rather than left as
folklore.

### B-1 · `B_box` — the value did not change, the basis did

The V2-R1 field table summed to **144 bits** and was labelled 184. That was an **arithmetic error**,
not a measurement. The fix was to ask what an ETSI CPM object container must carry, which supplied
**planar velocity (2 × 16) and an object ID (8)**; 144 + 32 + 8 lands back on 184.

**That coincidence is a coincidence, not a verification.** The two fields were added because the
standard container has them — not because 184 needed defending. The protocol accordingly does **not**
say 184 is "verified" or "confirmed", and it now carries a standing rule: **no field may ever be
added or removed to preserve a number already written.** If a future correction moves the total, the
total moves.

### D-1 · `B_F` derived from `N_cw`, and the padding that the direct route hides

`tools/v2_payload_chain.py` prints every step and refuses to finish if the identity fails:

```
739,200 elements x 8 bit            = 5,913,600 info bits
739 full packets (8,000 b) + tail 1,600 b;  740 x 320 = 236,800 header bits
full packet 8,320 b -> ceil/500 = 17 cw  (x739)
tail packet 1,920 b -> ceil/500 =  4 cw  (x1)
N_cw = 12,567
B_F  = 12,567 x 1000 / 4 / 1e6 = 3.14175 Msym/frame
```

Identity `B_F ≡ N_cw × n / log2 M / 1e6`: **PASS**. The forbidden direct route gives **3.07520**; the
**codeword-padding gap is +0.06655 Msym (+2.164 %)** — reproducing the reference estimate in the
instruction to all printed digits, and demonstrating exactly why D-1 bans the direct route.

β tiers: **0.31418 / 0.62835 / 0.94252** Msym. Ladder step (one codeword) = 0.00025 Msym; the tiers
are 1,257 steps apart, so codeword granularity does not blur them.

### D-2 · L on the same chain — and its reliability is computed, not assumed

`N_cw,L` ≈ **9–12** codewords against F's **12,567** — a factor of ~1,300 fewer chances to fail. That
is *why* L is reliable, and the protocol now says so instead of assuming `BLER_L`. Over the 220
sanity frames (ego box counts as a **proxy** until work package 4 produces the collaborator's):
`B_L` mean **0.00235 Msym = 0.75 % of the β = 0.10 budget`. The v1 all-or-nothing model and the
`BLER_L` grid are demoted to sensitivity arms; **P1-6 is closed by this**.

### Rulings written in

**C-1** E keeps the internal AutoEncoder (it is network forward path; bypassing it would break the
one-checkpoint control) and bypasses all communication coding; `B_E = 0`; the 2-bit request is a
fixed control overhead charged to no action. **C-2** `w`/`P`/`H_F` = 8 / 8,000 / 320, with the
partial-recovery rules written out to six numbered points so no implementation choice is left open.
**C-3** primary criterion entered verbatim, and the **primary-endpoint change is registered**:
nominal-τ → budget-feasible comparator, legitimate because **not one v2 number exists yet**, and
noted as making the bar **harder**, with reverting forbidden. **B-2** one ego + one collaborator, the
v1 P4-C nearest-collaborator rule quoted **in full** rather than named, `739,200` charged once per
frame, multi-collaborator demoted. **B-3** β = {0.10, 0.20, 0.30}, primary cell renamed *Test at
β = 0.20*. **B-4** int8 executed for real, with the ambiguity closed in three lines: the
collaborator→ego bottleneck is quantised, the ego's own features are not, E/L transmit no tensor;
"per-branch scale" defined as three symmetric scalars `max|x|/127`, validate-calibrated, frozen,
pre-shared.

**D-3** splits the E-collapse diagnostic into a **learning** question and a **design** question with
both wordings fixed now, and forbids merging them — `ρ_E ≈ 0` has an economic explanation when L
costs 0.75 % of the budget. **D-4** records the "β ≈ the allowed F-request rate" reading as
**explicitly unverified**, admissible only after checking realised `ρ_F` against β.

### §11 · Twelve work packages, thirteen product rows, and a provenance correction

The twelve titles are recorded verbatim; **their bodies are not in this repository**, so each carries
an *inferred* scope column marked as inferred.

**Correction that has to be said plainly:** the instruction calls the thirteen rows "P0-3 的 13 行
verbatim 产物清单". **They are not verbatim P0-3.** This executor wrote them in V2-R1 as a derived
dependency order and said so at the time. They are kept, clearly labelled, and will be replaced if
P0-3's actual lines differ.

The bidirectional mapping is complete: **all thirteen rows map to a package**; **package 6 (cue
regeneration) maps to nothing**, because the thirteen-row list omitted it — the omission the
instruction predicted, now explicit. Package 1 has no product row by design: it is a run-time
invariant, not a file.

### §12 · BLOCKED — and this is the stop

F asks for the supervisor's two tables (P1-1…P1-8, P2-1…P2-6) to be entered **verbatim, row by row**.
**Those tables are not in this repository and were not in the message.** Transcribing tables that
were never supplied would be fabrication, and a pre-registration is the last place that belongs. The
section keeps the correct shape with `TEXT REQUIRED` markers and **stays NOT LOCKED**.

**Manifest: 14 LOCKED, 0 PARTIAL, 1 NOT LOCKED.** Protocol sha256
`d5bd093ba2e4e3d92b555924dd5fdc86d43d9c4af7c501b3ed2207f37ebc576e`.

Per G-9 and the protocol's own rule, **mainline Tier A does not start.** Step 8's precondition
("以上全绿") is not met, and §12 is the only thing not green. It needs text, not work.

### Step 7 · Tail-only re-decode fraction, zero GPU

Parameter shares of the modules a codeword erasure forces to re-run (AutoEncoder decoders +
AttFusion + deblocks + heads) against the whole network: **842,384 / 7,112,752 = 0.118**, against the
0.15 the V2-R1 cost model assumed. **Parameters are a proxy for compute, not compute** — the deblocks
are transposed convolutions over the full BEV grid and are compute-heavy for their parameter count,
so the wall-clock `f_tail` is expected **higher** than 0.118. A ~10 s timing run would settle it and
is the right thing to do before tier B is priced.

### Not done, and why

**Step 6 (int8 scale calibration + clean-delivery AP/F1) was not run.** It requires a GPU pass over
validate, and this batch is specified as zero-GPU through step 7. It is also downstream of a protocol
that is not fully locked. It is ready to run the moment §12 lands.

21/21 gates PASS; main 16 pages, supplementary 12; PDFs restored to the freeze.

## V2-R4 — §11/§12 entered verbatim, protocol fully locked, int8 costs nothing measurable

**15/15 LOCKED, 0 NOT LOCKED.** Protocol sha256
`5577655a019d404ad3b5fb41756c976054a9959f86897f4431194e92dbd18d13` (was `d5bd093ba2e4…`).
The v1 manuscript was not touched: `paper/*.tex` 0, both PDFs 0, `results/main` 0.

### The 13-row attribution, settled by diff

V2-R3 reported that this repository's thirteen product rows were **not** P0-3 and said it could not
check, because P0-3's text was not here. It has now been supplied. **Row-by-row diff: 0 of 13 match.**
They are different lists that happened to share a length — P0-3 enumerates *what plan A invalidates*,
the V2-R1 table enumerated *a dependency order for re-deriving things*.

**P0-3 is authoritative and has replaced it** (§11.1, verbatim including its binding last line: one
complete re-freeze, bundled, with no old number kept because it "looks like it didn't change much").
The superseded table is retained at §11.4, labelled executor-derived, not deleted and not cited. The
twelve work-package bodies are likewise entered verbatim, replacing the `inferred` column.

### The mapping, and what it found this time

**All thirteen P0-3 rows map to a work package.** Four packages map to no P0-3 row — 1, 2, 6 and 8 —
and that asymmetry is the reason both lists are kept: P0-3 lists *old results that die*, the packages
list *work that must happen*. Three of the four produce things v1 never had (run-time invariants,
per-agent bottlenecks, transport products under partial recovery) and so cannot appear on a list of
invalidated v1 outputs.

**Package 6, cue regeneration, is the one that matters.** It is unmatched for a different reason: the
23-dimensional cue vector **did** exist in v1, and P0-3 does not list it — yet package 6 requires
every cue value depending on the new ego detections to be updated. **A cue set carried over
unregenerated would silently feed v1 detections into a v2 selector.** V2-R3 predicted this gap
against the derived list; it survives against the verbatim one, and is now flagged permanently.

### Section hashes: exactly three moved

§11 `eb79012f…` → `00b84fc4…`, §12 `PENDING` → `67cb50b5…`, §16 `d09229c1…` → `9c76ae43…`.
**The other twelve are byte-identical**, which is the receipt that V2-R4 changed only what it should.

### Step 4 — int8 scales calibrated on validate, frozen, and the loss measured

220 validate frames, every 9th so all nine scenes contribute, ego + one collaborator. Three symmetric
per-branch scales `s_b = max|x_b| / 127`, taken over every non-ego CAV's bottleneck so the scale is
conservative and independent of which collaborator the selection rule picks:

| branch | max\|x\| | `s_b` |
|---|---|---|
| 0 | 9.409498 | 0.07409054 |
| 1 | 13.652488 | 0.10749990 |
| 2 | 2.453234 | 0.01931680 |

Frozen into `results/manifests/V2_INT8_SCALES.json`. **Clean delivery, float vs int8, same frames:**

| | float | int8 | quantisation loss |
|---|---|---|---|
| AP@0.5 | 0.85489 | 0.85486 | **+0.00003** |
| AP@0.7 | 0.75119 | 0.75137 | **−0.00018** |
| mean per-frame F1 | 0.88808 | 0.88828 | **−0.00020** |

**int8 costs nothing measurable** — two of the three deltas are negative, i.e. inside noise. Reported
as measured, and it is **not** grounds for changing `w`; the `w ∈ {4, 16}` sensitivity arm is
untouched.

*Implementation note, because it is the kind of thing that must be visible:* `AutoEncoder.forward`
runs encoder and decoder in one call, so the bottleneck — the thing that would go on the wire — is
never exposed. `v2_int8_calibrate.py` wraps that call to split it and inserts the quantise/dequantise
pair exactly where the protocol says the channel is. Branch 2 carries no AutoEncoder and is quantised
where the fusion consumes it. **No weight, module or fusion rule is altered.**

### Step 5 — `f_tail` measured, and the proxy was badly wrong

| estimate | `f_tail` |
|---|---|
| V2-R1 assumption | 0.15 |
| V2-R3 parameter share | 0.118 |
| **V2-R4 measured wall clock** | **0.309** |

3.20 ms tail against 10.35 ms full at `record_len=[2]`, 20 timed runs after warm-up. **The parameter
share under-read it by 2.6×** — the deblocks are transposed convolutions over the full BEV grid,
cheap in parameters and expensive in compute. This is precisely why V2-R3 declined to price tier B
off the proxy, and the refusal paid: **tier B's typical estimate doubles, 5 h → ≈ 10 h**, and the
A+B+C typical total moves from ≈ 13 h to **≈ 18 h**. `docs/v2_gpu_cost_estimate.md` updated.

### Step 6 — Tier A is authorised and not yet started, and why that is not a stall

The protocol is fully locked and V2-R4 releases Tier A without further approval. **What does not yet
exist is the code**: work packages 1–5 (forward invariants, per-agent inference with the
nearest-collaborator rule, and the E/L/F product generators) have to be written before there is
anything to launch. The pieces built so far — the single-vehicle forward, the two-CAV restriction,
the transmit-quantiser and the payload chain — are the components those packages assemble, not the
packages themselves.

**Reporting an unstarted run as started would be the one failure mode this whole protocol exists to
prevent.** The authorisation is in hand; the next batch builds packages 1–5 and launches.

21/21 gates PASS; main 16 pages, supplementary 12.

## V2-R5 — work packages 1 and 2 built; the cue leakage defence made enforceable

**The v1 manuscript was not touched**: `paper/*.tex` 0, both PDFs 0, `results/main` 0.

### A-1 · A second instance of the same mistake, recorded next to the first

V2-R4's instruction guessed that the two thirteen-row lists were "highly similar, you may be
misremembering". The diff returned **0 of 13**. The guess treated **equal length as evidence of equal
content** — the same shape as B-1, where 144 + 32 + 8 landing back on 184 was read as confirmation
when it was arithmetic coincidence.

**One lesson, stated once, applying to both: a numeric coincidence is not an identity of objects.**
Two lists of the same length are not the same list; a total that comes out to the same number is not
the same total. Both cases are now in this log side by side because the pattern is what recurs, not
the particular numbers.

### B · Work package 6 is a leakage defence, and it is now written as one

**Adopted and strengthened.** Carrying the v1 cue *values* over unregenerated would feed v1
detections into a v2 selector — leakage in the ordinary sense, and **no gate in this repository would
catch it**: the values are plausible, the column names unchanged, every existing check passes. It is
invisible by construction.

`§9.1` now carries six acceptance criteria, all preconditions of the selector freeze: a per-dimension
table over all 23 rows marked `depends` / `independent`; **a code location as the basis of each
classification, with a verbal assertion explicitly not accepted, including mine**; recomputation with
old-and-new distributions printed for `depends` rows; an invariance demonstration for `independent`
rows, with *"it looks like a channel quantity"* named as not a demonstration; **an unclassifiable
dimension stops the batch**; and the table enters the manifest.

`§9` also splits the two statements that are easy to collapse (B-3): **the cue definitions carry over
unchanged, and every cue value must be recomputed.** They do not conflict, and the first does not
imply away the second.

### C · The int8 implementation note moved into the protocol, with a reconciliation pair

The pipeline detail was living in a commit message, which is exactly the **billing ≠ pipeline**
failure B-4 exists to prevent — an accounting document can say "int8" while the pipeline runs float
and nobody would see it. `§2` now carries a seven-row table pairing **protocol requirement ↔
implementation site**, so a change to either side without the other is visible.

Reporting constraints are written in as well: the permitted sentence is scoped to *this evaluation
setting*, and **"int8 is lossless" / "quantisation does not affect performance" are forbidden**. The
`w ∈ {4, 16}` arm may not be reduced because the measured loss was small.

### D · Tier B approved and priced; the ordering is a dependency

`f_tail = 0.309` adopted; 0.118 and 0.15 recorded beside it with *parameters are the wrong proxy for
compute, under-reading by 2.6×*. **Tier B approved at ≈ 10 h typical, to start after A is accepted**
— B reads what A writes, so the order is a dependency, not a preference. **A run exceeding 2× the
typical figure stops and reports.** Tier C stays unapproved pending the selection report.

### E · Work packages 1 and 2

**WP1 — forward invariants.** Checkpoint hashes, FOV, score threshold and NMS, with **the reference
values parsed out of the protocol rather than typed into the checker**, so an amendment cannot leave
it agreeing with a retired number. It is a *precondition call*: `assert_invariants()` runs before any
generator writes anything. Live tree **PASS** on all six. Self-test perturbs score threshold, NMS and
the x-range in turn — **all three FIRE**, live tree clean.

**WP2 — per-agent inference. The collaborator rule is not re-implemented.** `§2` quotes the v1 P4-C
subset rule verbatim, and that rule already exists as executable code in the sibling checkout
(`opencood/utils/catosg_collab_subset.py`, applied inside `__getitem__` before the pairwise
transformation). `CATOSG_MAX_COLLAB=1` selects ego + the single nearest collaborator by Euclidean
distance on `lidar_pose[0:2]`, ties by ascending CAV id. **Writing a second implementation of a rule
the protocol quotes is how two definitions drift apart**, so this module sets the variable and
asserts the effect instead of re-deriving distances.

Health check, 33 validate frames:

| | value |
|---|---|
| `n_cav` after the rule | **max 2, mean 2.000** — the rule took effect |
| frames with a collaborator | 33 / 33 |
| GT/frame | 26.39 (two-CAV GT, below the all-CAV 27.75 — as it must be) |
| ego boxes/frame | 22.58 |
| **collaborator boxes/frame** | **23.73** |
| ego AP@0.5 / mean F1 | 0.72869 / 0.79307 |
| rate | 0.828 s/frame |

**A number for work package 4 to correct:** the `B_L` proxy in §4.4 used the *ego's* 22.41 boxes.
The collaborator's mean is **23.73**, about 6 % higher, so the real `B_L` will come out slightly
above the 0.00235 Msym proxy. WP4 prints both, as E-4 requires.

Full validate run launched; test and Culver-City follow, then packages 3–5 per E-6.

21/21 gates PASS; main 16 pages, supplementary 12.
