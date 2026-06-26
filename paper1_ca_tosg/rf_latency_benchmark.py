#self+ CA-TOSG paper2: per-frame RF inference latency measurement (P50/P95/P99 over 2000 trials)
# -*- coding: utf-8 -*-
"""RF inference latency measurement on a single CPU core.

Replicates the deployment-mode call:
  s_t = rf.predict(x_t)
on the deployed rf_full.pkl. Reports per-sample latency (mean, std,
P50, P95, P99) over batches of size 1 to match the per-frame online
operating point of a 10 Hz LiDAR cycle.

Output: peiyi_work/01_paper_ca_tosg/runs/v4_latency/results.csv
"""
import os
import pickle
import time

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATASET = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/dataset.csv')
RF_PATH = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v2/rf_full.pkl')
OUT_DIR = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/runs/v4_latency')

WARMUP = 100      # discard first 100 to avoid sklearn JIT warm-up
N_TRIALS = 2000   # measured samples per regime
SEED = 0


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATASET)
    with open(RF_PATH, 'rb') as f: rf = pickle.load(f)
    feat_cols = list(rf.feature_names_in_)
    rng = np.random.default_rng(SEED)

    rows = []
    for batch_size in (1, 10, 100):
        # Random sample indices for each trial
        idxs = rng.integers(0, len(df), size=(WARMUP + N_TRIALS, batch_size))

        # Warm-up
        for w in range(WARMUP):
            _ = rf.predict(df.iloc[idxs[w]][feat_cols])

        # Measure
        ts = []
        for t in range(N_TRIALS):
            sub = df.iloc[idxs[WARMUP + t]][feat_cols]
            t0 = time.perf_counter()
            _ = rf.predict(sub)
            ts.append((time.perf_counter() - t0) * 1e3)  # ms

        ts = np.array(ts)
        # Latency per sample (relevant for online deployment)
        per_sample = ts / batch_size
        row = dict(
            batch_size=batch_size,
            n_trials=N_TRIALS,
            total_ms_mean=float(ts.mean()),
            total_ms_std=float(ts.std()),
            total_ms_p50=float(np.percentile(ts, 50)),
            total_ms_p95=float(np.percentile(ts, 95)),
            total_ms_p99=float(np.percentile(ts, 99)),
            per_sample_us_mean=float(per_sample.mean() * 1000),
            per_sample_us_std=float(per_sample.std() * 1000),
            per_sample_us_p50=float(np.percentile(per_sample, 50) * 1000),
            per_sample_us_p95=float(np.percentile(per_sample, 95) * 1000),
            per_sample_us_p99=float(np.percentile(per_sample, 99) * 1000),
        )
        rows.append(row)
        print(f'  batch={batch_size:3d}: total {ts.mean():.3f}±{ts.std():.3f} ms  '
              f'per-sample {per_sample.mean()*1000:.1f}±{per_sample.std()*1000:.1f} us  '
              f'(P50={np.percentile(per_sample,50)*1000:.1f}us P95={np.percentile(per_sample,95)*1000:.1f}us)')

    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, 'results.csv'), index=False)
    print('wrote', os.path.join(OUT_DIR, 'results.csv'))


if __name__ == '__main__':
    main()
