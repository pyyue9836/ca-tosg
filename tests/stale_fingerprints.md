# STALE FINGERPRINT LEDGER -- the block-exit grep reads THIS file, not memory
# (verification-derive-not-hardcode applies to the exit check itself). Each pattern is a v2/stale form that
# must have ZERO matches in a clean main.tex. Accumulated from all interceptions. Exit grep:
#   grep -nE -f <(grep '^RX ' stale_fingerprints.md | cut -c4-) paper/main.tex   # expect 0 hits
# Receipt reports: (#patterns, #hits). A hit = a surviving v2 residual -> reconcile before block exit.

## LEDGER (interception -> fingerprint -> what it catches)
# 1  C256 unconditional dominance        RX below: always dominated / unconditional dominance
# 2  v2 difficulty (-0.0134 / n=108)      RX: 0\.0134 ; n=108 ; difficulty_strata
# 3  threshold "matches / no advantage"   RX: no channel-averaged Pareto advantage ; matches the learned RF ; \tau...16 ; 0\.8886
# 4  acc-vs-oracle / 93.3%                RX: 93\.3 ; accuracy versus the oracle ; Acc.*oracle
# 5  feat-imp gamma-dominant (65% / 0.405) RX: 0\.405 ; 40\.5 ; 65\\% ; 24\.5
# 6  v2 robustness five-tuple             RX: -0\.025 ; -0\.070 ; -0\.057 ; \ge -0\.003 ; +0\.015~F1 edge
# 7  GT count 43                          RX: 28/43 ; vs \$?43
# 8  tab:ablation_threshold label         RX: tab:ablation_threshold
# 9  payload uncoded (numeric double)     RX: 0\.2475 ; 1\.98/4 ; 1\.98/8 ; 0\.248 IN A PAYLOAD CONTEXT ; divisors being the bits-per-symbol
#    (R17-C narrowing, 2026-08-16: the bare 0\.248 pattern collided with a legitimate NEW number --
#     channel_is_rayleigh's Gini importance 0.248 in tab:feature_importance, read from the frozen
#     selector. The retired value is the C_256 CHANNEL-USE PAYLOAD, so the pattern now requires a
#     payload word (Msym|Mbit|payload|C_{256}) on the same line, either side. NEGATIVE-TESTED against
#     the retired text at 6cc6d3b: 6/6 retired occurrences still blocked, 0 hits on the current text.
#    (P0 UPDATE 2026-08-17: `27\.5` REMOVED from this family. Under the corrected N=1
#     convention the deployed selector's own est_snr_db importance is 27.4786% -> 27.5%,
#     so the pattern now forbids a true value. 34\.9 and 62\.4 stay: those remain wrong
#     for every convention (the N=1 values are 34.2 and 61.7).)
#     Coverage was narrowed in CONTEXT, never in VALUE -- a payload sentence quoting 0.248 still fails.)
# 10 robustness split label (test->valid) RX: (handled by caption audit; no safe text pattern -- manual)
# 11 gamma-improves (narrative)           RX: improves F1 by ; alone improves F1 ; 5\.3 percentage
# 13 review-side ~10% payload             RX: 10\\%.{0,30}(payload|channel use) ; (payload|channel use).{0,30}10\\%
# AP/band v2                              RX: 15\.8 ; 18\.4 (not "18.4\%") ; \+0\.045 ; \+0\.017 ; \+0\.018 ; \+0\.05[^0-9]
#    (P0/R18: 0\.895 narrowed from "[^9]" to "(?![0-9])". The retired value was printed at three
#     decimals; the exclusion of a following 9 still let it match the corrected 5-decimal 0.89529,
#     which is a TRUE value (test channel-only F1 at B=0.30). Fourth collision of this class after
#     0.248, 27.5 and 18.4 -- retired-value patterns must be anchored against the precision they
#     were written for.)
# 14 two_regime panel(a) JSCC-flat level  RX: \$\\approx 0\.86 (validate flat 0.86 -> test 0.89; the near-
#    approx form only; bare table 0.864 untouched. Anchors the $\approx$ so 0.864 F1 cells never trip it.)
# 15 transitive-verb evasion (TG-10)       RX: (cut|save)[a-z' ]{0,28}channel use by  (retired "cut/save
# 16 acc-vs-oracle escape (TG-22)          RX: reproduces \$[0-9] ; decision agreement ; base rate ; selection accuracy (item-6 killed the metric; generalisation prose kept it via "reproduces X%")
#    channel use by X%"; fixed to "lower ... deployed channel use"; narrow enough to skip "reduce payload")
# 17 v3-selector importances (R17-C)      RX: 34\.9 ; 27\.5 ; 62\.4 ; 0\.349 ; 0\.275 ; "62\%" IN AN IMPORTANCE CONTEXT
#    (the deployed selector_B020's are 24.8 / 22.3 / 47.1; the retired v3 model's are the ones
#     above. The abstract survived the first errata pass because it printed the ROUNDED 62\%,
#     which no pattern covered -- hence the context-bound rounded form here. Same construction
#     as #9: a payload/importance word must appear on the line, so a bare 62\% elsewhere is
#     untouched. NEGATIVE-TESTED: the pre-R17 abstract sentence trips it, the current one does not.)
# 18 pre-corrigendum headline family (P0)  RX: 0\.90463 ; 0\.90326 ; 0\.90734 ; 56\.3 ; 1\.54\\times ;
#    0\.0027 test ; 6\.9--18\.9 ; 59\.9 ; 66\.6 ; 47\.1 ; 52\.9 ; "beats/outperforms the bandit"
#    (every one of these is a full-collaborator number withdrawn by Change-log P0 ruling (a).
#     The corrected values are 0.89148/0.89691/0.89783, 34.8%, 1.36x, headroom 0.0240 on test,
#     3.7-21.4%, 52.1/58.3 ms and 61.7/38.3. The last pattern is a WORDING guard: the bandit
#     comparator collapses to near-always-L, so "beats" would credit the selector with an
#     outcome that is really a collapse in the comparator -- same guard as the SECOND arm.)

## MACHINE-READABLE PATTERNS (lines beginning "RX "; the exit grep extracts col-4-onward)
RX 0\.2475
RX 1\.98/4
RX 1\.98/8
RX (0\.248[^0-9][^\n]*(Msym|Mbit|payload|C_\{256\})|(C_\{256\}|Msym|Mbit|payload)[^\n]*0\.248[^0-9])
RX divisors being the bits-per-symbol
RX always dominated
RX unconditional dominance
RX 0\.0134
RX n=108
RX difficulty_strata
RX no channel-averaged Pareto advantage
RX (matches|suffices|equals) the learned (RF|selector|policy)
RX threshold (matches|suffices|equals) 
RX 0\.8886
RX 93\.3
RX accuracy versus the oracle
RX 0\.405
RX 40\.5
RX 65\\%
RX 24\.5\\%
RX -0\.025
RX -0\.070
RX -0\.057
RX 28/43
RX tab:ablation_threshold
RX improves F1 by
RX alone improves F1
RX 5\.3 percentage
RX 15\.8
RX 18\.4[^\\%]
RX easier[a-z -]{0,25}(test|scene|split)
RX easy split
RX (stronger|weaker|better|worse)[a-z, -]{0,30}(split|scene|test|domain)
RX eas(y|ier)[a-z -]{0,25}(test|scene|split)
RX \+0\.017.{0,15}(under|F1|jscc|AWGN)
RX 1\{?,?\}?000 validate frames
RX 0\.844
RX 0\.895(?![0-9])
RX \$\\approx 0\.86
RX (cut|save)[a-z' ]{0,28}channel use by
RX 0\.081
RX 0\.888(?![0-9])
RX reproduces \$[0-9]
RX decision agreement
RX base rate
RX selection accuracy
# 17 leaky JSCC two_regime edge (RF + tau tuned ON the eval split). Clean double-freeze reverses it
#    to negative and the leakage-free k-fold gives the honest in-dist +0.022/+0.018/+0.020 (2026-08-02,
#    build_two_regime_edge_clean.py + kfold_two_regime_diag.py). Retired forms: the leaky +0.027 AWGN /
#    +0.025 OFDM edges, and the "oracle-tuned tau on the evaluation frames" phrasing. Abstract/intro/
#    conclusion now carry NO JSCC number; sec:jscc_aware carries in-dist +0.022 and deployed -0.004.
RX \+0\.027
RX oracle-tuned
RX \+0\.025.{0,8}F1 edge
# 18 S={L,C16} formalism (2026-08-02): C256 is dominated -> EXCLUDED from the deployed action set S,
#    which is now 2-element (Eq 1). Retired forms: the 3-element set literal {L,C_{16},C_{256}}, any
#    "selector picks C256" (s_t=C_{256}), and ternary-selector language (three-way/3-way; never present,
#    locked to prevent reintroduction). C256 STILL appears legitimately as the excluded PHY mode (Eq 5
#    q in {16,256}, payload B_{C256}, sec:candidates dominance, Fixed-C256 baseline, rho) -- only the
#    set-membership and selector-choice forms are stale.
RX \{L, ?C_\{16\}, ?C_\{256\}\}
RX s_t ?= ?C_\{256\}
RX three-way
RX 3-way
RX Pareto-dominat
RX Pareto-optimal

# 19 E-P4Bf (2026-08-15): the second-backbone arm FUSED -- the frozen selector does NOT transfer to
#    SECOND under the equal-budget protocol (rho_E 0.000/0.004-0.016 vs oracle 0.302/0.353;
#    selector-vs-oracle agreement 0.833 -> 0.578 -> 0.534; paired dF1 negative at every
#    off-validate point). Any claim that the second backbone validates, confirms or demonstrates
#    generalisation is therefore contradicted by the measurement and is locked out. The ALLOWED
#    wording is "in-sample effective, does not transfer under the equal-budget protocol".
RX second backbone validates
RX validates generalization
RX validates generalisation
RX backbone-independence
RX confirms backbone

# 20 R17 A6 (2026-08-16): the "matched payload / matched channel use" family
#    (P0/R18 UPDATE: "budget-matched" is REMOVED from this ban. It was banned as a vague equal-cost
#     claim; R18-3 introduced tau_feasible, an actually budget-matched comparator, so the phrase is
#     now the precise name for a real object. "matched payload"/"matched channel use" stay banned.)
#    (18\.4 narrowed to exclude "18.4\%" -- the retired AP-band value collided with the corrected
#     Culver payload share. 0\.275 narrowed to its gamma/subtotal context -- it is now est_snr_db's
#     true Gini importance in tab:feat_imp.)
#    overstated comparability -- the selector and the threshold rule are compared per BUDGET, not at
#    a matched payload. Approved replacement: "a threshold tuned on validate for the same target
#    budget". The section V-C transport sentence (C16 vs C256 at equal coded bits) was reworded to
#    "at the same coded-bit count" so this lock is unambiguous; that usage was never the objection.
RX matched payload
RX matched channel use
RX (matched payload|matched channel use)
RX 34\.9
RX 62\.4
RX 0\.349
RX 0\.275[^0-9]{0,12}(gamma|importance subtotal)
RX (6[23]\\%[^\n]{0,140}(importance|ego-side cues)|(importance|ego-side cues)[^\n]{0,140}6[23]\\%)
RX 0\.90463
RX 0\.90326
RX 0\.90734
RX 56\.3\\%
RX 1\.54\\times
RX 6\.9\$--\$18\.9
RX 59\.9\\pm5\.3
RX \\mathrm\{P95\}=66\.6
RX (beats|outperforms|defeats)[^.\n]{0,40}(bandit|reinforcement)
# R23-2: the retired threshold channel-use ratios in sec:threshold's summary paragraph. The
# corrected pair is 1.53x / 1.47x (B_tau/B_RF on test at B_max=0.20 and 0.30, from
# replay_summary.csv). Anchored on the \times so the bare numbers 2.3 / 1.7 stay usable.
RX 2\.3\\times
RX 1\.7\\times
# R23-1: the retired B_max=0.30 test payload. Corrected value 0.21196 (replay_summary.csv,
# split=test, budget=0.3, B_RF). Anchored NUMBER(?![0-9]) per the R20 rule, plus a payload word,
# because 0.187 also appears as a legitimate three-decimal value elsewhere in the record.
RX 0\.187(?![0-9])[^\n]{0,40}(Msym|payload|channel use)
RX (Msym|payload|channel use)[^\n]{0,40}0\.187(?![0-9])

# R20 note on pattern form: a numeric fingerprint must be written as
#   NUMBER(?![0-9])
# and never as NUMBER[^d]. The bracket form CONSUMES the following character, so the sweep cannot
# tell "the retired 0.888" from "a fresh 0.8883", and it also defeats the digit-boundary rule in
# tools/verify_results.py. `0\.888[^6]` was the last of these and is converted; the lookahead form
# preserves the original intent (0.8886 was the legitimate value it had to avoid) and adds prefix
# safety. Sixth instance of this collision family after 0.248, 27.5, 18.4, 0.895 and 0.081.

# R23-8: retired observation (iii) channel-use range. The corrected per-split ranges are
# 0.08102-0.20361 / 0.03680-0.21196 / 0.02437-0.18226 Msym (replay_summary.csv B_RF) = 8.2-20.6 /
# 3.7-21.4 / 2.5-18.4 % of Fixed F. Anchored NUMBER(?![0-9]) per the R20 rule.
RX 0\.158(?![0-9])[^\n]{0,30}0\.251(?![0-9])
RX 16\$?--?\$?25\\%[^\n]{0,40}Fixed

# R23-8: tab:ablation and the masked-oracle rows of tab:gen_headline, both retired. Corrected values
# come from feature_ablation.csv / fixed_references.csv and are now GENERATOR-OWNED
# (tools/build_paper_tables.py: ablation_body(), gen_headline_baselines()).
RX 0\.9011(?![0-9])
# The oracle values are anchored on the ROW LABEL, not written bare: 0.8891 is also a legitimate
# per-SNR value in tab:true_e2e_snr (AWGN 12/20 dB), and a bare pattern flagged it immediately --
# the seventh instance of the collision family recorded at the foot of this file.
RX Channel-aware oracle \(masked\)[^\n]{0,30}0\.(9165|8891)(?![0-9])
RX Channel-aware oracle \(masked\)[^\n]{0,50}0\.(1706|2542)(?![0-9])

# R24-1: the "beats simple rules" family. R21-A-2 established F1 PARITY at the primary cell
# (0.89697 hand rule vs 0.89691 selector, CI [-0.00002,+0.00012]); the selector's advantage is on
# PAYLOAD (28.9% less channel for the same F1). Any sentence claiming an F1 win over a hand /
# simple / threshold rule is retired. Verb-anchored so the payload claim stays sayable.
RX (beats|outperforms|better than|superior to)[^.\n]{0,60}(hand|simple|two-gate|two-parameter|heuristic) rule
RX (hand|simple|two-gate|two-parameter|heuristic) rule[^.\n]{0,60}(is beaten|falls short|cannot match|worse F1)
RX (F1|accuracy) (advantage|gain|win)[^.\n]{0,40}over[^.\n]{0,30}(threshold|hand|simple) rule

# R26-1/2: the easy-stratum effect and the delivery-semantics bracket, both re-read from their own
# products. Retired: -0.0040 (the frozen value is -0.00471 at test/B=0.20, and the effect is
# budget-monotone and split-dependent) and the 690-frame scope (the product says 964).
RX 0\.0040(?![0-9])[^\n]{0,60}(easy|over-request)
RX (easy|over-request)[^\n]{0,60}0\.0040(?![0-9])
RX \$690\$~?frames|the \$690\$ frames

# R28: the C256 paragraph's three pre-corrigendum percentage families, and the second harm
# quantifier, all sourced from results/sensitivity/c256_dominance_verify.csv (now registered in
# tests/retired_products.md as retired-not-a-source). Corrected: the paragraph carries no fractions
# at all, and the harm triple is 1.3 / 6.5 / 0.9 from the N=1 caches.
RX 99\.0 / 94\.2 / 99\.1
RX 0\.7 / 4\.2 / 0\.9
RX 2\.5 / 3\.2 / 4\.5
RX 1\.0 / 5\.8 / 0\.9

# R29: the "verify generalisation" family. Under a frozen selector the COMMUNICATION SAVING
# transfers to test and Culver-City, but F1 non-inferiority does NOT hold on Culver at B_max=0.20
# (dF -0.00883, CI [-0.00902,-0.00865], outside the 0.005 margin). "Verify generalisation" asserts
# both halves; only one survives. Verb-anchored so the transfer claim about payload stays sayable.
RX verify[a-z ]{0,20}(cross-split|domain-shift|Culver-City)[a-z ]{0,20}generalisation
RX (confirm|establish|demonstrate)[a-z ]{0,25}generalisation (to|across) (the )?(test|Culver)
RX generalis(es|ation) (holds|transfers) (on|to) (both|all) split

