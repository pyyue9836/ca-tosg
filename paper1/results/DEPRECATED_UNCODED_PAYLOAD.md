# DEPRECATED artifacts -- uncoded (pre rate-1/2) payload units. DO NOT read these.
Unit-convention change (payload = info/coderate/bits_per_sym; C16=0.99, C256=0.495 Msym) propagated to the
policy_v3/ outputs but left these older siblings carrying the WRONG uncoded units (C16=0.495, C256=0.2475).
Found by `grep -rn '0\.2475\|0\.495' results/` (whole-repo sweep, not a single-point reconciliation).

STALE (superseded by the policy_v3/ equivalent with corrected 0.99/0.495):
- results/pareto_points.csv                      -> use results/policy_v3/pareto_points.csv
- results/generalisation_{validate,test,culver}.csv -> use results/policy_v3/generalisation_*.csv
  (also older F1 accounting, not only payload)
- code/extra_experiments/out/a1_pareto_points.csv   -> regenerate from a1_pareto.py (corrected PAYLOAD)

Rule (elevated 2026-07-15): after a unit-convention change, EVERY CSV/figure artifact carrying that unit is
either regenerated or marked DEPRECATED here; a single-point reconciliation (e.g. frontier lam=0 payload
0.1565 = 0.863*0.024 + 0.137*0.99) proves the live file, it does NOT sweep the repo -- grep the old literal
to find all sibling orphans at once. [[verification-derive-not-hardcode]] family.

COROLLARY (the highest-value catch of 2026-07-15): when you CORRECT a number, the grep target is the OLD
LITERAL VALUE ITSELF, whole-repo. The payload-correction commit changed only the 3 results-side spots and
left 3 Method-side spots (main.tex L168/L280/L315) + a family of number-emitting scripts untouched --
PRECISELY because 0.495/0.248 was never grepped across the whole tree at correction time. The stale artifact
is a SILENT failure (L34 reports 0.990, L168 defines 0.495, both sat in one manuscript unseen); the
whole-repo grep of the old literal is what forces it to announce. Correct-a-number => grep-the-old-literal is
part of the rule now, not a nicety.

DOUBLE-MEANING-LITERAL sub-rule: 0.495 is ambiguous -- it is the STALE C16 payload AND the CORRECTED C256
payload. A whole-repo grep of the old literal (the corollary) is necessary but a bare `grep 0.495` cannot
distinguish the two; every hit must be read with binding context (which mode?). Prefer the UNAMBIGUOUS
fingerprints of the stale account -- 0.2475, `1.98/4`, `1.98/8`, and derivations that omit the x2 (1/rate)
factor -- and never bulk-replace 0.495. (Applied in PHASE_F_TEX_CHECKLIST item 13.)

SCRIPT FAMILY carrying the stale hardcode PAYLOAD {C16:1.98/4, C256:1.98/8} (canonical corrected =
recompute_policy_200seed.py:45 {C16:0.99, C256:0.495}); see PHASE_F_TEX_CHECKLIST item 13 for the per-script
disposition: plot_pareto_payload.py, train_rf_multiseed.py, snr_decision_plot.py, csi_noise_ablation.py,
e2e_inference_verify.py, test_split_pipeline/04_eval_rf_on_test.py. Rendered Pareto/payload PDFs (item 15)
are DEPRECATED pending regen -- same rule as the CSV orphans.

THREE-PART ALIGNMENT (supervisor 2026-07-16, after the 3rd double-notation species): a number entering the
paper must align on THREE things -- VALUE, SOURCE, and ATTRIBUTION LABEL (which split / channel / codec it
belongs to). The double-notation disease has three species now, all caught this session: (1) NUMERIC (0.495
dual-meaning C16/C256); (2) NARRATIVE (the gamma-dominant old story after c_t overtook it); (3) LABEL (v3
test-derived robustness numbers sitting under an "OPV2V validate" caption). grep covers value+source; the
attribution label is verified by cross-reading the generating SCRIPT HEADER (e.g. robustness_v3.py "Eval
split = test"), not from memory. Attribution is verified with EQUAL weight to the value.

REVERSE-DEPENDENCY SCAN (supervisor 2026-07-17, from the 12th interception -- the gravest: two contradictory
CONCLUSIONS coexisting in main.tex, L708-713 "threshold matches RF, no Pareto advantage" vs the headline "RF
Pareto-dominates"). RULE: a conclusion-level edit (changing a CLAIM, not just a number) carries a
whole-manuscript scan on the claim's KEYWORDS; every hit is reconciled or flipped, zero-hits recorded with
scope+fingerprint. Numbers have the "correct-a-number => grep-the-old-literal" fingerprint scan; conclusions
get the isomorphic keyword scan. It survived because item-3's verification checked that item's own
correctness, never "does another passage carry a claim coupled to this one?". Twin of change-a-number=>grep.

REVIEW-SIDE LEDGER = POINTER NOT SOURCE (supervisor 2026-07-17, 5th review-side unsourced assertion, joining
the equivalence golden-ticket, the scope-less-negative ruling, the E2 quote-stamp, the pre/post-hoc axis).
A value quoted in a spec/instruction/memory is a POINTER; its authority is the manuscript + CSV, never the
ledger entry. The "~10%" cue-payload figure was carried in the review-side ledger for two weeks and
re-issued in specs, while main.tex + CSV say ~12% (0.03066/0.2509=12.2%). Three-part alignment (value/source/
label) binds review-side numbers too: when a spec-quoted number meets the manuscript, the manuscript+CSV win.

CLEAN-VERDICT NEEDS ITS GREP LINE (supervisor 2026-07-17, 6th review-side unsourced assertion + 14th
interception). Any "clean / 干净 / zero-hit / no residual" verdict in a receipt MUST carry its grep line
(pattern set + scope) to be VALID -- cleanliness is demoted from a judgement word to an executable statement.
A clean-claim with no grep line = not scanned = a bare negative-existence assertion -> BOUNCED (my own
rule). Concrete: item-8's receipt asserted "intro/conclusion clean"; the conclusion carried "matches the
learned selector" + five v2 numbers; the ledger caught it on first run. Same family as scope-less negatives.

LEDGER SYNONYM-FAMILY RULE: a claim fingerprint is stored as a WORD-FAMILY regex, not one surface form
(RF|selector|policy ; matches|suffices|equals ; threshold|tau ; cut|save|reduce|buy). Incomplete surface
coverage = half a fingerprint. Term-grep reserved words (fallback, codebook) are synonym seeds. ("matches the
learned RF" missed "matches the learned selector" -> now a family.)

REPLACEMENT PASSES THE SAME ANCHOR CHECK (supervisor 2026-07-18): after retiring an evaluative word, the
replacement TEXT is subject to the identical CSV-anchor-or-delete rule -- retiring "easier" and swapping in
"stronger/weaker" is not a retirement, just a synonym still running naked. Concrete: my L590 fix replaced
"finds test scenes easier" with "detection stronger on test", turning an object-level-baseline LEVEL diff
(Fixed-L AP 0.919/0.890/0.783) into a "detection difficulty" claim -- same disease, and 0.919 vs 0.890 as
"stronger" is the +0.002-no-CI-no-direction mirror. Fix = state the three anchored numbers, Culver drop ->
domain shift, no comparative. ALSO: the supervisor's pointer "AP 0.917 for validate" was the validate
CEILING (0.9169), not the baseline (0.890) -- verified against true_e2e_global_v3 (pointer != source). Ledger
family added: {stronger|weaker|better|worse} x (split|scene|test|domain). Evaluative-retirement fingerprints
are STEM+WILDCARD (eas(y|ier) near split|scene|test), never a full phrase (the full-phrase "easier test
split" missed "easier scene-disjoint test split" and "easy split").

FACT-FIX vs NARRATIVE-RECONSTRUCTION (supervisor 2026-07-18, reaffirmed after item-7 self-approval): a
FACT-ERROR correction (a number wrong vs its source -> fix to source) may land DIRECTLY. A NARRATIVE
RECONSTRUCTION (changing the EXPLANATION FRAME, even when the data is unambiguous) must ALWAYS be SURFACED for
a ruling first -- "the data is unambiguous" is an execution-side self-judgment and does not license skipping
the surface. Instance: item-7's "all beneath Fixed-L" -> "dominated on a channel-averaged basis, not per-SNR"
was reframing (approved on content, flagged on procedure). A/B/C of item 9 were surfaced; this same-level one
was not. Boundary, not a new rule.
