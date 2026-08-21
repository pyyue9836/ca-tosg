# Registered comparison claims (R25-6)

Every explicit comparison the paper makes between two policies, as a checkable tuple.
`tests/test_comparison_direction.py` looks both quantities up in the canonical product that owns
them and fails when the claimed direction disagrees with the data. `probe` is a verbatim fragment of
the sentence that makes the claim; if the sentence disappears or is reworded, the row is reported so
the table cannot drift away from the text.

Directions: `>` A exceeds B, `<` A is below B, `~` parity (within 0.0005).

| label | A | B | dir | metric | split | budget | probe |
|---|---|---|---|---|---|---|---|
| threshold-F1-B010 | RF | tau_nominal | < | F1 | test | 0.10 | `the nominal threshold` |
| threshold-F1-B020 | RF | tau_nominal | < | F1 | test | 0.20 | `attains the marginally higher F1 at \emph{every} budget` |
| threshold-F1-B030 | RF | tau_nominal | < | F1 | test | 0.30 | `` |
| threshold-payload-B010 | RF | tau_nominal | < | payload | test | 0.10 | `` |
| threshold-payload-B020 | RF | tau_nominal | < | payload | test | 0.20 | `` |
| threshold-payload-B030 | RF | tau_nominal | < | payload | test | 0.30 | `` |
| feasible-F1-B020 | RF | tau_feasible | > | F1 | test | 0.20 | `ahead by $+0.00067$ at $0.20$` |
| feasible-F1-B010 | RF | tau_feasible | < | F1 | test | 0.10 | `` |
| feasible-F1-B030 | RF | tau_feasible | < | F1 | test | 0.30 | `` |
| channel-only-F1-B030 | channel_only | combined | < | F1 | test | 0.30 | `beaten on \emph{both} axes` |
| channel-only-payload-B030 | channel_only | combined | > | payload | test | 0.30 | `` |
| handrule3-F1-B020 | hand_rule_3 | RF | ~ | F1 | test | 0.20 | `it \emph{matches} the selector on F1` |
| handrule3-payload-B020 | hand_rule_3 | RF | > | payload | test | 0.20 | `The difference lies on the other axis` |
| handrule2-payload-B020 | hand_rule_2 | RF | < | payload | test | 0.20 | `degenerating to Fixed $L$` |
| abstract-handrule-F1 | hand_rule_3 | RF | ~ | F1 | test | 0.20 | `a three-scalar hand rule reach comparable F1` |
| abstract-handrule-payload | hand_rule_3 | RF | > | payload | test | 0.20 | `sending more feature messages, so the cues buy` |
| abstract-threshold-F1 | RF | tau_nominal | < | F1 | test | 0.20 | `non-inferior to the nominal SNR threshold within a $0.005$ margin` |
| common-volume-test | ceiling_common_volume | fixedL_common_volume | < | F1 | test | 0.20 | `on test it changes sign to $-0.0061$` |
| w2c-desc-validate-B010 | w2c_isect | catosg_isect | > | F1 | validate | 0.10 | `favour Where2comm by between $+0.00021$ and $+0.00723$` |
| w2c-desc-test-B010-REVERSED | w2c_isect | catosg_isect | < | F1 | test | 0.10 | `one favours \method{} by
$-0.00132$` |
| w2c-desc-culver-B030 | w2c_isect | catosg_isect | > | F1 | culver | 0.30 | `the $0.30$ rows are partly bought` |
