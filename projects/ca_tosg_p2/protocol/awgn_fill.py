#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R13 — fill the AWGN gap at 8.5 / 9.0 / 9.5 dB, 16-QAM, rate-1/2 5G-LDPC.

Why: `four_arm_eval.md` A-5 shows the complete F overtakes L on AWGN only when
p_cw < 1.37e-05. The committed table measures 1.3e-04 at 8 dB and has no sample at all between
8 and 10 dB, so the crossing lies in an unsampled interval.

**This measures the channel only.** No perception inference is run, no model is loaded, and no
held-out split is touched.

Rules, pre-registered in `p2_protocol.md` Amendment 3 BEFORE this was run:

  A-1  fixed sample sizes, no early stop: 1,000,000 codewords at each new point, 100,000 at each
       reproduction point. Every point runs to its full N whatever it observes.
  A-2  report k, N, k/N and a two-sided Wilson 95 % interval; when k = 0 additionally report the
       one-sided 95 % upper limit 1 - 0.05^(1/N). The two interval kinds are labelled apart.
  B-1  --check verifies the implementation item by item against ldpc_qam.py.
  B-2  the seed and the software versions are recorded; bit-identical reproduction across
       environments is NOT claimed.
  B-3  8 and 10 dB are re-measured and the difference from the committed values is reported in
       full; a few errors at 10 dB is ordinary variation and does not stop the run.

The physical layer is P1's: this module imports `bler_point` and uses it unmodified, and builds the
encoder / decoder / mapper / demapper / source from the module's own classes and constants. The only
change is to `MAX_CW` and `TARGET_ERR`, which `bler_point` reads from the module globals -- setting
TARGET_ERR beyond reach turns the adaptive loop into a fixed-N loop, which is exactly A-1.

    python awgn_fill.py            # run the measurement (about 86 min, CPU)
    python awgn_fill.py --check    # implementation check + byte-reproduce the report
"""
from __future__ import annotations
import argparse, inspect, json, math, os, platform, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
LDPC_PY = os.path.join(ROOT, 'projects', 'ca_tosg', 'communication', 'ldpc_qam.py')
OUT_DIR = os.path.join(ROOT, 'projects', 'ca_tosg_p2', 'results', 'channel')
CSV = os.path.join(OUT_DIR, 'bler_awgn_fill.csv')
JSN = os.path.join(OUT_DIR, 'bler_awgn_fill.json')
MD = os.path.join(HERE, 'awgn_fill.md')
P1_CSV = os.path.join(ROOT, 'results', 'channel', 'bler_sionna.csv')

QAM, BPS, CHANNEL = 16, 4, 'awgn'
NEW_POINTS = [8.5, 9.0, 9.5]
RECHECK_POINTS = [8.0, 10.0]
N_NEW = 1_000_000
N_RECHECK = 100_000
SEED_BASE = 20260913
Z95 = 1.959963984540054                      # two-sided normal quantile, 95 %
P_THRESHOLD = 1.37e-05                       # from four_arm_eval A-5


# ----------------------------------------------------------------- statistics
def wilson(k, n, z=Z95):
    """Two-sided Wilson score interval for a binomial proportion."""
    if n == 0:
        return (float('nan'), float('nan'))
    c = (k + z * z / 2.0) / (n + z * z)
    h = z / (n + z * z) * math.sqrt(k * (n - k) / n + z * z / 4.0)
    return (max(0.0, c - h), min(1.0, c + h))


def one_sided_upper(n, alpha=0.05):
    """Exact one-sided 95 % upper limit when zero errors are observed: 1 - alpha^(1/n).

    This is the exact Clopper-Pearson form; 3/n is its first-order approximation."""
    return 1.0 - alpha ** (1.0 / n)


# ------------------------------------------------------------- implementation
def load_ldpc():
    sys.path.insert(0, os.path.dirname(LDPC_PY))
    import ldpc_qam                                                  # noqa: E402
    return ldpc_qam


def build_blocks(ldpc):
    """Mirrors sweep_channel's construction, using the module's own classes and constants.

    check_implementation() asserts that the two lines this mirrors are still present verbatim in
    ldpc_qam.sweep_channel, so a change there cannot silently diverge from the fill.
    """
    enc = ldpc.LDPC5GEncoder(ldpc.K, ldpc.N)
    dec = ldpc.LDPC5GDecoder(enc, num_iter=ldpc.NUM_ITER)
    mp = ldpc.Mapper("qam", BPS)
    dmp = ldpc.Demapper("app", "qam", BPS)
    src = ldpc.BinarySource()
    return enc, dec, mp, dmp, src


def check_implementation(ldpc):
    """B-1: coding parameters, modulation, SNR definition, noise normalisation and decoder
    iterations, each checked against ldpc_qam.py rather than against a number typed here."""
    items = []

    def chk(name, got, want, how):
        ok = (got == want) if not isinstance(want, float) else abs(got - want) < 1e-12
        items.append({'item': name, 'value': got, 'expected': want, 'ok': bool(ok), 'source': how})
        if not ok:
            raise SystemExit(f'B-1 implementation check failed: {name}: {got!r} != {want!r}')

    chk('information bits K', ldpc.K, 500, 'ldpc_qam.K')
    chk('codeword length n', ldpc.N, 1000, 'ldpc_qam.N')
    chk('code rate', ldpc.CODERATE, ldpc.K / ldpc.N, 'derived from ldpc_qam.K / ldpc_qam.N')
    chk('decoder iterations', ldpc.NUM_ITER, 20, 'ldpc_qam.NUM_ITER')
    chk('batch size', ldpc.BATCH, 2000, 'ldpc_qam.BATCH')
    chk('bits per symbol', BPS, int(round(math.log2(QAM))), 'log2 of the constellation order')

    # SNR definition and noise normalisation, verified against the physics rather than a literal:
    # the x-axis is Es/N0 with unit symbol energy, so N0 must equal 10^(-EsN0/10) exactly, and the
    # Eb/N0 the module reports must be Es/N0 - 10 log10(R * bps).
    for e in (8.0, 9.5, 10.0):
        no, ebno = ldpc.esno_to_no(e, BPS)
        want_no = 10.0 ** (-e / 10.0)
        want_eb = e - 10.0 * math.log10(ldpc.CODERATE * BPS)
        if abs(no / want_no - 1.0) > 1e-6:
            raise SystemExit(f'B-1 noise normalisation failed at {e} dB: N0={no:g} != {want_no:g}')
        if abs(ebno - want_eb) > 1e-9:
            raise SystemExit(f'B-1 SNR definition failed at {e} dB: Eb/N0={ebno:g} != {want_eb:g}')
    items.append({'item': 'noise normalisation N0 = 10^(-EsN0/10)', 'value': 'verified at 8, 9.5, 10 dB',
                  'expected': 'exact', 'ok': True, 'source': 'ldpc_qam.esno_to_no vs the definition'})
    items.append({'item': 'Es/N0 -> Eb/N0 = Es/N0 - 10log10(R*bps)', 'value': 'verified at 8, 9.5, 10 dB',
                  'expected': 'exact', 'ok': True, 'source': 'ldpc_qam.esno_to_no vs the definition'})

    # the construction this file mirrors, and the AWGN branch it relies on, must be unchanged
    sweep_src = inspect.getsource(ldpc.sweep_channel)
    for needle in ('enc = LDPC5GEncoder(K, N); dec = LDPC5GDecoder(enc, num_iter=NUM_ITER)',
                   'mp = Mapper("qam", bps); dmp = Demapper("app", "qam", bps); src = BinarySource()'):
        if needle not in sweep_src:
            raise SystemExit(f'B-1: ldpc_qam.sweep_channel no longer contains: {needle}')
    point_src = inspect.getsource(ldpc.bler_point)
    for needle in ('y = AWGN()(x, no); llr = dmp(y, no)',
                   'while n_cw < MAX_CW and n_err < TARGET_ERR:',
                   'b = src([BATCH, K]); c = enc(b); x = mp(c)'):
        if needle not in point_src:
            raise SystemExit(f'B-1: ldpc_qam.bler_point no longer contains: {needle}')
    items.append({'item': 'encoder/decoder/mapper construction', 'value': 'verbatim match',
                  'expected': 'verbatim match', 'ok': True,
                  'source': 'inspect.getsource(ldpc_qam.sweep_channel)'})
    items.append({'item': 'AWGN branch and fixed-N loop', 'value': 'verbatim match',
                  'expected': 'verbatim match', 'ok': True,
                  'source': 'inspect.getsource(ldpc_qam.bler_point)'})
    return items


def versions(ldpc):
    import importlib.metadata as md
    v = {'python': platform.python_version()}
    for pkg in ('tensorflow', 'sionna', 'numpy'):
        try:
            v[pkg] = md.version(pkg)
        except Exception:
            v[pkg] = 'unknown'
    v['platform'] = platform.platform()
    v['cpu_count'] = os.cpu_count()
    return v


# ------------------------------------------------------------------ the run
def committed_rows():
    """The committed AWGN 16-QAM points at 8 and 10 dB, read from P1's table (never modified)."""
    import pandas as pd
    d = pd.read_csv(P1_CSV)
    d = d[(d['qam'] == QAM) & (d['channel'] == CHANNEL)]
    out = {}
    for e in RECHECK_POINTS:
        r = d[abs(d['esno_db'] - e) < 1e-9]
        if len(r) == 1:
            r = r.iloc[0]
            out[e] = {'bler_cw': float(r['bler_cw']), 'n_cw': int(r['n_cw']), 'n_err': int(r['n_err'])}
    return out


def measure(ldpc, esno, n_target, log):
    import tensorflow as tf
    seed = SEED_BASE + int(round(esno * 10))
    tf.random.set_seed(seed)
    # A-1: fixed N, no early stop. bler_point reads both from the module globals.
    ldpc.MAX_CW = n_target
    ldpc.TARGET_ERR = 1 << 62
    enc, dec, mp, dmp, src = build_blocks(ldpc)
    t0 = time.time()
    p, n_cw, n_err, ebno = ldpc.bler_point(esno, BPS, CHANNEL, enc, dec, mp, dmp, src)
    dt = time.time() - t0
    lo, hi = wilson(n_err, n_cw)
    row = {'qam': QAM, 'channel': CHANNEL, 'esno_db': esno, 'ebno_db': round(ebno, 4),
           'n_cw': n_cw, 'n_err': n_err, 'p_hat': n_err / n_cw,
           'wilson95_lo': lo, 'wilson95_hi': hi,
           'zero_error': n_err == 0,
           'one_sided_upper95': one_sided_upper(n_cw) if n_err == 0 else None,
           'seed': seed, 'seconds': dt}
    msg = (f'  Es/N0={esno:5.2f} dB  k={n_err:6d}  N={n_cw:9d}  p_hat={row["p_hat"]:.3e}  '
           f'Wilson95=[{lo:.3e}, {hi:.3e}]'
           + (f'  one-sided upper={row["one_sided_upper95"]:.3e}' if n_err == 0 else '')
           + f'  [{dt/60:.1f} min]')
    print(msg, flush=True)
    log.append(msg)
    return row


def run():
    ldpc = load_ldpc()
    items = check_implementation(ldpc)
    os.makedirs(OUT_DIR, exist_ok=True)
    print('B-1 implementation check: all items match ldpc_qam.py', flush=True)
    log, rows = [], []
    t0 = time.time()
    for e in RECHECK_POINTS:
        rows.append(measure(ldpc, e, N_RECHECK, log))
    for e in NEW_POINTS:
        rows.append(measure(ldpc, e, N_NEW, log))
    total_min = (time.time() - t0) / 60.0
    data = {'schema': 'catosg-p2-awgn-fill/1',
            'what': 'Channel measurement only. No perception inference, no model, no held-out split.',
            'registered_in': 'projects/ca_tosg_p2/protocol/p2_protocol.md, Amendment 3 (P2-R13)',
            'config': {'qam': QAM, 'bits_per_symbol': BPS, 'channel': CHANNEL,
                       'K': ldpc.K, 'n': ldpc.N, 'coderate': ldpc.CODERATE,
                       'num_iter': ldpc.NUM_ITER, 'batch': ldpc.BATCH,
                       'n_new_points': N_NEW, 'n_recheck_points': N_RECHECK,
                       'early_stop': False, 'seed_base': SEED_BASE},
            'implementation_check': items,
            'versions': versions(ldpc),
            'rows': sorted(rows, key=lambda r: r['esno_db']),
            'committed_reference': committed_rows(),
            'p_threshold': P_THRESHOLD,
            'wall_minutes': total_min}
    json.dump(data, open(JSN, 'w'), indent=1)
    import pandas as pd
    pd.DataFrame(data['rows']).to_csv(CSV, index=False)
    open(MD, 'w').write(render(data))
    print(f'\nwrote {os.path.relpath(CSV, ROOT)}, {os.path.relpath(JSN, ROOT)}, '
          f'{os.path.relpath(MD, ROOT)}  [{total_min:.1f} min total]')
    return 0


# -------------------------------------------------------------------- report
def fmt_p(r):
    if r['n_err'] == 0:
        return 'no error observed'
    return f'{r["p_hat"]:.3e}'


def verdict(r, thr=P_THRESHOLD):
    """D-1: the point supports L, supports the complete F, or does not distinguish.

    Decided by where the threshold sits relative to the two-sided Wilson interval -- the interval,
    not the point estimate, because the point estimate carries no uncertainty. A zero-error point is
    judged by its one-sided upper limit."""
    if r['n_err'] == 0:
        u = r['one_sided_upper95']
        return ('supports complete F' if u < thr else 'not distinguishable',
                f'zero errors; one-sided 95 % upper limit {u:.3e} '
                f'{"<" if u < thr else ">="} threshold {thr:.3e}')
    lo, hi = r['wilson95_lo'], r['wilson95_hi']
    if lo > thr:
        return ('supports L', f'Wilson interval lies entirely above the threshold {thr:.3e}')
    if hi < thr:
        return ('supports complete F', f'Wilson interval lies entirely below the threshold {thr:.3e}')
    return ('not distinguishable', f'Wilson interval straddles the threshold {thr:.3e}')


def render(d):
    o = []
    w = o.append
    w('# AWGN 8.5 / 9.0 / 9.5 dB — measured (P2-R13)')
    w('')
    w('**Generated by `awgn_fill.py`. Do not edit by hand; `--check` byte-compares this file.**')
    w('')
    w('Channel measurement only: no perception inference was run, no model was loaded and no')
    w('held-out split was touched. The rules below were registered in `p2_protocol.md`')
    w('(Amendment 3, P2-R13) **before** the measurement started.')
    w('')
    c = d['config']
    w(f'Rate-{c["K"]}/{c["n"]} 5G-LDPC (R = {c["coderate"]:.1f}), {c["qam"]}-QAM, {c["channel"].upper()}, '
      f'{c["num_iter"]} decoder iterations, batch {c["batch"]}, CPU only.')
    w(f'Fixed sample sizes with **no early stop**: {c["n_new_points"]:,} codewords at each new point, '
      f'{c["n_recheck_points"]:,} at each reproduction point.')
    w(f'Total wall time {d["wall_minutes"]:.1f} min.')
    w('')
    w('## Measured points')
    w('')
    w('| Es/N0 (dB) | errors k | codewords N | k/N | two-sided Wilson 95 % | one-sided 95 % upper (k = 0 only) |')
    w('|---:|---:|---:|---:|---|---|')
    for r in d['rows']:
        up = f'{r["one_sided_upper95"]:.3e}' if r['n_err'] == 0 else '—'
        w(f'| {r["esno_db"]:.1f} | {r["n_err"]:,} | {r["n_cw"]:,} | {fmt_p(r)} | '
          f'[{r["wilson95_lo"]:.3e}, {r["wilson95_hi"]:.3e}] | {up} |')
    w('')
    w('The two interval kinds are different quantities and are kept in different columns: the Wilson')
    w('column is a two-sided interval for the observed proportion; the last column is a one-sided 95 %')
    w('upper limit `1 - 0.05^(1/N)`, quoted only where no error was observed. **No point is reported as')
    w('`p_cw = 0`.**')
    w('')
    w('## Reproduction check at 8 and 10 dB (B-3)')
    w('')
    w('Reported in full, not used as a gate. A small number of errors at 10 dB is ordinary sampling')
    w('variation: the committed value there is itself zero errors in 100,000 codewords, which bounds')
    w('the rate but does not assert it is zero.')
    w('')
    w('| Es/N0 (dB) | committed k/N | committed bler_cw | new k/N | new estimate | consistent? |')
    w('|---:|---|---|---|---|---|')
    for e in sorted(d['committed_reference']):
        cr = d['committed_reference'][e]
        nr = next(r for r in d['rows'] if abs(r['esno_db'] - e) < 1e-9)
        lo, hi = nr['wilson95_lo'], nr['wilson95_hi']
        cons = 'yes' if lo <= cr['bler_cw'] <= hi else 'the committed value lies outside the new interval'
        w(f'| {e:.1f} | {cr["n_err"]:,}/{cr["n_cw"]:,} | {cr["bler_cw"]:.3e} | '
          f'{nr["n_err"]:,}/{nr["n_cw"]:,} | {fmt_p(nr)} | {cons} |')
    w('')
    w('Bit-identical reproduction is **not** claimed: `ldpc_qam.py` sets no seed of its own, so the')
    w('committed run cannot be replayed. This run fixes its own seeds and records them, which makes')
    w('*this* measurement replayable in *this* environment.')
    w('')
    w('## Per-point verdict (D-1)')
    w('')
    w(f'The complete F overtakes L on AWGN only when `p_cw < {d["p_threshold"]:.2e}`')
    w('(`four_arm_eval.md` A-5). That threshold is an **average-performance crossing estimate under the')
    w('current data, scene weights and message model** — not a per-frame reliability rule and not a')
    w('link-layer requirement. Each point is judged by its interval, not by its point estimate.')
    w('')
    w('| Es/N0 (dB) | verdict | basis |')
    w('|---:|---|---|')
    for r in d['rows']:
        v, why = verdict(r, d['p_threshold'])
        w(f'| {r["esno_db"]:.1f} | **{v}** | {why} |')
    w('')
    w('## Configuration, seeds and versions (B-1, B-2)')
    w('')
    w('| item | value | checked against |')
    w('|---|---|---|')
    for it in d['implementation_check']:
        w(f'| {it["item"]} | {it["value"]} | {it["source"]} |')
    w('')
    w('| point (dB) | seed |')
    w('|---:|---:|')
    for r in d['rows']:
        w(f'| {r["esno_db"]:.1f} | {r["seed"]} |')
    w('')
    v = d['versions']
    w('Software: ' + ', '.join(f'{k} {v[k]}' for k in ('python', 'tensorflow', 'sionna', 'numpy')) + '.')
    w(f'Platform: {v["platform"]}, {v["cpu_count"]} CPUs visible, GPU disabled by `ldpc_qam.py`')
    w('(TensorFlow has no sm_120 kernels for this card).')
    w('')
    w('`bler_frame` is deliberately absent: `ldpc_qam.py` computes it with N_CW = 3960 from the retired')
    w('1.98 Mbit budget, and the message here spans 12,567 codewords. `q_F` is computed from `bler_cw`.')
    w('')
    return '\n'.join(o) + '\n'


def check():
    ldpc = load_ldpc()
    check_implementation(ldpc)
    print('B-1 implementation check: all items match ldpc_qam.py')
    if not os.path.exists(JSN):
        print('no measurement present yet (%s absent) — nothing to byte-compare'
              % os.path.relpath(JSN, ROOT))
        return 0
    d = json.load(open(JSN))
    if render(d) != open(MD).read():
        raise SystemExit('awgn_fill.md does not match the measurement JSON')
    print('awgn fill: reproduced')
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    sys.exit(check() if a.check else run())
