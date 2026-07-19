# DIFF ASSEMBLY — final-gate package (main.tex v2 → HEAD)

The last gate of the whole case. Josh and the agent each read this once. It bundles the
full manuscript diff, proves every hunk is authorised (0 orphans), lists the figure
status bits, gives the per-figure visual checklist, and carries the final block-exit run.

## (a) Scope

- **Baseline** `f2df4ca` — "P1 Step5: v3 true_e2e AP (last data piece) → ALL numbers final".
  The v2 manuscript immediately before the Phase-F .tex mechanical pass. main.tex is
  untouched by the planning/edit-map commits that precede the first substitution `8f1caa6`.
- **HEAD** `afac630` — NR-LDPC naming sentence (RELATED 6-11 conditional).
- **main.tex diff**: 622 diff-lines, **22 hunks**, 162 insertions / 162 deletions.
  The balanced +/- is expected: the diff is dominated by v2→v3 line-for-line number
  substitutions (items 6–11). The net text ADDED (4-paragraph inserts #1/#2/#3, the
  feasibility-mask sentence, the NR sentence, three \label lines) is offset in the line
  count by the two-table merge (item 6) and the ap70/Rayleigh-panel deletions.
- **Figures**: changed set in the manifest, section (c).

Regenerate the diff:
`git diff f2df4ca HEAD -- paper1/paper/main.tex`

## (b) Orphan check — 0 unauthorised hunks

**Method (airtight form).** The f2df4ca..HEAD diff is, by git's construction, exactly the
net of the commits in that range that touch main.tex. Enumerate them; if every one is an
authorised Phase-F item / paragraph-insert / infra / ruling, then no hunk can originate
from an unauthorised change. `git log f2df4ca..HEAD -- paper1/paper/main.tex` yields **31
commits, all authorised** (Phase-F .tex 1–5/N, items 6–12, the gamma/easier/conclusion
audit commits, the 4-paragraph infra + inserts, the two figure-caption commits, the NR
sentence). **0 orphan commits ⇒ 0 orphan hunks.**

**Hunk → region → item/ruling (traceability aid; region from the git @@ context).**

| # | @@ context (region) | change | item / ruling-id | commit |
|---|---|---|---|---|
| 1 | Abstract (L34) | AP band, currency framing, 62%, channel-use band | .tex[2/N] | d7c4db0 |
| 2 | Intro contributions (L66–70) | central finding: currency + hard-frame gain | .tex[1/N] | 8f1caa6 |
| 3 | Related Work, semantic-comm | **paragraph #3 (CoDS)** insert | para-#3 | 32270ef |
| 4 | Message Candidates header | `\label{sec:candidates}` | infra | 4fa1368 |
| 5 | Message Candidates end | **paragraph #1 (C256)** insert | para-#1 | 4eaa204 |
| 6 | Communication Cost / eq:payload | payload defs → rate-1/2 (3.96 coded-bit deriv) | item-12 | c749a4d |
| 7 | Proposed Method header | `\label{sec:method}` | infra | 4fa1368 |
| 8 | Selector subsection (L282) | **0.999 feasibility-mask sentence** | infra / ruling B1 | 4fa1368 |
| 9 | Payload Accounting + Channel Settings | payload accounting rate-1/2 (drops v2 `1.98/4`,`0.248`,`divisors`) **+** NR-LDPC (Sionna, TR 37.885) sentence | item-12 **+** RELATED-6-11 (ADD) | c749a4d + afac630 |
| 10 | Headline Results, tab:headline(_agg) | true-e2e AP v3, Pareto-dominance reframing | .tex[3/N],[4/N] | e7f9e9d, fa00006 |
| 11 | Detection vs SNR (fig:ap_snr) | AP@0.5-only, per-SNR narrative reframe | fig ruling-c | 41e5031 |
| 12 | Feature Importance + Ablation | c_t-dominant 62.4%; two-table MERGE | item-11, item-6 | 69311d6, 968bb10 |
| 13 | True-e2e + Generalisation | v3 AP, test "comparable"/"sparser", band 16–25% | .tex[5/N] | cae8654, fa00006 |
| 14 | Difficulty stratification | +0.090 hard-frame gain, difficulty section | item-8 | 1891a02 |
| 15 | Difficulty→Threshold (net −23 ln) | threshold-flip: two-contradictory-conclusions fix | item-8 | 6057ed1 |
| 16 | jscc_aware two-regime section | central-message section (A/B/C/D rulings) | item-9 | 1dee697 |
| 17 | fig:two_regime caption (L789) | 0.86→0.89 flat level; test caption | fig two_regime | 5d003ec |
| 18 | tab:two_regime + **sec:harm** | **paragraph #2 (harm)** insert **+** tab v3 | para-#2, item-9 | 64f0299, 1dee697 |
| 19 | Robustness (L861) | σ-noise/aging/staleness v3 values | item-10 | 2189b2d |
| 20 | Robustness (L875) | mechanism sentence | item-10 | 2189b2d |
| 21 | Conclusion (L884) | AP→Culver-City attribution, +0.090, JSCC +0.027 | conclusion audit | 2b9c023, 3fd5265 |
| 22 | tab:robustness (L899) | request-delay bound | item-10 | 2189b2d |

Every hunk resolves to a numbered Phase-F item, a paragraph-insert id, an infra edit, or
a supervisor ruling (B1 mask / B2 fig / RELATED-6-11 NR / fig ruling-c). **Orphan hunks: 0.**

## (c) Figure manifest + per-figure visual checklist

13 figures are `\includegraphics`'d in main.tex. Payload convention throughout (rate-1/2
coded channel-use, Msym): **L = 0.024, C16 = 0.990, C256 = 0.495**; payload rows in figures
must read from the true_e2e_v3 / pareto_points_v3 / policy_v3 CSVs (never a hardcoded literal).

| figure | file | status | payload source (if any) | visual check |
|---|---|---|---|---|
| fig:overview | ca_tosg_method_overview.pdf | UNTOUCHED (07-05) | — | schematic only; no data |
| fig:bler | fig_channel_bler.pdf | UNTOUCHED (06-17) | — | 16-QAM cliff ≈12 dB, 256-QAM cliff to its right; **now also the target of #1 [^cliff] (B2)** — confirm the footnote's "256-QAM curve to the right of 16-QAM" matches the plot |
| fig:qualitative | fig_qualitative_bev.pdf | UNTOUCHED (06-17) | — | F1 0.67 vs 0.95 frame |
| fig:ap_snr | fig_ap50_{awgn,rayleigh}.pdf | REGEN (07-18) | true_e2e_v3 (Fixed-L 0.890, ceiling 0.917, knee 12 dB) | AP@0.5 only; CA-TOSG stars climb past 12 dB; JSCC below Fixed-L; no ap70 panel |
| fig:payload_snr | fig_payload_awgn.pdf | REGEN (07-18) | true_e2e_v3 rho_L; B_C16 0.99 | single AWGN panel; step at LDPC threshold; **Rayleigh panel deleted** |
| fig:decision_ratio | fig_decisions_{awgn,rayleigh}.pdf | REGEN (07-18) | true_e2e_v3 rho_L, step4_oracle_v3; C256=0 asserted | intersection SNR grid, no interpolation; zero C256 layer |
| — | fig_stacked_area.pdf | REGEN (07-18) | true_e2e_v3 rho_L (rho_C16=1−rho_L) | 3-layer, zero C256 layer drawn |
| fig:feat_imp | fig_feature_importance.pdf | REGEN (07-18) | feature_importance_v3.csv | c_t 0.349 top, channel-side Σ=0.624 |
| fig:pareto | fig_pareto_test.pdf | REGEN (07-18) | pareto_points_v3, true_e2e_v3_validate | Fixed-C256 line at 0.495; annotation (0.495,0.826) |
| fig:difficulty | fig_difficulty.pdf | **DATA-V3, PENDING VISUAL (07-13)** | a2_difficulty_v3 | **never in-thread approved — inspect at this gate** (hardest-stratum +0.090) |
| fig:two_regime | fig_two_regime.pdf | REGEN (07-18) | two_regime_edge_v3 test (bit-match) | (a) JSCC flat ≈0.89, LDPC cliff; (b) LDPC thr≈RF, JSCC L≈thr≪RF; edges +0.005/+0.027 |

**Deleted from the manuscript (2 logical figures, 0 remaining `\includegraphics`):**
- fig_ap70_{awgn,rayleigh}.pdf — AP@0.7 panels dropped (fig ruling-c; no v3 ap70 baseline).
- fig_payload_rayleigh.pdf — flat-Rayleigh payload panel folded into tab:true_e2e (fig ruling-b).
- (orphan file fig_channel_codec_ap_test.pdf exists on disk but is **not referenced** — the
  cut 9-panel "Figure A"; #1 [^cliff] was redirected off it to fig:bler by ruling B2.)

**Status tally:** 3 untouched · 6 regenerated figures (ap_snr, payload, decision_ratio,
stacked_area, feat_imp, pareto) + 1 regenerated + bit-match-verified (two_regime) · 1
data-v3 pending visual (difficulty) · 2 deleted.

## (d) Final block-exit + gates (reported with the diff)

- **STALE_FINGERPRINTS block-exit**: `0 hits / 39 patterns` on HEAD main.tex (canonical
  grep `grep -nE -f <(grep '^RX ' STALE_FINGERPRINTS.md | cut -c4-) paper/main.tex`).
- **normalize-compare gates**: paragraphs #1/#2/#3 all `GATE PASS, 0 non-whitelist diffs`
  (`code/verify_paragraph_insert.py 1 2 3`).
- **Cross-refs**: sec:harm / sec:candidates / sec:method / sec:difficulty / eq:payload /
  fig:bler / gan2025cods each resolve (label|bibkey = 1). Brace/`$` balance in the three
  inserted paragraphs: 55/55, 10/10, 5/5, all `$` even.

**Human eyes owed at this gate** (the dimensions no automated check covers):
1. fig:difficulty — the one pending-visual figure.
2. Paragraph transition sentences — the seam between each inserted paragraph and its
   neighbours (verbatim protocol cannot see flow). If a transition is needed it is
   manuscript prose → surface, do not add by habit.
3. The two ruling-authorised wording edits read in context: B2 [^cliff]→fig:bler, and the
   NR-LDPC sentence sitting under the class-agnostic framing.
