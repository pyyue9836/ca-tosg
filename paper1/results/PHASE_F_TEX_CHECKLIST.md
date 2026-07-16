# Phase F .tex substitution checklist — every v2 number in main.tex, line-by-line, ticked on replacement

Grep-verified list of ALL stale v2 numbers in paper/main.tex (line -> v2 value -> v3 replacement ->
source -> [ ] done). Substitute against THIS list, tick each; a residual is worse than a bridge para.
STATUS: ALL numbers final (F1-side + AP-side true_e2e_global_v3 done). Was:
v3 true_e2e re-run (true_e2e_global_v3_*.csv, running bv2d7ua0d).

AP +0.002 WORDING LANDMINE (test AP@.5 feature-active gain): NO CI support -> NEVER "improves"; write
"comparable to object-level" / "no significant change". Only bring a number if a CI backs it. (culver
+0.074 and validate +0.026 are the reportable AP gains; test is "comparable".)

Band DEFINITION (write once, cite everywhere; NEVER "RF/0.99"): "\method's channel-averaged payload is
X Msym of channel use per frame (at rate-1/2), i.e. Y% of the Fixed C_16 feature-level cost (0.99 Msym);
Y ranges 16.0-25.3% across the validate/test/Culver splits." Rounding: nearest 0.1 pp / 3 dp, declared once.

## Abstract (L34) + intro central finding (L69-70)
- [x] L34 `+0.05` (AP gain) -> `up to +0.074` (culver AP@.5 feat-active over Fixed-L; validate +0.026, test +0.002~0). src true_e2e_global_v3.
- [x] L34 `15.8-18.4%` -> `16.0-25.3%` (band def above). src policy_v3.
- [x] L34 `65%` (SNR+ch importance) -> `62%` (channel_is_rayleigh 0.349 + est_snr_db 0.275 = 0.624). src results/feature_importance_v3.csv.
- [x] L34 `+0.017 [+0.012,+0.022]` (JSCC edge) -> reframe to CURRENCY: cliff LDPC cues buy bandwidth
  (a7 payload -0.031 sig, F1 +0 ns); graceful JSCC cues buy accuracy (edge awgn test +0.0266
  [+0.0242,+0.0290]). src two_regime_edge_v3 + a7_cue_value_v3.
- [x] L34 `52.8` ms -> keep (batch-1 conservative; add the a8 13.9 ms protocol note; unify once).
- [x] L69 `+0.045` (hard-frame gain) -> v3 reliable-ch hard gain test +0.0896 [+0.0829,+0.0963] (all-channel
  +0.0240); DECLARE reliable-channel condition (AWGN 16 dB, deterministic). src a2.
- [x] L70 `+0.017 ... +0.015 (Rayleigh and OFDM)` -> v3 edges: awgn +0.0266, rayleigh +0.0223, ofdm +0.0251
  (test); + feasibility monotone (diversity order 8 / ~24 / unbounded dB; OFDM d=2.01 R2=0.99, Rayleigh
  d=0.84 R2=0.94). src two_regime_edge_v3 + PROVENANCE_ofdm.

## Method (L284)
- L284 `52.8 +-5.7 ms / P95 59.1` -> keep (latency protocol unchanged; channel-independent). Confirm vs a8.

## Headline results (L349-405)
- [x] L355 caption `0.078-0.091 / 15.8-18.4% / 0.495` -> v3 payload band; Fixed C16 = 0.99 (channel use). band def.
- [x] L376 `+0.018/+0.015/+0.054` -> v3 +0.026/+0.002/+0.074 (AP@.5); ceiling 0.917/0.922 -> 0.9169/0.9216/0.8720; Fixed-L 0.8902/0.9189/0.7828. src true_e2e_global_v3.
- [x] L376/380 `0.078 / 15.8-18.4%` -> band def.
- [x] L380 `0.889 @ 0.071` (threshold) vs `0.078` (RF) -> v3 test: threshold 0.9096@0.303, RF 0.9088@0.251.
  RECAST to Pareto: at MATCHED payload RF > threshold (frame CI excludes 0; +0.00049 test). src threshold_vs_rf.
- [x] L380 `+0.045 [+0.033,+0.059]` -> a2 reliable hard +0.0896 [.0829,.0963] / all-ch +0.0240 [.0222,.0259].
- [x] L390-395 tab:headline_agg: Fixed-L `0.887`@`0.024`; oracle `0.894`@`0.074`; RF `0.078`; threshold `0.071` ->
  v3 test: Fixed-L 0.9011@0.024, oracle 0.9140@0.179, RF 0.9088@0.251, threshold 0.9096@0.303, clairvoyant
  0.9170@0.123 (NEW row). src policy_v3/generalisation_test.

## true-e2e AP + fig:ap_snr (L409-437, 423/496/531/566/577/610/837) -- ALL [AP-PENDING]
- `0.917`/`0.922` ceiling, `0.909`/`0.895`/`0.844` AP-vs-SNR rows, knee dB -> v3 true_e2e_global_v3_*.csv.
  fig:ap_snr regen from the v3 CSV.

## Ablation tab:ablation (L482-496, 740-746) -- CSI LABEL + v3 F1
- Relabel variants: `RF+CSI` -> `RF + est. SNR`; `RF+CSI+ch` -> `RF + est. SNR + ch. type` (also L598/605).
- L740-746 F1 col `0.888/0.887/0.887/0.887 / 0.894/0.887` -> v3 a7: Channel-only 0.9089, Perception-only
  0.8996, Perception+SNR 0.8973, Full 0.9086, Oracle 0.9140, Fixed-L 0.9011 (@payloads). src a7_ablation_v3.
- L733 "adding 21 cues changes F1 by <0.001" -> v3 cues_add -0.00024 [-.00052,+.00003] ns (HOLDS). + payload
  currency: cues save 0.031 Msym (12%) sig. src a7_cue_value_v3.
- L496 `0.917 +-0.015` -> v3 full F1 0.9086 (@payload). L495 RF+CSI row -> Perception+SNR 0.8973.

## Generalisation (L579-663)
- [x] L583 `88.9%/91.3%` agreement -> test 85.4% / culver 87.0% (rf acc). `~11%` activation -> test 16.0% /
  culver 24.2%. `0.895/0.845` base rate -> test 0.8394 / culver 0.7585. `99.4%/99.6%` recovery -> test 99.4 /
  culver 99.3 (band 99.3-99.8, max validate 99.8). `16.4%/17.1%` -> per-split band. `0.913` culver acc -> 0.8703.
- [x] L587 caption `99.3-99.7% / 15.8-18.4%` -> `99.3-99.8% / 16-25%`. Mean over SNR [0,20], 50/50 AWGN/Rayleigh.
- [x] L594-605 tab:gen_headline: test oracle 0.074@0.894, Fixed-L 0.024@0.887, RF 0.081@0.888; culver oracle
  0.894, Fixed-L 0.887, RF 0.085@0.891 -> v3: test oracle 0.9140@0.179, Fixed-L 0.9011@0.024, RF 0.9088@0.251;
  culver oracle 0.8891@0.257, Fixed-L 0.8722@0.024, RF 0.8831@0.158. + clairvoyant rows. "RF + CSI + ch" ->
  "RF + est. SNR + ch. type". src policy_v3.
- L663 "reaches F1 0.888 @ 0.081" -> 0.9088 @ 0.251.

## Difficulty (L676-726)
- L683/697/718 `+0.045 [+0.033,+0.059]` -> a2 reliable hard test +0.0896 [.0829,.0963] (all-ch +0.0240).
- L708 `0.8886 [0.8878,0.8895] @ 0.078` -> v3 RF test 0.9088 @ 0.251 (frame CI from policy_v3).
- L709/725/726 `0.078/0.071` -> v3 payloads.

## JSCC-aware (L779, 818-820, 837) -- currency
- L779/818 `+0.017 [+0.012,+0.022] AWGN, +0.015 Rayleigh/OFDM` -> v3 edges awgn +0.0266, rayleigh +0.0223,
  ofdm +0.0251 (test); + threshold structurally useless (best-tau=20/0). src two_regime_edge_v3.
- L837 `0.917` -> v3 ceiling [AP-PENDING or JSCC F1 context].

## Robustness (L866-871, 893-902)
- L866/893 `-0.057` staleness -> v3 -0.0193 [-.0184,-.0203]. src robustness_staleness_v3.
- L870 `+0.015` -> v3 edge. L871/900 `52.8` -> keep. L902 (conclusion) `15.8-18.4% +0.045 +0.017 +0.015` ->
  v3 band + v3 gains + currency edges.

## Feature importance (L450-482) -- [TODO regen v3 feature_importance CSV]
- `65%` -> `62%` (0.624; channel_is_rayleigh dominates 0.349, est_snr_db 0.275). src feature_importance_v3.csv. DONE.

## CROSS-CUTTING NOTATION (unify during the .tex pass; reviewer flags mismatches)
- C256 AWGN cliff = 16.5 dB (Sionna frame-BLER onset, frame BLER < 0.999; 16-QAM = 8.0 dB). ONE convention
  across: the C256 paragraph (Josh), FIG_A_CAPTION, and any body table. Figure A's coarse 6-pt grid renders
  it as the 16->20 dB AP transition -- note the correspondence, do NOT write "17-20 dB" in one place and
  "16.5 dB" in another. src results/bler_sionna/bler_sionna.csv.
- C256 dominance = CONDITIONAL (eff_C256<=eff_C16 on 99.7/98.5/100% of frames; reverses on the <=1.5%
  comp<ego collaboration-harm frames). Identity eff_C256-eff_C16=(comp-ego)(b16-b256) verified max|err|=0.
  src results/c256_dominance_verify.csv. Weld the C256 and collaboration-harm paragraphs (shared (comp-ego)).

## CROSS-CUTTING (added 2026-07-15, from the C256 paragraph review)
- ABSOLUTE-SENTENCE GREP: grep the whole manuscript for "never select / never request / never activate /
  earns no place / always" and reconcile each with the C256 paragraph's caliber -- the deployed selector
  never REQUESTS C256 (class support 0/0/0), but the oracle frontier activates it at a minority 2.5/3.2/4.5%.
  An unqualified "never activated" anywhere conflicts with the frontier number; qualify by object (deployed
  selector vs oracle frontier). Twin of the killed "unconditional dominance" error.
- PAYLOAD TABLE CONSISTENCY: results/policy_v3/pareto_points.csv is STALE -- Fixed C16 0.495 / Fixed C256
  0.2475 are the OLD UNCODED payloads (pre rate-1/2 correction; file dated Jul 13, not regenerated). Correct
  = C16 0.99 / C256 0.495 (verified: frontier lam=0 payload 0.1565 = 0.863*0.024 + 0.137*0.99). Regenerate
  pareto_points.csv (and any payload table/figure) to 0.99/0.495 and confirm same value + same Msym notation
  as the C256 paragraph footnote [1.98 Mbit (Eq.7) x rate-1/2 -> 3.96 Mbit (Eq.11); /8 and /4 bit/sym].
  Frontier/band CSVs already carry corrected payloads; only the Fixed-baseline pareto row is stale.

## PARETO/PAYLOAD PROPAGATION FIX (NEW items 12-14, from the 2026-07-15 provenance event; item 12 is HIGH --
## it blocks C256-paragraph consistency)
12. METHOD payload definitions -- fix stale uncoded units to rate-1/2 coded, to match the results sections
    and the C256 paragraph footnote:
    - L168 Eq: B_{C16}=1.98/4~0.495 -> 1.98/(0.5*4)=0.99 ; B_{C256}=1.98/8~0.248 -> 1.98/(0.5*8)=0.495.
    - L280: B_{C16}~0.495 -> 0.99 ; B_{C256}~0.248 -> 0.495.
    - L315: B_{C16}=1.98/4~0.495 -> 0.99 ; B_{C256}=1.98/8~0.248 -> 0.495; REWRITE the derivation "the
      divisors being the bits-per-symbol" -> "1.98 Mbit source at rate-1/2 gives 3.96 Mbit coded, divided by
      the 4/8 bits-per-symbol of 16/256-QAM". Keep "~82x" object ratio (uses B_C=1.98 Mbit perception
      payload, unaffected). Confirm no other B_{C} literal survives (grep 0.495/0.248 in main.tex).
13. FIGURE/NUMBER-EMITTING SCRIPT SWEEP -- GRADED A/B/C (supervisor: train_rf_multiseed is a TRAINING-path
    script, not a plotting chore; do not one-pot them into "item 13 regen"). Every script hardcodes the STALE
    PAYLOAD {C16: 1.98/4=0.495, C256: 1.98/8=0.248}; canonical corrected = recompute_policy_200seed.py:45
    {C16:0.99, C256:0.495}. Common rule: change the hardcode to read the corrected source programmatically
    (verification-derive-not-hardcode extends to ALL number-emitting code; PLOTTING NOT EXEMPT). Disposition
    differs by class:
    CLASS A (pure figure generators -- regen + final-gate visual inspection; the "A-class regen" slot in the
    execution order):
    - code/plot_pareto_payload.py:29,58,74  (B_C=1.98/4; annotation xy=(0.495,..); Fixed-C256 line 1.98/8) +
      repoint read results/pareto_points.csv -> results/policy_v3/pareto_points.csv. Figs: fig_pareto_test,
      fig_payload_{awgn,rayleigh}.
    - code/snr_decision_plot.py:31          (decision figure)
    CLASS B (TRAINING / INFERENCE / reported-number path -- higher stakes; a stale payload biases an EMITTED
    METRIC, not just a plot axis. Recompute + CROSS-CHECK the reported value against main.tex; if it feeds a
    cited number, re-derive that number. Handle in the cross-check phase, NOT the figure-regen slot):
    - code/train_rf_multiseed.py:25         (multiseed_hardening.csv pay_rf -- deployed-point CI; L866-902 robustness)
    - code/e2e_inference_verify.py:47        (true-e2e inference verification path)
    - code/test_split_pipeline/04_eval_rf_on_test.py:27  (test-split eval numbers)
    CLASS C (ablation/robustness feeders -- fold into the owning item's recompute):
    - code/csi_noise_ablation.py:38         (CSI-noise robustness, folds into item 10)
    FAMILY EXHAUSTIVE = 6 scripts (CLOSED), by unambiguous-fingerprint grep (0.2475 / 1.98/4 / 1.98/8 in live
    .py, excluding comments/data/logs/correction-docs). NOT in the family: code/plot_with_rf.py:55 uses `1.98`
    flat = perception payload (not a channel-use /4 or /8) -> separate, intent-confirm only, no rescale.
    GREP DISCIPLINE for this sweep (0.495 is DOUBLE-MEANING -- stale C16 AND corrected C256; a bare grep 0.495
    cannot tell them apart). Scan with binding context, and prefer the UNAMBIGUOUS fingerprints of the stale
    account: 0.2475, `1.98/4`, `1.98/8`, and any derivation missing the x2 (1/rate) factor. A hit on 0.495
    must be read in situ (is it C16-stale or C256-correct?), never bulk-replaced.
14. Regenerate/retire the DEPRECATED_UNCODED_PAYLOAD.md orphans; confirm no live reader points at them.
15. RENDERED PDF DEPRECATION: every already-rendered Pareto/payload figure PDF (fig_pareto_test,
    fig_payload_{awgn,rayleigh}, any decision/robustness fig fed by a stale-PAYLOAD script) is marked
    pending-regen; the old PDF is DEPRECATED (same rule as the CSV orphans) until regenerated from a
    corrected source and visually inspected.

## FINAL-GATE VISUAL INSPECTION -- NEW COLUMN (per figure): PAYLOAD SOURCE = (generator script + source CSV +
## commit). A figure with a payload axis is not "passed" until its payload provenance is a corrected source.

## TERM-GREP (unify at .tex time; drafts NOT reopened for these)
- ego-only vs "ego's own object-level F1" vs "single-vehicle": unify to the glossed term "ego-only" across
  the manuscript (collab-harm footnote says "the ego's own object-level F1" -> "ego-only object-level F1").
  Grep {ego-only, ego's own, single-vehicle} and normalise; gloss once at first use.
- fallback = RESERVED word: bound to "transmission failed -> pipeline reverts to ego-only" ONLY. Do NOT use
  "fall back" for feasibility-gated selection of L (that is "defaults to the object-level message"). Grep
  {fallback, fall back} and confirm each is the failure-revert sense.
- "2-bit codebook" as a mechanism name -> "2-bit request" (codebook retired; "codeword" may stay for the '11'
  slot). Grep {codebook} and normalise. (C256 para already moved "codebook" -> "granularity ladder".)
