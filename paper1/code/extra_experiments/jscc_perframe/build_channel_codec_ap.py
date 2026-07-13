#self+ P1 Step-5 Figure A: channel x codec AP@0.5 vs SNR (9 panels), all vs canonical GT v3.
# Rows = channels {AWGN, Rayleigh, OFDM}; cols = codecs {LDPC-16, LDPC-256, JSCC}. + Fixed-L and
# upper (identity comp) references. LDPC/upper from the FROZEN comp/ego npz (no GPU); JSCC from
# results/jscc_v3/jscc_ap_f1_v3.csv (already scored). Reads only frozen inputs (comp/ego npz + v3 GT +
# BLER tables) -- ZERO dependency on the paper edit map.
"""
LDPC codec AP at (channel, snr): per realisation sample per-frame block success ~ Bernoulli(1-BLER),
mix comp (success) / ego (fail) boxes+scores, global-sort AP vs the canonical union GT; average over
N_SEED realisations. upper = comp AP (identity channel, no BLER). N_SEED small (characterisation figure,
not a CI headline) -- documented. Sends a review table BEFORE any plotting.
Output: results/jscc_v3/channel_codec_ap_v3.csv (long form: channel, codec, snr_db, ap50).
"""
import os, sys, argparse
import numpy as np, pandas as pd, torch
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, *(['..'] * 5)))
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, 'peiyi_work/paper1/code/extra_experiments'))
sys.path.insert(0, HERE)
from opencood.utils import eval_utils
import v3_eval as V
import score_jscc_v3 as SC

P1 = os.path.join(REPO, 'peiyi_work/paper1'); GS = os.path.join(P1, 'gs_rerun'); OUT = os.path.join(P1, 'results/jscc_v3')
SNR_GRID = [0, 4, 8, 12, 16, 20]
N_SEED = 25
THR = 0.5


def tt(a, shp):
    a = np.asarray(a, np.float32); return torch.from_numpy(a) if a.size else torch.zeros(shp, dtype=torch.float32)


def ap_mixed(cb, cs, eb, es, canon, succ):
    """Global-sort AP@0.5: per frame use comp if succ[i] else ego, vs canonical GT."""
    rs = {THR: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    for i in range(len(canon)):
        b, s = (cb[i], cs[i]) if succ[i] else (eb[i], es[i])
        eval_utils.caluclate_tp_fp(tt(b, (0, 8, 3)), tt(s, (0,)), tt(canon[i], (0, 8, 3)), rs, THR)
    return eval_utils.calculate_ap(rs, THR, True)[0]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--split', default='test'); o = ap.parse_args()
    sp = o.split
    co = np.load(f'{GS}/comp_{sp}.npz', allow_pickle=True); eg = np.load(f'{GS}/ego_{sp}.npz', allow_pickle=True)
    cb, cs, canon = list(co['boxes']), list(co['scores']), list(co['gts'])
    eb, es = list(eg['boxes']), list(eg['scores'])
    n = len(canon)
    jscc = pd.read_csv(os.path.join(OUT, 'jscc_ap_f1_v3.csv'))
    rows = []
    # upper (identity comp, no channel) reference; Fixed-L reference = the late-fusion AP (Fig ap_snr)
    upper = ap_mixed(cb, cs, eb, es, canon, np.ones(n, bool))
    print(f'[{sp}] upper (identity comp) AP@0.5 = {upper:.4f}', flush=True)
    for ch in ('awgn', 'rayleigh', 'ofdm'):
        for qam, codec in ((16, 'LDPC-16'), (256, 'LDPC-256')):
            for snr in SNR_GRID:
                b = float(V._bler(snr, qam, ch))
                aps = []
                for s in range(N_SEED):
                    rng = np.random.default_rng(1000 * s + snr)
                    succ = rng.random(n) > b
                    aps.append(ap_mixed(cb, cs, eb, es, canon, succ))
                rows.append(dict(channel=ch, codec=codec, snr_db=snr, ap50=round(float(np.mean(aps)), 4),
                                 ap50_std=round(float(np.std(aps)), 4), bler_frame=round(b, 4)))
                print(f'  {ch:8s} {codec:8s} snr{snr:2d}: AP@.5={np.mean(aps):.4f} (BLER={b:.3f})', flush=True)
        # JSCC panel from the scored table
        js = jscc[(jscc.channel == ch) & (jscc.split == sp)].sort_values('snr_db')
        for _, r in js.iterrows():
            rows.append(dict(channel=ch, codec='JSCC', snr_db=int(r.snr_db), ap50=round(float(r.ap50), 4),
                             ap50_std=0.0, bler_frame=np.nan))
    df = pd.DataFrame(rows)
    df.attrs['upper'] = upper
    df.to_csv(os.path.join(OUT, f'channel_codec_ap_v3_{sp}.csv'), index=False)
    print(f'\nupper(identity comp) AP@.5={upper:.4f}  [Fixed-L / L-branch reference is the late-fusion AP]')
    print('wrote', os.path.join(OUT, f'channel_codec_ap_v3_{sp}.csv'))
    # review pivot (rows=channel, cols=codec) at a few SNRs
    for snr in (0, 8, 16, 20):
        piv = df[df.snr_db == snr].pivot_table(index='channel', columns='codec', values='ap50')
        print(f'\n=== AP@0.5 at {snr} dB (upper={upper:.3f}) ===\n{piv.round(4).to_string()}')


if __name__ == '__main__':
    main()
