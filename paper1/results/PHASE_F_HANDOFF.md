# Phase F .tex mechanical pass — HANDOFF SNAPSHOT (PAUSED 2026-07-12, fatigue discipline)

Paused at 5/11 items by deliberate decision (mechanical pass = fatigue-error hotspot; expected-loss
asymmetry favours a fresh pass over a tired one). Zero-archaeology restart: work straight off this file +
PHASE_F_TEX_CHECKLIST.md. Final gate unchanged: 11/11 + all figures -> full manuscript diff, supervisor + Josh.

## EXECUTION ORDER (FIXED 2026-07-15, note inserted before item 12): re-verify (EXPANDED) -> INVARIANCE note
## -> item 12 -> items 6-11 -> A-class figure regen -> fig:ap_snr. The note gates everything after it: until
## the INVARIANCE note is delivered/clear, item 12 and all downstream stay frozen (else the note vanishes
## from the pipeline and item 12 lands C256 on an unproven frontier equivalence). Re-verify is ALWAYS first;
## item 12 does NOT precede it (supervisor rejected "item 12 first" -- not sequential; fatigue-tail recheck
## before any new edit). NOTE STATUS: DONE 2026-07-15 -- INVARIANCE_NOTE.md, frontier_is_corrected=True all
## splits (verify_frontier_payload_invariance.py); the 2.5/3.2/4.5% share is the corrected-payload object.
## C256 PARAGRAPH LANDING GATE = item 12 AND the INVARIANCE note BOTH clear (not item 12 alone). Note leg now
## clear; item 12 (Method L168/L280/L315) remains.
## NEXT-SESSION FIRST STEP: re-verify cae8654 (item 5), EXPANDED to a 5-item payload cross-check.
The last item done in a fatigue stretch is the risk peak. Re-read cae8654 (generalisation + tab:gen_headline
+ AP-vs-SNR) fresh, against policy_v3 / true_e2e_global_v3. NOW EXPANDED (post the 2026-07-15 provenance
event): re-pass ALL 5 done items for payload literals WITH the new prior "stale dual-notation (0.495 vs 0.990)
can coexist unseen in one manuscript". tab:headline_agg was checked (rho_L path, corrected); the untested
surface is the abstract band (L34) and the generalisation section (L584+) -- confirm every payload literal
there is the corrected 0.99 / 0.495 / 0.158-0.251, not a stray 0.495/0.248. THEN item 12 (Method L168/L280/
L315 + Eq), then items 6-11, then item 13 script sweep, then fig:ap_snr. Five minutes became fifteen; still first.

## DONE 5/11 (each: CSV-traced values, per-item commit + checklist tick, forbidden-notation clean)
1. intro central finding (L69-70) currency reframing            -- commit 8f1caa6
2. abstract (L34) band / currency / 62% importance             -- commit d7c4db0
3. headline diagnostic + tab:headline_agg (Pareto-dominance)    -- commit e7f9e9d
4. tab:headline true-e2e AP + observations (test comparable)    -- commit fa000064
5. generalisation + tab:gen_headline + AP-vs-SNR (recovery band)-- commit cae8654

## REMAINING 6/11 (mechanical; all v3 numbers final; ~1 h fresh)
6. tab:ablation (L485-497) + CSI relabel L485/496/497: RF-base / RF+CSI->RF + est. SNR / RF+CSI+ch->RF + est.
   SNR + ch. type; F1 col (L740-746 too) -> a7_ablation_v3 (Channel-only 0.909, Perception-only 0.900,
   Perception+SNR 0.897, Full 0.909, Oracle 0.914, Fixed-L 0.901). L497 "0.917+-0.015" -> v3 full 0.909.
7. true-e2e AP-vs-SNR section (L409-437) + fig:ap_snr REGEN: rows 0.909/0.895/0.844 + knee -> true_e2e_
   global_v3_*.csv (Fixed-L AP@.5 0.890/0.919/0.783; feat14 0.916/0.920/0.855; knee ~12 dB). fig:ap_snr
   regenerated from the v3 CSV (generator code/plot_ap_snr.py -> point at true_e2e_global_v3).
8. Difficulty (L676-726): L683/697/718 +0.045 [+0.033,+0.059] -> a2 reliable hard +0.09 [+0.083,+0.096]
   (all-ch +0.024 [+0.022,+0.026]); L708 0.8886 [.8878,.8895]@0.078 -> RF test 0.909@0.251; L709/725/726
   payloads -> v3. DECLARE reliable-channel condition (AWGN 16 dB deterministic).
9. JSCC-aware (L779, 818-820, 837): +0.017 [+0.012,+0.022] AWGN / +0.015 -> v3 edges awgn +0.027
   [+0.024,+0.029], rayleigh +0.022, ofdm +0.025 (test); threshold structurally useless (best-tau=20/0);
   L837 0.917 ceiling. Add feasibility monotone + "empirical diversity order ~2 (BLER slope fit)".
10. Robustness (L866-902): L866/893 -0.057 -> -0.019 [-.018,-.020]; L870 +0.015 -> v3 edge; L871/900 52.8
    keep; L902 conclusion 15.8-18.4%/+0.045/+0.017/+0.015 -> band 16-25% / +0.09 / currency edges.
11. Feature importance (L450-482): 65% -> 62% (channel_is_rayleigh 0.349 + est_snr_db 0.275). Top cues after
    = pcd_* LiDAR geometry (not confidence/temporal -- fix the cue description if it overstates).

## REQUIRED INSERTION SENTENCES (verify present after the pass)
- Band definition once (numerator/denominator/0.99-of-what/splits), cite everywhere; NEVER "RF/0.99".
- Rounding rule declared once (nearest 0.1 pp / 3 dp).
- Diversity-order provenance: "empirical diversity order ~2 (BLER slope fit)"; Rayleigh 0.84 one line in body.
- Figure A caption sentence in BOTH body and caption: "the OFDM-LDPC feasibility threshold (~24 dB,
  diversity order ~2) lies above the evaluated SNR range".
- AP +0.002 (test): "comparable" / "no significant change", NEVER "improves".
- Recovery: band "99.3-99.8%", NEVER ">=99.4%".

## SUSPENDED ITEMS (not blocked by the pause)
- Figure A 9-panel (bx92gzq4n): running (ofdm LDPC-256, near done). On completion -> send the 9-panel
  row/col layout to the supervisor for review; figure INSERTION only is gated, not the .tex pass.
- fig:ap_snr regen: part of item 7.
- Josh's 4 hand-written paragraphs: see results/JOSH_PARAGRAPHS.md (independent of this pause).

## OLD-ACCOUNT CHECKS (recorded, not verbal; 2026-07-12)
- clairvoyant vs ceiling: DISTINCT quantities, NOT the same (hypothesis "clairvoyant = ceiling" is FALSE).
  clairvoyant_upper = F1 metric, 200-real, the SELECTOR's post-hoc block-sampling upper bound
  (0.9139/0.9170/0.8900 val/test/culver). Feature-ceiling = AP@0.5 metric, the compressed model under an
  identity channel (0.9169/0.9216/0.8720). Different metric AND different object; the test-split near-match
  (0.917 vs 0.922) is coincidental. Both kept, labelled separately, in different tables (headline_agg F1 vs
  tab:headline AP). Account resolved: not redundant, do not conflate. HARD LABEL REQUIREMENT (post the
  Culver 0.8867 coincidence lesson -- labels must be self-contained out of context): selector side ->
  "selector F1 upper bound (clairvoyant CSI)"; codec side -> "delivery ceiling (error-free transport, AP)".
  If the two numbers appear ADJACENT in the body, a footnote must pre-empt: "different metric and object;
  the closeness is coincidental." (Apply during the .tex pass, items 3/7.)
- channel_codec_ap v3 RE-OUTPUT (the actual old account, = attribution answered above but the re-run status
  is separate): TEST split DONE = channel_codec_ap_v3_test.csv, commit a1f4b8c. VALIDATE split = running
  (b1wu3r539) -> channel_codec_ap_v3_validate.csv; when done this line gets its md5/commit and the data-closure
  declaration is airtight for both splits. (channel_codec_ap NOT merged into two_regime_edge -- separate by
  design, different metric AP vs F1 and object codec vs selector.)

## JOSH: HARQ para is a FINALISED DRAFT (JOSH_PARAGRAPHS.md #4) -> 3 paragraphs remain to hand-write
(C256 dominance, CoDS positioning, collaboration-harm). This is the schedule's long pole for the final gate.
Order (supervisor): C256 -> collaboration-harm (both use today's frozen numbers, write while hot) -> CoDS
(outward positioning, highest wording risk, LAST; check arXiv 2512.22513's CURRENT version before writing --
positioning against an old competitor version is a submission liability).

## FINAL-GATE FIGURE VISUAL INSPECTION (rendered figures are NOT covered by the .tex diff)
The diff covers .tex text only. At the final gate, EACH rendered figure is visually inspected against this
thread's frozen caliber, item by item -- a claim-checklist is not evidence. fig_channel_codec_ap_test.pdf:
[ ] 3x3 structure (rows AWGN/Rayleigh/OFDM, cols LDPC+16-QAM/LDPC+256-QAM/JSCC); [ ] shared y-axis 0.70-0.95
all 9 panels; [ ] 3 reference-line styles distinct (ceiling dashed / L dash-dot / ego dotted) + values in
legend; [ ] 6 SNR markers + straight guides (no spline); [ ] caption covers all 4 dead panels + monotone
(8/~24/unbounded) + headroom sentence (no directional "saturates" claim); [ ] 0.922/0.919/0.735 byte-exact
vs tab:headline. fig:ap_snr (regen, item 7): same-rule inspection when regenerated.

## VALIDATE channel_codec_ap ACCEPTANCE CRITERION (nailed, so "verified" is not subjective)
Regime SHAPE must be INVARIANT vs test: AWGN-LDPC (2 panels) cliff (ego floor -> ceiling transition);
Rayleigh/OFDM-LDPC (4 panels) FLAT-DEAD at the ego floor; JSCC (3 panels) graceful monotone. ONLY the AP
levels and small cliff-position shifts may move. ANY panel breaking the regime (e.g. Rayleigh-LDPC off the
floor) => STOP and investigate, NOT a footnote. If shape holds -> drop the "validate in appendix" line and
post a single-line confirmation with the commit hash.

## VALIDATE channel_codec_ap VERIFICATION RESULT (execution-side check; verdict is the supervisor's)
channel_codec_ap_v3_validate.csv committed (this commit). Initial shape-check FALSE-flagged breaks because
it hard-coded TEST levels (ego 0.735, JSCC>0.78); investigated per criterion (3) -> a CHECK BUG, not a
regime break. Re-checked against VALIDATE's OWN levels (validate ego-only AP 0.6116 vs test 0.7350; validate
ceiling 0.9169): regime SHAPE INVARIANT on all 9 panels -- AWGN-LDPC x2 cliff (ego 0.612 -> ceiling 0.917);
Rayleigh/OFDM-LDPC x4 flat-dead byte-exact at validate ego 0.612; JSCC x3 graceful, monotone-increasing,
cliff-free, above the ego floor. Only AP levels shifted down (validate harder), as (3) allows. ONE HONEST
FLAG surfaced (not a verdict): ofdm-JSCC validate spread 0.071 (vs awgn 0.016) -- still graceful+monotone+
cliff-free (regime intact); the larger low-SNR spread is OFDM's real structure-sensitivity, consistent with
the JSCC F1 curves (ofdm 0.79-0.82 with a 0-dB dip). Supervisor to rule; "validate in appendix" line pending
that ruling.

## VALIDATE channel_codec_ap -- VERDICT: PASS (supervisor 2026-07-14). Row CLOSED.
f24d4d2 | 9/9 panels regime-invariant vs test (four flat-dead panels byte-exact min=max=ego -- the
strictest pass form, not "near-flat"; validate ceiling 0.917 matches the thread's true_e2e v3 record
0.917/0.922/0.872, cross-stage consistent) | FLAG (ofdm-JSCC validate spread 0.071) PASSED, not
investigated. Two consistency arguments for the flag: (i) cross-split RATIO reproduction -- OFDM-JSCC
spread is 3-4x AWGN-JSCC on BOTH splits (test 0.036 vs 0.012 = 3.1x; validate 0.071 vs 0.016 = 4.4x), so
"OFDM more low-SNR-sensitive" is a structure present on both, only amplified by validate's difficulty ->
shape invariant, level scaled = squarely inside criterion (3); (ii) F1-side corroboration (ofdm JSCC F1
0.79-0.82 with a 0-dB dip). Flag -> ARCHIVE (here), NOT the caption (it is within-regime; over-annotation
invites questions). DATA-CLOSURE DECLARATION now truly holds (both splits).

## DISCIPLINE RULE (elevated from the check-bug, 2026-07-14): verification scripts derive reference values
programmatically from the split's OWN source CSV -- NEVER hardcode a literal. The isomorph of "numbers are
not transcribed from memory", applied to verification code. Qualitative note: this bug was a LOUD failure
(false-positive -> triggered the (3) stop-and-investigate -> the protocol ran correctly, handling was
right). The real danger is a SILENT failure -- the same hardcode in the OTHER direction is a false-PASS.
The rule seals that direction. [[hash-line-every-delivery]] [[negative-existence-search-scope]] family.

## PARETO_POINTS PROVENANCE EVENT (2026-07-15) -- old-vs-new diff is NOT all-same
pareto_points.csv staleness is a propagation-incompleteness event (the annual-review doc-vs-repo mismatch,
same file). Diff result: the payload correction reached the RESULTS sections (main.tex L34/L355/L376:
Fixed C16 0.990, 16-25%, 0.158-0.251 Msym = corrected policy_v3) but NOT the METHOD payload DEFINITIONS
(main.tex L168 Eq B_s, L280, L315: B_C16=1.98/4=0.495, B_C256=1.98/8=0.248 -- uncoded; L315 even states
"divisors being the bits-per-symbol", omitting rate-1/2). The manuscript currently DEFINES 0.495 then
REPORTS 0.990 -- a live internal contradiction, and the incoming C256 paragraph footnote (1.98 x rate-1/2 ->
3.96 Mbit, /4 /8) contradicts L168/L315 until fixed. tab:headline_agg CONFIRMED corrected (rho_L path, not
the pareto file). Figure generator plot_pareto_payload.py reads the STALE top-level pareto_points.csv and
hardcodes B_C=0.495 / Fixed-C256=1.98/8 -> fig_pareto_test + fig_payload_* carry halved C payloads.

## HAND-WRITTEN-PARAGRAPH GATE ARCHIVAL (2026-07-15) -- what the provenance gate actually caught
Collaboration-harm v1 real defects caught by the gate (the bar working): (1) GT count 43 was stale -> 41.0
(gt_object_stats_v3.csv); (2) "adds false positives" over-reached -- no ego/compressed confusion columns
exist to verify an FP decomposition -> result-level wording. RULE (confirmed): hand-written paragraphs pass
NUMBERS first, rhetoric second -- prose is the highest-concentration zone for memory-transcription risk.
AGENT ERROR in v2 (owned, reversed in v3): the "-0.0147 is unsourced / no CI" catch was a FALSE ALARM from
grepping only results/ (missed code/extra_experiments/out/a2_difficulty_reliable_v3.csv). -0.0147 is correct,
n=713, 95% CI [-0.0179,-0.0115], significant. The agent replaced it with the STALE v2 -0.0134 (n=108). The
supervisor's point-2 gate (footnote evidence must match the sentence) forced the return to the CSV that
surfaced the agent's own error. negative-existence-search-scope reinforced (2026-07-16, receipt-format
upgrade): a "no source / doesn't exist / not found" assertion MUST carry THREE things or it is INVALID --
(1) search scope (path set), (2) fingerprint (pattern set), (3) tool line. TWO-SIDED responsibility: the
adjudicator who ruled "descriptive substitution" on the scope-less negative shares the fault; a ruling
built on an unverified negative inherits its invalidity, so a scope-less negative is BOUNCED for its scope
before any ruling. The -0.0134/n=108 v2 artifact that the agent swapped in is now DEPRECATED
(DEPRECATED_V2_DIFFICULTY.md) -- it actively supplied a wrong number, the stale-artifact protocol's 2nd
poster. Point-4 structural upgrade: the -0.0147 attribution is now a verified structural fact
(harm_stratum_structural.csv) -- 635/713 request C16, the 78 L-frames are frame-identical to Fixed-L
(max|diff|=0), so the paired difference arises entirely on the C16 frames.

## plot_with_rf.py -- BINARY RESOLVED: NOT-FOR-PAPER. Writes fig_{ap50,ap70}_{awgn,rayleigh} to
peiyi_work/01_paper_ca_tosg/runs/v3_with_rf/ (OLD path, NOT paper/figures/); plots payload with 1.98 FLAT =
source-bit (a THIRD convention, distinct from stale-half and corrected-Msym). main.tex's AP figures come from
plot_ap_snr.py (item 7), not here. Marked not-for-paper. Guard if ever revived: its payload panel is
source-bit, must NOT be cross-read with Msym axes.

## A-CLASS BATCH (execution order: ... -> A-class -> fig:ap_snr): (1) multiseed_hardening.csv pay_* columns
## re-derive under corrected PAYLOAD (train_rf_multiseed report-only); (2) fold in the v2-difficulty artifact
## DEPRECATION (DEPRECATED_V2_DIFFICULTY.md -- difficulty_strata{,_goodchannel}.csv, no live reader, Jun-17
## v2, superseded by a2_difficulty_{,reliable_}v3.csv).

## HAND-WRITTEN-PARAGRAPH SCORECARD (all 4 CLOSED 2026-07-16)
Rounds and what each round's gate stopped from reaching a TVT reviewer:
- C256 dominance (2 rounds): killed "UNCONDITIONAL dominance" (it is conditional, 99.7/98.5/100%).
- Collaboration-harm (3 rounds): killed an UNSOURCED CI ("-0.0147, 95% CI" -- the number was real but my
  "no source" catch was a scope-less negative; net: restored -0.0147 w/ CI, DEPRECATED the wrong -0.0134).
- CoDS positioning (3 rounds): killed a FAKE QUOTE ("not adaptive to channel state" = summarizer paraphrase,
  not in the paper) and a FAKE STANDARD-FAMILY claim ("same 802.11bd family we adopt" -- our PHY is NR-LDPC).
Not one of these should have appeared in front of a reviewer. Paragraph drafts final in PARAGRAPH_DRAFTS.md.

## SCORECARD -- BIDIRECTIONAL (the symmetric record; without it the scorecard is PR, not a record)
The 9 rounds' 9 catches are ONE family -- un-sourced assertions -- and the protocol intercepted them on BOTH
sides. That two-sided interception is the actual evidence it works.
- EXECUTION-side catches (5): unconditional-dominance overclaim; 43->41 stale GT; FP-mechanism over-reach
  (no confusion cols); fake quote "not adaptive to channel state" (summarizer paraphrase); fake standard-
  family "same 802.11bd we adopt" (our PHY is NR-LDPC).
- REVIEW-side origins (4), owned here: (a) the equivalence "golden ticket" -- the assumption that B_L is
  negligible, FALSIFIED by B_L=0.024 (it is the fixed anchor that breaks the lambda-rescale); (b) a ruling
  built directly on a scope-less negative -- the -0.0147 wrong case, co-responsibility accepted; (c) the E2
  "strongest source" stamp -- a paraphrase certified as a quotation, the stamp was the reviewer's; (d) the
  pre/post-hoc axis -- drawn from abstract granularity, shattered the moment the full text arrived.
Same protocol, both directions. That is why it holds.

## INSERTION PROTOCOL (plugs the last real gap: rounds 6-9 audits are silently VOID if "polished" at insert)
(a) SOURCE: the 4 paragraphs live ONLY in PARAGRAPH_DRAFTS.md #1-#4 -- the sole insertion source.
(b) INSERTION = VERBATIM. Only three transforms permitted: (1) placeholder resolution (\S VI / \S Method /
    \S Difficulty / Fig. placeholders -> real \ref; grep each label's existence FIRST); (2) LaTeX-ification
    (\method macro, subscript math mode, escaping); (3) footnote-number adaptation. ANY other word change =
    RE-OPEN that paragraph's review. No "while I'm here" polishing.
(c) COMMIT: one commit per paragraph insertion; one checklist item each; the C256 insertion item is PREFIXED
    with the item-12 gate (C256 cannot enter Method until item 12 clears).
(d) VERIFY: after insertion, a scripted normalize-and-compare (drafts vs the landed .tex paragraph, whitespace
    /macro-normalised) -- verification-derive family; the comparison result goes INTO the commit.

## RE-VERIFY EXPANDED -- RESULT (execution-side; ruling is the supervisor's): PASS. All 5 done items' payload
## literals correct (Fixed C16=0.990, C256=0.495, L=0.024, \method 0.158-0.251, band 16-25%); the "stale dual-
## notation coexists" prior found NOTHING in the done surface (every 0.495 is C256, never C16); forbidden
## notations (>=99.4%, RF/0.99) absent. The only stale payload literals are L168/L280/L315 = item-12's known
## target, NOT a done-item regression. cae8654 (item 5): tab:gen_headline C16=0.990 / C256=0.495 / RF 0.251
## /0.158 confirmed. -> item 12 next.

## ITEM 12 DONE (2026-07-16) + GEN SPOT-CHECK
Item 12: L168 (Eq) / L280 / L315 corrected 1.98/4->3.96/4=0.99 and 1.98/8->3.96/8=0.495; the rate-1/2
coded-bit derivation (1.98 Mbit -> 3.96 Mbit coded -> /log2 M) now stated once in the Eq + payload-accounting
subsection. STALE-fingerprint grep (0.2475 / 1.98/4 / 1.98/8 / 0.248 / "divisors being the bits-per-symbol")
= 0 across main.tex. C256 insertion gate cleared.
GEN SPOT-CHECK (closes the re-verify coverage gap -- non-payload dimension): tab:gen_headline test \method
F1 0.909 == generalisation_test.csv rf_full 0.9088; culver oracle F1 0.889 == generalisation_culver.csv
oracle_masked 0.8891. Both round-match -> gen-section non-payload numbers trace to source. cae8654 closed.

## ITEM 11 (upgraded record, not "62.4% aligned"): v3 DOMINANT-FEATURE FLIP (gamma -> c_t). channel_is_
## rayleigh 0.349 now outranks est_snr_db 0.275 (v2: gamma 0.405 > c_t 0.245). This is a narrative head-swap,
## not a number tweak. Flip is self-consistent with v3 physics (Rayleigh feasible set -> L regardless of SNR).
## DONE: table reordered+revalued, prose 34.9/27.5/62.4, captions 62.4%, MECHANISM SENTENCE placed (c_t
## outranks gamma because Rayleigh collapses the feasible set to L). Narrative grep (a) SWEPT: no "SNR is the
## dominant feature" violation; reconciliation touch-ups (L717/755/787/812 "channel state" not "SNR alone";
## L34 reorder) queued for the dense block. item-10 csi_noise judgment DONE (report-only; v3 -0.0002/-0.0009/
## -0.0037 from robustness_csi_noise_v3.csv; stale csi_noise_ablation.py -> C-class DEPRECATE).

## ITEM-6 #4 JUDGMENT (belated report, supervisor flagged the receipt gap): a7_ablation.py RETRAINS an RF per
## feature subset (line 6 "Train an RF per feature subset on the FROZEN v3 oracle_3way labels"; fit() builds a
## new RandomForestClassifier). So the 0.240 Full row is a per-cut retrained instance, NOT the deployed
## selector_rf.pkl (0.251 in tab:headline_agg). The 0.240-vs-0.251 near-but-different is expected -> caption
## note added. Judgment = RETRAINED (source: code/extra_experiments/a7_ablation.py:6,24-28).
## CONCLUSION-FIX TRACEABILITY (exit-grep-triggered, NOT exempt from the final-gate diff-to-checklist map):
## L886 conclusion fixes -> commit 0b7ca48 (band/AP/gains/matches-narrative) + this turn (AP Culver-City
## attribution). Each conclusion number's label: AP +0.07 = Culver-City (validate +0.026, test comparable);
## hard +0.090 = test (a2 reliable Hard, validate +0.035, CI [+0.083,+0.096]); JSCC +0.027 = AWGN/test,
## +0.022 = Rayleigh/test (two_regime_edge_v3). Every final-gate diff hunk maps to a checklist/HANDOFF line.

## GAMMA-MECHANISM RAYLEIGH=OFDM BIT-IDENTITY -- NECESSITY PROVEN (2026-07-17, 3rd application of "a perfect
## number must self-prove its necessity", after identity max|err|=0 and the L-frame identity). delta_F1
## Rayleigh -0.0105 == OFDM -0.0105 to 4 dp; per-frame realised-eff max|diff| (Rayleigh vs OFDM, Perception+
## gamma, 200 real) = 1.7e-16 (floating zero) -> STRUCTURAL, not a copy/index bug. Root: rayleigh frame-BLER
## == 1.0 at every 0-20 dB grid point; ofdm interpolates to 1.0 across [0,20] (its <1 grid points are ABOVE
## 20 dB -- an independent anchor for the ~24 dB OFDM feasibility threshold, same source as the Figure A caption) -> eff_C16 = comp*(1-b)+ego*b = ego EXACTLY on BOTH channels -> identical requests (frac_C16
## channel-invariant) x identical delivery -> identical per-frame outcome -> delta bit-identical NECESSARILY.
## The gamma sentence's "-0.011 on both Rayleigh and OFDM" is therefore a structural statement. My earlier
## equal-weight OFDM~-0.004 guess was a non-source arithmetic expectation (aggregate F1 is not stratum-linear);
## the measured -0.0105 stands.
