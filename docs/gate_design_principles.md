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
