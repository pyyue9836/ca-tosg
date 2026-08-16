#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P5-7 (E) item 18: in-figure vs caption vs body text, three-way.

The figure generators record every number they actually plotted into
`results/provenance/PROVENANCE_figures.json`. This checker takes each of those numbers and asks
where it appears in `paper/main.tex` -- inside a figure/table environment (the caption side) and
outside one (the body side).

It **reports**; it does not choose. A number drawn but absent from both caption and body is listed,
a number present in one and not the other is listed, and a near-miss (the same value at a
neighbouring rounding) is listed as a near-miss rather than silently accepted. Deciding which of
the three is wrong is a human call, and this tool deliberately does not make it.

    python tools/check_figure_consistency.py
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, 'paper', 'main.tex')
PROV = os.path.join(ROOT, 'results', 'provenance', 'PROVENANCE_figures.json')

# numbers that are axis furniture or shared constants, not claims to be cross-checked
SKIP_KEYS = ('knee_db',)


def split_caption_body(tex):
    """Return (caption_text, body_text): everything inside \\caption{...} vs everything else."""
    caps, body, i = [], [], 0
    for m in re.finditer(r'\\caption\{', tex):
        start = m.end()
        depth, j = 1, start
        while j < len(tex) and depth:
            if tex[j] == '{':
                depth += 1
            elif tex[j] == '}':
                depth -= 1
            j += 1
        caps.append(tex[start:j - 1])
        body.append(tex[i:m.start()])
        i = j
    body.append(tex[i:])
    return '\n'.join(caps), '\n'.join(body)


def appears(value, text):
    """Does `value` appear as a printed number at its OWN precision, or rounded by one digit?

    Degrading further would make almost anything match: 0.9244 truncated to "0.9" appears on nearly
    every page, and an earlier version of this check reported exactly that as a hit. Only the value
    as stored and one digit coarser are tried, and a literal shorter than three significant digits
    is refused outright.
    """
    exact = ('%f' % value).rstrip('0').rstrip('.')
    dec = len(exact.split('.')[1]) if '.' in exact else 0
    lits = [exact]                      # the exact literal is specific by construction
    if dec >= 1:                        # the COARSENED one is what can collide, so gate that
        coarse = f'{value:.{dec - 1}f}'
        if len(coarse.lstrip('-0.').replace('.', '')) >= 3:
            lits.append(coarse)
    for lit in lits:
        if re.search(r'(?<![\d.])' + re.escape(lit) + r'(?![\d])', text):
            return lit
    # FINER direction: the provenance file stores 4 dp while the tables print 5, so 0.9033 was
    # reported as "nowhere" although the body states 0.90326 -- the same number, printed more
    # precisely. A finer literal counts only if it ROUNDS BACK to the stored value at the stored
    # precision, which cannot make a coarser (collision-prone) match, only a stricter one.
    if dec >= 1:
        for m in re.finditer(r'(?<![\d.])(-?\d+\.\d{%d,})(?![\d])' % (dec + 1), text):
            if f'{float(m.group(1)):.{dec}f}' == f'{value:.{dec}f}':
                return m.group(1)
    return None


SENT_SPLIT = re.compile(r'(?<=[.;:])\s+')


def sentences_with(text, lit):
    """Every sentence-ish window of `text` in which the literal appears."""
    out = []
    for m in re.finditer(r'(?<![\d.])' + re.escape(lit) + r'(?![\d])', text):
        a = text.rfind('.', max(0, m.start() - 700), m.start())
        b = text.find('.', m.end())
        out.append(text[(a + 1 if a >= 0 else max(0, m.start() - 700)):
                        (b if b >= 0 else min(len(text), m.end() + 700))])
    return out


def conditions_of(window):
    """Condition markers a sentence pins down. Absent == unconstrained, not 'wrong'."""
    c = {}
    # SET semantics, as already used for SNR below: a sentence that names TWO splits (or two
    # channels) does not pin either one -- it is unconstrained on that axis. The previous elif chain
    # silently resolved "under Rayleigh and for AWGN SNR <= 8 dB" to Rayleigh alone and reported the
    # AWGN-drawn payload as a condition mismatch. Naming more conditions must never make a sentence
    # match a NARROWER set than naming none, so this only ever relaxes ambiguous sentences.
    splits = {k for k, rx in (('validate', r'\bvalidate\b'), ('culver', r'Culver'),
                              ('test', r'\btest\b')) if re.search(rx, window, re.I)}
    if len(splits) == 1:
        c['split'] = splits.pop()
    m = re.search(r'B_\{?\\max\}?\s*\{?=?\}?\s*([0-9.]+)', window)
    if m:
        c['budget'] = float(m.group(1))
    chans = {k for k, rx in (('rayleigh', r'Rayleigh'), ('awgn', r'AWGN'))
             if re.search(rx, window, re.I)}
    if len(chans) == 1:
        c['channel'] = chans.pop()
    snrs = {float(x) for x in re.findall(r'\$?([0-9]{1,2})\$?~?\s*dB', window)}
    if len(snrs) == 1:
        c['snr_db'] = snrs.pop()
    return c


def compatible(tags, window):
    """True unless the sentence pins a condition to something DIFFERENT from the drawn one."""
    got = conditions_of(window)
    for k, v in got.items():
        t = tags.get(k)
        if t is None:
            continue
        if k == 'snr_db':
            # an SNR named in the sentence must be the one the number was drawn at
            if abs(float(t) - float(v)) > 1e-9:
                return False
        elif str(t) != str(v):
            return False
    return True


def main() -> int:
    if not os.path.exists(PROV):
        print(f'{PROV} absent -- run tools/generate_figures.py first')
        return 1
    prov = json.load(open(PROV))
    tex = open(MAIN, encoding='utf-8').read()
    caption, body = split_caption_body(tex)

    rows, missing_both, one_sided, wrong_condition = [], [], [], []
    for key, item in sorted(prov['numbers_drawn'].items()):
        if key in SKIP_KEYS:
            continue
        val = item['value'] if isinstance(item, dict) else item
        tags = {k: item.get(k) for k in ('split', 'budget', 'channel', 'snr_db')} \
            if isinstance(item, dict) else {}
        c = b = None
        for side, text in (('c', caption), ('b', body)):
            lit = appears(val, text)
            if lit is None:
                continue
            wins = sentences_with(text, lit)
            ok = [w for w in wins if compatible(tags, w)]
            if ok:
                if side == 'c':
                    c = lit
                else:
                    b = lit
            elif wins:
                wrong_condition.append((key, val, tags, 'caption' if side == 'c' else 'body'))
        rows.append((key, val, c, b))
        if c is None and b is None:
            missing_both.append((key, val))
        elif (c is None) != (b is None):
            one_sided.append((key, val, 'caption only' if b is None else 'body only'))

    w = max(len(r[0]) for r in rows)
    print('=' * (w + 46))
    print(f'{"drawn number".ljust(w)}  {"value":>9}  {"in caption":>11}  {"in body":>9}')
    print('-' * (w + 46))
    for key, val, c, b in rows:
        print(f'{key.ljust(w)}  {val:>9}  {str(c or "-"):>11}  {str(b or "-"):>9}')
    print('=' * (w + 46))

    print(f'\ndrawn and quoted on BOTH sides   : {sum(1 for _k,_v,c,b in rows if c and b)}')
    print(f'value present but at a DIFFERENT condition: {len(wrong_condition)}')
    print(f'drawn and quoted on ONE side     : {len(one_sided)}')
    print(f'drawn but quoted NOWHERE         : {len(missing_both)}')
    if one_sided:
        print('\nONE-SIDED (a figure number that the caption or the body states, but not both).')
        print('Not necessarily an error -- a number may legitimately live only in a caption.')
        for key, val, where in one_sided:
            print(f'  {key:38s} {val:>9}   {where}')
    if missing_both:
        print('\nDRAWN BUT NEVER STATED (the figure shows it; no caption or sentence does).')
        for key, val in missing_both:
            print(f'  {key:38s} {val:>9}')
    if wrong_condition:
        print('\nSAME VALUE, DIFFERENT CONDITION (the literal occurs, but only in a sentence that '
              'pins a different split/budget/channel/SNR -- not counted as a match):')
        for key, val, tags, side in wrong_condition:
            t = ' '.join(f'{k}={v}' for k, v in tags.items() if v is not None)
            print(f'  {key:38s} {val:>9}  drawn at [{t}]  ({side})')
    print('\nMatching is CONDITION-AWARE: a number counts as quoted only in a sentence whose '
          'stated split / budget / channel / SNR does not contradict the one it was drawn at, so '
          '0.9244 at 20 dB and 0.9243 at 10 dB are no longer a conflict.')
    print('This tool REPORTS. It does not decide which of figure / caption / body is right.')

    out = os.path.join(ROOT, 'docs', 'figure_text_consistency.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# Figure / caption / body consistency — POST-EXPERIMENT list\n\n')
        f.write('**POST-EXPERIMENT.** Generated by `python tools/check_figure_consistency.py` from '
                '`results/provenance/PROVENANCE_figures.json`. Nothing here has been acted on: the '
                'prose was deliberately not edited in the batch that produced this list. Each row '
                'is a decision for Peiyi, not a defect the tool resolved.\n\n')
        f.write('Matching is condition-aware: a drawn number counts as quoted only inside a '
                'sentence whose stated split / budget / channel / SNR does not contradict the '
                'condition it was drawn at.\n\n')
        f.write(f'| state | count |\n|---|---|\n'
                f'| quoted on both sides | {sum(1 for _k,_v,c,b in rows if c and b)} |\n'
                f'| quoted on one side only | {len(one_sided)} |\n'
                f'| drawn but never stated | {len(missing_both)} |\n'
                f'| same value, different condition | {len(wrong_condition)} |\n\n')
        f.write('## Quoted on one side only\n\n| drawn number | value | where |\n|---|---|---|\n')
        for key, val, where in one_sided:
            f.write(f'| `{key}` | {val} | {where} |\n')
        f.write('\n## Drawn but never stated\n\n| drawn number | value | condition |\n|---|---|---|\n')
        for key, val in missing_both:
            it = prov['numbers_drawn'][key]
            t = ' '.join(f'{k}={it[k]}' for k in ('split','budget','channel','snr_db')
                         if isinstance(it, dict) and it.get(k) is not None)
            f.write(f'| `{key}` | {val} | {t} |\n')
        f.write('\n## Same value, different condition\n\n'
                '| drawn number | value | drawn at | side |\n|---|---|---|---|\n')
        for key, val, tags, side in wrong_condition:
            t = ' '.join(f'{k}={v}' for k, v in tags.items() if v is not None)
            f.write(f'| `{key}` | {val} | {t} | {side} |\n')
    print(f'\nwrote {os.path.relpath(out, ROOT)} (POST-EXPERIMENT, not acted on)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
