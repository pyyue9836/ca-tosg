#self+ A1: communication-perception Pareto frontier (F1 vs payload) + Lagrangian lambda sweep
"""
Reframes the contribution from "average-metric gain" to "Pareto-optimality".
For each split we plot, on the payload--F1 plane:
  - the fixed policies L / C16 / C256 (single points),
  - the channel-aware oracle (single point),
  - the Lagrangian oracle frontier s*=argmax_s(eff_f1_s - lambda * B_s) swept over lambda
    (the achievable upper frontier; lambda=0 -> max F1, lambda->inf -> min payload = L),
  - the DEPLOYED Random Forest selector (rf_full.pkl) operating point,
  - the RF retrained on lambda-cost oracle labels for several lambda (learned achievable frontier).
Outputs: paper/figures/fig_pareto_{validate,test}.pdf  +  runs CSV of frontier points.
All numbers come from cached per-frame effective F1 / payload -- no inference re-run.
"""
import os, pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier

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

# selector feature set (must mirror train_rf_v2.py 'full' mode)
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


def feat_cols(df):
    return [c for c in df.columns if c not in EXCLUDE]


def eff_matrix(df):
    return df[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy()


def realised(df, actions):
    actions = np.asarray(actions)
    eff = eff_matrix(df)
    idx = np.array([ACTIONS.index(a) for a in actions])
    f1 = eff[np.arange(len(df)), idx].mean()
    pay = np.array([PAYLOAD[a] for a in actions]).mean()
    return pay, f1


def lambda_oracle_actions(df, lam):
    eff = eff_matrix(df)
    payvec = np.array([PAYLOAD[a] for a in ACTIONS])
    obj = eff - lam * payvec[None, :]
    return np.array(ACTIONS)[obj.argmax(1)]


def fixed_point(df, a):
    eff = eff_matrix(df)[:, ACTIONS.index(a)]
    return PAYLOAD[a], eff.mean()


def run_split(name, csv, train_df=None, rf=None):
    df = pd.read_csv(csv)
    pts = {}
    for a in ACTIONS:
        pts[f'Fixed {a}'] = fixed_point(df, a)
    # oracle (lambda=0)
    pts['Oracle'] = realised(df, df['oracle_3way'].to_numpy())
    # Lagrangian oracle frontier
    lams = np.concatenate([[0.0], np.geomspace(1e-3, 5.0, 40)])
    front = [realised(df, lambda_oracle_actions(df, l)) for l in lams]
    front = np.array(front)
    # deployed RF
    cols = feat_cols(df)
    rf_pay = rf_f1 = None
    if rf is not None:
        cols_rf = [c for c in cols if c in df.columns]
        pred = rf.predict(df[rf.feature_names_in_])
        rf_pay, rf_f1 = realised(df, pred)
        pts['CA-TOSG (RF, deployed)'] = (rf_pay, rf_f1)
    # RF + lambda (retrain on lambda-cost labels using train_df, eval on df)
    rfl = []
    if train_df is not None:
        tcols = feat_cols(train_df)
        common = [c for c in tcols if c in df.columns]
        for lam in [0.0, 0.05, 0.2, 0.5, 1.0, 2.0]:
            y = lambda_oracle_actions(train_df, lam)
            m = RandomForestClassifier(n_estimators=400, max_depth=10,
                                       min_samples_leaf=4, random_state=SEED, n_jobs=-1)
            m.fit(train_df[common], y)
            p = m.predict(df[common])
            rfl.append((lam, *realised(df, p)))
    return df, pts, lams, front, np.array(rfl) if rfl else None


def plot(name, pts, front, rfl):
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    ax.plot(front[:, 0], front[:, 1], '-', color='0.5', lw=1.5, zorder=1,
            label='Lagrangian oracle frontier')
    if rfl is not None:
        ax.plot(rfl[:, 1], rfl[:, 2], 'o--', color='#9467bd', ms=4, lw=1.2,
                zorder=2, label=r'CA-TOSG (RF) $\lambda$-sweep')
    markers = {'Fixed L': ('s', '#1f77b4'), 'Fixed C16': ('^', '#d62728'),
               'Fixed C256': ('v', '#ff7f0e'), 'Oracle': ('*', '#2ca02c'),
               'CA-TOSG (RF, deployed)': ('D', '#9467bd')}
    for k, (x, y) in pts.items():
        m, c = markers.get(k, ('o', 'k'))
        ax.scatter([x], [y], marker=m, c=c, s=90 if m == '*' else 55, zorder=4,
                   edgecolors='k', linewidths=0.5, label=k)
    ax.set_xlabel('Average payload (Mbit/frame, log scale)')
    ax.set_ylabel('Mean realised F1')
    ax.set_xscale('log')
    ax.set_xlim(0.018, 0.65)
    ax.set_ylim(0.05, 0.95)
    ax.grid(True, alpha=0.3, which='both')
    ax.annotate('fixed feature-level\npolicies are dominated',
                xy=(0.495, 0.414), xytext=(0.12, 0.30), fontsize=7, color='0.3',
                arrowprops=dict(arrowstyle='->', color='0.5', lw=0.8))
    ax.legend(fontsize=7, loc='center left', bbox_to_anchor=(1.01, 0.5),
              framealpha=0.95)
    ax.set_title(f'OPV2V {name}', fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIGDIR, f'fig_pareto_{name}.pdf')
    fig.savefig(out, bbox_inches='tight')
    fig.savefig(out.replace('.pdf', '_preview.png'), bbox_inches='tight', dpi=140)
    print('wrote', out)


def main():
    with open(RF_PKL, 'rb') as f:
        rf = pickle.load(f)
    val_df = pd.read_csv(VAL_CSV)

    rows = []
    for name, csv in [('validate', VAL_CSV), ('test', TEST_CSV)]:
        df, pts, lams, front, rfl = run_split(name, csv, train_df=val_df, rf=rf)
        plot(name, pts, front, rfl)
        for k, (x, y) in pts.items():
            rows.append(dict(split=name, policy=k, payload=round(x, 4), f1=round(y, 4)))
        print(f'\n=== {name} key points ===')
        for k, (x, y) in pts.items():
            print(f'  {k:28s} payload={x:.4f}  F1={y:.4f}')
        if rfl is not None:
            print('  RF lambda-sweep (lam, payload, F1):')
            for r in rfl:
                print(f'    lam={r[0]:.2f}  payload={r[1]:.4f}  F1={r[2]:.4f}')
    pd.DataFrame(rows).to_csv(os.path.join(OUTDIR, 'a1_pareto_points.csv'), index=False)
    print('\nwrote', os.path.join(OUTDIR, 'a1_pareto_points.csv'))


if __name__ == '__main__':
    main()
