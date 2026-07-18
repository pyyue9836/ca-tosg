# STALE FINGERPRINT LEDGER -- the block-exit grep reads THIS file, not memory
# (verification-derive-not-hardcode applies to the exit check itself). Each pattern is a v2/stale form that
# must have ZERO matches in a clean main.tex. Accumulated from all interceptions. Exit grep:
#   grep -nE -f <(grep '^RX ' STALE_FINGERPRINTS.md | cut -c4-) paper/main.tex   # expect 0 hits
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
# 9  payload uncoded (numeric double)     RX: 0\.2475 ; 1\.98/4 ; 1\.98/8 ; 0\.248[^0-9] ; divisors being the bits-per-symbol
# 10 robustness split label (test->valid) RX: (handled by caption audit; no safe text pattern -- manual)
# 11 gamma-improves (narrative)           RX: improves F1 by ; alone improves F1 ; 5\.3 percentage
# 13 review-side ~10% payload             RX: 10\\%.{0,30}(payload|channel use) ; (payload|channel use).{0,30}10\\%
# AP/band v2                              RX: 15\.8 ; 18\.4 ; \+0\.045 ; \+0\.017 ; \+0\.018 ; \+0\.05[^0-9]

## MACHINE-READABLE PATTERNS (lines beginning "RX "; the exit grep extracts col-4-onward)
RX 0\.2475
RX 1\.98/4
RX 1\.98/8
RX 0\.248[^0-9]
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
RX 0\.895
RX C-value = three-name distinction (a7 -0.0002 / Pareto +0.0005 / two-regime +0.005) -- see checklist
