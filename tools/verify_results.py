#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the gates. Exit 0 iff all that ran passed.

  python tools/verify_results.py                 every gate: needs the git-excluded data/p2/
                                                 artefacts and the sibling OpenCOOD checkout
  python tools/verify_results.py --content-only  only the checks a CLEAN CLONE can run (15 of 29)

  A clean clone CANNOT complete the full verification, and this script does not pretend otherwise:
  the fourteen artefact-tier gates fail loudly on missing data rather than skipping, because a gate that
  cannot verify must never report success. --content-only is the honest subset, not a softer run.

  GATE-COUNT-LINE: 29 checks in total, 15 of which a clean clone can run.

  python tools/verify_results.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


import re
import subprocess

PY = sys.executable
# Tier, re-derived from MEASURED dependencies (P0-4), not from how each gate was labelled when it
# was written. A gate was run with `torch`, `spconv` and `sionna` replaced by import-raising stubs;
# the local-artefact column was read off each file's own references.
#
#   'content'   -- no torch/spconv AND no git-excluded artefact: runs on a clean clone
#   'artifacts' -- needs torch (frozen .pt/.pkl models) or the git-excluded data/p2 + OpenCOOD caches
#
# What moved and why:
#   bandit fold scaling   content -> artifacts   loads data/p2/p4a_bandit_B0XX.pt, so it needs torch
#   payload chain         content -> artifacts   no torch, but it reads the sibling OpenCOOD
#                                                checkout (dataset_validate_v3.csv + a hypes yaml)
#   data leakage, manifest  stay artifacts       both read data/p2 + the OpenCOOD cue CSVs
#   assumptions ledger    content                its artefact references are STRINGS it scans for,
#                                                not files it opens
GATES = [
    ('artifacts', 'payload chain',        [PY, 'tests/test_payload.py']),
    ('content',   'paragraph insertion',  [PY, 'tests/test_paragraph_insert.py', '1', '2', '3']),
    ('content',   'claims vs main.tex',   [PY, 'tests/test_result_consistency.py', '--check']),
    ('artifacts', 'data leakage + freeze',[PY, 'tests/test_data_leakage.py']),
    ('artifacts', 'manifest relpaths',    [PY, 'tests/test_manifest.py']),
    ('artifacts', 'bandit fold scaling',  [PY, 'tests/test_bandit_fold_scaling.py']),
    ('content',   'P3 SNR support',       [PY, 'tests/test_p3_snr_support.py']),
    ('content',   'intra-repo imports',   [PY, 'tests/test_intra_repo_imports.py']),
    ('content',   'action-set wording',   [PY, 'tests/test_action_set_wording.py']),
    ('artifacts', 'numeric literals',     [PY, 'tests/test_numeric_literals.py']),
    ('artifacts', 'comparison direction', [PY, 'tests/test_comparison_direction.py']),
    ('artifacts', 'R9 locked wording',    [PY, 'tools/build_r9_claims.py', '--check']),
    ('artifacts', 'paper compiles',       [PY, 'tests/test_compile.py']),
    # R43-4: the generators run their own substitutions; a pattern that no longer matches the
    # delivered text is a FAIL here instead of a silent no-op nobody sees until the next run.
    ('content',   'generators --check',  [PY, 'tests/test_generators_check.py']),
    # R45-6: the paper vs the RECORD. Every other gate compares the paper against data; this one
    # blocks a sentence the protocol has already ruled false-as-written or superseded.
    ('content',   'protocol reconcile',  [PY, 'tests/test_protocol_reconciliation.py']),
    # R63-3: the transport cells must report what the simulation used, not a design value.
    ('content',   'transport products',  [PY, 'tests/test_transport_products.py']),
    ('content',   'canonical quantities', [PY, 'tests/test_canonical_quantities.py']),
    ('content',   'assumptions ledger',   [PY, 'tests/test_assumptions_ledger.py']),
    # R68: the numbers<->CSV report was written by a tool that ALWAYS returned 0 and that nobody
    # re-ran. It sat at "MISS 0" from R57 while a fresh run said "MISS 1" -- a bound literal
    # (`0.007`) that no product held, because it was a bound rounded DOWN. Same family as
    # check_figure_consistency --check: a stale report is a stale claim about the tree, so --check
    # fails on a MISS, on an unlocated table cell, and on the committed report drifting from a
    # fresh build. It is the slowest gate here (~85 s); that is the price of it being real.
    ('content',   'p6 numbers vs CSV',    [PY, 'tools/p6_numbers_vs_csv.py', '--check']),
    # R69-2: deleting a product answered "does anything READ this?" and never "can anything WRITE
    # it?". Two scripts could still rebuild theirs -- verify_c256_dominance.py and action_dist.py --
    # and one routine run would have put a pre-corrigendum product back in results/, where every
    # tool treats a present file as a real one. tests/retired_products.md is now binding in both
    # directions: not evidence, and not re-creatable.
    ('content',   'retired-write sweep',  [PY, 'tests/test_no_retired_writes.py']),
    # V2-R6 A: work package 2 computed held-out accuracy before the selector freeze. Moving it to
    # results/v2/sealed/ and gating the generator behind --held-out-eval were repairs; this is what
    # makes them hold. Same principle as gate 21: judge the CAPABILITY, not the intent.
    ('content',   'sealed held-out',      [PY, 'tests/test_sealed_heldout.py']),
    # V2-R16/R17: shuffle_points() drew from the global unseeded numpy RNG, so two runs of the same
    # frame disagreed (~1.5% of frames by one box, AP by 1e-5..1e-4). Found only because a
    # reconstruction bridge compared two runs bit for bit -- v1 never did. This gate keeps the
    # per-sample RandomState fix from regressing, and enumerates the whole identity set for seed
    # collisions every run.
    ('artifacts', 'eval determinism',     [PY, 'tests/test_eval_determinism.py']),
    # V2-R20 D: the v2 products cannot be reproduced from this repository alone -- files in the
    # sibling OpenCOOD checkout are required. The intra-repo import gate found that and was RIGHT;
    # it was narrowed against this manifest rather than exempted. Pins the upstream base commit and
    # every file's content hash, so "it works on one machine" cannot pass for reproducible again.
    ('artifacts', 'sibling dependency',   [PY, 'tools/build_sibling_dependency_manifest.py',
                                           '--check']),
    # V2-R20 B-1: the identity-alignment verdict -- the quantity whose correct value really IS 100 %
    # (unlike the 73.6 % coordinate-frame diagnostic, which fails downward only). Re-runs the cheap
    # parts live and recomputes the audit's recorded input hashes, so a stale verdict cannot pass.
    ('artifacts', 'alignment audit',      [PY, 'tests/test_alignment_audit.py']),
    # V2-R21 B: patches/opencood/ is the ONLY portable form of the sibling modifications, and it
    # went stale at V2-R16 and survived four rounds with every gate green -- because no gate ever
    # ran the generator (the R63 family). Gate 24 pins the manifest; this pins the patches against
    # the tree they claim to describe, in BOTH directions (patch content and worktree content), so
    # neither can be quietly rewritten to match the other.
    ('artifacts', 'patch freshness',      [PY, 'tests/test_patch_freshness.py']),
    # V2-R22 F / V2-R24 B-1: the cue schema. F-3 is done by DATA FLOW, not by name -- the cues are
    # recomputed from the ego-only path and must match, while an all-CAV control must differ. A
    # rename is exactly what a wrong implementation would also do, so a name check would prove
    # nothing here.
    ('artifacts', 'cue schema',           [PY, 'tests/test_cue_schema.py']),
    # V2-R21 C-5: no ground truth, task metric, oracle label, delivery outcome or future information
    # may reach the ACTIVE cue schema. Held red on purpose from V2-R21 until the §9 amendment
    # removed ego_num_objects; registered now that it is green on its own merits (F-7).
    ('content',   'cue field whitelist',  [PY, 'tests/test_cue_field_whitelist.py']),
    # V2-R24 B-2: the schema freeze. Pins the field list AND its order, a code location per field,
    # the FOV the statistics are defined over, and the WP2 products + checkpoint the schema depends
    # on. ego_detected_box_count IS a detector output, so a schema frozen without pinning those
    # would be frozen against a moving input.
    ('artifacts', 'cue schema freeze',    [PY, 'tools/build_cue_schema_manifest.py', '--check']),
]


# R20 9c: the fingerprint sweep covers the reader-facing docs too. It read main.tex only, so a
# retired number could (and did) survive in README and docs/ with every gate green.
FINGERPRINT_TARGETS = ('paper/main.tex', 'paper/supplementary.tex', 'README.md', 'docs/model_zoo.md',
                       'docs/milestone_summary.md')
# NOT swept, by design: docs/p0_corrigendum.md and docs/canonical_quantities.md exist to record what
# the retired values WERE (old-vs-new tables, "which side flipped"), so a retired number is correct
# content there. Sweeping them would force the record to delete its own evidence.


def block_exit():
    """Retired fingerprints must not reappear in the paper or the reader-facing docs."""
    pats = [l[3:].strip() for l in open(os.path.join(ROOT, 'tests/stale_fingerprints.md'),
                                        encoding='utf-8') if l.startswith('RX ')]
    n = 0
    for rel in FINGERPRINT_TARGETS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        body = open(path, encoding='utf-8').read()
        for p in pats:
            # A retired VALUE is that value, not a prefix of a longer one. Without this, patterns
            # written for main.tex's 3-4 decimal prose fire on generated tables that print 5 --
            # 0.888 matched a per-class F1 of 0.8883, 0.081 matched a payload of 0.08102. This is the
            # same anchoring failure as the 0.248 / 27.5 / 18.4 / 0.895 collisions, fixed once here
            # instead of pattern by pattern.
            for m in re.finditer(p, body):
                tail = body[m.end():m.end() + 1]
                if tail.isdigit():
                    continue
                print('  STALE FINGERPRINT PRESENT in %s: %s' % (rel, p))
                n += 1
                break
    return n


if __name__ == '__main__':
    content_only = '--content-only' in sys.argv
    rc = 0
    for tier, name, cmd in GATES:
        if content_only and tier != 'content':
            print('%-24s not run (--content-only; needs data/p2/ + the OpenCOOD checkout)' % name)
            continue
        if not os.path.exists(os.path.join(ROOT, cmd[1])):
            print('%-24s SKIP (absent: %s)' % (name, cmd[1]))
            continue
        r = subprocess.run(cmd, cwd=ROOT)
        print('%-24s %s' % (name, 'PASS' if r.returncode == 0 else 'FAIL'))
        rc |= r.returncode
    n = block_exit()
    print('%-24s %s' % ('stale-fingerprint exit', 'PASS' if n == 0 else 'FAIL (%d)' % n))
    rc |= (1 if n else 0)
    tier_note = (' (content tier only -- %d artefact-tier gates not run)'
                 % sum(1 for t, _n, _c in GATES if t != 'content')) if content_only else ''
    print('\n%s%s' % ('ALL GATES PASS' if rc == 0 else 'GATE FAILURE', tier_note))
    sys.exit(rc)
