#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R16 C — why the first forest declines F. Diagnosis only: nothing is tuned, nothing is refitted.

It reads the per-row out-of-fold product written by `rf_round1.py` and the fold record beside it. No
model is trained here, no hyperparameter is touched, no label rule is changed, and the configuration
under examination is exactly the one that produced the negative result.

  C-1  fit versus generalise: the forest's F share on the scenes it was fitted on, against its share
       out of fold, against the offline reference
  C-2  where the F1 loss comes from, by error type, with row counts and per-row size so that "happens
       often" is separated from "costs a lot each time"
  C-3  what the forest believed: the distribution of P(F), whether F was ranked second or dismissed
  C-4  the same F-selection rate binned by the margin |Q_F - Q_L|, which tests directly whether the
       classifier is blind to how much the choice is worth
  C-5  the same four readings per cell, with AWGN 10-20 dB taken one cell at a time

    python rf_diagnostics.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
OOF_CSV = os.path.join(P2, 'results', 'rf', 'rf_round1_oof.csv')
ROUND1 = os.path.join(HERE, 'rf_round1.json')
OUT_JSON = os.path.join(HERE, 'rf_diagnostics.json')
OUT_MD = os.path.join(HERE, 'rf_diagnostics.md')

sys.path.insert(0, HERE)
from offline_potential import scene_equal, ACTIONS, TOL                       # noqa: E402

MARGIN_EDGES = [0.0, TOL, 0.005, 0.02, 0.05, 0.10, np.inf]
MARGIN_LABELS = ['tie (<= TOL)', '(TOL, 0.005]', '(0.005, 0.02]', '(0.02, 0.05]',
                 '(0.05, 0.10]', '> 0.10']
Q_HI_CELLS = [('awgn', s) for s in (10, 12, 14, 16, 18, 20)]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load():
    d = pd.read_csv(OOF_CSV)
    r1 = json.load(open(ROUND1))
    if sha(OOF_CSV) != r1['oof_product']['sha256']:
        raise SystemExit('the per-row product does not match the hash rf_round1.json recorded -- '
                         'diagnosing a file that is not the one the result came from')
    q = d[['Q_E', 'Q_L', 'Q_F']].to_numpy()
    d['Q_star'] = np.choose([ACTIONS.index(a) for a in d.a_star], q.T)
    d['Q_rf'] = np.choose([ACTIONS.index(a) for a in d.pred_joint], q.T)
    d['loss'] = d.Q_star - d.Q_rf
    # a* is the CHEAPEST action within TOL of the maximum, so a forest that picks a different tied
    # action can score up to TOL higher. That is the tie rule working as defined, not a broken label.
    # This is the same trap as offline_potential's tie-slack guard and it caught me twice: a guard has
    # to be written against the rule it is guarding, not against floating-point noise.
    min_loss = float(d.loss.min())
    if min_loss < -TOL - 1e-12:
        raise SystemExit(f'the forest beats the labelled optimum by {-min_loss:g}, beyond the tie '
                         f'slack {TOL:g} -- the label is not an argmax')
    tie = {'min_loss': min_loss, 'rows_below_zero': int((d.loss < 0).sum()),
           'explanation': 'any negative loss is at most TOL and comes from the cheaper-payload tie '
                          'rule: the forest took the dearer of two actions that score within TOL of '
                          'each other. It is reported rather than clipped'}
    d['margin_FL'] = (d.Q_F - d.Q_L).abs()
    d['margin_bin'] = pd.cut(d.margin_FL, bins=MARGIN_EDGES, labels=MARGIN_LABELS,
                             include_lowest=True, right=True)
    return d, r1, tie


# ------------------------------------------------------------------ C-1 .. C-4
def c1_fit_vs_generalise(r1, d):
    sc = d.scene.to_numpy()
    rows = [{'held_out_scene': f['held_out_scene'],
             'rf_F_share_training_scenes': f['F_share_in_training_scenes'],
             'reference_F_share_training_scenes': f['reference_F_share_in_training_scenes'],
             'rf_F_share_held_out': f['F_share_held_out'],
             'reference_F_share_held_out': f['reference_F_share_held_out']} for f in r1['folds']]
    tr = float(np.mean([x['rf_F_share_training_scenes'] for x in rows]))
    te = float(np.mean([x['rf_F_share_held_out'] for x in rows]))
    ref = scene_equal((d.a_star.to_numpy() == 'F').astype(float), sc)
    verdict = ('underfitting the action: the forest already declines F on the very scenes it was '
               'fitted on, so the gap is not a generalisation gap'
               if tr < 0.5 * ref else
               'a generalisation gap: the forest requests F in training and not out of fold'
               if te < 0.5 * tr else
               'neither pattern is clean: the training and held-out shares are close to each other '
               'and to the reference')
    return {'per_fold': rows, 'mean_rf_F_share_training': tr, 'mean_rf_F_share_held_out': te,
            'reference_F_share': ref, 'reading': verdict,
            'note': 'the training-scene share is an in-sample number and is reported only to '
                    'separate fitting from generalisation. It is never a result'}


def c2_loss_sources(d, mask=None):
    t = d if mask is None else d[mask]
    if not len(t):
        return None
    sc = t.scene.to_numpy()
    loss = t.loss.to_numpy()
    total = scene_equal(loss, sc)
    cats = {}
    for star in ACTIONS:
        for pred in ACTIONS:
            if star == pred:
                continue
            m = ((t.a_star == star) & (t.pred_joint == pred)).to_numpy()
            if not m.any():
                continue
            cats[f'should {star}, chose {pred}'] = {
                'rows': int(m.sum()), 'row_share': float(m.mean()),
                'scene_equal_loss': scene_equal(loss * m, sc),
                'share_of_total_loss': float(scene_equal(loss * m, sc) / total) if total > 0 else 0.0,
                'mean_loss_per_row': float(loss[m].mean())}
    agree = (t.a_star == t.pred_joint).to_numpy()
    return {'scene_equal_total_loss': total, 'rows': int(len(t)),
            'agreement_rows': int(agree.sum()), 'agreement_row_share': float(agree.mean()),
            'categories': dict(sorted(cats.items(), key=lambda kv: -kv[1]['scene_equal_loss'])),
            'identity_note': 'the category losses sum to the total by construction, so the ranking '
                             'is a decomposition and not a set of separate estimates'}


def c3_beliefs(d, mask=None):
    t = d if mask is None else d[mask]
    P = t[['p_E', 'p_L', 'p_F']].to_numpy()
    out = {}
    for star in ('F', 'L', 'E'):
        m = (t.a_star == star).to_numpy()
        if not m.any():
            out[star] = None
            continue
        pf = P[m, 2]
        rank = (P[m] > pf[:, None]).sum(axis=1) + 1          # 1 = highest probability
        out[star] = {'rows': int(m.sum()),
                     'p_F_quantiles': {k: float(np.percentile(pf, q)) for k, q in
                                       (('p05', 5), ('p25', 25), ('p50', 50), ('p75', 75),
                                        ('p95', 95))},
                     'p_F_mean': float(pf.mean()),
                     'share_F_ranked_first': float((rank == 1).mean()),
                     'share_F_ranked_second': float((rank == 2).mean()),
                     'share_F_ranked_third': float((rank == 3).mean()),
                     'share_p_F_below_0.05': float((pf < 0.05).mean()),
                     'share_p_F_above_0.25': float((pf > 0.25).mean())}
    f, l = out.get('F'), out.get('L')
    if f and l:
        # The rank histogram alone says nothing about whether P(F) is informative: "F ranked second"
        # can happen on every row while P(F) is a constant. What matters is whether P(F) is higher
        # where F is actually optimal, so that is what decides the reading.
        disc = f['p_F_mean'] - l['p_F_mean']
        out['p_F_discrimination'] = {
            'mean_p_F_where_F_optimal': f['p_F_mean'], 'mean_p_F_where_L_optimal': l['p_F_mean'],
            'difference': disc,
            'definition': 'mean P(F) on rows where F is optimal minus mean P(F) on rows where L is. '
                          'Positive means the probability carries signal about F; zero or negative '
                          'means it does not, whatever the rank histogram looks like'}
        if disc <= 0:
            out['reading'] = (f'P(F) does not separate the two cases at all: it averages '
                              f'{f["p_F_mean"]:.4f} where F is optimal and {l["p_F_mean"]:.4f} where L '
                              'is, so it is flat or slightly inverted. The shortfall is not a '
                              'threshold that could be moved -- the probability carries no usable '
                              'signal about F on these rows')
        elif disc < 0.05:
            out['reading'] = (f'P(F) is only {disc:.4f} higher where F is optimal ({f["p_F_mean"]:.4f} '
                              f'against {l["p_F_mean"]:.4f}), which is barely any separation. Moving a '
                              'decision threshold would trade F recall against F precision almost one '
                              'for one')
        else:
            out['reading'] = (f'P(F) is {disc:.4f} higher where F is optimal ({f["p_F_mean"]:.4f} '
                              f'against {l["p_F_mean"]:.4f}), so the ordering does carry signal and '
                              'the argmax is what discards it')
    return out


def c4_margin(d, mask=None):
    t = d if mask is None else d[mask]
    rows = []
    for lab in MARGIN_LABELS:
        m = (t.margin_bin == lab).to_numpy()
        if not m.any():
            continue
        sub = t[m]
        star_F = (sub.a_star == 'F').to_numpy()
        rows.append({'bin': lab, 'rows': int(m.sum()),
                     'reference_F_share': float(star_F.mean()),
                     'rf_F_share': float((sub.pred_joint == 'F').mean()),
                     'rf_F_share_where_F_is_optimal': (float((sub.pred_joint[star_F] == 'F').mean())
                                                       if star_F.any() else None),
                     'mean_p_F_where_F_is_optimal': (float(sub.p_F.to_numpy()[star_F].mean())
                                                     if star_F.any() else None),
                     'mean_margin': float(sub.margin_FL.mean())})
    ok = [r for r in rows if r['rf_F_share_where_F_is_optimal'] is not None]
    trend = None
    if len(ok) >= 2:
        lo, hi = ok[0], ok[-1]
        v0, vN = lo['rf_F_share_where_F_is_optimal'], hi['rf_F_share_where_F_is_optimal']
        ref = hi['reference_F_share']
        direction = (f'the F-selection rate does rise with the margin, from {v0 * 100:.1f} % in the '
                     f'{lo["bin"]} bin to {vN * 100:.1f} % in the {hi["bin"]} bin, so the forest is '
                     'not wholly blind to how much the choice is worth'
                     if vN > v0 + 0.01 else
                     f'the F-selection rate does not rise with the margin ({v0 * 100:.1f} % to '
                     f'{vN * 100:.1f} %): a decision worth almost nothing and one worth a fifth of an '
                     'F1 point are treated the same way, which is what a plain classification '
                     'objective does')
        # The two share columns are conditioned differently and must not be divided into each other:
        # rf_F_share_where_F_is_optimal is a recall on the rows where F is optimal, whose ideal value
        # is 100 %; reference_F_share is an unconditional share of the bin. Comparing them directly is
        # the same denominator mix-up as the payload-versus-share error of P2-R14 A-2.
        scale = (f'but that is a recall on the rows where F is optimal, where an oracle reaches 100 %, '
                 f'so {vN * 100:.1f} % leaves {(1 - vN) * 100:.1f} % of them taking a lesser action. '
                 f'Unconditionally the forest requests F on {hi["rf_F_share"] * 100:.1f} % of that '
                 f"bin's rows against a reference {ref * 100:.1f} %")
        trend = f'{direction} -- {scale}'
    return {'bins': rows, 'reading': trend,
            'note': 'the margin is |Q_F - Q_L| on the same row, so it measures how much the F-versus-L '
                    'choice is worth under the locked accounting',
            'conditioning_note': 'the two RF columns are not comparable to each other: "RF F share" is '
                                 'unconditional within the bin and belongs beside the reference share, '
                                 'while "RF F share where F is optimal" is a recall whose ideal value '
                                 'is 100 %'}


def build():
    d, r1, tie = load()
    cells = []
    for (c, s), t in d.groupby(['channel', 'snr_db']):
        m = ((d.channel == c) & (d.snr_db == s)).to_numpy()
        cells.append({'channel': c, 'snr_db': int(s), 'rows': int(m.sum()),
                      'reference_F_share': scene_equal((d.a_star.to_numpy()[m] == 'F').astype(float),
                                                       d.scene.to_numpy()[m]),
                      'rf_F_share': scene_equal((d.pred_joint.to_numpy()[m] == 'F').astype(float),
                                                d.scene.to_numpy()[m]),
                      'mean_p_F': float(d.p_F.to_numpy()[m].mean()),
                      'mean_p_F_where_F_is_optimal': (
                          float(d.p_F.to_numpy()[m & (d.a_star.to_numpy() == 'F')].mean())
                          if (m & (d.a_star.to_numpy() == 'F')).any() else None),
                      'scene_equal_loss': scene_equal(d.loss.to_numpy()[m], d.scene.to_numpy()[m])})
    cells.sort(key=lambda r: (r['channel'], r['snr_db']))

    hi_mask = np.zeros(len(d), bool)
    for c, s in Q_HI_CELLS:
        hi_mask |= ((d.channel == c) & (d.snr_db == s)).to_numpy()

    per_hi_cell = {}
    for c, s in Q_HI_CELLS:
        m = ((d.channel == c) & (d.snr_db == s)).to_numpy()
        per_hi_cell[f'{c} {s} dB'] = {'C2': c2_loss_sources(d, m), 'C3': c3_beliefs(d, m),
                                      'C4': c4_margin(d, m)}

    return {'schema': 'catosg-p2-rf-diagnostics/1',
            'status': 'DIAGNOSIS ONLY. No model is fitted, no hyperparameter is changed, no label '
                      'rule is altered. It reads the out-of-fold record of the round that produced '
                      'the negative result',
            'inputs': {'oof': sha(OOF_CSV), 'round1': sha(ROUND1)},
            'tie_slack': tie,
            'grid_caveat': 'this round uses the original 22-cell grid. The measured 8.5, 9.0 and 9.5 '
                           'dB points are not in it, so nothing here is affected by them and nothing '
                           'here should be read as covering that SNR range',
            'C1_fit_vs_generalise': c1_fit_vs_generalise(r1, d),
            'C2_loss_sources': {'all cells': c2_loss_sources(d),
                                'AWGN only': c2_loss_sources(d, (d.channel == 'awgn').to_numpy()),
                                'Rayleigh only': c2_loss_sources(d, (d.channel == 'rayleigh').to_numpy()),
                                'high-reliability AWGN cells': c2_loss_sources(d, hi_mask)},
            'C3_beliefs': {'all cells': c3_beliefs(d),
                           'AWGN only': c3_beliefs(d, (d.channel == 'awgn').to_numpy()),
                           'high-reliability AWGN cells': c3_beliefs(d, hi_mask)},
            'C4_margin': {'all cells': c4_margin(d),
                          'AWGN only': c4_margin(d, (d.channel == 'awgn').to_numpy()),
                          'high-reliability AWGN cells': c4_margin(d, hi_mask)},
            'C5_per_cell': cells, 'C5_per_high_reliability_cell': per_hi_cell,
            'command': 'python projects/ca_tosg_p2/protocol/rf_diagnostics.py'}


def cap1(t):
    return t[:1].upper() + t[1:]


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/rf_diagnostics.py -- do not edit by hand -->',
         '# Why the first forest declines F (P2-R16 C)', '',
         f"**{m['status']}.**", '', f"**Grid.** {cap1(m['grid_caveat'])}.", '',
         f"**Tie slack.** {m['tie_slack']['rows_below_zero']:,} rows carry a loss below zero, the "
         f"smallest being {m['tie_slack']['min_loss']:.2e}. {cap1(m['tie_slack']['explanation'])}.", '',
         '## C-1 Fitting or generalising', '',
         '| held-out scene | RF F share, training scenes | reference, training | RF F share, held out '
         '| reference, held out |', '|---|---:|---:|---:|---:|']
    c1 = m['C1_fit_vs_generalise']
    for r in c1['per_fold']:
        L.append(f"| {r['held_out_scene']} | {r['rf_F_share_training_scenes'] * 100:.1f} % | "
                 f"{r['reference_F_share_training_scenes'] * 100:.1f} % | "
                 f"{r['rf_F_share_held_out'] * 100:.1f} % | "
                 f"{r['reference_F_share_held_out'] * 100:.1f} % |")
    L += ['', f"Mean over folds: **{c1['mean_rf_F_share_training'] * 100:.1f} %** in training scenes "
          f"and **{c1['mean_rf_F_share_held_out'] * 100:.1f} %** out of fold, against a reference of "
          f"**{c1['reference_F_share'] * 100:.1f} %**.", '',
          f"**Reading: {c1['reading']}.**", '', f"{cap1(c1['note'])}.", '',
          '## C-2 Where the F1 loss comes from', '']
    for lab, v in m['C2_loss_sources'].items():
        if not v:
            continue
        L += [f"### {lab}", '',
              f"Scene-equal total loss against the labelled optimum: **{v['scene_equal_total_loss']:+.5f}**. "
              f"The forest agrees with the optimum on {v['agreement_rows']:,} of {v['rows']:,} rows "
              f"({v['agreement_row_share'] * 100:.1f} %).", '',
              '| error | rows | row share | scene-equal loss | share of total loss | loss per row |',
              '|---|---:|---:|---:|---:|---:|']
        for k, c in v['categories'].items():
            L.append(f"| {k} | {c['rows']:,} | {c['row_share'] * 100:.1f} % | "
                     f"{c['scene_equal_loss']:+.5f} | {c['share_of_total_loss'] * 100:.1f} % | "
                     f"{c['mean_loss_per_row']:+.5f} |")
        L += ['', f"{cap1(v['identity_note'])}.", '']
    L += ['## C-3 What the forest believed', '']
    for lab, v in m['C3_beliefs'].items():
        L += [f"### {lab}", '',
              '| rows where a\\* is | rows | mean P(F) | P(F) p05 | p25 | p50 | p75 | p95 | F ranked '
              '1st | 2nd | 3rd | P(F) < 0.05 |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for star in ('F', 'L', 'E'):
            r = v.get(star)
            if not r:
                continue
            q = r['p_F_quantiles']
            L.append(f"| **{star}** | {r['rows']:,} | {r['p_F_mean']:.4f} | {q['p05']:.4f} | "
                     f"{q['p25']:.4f} | {q['p50']:.4f} | {q['p75']:.4f} | {q['p95']:.4f} | "
                     f"{r['share_F_ranked_first'] * 100:.1f} % | "
                     f"{r['share_F_ranked_second'] * 100:.1f} % | "
                     f"{r['share_F_ranked_third'] * 100:.1f} % | "
                     f"{r['share_p_F_below_0.05'] * 100:.1f} % |")
        if v.get('reading'):
            L += ['', f"**Reading: {v['reading']}.**", '']
        else:
            L.append('')
    L += ['## C-4 Does the forest see how much the choice is worth', '']
    for lab, v in m['C4_margin'].items():
        L += [f"### {lab}", '', f"{cap1(v['note'])}.", '', f"{cap1(v['conditioning_note'])}.", '',
              '| margin bin | rows | mean margin | reference F share | RF F share | RF F share where '
              'F is optimal | mean P(F) where F is optimal |',
              '|---|---:|---:|---:|---:|---:|---:|']
        for r in v['bins']:
            w = ('—' if r['rf_F_share_where_F_is_optimal'] is None
                 else f"{r['rf_F_share_where_F_is_optimal'] * 100:.1f} %")
            pf = ('—' if r['mean_p_F_where_F_is_optimal'] is None
                  else f"{r['mean_p_F_where_F_is_optimal']:.4f}")
            L.append(f"| {r['bin']} | {r['rows']:,} | {r['mean_margin']:.5f} | "
                     f"{r['reference_F_share'] * 100:.1f} % | {r['rf_F_share'] * 100:.1f} % | "
                     f"{w} | {pf} |")
        if v.get('reading'):
            L += ['', f"**Reading: {v['reading']}.**", '']
        else:
            L.append('')
    L += ['## C-5 Per cell', '',
          '| channel | SNR | reference F share | RF F share | mean P(F) | mean P(F) where F optimal | '
          'scene-equal loss |', '|---|---:|---:|---:|---:|---:|---:|']
    for r in m['C5_per_cell']:
        pf = ('—' if r['mean_p_F_where_F_is_optimal'] is None
              else f"{r['mean_p_F_where_F_is_optimal']:.4f}")
        L.append(f"| {r['channel']} | {r['snr_db']} | {r['reference_F_share'] * 100:.1f} % | "
                 f"{r['rf_F_share'] * 100:.1f} % | {r['mean_p_F']:.4f} | {pf} | "
                 f"{r['scene_equal_loss']:+.5f} |")
    L += ['', '### The high-reliability AWGN cells, one at a time', '']
    for cell, v in m['C5_per_high_reliability_cell'].items():
        c2, c3, c4 = v['C2'], v['C3'], v['C4']
        f = c3.get('F') if c3 else None
        top = next(iter(c2['categories'].items())) if c2 and c2['categories'] else None
        L.append(f"* **{cell}** — total loss {c2['scene_equal_total_loss']:+.5f}; "
                 + (f"largest error `{top[0]}` at {top[1]['scene_equal_loss']:+.5f} over "
                    f"{top[1]['rows']:,} rows; " if top else '')
                 + (f"where F is optimal the forest ranks it first on "
                    f"{f['share_F_ranked_first'] * 100:.1f} %, second on "
                    f"{f['share_F_ranked_second'] * 100:.1f} %, with mean P(F) {f['p_F_mean']:.4f}"
                    if f else 'F is optimal on no row here'))
    L += ['', '## Inputs', '', '| file | sha256 |', '|---|---|']
    for k, v in m['inputs'].items():
        L.append(f"| {k} | `{v[:16]}…` |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        ok = (os.path.exists(OUT_JSON) and open(OUT_JSON).read() == js
              and os.path.exists(OUT_MD) and open(OUT_MD).read() == md)
        print('rf diagnostics:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
