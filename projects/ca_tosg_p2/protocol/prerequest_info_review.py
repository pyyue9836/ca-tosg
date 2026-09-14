#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R26 — what existing methods use to decide BEFORE the request. Literature only, zero experiments.

Three columns per paper and nothing else: what information the decision uses, whose information it is,
and what it costs to obtain. Every quote is checked against a text extracted from the paper's own PDF
and archived in `results/lit/`, so a quote that drifted from its source fails generation rather than
reaching the table.

What `--check` enforces:

  * every quote appears VERBATIM in the archived extraction, after collapsing whitespace -- PDF
    extraction inserts line breaks and hyphenates across them, so the comparison is whitespace-
    collapsed and the quotes are stored exactly as the extraction renders them, ligatures included;
  * every quote is 15 words or fewer;
  * every cited section label also appears verbatim, at a position BEFORE its quote, and is the
    nearest of that paper's declared labels -- the label is chosen by hand and verified by machine,
    because automatic heading detection on these seven PDFs returned things like "4 Mar" and
    "3 Abstract" and a citation column built on that would be false precision;
  * a row marked UNVERIFIED carries no quote at all;
  * a row marked ESTIMATE states its assumption.

Two corrections to what a web summariser told me, recorded because they would otherwise have entered
the table as facts: the figures "22 MBpf" and "0.98 MBpf" attributed to When2com do not occur anywhere
in its text (0 hits), and neither does "quarter" -- "a quarter of the bandwidth" belongs to Who2com's
abstract. Both were dropped and replaced with numbers that are verbatim in the source.

    python prerequest_info_review.py [--check]
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
P2 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(P2))
LIT = os.path.join(P2, 'results', 'lit')
OUT_MD = os.path.join(ROOT, 'docs', 'p2_prerequest_info_review.md')
OUT_JSON = os.path.join(HERE, 'prerequest_info_review.json')

MAX_QUOTE_WORDS = 15

# Section labels declared per paper; each is verified to exist verbatim in the extraction.
LABELS = {
    'where2comm': ['4.1 Observation encoder', '4.2 Spatial con', '4.3 Spatial con', '4.4 Spatial con',
                   '4.5 Detection decoder', '5.1 Datasets and experimental settings',
                   '7.5 Detailed information about experimental settings'],
    'when2com': ['3.2. Communication Groups Construction',
                 'Bandwidth (Mbpf / # of links)'],
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
    dict(key='where2comm', name='Where2comm', venue='NeurIPS 2022', url='https://arxiv.org/abs/2209.12836',
         b1_quote='The spatial conﬁdence generator generates a spatial conﬁdence map from the feature map',
         b1_label='4.2 Spatial con',
         b1='A confidence map produced by a detection decoder run on the agent\'s OWN feature map, '
             'before anything is received.',
         b2_quote='The request map of theith agent is R(k) i = 1− C(k) i',
         b2_label='4.3 Spatial con',
         b2='Ego-side. The ego derives its own request map and sends it; the collaborator then selects '
            'what to return. Round 0 uses the sender\'s confidence alone, so the request only steers '
            'rounds after the first.',
         b3_quote='the communication volume is log2 ( |M(k) i→j|× D× 32/8 )',
         b3_label='7.5 Detailed information about experimental settings',
         b3='Defined, not a fixed figure: log2 of selected cells x channels x 4 bytes. The request map '
            'itself is H x W and its cost is not separately accounted in that formula.',
         b3_kind='quoted',
         implication='The only decision input is the ego\'s own detection confidence, which is exactly '
                     'the quantity our forest already receives as cues; the request map adds a '
                     'collaborator-side selector that our single-collaborator setting does not have.'),
    dict(key='when2com', name='When2com', venue='CVPR 2020', url='https://arxiv.org/abs/2006.00176',
         b1_quote='compresses its local observationsxi into a com- pact query vectorµi and a key vectorκi',
         b1_label='3.2. Communication Groups Construction',
         b1='A learned low-dimensional query from the agent\'s own raw observation; no ground truth and '
            'nothing received.',
         b2_quote='We further broad- cast the query to all of other agents',
         b2_label='3.2. Communication Groups Construction',
         b2='Both: ego broadcasts a query, every other agent holds a key, and the match decides who '
            'transmits.',
         b3_quote='Ours 0.385 / 0.77',
         b3_label='Bandwidth (Mbpf / # of links)',
         b3_label_note='a table header, not a section heading: this paper\'s experiment-section '
                       'headings did not survive PDF extraction, so no section number is claimed',
         b3='MBytes per frame and links per agent, against 2.5 / 5 for the fully connected baselines. '
            'The text also states a one-fourth bandwidth ratio, but that sentence is interrupted by a '
            'figure\'s axis labels in the extraction and so is not quoted here. The query\'s own size '
            'is never costed.',
         b3_kind='quoted',
         implication='The handshake needs a reply from every candidate before the ego can choose, so '
                     'its decision information is not available to a vehicle that must decide alone.'),
    dict(key='who2com', name='Who2com', venue='ICRA 2020', url='https://arxiv.org/abs/2003.09575',
         b1_quote='compute a matching score, s ji, between their keys, κi∈ Rk, and the request message',
         b1_label='B. Communication via Three-Stage Handshake',
         b1='A learned key from each candidate\'s own observation, scored against the requester\'s '
            'compressed request.',
         b2_quote='the de- graded agent ﬁrst broadcasts its request message',
         b2_label='B. Communication via Three-Stage Handshake',
         b2='Both, in three stages: request from ego, scores back from candidates, then ego connects.',
         b3_quote='comparable to centralized ones using a quarter of the bandwidth',
         b3_label='Abstract',
         b3='A ratio in the abstract. The paper states its selection sends one feature map where '
            'centralized baselines send all; the request and score messages are not costed in bits.',
         b3_kind='quoted',
         implication='The score that decides comes from the collaborator, not the ego, so the '
                     'information we are looking for does not exist before the exchange.'),
    dict(key='select2col', name='Select2Col', venue='IEEE TVT 2024', url='https://arxiv.org/abs/2307.16517',
         b1_quote='each node corresponds to an agent and comprises its sparse map along with the semantic',
         b1_label='A. Enhanced Weight Estimation',
         b1='A GNN over per-agent nodes, each holding that agent\'s sparse feature map and its '
            'information latency.',
         b2_quote='receives semantic information transmitted by its neighboring agents',
         b2_label='A. System Model',
         b2='Collaborator-side, and only after arrival: the sparse maps that form the GNN nodes are the '
            'received semantic information.',
         b3='Not given as bits or a ratio for the decision itself. No estimate is offered either, '
            'because the selection happens after reception and therefore has no pre-request signalling '
            'cost to estimate; the paper models transmission latency instead.',
         b3_kind='not_given_no_estimate',
         implication='This is a post-reception filter, not a pre-request decision, so it is a '
                     'counter-example to the question rather than an answer to it.'),
    dict(key='smartcooper', name='SmartCooper', venue='ICRA 2024', url='https://arxiv.org/abs/2402.00321',
         b1_quote='dynamically adjust the compression ratio based on the channel state information',
         b1_label='Abstract',
         b1='Channel state information for the compression ratio; sensing-coverage overlap for the '
            'judger.',
         b2_quote='our judger scores reconstructed image sequences based on the union of sensing coverage',
         b2_label='I. I NTRODUCTION',
         b2='Split: CSI is available before transmission, but the judger scores data that has already '
            'been transmitted and reconstructed at the ego.',
         b3_quote='a substantial reduction in communication costs by 23.10%',
         b3_label='Abstract',
         b3='A ratio against a no-judger scheme. Since the judger runs after reconstruction, the saving '
            'is on subsequent rounds, not on the transmission it judges.',
         b3_kind='quoted',
         implication='Its channel half matches what our arm already has; its task half needs the data '
                     'first, which is the same wall our rounds 1 to 4 ran into.'),
    dict(key='cods', name='CoDS', venue='arXiv 2512.22513', url='https://arxiv.org/abs/2512.22513',
         b1_quote='the spatial compression ratio as the fraction of featu res selected for transmission',
         b1_label='II. S YSTEM MODEL',
         b1='A selection mask over the sender\'s own BEV feature map, plus SNR for modulation and code '
            'rate.',
         b2_quote='the CA V ﬁrst employs a feature extraction network',
         b2_label='II. S YSTEM MODEL',
         b2='Collaborator-side, before transmission: the CAV decides what of its own features to send. '
            'The ego does not request.',
         b3_quote='Channel Uses = Qd × q C × γs × Rc × log2 Or',
         b3_label='IV. S IMULATION RESULTS',
         b3='A formula in channel uses, with quantisation bits q, spatial ratio, LDPC rate and '
            'modulation order -- the same accounting our payload chain uses.',
         b3_kind='quoted',
         implication='Closest to our transmission model, but the decision sits at the sender about its '
                     'own data; it does not tell an ego vehicle what to ask for.'),
    dict(key='semharq', name='SemHARQ', venue='arXiv 2404.08490', url='https://arxiv.org/abs/2404.08490',
         b1_quote='the gradients of the task performance with respect to the features are considered',
         b1_label='I. I NTRODUCTION',
         b1='Feature importance from task-performance gradients at the transmitter; distortion of '
            'received features at the receiver.',
         b2_quote='generate a binary feedback vector p(j+1)',
         b2_label='II. S YSTEM MODEL',
         b2='Both, but after a first transmission: the receiver evaluates what arrived and feeds back '
            'which features to resend.',
         b3='No figure for the feedback overhead is given. Estimated: the feedback is one bit per '
            'feature in the transmitted block, so B bits per retransmission round.',
         b3_kind='estimate',
         b3_assumption='Assumes the binary vector p is uncoded, one bit per feature of the block just '
                       'received, and sent once per round; the paper states the vector exists and its '
                       'indexing but gives neither its length in bits nor a channel for it.',
         implication='Its decision information is retrospective -- it needs a first transmission before '
                     'it can rank anything, so it cannot inform a first request.'),
    dict(key=None, name='ML-Cooper', venue='IEEE IoT-J 9(21):21370-21381, 2022',
         url='https://ieeexplore.ieee.org/document/9786737/',
         b1='UNVERIFIED', b2='UNVERIFIED', b3='UNVERIFIED', b3_kind='unverified',
         implication='UNVERIFIED: not entered into the comparison. The full text is behind IEEE '
                     'Xplore, the abstract page returned empty on fetch and no preprint was found, so '
                     'no quote could be located. Only the bibliographic record above is confirmed.'),
]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def flat(p):
    return re.sub(r'\s+', ' ', open(p, encoding='utf-8', errors='replace').read())


def verify():
    """Every quote and every label located in the archived extraction, or generation fails."""
    texts, checks, mismatch = {}, [], []
    for k in LABELS:
        f = os.path.join(LIT, k + '.txt')
        if not os.path.exists(f):
            raise SystemExit(f'archived extraction missing: {os.path.relpath(f, ROOT)}')
        texts[k] = flat(f)

    for p in PAPERS:
        k = p['key']
        if k is None:
            for col in ('b1', 'b2', 'b3'):
                if p[col] != 'UNVERIFIED':
                    raise SystemExit(f'{p["name"]}: an unverified row must carry no content')
                if f'{col}_quote' in p:
                    raise SystemExit(f'{p["name"]}: an unverified row must carry no quote')
            checks.append({'paper': p['name'], 'status': 'unverified', 'quotes_checked': 0})
            continue
        t = texts[k]
        # labels first
        label_pos = {}
        for lab in LABELS[k]:
            i = t.find(lab)
            if i < 0:
                raise SystemExit(f'{p["name"]}: declared section label not in the source: {lab!r}')
            label_pos[lab] = i
        n = 0
        for col in ('b1', 'b2', 'b3'):
            q = p.get(f'{col}_quote')
            if q is None:
                continue
            words = len(q.split())
            if words > MAX_QUOTE_WORDS:
                raise SystemExit(f'{p["name"]} {col}: quote is {words} words, over {MAX_QUOTE_WORDS}')
            pos = t.find(q)
            if pos < 0:
                raise SystemExit(f'{p["name"]} {col}: quote not verbatim in the source: {q!r}')
            # Derive the anchor: the nearest declared label that precedes the quote. If no declared
            # label precedes it, the quote sits in the front matter and the anchor is the Abstract --
            # a structural position, not a string, so it is not searched for verbatim.
            before = [(i, l) for l, i in label_pos.items() if i < pos]
            derived = max(before)[1] if before else 'Abstract'
            lab = p[f'{col}_label']
            if lab != derived:
                mismatch.append(f'{p["name"]} {col}: supplied {lab!r}, derived {derived!r} '
                                f'(quote at {pos}, labels at '
                                + ', '.join(f'{l!r}@{i}' for l, i in sorted(label_pos.items(),
                                                                            key=lambda kv: kv[1]))
                                + ')')
            n += 1
        if p['b3_kind'] == 'estimate' and not p.get('b3_assumption'):
            raise SystemExit(f'{p["name"]}: an estimate must state its assumption')
        if p['b3_kind'] == 'estimate' and 'b3_quote' in p:
            raise SystemExit(f'{p["name"]}: b3 is an estimate and must not also carry a quote')
        checks.append({'paper': p['name'], 'status': 'verified', 'quotes_checked': n,
                       'labels_checked': len(LABELS[k])})
    if mismatch:
        raise SystemExit('the supplied section anchors disagree with what the source shows:\n  '
                         + '\n  '.join(mismatch))
    return checks


def build():
    checks = verify()
    return {'schema': 'catosg-p2-prerequest-review/1',
            'status': 'LITERATURE ONLY. No experiment, no model, no code change. Every quote is '
                      'verified verbatim against a text extracted from the paper\'s own PDF and '
                      'archived under results/lit/',
            'max_quote_words': MAX_QUOTE_WORDS,
            'web_summary_corrections': [
                'the figures "22 MBpf" and "0.98 MBpf" attributed to When2com by a web summariser occur '
                '0 times in its text and were dropped',
                '"quarter" occurs 0 times in When2com; "a quarter of the bandwidth" is Who2com\'s '
                'abstract and is cited there only',
            ],
            'section_label_note': 'section labels are hand-chosen and machine-verified: each must occur '
                                  'verbatim, before its quote, with no other declared label between. '
                                  'Automatic heading detection was tried first and rejected -- on these '
                                  'PDFs it returned "4 Mar" and "3 Abstract" as headings',
            'papers': [{k: v for k, v in p.items()} for p in PAPERS],
            'verification': checks,
            'sources': {k: {'path': os.path.relpath(os.path.join(LIT, k + '.txt'), ROOT),
                            'sha256': sha(os.path.join(LIT, k + '.txt'))} for k in sorted(LABELS)},
            'command': 'python projects/ca_tosg_p2/protocol/prerequest_info_review.py'}


def markdown(m):
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/prerequest_info_review.py -- do not edit by hand -->',
         '# Pre-request decision information in existing methods (P2-R26)', '',
         f"**{m['status']}.**", '',
         f"**Section labels.** {m['section_label_note'][0].upper() + m['section_label_note'][1:]}.", '',
         '**Two corrections to a web summary, recorded so they cannot re-enter as facts.**', '']
    for c in m['web_summary_corrections']:
        L.append(f"* {c[0].upper() + c[1:]}.")
    L += ['', '## The table', '',
          '| method | B-1 what information decides | B-2 whose information | B-3 cost of obtaining it |',
          '|---|---|---|---|']
    for p in m['papers']:
        if p['key'] is None:
            L.append(f"| **{p['name']}** ({p['venue']}) | 未核实 | 未核实 | 未核实 |")
            continue
        cells = []
        for col in ('b1', 'b2', 'b3'):
            q = p.get(f'{col}_quote')
            body = p[col]
            if q:
                note = p.get(f'{col}_label_note')
                anchor = f"*{p[f'{col}_label']}*" + (f" [{note}]" if note else '')
                cells.append(f"“{q}” ({anchor}) — {body}")
            elif p['b3_kind'] == 'estimate' and col == 'b3':
                cells.append(f"**估算** — {body} *Assumption:* {p['b3_assumption']}")
            else:
                cells.append(body)
        L.append(f"| **{p['name']}** ({p['venue']}) | {cells[0]} | {cells[1]} | {cells[2]} |")
    L += ['', '## What each row means for us', '',
          'Factual relations only; no recommendation is drawn here.', '']
    for p in m['papers']:
        L.append(f"* **{p['name']}** — {p['implication']}")
    L += ['', '## Verification', '',
          f"Quotes are at most {m['max_quote_words']} words and are compared after collapsing "
          'whitespace, because PDF extraction breaks lines and hyphenates across them; the quotes are '
          'stored exactly as the extraction renders them, ligatures included.', '',
          '| paper | status | quotes checked | labels checked |', '|---|---|---:|---:|']
    for c in m['verification']:
        L.append(f"| {c['paper']} | {c['status']} | {c['quotes_checked']} | "
                 f"{c.get('labels_checked', 0)} |")
    L += ['', '## Sources', '',
          'Each row is backed by a text extracted from the paper\'s own PDF and archived in the '
          'repository, so a quote can be re-checked without refetching.', '',
          '| paper | archived extraction | sha256 |', '|---|---|---|']
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
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
