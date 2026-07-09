#self+ C: vehicular channel extensions -- Rician fading sweep + CSI channel-aging
"""
Extends the AWGN/Rayleigh study toward vehicular channels.

(1) Rician fading, K in {0 (=Rayleigh), 4, 10 dB, AWGN-limit}: BLER is the AWGN
    BLER averaged over the Rician SNR pdf
      p(g) = ((1+K)/gbar) exp(-K - (1+K)g/gbar) I0( 2 sqrt(K(1+K) g/gbar) ).
    We report, per K and mean SNR, the channel-aware oracle's realised F1, payload,
    and C-activation rate over the test frames. As K grows the selector's knee
    moves from Rayleigh-like (stay at L) to AWGN-like (activate C) -- the framework
    handles the whole fading-severity range without modification.

(2) Channel aging: the selector decides on CSI estimated tau ms earlier; with a
    Jakes model at carrier 5.9 GHz and speed v, the SNR estimate decorrelates, which
    we model as est-SNR error with std sigma(tau,v). We report realised F1 vs CSI
    delay at v = 60 km/h. (Complements the CSI-noise ablation already in the paper.)

Outputs: out/c_rician.csv, out/c_aging.csv, paper/figures/fig_rician.pdf
"""
import os
import numpy as np
import pandas as pd
from scipy.special import i0e
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import _common as C

BLER = pd.read_csv(os.path.join(C.REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv'))


def bler_awgn(snr_db, qam):
    sub = BLER[BLER['qam'] == qam].sort_values('snr_db')
    return np.clip(np.interp(snr_db, sub['snr_db'], sub['bler'], left=1.0, right=0.0), 0, 1)


def bler_rician(gbar_db, qam, Kf, n=600):
    """AWGN BLER averaged over a Rician SNR pdf with linear K-factor Kf, mean gbar."""
    gbar = 10.0 ** (np.atleast_1d(gbar_db).astype(float) / 10.0)
    out = np.zeros(len(gbar))
    gd = np.linspace(-20, 45, n); gl = 10.0 ** (gd / 10.0)
    bl = bler_awgn(gd, qam)
    for i, gb in enumerate(gbar):
        # Rician pdf in linear SNR; i0e for numerical stability (i0e=I0*exp(-|x|))
        x = 2.0 * np.sqrt(Kf * (1 + Kf) * gl / gb)
        pdf = ((1 + Kf) / gb) * np.exp(-Kf - (1 + Kf) * gl / gb + x) * i0e(x)
        jac = gl * np.log(10) / 10.0
        out[i] = np.clip(np.trapz(bl * pdf * jac, gd), 0, 1)
    return out


def oracle_metrics(df, bC16, bC256):
    effL = df['late_f1'].to_numpy()
    cf = df['compressed_f1'].to_numpy()
    eff = np.stack([effL, cf * (1 - bC16), cf * (1 - bC256)], 1)
    payvec = np.array([C.PAYLOAD['L'], C.PAYLOAD['C16'], C.PAYLOAD['C256']])
    act = np.array(C.ACTIONS)[eff.argmax(1)]
    f1 = eff[np.arange(len(df)), eff.argmax(1)].mean()
    pay = np.array([{'L': payvec[0], 'C16': payvec[1], 'C256': payvec[2]}[a] for a in act]).mean()
    cact = float(np.isin(act, ['C16', 'C256']).mean())
    return float(f1), float(pay), cact


def main():
    df = pd.read_csv(C.TEST_CSV)
    snr_grid = np.arange(0, 21, 2.0)
    K_settings = [('Rayleigh (K=0)', 0.0), ('Rician K=4', 10 ** (4 / 10)),
                  ('Rician K=10', 10 ** (10 / 10))]

    # (1) Rician sweep
    rows = []
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    for label, Kf in K_settings:
        cact_curve = []
        for g in snr_grid:
            bC16 = float(bler_rician(g, 16, Kf)[0]) if Kf > 0 else None
            bC256 = float(bler_rician(g, 256, Kf)[0]) if Kf > 0 else None
            if Kf == 0:  # Rayleigh closed-ish via K->0 integral
                bC16 = float(bler_rician(g, 16, 1e-6)[0])
                bC256 = float(bler_rician(g, 256, 1e-6)[0])
            f1, pay, cact = oracle_metrics(df, bC16, bC256)
            cact_curve.append(cact)
            rows.append(dict(channel=label, snr_db=g, bler_C16=round(bC16, 4),
                             oracle_f1=round(f1, 4), oracle_payload=round(pay, 4),
                             C_activation=round(cact, 3)))
        ax.plot(snr_grid, cact_curve, 'o-', ms=3, label=label)
    # AWGN reference
    cact_awgn = []
    for g in snr_grid:
        f1, pay, cact = oracle_metrics(df, float(bler_awgn(g, 16)), float(bler_awgn(g, 256)))
        cact_awgn.append(cact)
        rows.append(dict(channel='AWGN', snr_db=g, bler_C16=round(float(bler_awgn(g, 16)), 4),
                         oracle_f1=round(f1, 4), oracle_payload=round(pay, 4),
                         C_activation=round(cact, 3)))
    ax.plot(snr_grid, cact_awgn, 's--', ms=3, color='k', label='AWGN')
    ax.set_xlabel('mean SNR (dB)'); ax.set_ylabel('feature-level (C) activation rate')
    ax.set_title('Selector C-activation vs fading severity', fontsize=9)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=7)
    fig.tight_layout()
    out = os.path.join(C.FIGDIR, 'fig_rician.pdf')
    fig.savefig(out, bbox_inches='tight')
    fig.savefig(out.replace('.pdf', '_preview.png'), bbox_inches='tight', dpi=140)
    pd.DataFrame(rows).to_csv(os.path.join(C.OUTDIR, 'c_rician.csv'), index=False)
    print('wrote', out)
    print(pd.DataFrame(rows).pivot_table(index='snr_db', columns='channel',
          values='C_activation').round(2).to_string())

    # (2) Channel aging: Jakes decorrelation -> est-SNR error std vs delay at 60 km/h
    fc = 5.9e9; v = 60 / 3.6; fd = v * fc / 3e8  # Doppler ~ 327 Hz
    arows = []
    rf = C.load_rf()
    base_snr = df['est_snr_db'].to_numpy()
    rng = np.random.default_rng(0)
    for tau_ms in [0, 10, 20, 50]:
        # Jakes time correlation J0(2 pi fd tau); aging error std grows with (1-rho)
        from scipy.special import j0
        r = float(j0(2 * np.pi * fd * tau_ms * 1e-3))
        sigma = np.sqrt(max(0.0, 1 - r ** 2)) * 6.0  # scale to dB-domain error (6 dB spread)
        d2 = df.copy()
        d2['est_snr_db'] = base_snr + rng.normal(0, sigma, len(df))
        act = np.asarray(C.rf_predict(rf, d2))         # decide on stale CSI
        _, f1 = C.realised(df, act)                    # evaluate on TRUE channel
        stale = float((act != np.asarray(C.rf_predict(rf, df))).mean())
        arows.append(dict(speed_kmh=60, delay_ms=tau_ms, jakes_rho=round(r, 3),
                          snr_err_std_db=round(sigma, 2), realised_f1=round(f1, 4),
                          stale_decision_rate=round(stale, 3)))
    pd.DataFrame(arows).to_csv(os.path.join(C.OUTDIR, 'c_aging.csv'), index=False)
    print('\n=== channel aging (60 km/h, fd~%.0f Hz) ===' % fd)
    print(pd.DataFrame(arows).to_string())


if __name__ == '__main__':
    main()
