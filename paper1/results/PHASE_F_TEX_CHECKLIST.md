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
- STANDARD-FAMILY grep "802.11": main.tex is standard-AGNOSTIC (names both 802.11bd and NR sidelink as
  example signalling stacks, cites {ieee80211bd, 3gpp38885}, models generic rate-1/2 LDPC+QAM; the BLER table
  is Sionna NR-LDPC + TR 37.885 = 3GPP NR lineage). CONFIRM no sentence anywhere claims the PHY "adopts" or
  "is in" the 802.11bd family exclusively (that would be false -- 802.11bd is IEEE/DSRC; our PHY model is NR).
  The CoDS paragraph uses NO family name (neutral "cliff-prone class of digital transport"). Keep it agnostic.
- CODE-SPEC PIN (6-11 batch, conditional): grep main.tex {Sionna, NR, 5G, LDPC5G, 37.885, base graph}. If
  Methods already names the specific simulated code -> no-op. Else add once: "we instantiate this transport
  with the 5G NR LDPC (Sionna) under TR 37.885 Urban NLOSv." Framework stays class-agnostic (802.11bd OR NR
  sidelink for signalling); the SIMULATED entity must be named -- the 8.0/16.5 dB onset is code-construction-
  dependent (NR-LDPC != 802.11 n=1296), a reproducibility gap otherwise.

## ITEM 12 DONE (2026-07-16): L168 Eq / L280 / L315 -> corrected 0.99 / 0.495 with the rate-1/2 coded-bit
## derivation (1.98 Mbit -> 3.96 Mbit coded -> /4, /8). STALE fingerprint grep = 0. C256 insertion UNBLOCKED.
## - C256 insertion note (spec a): at insertion, trim the C256 footnote [^pay] to REFERENCE the Method payload
##   derivation (now canonical at L315 / Eq) rather than repeat it; the [^pay] Eq.(7)/(11) placeholders
##   resolve to the real Method labels. This is an allowed insertion-time refinement, flag it in the C256
##   insertion commit.
## RECEIPT-COVERAGE RULE (supervisor 2026-07-16): a receipt's coverage claim must align with the item's
## ORIGINAL definition -- one line for what was done, one for what was not. (Re-verify expanded's spot-check
## dimension was under-reported; closed by the gen-section spot-check below.)

## PRE-BLOCK JUDGMENTS (2026-07-16; done BEFORE opening L676-902, per supervisor)
### item-10 csi_noise judgment (C-class traceability -- the data task, conclusion-first):
csi_noise feeds ONLY the SNR-estimation-noise ΔF1 rows of tab:robustness (L866-902). Per-number:
  - sigma<=1 dB  ΔF1 : F1-based -> report-only re payload. v3 = -0.0002 (robustness_csi_noise_v3.csv)
  - sigma=2 dB   ΔF1 : F1-based -> report-only.            v3 = -0.0009
  - sigma=5 dB   ΔF1 : F1-based -> report-only.            v3 = -0.0037
NO csi_noise PAYLOAD number is cited in main.tex -> the stale PAYLOAD dict is report-only (no contamination).
BUT the CITED ΔF1 values are STALE v2 (-0.003/-0.025/-0.070) and must update to v3 (-0.0002/-0.0009/-0.0037,
~20x smaller -- v3 far more CSI-noise robust); v3 source = robustness_csi_noise_v3.csv (corrected payload
0.2509, WITH CI). The stale-hardcode code/csi_noise_ablation.py (PAYLOAD 1.98/4, OUT v4_csi_noise, no CI) is
SUPERSEDED by it -> C-class DEPRECATE (add to DEPRECATED_UNCODED_PAYLOAD script family disposition).
### item-11 narrative grep (a): NOT zero hits, but NO statement asserts "SNR is the single dominant FEATURE".
Fingerprints {SNR ... dominant/sufficient/first, gamma alone} -> hits at L503 (item-6 ablation prose, stale
0.839/0.851), L717/L755/L787/L812 ("SNR is a (near-)sufficient statistic" = the CURRENCY finding: channel
state sufficient vs perception cues UNDER THE CLIFF -- consistent with c_t-dominance, different regime), and
abstract L34 ("estimated SNR and channel-type ... jointly", lists SNR first). RECONCILE in the dense block:
(i) confirm "sufficient statistic" reads as CHANNEL STATE (SNR+type), not "SNR alone" where a7 shows both
matter; (ii) abstract L34 reorder to "channel-type and estimated SNR" (c_t 0.349 > gamma 0.275). No
narrative-flip VIOLATION found; these are consistency touch-ups, recorded with scope+fingerprint.

## REVERSE-DEPENDENCY SCAN result (item-8 threshold flip, 2026-07-17): fingerprints {threshold matches/
## suffices, no Pareto advantage, marginal, sufficient statistic}. NON-zero -- 3 coupled residuals in the
## JSCC-aware section (item 9) still carry the OLD "threshold matches the learned selector under LDPC":
##   L756 "a one-line threshold matches the learned selector"
##   L778 "the threshold suffices, reproducing Section~\ref{sec:threshold}"
##   L802 "Under LDPC the threshold matches \method; under JSCC the threshold collapses"
## RECONCILE at item-9 edit: "matches/suffices" -> "nearly matches / captures most of the F1 (marginally
## Pareto-dominated at matched payload)" -- consistent with the flipped threshold section + headline. The
## LDPC-half currency claim (threshold captures most) stays; "matches" (= equal) must not survive next to the
## headline's "Pareto-dominates". intro(L34/70)/conclusion(L902+): no residual old-conclusion hit (currency
## framing only). Scan scope = full main.tex; recorded per the reverse-dependency-scan rule.

## ITEM 6 SPECS (2026-07-17):
- DENOMINATOR (cue payload saving): 0.03066 Msym / RF-deployed 0.2509 = 12.2% ~ 12% (a7_cue_value_v3). Unify
  all four "~12%" sites: body (L70/L381/L715) = "of the selector's deployed channel use" (full denominator,
  ONE definition, others reference); abstract (L34) stays terse = "~12% lower channel use". No "~10%" anywhere.
- MECHANISM-TRANSPARENT WORDING (new landmine): Full payload 0.2399 < Channel-only 0.2706 because perception
  cues make the selector pick the low-payload action (L) MORE OFTEN -- nothing is compressed. Transitive
  "cues cut/save/reduce/buy payload" invites "how does a cue reduce bits?". Use: "with perception cues the
  selector selects the low-payload action more often, lowering deployed channel use by ~12% at equal F1."
  grep {cut, save, reduce, buy} x {payload, channel use, bandwidth} across the block; reconcile hits.

## GAMMA-FLIP REVERSE-DEPENDENCY SCAN (2026-07-17, the debt I owed -- item-6 receipt had treated the flip as
## an in-section rewrite and skipped the scan). Fingerprints {improves F1, adding gamma/SNR improves, est_snr
## adds, "improves F1 by 0.012"}. RESULT: A/B = ZERO -- the reversed v2 claim "gamma improves F1" is fully
## gone (the merge deleted the old caption "improves F1 by 0.012 ... 5.3 percentage points"). Sites:
##  (i) §Features: c_t>gamma narrative + its mechanism sentence already self-consistent -- gamma has
##      importance yet adding it atop perception cues doesn't help; NO contradiction, no edit.
##  (ii) intro/abstract: no "channel features improve F1" claim (62% is IMPORTANCE, not F1 improvement). clean.
##  (iii) L721/738/794 "SNR (near-)sufficient statistic" (currency): surface-contradiction with the flip ->
##      RECONCILED with one sentence landed in the ablation prose (sec:ablation): SNR is decisive as the
##      THRESHOLD SIGNAL but adds no F1 as an ADDITIONAL RF FEATURE atop perception cues -- two distinct roles.
## DEFERRED to item-9 reconciliation (do not open separately): whether to add a gamma-marginal MECHANISM
## sentence (welded to item 10/11 -- three v3 flips one physics line: c_t-dominant / CSI-noise immunity /
## gamma-marginal-no-gain). Paper DOES report the gamma-alone number (ablation table + prose) -> likely add.
## BLOCK-EXIT GREP UNION now includes the gamma-improves family: {v2 payload fingerprints} U {old-conclusion
## keywords: threshold matches/suffices, no Pareto advantage} U {improves F1, adding gamma/SNR improves}.

## GAMMA MECHANISM -- CONFIRMED (verify_gamma_mechanism.py -> gamma_mechanism.csv, 2026-07-17): the strong
## hypothesis holds. delta(Perception+gamma - Perception-only) by channel: AWGN +0.0060, Rayleigh -0.0105
## (loss concentrated on Rayleigh = True). Both cuts request the SAME extra payload 0.089->0.182 on BOTH
## channels (Perception+gamma cannot see channel type), but on Rayleigh (frame BLER~1) the emboldened C16
## requests fail and collapse to the ego floor. Net (0.006-0.0105)/2 ~ -0.0023 ~ observed -0.003. My earlier
## "continuous noise dimension" hypothesis is RETRACTED (unsourced); this is the sourced structural version.
## READY SENTENCE (write at item-9 decision point, LAND at ablation prose beside the gamma-alone number,
## welded to §Features): "The loss is channel-specific: without $c_t$ the extra $\hat\gamma_t$-driven $C_{16}$
## requests fire on Rayleigh frames too, where the LDPC block almost always fails (Fig.~\ref{fig:bler}) and
## the output collapses to the ego floor (AWGN $+0.006$, Rayleigh $-0.011$ F1); adding $c_t$ restores the
## gating." Three v3 flips = one physics line: c_t-dominant (§Features) / CSI-noise immunity (item 10) /
## gamma-marginal-and-Rayleigh-harmful (here).
## ITEM-9 SPEC (two-role reconciliation single home): the "SNR threshold-signal vs RF-feature" sentence lives
## in §Ablation; item-9's L738/756/778/802 handling REFERENCES it ("as distinguished in Section~\ref{sec:
## ablation}"), does NOT restate -- argument-double-notation defence applies to the reconciliation sentence too.
## ITEM-6 #4 (same-reader): a7 RETRAINS per cut -> tab:ablation caption note added (per-cut retrained; deployed
## = Full, 0.909@0.251 vs per-cut Full 0.240 as separate instances). Resolved.

## ITEM 9 DONE (2026-07-18, two-regime central-message section):
- A (split): moved from "1000 validate frames" -> "2170 test frames" (currency +0.027 is test; validate JSCC
  edge only +0.004). fig:two_regime caption now says test -> A-CLASS REGEN REQUIRED (figure still shows
  validate data). Split-dependence acknowledged in a footnote (test +0.027 vs validate +0.004; anchored in
  rf_f1/FixedL per split: validate 0.911/0.907, test 0.928/0.901).
- B (JSCC cue anchor): no independent JSCC-domain cue ablation -> retreated to "not attainable by SNR
  thresholding alone" (no cue-driven mechanism claim). Edges test: JSCC +0.027/+0.022/+0.025, LDPC +0.005.
- B (LDPC now significant): v2 "insignificant, threshold suffices" -> "small (+0.005), the selector's
  function-form margin, not a cue gain (cues add no F1, sec:ablation); ~6x smaller than the JSCC edge".
- C (THREE "LDPC edge" values, three names, NEVER unify -- highest same-reader risk): footnote distinguishes
  a7 -0.0002 (feature ablation, Full vs channel-only) / headline +0.0005 (matched-payload Pareto vs retuned
  tau) / two-regime +0.005 (per-frame vs oracle-tuned tau); ordering -0.0002<+0.0005<+0.005 is informative.
  Each site cites its name; ledger has the bare-quote fingerprint.
- D: 5 residuals L738/L756/L778/L784/L802 reconciled ("matches/suffices"->"closely tracks/captures most";
  table caption "insignificant"->"small"); grep matches/suffices/insignificant/+0.017 = 0.
- L717 touchpoint: L721 "estimated SNR a near-sufficient statistic" -> "channel state a near-sufficient
  statistic" (a7: Channel-only = SNR+type is what suffices, not SNR alone).
