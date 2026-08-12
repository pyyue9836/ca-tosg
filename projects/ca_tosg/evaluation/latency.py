#self+ CA-TOSG P2-C: per-frame selector inference latency on the FROZEN selectors (batch-1 online point)
# -*- coding: utf-8 -*-
"""P2-C latency re-measurement on the FROZEN selectors + end-to-end timing table.

PROTOCOL step-4 requires the deployed-selector latency to be RE-MEASURED on the P2 frozen product (the
old 52.8 ms was the RETIRED v2 selector; that CSV was archived then removed in P1.5). This script now
reads the three frozen selectors from FROZEN_MANIFEST.json (sha256-verified before load, exactly like
deployment.py) and measures the deployment predict() call.

Latency protocol (same as extra_experiments/a8_models.py -- the batch-1 online 10 Hz operating point):
  WARMUP discarded, then N_TRIALS per-call timings; report mean / std / P50 / P95 / P99 (ms) + model
  size. Each trial is a real deployment call: one frame's 23-feature vector in the model's training
  column order (built by eval_p2_deploy._feature_matrix), a random frame, a random est_snr ~ U[0,20] dB
  and a random channel ~ Bernoulli(0.5). The frozen models were fitted on an unnamed numpy array, so
  predict() takes the numpy matrix directly (no feature_names_in_).

End-to-end timing table (system_timing.csv). One row per per-frame pipeline stage, each tagged
measured / calculated / assumed / not-included with an explicit source. ONLY the selector-inference row
is `measured` (from this run). Transmission time is `not-included`: B_max is a prespecified channel-use
budget NOT mapped to a physical link rate (PROTOCOL sec 5), so a wall-clock transmission latency is not
derivable this round. Backbone inference / cue extraction / feature encode / fusion are `not-included`
(not measured this round; incurred by every policy alike). The 100 ms LiDAR period is `assumed` (the
10 Hz operating point); the 2-bit request is `calculated` (negligible, piggy-backed on CAM).

Outputs (results/p2_latency/):
  selector_latency.csv  -- per frozen selector: mean/std/P50/P95/P99 ms + size_kb (batch-1).
  system_timing.csv      -- per-frame pipeline timing table with per-row measured/calculated/assumed/
                         not-included tags + source (selector row filled from selector_latency.csv).
  PROVENANCE_latency.txt

Run:  /path/to/env/python projects/ca_tosg/evaluation/latency.py
"""
import io
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'p2_dataprep'))
# --- ca-tosg layout bootstrap (restructure commit 2/4) ---
import os as _o, sys as _s
_CT_ROOT = _o.path.abspath(_o.path.join(_o.path.dirname(_o.path.abspath(__file__)), '..', '..', '..'))
for _d in ('projects/ca_tosg/evaluation', 'projects/ca_tosg/evaluation/ablations', 'projects/ca_tosg/utils', 'projects/ca_tosg/datasets'):
    _s.path.insert(0, _o.path.join(_CT_ROOT, _d))
# --- end bootstrap ---
import deployment as D          # frozen-manifest loader + feature-matrix builder (single source)

P1 = D.P1
OUT_DIR = os.path.join(P1, 'results/latency')

PROV_DIR = os.path.join(P1, 'results/provenance')
WARMUP = 100        # discard sklearn warm-up (a8_models n_warm)
N_TRIALS = 1000     # measured calls per model (a8_models n_meas)
SEED = 0
LIDAR_PERIOD_MS = 100.0   # 10 Hz operating point -- ASSUMED (main.tex claim c1c08b6), not measured


def size_kb(model):
    buf = io.BytesIO(); pickle.dump(model, buf); return buf.tell() / 1024.0


def measure_model(model, feat, cues_df, rng):
    """batch-1 per-call latency (ms). Random frame + random est_snr/channel each trial."""
    n = len(cues_df)
    fidx = rng.integers(0, n, size=WARMUP + N_TRIALS)
    snr = rng.uniform(0, 20, size=WARMUP + N_TRIALS)
    ray = rng.random(size=WARMUP + N_TRIALS) < 0.5
    # pre-build the batch-1 numpy vectors (build cost excluded from the timed region)
    X = [D._feature_matrix(feat, cues_df.iloc[[fidx[i]]], snr[i:i + 1], ray[i:i + 1])
         for i in range(WARMUP + N_TRIALS)]
    for i in range(WARMUP):
        model.predict(X[i])
    ts = np.empty(N_TRIALS)
    for i in range(N_TRIALS):
        x = X[WARMUP + i]
        t0 = time.perf_counter()
        model.predict(x)
        ts[i] = (time.perf_counter() - t0) * 1e3
    return ts


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    man, budgets = D.load_manifest()
    cues = pd.read_csv(os.path.join(D.DATA, D.DATASET['test']))   # test cues = deployment operating set
    rng = np.random.default_rng(SEED)

    rows = []
    for tag in sorted(budgets):
        bd = budgets[tag]; bmax = float(tag)
        ts = measure_model(bd['model'], bd['feat'], cues, rng)
        rows.append(dict(
            budget=bmax, model=f'selector_B{int(round(bmax * 100)):03d}',
            candidate_index=man['budgets'][tag]['candidate_index'],
            n_trials=N_TRIALS, batch_size=1,
            mean_ms=round(float(ts.mean()), 3), std_ms=round(float(ts.std()), 3),
            p50_ms=round(float(np.percentile(ts, 50)), 3),
            p95_ms=round(float(np.percentile(ts, 95)), 3),
            p99_ms=round(float(np.percentile(ts, 99)), 3),
            size_kb=round(size_kb(bd['model']), 1)))
        print(f"  {rows[-1]['model']}: mean {ts.mean():.2f}+/-{ts.std():.2f} ms  "
              f"P50={np.percentile(ts,50):.2f} P95={np.percentile(ts,95):.2f} "
              f"P99={np.percentile(ts,99):.2f} ms  size={rows[-1]['size_kb']} kB", flush=True)
    lat = pd.DataFrame(rows)
    lat.to_csv(os.path.join(OUT_DIR, 'selector_latency.csv'), index=False)

    # ---- end-to-end per-frame timing table (per-row provenance tags) ----
    sel_mean = float(lat['mean_ms'].max())   # worst-case (slowest) frozen selector, for the budget row
    sel_p95 = float(lat['p95_ms'].max())
    e2e = [
        dict(stage='LiDAR frame period (10 Hz)', value_ms=round(LIDAR_PERIOD_MS, 3), tag='assumed',
             source='10 Hz operating point (main.tex c1c08b6); the per-frame budget; not measured'),
        dict(stage='Ego LiDAR detection backbone (PointPillar)', value_ms='', tag='not-included',
             source='not measured this round; incurred by every policy/baseline alike (not selection overhead)'),
        dict(stage='Online cue extraction (23 selector features)', value_ms='', tag='not-included',
             source='not measured this round; per-frame feature computation; policy-independent'),
        dict(stage='Selector inference (RF predict; batch-1)',
             value_ms=round(sel_mean, 3), tag='measured',
             source=f'selector_latency.csv; slowest frozen selector (mean; P95={sel_p95:.2f} ms); '
                    f'{N_TRIALS} batch-1 calls; WARMUP={WARMUP}'),
        dict(stage='2-bit request signalling (piggy-backed on CAM)', value_ms='', tag='calculated',
             source='2 bit/frame @10 Hz = 20 bps; provisioned in the standard CAM budget (main.tex '
                    'c0a4e89); no extra airtime'),
        dict(stage='Message transmission (L / F payload over link)', value_ms='', tag='not-included',
             source='B_max is a PRESPECIFIED channel-use budget; NOT mapped to a physical link rate '
                    '(PROTOCOL sec 5); wall-clock transmission latency is not derivable this round'),
        dict(stage='Collaborator feature encode / compression', value_ms='', tag='not-included',
             source='not measured this round; sender-side; policy-dependent but out of scope for P2-C'),
        dict(stage='Fusion + post-processing at ego', value_ms='', tag='not-included',
             source='not measured this round; shared detector post-processing'),
    ]
    pd.DataFrame(e2e).to_csv(os.path.join(OUT_DIR, 'system_timing.csv'), index=False)

    with open(os.path.join(PROV_DIR, 'PROVENANCE_latency.txt'), 'w') as f:
        f.write('CA-TOSG P2-C -- frozen-selector latency + end-to-end timing (latency.py)\n' + '=' * 80 + '\n')
        f.write(f'manifest: results/manifests/FROZEN_MANIFEST.json (schema {man["schema"]}, '
                f'freeze {man["freeze_timestamp"]})\n')
        f.write('3 frozen selectors sha256-verified before load (via eval_p2_deploy.load_manifest).\n')
        f.write(f'Latency protocol = a8_models batch-1 online point: WARMUP={WARMUP} discarded, '
                f'N_TRIALS={N_TRIALS} per-call timings; mean/std/P50/P95/P99 ms + pickled size_kb.\n')
        f.write(f'Each trial: one test frame (random), est_snr~U[0,20] dB, channel~Bernoulli(0.5); '
                f'seed={SEED}. Models fitted on unnamed numpy -> predict() on the numpy matrix directly.\n')
        f.write('system_timing.csv: per-frame pipeline, one row per stage, tag in '
                '{measured, calculated, assumed, not-included} with an explicit source.\n')
        f.write('  ONLY the selector-inference row is `measured` (this run, slowest frozen selector).\n')
        f.write('  Transmission time is `not-included`: PROTOCOL sec 5 budgets are prespecified '
                'channel uses, not a physical link rate -> no wall-clock latency this round.\n')
        f.write('LiDAR period 100 ms = `assumed` (10 Hz); 2-bit request = `calculated` (20 bps, CAM).\n')
    print(f'\nselector inference (slowest frozen): mean {sel_mean:.2f} ms, P95 {sel_p95:.2f} ms '
          f'vs the {LIDAR_PERIOD_MS:.0f} ms 10 Hz budget.')
    print('wrote results/p2_latency/{selector_latency.csv,system_timing.csv,PROVENANCE_latency.txt}', flush=True)


if __name__ == '__main__':
    main()
