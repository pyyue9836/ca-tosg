#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0-5b: regenerate the retired-convention products the paper actually depends on.

Of the 59 CSVs still carrying the retired full-collaborator convention after the promotion, **10**
are cited by a ledger claim or drawn by a figure. The rest are retired v3-engine outputs the paper
no longer cites, and regenerating them would resurrect an engine three change-log entries have
retired -- so they are left alone, and this file records that decision rather than quietly skipping
them.

Each generator runs behind an **allowlist guard**: every deployed product is hashed before and
after, and any change outside the files that generator is authorised to write aborts the run. The
whole-tree guard used for the arm stages cannot be used here, because these generators are *supposed*
to rewrite their own deployed outputs.

    python tools/regenerate_p0_products.py --list
    python tools/regenerate_p0_products.py --selfcheck-gt
    python tools/regenerate_p0_products.py --run
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

# (label, command, files this generator is allowed to write)
JOBS = [
    ('fixed_references', [PY, 'projects/ca_tosg/evaluation/fixed_references.py'],
     ['results/main/fixed_references.csv', 'results/provenance/PROVENANCE_fixed_references.txt']),
    ('true_e2e_ap', [PY, 'tools/evaluate_ap.py'],
     ['results/main/true_e2e_ap.csv', 'results/provenance/PROVENANCE_ap.txt',
      'results/provenance/PROVENANCE_e2e_ap.txt']),
    # tools/evaluate_ap.py runs end_to_end_ap.main() only; the per-SNR table is a separate script
    ('true_e2e_ap_by_snr', [PY, 'projects/ca_tosg/evaluation/end_to_end_ap_snr.py'],
     ['results/main/true_e2e_ap_by_snr.csv', 'results/provenance/PROVENANCE_ap_snr.txt']),
    ('frozen_curves', [PY, 'projects/ca_tosg/evaluation/frozen_curves.py'],
     ['results/main/frozen_curves.csv', 'results/provenance/PROVENANCE_frozen_curves.txt']),
    ('difficulty_frozen', [PY, 'projects/ca_tosg/evaluation/difficulty_frozen.py'],
     ['results/sensitivity/difficulty_frozen.csv',
      'results/provenance/PROVENANCE_difficulty_frozen.txt']),
    ('canonical_rescore', [PY, 'projects/ca_tosg/evaluation/canonical_rescore.py'],
     ['results/sensitivity/canonical_rescore.csv', 'results/sensitivity/canonical_f1_columns.csv',
      'results/provenance/PROVENANCE_canonical_rescore.txt']),
    ('collaborator_scale', [PY, 'projects/ca_tosg/evaluation/collaborator_scale.py'],
     ['results/sensitivity/collaborator_scale.csv', 'results/provenance/PROVENANCE_p4c.txt',
      'results/manifests/P4C_MANIFEST.json']),
    ('baseline_sanity', [PY, 'tools/run_sensitivity.py'],
     None),          # writes a whole family; guarded by prefix instead (see ALLOW_PREFIX)
    # JOBS omission caught in R18-5: c256_dominance_verify and the collaboration-harm family were
    # both on the work list and neither had a job, so L177 and L749 kept retired-convention numbers.
    ('c256_dominance', [PY, 'projects/ca_tosg/evaluation/verifiers/verify_c256_dominance.py'],
     ['results/sensitivity/c256_dominance_verify.csv',
      'results/provenance/PROVENANCE_c256_dominance.txt']),
    ('collab_harm', [PY, 'projects/ca_tosg/evaluation/collab_harm.py'],
     ['results/main/step4_collaboration_harm.csv',
      'results/provenance/PROVENANCE_collab_harm.txt']),
    ('harm_stratum', [PY, 'projects/ca_tosg/evaluation/verifiers/verify_harm_stratum_structural.py'],
     ['results/sensitivity/harm_stratum_structural.csv',
      'results/provenance/PROVENANCE_harm_stratum.txt']),
    ('ego_only_acceptance', [PY, 'projects/ca_tosg/datasets/run_ego_only.py'],
     ['results/main/ego_only_acceptance.csv',
      'results/provenance/PROVENANCE_ego_only.txt']),
]
ALLOW_PREFIX = {'baseline_sanity': ('results/sensitivity/', 'results/provenance/')}

# CONVENTION-INDEPENDENT, deliberately NOT regenerated. The collaborator correction changes which
# boxes a frame receives, not the ground truth: the canonical union GT is the full-set one for every
# arm (P4-C ruling 1) and is byte-identical before and after. Regenerating these would also mean
# repairing gt_audit.py, which has been unrunnable since the restructure (523f062) and does not even
# write gt_object_stats.csv despite results/README naming it as the generator -- a stale index entry.
UNAFFECTED = {'results/sensitivity/gt_audit.csv': 'GT statistics; GT is canonical and unchanged',
              'results/sensitivity/gt_object_stats.csv': 'GT object counts; unchanged by P0'}

DEPLOYED = ('results/main', 'results/manifests', 'results/provenance', 'results/sensitivity',
            'results/baselines', 'results/channel', 'results/latency', 'data/p2')


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def snapshot():
    out = {}
    for d in DEPLOYED:
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, d)):
            for f in files:
                full = os.path.join(dirpath, f)
                out[os.path.relpath(full, ROOT)] = md5(full)
    return out


def run_job(label, cmd, allowed):
    before = snapshot()
    print(f'\n=== {label}: {" ".join(cmd[1:])} ===')
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [l for l in r.stdout.splitlines() if l.strip()][-3:]
    for l in tail:
        print('   ', l[:150])
    if r.returncode != 0:
        print('    STDERR:', r.stderr.strip().splitlines()[-3:] if r.stderr else '(none)')
    after = snapshot()
    touched = sorted([k for k in after if k not in before or before.get(k) != after[k]])
    prefixes = ALLOW_PREFIX.get(label)
    unauthorised = []
    for k in touched:
        if allowed is not None and k in allowed:
            continue
        if prefixes and k.startswith(prefixes):
            continue
        unauthorised.append(k)
    print(f'    touched {len(touched)} deployed file(s); '
          f'{len(unauthorised)} outside this generator\'s allowlist')
    for k in unauthorised:
        print('      UNAUTHORISED WRITE:', k)
    if unauthorised:
        raise SystemExit(f'{label}: wrote outside its allowlist -- aborting the batch')
    return r.returncode, touched


def selfcheck_gt():
    """The one product whose retired version MUST still reproduce: GT statistics.

    GT is the canonical full-set union and is unchanged by the collaborator correction, so
    `gt_object_stats.csv` must come out bit-identical to the committed retired version. If it does
    not, the shim is feeding something other than the canonical GT and nothing else in this batch
    can be trusted.
    """
    p = 'results/sensitivity/gt_object_stats.csv'
    before = md5(os.path.join(ROOT, p))
    r = subprocess.run([PY, 'projects/ca_tosg/evaluation/gt_audit.py'], cwd=ROOT,
                       capture_output=True, text=True)
    after = md5(os.path.join(ROOT, p))
    if r.returncode != 0:
        print(f'  {p}: generator FAILED (exit {r.returncode}) -- '
              f'{(r.stderr or "").strip().splitlines()[-1][:120] if r.stderr else "no stderr"}')
        return 1
    ok = before == after
    verdict = ('BIT-IDENTICAL (GT ruler unchanged)' if ok else
               '**DIFFERS** -- the shim is not feeding the canonical GT')
    print(f'  {p}: {before[:12]} -> {after[:12]}  {verdict}')
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--list', action='store_true')
    g.add_argument('--selfcheck-gt', action='store_true')
    g.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if a.list:
        for label, cmd, allowed in JOBS:
            print(f'{label:20s} {" ".join(cmd[1:]):55s} '
                  f'{len(allowed) if allowed else "prefix-guarded"} output(s)')
        return 0
    if a.selfcheck_gt:
        return selfcheck_gt()
    rc = 0
    for label, cmd, allowed in JOBS:
        code, _t = run_job(label, cmd, allowed)
        rc |= code
    print('\nregeneration ' + ('COMPLETE' if rc == 0 else 'had failures -- see above'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
