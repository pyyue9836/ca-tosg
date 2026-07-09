#self+ Test-split pipeline 05: TRUE end-to-end AP on the OPV2V test split using cached test-split predictions, with Bernoulli channel realisations; produces the AP table that goes in §V "Generalisation to OPV2V Test Split"
"""
Mirrors true_e2e_ap_inference.py but on the OPV2V test split:
  for each frame, RF picks L or C, cached test prediction is selected, with
  prob BLER_q the C frame is dropped and falls back to the L prediction; AP
  is computed via opencood.utils.eval_utils.

Output: runs/test_true_e2e_ap.csv (one row per operating point).
"""
import os
import pickle
import sys
import numpy as np
import pandas as pd
import torch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, REPO)
from opencood.utils import eval_utils

SPLIT = os.environ.get('CATOSG_SPLIT', 'test')
TAG = 'culver' if 'culver' in SPLIT else 'test'
RUNS = 'runs' if TAG == 'test' else 'runs_culver'
PRETRAINED = os.path.join(REPO, 'peiyi_work/05_pretrained_models')
LATE_NPY = os.path.join(PRETRAINED, f'pointpillar_late_fusion_{TAG}_eval', 'npy')
COMP_NPY = os.path.join(PRETRAINED, 'pointpillar_attentive_fusion',
    f'pointpillar_attentive_fusion_compression_{TAG}_eval', 'npy')
DATASET = os.path.join(REPO,
    f'peiyi_work/01_paper_ca_tosg/test_split_pipeline/{RUNS}/test_dataset.csv')
RF_PATH = os.path.join(REPO,
    'peiyi_work/01_paper_ca_tosg/runs/v2/rf_full.pkl')
BLER_CSV = os.path.join(REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT_DIR = os.path.join(REPO,
    f'peiyi_work/01_paper_ca_tosg/test_split_pipeline/{RUNS}')

OPS = [
    ('awgn', 0.0), ('awgn', 8.0), ('awgn', 12.0), ('awgn', 14.0),
    ('awgn', 16.0), ('awgn', 20.0),
    ('rayleigh', 0.0), ('rayleigh', 10.0), ('rayleigh', 20.0),
]
N_REPEAT = 5
SEED = 0


def load_boxes(npy_dir, sid):
    p = os.path.join(npy_dir, f'{sid:04d}_pred.npy')
    if not os.path.exists(p): return np.zeros((0, 8, 3), dtype=np.float32)
    a = np.load(p, allow_pickle=True)
    return a if a.size > 0 else np.zeros((0, 8, 3), dtype=np.float32)


def load_gt(npy_dir, sid):
    p = os.path.join(npy_dir, f'{sid:04d}_gt.npy_test.npy')
    if not os.path.exists(p): return np.zeros((0, 8, 3), dtype=np.float32)
    a = np.load(p, allow_pickle=True)
    return a if a.size > 0 else np.zeros((0, 8, 3), dtype=np.float32)


def boxes_to_tensor(arr):
    if arr.size == 0: return torch.zeros((0, 8, 3), dtype=torch.float32)
    return torch.from_numpy(arr.astype(np.float32))


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


def evaluate_policy(actions, df_ds, b16, b256, rng):
    result_stat = {0.3: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.5: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.7: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    for i, row in df_ds.iterrows():
        sid = int(row['sample_id'])
        a = actions[i]
        gt = load_gt(LATE_NPY, sid)
        if gt.size == 0: continue
        if a == 'L':
            pred = load_boxes(LATE_NPY, sid)
        elif a == 'C16':
            survives = rng.random() > b16
            pred = load_boxes(COMP_NPY, sid) if survives else load_boxes(LATE_NPY, sid)
        else:
            survives = rng.random() > b256
            pred = load_boxes(COMP_NPY, sid) if survives else load_boxes(LATE_NPY, sid)
        pt = boxes_to_tensor(pred); gt_t = boxes_to_tensor(gt)
        sc = torch.ones(len(pt), dtype=torch.float32)
        for thr in (0.3, 0.5, 0.7):
            eval_utils.caluclate_tp_fp(pt, sc, gt_t, result_stat, thr)
    ap30, _, _ = eval_utils.calculate_ap(result_stat, 0.30, False)
    ap50, _, _ = eval_utils.calculate_ap(result_stat, 0.50, False)
    ap70, _, _ = eval_utils.calculate_ap(result_stat, 0.70, False)
    return ap30, ap50, ap70


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATASET).reset_index(drop=True)
    bler_df = pd.read_csv(BLER_CSV)
    with open(RF_PATH, 'rb') as f: rf = pickle.load(f)
    feat_cols = list(rf.feature_names_in_)

    rows = []
    for ch, snr in OPS:
        d = df.copy()
        d['est_snr_db'] = snr
        d['channel_is_rayleigh'] = int(ch == 'rayleigh')
        actions = rf.predict(d[feat_cols])
        b16 = bler_rayleigh(snr, bler_df, 16) if ch == 'rayleigh' \
            else bler_awgn(snr, bler_df, 16)
        b256 = bler_rayleigh(snr, bler_df, 256) if ch == 'rayleigh' \
            else bler_awgn(snr, bler_df, 256)
        ap30s, ap50s, ap70s = [], [], []
        for r in range(N_REPEAT):
            rng = np.random.default_rng(SEED + r)
            a30, a50, a70 = evaluate_policy(actions, d, b16, b256, rng)
            ap30s.append(a30); ap50s.append(a50); ap70s.append(a70)
        rho_L = float((actions == 'L').mean())
        print(f'  {ch:8s} SNR={snr:5.1f} dB:  '
              f'AP@0.5={np.mean(ap50s):.4f}\xb1{np.std(ap50s):.4f}  '
              f'AP@0.7={np.mean(ap70s):.4f}\xb1{np.std(ap70s):.4f}  '
              f'rho_L={rho_L:.3f}')
        rows.append(dict(channel=ch, snr_db=snr, rho_L=rho_L,
                          bler_16=b16, bler_256=b256,
                          ap30_mean=float(np.mean(ap30s)), ap30_std=float(np.std(ap30s)),
                          ap50_mean=float(np.mean(ap50s)), ap50_std=float(np.std(ap50s)),
                          ap70_mean=float(np.mean(ap70s)), ap70_std=float(np.std(ap70s))))
    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, 'test_true_e2e_ap.csv'), index=False)
    print(f'\nwrote {os.path.join(OUT_DIR, "test_true_e2e_ap.csv")}')


if __name__ == '__main__':
    main()
