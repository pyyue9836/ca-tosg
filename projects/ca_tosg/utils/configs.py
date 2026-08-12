#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""configs/ is a DERIVED VIEW of docs/experiment_protocol.md, never a second source of truth.

The protocol document defines the experiment's intent; a config file is a machine-readable copy
of the part of it a command needs. This module is the only thing allowed to produce configs/*.yaml,
and every value it emits is parsed back out of the protocol -- nothing is retyped here. Each emitted
file carries the md5 of the exact protocol text it was derived from, so drift is detectable rather
than silent.

`tests/test_manifest.py` regenerates all five files and byte-compares them against the committed
ones: if the protocol changes and configs/ is not regenerated (or vice versa), the gate FAILS.

  python projects/ca_tosg/utils/configs.py --write     # regenerate configs/
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
PROTOCOL = os.path.join(ROOT, 'docs/experiment_protocol.md')
CONFIG_DIR = os.path.join(ROOT, 'configs')
MANIFEST = os.path.join(ROOT, 'results/manifests/FROZEN_MANIFEST.json')

BANNER = ('# GENERATED -- do not edit. Derived from docs/experiment_protocol.md by\n'
          '# projects/ca_tosg/utils/configs.py; verified byte-for-byte by tests/test_manifest.py.\n'
          '# The protocol is the single normative source; this file is a view of it.\n')


def _md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def protocol_text():
    return open(PROTOCOL, encoding='utf-8').read()


def json_block(tag, txt=None):
    """Return (parsed, raw_text, md5) for a ```json <TAG> fenced block."""
    txt = txt if txt is not None else protocol_text()
    m = re.search(r'```json %s\s*(\{.*?\})\s*```' % re.escape(tag), txt, re.S)
    if not m:
        raise SystemExit('protocol block %s not found' % tag)
    return json.loads(m.group(1)), m.group(1), _md5(m.group(1))


def section(title, txt=None):
    """Return (raw_text, md5) of one '## <title>' section, up to the next '## '."""
    txt = txt if txt is not None else protocol_text()
    m = re.search(r'(?m)^## %s\s*$(.*?)(?=^## )' % re.escape(title), txt, re.S)
    if not m:
        raise SystemExit('protocol section %r not found' % title)
    return m.group(1), _md5(m.group(1))


# ------------------------------------------------------------------ parsers (protocol -> values)
def channel_grid(sec):
    snr = re.search(r'\*\*SNR grid:\*\*\s*\{([0-9,\s]+)\}\s*dB', sec)
    chans = re.search(r'\*\*Channels:\*\*\s*\{([A-Za-z,\s]+)\}', sec)
    bler = re.search(r'Sionna 5G-LDPC \(k=(\d+), n=(\d+)\) rate-(\d)/(\d) \+ ([\d/]+)-QAM', sec)
    tbl = re.search(r'`(results/[^`]*bler[^`]*\.csv)`', sec)
    col = re.search(r'\(`(bler_\w+)` column\)', sec)
    dep = re.search(r'per-frame SNR ~ U\[(\d+),\s*(\d+)\] dB .* channel ~ Bernoulli\(([0-9.]+) '
                    r'Rayleigh\), (\d+) realisations', sec)
    if not all([snr, chans, bler, tbl, col, dep]):
        raise SystemExit('channel-grid parse failed -- protocol wording changed, fix the parser')
    return dict(
        snr_db=[int(x) for x in snr.group(1).replace(' ', '').split(',')],
        channels=[c.strip().lower() for c in chans.group(1).split(',')],
        ldpc_k=int(bler.group(1)), ldpc_n=int(bler.group(2)),
        code_rate='%s/%s' % (bler.group(3), bler.group(4)),
        modulations=['%s-QAM' % q for q in bler.group(5).split('/')],
        table=tbl.group(1), column=col.group(1),
        deploy_snr_low=int(dep.group(1)), deploy_snr_high=int(dep.group(2)),
        deploy_p_rayleigh=float(dep.group(3)), deploy_realisations=int(dep.group(4)))


def action_set(sec):
    rows = {}
    for a, cost in re.findall(r'\|\s*\*\*([ELF])\*\*\s*\|[^|]*\|\s*B_[ELF]\s*=\s*([0-9.]+)', sec):
        rows[a] = float(cost)
    inf = re.search(r'BLER_F\s*≥\s*([0-9.]+)', sec)
    if len(rows) != 3 or not inf:
        raise SystemExit('action-set parse failed -- protocol table changed, fix the parser')
    return dict(payload_msym=rows, bler_infeasible=float(inf.group(1)))


def sensitivity_items(sec):
    items = []
    for line in sec.splitlines():
        m = re.match(r'\|\s*([0-9]+(?:-var)?)\s*\|\s*([^|(]+)\(`([^`]+)`\)\s*\|', line)
        if m:
            items.append(dict(item=m.group(1).strip(), condition=m.group(2).strip(),
                              output=m.group(3).strip()))
    if not items:
        raise SystemExit('sensitivity-table parse failed -- Appendix B changed, fix the parser')
    return items


# ------------------------------------------------------------------ emitters
def _yaml(obj, indent=0):
    pad = '  ' * indent
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append('%s%s:' % (pad, k))
                out.append(_yaml(v, indent + 1))
            else:
                out.append('%s%s: %s' % (pad, k, _scalar(v)))
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, dict):
                body = _yaml(v, indent + 1).splitlines()
                out.append('%s- %s' % (pad, body[0].strip()))
                out += body[1:]
            else:
                out.append('%s- %s' % (pad, _scalar(v)))
    return '\n'.join(out)


def _scalar(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return v if re.match(r'^[\w./+-]+$', v) else '"%s"' % v
    return repr(v)


def build():
    txt = protocol_text()
    cand, _, cand_md5 = json_block('CATOSG-CANDIDATES', txt)
    ch_sec, ch_md5 = section('3. Channel grid', txt)
    ac_sec, ac_md5 = section('4. Action set S = {E, L, F}', txt)
    appb = re.search(r'(?ms)^## Appendix B — P3 sensitivity expected behaviours.*?(?=^### )', txt)
    if not appb:
        raise SystemExit('Appendix B not found')
    b_sec, b_md5 = appb.group(0), _md5(appb.group(0))

    ch = channel_grid(ch_sec)
    ac = action_set(ac_sec)
    files = {}

    frozen = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {'budgets': {}}
    for b in cand['budgets']:
        tag = 'B%03d' % round(b * 100)
        fz = frozen.get('budgets', {}).get('%.2f' % b, {})
        cfg = {
            'name': 'catosg_%s' % tag.lower(),
            'derived_from': {
                'protocol': 'docs/experiment_protocol.md',
                'candidate_block_md5': cand_md5,
                'action_section_md5': ac_md5,
                'channel_section_md5': ch_md5,
            },
            'budget': {'b_max_msym': b, 'tag': tag},
            'seed': cand['seed'],
            'action_set': {'actions': ['E', 'L', 'F'],
                           'payload_msym': ac['payload_msym'],
                           'bler_infeasible': ac['bler_infeasible']},
            'search_space': {'hyperparameters': cand['hyperparameters'],
                             'class_weight': cand['class_weight'],
                             'lambda_grid': cand['lambda_grid']},
            'loso': cand['loso'],
            'aggregation': cand['aggregation'],
            'selection': cand['selection'],
            'tie_break': cand['tie_break'],
        }
        if fz:
            cfg['frozen'] = {
                'selector': fz.get('selector'), 'candidate_index': fz.get('candidate_index'),
                'walk_depth': fz.get('walk_depth'), 'lambda_star': fz.get('lambda_star'),
                'tau_star': fz.get('tau_star'), 'class_weight': fz.get('class_weight'),
                'hyperparameters': fz.get('hyperparameters'),
                'model_sha256': fz.get('model_sha256'),
                'frozen_validate_payload': fz.get('frozen_validate_payload'),
            }
        files['catosg_%s.yaml' % tag.lower()] = BANNER + _yaml(cfg) + '\n'

    files['phy_ldpc_qam.yaml'] = BANNER + _yaml({
        'name': 'phy_ldpc_qam',
        'derived_from': {'protocol': 'docs/experiment_protocol.md',
                         'channel_section_md5': ch_md5},
        'code': {'family': '5G-LDPC', 'k': ch['ldpc_k'], 'n': ch['ldpc_n'],
                 'rate': ch['code_rate']},
        'modulation': ch['modulations'],
        'snr': {'axis': 'EsN0_dB', 'grid_db': ch['snr_db']},
        'channels': ch['channels'],
        'table': {'path': ch['table'], 'frame_column': ch['column']},
        'deployment_distribution': {
            'snr_db': 'U[%d,%d]' % (ch['deploy_snr_low'], ch['deploy_snr_high']),
            'p_rayleigh': ch['deploy_p_rayleigh'],
            'realisations': ch['deploy_realisations']},
    }) + '\n'

    files['sensitivity.yaml'] = BANNER + _yaml({
        'name': 'sensitivity',
        'derived_from': {'protocol': 'docs/experiment_protocol.md',
                         'appendix_b_md5': b_md5},
        'note': 'Appendix B rows are falsifiable predictions, not targets: a miss is reported, '
                'not fixed.',
        'items': sensitivity_items(b_sec),
    }) + '\n'
    return files


def main():
    files = build()
    if '--write' in sys.argv:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        for name, body in files.items():
            open(os.path.join(CONFIG_DIR, name), 'w', encoding='utf-8').write(body)
            print('wrote configs/%s (%d bytes)' % (name, len(body)))
    else:
        for name, body in files.items():
            p = os.path.join(CONFIG_DIR, name)
            same = os.path.exists(p) and open(p, encoding='utf-8').read() == body
            print('%-24s %s' % (name, 'OK' if same else 'DRIFT'))


if __name__ == '__main__':
    main()
