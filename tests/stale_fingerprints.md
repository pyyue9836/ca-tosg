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
#     Coverage was narrowed in CONTEXT, never in VALUE -- a payload sentence quoting 0.248 still fails.)
# 10 robustness split label (test->valid) RX: (handled by caption audit; no safe text pattern -- manual)
# 11 gamma-improves (narrative)           RX: improves F1 by ; alone improves F1 ; 5\.3 percentage
# 13 review-side ~10% payload             RX: 10\\%.{0,30}(payload|channel use) ; (payload|channel use).{0,30}10\\%
# AP/band v2                              RX: 15\.8 ; 18\.4 ; \+0\.045 ; \+0\.017 ; \+0\.018 ; \+0\.05[^0-9]
# 14 two_regime panel(a) JSCC-flat level  RX: \$\\approx 0\.86 (validate flat 0.86 -> test 0.89; the near-
#    approx form only; bare table 0.864 untouched. Anchors the $\approx$ so 0.864 F1 cells never trip it.)
# 15 transitive-verb evasion (TG-10)       RX: (cut|save)[a-z' ]{0,28}channel use by  (retired "cut/save
# 16 acc-vs-oracle escape (TG-22)          RX: reproduces \$[0-9] ; decision agreement ; base rate ; selection accuracy (item-6 killed the metric; generalisation prose kept it via "reproduces X%")
#    channel use by X%"; fixed to "lower ... deployed channel use"; narrow enough to skip "reduce payload")

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
RX 18\.4
RX easier[a-z -]{0,25}(test|scene|split)
RX easy split
RX (stronger|weaker|better|worse)[a-z, -]{0,30}(split|scene|test|domain)
RX eas(y|ier)[a-z -]{0,25}(test|scene|split)
RX \+0\.017.{0,15}(under|F1|jscc|AWGN)
RX 1\{?,?\}?000 validate frames
RX 0\.844
RX 0\.895[^9]
RX \$\\approx 0\.86
RX (cut|save)[a-z' ]{0,28}channel use by
RX 0\.081
RX 0\.888[^6]
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

# 20 R17 A6 (2026-08-16): the "matched payload / matched channel use / budget-matched" family
#    overstated comparability -- the selector and the threshold rule are compared per BUDGET, not at
#    a matched payload. Approved replacement: "a threshold tuned on validate for the same target
#    budget". The section V-C transport sentence (C16 vs C256 at equal coded bits) was reworded to
#    "at the same coded-bit count" so this lock is unambiguous; that usage was never the objection.
RX matched payload
RX matched channel use
RX budget-matched
