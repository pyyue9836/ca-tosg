#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R26/R27 — what existing methods use to decide, what they decide, and when. Literature only.

Five columns per paper: what information the decision uses, whose information it is, what the decision
selects, when it happens relative to which transmission, and what obtaining that information costs.

Every quote is checked against a text extracted from the paper's own PDF and archived under
`results/lit/` with its sha256, so a quote that drifts from its source fails generation rather than
reaching the table. What `--check` enforces:

  * every quote appears VERBATIM in the archived extraction after collapsing whitespace -- PDF
    extraction inserts line breaks and hyphenates across them, so quotes are stored exactly as the
    extraction renders them, ligatures included;
  * every quote is 15 words or fewer;
  * the cited anchor equals the nearest declared section label preceding the quote, or `Abstract` when
    none precedes. Automatic heading detection was tried and rejected: on these PDFs it returned
    "4 Mar" and "3 Abstract" as headings, and a citation column built on that would be false
    precision. Labels are hand-picked and machine-verified, and a mismatch reports supplied versus
    derived for every row at once;
  * a row marked UNVERIFIED carries no quote at all; an ESTIMATE states its assumption;
  * the cost column carries one of three declared classes, so "the formula excludes it", "it is not
    itemised" and "no source could be opened" are never merged into one claim.

Two corrections to a web summariser, recorded so they cannot re-enter as facts: the figures "22 MBpf"
and "0.98 MBpf" attributed to When2com occur 0 times in its text, and "quarter" occurs 0 times there --
"a quarter of the bandwidth" is Who2com's abstract. Both were dropped for numbers verbatim in source.

    python prerequest_info_review.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
LIT = os.path.join(P2, 'results', 'lit')
CONF_JSON = os.path.join(HERE, 'ego_conf_cues.json')
OUT_MD = os.path.join(ROOT, 'docs', 'p2_prerequest_info_review.md')
OUT_JSON = os.path.join(HERE, 'prerequest_info_review.json')

MAX_QUOTE_WORDS = 15

# D: three cost classes, kept apart rather than collapsed into a single summary sentence.
COST_CLASSES = {
    'formula_excludes': 'the paper gives a cost formula and that formula demonstrably excludes the '
                        'decision signalling',
    'not_itemised': 'the paper reports a figure or ratio but does not itemise the decision signalling, '
                    'so whether it is included cannot be confirmed',
    'unverified': 'no source text could be opened, so nothing is claimed',
}

TIMING = {
    'before_handshake': '握手前 (before the handshake itself)',
    'before_message': '正式感知消息前 (before the perception message proper)',
    'after_first_tx': '首次传输后 (after a first transmission)',
    'after_reception': '接收后 (after reception)',
    'unverified': '未核实',
}

LABELS = {
    'where2comm': ['4.1 Observation encoder', '4.2 Spatial con', '4.3 Spatial con', '4.4 Spatial con',
                   '4.5 Detection decoder', '5.1 Datasets and experimental settings',
                   '7.5 Detailed information about experimental settings'],
    'when2com': ['3.2. Communication Groups Construction', 'Bandwidth (Mbpf / # of links)'],
    'who2com': ['I. I NTRODUCTION', 'III. P ROPOSED METHOD',
                'B. Communication via Three-Stage Handshake', 'D. Evaluation metrics'],
    'select2col': ['III. S YSTEM MODEL AND PROBLEM FORMULATION', 'A. System Model',
                   'V. C OLLABORATOR SELECTION BASED ON IOSI', 'A. Enhanced Weight Estimation'],
    'smartcooper': ['I. I NTRODUCTION', 'III. O UR PROPOSED SCHEME', 'A. Channel-aware Optimization',
                    'B. Adaptive Judger Mechanism'],
    'cods': ['II. S YSTEM MODEL', 'A. Semantic Compression Codec', 'IV. S IMULATION RESULTS'],
    'semharq': ['I. I NTRODUCTION', 'II. S YSTEM MODEL', 'B. Feature importance ranking'],
}

PAPERS = [
    dict(key='where2comm', name='Where2comm', venue='NeurIPS 2022',
         url='https://arxiv.org/abs/2209.12836',
         b1_quote='The spatial conﬁdence generator generates a spatial conﬁdence map from the feature map',
         b1_label='4.2 Spatial con',
         b1='A confidence map from a detection decoder over the agent\'s own feature map.',
         b2_quote='The request map of theith agent is R(k) i = 1− C(k) i',
         b2_label='4.3 Spatial con',
         b2b_quote='Φselect(C(k) i ⊙ R(k−1) j )',
         b2b_label='4.3 Spatial con',
         b2='Split by round. The initial round is decided by the sending agent\'s own local confidence '
            'map alone; later rounds combine it with the receiver\'s request map from the previous '
            'round, which is Eq. (2). The ego\'s request therefore steers rounds after the first, not '
            'the first.',
         sel='Which spatial regions to send, and to whom: a per-location binary mask over the BEV '
             'feature map, one mask per receiver.',
         timing='before_message',
         timing_note='initial round before the perception message; later rounds use the previous '
                     'round\'s exchange',
         b3_quote='the communication volume is log2 ( |M(k) i→j|× D× 32/8 )',
         b3_label='7.5 Detailed information about experimental settings',
         b3='Eq. (5) counts the selected feature volume: log2 of selected cells x channels x 4 bytes. '
            'The request map is H x W and does not appear in that formula.',
         cost_class='formula_excludes',
         implication='Its decision input is the ego\'s own detection confidence, kept as a spatial map '
                     'over locations.'),

    dict(key='when2com', name='When2com', venue='CVPR 2020', url='https://arxiv.org/abs/2006.00176',
         b1_quote='compresses its local observationsxi into a com- pact query vectorµi and a key vectorκi',
         b1_label='3.2. Communication Groups Construction',
         b1='A learned low-dimensional query from the agent\'s own raw observation.',
         b2_quote='We further broad- cast the query to all of other agents',
         b2_label='3.2. Communication Groups Construction',
         b2='Both sides: the ego broadcasts a query, every other agent holds a key, and the match sets '
            'the connection weights.',
         sel='Whom to connect to and how strongly: the communication group and its connection weights, '
             'pruned by an activation.',
         timing='before_handshake',
         timing_note='the query and key are formed from local observations before the handshake runs',
         b3_quote='Ours 0.385 / 0.77',
         b3_label='Bandwidth (Mbpf / # of links)',
         b3_label_note='a table header, not a section heading: this paper\'s experiment-section '
                       'headings did not survive PDF extraction, so no section number is claimed',
         b3='MBytes per frame and links per agent, against 2.5 / 5 for the fully connected baselines. '
            'The text also states a one-fourth bandwidth ratio, but that sentence is interrupted by a '
            'figure\'s axis labels in the extraction and is therefore not quoted. The query\'s own '
            'size is not itemised.',
         cost_class='not_itemised',
         implication='The decision needs a key from every candidate, so it is not formed by the ego '
                     'alone.'),

    dict(key='who2com', name='Who2com', venue='ICRA 2020', url='https://arxiv.org/abs/2003.09575',
         b1_quote='compute a matching score, s ji, between their keys, κi∈ Rk, and the request message',
         b1_label='B. Communication via Three-Stage Handshake',
         b1='A learned key from each candidate\'s own observation, scored against the requester\'s '
            'compressed request.',
         b2_quote='the de- graded agent ﬁrst broadcasts its request message',
         b2_label='B. Communication via Three-Stage Handshake',
         b2='Both sides, in three stages: request from the ego, scores back from candidates, then the '
            'ego connects.',
         sel='Whom to receive from: the best n agents, each then sending one full feature map.',
         timing='before_message',
         timing_note='the three-stage handshake completes before the selected agent sends its feature '
                     'map',
         b3_quote='comparable to centralized ones using a quarter of the bandwidth',
         b3_label='Abstract',
         b3='A ratio in the abstract; the selection sends one feature map where centralized baselines '
            'send all. The request and the returned scores are not itemised.',
         cost_class='not_itemised',
         implication='The score that decides is computed by the candidates, not by the ego.'),

    dict(key='select2col', name='Select2Col', venue='IEEE TVT 2024',
         url='https://arxiv.org/abs/2307.16517',
         b1_quote='each node corresponds to an agent and comprises its sparse map along with the semantic',
         b1_label='A. Enhanced Weight Estimation',
         b1='A GNN over per-agent nodes, each holding that agent\'s sparse feature map and its '
            'information latency.',
         b2_quote='receives semantic information transmitted by its neighboring agents',
         b2_label='A. System Model',
         b2='Collaborator-side, and only after arrival: the sparse maps forming the GNN nodes are the '
            'received semantic information.',
         sel='Which collaborators to keep and how to weight them for fusion; agents below a weight '
             'threshold are dropped.',
         timing='after_reception',
         b3='Not itemised for the decision itself; the paper models transmission latency instead. No '
            'estimate is offered, because the quantity would be the cost of something this process '
            'does not do.',
         cost_class='not_itemised',
         implication='A process of a different shape: it decides after receiving, so its decision '
                     'information is not of a kind the ego holds beforehand.'),

    dict(key='smartcooper', name='SmartCooper', venue='ICRA 2024',
         url='https://arxiv.org/abs/2402.00321',
         b1_quote='dynamically adjust the compression ratio based on the channel state information',
         b1_label='Abstract',
         b1='Channel state information sets the compression ratio; sensing-coverage overlap drives the '
            'judger.',
         b2_quote='our judger scores reconstructed image sequences based on the union of sensing coverage',
         b2_label='I. I NTRODUCTION',
         b2='Split: CSI is available before transmission, but the judger scores data already '
            'transmitted and reconstructed at the ego.',
         sel='The compression ratio per vehicle, and whether reconstructed data is admitted to fusion '
             'at all.',
         timing='after_reception',
         timing_note='the CSI half is before the message; the judger half is after reconstruction, and '
                     'the row is classified by the judger',
         b3_quote='a substantial reduction in communication costs by 23.10%',
         b3_label='Abstract',
         b3='A ratio against a no-judger scheme. Since the judger runs after reconstruction, the saving '
            'falls on later rounds rather than on the transmission being judged. Not itemised for the '
            'decision.',
         cost_class='not_itemised',
         implication='A process of a different shape: its channel half is pre-transmission, its task '
                     'half needs the data first.'),

    dict(key='cods', name='CoDS',
         venue='“CoDS: Collaborative Perception via Digital Semantic Communication”, Jipeng Gan, Le '
               'Liang, Hua Zhang, Chongtao Guo, Shi Jin, arXiv 2512.22513',
         url='https://arxiv.org/abs/2512.22513',
         b1_quote='the spatial compression ratio as the fraction of featu res selected for transmission',
         b1_label='II. S YSTEM MODEL',
         b1='A selection mask over the sender\'s own BEV feature map, plus SNR for modulation and code '
            'rate.',
         b2_quote='the CA V ﬁrst employs a feature extraction network',
         b2_label='II. S YSTEM MODEL',
         b2='Sender-side, before transmission: the CAV decides what of its own features to send. The '
            'ego does not request.',
         sel='Which of its own feature cells to send, the channel compression ratio, and the modulation '
             'order and code rate.',
         timing='before_message',
         b3_quote='Channel Uses = Qd × q C × γs × Rc × log2 Or',
         b3_label='IV. S IMULATION RESULTS',
         b3='Also expressed in Channel Uses. Whether it is the same accounting as ours is not settled '
            'here: code rate, modulation order, the mask or index overhead, packet headers, and '
            'whether a failed message is still charged all remain to be checked against our chain.',
         cost_class='not_itemised',
         implication='The nearest transmission accounting to ours, with the decision sitting at the '
                     'sender about its own data.'),

    dict(key='semharq', name='SemHARQ', venue='arXiv 2404.08490',
         url='https://arxiv.org/abs/2404.08490',
         b1_quote='the gradients of the task performance with respect to the features are considered',
         b1_label='I. I NTRODUCTION',
         b1='Feature importance from task-performance gradients at the transmitter; distortion of '
            'received features at the receiver.',
         b2_quote='generate a binary feedback vector p(j+1)',
         b2_label='II. S YSTEM MODEL',
         b2='Both, but only after a first transmission: the receiver evaluates what arrived and feeds '
            'back which features to resend.',
         sel='Which features to send first, how many per round, and which corrupted features to '
             'retransmit.',
         timing='after_first_tx',
         timing_note='the importance ranking is formed at the transmitter before sending, but the '
                     'retransmission decision requires the first transmission to have happened',
         b3='No figure for the feedback overhead is given. Estimated: one bit per feature of the block '
            'just received, so B bits per retransmission round.',
         b3_kind='estimate',
         b3_assumption='Assumes the binary vector p is uncoded, one bit per feature of the block just '
                       'received, and sent once per round; the paper states the vector and its '
                       'indexing but gives neither a length in bits nor a channel for it.',
         cost_class='not_itemised',
         implication='A process of a different shape: its ranking is retrospective, needing a '
                     'transmission before it can rank.'),

    dict(key=None, name='ML-Cooper', venue='IEEE IoT-J 9(21):21370-21381, 2022',
         url='https://ieeexplore.ieee.org/document/9786737/',
         b1='UNVERIFIED', b2='UNVERIFIED', b3='UNVERIFIED', sel='UNVERIFIED',
         timing='unverified', cost_class='unverified',
         implication='UNVERIFIED: the full text is behind IEEE Xplore, the abstract page returned '
                     'empty on fetch and no preprint was found, so no quote could be located. Only '
                     'the bibliographic record is confirmed.'),
]

# C: one comparison of information content, stated as a fact about what each quantity retains.
COMPARISON = dict(
    w2_quote_a='spatial conﬁdence map reﬂects the perceptually critical level of various spatial areas',
    w2_label_a='4.2 Spatial con',
    w2_quote_b='for the locations with low conﬁdence score, an agent is hard to tell',
    w2_label_b='4.3 Spatial con',
)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def flat(p):
    return re.sub(r'\s+', ' ', open(p, encoding='utf-8', errors='replace').read())


def verify(texts):
    """Locate every quote, derive its anchor, and report all disagreements at once."""
    checks, mismatch = [], []
    for p in PAPERS:
        k = p['key']
        if k is None:
            for col in ('b1', 'b2', 'b3', 'sel'):
                if p[col] != 'UNVERIFIED':
                    raise SystemExit(f'{p["name"]}: an unverified row must carry no content')
            if any(key.endswith('_quote') for key in p):
                raise SystemExit(f'{p["name"]}: an unverified row must carry no quote')
            checks.append({'paper': p['name'], 'status': 'unverified', 'quotes_checked': 0})
            continue
        t = texts[k]
        label_pos = {}
        for lab in LABELS[k]:
            i = t.find(lab)
            if i < 0:
                raise SystemExit(f'{p["name"]}: declared label not in source: {lab!r}')
            label_pos[lab] = i
        n = 0
        for key in [x for x in p if x.endswith('_quote')]:
            stem = key[:-6]
            q = p[key]
            if len(q.split()) > MAX_QUOTE_WORDS:
                raise SystemExit(f'{p["name"]} {stem}: quote is {len(q.split())} words')
            pos = t.find(q)
            if pos < 0:
                raise SystemExit(f'{p["name"]} {stem}: quote not verbatim in source: {q!r}')
            before = [(i, l) for l, i in label_pos.items() if i < pos]
            derived = max(before)[1] if before else 'Abstract'
            supplied = p[f'{stem}_label']
            if supplied != derived:
                mismatch.append(f'{p["name"]} {stem}: supplied {supplied!r}, derived {derived!r} '
                                f'(quote at {pos})')
            n += 1
        if p.get('b3_kind') == 'estimate':
            if not p.get('b3_assumption'):
                raise SystemExit(f'{p["name"]}: an estimate must state its assumption')
            if 'b3_quote' in p:
                raise SystemExit(f'{p["name"]}: an estimate must not also carry a quote')
        if p['cost_class'] not in COST_CLASSES:
            raise SystemExit(f'{p["name"]}: unknown cost class {p["cost_class"]!r}')
        if p['timing'] not in TIMING:
            raise SystemExit(f'{p["name"]}: unknown timing {p["timing"]!r}')
        checks.append({'paper': p['name'], 'status': 'verified', 'quotes_checked': n,
                       'labels_checked': len(LABELS[k])})

    t = texts['where2comm']
    lp = {lab: t.find(lab) for lab in LABELS['where2comm']}
    for qk, lk in (('w2_quote_a', 'w2_label_a'), ('w2_quote_b', 'w2_label_b')):
        q = COMPARISON[qk]
        if len(q.split()) > MAX_QUOTE_WORDS:
            raise SystemExit(f'comparison {qk}: quote is {len(q.split())} words')
        pos = t.find(q)
        if pos < 0:
            raise SystemExit(f'comparison {qk}: quote not verbatim in source: {q!r}')
        before = [(i, l) for l, i in lp.items() if 0 <= i < pos]
        derived = max(before)[1] if before else 'Abstract'
        if COMPARISON[lk] != derived:
            mismatch.append(f'comparison {qk}: supplied {COMPARISON[lk]!r}, derived {derived!r} '
                            f'(quote at {pos})')
    if mismatch:
        raise SystemExit('the supplied section anchors disagree with the source:\n  '
                         + '\n  '.join(mismatch))
    return checks


def build():
    texts = {}
    for k in LABELS:
        f = os.path.join(LIT, k + '.txt')
        if not os.path.exists(f):
            raise SystemExit(f'archived extraction missing: {os.path.relpath(f, ROOT)}')
        texts[k] = flat(f)
    checks = verify(texts)

    conf = json.load(open(CONF_JSON, encoding='utf-8'))
    ours = {'fields': conf['fields'], 'score_min': conf['score_distribution']['min'],
            'boxes': conf['score_distribution']['boxes'],
            'zero_box_frames': conf['zero_box_frames'],
            'truncation': conf['score_distribution']['truncation_note']}

    return {'schema': 'catosg-p2-prerequest-review/2',
            'status': 'LITERATURE ONLY. No experiment, no model, no code change beyond this generator. '
                      'Every quote is verified verbatim against a text extracted from the paper\'s own '
                      'PDF and archived under results/lit/',
            'max_quote_words': MAX_QUOTE_WORDS,
            'cost_classes': COST_CLASSES, 'timing_values': TIMING,
            'web_summary_corrections': [
                'the figures "22 MBpf" and "0.98 MBpf" attributed to When2com occur 0 times in its '
                'text and were dropped',
                '"quarter" occurs 0 times in When2com; "a quarter of the bandwidth" is Who2com\'s '
                'abstract and is cited there only'],
            'anchor_note': 'anchors are hand-picked and machine-verified: each must equal the nearest '
                           'declared label preceding its quote, or Abstract when none precedes. '
                           'Automatic heading detection was rejected after it returned "4 Mar" and '
                           '"3 Abstract" as headings on these PDFs',
            'papers': [dict(p) for p in PAPERS],
            'comparison': COMPARISON, 'our_five_dimensions': ours,
            'verification': checks,
            'sources': {k: {'path': os.path.relpath(os.path.join(LIT, k + '.txt'), ROOT),
                            'sha256': sha(os.path.join(LIT, k + '.txt'))} for k in sorted(LABELS)},
            'command': 'python projects/ca_tosg_p2/protocol/prerequest_info_review.py'}


def md_cell(t):
    """A markdown table cell: pipes escaped so a quoted formula cannot split the row.

    Escaping happens here and nowhere else. The quote stored in the data keeps its raw characters and
    is what the verbatim gate compares against the source; only the rendered cell is escaped.
    """
    return t.replace('|', '\\|')


def cell(p, col):
    q = p.get(f'{col}_quote')
    body = p[col]
    if q:
        note = p.get(f'{col}_label_note')
        anchor = f"*{p[f'{col}_label']}*" + (f" [{note}]" if note else '')
        out = f"“{q}” ({anchor}) — {body}"
        q2 = p.get(f'{col}b_quote')
        if q2:
            out += f" Later rounds: “{q2}” (*{p[f'{col}b_label']}*)."
        return out
    if col == 'b3' and p.get('b3_kind') == 'estimate':
        return f"**估算** — {body} *Assumption:* {p['b3_assumption']}"
    return body


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/prerequest_info_review.py -- do not edit by hand -->',
         '# Decision information, decision object and decision timing in existing methods (P2-R27)', '',
         f"**{m['status']}.**", '',
         f"**Anchors.** {m['anchor_note'][0].upper() + m['anchor_note'][1:]}.", '',
         '**Two corrections to a web summary, recorded so they cannot re-enter as facts.**', '']
    for c in m['web_summary_corrections']:
        L.append(f"* {c[0].upper() + c[1:]}.")
    L += ['', '## Cost classes, kept apart', '', '| class | meaning |', '|---|---|']
    for k, v in m['cost_classes'].items():
        L.append(f"| `{k}` | {v} |")
    L += ['', '## The table', '',
          '| method | B-1 what information decides | B-2 whose information | A-1 what is selected | '
          'A-2 when, relative to which transmission | B-3 cost of obtaining it | cost class |',
          '|---|---|---|---|---|---|---|']
    for p in m['papers']:
        if p['key'] is None:
            L.append(f"| **{p['name']}** ({p['venue']}) | 未核实 | 未核实 | 未核实 | 未核实 | 未核实 | "
                     f"`{p['cost_class']}` |")
            continue
        tim = m['timing_values'][p['timing']]
        if p.get('timing_note'):
            tim += f" — {p['timing_note']}"
        L.append('| ' + ' | '.join(md_cell(x) for x in (
            f"**{p['name']}** ({p['venue']})", cell(p, 'b1'), cell(p, 'b2'), p['sel'], tim,
            cell(p, 'b3'), f"`{p['cost_class']}`")) + ' |')
    c, o = m['comparison'], m['our_five_dimensions']
    L += ['', '## C One comparison of information content, stated as a fact', '',
          f"Where2comm retains **position**: “{c['w2_quote_a']}” (*{c['w2_label_a']}*), and it retains "
          f"the **low-confidence** areas rather than discarding them: “{c['w2_quote_b']}” "
          f"(*{c['w2_label_b']}*). Its decision object is a region.", '',
          f"This project's P2-R18 five dimensions are **global statistics of post-processed box "
          f"scores** — {', '.join('`' + f + '`' for f in o['fields'])} over {o['boxes']:,} boxes. "
          f"Position is not retained, and boxes scoring below 0.2 are already discarded: "
          f"{o['truncation']}. Zero-box frames on validate: {o['zero_box_frames']}.", '',
          '**These are not the same information.** The P2-R18 result therefore does not cover the '
          'Where2comm quantity: a spatial map of where confidence is low is not recoverable from five '
          'scalars of a truncated score distribution.', '',
          '## What each row means for us', '',
          'Factual relations only; no recommendation is drawn here.', '']
    for p in m['papers']:
        L.append(f"* **{p['name']}** — {p['implication']}")
    L += ['', '## Conclusion', '',
          'The information these methods use includes ego-side global statistics, spatial structure, '
          'the sending agent\'s own information, and requests or feedback exchanged during '
          'communication. The selection problem each one solves, and the moment at which its '
          'information becomes available, differ from one another and from ours.', '',
          'Three possibilities remain undistinguished by anything measured so far, and they are listed '
          'side by side without preference:', '',
          '1. the ego\'s own pre-request information is insufficient to predict the F-versus-L '
          'advantage;',
          '2. the information is present but lost in the statistical extraction, for example by '
          'discarding position and truncating the score distribution;',
          '3. the information survives extraction but the learning methods tried have not used it.', '',
          '## Verification', '',
          f"Quotes are at most {m['max_quote_words']} words, compared after collapsing whitespace, and "
          'stored exactly as the extraction renders them.', '',
          '| paper | status | quotes checked | labels checked |', '|---|---|---:|---:|']
    for ck in m['verification']:
        L.append(f"| {ck['paper']} | {ck['status']} | {ck['quotes_checked']} | "
                 f"{ck.get('labels_checked', 0)} |")
    L += ['', '## Sources', '', '| paper | archived extraction | sha256 |', '|---|---|---|']
    for k, v in m['sources'].items():
        L.append(f"| {k} | `{v['path']}` | `{v['sha256'][:16]}…` |")
    L += ['', '| method | primary source |', '|---|---|']
    for p in m['papers']:
        L.append(f"| {p['name']} | {p['url']} |")
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    js, md = json.dumps(m, indent=1, ensure_ascii=False) + '\n', markdown(m)
    if a.check:
        ok = (os.path.exists(OUT_JSON) and open(OUT_JSON, encoding='utf-8').read() == js
              and os.path.exists(OUT_MD) and open(OUT_MD, encoding='utf-8').read() == md)
        print('prerequest info review:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w', encoding='utf-8').write(js)
    open(OUT_MD, 'w', encoding='utf-8').write(md)
    print('wrote', os.path.relpath(OUT_MD, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())
