# Phase F .tex mechanical pass — HANDOFF SNAPSHOT (PAUSED 2026-07-12, fatigue discipline)

Paused at 5/11 items by deliberate decision (mechanical pass = fatigue-error hotspot; expected-loss
asymmetry favours a fresh pass over a tired one). Zero-archaeology restart: work straight off this file +
PHASE_F_TEX_CHECKLIST.md. Final gate unchanged: 11/11 + all figures -> full manuscript diff, supervisor + Josh.

## NEXT-SESSION FIRST STEP (before item 6): re-verify commit cae8654 (item 5)
The last item done in a fatigue stretch is the risk peak. Re-read cae8654 (generalisation + tab:gen_headline
+ AP-vs-SNR) fresh, against policy_v3 / true_e2e_global_v3, BEFORE starting item 6. Five minutes.

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
  tab:headline AP). Account resolved: not redundant, do not conflate.
- channel_codec_ap vs two_regime_edge: SEPARATE artifacts, correctly NOT merged. channel_codec_ap_v3_test.csv
  (channel,codec,snr_db,ap50) = Figure-A fixed-codec AP-vs-SNR characterisation; two_regime_edge_v3.csv
  (rf_f1,edge_...) = RF-vs-threshold F1 edge (selector value). Different metric (AP vs F1) + object (codec
  vs selector). No merge -- by design.

## JOSH: HARQ para is a FINALISED DRAFT (JOSH_PARAGRAPHS.md #4) -> 3 paragraphs remain to hand-write
(C256 dominance, CoDS positioning, collaboration-harm). This is the schedule's long pole for the final gate.
