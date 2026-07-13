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
- L355 caption `0.078-0.091 / 15.8-18.4% / 0.495` -> v3 payload band; Fixed C16 = 0.99 (channel use). band def.
- L376 `+0.018/+0.015/+0.054` -> v3 +0.026/+0.002/+0.074 (AP@.5); ceiling 0.917/0.922 -> 0.9169/0.9216/0.8720; Fixed-L 0.8902/0.9189/0.7828. src true_e2e_global_v3.
- L376/380 `0.078 / 15.8-18.4%` -> band def.
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
- L583 `88.9%/91.3%` agreement -> test 85.4% / culver 87.0% (rf acc). `~11%` activation -> test 16.0% /
  culver 24.2%. `0.895/0.845` base rate -> test 0.8394 / culver 0.7585. `99.4%/99.6%` recovery -> test 99.4 /
  culver 99.3 (band 99.3-99.8, max validate 99.8). `16.4%/17.1%` -> per-split band. `0.913` culver acc -> 0.8703.
- L587 caption `99.3-99.7% / 15.8-18.4%` -> `99.3-99.8% / 16-25%`. Mean over SNR [0,20], 50/50 AWGN/Rayleigh.
- L594-605 tab:gen_headline: test oracle 0.074@0.894, Fixed-L 0.024@0.887, RF 0.081@0.888; culver oracle
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
