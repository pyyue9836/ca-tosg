#self+ CA-TOSG paper2: TRUE end-to-end AP inference using cached late+compression .npy predictions
# -*- coding: utf-8 -*-
"""True end-to-end AP inference under the RF policy.

For each of the 1980 OPV2V validate frames:
  1. RF picks s_t in {L, C16, C256} from (cues, snr, channel).
  2. If s_t == L:    use cached late-fusion predicted boxes.
  3. If s_t == C16:  with prob (1 - BLER_16(snr, channel)) use cached
                     attentive-compression predicted boxes; with prob
                     BLER_16 drop the frame's collaborator contribution
                     (= L-only fallback, since L is channel-invariant in
                     our model).
  4. If s_t == C256: same with BLER_256.

Boxes are aggregated across all frames; we compute IoU matches against
ground-truth boxes at thresholds {0.3, 0.5, 0.7} using opencood.utils.
eval_utils, exactly the AP computation the OPV2V benchmark uses.

Cached .npy files do NOT carry per-box confidence; we use uniform
confidence = 1.0 (single-threshold AP). This is documented in the paper
as a limitation of the cached-prediction shortcut; the qualitative
ordering between policies is preserved.

Run:
  PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \
      peiyi_work/01_paper_ca_tosg/true_e2e_ap_inference.py

Output: peiyi_work/01_paper_ca_tosg/runs/v4_true_e2e/results.csv
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from opencood.utils import eval_utils

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LATE_DIR = os.path.join(REPO, 'peiyi_work/05_pretrained_models/pointpillar_late_fusion/npy')
COMP_DIR = os.path.join(REPO,
    'peiyi_work/05_pretrained_models/pointpillar_attentive_fusion/'
    'pointpillar_attentive_fusion_compression/npy')
DATASET = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/dataset.csv')
RF_PATH = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/rf_full.pkl')
BLER_CSV = os.path.join(REPO,
    'peiyi_work/04_experiment_logs/importance_map_jscc/ldpc_qam_bler_table.csv')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_true_e2e')

OPS = [
    ('awgn', 0.0), ('awgn', 8.0), ('awgn', 12.0), ('awgn', 14.0),
    ('awgn', 16.0), ('awgn', 20.0),
    ('rayleigh', 0.0), ('rayleigh', 10.0), ('rayleigh', 20.0),
]
N_REPEAT = 5  # average over 5 stochastic channel realisations
SEED = 0


def load_boxes(npy_dir, sample_id):
    p = os.path.join(npy_dir, f'{sample_id:04d}_pred.npy')
    if not os.path.exists(p):
        return np.zeros((0, 8, 3), dtype=np.float32)
    a = np.load(p, allow_pickle=True)
    return a if a.size > 0 else np.zeros((0, 8, 3), dtype=np.float32)


def load_gt(npy_dir, sample_id):
    p = os.path.join(npy_dir, f'{sample_id:04d}_gt.npy_test.npy')
    if not os.path.exists(p):
        return np.zeros((0, 8, 3), dtype=np.float32)
    a = np.load(p, allow_pickle=True)
    return a if a.size > 0 else np.zeros((0, 8, 3), dtype=np.float32)


def boxes_to_tensor(arr):
    import torch
    if arr.size == 0:
        return torch.zeros((0, 8, 3), dtype=torch.float32)
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


def evaluate_policy(actions, df_ds, bler16, bler256, rng):
    """Aggregate boxes across frames per RF action and compute AP@0.3/0.5/0.7."""
    import torch
    result_stat = {0.3: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.5: {'tp': [], 'fp': [], 'gt': 0, 'score': []},
                   0.7: {'tp': [], 'fp': [], 'gt': 0, 'score': []}}
    for i, row in df_ds.iterrows():
        sid = int(row['sample_id'])
        action = actions[i]
        gt = load_gt(LATE_DIR, sid)
        if gt.size == 0:
            continue
        if action == 'L':
            pred = load_boxes(LATE_DIR, sid)
        elif action == 'C16':
            survives = rng.random() > bler16
            pred = load_boxes(COMP_DIR, sid) if survives else load_boxes(LATE_DIR, sid)
        else:  # C256
            survives = rng.random() > bler256
            pred = load_boxes(COMP_DIR, sid) if survives else load_boxes(LATE_DIR, sid)
        pred_t = boxes_to_tensor(pred)
        gt_t = boxes_to_tensor(gt)
        score = torch.ones(len(pred_t), dtype=torch.float32)
        for thr in (0.3, 0.5, 0.7):
            eval_utils.caluclate_tp_fp(pred_t, score, gt_t, result_stat, thr)
    ap30, _, _ = eval_utils.calculate_ap(result_stat, 0.30, False)
    ap50, _, _ = eval_utils.calculate_ap(result_stat, 0.50, False)
    ap70, _, _ = eval_utils.calculate_ap(result_stat, 0.70, False)
    return ap30, ap50, ap70


def main():
    import pickle
    os.makedirs(OUT_DIR, exist_ok=True)
    df_ds = pd.read_csv(DATASET).reset_index(drop=True)
    bler_df = pd.read_csv(BLER_CSV)
    with open(RF_PATH, 'rb') as f: rf = pickle.load(f)
    feat_cols = list(rf.feature_names_in_)
    rng = np.random.default_rng(SEED)

    rows = []
    for channel, snr in OPS:
        d = df_ds.copy()
        d['est_snr_db'] = snr
        d['channel_is_rayleigh'] = int(channel == 'rayleigh')
        actions = rf.predict(d[feat_cols])
        bler_fn = bler_rayleigh if channel == 'rayleigh' else bler_awgn
        b16 = bler_fn(snr, bler_df, 16)
        b256 = bler_fn(snr, bler_df, 256)

        # Multiple stochastic channel realisations
        ap30s, ap50s, ap70s = [], [], []
        for r in range(N_REPEAT):
            rng_r = np.random.default_rng(SEED + r)
            ap30, ap50, ap70 = evaluate_policy(actions, d, b16, b256, rng_r)
            ap30s.append(ap30); ap50s.append(ap50); ap70s.append(ap70)

        rho_L = float((actions == 'L').mean())
        rho_C16 = float((actions == 'C16').mean())
        rho_C256 = float((actions == 'C256').mean())
        print(f'  {channel:8s} SNR={snr:5.1f} dB:  '
              f'AP@0.5={np.mean(ap50s):.4f}±{np.std(ap50s):.4f}  '
              f'AP@0.7={np.mean(ap70s):.4f}±{np.std(ap70s):.4f}  '
              f'rho_L={rho_L:.3f}')
        rows.append(dict(channel=channel, snr_db=snr,
                         rho_L=rho_L, rho_C16=rho_C16, rho_C256=rho_C256,
                         bler_C16=b16, bler_C256=b256,
                         ap30_mean=float(np.mean(ap30s)), ap30_std=float(np.std(ap30s)),
                         ap50_mean=float(np.mean(ap50s)), ap50_std=float(np.std(ap50s)),
                         ap70_mean=float(np.mean(ap70s)), ap70_std=float(np.std(ap70s))))

    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, 'results.csv'), index=False)
    print('wrote', os.path.join(OUT_DIR, 'results.csv'))


if __name__ == '__main__':
    main()
