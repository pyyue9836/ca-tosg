#self+ Test-split pipeline 04: apply rf_full (trained on validate) to the OPV2V test split; report held-out generalisation results — accuracy vs oracle, realised F1, average payload
"""
Loads the deployed selector rf_full.pkl (trained on validate-split 70/30) and
runs it on test_dataset.csv (full test split, never seen during training).
This is the genuine held-out generalisation test for the paper.

Output: runs/test_rf_results.csv  +  runs/test_snr_sweep.csv
"""
import os
import sys
import pickle
import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

# read the channel-use payloads from the single canonical source (projects/ca_tosg/evaluation/ablations/_common.py)
# instead of the old uncoded literal 1.98/4, 1.98/8 (=0.495/0.2475, wrong for the rate-1/2 chain).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'extra_experiments'))

RUNS = 'runs' if 'culver' not in os.environ.get('CATOSG_SPLIT', 'test') else 'runs_culver'
DATASET = os.path.join(REPO,
    f'peiyi_work/01_paper_ca_tosg/test_split_pipeline/{RUNS}/test_dataset.csv')
RF_PATH = os.path.join(REPO,
    'peiyi_work/01_paper_ca_tosg/runs/v2/rf_full.pkl')
# SUPERSEDED (P1, 2026-08): consumes the DEPRECATED codeword-level ldpc_qam_bler_table.csv and the
# RETIRED v2 selector (runs/v2/rf_full.pkl). NOT a source of any frozen paper number -- the held-out
# test-split policy numbers now come from policy_200seed.py (bler_sionna frame-level).
# Do not rerun for paper values; P2 regenerates under docs/experiment_protocol.md. NOT repointed to bler_sionna:
# incompatible schema would break this codeword-level loader.
BLER_CSV = os.path.join(REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT_DIR = os.path.join(REPO,
    f'peiyi_work/01_paper_ca_tosg/test_split_pipeline/{RUNS}')

# --- ca-tosg layout bootstrap (restructure commit 2/4) ---
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/evaluation/ablations', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
# --- end bootstrap ---
from _common import PAYLOAD  # {'L':0.024,'C16':0.99,'C256':0.495} -- rate-1/2 coded channel-use (Msym)
SNR_GRID = np.array([0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20], dtype=float)
ACTIONS = ['L', 'C16', 'C256']


def realised(df, actions):
    actions = np.asarray(actions)
    f1 = np.choose(
        (actions == 'C256').astype(int) * 2 + (actions == 'C16').astype(int),
        [df['eff_f1_L'].to_numpy(), df['eff_f1_C16'].to_numpy(),
         df['eff_f1_C256'].to_numpy()])
    pay = np.zeros_like(f1)
    for a in PAYLOAD: pay[actions == a] = PAYLOAD[a]
    return float(pay.mean()), float(f1.mean())


def bler_awgn(snr, df, qam):
    s = df[df['qam'] == qam].sort_values('snr_db')
    return float(np.clip(np.interp(snr, s['snr_db'], s['bler'],
                                    left=1.0, right=0.0), 0.0, 1.0))


def bler_rayleigh(snr_mean, df, qam):
    s = df[df['qam'] == qam].sort_values('snr_db')
    xs = s['snr_db'].to_numpy(); ys = s['bler'].to_numpy()
    gb = 10.0 ** (snr_mean / 10.0)
    g_db = np.linspace(-15.0, 40.0, 400)
    g_lin = 10.0 ** (g_db / 10.0)
    bler_g = np.clip(np.interp(g_db, xs, ys, left=1.0, right=0.0), 0.0, 1.0)
    pdf = (1.0 / gb) * np.exp(-g_lin / gb)
    jac = g_lin * np.log(10) / 10.0
    return float(np.clip(np.trapz(bler_g * pdf * jac, g_db), 0.0, 1.0))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATASET)
    bler_df = pd.read_csv(BLER_CSV)
    with open(RF_PATH, 'rb') as f: rf = pickle.load(f)
    feat_cols = list(rf.feature_names_in_)
    print(f'test split: {df.shape}  RF feats: {len(feat_cols)}')

    # --- Headline result (random per-frame SNR + channel) ---
    actions = rf.predict(df[feat_cols])
    accuracy = float((actions == df['oracle_3way'].to_numpy()).mean())
    pay, f1 = realised(df, actions)
    # Reference policies
    or_pay, or_f1 = realised(df, df['oracle_3way'].to_numpy())
    rows = [
        {'policy': 'oracle_3way', 'accuracy': 1.0, 'mean_payload': or_pay,
         'mean_f1': or_f1},
        {'policy': 'rf_full_on_test', 'accuracy': accuracy,
         'mean_payload': pay, 'mean_f1': f1},
    ]
    for a in ('L', 'C16', 'C256'):
        pred = np.array([a] * len(df))
        p, f = realised(df, pred)
        rows.append({'policy': f'fixed_{a}',
                     'accuracy': float((df['oracle_3way'] == a).mean()),
                     'mean_payload': p, 'mean_f1': f})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT_DIR, 'test_rf_results.csv'), index=False)
    print('\n=== TEST SPLIT HELD-OUT RESULTS ===')
    print(out.to_string(index=False))

    # --- SNR sweep (per-channel) ---
    sweep_rows = []
    for ch in ('awgn', 'rayleigh'):
        for snr in SNR_GRID:
            d = df.copy()
            d['est_snr_db'] = snr
            d['channel_is_rayleigh'] = int(ch == 'rayleigh')
            bler_fn = bler_rayleigh if ch == 'rayleigh' else bler_awgn
            b16 = bler_fn(snr, bler_df, 16)
            b256 = bler_fn(snr, bler_df, 256)
            d['eff_f1_C16'] = d['compressed_f1'] * (1.0 - b16)
            d['eff_f1_C256'] = d['compressed_f1'] * (1.0 - b256)
            d['eff_f1_L'] = d['late_f1']
            pred = rf.predict(d[feat_cols])
            rf_pay, rf_f1 = realised(d, pred)
            row = dict(channel=ch, snr_db=float(snr),
                       rf_pay=rf_pay, rf_f1=rf_f1)
            for a in ACTIONS:
                row[f'rf_frac_{a}'] = float((pred == a).mean())
            sweep_rows.append(row)
    sweep = pd.DataFrame(sweep_rows)
    sweep.to_csv(os.path.join(OUT_DIR, 'test_snr_sweep.csv'), index=False)
    print('\n--- SNR sweep saved ---')
    print(sweep[['channel', 'snr_db', 'rf_frac_L', 'rf_f1', 'rf_pay']]
          .round(3).to_string(index=False))


if __name__ == '__main__':
    main()
