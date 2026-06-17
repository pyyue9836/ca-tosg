#self+ Shared helpers for the extra (revision) experiments A2-A8.
"""Single source of truth for payload accounting, the selector feature set
(mirrors train_rf_v2.py 'full' mode), effective-F1 bookkeeping, and policy
realisation. All experiments read the cached per-frame CSVs -- no inference."""
import os
import pickle
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
ROOT = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg')
VAL_CSV = os.path.join(ROOT, 'runs/v2/dataset.csv')
TEST_CSV = os.path.join(ROOT, 'test_split_pipeline/runs/test_dataset.csv')
RF_PKL = os.path.join(ROOT, 'runs/v2/rf_full.pkl')
OUTDIR = os.path.join(ROOT, 'extra_experiments/out')
FIGDIR = os.path.join(ROOT, 'paper/figures')
os.makedirs(OUTDIR, exist_ok=True)

PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}
ACTIONS = ['L', 'C16', 'C256']
SEED = 0

EXCLUDE = {
    'sample_id', 'cav_keys', 'channel_type',
    *[f'{m}_{s}' for m in ['late', 'early', 'intermediate', 'compressed']
      for s in ['num_pred', 'num_gt', 'tp', 'fp', 'fn', 'precision', 'recall',
                'f1', 'payload_Mbit']],
    *[f'{m}_f1_gain_over_late' for m in ['late', 'early', 'intermediate', 'compressed']],
    *[f'{m}_gain_per_extra_Mbit' for m in ['late', 'early', 'intermediate', 'compressed']],
    'best_method_by_f1', 'best_level_by_f1', 'best_f1', 'best_payload_Mbit',
    'bler_C16', 'bler_C256', 'eff_f1_L', 'eff_f1_C16', 'eff_f1_C256', 'oracle_3way',
}


def feat_cols(df, mode='full'):
    cols = [c for c in df.columns if c not in EXCLUDE]
    if mode == 'base':
        cols = [c for c in cols if c not in ('est_snr_db', 'channel_is_rayleigh')]
    elif mode == 'csi':
        cols = [c for c in cols if c != 'channel_is_rayleigh']
    elif mode == 'channel_only':
        cols = [c for c in cols if c in ('est_snr_db', 'channel_is_rayleigh')]
    elif mode == 'perception_only':
        cols = [c for c in cols if c not in ('est_snr_db', 'channel_is_rayleigh')]
    return cols


def eff_matrix(df):
    return df[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy()


def realised(df, actions):
    actions = np.asarray(actions)
    eff = eff_matrix(df)
    idx = np.array([ACTIONS.index(a) for a in actions])
    f1 = eff[np.arange(len(df)), idx].mean()
    pay = np.array([PAYLOAD[a] for a in actions]).mean()
    return float(pay), float(f1)


def lambda_oracle_actions(df, lam):
    eff = eff_matrix(df)
    payvec = np.array([PAYLOAD[a] for a in ACTIONS])
    return np.array(ACTIONS)[(eff - lam * payvec[None, :]).argmax(1)]


def action_ratios(actions):
    actions = np.asarray(actions)
    return {a: float((actions == a).mean()) for a in ACTIONS}


def load_rf():
    with open(RF_PKL, 'rb') as f:
        return pickle.load(f)


def rf_predict(rf, df):
    return rf.predict(df[rf.feature_names_in_])
