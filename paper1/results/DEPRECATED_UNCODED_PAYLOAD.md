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
