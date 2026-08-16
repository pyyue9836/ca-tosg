# R17-C — sentences proposed for deletion or recompute (STOP POINT)

**Nothing here has been deleted.** R17-C requires this list to be read before any sentence goes.

The four families named in the ruling are bound and are no longer candidates: the abstract payload range (`tests/test_payload.py` 3b chain), the feature importances (recomputed from the frozen `selector_B020.pkl` into `results/main/feature_importance_frozen.csv`), the selector latency (`results/latency/selector_latency.csv`) and the payload reduction (`results/main/replay_summary.csv`). Every structural-constant claim is cited to its derivation and the notation table. These five are the whole residue: sentences carrying numbers that no committed result file holds.

Rule each with `delete`, `recompute` (I cost it first and report back) or `leave` (kept, marked "no committed evidence" in the ledger).

### B — full claim text for the rows proposed for deletion or recompute

**B4 `cdc39e3` — Results and Analysis → Generalisation to OPV2V Test and Culver-City Splits [sec:generalisation], line 561**

> Both intervals are budget-indexed and are read from replay\_summary.csv and fixed\_references.csv; the single-number recovers 99.3--99.8\% of the oracle claim of an earlier version conflated the three budgets and is withdrawn.

**B5 `cec993e` — Results and Analysis → Is a Learned Selector Necessary? Comparison with an SNR-Threshold Rule [sec:threshold], line 700**

> Neither half of the input is sufficient on its own, and the shape of the failure is the informative part: given only the channel state the selector stops requesting features altogether at the two tighter budgets (feature-request rate 0, payload pinned at B_L), and at B_=0.30 it does reach a higher F1 than the full selector but only by spending 1.54 × the channel use (Section [ref]).

**B6 `cdffce3` — Results and Analysis → Is a Learned Selector Necessary? Comparison with an SNR-Threshold Rule [sec:threshold], line 710**

> Dropping the range, density, or object-count cue groups changes F1 by <0.001; the channel-averaged payloads are in Table [ref].

**B7 `c314995` — Results and Analysis → Deployment Robustness and Cost [sec:robustness], line 799**

> The framework also spans the full fading-severity range: replacing the AWGN/Rayleigh limits with Rician fading moves the feature-activation knee smoothly between them as the line-of-sight component strengthens, and the two-regime result of Appendix [ref] reproduces under OFDM (in-distribution +0.020 F1 edge).

**B8 `c2aa3e2` — When Are Perception Cues Necessary? LDPC Cliff versus JSCC Graceful Degradation [sec:jscc_aware], line 900**

> The selector recovers 55--70\% of the clairvoyant oracle headroom (e.g.\ +0.031 F1 on AWGN test): the graceful-channel decision is genuinely content-bound and carried by the ego-side cues, a gain no SNR threshold can reach.


---

## How to rule

Reply with row ids and a verb; ranges and blocks are fine. Anything not mentioned is left untouched.

- **List A** verbs: `caption` (state it in the caption), `body` (state it in the text), `drop` (stop drawing it), `label` (add the condition), `leave`.
- **List B** verbs: `evidence` (attach the cited source), `recompute` (I run it and report cost first), `delete` (remove the sentence), `leave`.

e.g. `A2-A7 caption; A8 drop; B1-B41 evidence; B44 delete; rest leave`.

The landing pass applies every ruling in one batch, regenerates the ledger and the figure-consistency list, and re-runs all nine gates.
