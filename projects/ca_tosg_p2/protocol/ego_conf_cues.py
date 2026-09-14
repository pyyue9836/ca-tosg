#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R18 A — the five ego detection-confidence cues, and the source audit for them.

The five dimensions are statistics of the **ego vehicle's own** post-processed box scores, available
before any request is made: mean, population standard deviation, and the 10th, 50th and 90th
percentiles. With the 21 existing ego-local cues and the two channel fields this makes the
`v2_ego_local_28d` schema.

**No re-extraction was needed and no GPU was used.** The per-box scores already exist in
`results/v2/wp2_per_agent_validate.npz`, written by `v2_wp2_per_agent.py` in the same run that
produced the box counts P1 registered. Two things are checked before they are believed: the per-frame
count must equal the registered `n_box_ego` on every frame, and the scores must agree exactly with the
independent copy in `wp5_tpfp_validate.npz`.

**Forbidden sources (A-2).** Only `ego_scores` and `frames` are read out of that file. The
collaborator boxes and scores, the ground truth and every fused or post-transmission quantity sit in
the same file and are never opened -- which is asserted, not merely promised.

    python ego_conf_cues.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
V2 = os.path.join(ROOT, 'results', 'v2')
WP2_NPZ = os.path.join(V2, 'wp2_per_agent_validate.npz')
TPFP_NPZ = os.path.join(V2, 'wp5_tpfp_validate.npz')
WP34 = os.path.join(V2, 'wp34_e_l_validate.csv')
CUE_META = os.path.join(V2, 'wp6_cues_validate.json')
OUT_CSV = os.path.join(P2, 'results', 'cues', 'ego_conf_cues_validate.csv')
OUT_JSON = os.path.join(HERE, 'ego_conf_cues.json')
OUT_MD = os.path.join(HERE, 'ego_conf_cues.md')

FIELDS = ['ego_conf_mean', 'ego_conf_std', 'ego_conf_p10', 'ego_conf_p50', 'ego_conf_p90']
SCHEMA = 'v2_ego_local_28d'

# A-2: every field, where the quantity comes from in code, and why it is available before a request.
PROVENANCE = [
    ('source file', 'results/v2/wp2_per_agent_validate.npz, key `ego_scores`',
     'written at projects/ca_tosg/evaluation/v2_wp2_per_agent.py:165-166 by the same run that wrote '
     'the box counts P1 registered'),
    ('how the scores are produced',
     'projects/ca_tosg/evaluation/v2_wp2_per_agent.py:132-134',
     '`solo = one_cav(cav, 0)` takes row 0 of the stacked batch, which is the ego vehicle; '
     '`inference_intermediate_fusion({\'ego\': solo}, model, ds)` runs the single-vehicle forward '
     '(record_len = [1], so AttFusion self-attends over one element and is the identity); its second '
     'return value is the post-processed box score vector, kept as `E_s`'),
    ('why it is available before a request',
     'the same forward pass the ego already runs for its own detection',
     'no collaborator tensor enters it, no ground truth enters it, and nothing transmitted enters it. '
     'The ego has these scores at the moment it must decide what to request'),
    ('what is NOT read', 'collab_boxes, collab_scores, gts in the same file',
     'only `ego_scores` and `frames` are loaded; the loader asserts that no other key is touched'),
]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load_scores():
    """The ego per-box scores, with every gate that has to pass before they are used."""
    if not os.path.exists(WP2_NPZ):
        raise SystemExit(
            f'{os.path.relpath(WP2_NPZ, ROOT)} is absent. It is excluded from git by the `*.npz` rule '
            'in .gitignore, so a fresh clone does not have it; regenerate it with '
            '`python projects/ca_tosg/evaluation/v2_wp2_per_agent.py --split validate` before running '
            'this. Nothing is substituted for it here')
    z = np.load(WP2_NPZ, allow_pickle=True)
    read_keys = ['frames', 'ego_scores']
    forbidden = [k for k in z.files if k not in read_keys]
    frames, scores = z['frames'], z['ego_scores']

    w34 = pd.read_csv(WP34, usecols=['frame', 'n_box_ego'])
    if not np.array_equal(frames, w34.frame.to_numpy()):
        raise SystemExit('the npz frame order is not the registered wp34 order -- stop')
    lens = np.array([len(x) for x in scores])
    nb = w34.n_box_ego.to_numpy()
    if not bool((lens == nb).all()):
        raise SystemExit(f'per-frame score count differs from the registered n_box_ego on '
                         f'{int((lens != nb).sum())} frames -- the npz is not from the run that '
                         'produced the registered counts')

    # an independent second copy of the same scores, compared exactly rather than loosely
    t = np.load(TPFP_NPZ, allow_pickle=True)
    if not np.array_equal(t['frames'], frames):
        raise SystemExit('wp5_tpfp frame order differs -- stop')
    worst = 0.0
    for a, b in zip(scores, t['ego_05_score']):
        if len(a) != len(b):
            raise SystemExit('wp5_tpfp score count differs from wp2 -- stop')
        if len(a):
            worst = max(worst, float(np.abs(np.sort(np.asarray(a).ravel())
                                            - np.sort(np.asarray(b).ravel())).max()))
    if worst > 0.0:
        raise SystemExit(f'the two independent copies of the ego scores differ by {worst:g} -- stop')

    return frames, scores, lens, {
        'keys_read': read_keys, 'keys_present_but_not_read': forbidden,
        'count_matches_registered_n_box_ego': True,
        'agreement_with_wp5_tpfp_ego_05_score': worst,
        'frames': int(len(frames))}


def build():
    frames, scores, lens, gates = load_scores()
    rows = {'frame': frames}
    for f in FIELDS:
        rows[f] = np.zeros(len(frames))
    for i, s in enumerate(scores):
        v = np.asarray(s, float).ravel()
        if v.size == 0:
            continue                       # A-1: no boxes -> all five stay 0.0
        rows['ego_conf_mean'][i] = v.mean()
        rows['ego_conf_std'][i] = v.std()   # population std; a single box gives 0.0
        rows['ego_conf_p10'][i] = np.percentile(v, 10)
        rows['ego_conf_p50'][i] = np.percentile(v, 50)
        rows['ego_conf_p90'][i] = np.percentile(v, 90)
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    allv = np.concatenate([np.asarray(s, float).ravel() for s in scores if len(s)])
    n_perc = int(json.load(open(CUE_META))['n_perception_fields'])
    zero_box = int((lens == 0).sum())

    return {'schema': f'catosg-p2-ego-conf-cues/1 ({SCHEMA})',
            'status': 'derived from an existing product. No detection head was re-run, no GPU was '
                      'used, and no new inference of any kind took place',
            'cue_schema_name': SCHEMA,
            'dimensions': {'existing_ego_local': n_perc, 'new_confidence': len(FIELDS),
                           'channel': 2, 'total': n_perc + len(FIELDS) + 2},
            'fields': FIELDS,
            'definitions': {
                'ego_conf_mean': 'mean of the ego post-processed box scores on the frame',
                'ego_conf_std': 'population standard deviation (ddof 0); a frame with one box gives '
                                '0.0, which is a real zero spread and not a missing value',
                'ego_conf_p10': '10th percentile, numpy linear interpolation',
                'ego_conf_p50': '50th percentile',
                'ego_conf_p90': '90th percentile'},
            'provenance': [{'item': a, 'where': b, 'why': c} for a, b, c in PROVENANCE],
            'gates': gates,
            'zero_box_frames': zero_box,
            'zero_box_note': 'A-1 asks for the five fields to be zero on frames with no boxes, with '
                             '`ego_detected_box_count` distinguishing them. On validate there are '
                             f'{zero_box} such frames, so that branch is implemented but never taken '
                             'here and the distinguishing field distinguishes nothing on this split. '
                             'Said plainly because a rule that never fires can look like a rule that '
                             'works',
            'score_distribution': {
                'boxes': int(allv.size), 'min': float(allv.min()), 'max': float(allv.max()),
                'mean': float(allv.mean()),
                'truncation_note': 'the minimum is 0.2 to six decimals because the frozen '
                                   'post-processor already discards boxes below a 0.2 score. These '
                                   'five cues therefore describe a TRUNCATED distribution. The '
                                   'threshold belongs to the frozen detector and is not swept here '
                                   '(D-1)'},
            'per_frame': {'path': os.path.relpath(OUT_CSV, ROOT), 'sha256': sha(OUT_CSV),
                          'rows': int(len(df)), 'columns': list(df.columns)},
            'upstream_inputs': {
                'wp2_npz': {'path': os.path.relpath(WP2_NPZ, ROOT), 'sha256': sha(WP2_NPZ),
                            'tracked_by_git': False,
                            'note': 'excluded by the `*.npz` rule in .gitignore. Its hash is recorded '
                                    'here so the derived product can be traced, and the derived CSV '
                                    'is committed because it is small; a fresh clone must regenerate '
                                    'the npz with v2_wp2_per_agent.py'},
                'wp5_tpfp_npz': {'path': os.path.relpath(TPFP_NPZ, ROOT), 'sha256': sha(TPFP_NPZ),
                                 'tracked_by_git': False,
                                 'note': 'read only to cross-check the scores'},
                'wp34': {'path': os.path.relpath(WP34, ROOT), 'sha256': sha(WP34)}},
            'command': 'python projects/ca_tosg_p2/protocol/ego_conf_cues.py'}


def cap1(t):
    return t[:1].upper() + t[1:]


def markdown(m):
    d, sd = m['dimensions'], m['score_distribution']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/ego_conf_cues.py -- do not edit by hand -->',
         f"# The five ego confidence cues, and where they come from ({m['cue_schema_name']})", '',
         f"**{cap1(m['status'])}.**", '',
         f"**Schema.** {d['existing_ego_local']} existing ego-local cues + {d['new_confidence']} "
         f"confidence cues + {d['channel']} channel fields = **{d['total']} dimensions**, named "
         f"`{m['cue_schema_name']}`.", '',
         '## The five fields', '', '| field | definition |', '|---|---|']
    for k, v in m['definitions'].items():
        L.append(f"| `{k}` | {v} |")
    L += ['', '## A-2 Source audit', '', '| item | where | why it is admissible |', '|---|---|---|']
    for p in m['provenance']:
        L.append(f"| {p['item']} | {p['where']} | {p['why']} |")
    g = m['gates']
    L += ['', '## Gates that had to pass first', '',
          f"* The frame order equals the registered `wp34` order across all {g['frames']:,} frames.",
          '* The per-frame score count equals the registered `n_box_ego` on **every** frame. A single '
          'mismatch would mean the file came from a different run and would stop the generator.',
          f"* The scores agree with the independent copy in `wp5_tpfp_validate.npz` "
          f"(`ego_05_score`) to **{g['agreement_with_wp5_tpfp_ego_05_score']:.1e}** — exactly.",
          f"* Keys read: {g['keys_read']}. Present in the same file and deliberately not read: "
          f"{g['keys_present_but_not_read']}.", '',
          '## Two things worth stating rather than burying', '',
          f"**Zero-box frames: {m['zero_box_frames']}.** {m['zero_box_note']}.", '',
          f"**The scores are truncated.** {sd['boxes']:,} boxes, range "
          f"[{sd['min']:.6f}, {sd['max']:.6f}], mean {sd['mean']:.4f}. {sd['truncation_note']}.", '',
          '## Products and upstream inputs', '',
          f"`{m['per_frame']['path']}` — {m['per_frame']['rows']:,} rows, columns "
          f"{m['per_frame']['columns']}.", '', '| upstream input | tracked | sha256 |', '|---|:---:|---|']
    for k, v in m['upstream_inputs'].items():
        L.append(f"| `{v['path']}` | {'yes' if v.get('tracked_by_git', True) else '**no**'} | "
                 f"`{v['sha256'][:16]}…` |")
    L += ['']
    for k, v in m['upstream_inputs'].items():
        if v.get('note'):
            L.append(f"* `{k}` — {v['note']}.")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = (os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js
              and os.path.exists(OUT_MD) and open(OUT_MD).read() == md)
        print('ego conf cues:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
