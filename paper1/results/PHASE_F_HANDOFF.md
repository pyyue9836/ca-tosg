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
