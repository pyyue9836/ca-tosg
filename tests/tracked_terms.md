# Tracked terminology (R27-1)

Entities whose *description* — not whose number — has gone wrong more than once. `p6_cross_section_scan.py`
reads this table as its TERMINOLOGY class: any match of `forbidden` in `paper/main.tex` is a
conflict, and `reason` says why the wording is wrong rather than merely dispreferred.

| term | forbidden (regex) | required framing | reason |
|---|---|---|---|
| signalling direction | `the sender (adaptively )?(selects&#124;decides&#124;chooses)` | the ego receiver selects and requests; the collaborator transmits what was requested | The architecture is receiver-driven (Sec. III-A): the ego evaluates its own perception and channel state and signals a 2-bit request. Writing it sender-side inverts the contribution. Third recurrence — corrected in R27-1. |
| signalling direction | `sender-driven` | receiver-driven | Same entity, adjectival form. |
| JSCC arm status | `ImportanceMapJSCC[^.]{0,80}(mainline&#124;main protocol&#124;headline table)` | prior-protocol, exploratory, Appendix A only | The JSCC arm was never re-evaluated under the frozen single-collaborator protocol and appears in no mainline table (R27-2). |

A literal `|` inside a regex breaks the markdown row, so alternation is written `&#124;` and decoded by the parser — the first draft of this table silently parsed 1 of 3 rows, and the self-test caught it because the injected fault stopped firing.
