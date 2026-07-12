#self+ CA-TOSG P1 Step-4 acceptance (i): oracle action distribution by split x channel x SNR.
# -*- coding: utf-8 -*-
"""Sweep the training oracle's action mix over an Es/N0 grid x channel x split, holding the
per-frame cues/F1 fixed and setting every frame to the swept (channel, snr). Recomputes the same
Sionna frame BLER + ego fallback + lam=0 argmax as make_dataset.py. Checks 3 pre-registered
predictions and writes results/step4_oracle_action_dist_v3.csv.

Predictions (from the P1 Step-4 GO):
  P1  Rayleigh -> L ~ 100% at every SNR (Sionna Rayleigh frame BLER = 1 for 16- and 256-QAM).
  P2  AWGN feature-selection concentrated ABOVE the new frame cliff (C activation ~0 at low SNR,
      rising only past the cliff).
  P3  C256 has essentially no feasible window in 0-20 dB (rate-matched 3rd action is starved).
"""
import os
import numpy as np
import pandas as pd

REPO = '/home/josh/cooperative_semantic_perception/OpenCOOD'
P1 = os.path.join(REPO, 'peiyi_work/paper1')
DATA = os.path.join(P1, 'data')
RESULTS = os.path.join(P1, 'results')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
SPLITS = ('validate', 'test', 'culver')
ACTIONS = np.array(['L', 'C16', 'C256'])
SNR_GRID = list(range(0, 25, 2))   # Es/N0 dB; extends past 20 to probe any C256 window


def bler_scalar(snr, tbl, qam, channel):
    s = tbl[(tbl['qam'] == qam) & (tbl['channel'] == channel)].sort_values('esno_db')
    xs = s['esno_db'].to_numpy(); ys = s['bler_frame'].to_numpy()
    return float(np.clip(np.interp(snr, xs, ys, left=1.0, right=float(ys[-1])), 0.0, 1.0))


def main():
    tbl = pd.read_csv(BLER_CSV)
    rows = []
    for sp in SPLITS:
        df = pd.read_csv(os.path.join(DATA, f'dataset_{sp}_v3.csv'))
        late = df['late_f1'].to_numpy(); comp = df['compressed_f1'].to_numpy()
        ego = df['ego_f1'].to_numpy(); n = len(df)
        for ch in ('awgn', 'rayleigh'):
            for snr in SNR_GRID:
                b16 = bler_scalar(snr, tbl, 16, ch)
                b256 = bler_scalar(snr, tbl, 256, ch)
                eff = np.stack([late,
                                comp * (1 - b16) + ego * b16,
                                comp * (1 - b256) + ego * b256], axis=1)
                pick = ACTIONS[eff.argmax(1)]
                rows.append(dict(split=sp, channel=ch, snr_db=snr,
                                 bler_C16=round(b16, 4), bler_C256=round(b256, 4),
                                 frac_L=round(float((pick == 'L').mean()), 4),
                                 frac_C16=round(float((pick == 'C16').mean()), 4),
                                 frac_C256=round(float((pick == 'C256').mean()), 4),
                                 n=n))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RESULTS, 'step4_oracle_action_dist_v3.csv'), index=False)

    # ---- check the 3 predictions ----
    print('wrote results/step4_oracle_action_dist_v3.csv', out.shape)
    ray = out[out.channel == 'rayleigh']
    p1 = float(ray['frac_L'].min())
    print(f'\n[P1] Rayleigh frac_L min over all (split,SNR) = {p1:.4f}  '
          f'(expect ~1.00) -> {"PASS" if p1 > 0.999 else "CHECK"}')

    awgn = out[out.channel == 'awgn']
    print('\n[P2] AWGN C-activation vs SNR (frac_C16+frac_C256), by split:')
    for sp in SPLITS:
        s = awgn[awgn.split == sp].sort_values('snr_db')
        cact = (s['frac_C16'] + s['frac_C256']).to_numpy()
        lo = cact[s['snr_db'].to_numpy() <= 4].max()   # low-SNR C activation
        hi = cact[s['snr_db'].to_numpy() >= 14].max()  # high-SNR C activation
        cliff = s['snr_db'].to_numpy()[np.argmax(cact > 0.01)] if (cact > 0.01).any() else None
        print(f'  {sp:9s} C-active@<=4dB={lo:.3f}  C-active@>=14dB={hi:.3f}  '
              f'first-SNR(C>0.01)={cliff}')

    print('\n[P3] C256 feasibility (max frac_C256 anywhere) by channel:')
    for ch in ('awgn', 'rayleigh'):
        m = out[out.channel == ch]['frac_C256'].max()
        win = out[(out.channel == ch) & (out.frac_C256 > 0.01)]['snr_db'].tolist()
        print(f'  {ch:8s} max frac_C256 = {m:.4f}  window(SNR where >1%) = {win}')


if __name__ == '__main__':
    main()
