#self+ CA-TOSG P1 Step-4: regenerate 3-way oracle labels (L / C16 / C256) on the canonical v3
# datasets, using the NEW Sionna frame-level BLER table + ego-only failure fallback.
# -*- coding: utf-8 -*-
"""P1 Step-4 dataset finaliser.

Inputs  : data/dataset_{split}_v3.csv  (from recompute_canonical_f1.py -- carries the canonical
          late_f1 / compressed_f1 / ego_f1 columns AND the FROZEN single-draw channel realisation
          est_snr_db / channel_type / channel_is_rayleigh inherited from the v2 dataset).
Action  : overwrite ONLY the physical-layer / label columns of each v3 CSV, in place:
            bler_C16, bler_C256, eff_f1_L, eff_f1_C16, eff_f1_C256, oracle_3way.
          Everything else (cues, canonical F1 columns, the frozen SNR/channel draw) is untouched.

Two P1 changes vs v2 (both flow into the oracle label; neither is a bug -- see PROVENANCE):
  1. BLER SOURCE = Sionna frame-level table results/bler_sionna/bler_sionna.csv, reading the
     `bler_frame` column (= 1-(1-p_cw)^3960, Es/N0 axis) -- NOT the deprecated codeword-level
     ldpc_qam_bler_table.csv (whose codeword BLER, used as if frame-level, was ~3 orders too
     optimistic). est_snr_db is read as Es/N0, identical to true_e2e_global.py.
  2. FAILURE FALLBACK = ego-only. When a requested feature message fails (BLER) the ego keeps ONLY
     its own single-vehicle detection (ego_f1), NOT the object-level L message (which was not
     requested):  eff_f1_C = comp_f1*(1-BLER) + ego_f1*BLER   (v2 used *(1-BLER), i.e. failure->0).

WHY REUSE THE FROZEN DRAW (not redraw): the ONLY controlled changes v2->v3 are {canonical F1,
Sionna BLER, ego fallback}. Redrawing (snr, channel) would confound the label shift with a new
random realisation. So est_snr_db / channel_type / channel_is_rayleigh are read straight from the
v3 CSV and never resampled here.

LAMBDA (pinned, P1 Step-4 requirement 1): the training oracle is the lam=0 channel-state-conditioned
expected-utility argmax -- argmax_a eff_f1_a with NO payload penalty. This is BOTH v2's lambda VALUE
(v2's oracle_3way was also the pure argmax) AND v2's SAME criterion; the two interpretations coincide
at lam=0, so there is nothing to re-tune. The ego fallback + Sionna BLER legitimately MOVE the
resulting operating point (payload); we do NOT re-tune anything to chase v2's 0.0841 payload. The
Lagrangian lambda>0 sweep lives only in the pareto experiment (a1_pareto.py) and is not touched here.

FEASIBILITY MASK (supervisor ruling 2026-07-12, NOT lambda): a request that cannot be delivered is
not a feasible action -- it spends the collaborator's channel-use for zero information (payload is
billed per REQUEST; a failed transmission is not refunded). So when the frame-level BLER of a
feature action is >= BLER_INFEASIBLE (=0.999, i.e. certain failure), that action is removed from the
ORACLE's feasible action set for LABEL GENERATION ONLY. This is a feasible-set CONSTRAINT, not a
preference parameter: it does not move a global operating point and does not reintroduce the lam
degree of freedom we just pinned. It fixes the lam=0 artifact where the payload-blind oracle would
otherwise label a Rayleigh (BLER=1) frame C16 purely to fail into the ego fallback -- forcing the
collaborator to actually emit 0.495 Mbit for a guaranteed-failed decode. The eff_f1_* columns keep
the TRUE effective F1 (comp*(1-BLER)+ego*BLER) so every POLICY evaluation is unchanged (Fixed C16 is
still, correctly, beaten down to ego level under Rayleigh -- that is its job as a baseline); only the
oracle LABEL argmax is masked.
"""
import hashlib
import os

import numpy as np
import pandas as pd

REPO = '/home/josh/cooperative_semantic_perception/OpenCOOD'
P1 = os.path.join(REPO, 'peiyi_work/paper1')
DATA = os.path.join(P1, 'data')
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')  # frame-level, Es/N0

SPLITS = ('validate', 'test', 'culver')
ACTIONS = np.array(['L', 'C16', 'C256'])
BLER_INFEASIBLE = 0.999  # frame BLER >= this => action cannot be delivered => infeasible for the label
# Channel-use-equivalent payload (Mbit); both C variants carry the same 1.98 Mbit perception
# payload but C-256 uses half the symbols (8 vs 4 bits/sym). Kept for the printed sanity report;
# the label itself (lam=0 argmax of eff_f1) does NOT depend on payload.
PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}


def bler_frame_vec(snr_arr, tbl, qam, channel):
    """Frame-level BLER at Es/N0=snr (dB) for a QAM order over a channel, from the Sionna table.
    Mirrors true_e2e_global.bler_frame exactly: interp over esno_db on the `bler_frame` column,
    left-fill=1 (below the table -> certain failure), right-fill = last tabulated value."""
    s = tbl[(tbl['qam'] == qam) & (tbl['channel'] == channel)].sort_values('esno_db')
    xs = s['esno_db'].to_numpy(); ys = s['bler_frame'].to_numpy()
    return np.clip(np.interp(snr_arr, xs, ys, left=1.0, right=float(ys[-1])), 0.0, 1.0)


def main():
    tbl = pd.read_csv(BLER_CSV)
    print('Sionna BLER table:', BLER_CSV, tbl.shape,
          '| reading column: bler_frame (NOT bler_cw)')
    md5s = {}
    for sp in SPLITS:
        path = os.path.join(DATA, f'dataset_{sp}_v3.csv')
        df = pd.read_csv(path)
        snr = df['est_snr_db'].to_numpy()
        is_ray = (df['channel_type'].to_numpy() == 'rayleigh')
        # sanity: the frozen channel_is_rayleigh flag must agree with channel_type
        assert np.array_equal(is_ray.astype(int), df['channel_is_rayleigh'].to_numpy().astype(int)), \
            f'{sp}: channel_type vs channel_is_rayleigh mismatch'

        b16 = np.where(is_ray, bler_frame_vec(snr, tbl, 16, 'rayleigh'),
                       bler_frame_vec(snr, tbl, 16, 'awgn'))
        b256 = np.where(is_ray, bler_frame_vec(snr, tbl, 256, 'rayleigh'),
                        bler_frame_vec(snr, tbl, 256, 'awgn'))
        df['bler_C16'] = b16
        df['bler_C256'] = b256

        comp = df['compressed_f1'].to_numpy(); ego = df['ego_f1'].to_numpy()
        df['eff_f1_L'] = df['late_f1']
        df['eff_f1_C16'] = comp * (1.0 - b16) + ego * b16
        df['eff_f1_C256'] = comp * (1.0 - b256) + ego * b256

        # eff_f1_* columns keep the TRUE eff (used by every policy evaluation). The feasibility mask
        # acts ONLY on the oracle LABEL argmax: an action whose frame BLER >= BLER_INFEASIBLE is a
        # guaranteed-failed request (spends channel-use for zero info) and is removed from the set.
        masked = df[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy().copy()
        n_c16_masked = int((b16 >= BLER_INFEASIBLE).sum())
        n_c256_masked = int((b256 >= BLER_INFEASIBLE).sum())
        masked[b16 >= BLER_INFEASIBLE, 1] = -np.inf
        masked[b256 >= BLER_INFEASIBLE, 2] = -np.inf
        df['oracle_3way'] = ACTIONS[np.argmax(masked, axis=1)]

        df.to_csv(path, index=False)
        md5s[sp] = hashlib.md5(open(path, 'rb').read()).hexdigest()

        rates = {a: float((df['oracle_3way'] == a).mean()) for a in ACTIONS}
        print(f'\n[{sp}] n={len(df)}  oracle base-rate {rates}')
        print(f'  feasibility mask: C16 infeasible on {n_c16_masked}/{len(df)} frames, '
              f'C256 on {n_c256_masked}/{len(df)} (BLER>={BLER_INFEASIBLE})')
        print(f'  mean BLER frame: C16 awgn={b16[~is_ray].mean():.4f} ray={b16[is_ray].mean():.4f} '
              f'| C256 awgn={b256[~is_ray].mean():.4f} ray={b256[is_ray].mean():.4f}')
        print(f'  mean eff_f1  L={df.eff_f1_L.mean():.4f} C16={df.eff_f1_C16.mean():.4f} '
              f'C256={df.eff_f1_C256.mean():.4f}')
        print(f'  md5(dataset_{sp}_v3.csv) = {md5s[sp]}')

    print('\n=== dataset_*_v3.csv md5 (for PROVENANCE) ===')
    for sp in SPLITS:
        print(f'  {sp:9s} {md5s[sp]}')


if __name__ == '__main__':
    main()
