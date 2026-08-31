# STOP-WORK ORDER — v1 manuscript frozen pending the plan-A re-freeze

**In force from commit `400bfb6d` (the R71 tip, this file's parent).** Issued by Josh, V2-R1
(revised), item 1. Lifted only by Josh, in writing, when plan A's re-freeze lands.

## What is frozen — zero changes until the plan-A re-freeze

| frozen | why it is on the list |
|---|---|
| `paper/main.tex` | the whole manuscript, not only its numbers |
| `paper/supplementary.tex` | same |
| the abstract | it carries the headline payload range |
| `tab:headline`, `tab:headline_agg`, `tab:gen_headline` | the headline tables |
| every results figure | `fig_ap50_*`, `fig_payload_awgn`, `fig_decisions_*`, `fig_stacked_area`, `fig_pareto_test`, `fig_difficulty`, `fig_feature_importance` |
| the Conclusion | it restates the headline |
| the page count | 16 main / 12 supplementary — not a target to optimise while frozen |

**No new gate may be added for a v1 result.** The verification suite stands at 21 checks and stops
there for the v1 manuscript. Hardening a number that plan A is about to replace spends effort on a
result with a scheduled end, and — worse — makes it more expensive to withdraw. Gates for the plan-A
products are a separate question, decided after the protocol is locked.

## What is NOT frozen

* `docs/unified_branch_protocol_v2.md` and everything it governs — the point of the freeze is to let
  the protocol be written without the manuscript moving under it.
* `results/v2/**` — plan-A products, which are new files, not edits to frozen ones.
* `docs/history/protocol_changelog.md`, `docs/HANDOFF.md` and this file — the record must stay able
  to record.
* Bug fixes to *tooling* that do not change a delivered number. If one would, it stops and asks.

## Why a freeze rather than "just be careful"

Plan A re-derives all three actions from one checkpoint, which changes `B_L`, `B_F`, the action mix,
the payload axis and every headline cell that rests on them. A v1 edit made in the meantime is work
that will be thrown away at best, and at worst survives into the v2 manuscript as an
un-re-derived sentence — the exact failure the P0 corrigendum cost a full rebuild to clear.

The v1 results are **not withdrawn and not deleted**. They are a completed, verified, internally
consistent state, and they stay exactly as they are until there is something to replace them with.
Their disposition — history track, with labels, per V2-R1 item 2h — is decided in the protocol, not
here.

## An operational trap, found on the first day of the freeze

**`python tests/test_compile.py` rewrites `paper/main.pdf` and `paper/supplementary.pdf` every time
it runs** — and it runs as one of the 21 gates, so `tools/verify_results.py` mutates two frozen files
as a side effect. The rewritten bytes are not content-identical to the committed ones even after
normalising `/CreationDate`; tectonic varies other metadata too.

Under the freeze, after any full gate run:

```bash
git restore paper/main.pdf paper/supplementary.pdf     # the freeze holds byte-for-byte
```

The gate still verifies (16 pages, 12 pages, 0 errors); what is discarded is a byte-identical-in-
content rebuild that would otherwise show up as a diff on a frozen file. Do not commit a PDF change
while the freeze is in force.

## Standing check before touching anything

If a change would alter a byte of `paper/main.tex` or `paper/supplementary.tex`, or any number in a
committed `results/main/**` product, it is inside the freeze: stop and ask Josh. Everything else is
ordinary work.

---

## AMENDMENT — Josh's ruling, V2-R47 A (2026-08-31)

**This supersedes nothing above; it relocates what the freeze protects and says so explicitly.**

### A-1 — the frozen documents are archived, not deleted, and not edited

| was | is now |
|---|---|
| `paper/main.tex` | `paper/archive/manuscript_frozen.tex` |
| `paper/supplementary.tex` | `paper/archive/supplementary_frozen.tex` |
| `paper/v2_draft/main.tex` (the 4-page brief) | `paper/archive/results_brief.tex` |
| `paper/main.pdf` | `paper/archive/manuscript_frozen.pdf` |
| `paper/supplementary.pdf` | `paper/archive/supplementary_frozen.pdf` |

Moved with `git mv`, so the history follows the content.

### A-2 — the protection level does not drop

The three `.tex` files and the two PDFs stay **in HEAD** and stay **byte-for-byte unchangeable**.
`V1_FREEZE_WITNESS.json` keeps its original SHA-256 values; only the paths it names change. A
one-byte edit to any archived file is a gate FAILURE, exactly as before the move. The gate carries
an injection self-test that proves it fires.

**Why a path change is not a weakening:** the witness compares the **committed** blob. The content
being verified, the hash it is verified against, and the failure it produces are all unchanged. What
moved is where in the tree that content sits.

### A-3 — one official manuscript, no version suffixes

The journal-length manuscript is built under `paper/` with no version-suffixed names:
`paper/main.tex`, `paper/supplementary.tex`, `paper/references.bib`, `paper/figures/`,
`paper/tables/`. **There is exactly one manuscript under `paper/`.** No `v2_draft/`, no `v2_full/`,
no parallel copy. `paper/archive/` holds superseded documents and is never a second live draft.

### A-4 — what the archive may be used for

The archived long-form manuscript is **structure and bibliography material only**. Every
experimental number, figure, table and conclusion in the new manuscript comes from the closed-out
products via `tools/build_v2_paper_numbers.py`. No number is copied out of the archive.

### A-5 — naming

New paper-side files carry no version suffix. The `V2_*` manifest filenames are referenced by gates
and are **not** renamed this round; they are renamed together once the manuscript is final.

### What this amendment does NOT lift

The archived documents remain frozen under the original terms above. "Frozen" now means: present in
HEAD at the archive path, hash-pinned, and never edited. The freeze on `results/main/**` is
untouched.
