# Gate design — the standard library

Four rules, each bought with a real failure in this repository. They are collected here because they
were previously scattered across change-log entries, which meant each one had to be rediscovered.
A new gate is reviewed against all four before it is registered in `tools/verify_results.py`.

---

## 1. Judge the capability, not the intent

A gate must ask *"could this happen?"*, never *"was this meant to happen?"*.

**Bought by:** work package 2 computed held-out accuracy before the selector freeze (V2-R6 A). Moving
the products to `results/v2/sealed/` and putting the generator behind `--held-out-eval` were repairs;
what makes them hold is gate 22, which scans every live `.py` for the *ability* to read sealed
accuracy. The same reasoning produced gate 21: a retired product is banned not only as evidence but
as something any script could re-create.

**Test:** if the gate would pass a tree in which a careless edit re-enables the hazard, it is
checking intent.

## 2. A pattern being alive is not the code running

A regex, a registry row or a documented convention proves only that a *string* exists. It says
nothing about whether the code that consumes it still executes.

**Bought by:** R43-4 — generators whose substitution patterns had silently stopped matching the
delivered text, so the generator ran, changed nothing, and reported success. Also R68: a report tool
that always returned 0 and that nobody re-ran, leaving `MISS 0` on record while a fresh run said
`MISS 1`.

**Test:** does the gate *execute* the thing it certifies, or only read what that thing left behind?

## 3. A gate with a false positive is worse than no gate

It teaches people to skip the suite, and a skipped suite protects nothing.

**Bought by:** gate 22 needed three narrowings (`results_index.py` *catalogues* the `--held-out-eval`
command in an attribution row; it shells out to `git ls-files` for an unrelated reason; hashing every
file under `sealed/` made editing that directory's README read as tampering). Gate 24's serialisation
had to be pinned for the same reason.

**Corollary, V2-R20 D-1:** *before* concluding a gate is a false positive, check whether it has found
something real and merely lacks the vocabulary to say what. The `intra-repo imports` failure was
called a false positive; it was a genuine reproducibility hole — a required module existed in one
working tree and in no patch. The remedy was to make the gate *precise*, not to exempt the import.
**Narrowing a blunt gate and loosening a gate look alike in the diff and are opposites in effect.**

## 4. A gate that cannot fail

The worst of the four, because it reports success forever and nothing distinguishes it from a gate
that is working.

**Bought by, as a near miss:** V2-R19's row-1 binding check read a dict key that does not exist at
that level, so every digest came back `None` — and the negative control, written as
`if c is None or c != a`, counted `None` as "differs" and **passed vacuously**. It would have
reported a control that never ran as a control that succeeded.

**Bought by, as a design question:** the identity-alignment audit costs ~25 minutes on validate, so
gate 25 stores its verdict. A stored verdict re-read from a JSON that says `100 %` is exactly a gate
that cannot fail. The fix is the positive instance of this rule: **the audit records the SHA-256 of
every product it was computed from, and the gate recomputes them**, so a verdict that no longer
describes the tree is a FAIL rather than a pass. The cheap parts are additionally re-run live.

**Instances so far — the list is kept because the shape recurs and the count matters:**

| # | where | how it could not fail |
|---|---|---|
| 1 | V2-R19 row-1 binding check | every digest came back `None`; the control read `if c is None or c != a`, so `None` counted as "differs" and passed vacuously |
| 2 | gate 25, by design question | a stored `100 %` verdict re-read from JSON — fixed by recording the inputs' SHA-256 and recomputing them |
| 3 | gate 27's F-2 | scanned `forbidden_and_absent` for banned words, i.e. flagged a declaration for containing the words it exists to contain (that is failure 3, but it arrived from the same carelessness) |
| 4 | gate 26's negative control | a `None` from the 2nd-nearest arm would have counted as "differs" — caught before it shipped |
| 5 | **V2-R25 `eff_f` self-check** | compared the interpolant against **the same matrix it was built from**, which is self-consistent by construction; all three D-4 injections came back SILENT. Fixed with an explicit reference matrix; injections now FIRE and node reproduction is exact to 1e-12. **Written, run and corrected by the executor within one batch** — the injection is what found it, not review |

**Test — the only reliable one:** every gate carries a `--self-test` that *injects the fault it
claims to catch* and asserts the gate FIRES, with a clean baseline asserted first so that a firing
for an unrelated reason cannot be mistaken for coverage. Gates 24, 25 and 26 carry 3, 5 and 3
injections respectively. Where an injection is *expected* to stay silent — a renamed field with no
source evidence, in `test_cue_field_whitelist.py` — that limitation is asserted and printed, so the
hole is documented rather than discovered.

---

### A positive instance, recorded because the shape is reusable (V2-R33 E-1)

**The unseal register.** After WP11 the primary result legitimately lives in the open tree, and the
obvious way to let it is to add the file to an allow-list. That would have exempted it **by name** —
the same hole rule 3's corollary describes. Instead `results/manifests/V2_UNSEAL_RECORD.json` records
the path, timestamp, commit, hash and scope of the unsealing act, and gate 22 consults that record.

**The file is readable because a dated act made it so, not because someone edited a set literal.**
That is "judge the capability, not the intent" applied constructively: the gate still judges
capability, and the register supplies the one thing a capability check cannot — *when, and by what,
this became permitted*.

### Why the fourth was not obvious

Rules 1–3 are about a gate being *too weak*, *misdirected*, or *too noisy*. Rule 4 is about a gate
being **unfalsifiable**, and it is invisible to every ordinary check: the suite is green, the gate is
registered, the artefact exists, and none of that is evidence. The only thing that distinguishes a
working gate from an unfalsifiable one is having watched it fail on purpose.

---

### A table with no generator (V2-R40 C-2)

`results/baselines/where2comm_v2/sparsity_payload.csv` carried a `B_w2c_msym` column whose recorded
provenance was *"`sweep.sh` then the accounting in the R55/R57 change-log"* — that is, **arithmetic
done by hand in prose**. No generator owned it, so nothing could re-derive it, and nothing would have
noticed it drifting.

It went wrong twice over: the column was **hand-maintained**, and the convention it encoded
(0.9155 bit/element) was **v1's**, which §3.3 had already reduced to a historical reference. The
column is now retired outright rather than recomputed.

**The rule this instance buys, and it is a standing one (V2-R41 A-2): a number no script can
regenerate is a NOTE, not a RESULT.** `docs/HANDOFF_V2.md`'s closing checklist exists for exactly this failure mode, and this is the
case where the generator never existed at all.

---

## 5. The generate-then-verify chain breaks at the figure

Every other artefact in this repository is checked by regenerating it and comparing. A figure cannot
be checked that way: it regenerates byte-identically while being *wrong about the system it depicts*.

**Bought by (V2-R44 A-1):** the first `fig1_system` drew the channel estimate as an output of the
collaborator's LiDAR — it is an ego-side input — and ran an arrow from action E into the transport
chain, when E sends no message at all. Both survived generation, provenance hashing and the whole
33-gate suite, because **both are semantic errors, not numeric or lexical ones**. They were found by
rendering the PDF to a raster and looking at it.

**Same blind spot as R63** ("the gates check committed artefacts and none of them runs the
generator"), one level further out: here the generator *does* run, and what it produces still has to
be read by a person.

**The rule:** a figure is not done when it is generated. It is done when someone has rendered it and
looked at it against the thing it claims to describe.

## 6. Never two y-scales on one panel

**Bought by (V2-R44 A-2):** the primary result has a payload ratio of ~400× beside an $F_1$
shortfall of 0.0024. The tempting layout is one panel with two y-axes.

It must not be, and the reason is specific rather than aesthetic: **with two scales, the point where
the curves cross is an artefact of the scaling choice**, and a reader cannot tell which ruler a mark
belongs to. The claim here is precisely a crossing — the confidence bound crosses the preregistered
margin — so it has to be *seen*, not asserted. That requires the bound and the margin on **one
ruler**, which means a separate panel at its own scale, with the large-ratio quantity given a log
axis of its own.

### Instances six and seven of "a gate that cannot fail" (V2-R48 C-2)

`tools/p6_numbers_vs_csv.py` and `tools/build_paper_tables.py` both read the delivered manuscript
behind `if os.path.exists(...)`. Neither would have raised when the path moved; both would have
reported success over an empty string. The guards are removed and a missing frozen document is now
a failure.

**The general shape:** a fallback that turns "I cannot check this" into "there is nothing to
check". It is invisible while the path is right, and it is exactly wrong at the moment the path
stops being right — which is the only moment the check mattered.

### Instance eight: the exception that excused its neighbour (V2-R48 C-1)

`tests/test_paper_numbers_are_macros.py` searched for a registered exception pattern anywhere in a
$\pm 60$-character window around a numeric literal. `AP@0.5 of 0.86994` was therefore excused by
the row that legalises the metric threshold `0.5` — a hand-typed AP passing the gate written to
catch hand-typed APs. A pattern now excuses only the literal its own match covers.

**Bought by:** the gate's own injection self-test, on its first run. A whitelist scoped to a window
rather than to the token is a whitelist that grows silently with the text around it.

### Instance nine: a rule that had never been run against the text it governs (V2-R49 B-2)

The ruled sentence *"...not a demonstration that a learned selector beats simple rules---at equal
budget it does not"* matches the retired-claim pattern `beats ... simple rule` word for word. It sat
in the 4-page brief for two rounds and never fired — **not because the sweep judged it and cleared
it, but because the brief's path, `paper/v2_draft/main.tex`, was not on the target list.** Moving
the same sentence into `paper/main.tex`, which is on the list, is what surfaced it.

**A rule that has never run against the text it governs has not been verified.** This is the same
family as "a gate that cannot fail" with a different cause: those fail because the judgement is
self-consistent, this one because the coverage had a hole. `tests/test_fingerprint_coverage.py`
(gate 35) closes it by requiring the target list to cover every delivered document, with an
injection that removes one and checks it fires.

### Why the pattern was narrowed and the text was not (V2-R49 A-4)

The pattern's intent is *"no claim of an F1 win over a hand or simple rule survives."* The sentence
it fired on **is that claim's withdrawal** — same words, opposite direction, and the pattern is
verb-anchored so it cannot tell them apart. The fix is a fixed, enumerable list of withdrawal
lead-ins (`NEGATION_LEADINS`), applied only within the sentence containing the match, with
injections proving the affirmative form still fires and that deleting the negation restores the
failure.

**Editing the conclusion so the regex stops complaining would let the guard write the conclusion.**
That is the line: a gate may constrain how a result is stated, and may never decide what the result
is. The narrowing has an exact scope and three tests; the alternative had neither.

**And one shortcut refused, recorded because it worked.** `[^.\n]` excludes newlines, so simply
breaking the line between "beats" and "simple rules" would have silenced the sweep completely. The
reader would see the identical words. Literally true, read false — against the gate itself.

### Near-identical names with unrelated meanings — the fourth instance (V2-R53 A-3)

`n_box_collab` is what the collaborator **transmits**, and is what the object-level payload is
billed on. `n_box_L` is the **post-fusion late-detection output**, and is never charged. The paper's
payload paragraph quoted the second while describing the first. The billing itself was always
correct; only the sentence was wrong.

Confirmed by re-deriving rather than by reading the code: pushing each candidate count through the
real chain (184 bit/box → 8000-bit packets with 320-bit headers → LDPC $K=500$) and comparing the
predicted codeword count against the recorded one, frame by frame —

| count | exact per-frame match | mean predicted $N_{cw}$ |
|---|---|---|
| `n_box_collab` (24.08) | **94.85 %** | 10.049 |
| `n_box_L` (28.40) | 15.05 % | 11.691 |
| `n_box_ego` (22.56) | 31.06 % | 9.484 |

against a recorded mean of 10.101.

**The family, now four deep:**

1. `p_cw` versus `p_cw_F` — a per-codeword probability read as a per-message one;
2. one IoU threshold reused for two different comparisons that needed different values;
3. `catosg_split` missing, so a seed identity silently read `'unknown'` and the arm ran under a
   different seed space from every other product;
4. `n_box_collab` versus `n_box_L` — this one.

**What makes the family dangerous is the shared shape, not the shared topic:** the names differ by
one token, the meanings do not overlap, taking the wrong one raises nothing, and the number that
comes out is the right order of magnitude. Nothing in a re-read distinguishes them. The fix is the
same each time — **give the two quantities names that cannot be confused, and delete the ambiguous
one without leaving an alias**, because an alias preserves exactly the confusion being removed.
