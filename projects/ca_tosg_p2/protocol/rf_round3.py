#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R18 — round 3: the same forest, five more inputs. 23 dimensions against 28.

**The only change is the input.** The forest is back to round 1's settings, read from
`V2_PRIMARY_FREEZE` exactly as round 1 read them, so `max_depth` is None again and depth 8 is not
used. Labels, the original 22-cell grid, the nine scene-level folds, the per-fold tau fit, the
message accounting, the cheaper-payload tie rule and the seed are unchanged.

B-2 is a gate, not a claim: the 23-dimensional arm is re-run here and must reproduce the stored
round-1 per-row product action for action and probability for probability. If it does not, the
generator stops, because then the round would have more than one variable in it.

  C-1  F1, recall, misses, payload and request shares, 23d against 28d, channels apart, the
       high-reliability cells on their own
  C-2  the six-category loss decomposition side by side, held out and in training
  C-3  P(F | F optimal) - P(F | L optimal), training and held out
  C-4  28d - 23d and 28d - channel rule, per scene with bootstrap intervals
  C-5  what the five new cues look like on F-optimal, L-optimal and E-optimal rows -- reported only

    python rf_round3.py [--check] [--jobs N]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
ROUND1_OOF = os.path.join(P2, 'results', 'rf', 'rf_round1_oof.csv')
CONF_CSV = os.path.join(P2, 'results', 'cues', 'ego_conf_cues_validate.csv')
CONF_JSON = os.path.join(HERE, 'ego_conf_cues.json')
ROWS_GZ = os.path.join(P2, 'results', 'rf', 'rf_round3_rows.csv.gz')
OUT_JSON = os.path.join(HERE, 'rf_round3.json')
OUT_MD = os.path.join(HERE, 'rf_round3.md')

sys.path.insert(0, HERE)
from offline_potential import build_table, scene_equal, boot, ACTIONS                  # noqa: E402
from rf_round1 import (hyperparameters, outcome, evaluate, confusion, CUES, CUE_META,  # noqa: E402
                       VOLATILE_FIELDS, strip_volatile, json_diff)
from rf_round2 import (load_frame_outcomes, loss_breakdown, discrimination,            # noqa: E402
                       pooled_train, run_round, cap1, HI_CELLS)
from ego_conf_cues import FIELDS as CONF_FIELDS, SCHEMA                                # noqa: E402

ARMS_23 = 'RF_23d'
ARMS_28 = 'RF_28d'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def cue_frames():
    """The 21 existing cues, and the same table with the five confidence cues joined on."""
    cues = pd.read_csv(CUES)
    base = list(json.load(open(CUE_META))['perception_fields'])
    if not os.path.exists(CONF_CSV):
        raise SystemExit('the confidence cues are absent; run ego_conf_cues.py first')
    conf = pd.read_csv(CONF_CSV)
    missing = [c for c in CONF_FIELDS if c not in conf.columns]
    if missing:
        raise SystemExit(f'confidence cue columns missing: {missing}')
    if set(conf.frame) != set(cues.frame):
        raise SystemExit('the confidence cue frames are not the cue-table frames -- stop')
    merged = cues.merge(conf, on='frame', how='left', validate='one_to_one')
    if merged[CONF_FIELDS].isna().any().any():
        raise SystemExit('a frame has no confidence cue after the join -- stop')
    overlap = [c for c in CONF_FIELDS if c in base]
    if overlap:
        raise SystemExit(f'a confidence field collides with an existing cue name: {overlap}')
    return merged, base, base + CONF_FIELDS


def build(jobs=-1):
    g, n_cw_F, B_F_sym = build_table()
    fo, tp_dev = load_frame_outcomes(g)
    cues, base_fields, all_fields = cue_frames()
    labels = g.a_star.to_numpy().astype(object)
    scenes = g.scene.to_numpy()
    ch = g.channel.to_numpy()

    runs = {}
    for tag, fields in ((ARMS_23, base_fields), (ARMS_28, all_fields)):
        print(f'{tag} ({len(fields) + 2} inputs)', flush=True)
        runs[tag] = run_round(g, cues, fields, labels, jobs, None, tag)

    # B-2: the 23-dimensional arm must BE round 1
    stored = pd.read_csv(ROUND1_OOF)
    r23 = runs[ARMS_23]
    same_pred = bool((stored.pred_joint.to_numpy() == r23['oof_pred']).all())
    same_rule = bool((stored.pred_channel_rule.to_numpy() == r23['rule_pred']).all())
    max_dp = float(np.abs(stored[['p_E', 'p_L', 'p_F']].to_numpy() - r23['oof_proba']).max())
    if not (same_pred and same_rule) or max_dp > 1e-12:
        raise SystemExit(f'the 23-dimensional re-run is not round 1 (actions {same_pred}/{same_rule}, '
                         f'max |dp| {max_dp:g}) -- more than the input has changed')
    gate = {'actions_identical_to_round1': same_pred, 'channel_rule_identical': same_rule,
            'max_abs_probability_difference': max_dp,
            'what_this_proves': 'the 23-dimensional arm below is the round-1 forest, so the only '
                                'difference between the two arms is the five added inputs'}

    # per-row product, both arms, both splits
    frames = []
    for tag in (ARMS_23, ARMS_28):
        r = runs[tag]
        frames.append(pd.DataFrame({
            'arm': tag, 'fold': 'held_out', 'split': 'held_out',
            'sample_id': g.sample_id.to_numpy(), 'scene': scenes, 'snr_db': g.snr_db.to_numpy(),
            'channel': ch, 'a_star': labels, 'pred': r['oof_pred'],
            'p_E': r['oof_proba'][:, 0], 'p_L': r['oof_proba'][:, 1], 'p_F': r['oof_proba'][:, 2]}))
        for b in r['train_blocks']:
            i = b['idx']
            frames.append(pd.DataFrame({
                'arm': tag, 'fold': b['scene_held_out'], 'split': 'training',
                'sample_id': g.sample_id.to_numpy()[i], 'scene': scenes[i],
                'snr_db': g.snr_db.to_numpy()[i], 'channel': ch[i], 'a_star': labels[i],
                'pred': b['pred'], 'p_E': b['proba'][:, 0], 'p_L': b['proba'][:, 1],
                'p_F': b['proba'][:, 2]}))
    rows = pd.concat(frames, ignore_index=True)
    os.makedirs(os.path.dirname(ROWS_GZ), exist_ok=True)
    rows.to_csv(ROWS_GZ, index=False, compression={'method': 'gzip', 'mtime': 0})

    # ---------------- C-1 ----------------
    chosen = {ARMS_23: runs[ARMS_23]['oof_pred'], ARMS_28: runs[ARMS_28]['oof_pred'],
              'channel_rule': runs[ARMS_23]['rule_pred'], 'offline_optimum': labels,
              'fixed_E': np.full(len(g), 'E', object), 'fixed_L': np.full(len(g), 'L', object),
              'fixed_F': np.full(len(g), 'F', object)}
    hi = np.zeros(len(g), bool)
    for c, s in HI_CELLS:
        hi |= ((g.channel == c) & (g.snr_db == s)).to_numpy()
    subsets = [('all 22 cells', np.ones(len(g), bool)), ('AWGN only', ch == 'awgn'),
               ('Rayleigh only', ch == 'rayleigh'), ('high-reliability AWGN cells', hi)]
    arms = [evaluate(g, fo, chosen, m, lab) for lab, m in subsets]

    # ---------------- C-2, C-3 ----------------
    c2, c3 = {}, {}
    for tag in (ARMS_23, ARMS_28):
        r = runs[tag]
        idx, pred, proba, brk = pooled_train(g, labels, scenes, r['train_blocks'])
        oof = loss_breakdown(g, labels, r['oof_pred'], scenes)
        c2[tag] = {'training_pooled': brk, 'held_out': oof,
                   'confusion_held_out': confusion(labels, r['oof_pred'], ch,
                                                   np.ones(len(g), bool)),
                   'confusion_training_pooled': confusion(labels[idx], pred, ch[idx],
                                                          np.ones(len(idx), bool))}
        c3[tag] = {'training_high_reliability': discrimination(proba, labels[idx], hi[idx]),
                   'held_out_high_reliability': discrimination(r['oof_proba'], labels, hi),
                   'held_out_all_cells': discrimination(r['oof_proba'], labels,
                                                        np.ones(len(g), bool))}

    # ---------------- C-4 ----------------
    c4 = {}
    for lab, m in subsets:
        sc = scenes[m]
        out = {}
        for a, b in ((ARMS_28, ARMS_23), (ARMS_28, 'channel_rule')):
            d = outcome(g, fo, chosen[a])[0][m] - outcome(g, fo, chosen[b])[0][m]
            per = [{'scene': str(s), 'diff': float(d[sc == s].mean())} for s in np.unique(sc)]
            out[f'{a} - {b}'] = {'bootstrap': boot(d, sc), 'per_scene': per,
                                 'scenes_negative': [x['scene'] for x in per if x['diff'] < 0]}
        c4[lab] = out

    # ---------------- C-5: the new cues by which action is optimal ----------------
    cm = cues.set_index('frame').loc[g.sample_id.to_numpy()]
    c5 = {}
    for f in CONF_FIELDS:
        v = cm[f].to_numpy(float)
        per = {}
        for a in ACTIONS:
            mk = labels == a
            per[a] = {'rows': int(mk.sum()), 'mean': float(v[mk].mean()),
                      'p10': float(np.percentile(v[mk], 10)),
                      'p50': float(np.percentile(v[mk], 50)),
                      'p90': float(np.percentile(v[mk], 90))}
        hf, hl = hi & (labels == 'F'), hi & (labels == 'L')
        per['high_reliability_F_minus_L_mean'] = (float(v[hf].mean() - v[hl].mean())
                                                 if hf.any() and hl.any() else None)
        c5[f] = per
    c5_note = ('reported only. No threshold is set on any of these and no arm is tuned from them '
               '(D-1). A row is a frame-cell pair, so the same frame appears under different optimal '
               'actions in different cells: these distributions describe rows, not frames')

    return {'schema': 'catosg-p2-rf-round3/1',
            'status': 'DEVELOPMENT VALIDATION ONLY. Nine-fold leave-one-scene-out on validate; no '
                      'held-out-split result and no selection on validate after the folds. test and '
                      'Culver are not opened',
            'the_only_change': f'the input: {len(base_fields)} + 2 = {len(base_fields) + 2} '
                               f'dimensions against {len(all_fields)} + 2 = {len(all_fields) + 2} '
                               f'({SCHEMA}). The forest is round 1 again, max_depth None, read from '
                               'the freeze manifest; depth 8 is not used',
            'B2_gate': gate,
            'hyperparameters': runs[ARMS_23]['hp'],
            'feature_counts': {ARMS_23: len(base_fields) + 2, ARMS_28: len(all_fields) + 2},
            'new_fields': CONF_FIELDS,
            'inputs': {'round1_oof': sha(ROUND1_OOF), 'conf_cues': sha(CONF_CSV),
                       'conf_audit': sha(CONF_JSON), 'cues': sha(CUES)},
            'row_product': {'path': os.path.relpath(ROWS_GZ, ROOT), 'sha256': sha(ROWS_GZ),
                            'rows': int(len(rows)), 'columns': list(rows.columns)},
            'C1_arms': arms, 'C2_loss': c2, 'C3_discrimination': c3, 'C4_differences': c4,
            'C5_new_cue_distributions': c5, 'C5_note': c5_note,
            'folds': {tag: runs[tag]['folds'] for tag in (ARMS_23, ARMS_28)},
            'command': 'python projects/ca_tosg_p2/protocol/rf_round3.py'}


ARM_ORDER = ('offline_optimum', 'channel_rule', ARMS_23, ARMS_28, 'fixed_L', 'fixed_F', 'fixed_E')
CATS = ('should F, chose L', 'should F, chose E', 'should L, chose E', 'should L, chose F',
        'should E, chose L', 'should E, chose F')


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/rf_round3.py -- do not edit by hand -->',
         '# Round 3: five ego confidence cues added (P2-R18)', '',
         f"**{m['status']}.**", '', f"**The only change.** {cap1(m['the_only_change'])}.", '',
         f"**New fields.** {', '.join('`' + f + '`' for f in m['new_fields'])}.", '',
         '## B-2 That nothing but the input moved', '']
    gt = m['B2_gate']
    L += [f"The 23-dimensional arm reproduces the stored round-1 product exactly: actions identical "
          f"({gt['actions_identical_to_round1']}), channel-rule actions identical "
          f"({gt['channel_rule_identical']}), largest probability difference "
          f"{gt['max_abs_probability_difference']:.1e}. {cap1(gt['what_this_proves'])}.", '',
          f"Forest settings, both arms: {m['hyperparameters']}.", '',
          '## C-1 The arms, held out', '']
    for r in m['C1_arms']:
        L += [f"### {r['label']} ({r['rows']:,} rows)", '',
              '| arm | scene-equal F1 | recall | misses / frame | QAM symbols | request E | L | F |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
        for arm in ARM_ORDER:
            v = r['arms'].get(arm)
            if not v:
                continue
            s = v['request_share']
            L.append(f"| `{arm}` | {v['f1']:.5f} | {v['recall']:.5f} | {v['misses_per_frame']:.3f} | "
                     f"{v['qam_symbols']:,.0f} | {s['E'] * 100:.1f} % | {s['L'] * 100:.1f} % | "
                     f"{s['F'] * 100:.1f} % |")
        L.append('')
    L += ['## C-2 The loss, six categories, both arms', '',
          '| arm | split | F label recall | agreement | total loss | '
          + ' | '.join(CATS) + ' |',
          '|---|---|---:|---:|---:|' + '---:|' * len(CATS)]
    for tag, v in m['C2_loss'].items():
        for key, title in (('training_pooled', 'training'), ('held_out', 'held out')):
            b = v[key]
            cells = [f"{b['categories'].get(c, {}).get('scene_equal_loss', 0.0):+.5f}" for c in CATS]
            L.append(f"| `{tag}` | {title} | "
                     + (f"{b['F_label_recall'] * 100:.1f} %" if b['F_label_recall'] is not None else '—')
                     + f" | {b['agreement_share'] * 100:.1f} % | "
                     f"{b['scene_equal_total_loss']:+.5f} | " + ' | '.join(cells) + ' |')
    L += ['', '### Confusion against a\\*, held out', '']
    for tag, v in m['C2_loss'].items():
        c = v['confusion_held_out']['all']
        L += [f"**`{tag}`** — accuracy {c['accuracy'] * 100:.1f} %", '',
              '| true \\ predicted | E | L | F | recall |', '|---|---:|---:|---:|---:|']
        for a in ACTIONS:
            row = c['matrix_true_by_predicted'][a]
            rec = c['per_action'][a]['recall']
            L.append(f"| **{a}** | {row['E']:,} | {row['L']:,} | {row['F']:,} | "
                     + (f"{rec * 100:.1f} %" if rec is not None else '—') + ' |')
        L.append('')
    L += ['## C-3 Does P(F) separate F from L', '',
          '| arm | split / subset | P(F) where F optimal | where L optimal | difference |',
          '|---|---|---:|---:|---:|']
    for tag, v in m['C3_discrimination'].items():
        for key, title in (('training_high_reliability', 'training, high-reliability cells'),
                           ('held_out_high_reliability', 'held out, high-reliability cells'),
                           ('held_out_all_cells', 'held out, all cells')):
            d = v.get(key)
            if not d:
                continue
            L.append(f"| `{tag}` | {title} | {d['mean_p_F_where_F_optimal']:.4f} | "
                     f"{d['mean_p_F_where_L_optimal']:.4f} | {d['difference']:+.4f} |")
    L += ['', '## C-4 Differences, per scene and bootstrapped', '']
    for lab, v in m['C4_differences'].items():
        L += [f"### {lab}", '', '| difference | scene-equal mean | bootstrap 95 % | scenes negative |',
              '|---|---:|---|---|']
        for k, d in v.items():
            b = d['bootstrap']
            L.append(f"| {k} | {b['mean']:+.5f} | [{b['lcb95']:+.5f}, {b['ucb95']:+.5f}] | "
                     f"{len(d['scenes_negative'])}/9 |")
        L.append('')
    L += ['## C-5 What the new cues look like where each action is optimal', '',
          f"{cap1(m['C5_note'])}.", '',
          '| cue | a\\* | rows | mean | p10 | p50 | p90 | F − L mean, high-reliability cells |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for f, per in m['C5_new_cue_distributions'].items():
        gap = per.get('high_reliability_F_minus_L_mean')
        for i, a in enumerate(ACTIONS):
            v = per[a]
            L.append(f"| `{f}` | {a} | {v['rows']:,} | {v['mean']:.4f} | {v['p10']:.4f} | "
                     f"{v['p50']:.4f} | {v['p90']:.4f} | "
                     + ((f"{gap:+.4f}" if gap is not None else '—') if i == 0 else '') + ' |')
    pr = m['row_product']
    L += ['', '## Products', '',
          f"`{pr['path']}` — {pr['rows']:,} rows, both arms, training and held-out, with the action "
          'taken and the three class probabilities. Its sha256 is recorded and `--check` verifies it.',
          '', '## Inputs', '', '| file | sha256 |', '|---|---|']
    for k, v in m['inputs'].items():
        L.append(f"| {k} | `{v[:16]}…` |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--rerender', action='store_true')
    ap.add_argument('--jobs', type=int, default=-1)
    a = ap.parse_args()

    if a.rerender:
        m = json.load(open(OUT_JSON))
        open(OUT_MD, 'w').write(markdown(m))
        print('rf round3: markdown rewritten from the stored record (no retraining)')
        return 0

    if a.check and not a.full:
        if not os.path.exists(OUT_JSON):
            print('rf round3: FAIL -- no stored record'); return 1
        m = json.load(open(OUT_JSON))
        md_ok = os.path.exists(OUT_MD) and open(OUT_MD).read() == markdown(m)
        have = os.path.exists(ROWS_GZ)
        prod_ok = have and sha(ROWS_GZ) == m['row_product']['sha256']
        print('rf round3:', 'document matches the record' if md_ok else 'FAIL -- document differs')
        print('  per-row product:', 'hash matches the record' if prod_ok
              else ('FAIL -- missing' if not have else 'FAIL -- hash differs'))
        print('  (the record itself is not re-derived at this level; use --check --full)')
        return 0 if (md_ok and prod_ok) else 1

    m = build(a.jobs)
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        stored = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
        diffs = json_diff(strip_volatile(stored), strip_volatile(m))
        md_ok = os.path.exists(OUT_MD) and open(OUT_MD).read() == md
        print(f'rf round3: comparison excludes {VOLATILE_FIELDS} -- wall-clock')
        if diffs:
            print(f'  FAIL -- differs at {len(diffs)} path(s):')
            for d in diffs[:20]:
                print('   ', d)
        if not md_ok:
            print('  FAIL -- the document is not what the generator writes')
        if not diffs and md_ok:
            print('  reproduced end to end (everything but the timing fields)')
            return 0
        return 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
