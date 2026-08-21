# Paper ↔ protocol reconciliation (R45-6)

`tests/test_protocol_reconciliation.py` reads this table. Each row pairs a **finding recorded in
`docs/experiment_protocol.md`** with what the delivered documents are allowed to say about it. The
gate exists because the two files drifted apart twice without any existing check noticing: the
protocol recorded a measurement as *false as written*, and `main.tex` went on asserting the
retired form for four more batches.

Columns:

| column | meaning |
|---|---|
| `id` | short label for the pair |
| `protocol_probe` | a substring that must be present in `docs/experiment_protocol.md`; if it disappears, the row is stale and the gate FAILS (the record is the anchor, so it may not vanish silently) |
| `verdict` | `false-as-written` or `superseded` — what the protocol says about the retired claim |
| `retired_regex` | the retired form. **Zero** matches allowed in `main.tex` + `supplementary.tex` |
| `required_probe` | a substring at least one delivered document must contain — the replacement claim. Empty means "no positive requirement" |
| `why` | why this pair is load-bearing |

A literal `|` inside a regex breaks the markdown row, so alternation is written `&#124;`.

| id | protocol_probe | verdict | retired_regex | required_probe | why |
|---|---|---|---|---|---|
| anchor-insensitivity | "Conclusions are insensitive to this constant" — measured, and false as written | false-as-written | `conclusions are insensitive to this constant&#124;rescale the feature cost of all policies equally&#124;insensitive to this (constant&#124;anchor)` | declared source-budget convention | The protocol measured the counterfactual: the headline channel-use fraction moves by −0.90 % to −7.75 % under the paper's own named re-anchor and −4.86 % to −41.99 % under the declared→deployed one. Only the ordering survives. The paper asserted the opposite for four batches after the measurement landed. |
| c256-dominance | SUPERSEDED BY R31-1 | superseded | `(dominated&#124;dominates)[^.\n]{0,40}C_?\{?256\}?` | physical-layer comparator | R31-1 withdrew the set-domination argument: C256 is excluded by design (modulation order is a transport parameter), not by measurement. |
| reference-tensor | The reference geometry is not the deployed tensor | false-as-written | `(transmitted&#124;deployed) BEV feature tensor of size&#124;encodes the transmitted BEV feature tensor&#124;y \\in \[-38\.4, 38\.4\]` | This reference geometry is not the transmitted tensor | R46-1: the 256x48x176 geometry is the JSCC baseline's, used here only to fix a source-budget convention. The deployed pointpillar checkpoint is configured y in [-40, 40] and its three-branch pyramid measures 3,942,400 pre-compression / 739,200 transmitted elements. Calling the reference the transmitted tensor asserts a measurement that contradicts the probe. |
| shared-backbone | The branches do NOT share weights | false-as-written | `(all methods&#124;all branches)[^.\n]{0,50}(share&#124;shares) the same (backbone&#124;weights)&#124;(identical&#124;the same) backbone and detection head` | do \emph{not} share weights | R46-2: L's late-fusion checkpoint and F's attentive-compression checkpoint are separate trainings, so the clean-channel gap between them carries each branch's whole pipeline. The unified-weight construction that would license the retired sentence is pre-registered and not run. |
| headroom-fov | field-of-view effect rather than a granularity effect | false-as-written | `headroom[^.\n]{0,120}(purely&#124;entirely&#124;solely) (a )?(semantic&#124;granularity)` | fields of view differ | R53: the headroom triple is measured between branches with different configured ranges (L x +-70.4, F x +-140.8) against one canonical GT that reaches &#124;x&#124; ~ 119 m. Inside a common volume it falls to 0.0117 / -0.0061 / 0.0252, changing sign on test. Any sentence attributing the headroom purely to granularity contradicts the diagnostic. |
| w2c-no-verdict | budget-matched comparison at the confirmatory cell could not be performed | false-as-written | `[Ww]here2comm[^.\n]{0,90}(?<!not )(?<!could not be )(adjudicat&#124;verdict&#124;confirmatory (win&#124;loss&#124;result))` | could not be performed | R57: the confirmatory cell was never run -- the comparator's threshold has no setting within +-20% of the 0.20 cap, bracket [0.0802, 0.3130] on test. Any sentence claiming a verdict for this arm contradicts the record. |
| latency-budget | Selector-only latency | superseded | `fits (the&#124;within the) \$100\$~ms budget&#124;within the \$100\$~ms frame interval` | end-to-end system latency is not measured here | The measured quantity is the selector alone; "fits within the 100 ms budget" reads as an end-to-end system claim the paper never measured. |
