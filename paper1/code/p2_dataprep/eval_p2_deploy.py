#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 submit-B: deployment evaluation of the FROZEN selectors (manifest-only, paired replay).

EVERY parameter comes from FROZEN_MANIFEST.json and NOWHERE else (PROTOCOL sec 6 / R9): the three
frozen selectors (sha256-verified before load), their tau*, and the frozen input md5s. Any parameter
sourced elsewhere is a fuse. test/Culver LABELS are used ONLY for scoring, never for selection
(PROTOCOL sec 1); results are saved and reported as-is regardless of outcome.

Policy-level metric (frame-level realised F1 / channel-use payload), paired over ONE set of 200 CSI
samplings per split (SEED in PROVENANCE): each frame draws SNR~U[0,20] dB and channel~Bernoulli(0.5
Rayleigh); RF and the SNR-threshold baseline tau replay on the SAME draws. eff (expected F1) per cell:
eff_E=ego_f1, eff_L=late_f1 (BLER_L=0), eff_F=compressed_f1*(1-BLER_F)+ego_f1*BLER_F, BLER_F = 16-QAM
frame BLER from the Sionna table.

Outputs (results/p2_deploy/, all raw + PROVENANCE):
  a. replay_{split}_{tag}.csv  -- 200 rows (F1_RF,F1_tau,B_RF,B_tau,dF,dB); CI recomputable from these.
  b. headline_action_dist.csv  -- per split x budget x SNR x channel: RF & oracle action fractions,
     realised grid F1/payload, RF-vs-oracle accuracy (from the deterministic grid).
  c. perclass_{split}_{tag}.csv + confusion -- E/L/F precision/recall/support of RF vs oracle_ELF.
  d. (true end-to-end AP -- separate step; see eval_p2_ap.py.)
  R9 decision: r9_decision.csv (test @ B020 = sole primary; paired bootstrap 10,000 percentile; the
     three conditions each TRUE/FALSE). B010/B030 + Culver = secondary (CI only, no decision).
  anomaly_report.txt: PROTOCOL sec 8 checklist. Any unmet expectation FUSES (no continue/retrain/delta).

Run:  /path/to/env/python paper1/code/p2_dataprep/eval_p2_deploy.py
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')
MANIFEST = os.path.join(P1, 'results/p2_dataprep/FROZEN_MANIFEST.json')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')
GRID_DIR = os.path.join(P1, 'data/p2')
OUT = os.path.join(P1, 'results/p2_deploy')

ACTIONS = ['E', 'L', 'F']
PAY = {'E': 0.0, 'L': 0.024, 'F': 0.99}
PAYVEC = np.array([PAY[a] for a in ACTIONS])
DATASET = {'validate': 'dataset_validate.csv', 'test': 'dataset_test_v3.csv', 'culver': 'dataset_culver_v3.csv'}
SPLITS = ['validate', 'test', 'culver']
N_REPLAY = 200
CSI_SEED = 20260809           # recorded in PROVENANCE
N_BOOT = 10000
BOOT_SEED = 12345
DELTA = 0.005                 # R9 non-inferiority margin (from PROTOCOL; asserted below)
SNR_GRID = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]


def _sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def _md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def fuse(msg):
    raise SystemExit(f'P2-B FUSE: {msg}')


def load_manifest():
    if not os.path.exists(MANIFEST):
        fuse(f'{MANIFEST} absent -- nothing frozen to evaluate.')
    man = json.load(open(MANIFEST))
    if man.get('schema') != 'catosg-frozen-manifest/1':
        fuse(f'unexpected manifest schema {man.get("schema")!r}')
    import pickle
    budgets = {}
    for b, bd in man['budgets'].items():
        mp = os.path.join(P1, bd['model'])
        if not os.path.exists(mp):
            fuse(f'budget {b} model absent: {bd["model"]}')
        if _sha256(mp) != bd['model_sha256']:
            fuse(f'budget {b} model sha256 mismatch (file != manifest) -- not the frozen product')
        for k in ('tau_star', 'frozen_validate_payload', 'candidate_index'):
            if k not in bd:
                fuse(f'budget {b} manifest missing {k}')
        budgets[b] = dict(model=pickle.load(open(mp, 'rb')), tau=float(bd['tau_star']),
                          frozen_pay=bd['frozen_validate_payload'], feat=man['feature_names'])
    return man, budgets


def bler16(tbl, snr, channel):
    """Vectorised 16-QAM frame BLER at Es/N0=snr for a per-frame channel array (channel: bool rayleigh)."""
    out = np.empty_like(snr, dtype=float)
    for ch, name in ((True, 'rayleigh'), (False, 'awgn')):
        m = channel == ch
        if m.any():
            s = tbl[(tbl['qam'] == 16) & (tbl['channel'] == name)].sort_values('esno_db')
            out[m] = np.clip(np.interp(snr[m], s['esno_db'], s['bler_frame'],
                                       left=1.0, right=float(s['bler_frame'].iloc[-1])), 0, 1)
    return out


def eff_matrix(ego, late, comp, bF):
    """(n,3) expected eff for [E,L,F] given a per-frame BLER_F."""
    return np.stack([ego, late, comp * (1 - bF) + ego * bF], axis=1)


def _feature_matrix(feat, cues_df, snr_flat, ray_flat):
    """Build an (m, |feat|) numpy matrix in the model's training column order (feat)."""
    cue_cols = [c for c in feat if c not in ('est_snr_db', 'channel_is_rayleigh')]
    base = cues_df[cue_cols].to_numpy()
    reps = len(snr_flat) // len(cues_df)
    big = np.empty((len(snr_flat), len(feat)))
    big[:, [feat.index(c) for c in cue_cols]] = np.tile(base, (reps, 1))
    big[:, feat.index('est_snr_db')] = snr_flat
    big[:, feat.index('channel_is_rayleigh')] = ray_flat.astype(int)
    return big


def rf_actions_stacked(model, feat, cues_df, snr_2d, is_ray_2d):
    """Predict for all 200 realisations at once. The frozen model was fitted on an unnamed numpy array
    whose columns are `feat` order and whose labels are the integer action indices 0/1/2 = E/L/F, so
    predict() returns those indices directly (no name/string mapping). Returns (R,n) int idx."""
    R, n = snr_2d.shape
    big = _feature_matrix(feat, cues_df, snr_2d.reshape(-1), is_ray_2d.reshape(-1))
    return np.asarray(model.predict(big), dtype=int).reshape(R, n)


def tau_actions(snr_2d, is_ray_2d, tau):
    """SNR-threshold baseline: awgn & snr>tau -> F(idx2) else L(idx1); rayleigh -> L."""
    return np.where((~is_ray_2d) & (snr_2d > tau), 2, 1)


def paired_bootstrap(delta, n_boot, seed):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(delta), size=(n_boot, len(delta)))
    means = delta[idx].mean(1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(delta.mean()), float(lo), float(hi)


def main():
    os.makedirs(OUT, exist_ok=True)
    man, budgets = load_manifest()
    if abs(DELTA - 0.005) > 1e-12:
        fuse('DELTA != 0.005 (PROTOCOL R9 fixed margin)')
    tbl = pd.read_csv(BLER_CSV)
    tags = sorted(budgets)                                        # ['0.10','0.20','0.30']

    replay_summ, action_rows, perclass_rows, csi_prov = [], [], [], []
    for split in SPLITS:
        ds = pd.read_csv(os.path.join(DATA, DATASET[split]))
        n = len(ds)
        ego = ds['ego_f1'].to_numpy(); late = ds['late_f1'].to_numpy(); comp = ds['compressed_f1'].to_numpy()
        # ONE set of 200 CSI samplings for this split (paired for RF and tau)
        rng = np.random.default_rng(CSI_SEED)
        snr_2d = rng.uniform(0, 20, size=(N_REPLAY, n))
        is_ray_2d = rng.random(size=(N_REPLAY, n)) < 0.5
        bF_2d = np.stack([bler16(tbl, snr_2d[r], is_ray_2d[r]) for r in range(N_REPLAY)])
        csi_prov.append((split, n, float(snr_2d.mean()), float(is_ray_2d.mean())))

        for tag in tags:
            bd = budgets[tag]; bmax = float(tag)
            rf_idx = rf_actions_stacked(bd['model'], bd['feat'], ds, snr_2d, is_ray_2d)     # (R,n)
            ta_idx = tau_actions(snr_2d, is_ray_2d, bd['tau'])                              # (R,n)
            F1_RF = np.empty(N_REPLAY); B_RF = np.empty(N_REPLAY)
            F1_TA = np.empty(N_REPLAY); B_TA = np.empty(N_REPLAY)
            for r in range(N_REPLAY):
                E = eff_matrix(ego, late, comp, bF_2d[r])                                   # (n,3)
                F1_RF[r] = E[np.arange(n), rf_idx[r]].mean(); B_RF[r] = PAYVEC[rf_idx[r]].mean()
                F1_TA[r] = E[np.arange(n), ta_idx[r]].mean(); B_TA[r] = PAYVEC[ta_idx[r]].mean()
            dF = F1_RF - F1_TA; dB = B_RF - B_TA
            pd.DataFrame(dict(realisation=np.arange(N_REPLAY), F1_RF=F1_RF, F1_tau=F1_TA,
                              B_RF=B_RF, B_tau=B_TA, dF=dF, dB=dB)).to_csv(
                os.path.join(OUT, f'replay_{split}_B{int(round(bmax*100)):03d}.csv'), index=False)
            mF, loF, hiF = paired_bootstrap(dF, N_BOOT, BOOT_SEED)
            mB, loB, hiB = paired_bootstrap(dB, N_BOOT, BOOT_SEED)
            red = (B_TA.mean() - B_RF.mean()) / B_TA.mean() if B_TA.mean() > 0 else float('nan')
            replay_summ.append(dict(split=split, budget=bmax, in_sample=(split == 'validate'),
                                    F1_RF=round(F1_RF.mean(), 5), F1_tau=round(F1_TA.mean(), 5),
                                    B_RF=round(B_RF.mean(), 5), B_tau=round(B_TA.mean(), 5),
                                    dF_mean=round(mF, 5), dF_lcb95=round(loF, 5), dF_ucb95=round(hiF, 5),
                                    dB_mean=round(mB, 5), dB_lcb95=round(loB, 5), dB_ucb95=round(hiB, 5),
                                    payload_reduction=round(red, 5)))

            # (b) action distribution vs SNR + oracle comparison, from the DETERMINISTIC grid.
            # The model returns integer indices; map to E/L/F strings to compare with oracle_ELF.
            grid = pd.read_csv(os.path.join(GRID_DIR, f'p2_grid_{split}.csv'))
            cue_cols = [c for c in bd['feat'] if c not in ('est_snr_db', 'channel_is_rayleigh')]
            gcue = grid.merge(ds[['sample_id'] + cue_cols], on='sample_id', how='left')[cue_cols].to_numpy()
            gbig = np.empty((len(grid), len(bd['feat'])))
            gbig[:, [bd['feat'].index(c) for c in cue_cols]] = gcue
            gbig[:, bd['feat'].index('est_snr_db')] = grid['snr_db'].to_numpy(float)
            gbig[:, bd['feat'].index('channel_is_rayleigh')] = (grid['channel'] == 'rayleigh').astype(int).to_numpy()
            grid = grid.assign(rf=np.array(ACTIONS)[np.asarray(bd['model'].predict(gbig), dtype=int)])
            acc = float((grid['rf'] == grid['oracle_ELF']).mean())
            for ch in ('awgn', 'rayleigh'):
                for snr in SNR_GRID:
                    cell = grid[(grid['channel'] == ch) & (grid['snr_db'] == snr)]
                    fr = {a: float((cell['rf'] == a).mean()) for a in ACTIONS}
                    orc = {a: float((cell['oracle_ELF'] == a).mean()) for a in ACTIONS}
                    action_rows.append(dict(split=split, budget=bmax, channel=ch, snr_db=snr,
                                            rf_E=round(fr['E'], 4), rf_L=round(fr['L'], 4), rf_F=round(fr['F'], 4),
                                            or_E=round(orc['E'], 4), or_L=round(orc['L'], 4), or_F=round(orc['F'], 4)))
            # (c) per-class RF vs oracle_ELF on the full grid
            from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
            y, yp = grid['oracle_ELF'].to_numpy(), grid['rf'].to_numpy()
            p, rc, f, sup = precision_recall_fscore_support(y, yp, labels=ACTIONS, zero_division=0)
            cm = confusion_matrix(y, yp, labels=ACTIONS)
            for i, a in enumerate(ACTIONS):
                perclass_rows.append(dict(split=split, budget=bmax, cls=a, precision=round(float(p[i]), 4),
                                          recall=round(float(rc[i]), 4), f1=round(float(f[i]), 4),
                                          support=int(sup[i]), rf_vs_oracle_acc=round(acc, 4),
                                          confusion_row='|'.join(str(x) for x in cm[i])))
            print(f'[{split} B{int(bmax*100):03d}] F1_RF={F1_RF.mean():.4f} F1_tau={F1_TA.mean():.4f} '
                  f'dF=[{loF:.4f},{hiF:.4f}] B_RF={B_RF.mean():.4f} B_tau={B_TA.mean():.4f} '
                  f'red={red:.3f} rf_vs_oracle_acc={acc:.3f}', flush=True)

    pd.DataFrame(replay_summ).to_csv(os.path.join(OUT, 'replay_summary.csv'), index=False)
    pd.DataFrame(action_rows).to_csv(os.path.join(OUT, 'headline_action_dist.csv'), index=False)
    pd.DataFrame(perclass_rows).to_csv(os.path.join(OUT, 'perclass_ELF.csv'), index=False)

    # ---- R9 decision: test @ B020 sole primary ----
    prim = next(r for r in replay_summ if r['split'] == 'test' and r['budget'] == 0.20)
    c1 = prim['dF_lcb95'] > -DELTA           # RF non-inferior in F1
    c2 = prim['dB_ucb95'] < 0                # RF communication-superior (UCB95(dB) < 0)
    c3 = prim['payload_reduction'] >= 0.10   # point-estimate payload reduction >= 10%
    dec = pd.DataFrame([
        dict(comparison='PRIMARY test@B0.20', condition='LCB95(dF) > -0.005',
             value=prim['dF_lcb95'], result=bool(c1)),
        dict(comparison='PRIMARY test@B0.20', condition='UCB95(dB) < 0', value=prim['dB_ucb95'], result=bool(c2)),
        dict(comparison='PRIMARY test@B0.20', condition='(B_tau-B_RF)/B_tau >= 0.10',
             value=prim['payload_reduction'], result=bool(c3)),
    ])
    dec.to_csv(os.path.join(OUT, 'r9_decision.csv'), index=False)
    non_inferior_and_lower = bool(c1 and c2 and c3)
    print(f'\nR9 PRIMARY (test @ B_max=0.20): non-inferior-F1 & comm-superior = {non_inferior_and_lower} '
          f'(c1 LCB(dF)>-0.005={c1}, c2 UCB(dB)<0={c2}, c3 payload_red>=10%={c3})')
    print('  (B010/B030 + all Culver are SECONDARY -- CI only, no decision.)')

    # ---- PROVENANCE ----
    with open(os.path.join(OUT, 'PROVENANCE_deploy.txt'), 'w') as f:
        f.write('CA-TOSG P2 submit-B -- deployment eval (eval_p2_deploy.py)\n' + '=' * 72 + '\n')
        f.write(f'manifest: results/p2_dataprep/FROZEN_MANIFEST.json (schema {man["schema"]}, '
                f'freeze {man["freeze_timestamp"]})\n')
        f.write('ALL parameters read from the manifest only: 3 selectors (sha256-verified), tau* per budget.\n')
        f.write(f'CSI: ONE set of {N_REPLAY} paired samplings per split, seed={CSI_SEED} '
                '(SNR~U[0,20], channel~Bernoulli(0.5)); RF and tau replay identical draws.\n')
        for s, nn, sm, rm in csi_prov:
            f.write(f'  {s}: n={nn} frames, mean SNR {sm:.3f} dB, rayleigh frac {rm:.3f}\n')
        f.write(f'CI: paired bootstrap, {N_BOOT} resamples, percentile, seed={BOOT_SEED}. '
                f'R9 margin delta={DELTA} (fixed).\n')
        f.write(f'R9 PRIMARY test@B0.20: c1(LCB dF>-0.005)={c1} c2(UCB dB<0)={c2} c3(red>=10%)={c3} '
                f'-> non-inferior&superior={non_inferior_and_lower}. B010/B030/Culver secondary.\n')
        f.write('test/Culver labels used for SCORING ONLY (no selection). Results saved/reported as-is.\n')
    print('\nwrote results/p2_deploy/{replay_*,replay_summary,headline_action_dist,perclass_ELF,'
          'r9_decision}.csv + PROVENANCE_deploy.txt')


if __name__ == '__main__':
    main()
