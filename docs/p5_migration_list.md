# P5 migration list — round 1 (inventory only)

**Status: INVENTORY. `paper/main.tex` is not edited by this round — not one character.** Every row
below is a proposal to be checked before anything moves. Frozen products, manifests, deployed
models, δ, τ\*, the mainline replay and every committed result CSV are untouched.

**Search scope** (so a count means something): `git grep` over all tracked files for the token; the
claims ledger `docs/claims.md` (97 rows, auto-generated from `main.tex`); and `main.tex` itself for
the terminology chain. Nothing outside the tracked tree was searched.

---

## 0. Counts, up front

| item | count | note |
|---|---|---|
| `P2-PENDING-MIGRATION` in `docs/claims.md` | **9** | the 9 pending prose edits — §1 |
| `P2-PENDING-MIGRATION` elsewhere | 2 | `docs/experiment_protocol.md` — the register itself and one cross-reference, not edits |
| claim rows in `docs/claims.md` | 97 | 27 evidence-filled, 70 evidence-empty |
| rows flagged **STALE** | **0** | §3 |
| rows with **dangling** evidence (cited file absent) | **0** | checked by resolving every cited path — §3 |
| `C_{16}` occurrences in `main.tex` | 52 (42 lines) | §4 |
| `C_{256}` occurrences | 21 (18 lines) | §4 |
| bare `C16` / `C256` in prose | 5 | §4 |

---

## 1. The 9 `P2-PENDING-MIGRATION` items

They are three issue families, not nine independent edits.

### Family A — latency: retired-v2 selector → P2 frozen selectors (4 rows: claims 11, 40, 101, 103)

**现文** (`main.tex:848–849`, and the same numbers in the abstract and conclusion):

> Random Forest runs in $52.8\pm5.7$~ms per frame ($\mathrm{P95}=59.1$~ms) on a single CPU
> core---within the $100$~ms budget of a $10$~Hz LiDAR cycle---

**新文** (source `results/latency/selector_latency.csv`, 1000 batch-1 trials per frozen selector):

> Random Forest runs in $59.9\pm5.3$~ms per frame ($\mathrm{P95}=69.3$~ms) on a single CPU
> core---within the $100$~ms budget of a $10$~Hz LiDAR cycle---

- 52.8 ± 5.7 / P95 59.1 / 2 000 trials was the **retired v2 selector**; the P2 frozen selectors
  measure 59.8 / 59.7 / 59.9 ms mean (B010/B020/B030), P95 69.3 / 68.0 / 66.6, 1 000 trials each.
- The quoted figure should be the **slowest** frozen selector, as the deployment claim must hold for
  all three: mean 59.9, P95 69.3.
- **The conclusion survives** — 59.9 ms is still inside the 100 ms budget — but the margin narrows
  from 47 ms to 40 ms, and the P95 from 41 ms to 31 ms. The "10× lower latency" claim for the
  decision-tree/logistic variants (`main.tex:849–850`) is **not** re-measured on the P2 products and
  must either be re-measured or dropped.

### Family B — true end-to-end AP: legacy 3-way scorer → R11 6d descriptive AP (3 rows: claims 10, 57, 104)

**现文** (`main.tex:384`, abstract, conclusion):

> AP@0.5 rises by $+0.026$ (validate) and $+0.072$ (Culver-City) … comparable to object-level on the
> sparser test split (AP@0.5 $+0.001$)

**新文** (source `results/main/true_e2e_ap.csv`, CA-TOSG-RF vs Fixed-L, per budget):

| split | B=0.10 | B=0.20 | B=0.30 |
|---|---|---|---|
| validate | +0.0035 | +0.0057 | **+0.0069** |
| test | −0.0008 | −0.0007 | −0.0002 |
| culver | +0.0003 | +0.0020 | **+0.0173** |

**This is the largest change in the list and it is not cosmetic.** The Culver lift falls from
**+0.072 to +0.0173** (≈4×) and the validate lift from **+0.026 to +0.0069** (≈4×); on test the sign
flips from **+0.001 to −0.0002…−0.0008**. Any sentence of the form "lifts AP by up to +0.074" cannot
survive in that form. The honest replacement claim is a **payload** claim, not an AP-lift claim —
which is what the current headline table already says at the operating points (§ Family C).
The old numbers came from the legacy 3-way scorer at 5 channel realisations per point; the new ones
are the 200-realisation descriptive AP. They are not the same quantity and must not be blended.

### Family C — policy engine: legacy `oracle_3way` → P2 frozen-selector replay (2 rows: claims 81, 85)

**现文** (`main.tex:624`, `688`, table row `402`):

> on test, the deployed selector reaches F1 $0.909$ at $0.251$~Msym/frame, within 0.005 F1 of the
> oracle and at 25\% of the $C_{16}$ payload … (RF $0.251$ versus the $\tau{=}8.5$ threshold's $0.303$)

**新文** (source `results/main/replay_summary.csv`, test split, 200-realisation frozen replay):

| B_max | F1 (RF) | payload (RF) | F1 (τ) | payload (τ) |
|---|---|---|---|---|
| 0.10 | 0.90326 | 0.06798 | 0.90271 | 0.07240 |
| 0.20 | 0.90463 | 0.09472 | 0.90740 | 0.21679 |
| 0.30 | 0.90734 | 0.18703 | 0.90937 | 0.31250 |

- The old sentence quotes **one** operating point (0.909 / 0.251); the P2 product is **three frozen
  selectors, one per budget**, so the prose must become budget-indexed or pick a budget and say so.
- "25% of the $C_{16}$ payload" becomes **9.6%** of B_F at B_max=0.20 (0.0947 / 0.99), or 18.9% at
  B_max=0.30. The direction of the claim strengthens; the number changes.
- "within 0.005 F1 of the oracle" is **not** recomputed against the P2 oracle and must be
  re-derived or dropped.
- **τ now beats RF on F1 at B_max 0.20 and 0.30 on test** (0.90740 vs 0.90463; 0.90937 vs 0.90734),
  at 2.3× and 1.7× the payload. The paper currently frames τ as the weaker challenger on both axes.
  The surviving claim is payload at comparable F1, not F1.

---

## 2. Pending edits registered outside `claims.md` (not part of the 9)

| # | where | 现文 | 新文 | source |
|---|---|---|---|---|
| W1 | `main.tex:207` | "where $\bar B_{\max}$ is the per-frame bandwidth budget." | "where $\bar B_{\max}$ is the prespecified average communication budget (a bound on the mean per-frame payload, not a per-frame cap)." | Change-log WORDING-1; the symbol already carries the bar |
| W2 | `main.tex:494–512` (`sec:ablation`) | "Channel only ($\hat\gamma,c$) 2 → 0.909 / 0.271", "Full (all features) 23 → 0.909 / 0.240", "channel state alone reaches 0.909 and the full selector matches it" | superseded by **FA-1** (Appendix E): channel-only collapses to all-L at B_max 0.10/0.20 (ρ_F = 0.000) and only requests F at 0.30; task-only never requests F at any budget; **neither half alone yields a graded policy** | `results/sensitivity/feature_ablation.csv` |

W2 is a genuine chain the brief did not list: the paper's ablation table reports an older
channel-only/full comparison that the FA-1 run supersedes, and the "perception cues barely move F1"
reading does not survive it.

---

## 3. `claims.md` — STALE and orphan inventory

- **STALE: 0.** The ledger flags a row STALE when its Exact value changes on re-generation; the
  footer of the current ledger reads *"27 preserved, 0 flagged STALE (numbers changed) this re-run"*.
  Nothing to migrate under this heading today.
- **Orphan (evidence-empty): 70 of 97 rows** carry neither a CSV nor a generator. These are not
  errors — they are the P2–P4 back-fill backlog, and the ledger says so in its header. They are
  listed here because "orphan" and "STALE" get conflated: an empty evidence cell is an **open TODO**,
  a STALE flag is a **contradiction**. There are currently 70 of the former and 0 of the latter.
- **Dangling evidence: 0.** Every CSV and generator path cited by the 27 filled rows was resolved
  against the tree; all 27 exist. (This is the check that would have caught the restructure breaking
  a citation, so it is worth stating that it passes rather than assuming it.)

Disposition proposed for P5: the 9 `P2-PENDING-MIGRATION` rows are edited in `main.tex` first, the
ledger is then regenerated (it is auto-generated), and only afterwards is the back-fill backlog
worked — otherwise the back-fill is done twice.

---

## 4. Terminology chain: `C_{16}` → **F**

The protocol's action set is **{E, L, F}** (§4). `main.tex` still uses **{L, C₁₆}** with C₂₅₆ as a
second "mode". Three distinct usages hide behind the same symbol and they migrate differently:

| usage | occurrences | 现文 example | 新文 | note |
|---|---|---|---|---|
| **the action** | `main.tex:125`, 128, 402, 500–503, 559, 624, 688 and the abstract | `s_t \in \mathcal{S} = \{L, C_{16}\}` | `s_t \in \mathcal{S} = \{E, L, F\}` | **also adds E**, which the paper does not currently have as an action — it appears only as the failure fallback. This is a structural edit, not a rename. |
| **the payload constant** | `main.tex:175` | `B_{C_{16}} = 3.96/4 \approx 0.99` | `B_F = 3.96/4 \approx 0.99` | pure rename; the value is unchanged and `tests/test_payload.py` pins it |
| **the 256-QAM comparator** | `main.tex:146`, 175, and 18 other lines | "A second feature-level mode $C_{256}$" | keep the symbol, but present it as a **physical-layer comparator, not a deployed action** | §4 of the protocol already fixes the wording for this and marks it "do not paraphrase" |

**Do not blanket-substitute.** A global `C_{16}` → `F` would silently promote C₂₅₆ to an action and
would rewrite the payload equation's subscript inconsistently with the frozen `tests/test_payload.py`
link names. The three usages must be migrated separately, and the E-action addition is the one that
needs a real paragraph, not a symbol swap.

---

## 5. Second backbone — placeholder, **pending P4-B**

`main.tex` has **no** second-backbone section today (grep for SECOND / VoxelNet / "second backbone"
in `main.tex`: 0 hits in that sense). P4-B is pre-registered in the change-log as *"PLAN
pre-registered; inference NOT yet run"*.

Proposed placement, to be created as an **empty placeholder** in the P5 edit round and left empty
until P4-B produces numbers:

```
\subsection{Generality across Detector Backbones}\label{sec:second_backbone}
% PLACEHOLDER -- pending P4-B (second backbone, SECOND/VoxelNet intermediate fusion).
% Inference NOT run; see docs/experiment_protocol.md Change-log P4-B.
% Do not write prose here until the cache protocol has produced results.
```

Between `\subsection{Comparison with Where2comm}` (line 802) and
`\subsection{Deployment Robustness and Cost}` (line 835) — i.e. after the external comparison and
before deployment cost, which is where a generality arm reads naturally.

**A placeholder is not a claim.** Nothing in it may be cited, and the gates do not read it.

---

## 6. What this round deliberately did not do

- No edit to `paper/main.tex` — not one character. The three gates that read it byte-exactly
  (stale-fingerprint block-exit, `docs/claims.md`, paragraph insertion) are therefore untouched and
  still pass.
- No regeneration of `docs/claims.md` (it is derived from `main.tex`, which has not moved).
- No change to any frozen manifest, model, result CSV, δ or τ\*.
- No decision about which of the surviving claims to keep: Families B and C change the *shape* of
  two headline sentences, and that is an author's call, not a migration mechanic's.
