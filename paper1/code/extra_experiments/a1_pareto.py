#self+ A1 v3: communication-perception Pareto frontier (F1 vs payload) + Lagrangian lambda sweep,
# on the canonical v3 datasets. ADDS the C256 activation rate ALONG the Lagrangian frontier -- the
# empirical test of whether the rate-matched 3rd action ever earns a foothold once its lower payload
# (0.2475 vs 0.495 Mbit) is allowed to compete (under lam=0 it is provably dominated: eff_C256 <=
# eff_C16 pointwise since identical content at higher BLER, so payload-blind argmax never prefers it;
# the ONLY place C256 can win is lambda>0, here).
"""
Self-contained v3 (does NOT use the stale _common paths). Reads data/dataset_{split}_v3.csv (which
carry eff_f1_L/C16/C256, bler_C16/C256, oracle_3way from make_dataset.py) + data/selector_rf.pkl.
Feasibility mask (BLER>=0.999) removes an action from the frontier argmax -- an undeliverable request
is not a real frontier point. validate uses the same held-out 30% (SEED0) as the deployed selector.
Outputs: paper/figures/fig_pareto_{validate,test,culver}.pdf + out/a1_pareto_points.csv
         + out/a1_c256_frontier.csv (lambda, C256 activation, C16 activation, payload, F1 per split).
"""
import os, sys, pickle
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

HERE = os.path.dirname(os.path.abspath(__file__)); P1 = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(P1, 'data'); OUTDIR = os.path.join(HERE, 'out')
FIGDIR = os.path.join(P1, 'paper/figures')
os.makedirs(OUTDIR, exist_ok=True); os.makedirs(FIGDIR, exist_ok=True)
try:
    sys.path.insert(0, os.path.join(P1, 'code')); import paper_style as PS; PS.apply()
except Exception:
    PS = None

PAYLOAD = {'L': 0.024, 'C16': 1.98 / 4.0, 'C256': 1.98 / 8.0}
ACTIONS = ['L', 'C16', 'C256']; PAYVEC = np.array([PAYLOAD[a] for a in ACTIONS])
SEED = 0; BLER_INFEASIBLE = 0.999
EXCLUDE = {'sample_id', 'cav_keys', 'channel_type', 'est_snr_db', 'channel_is_rayleigh',
           'bler_C16', 'bler_C256', 'eff_f1_L', 'eff_f1_C16', 'eff_f1_C256', 'oracle_3way', 'ego_f1',
           *[f'{m}_{s}' for m in ('late', 'early', 'intermediate', 'compressed')
             for s in ('num_pred', 'num_gt', 'tp', 'fp', 'fn', 'precision', 'recall', 'f1', 'payload_Mbit')],
           *[f'{m}_f1_gain_over_late' for m in ('late', 'early', 'intermediate', 'compressed')],
           *[f'{m}_gain_per_extra_Mbit' for m in ('late', 'early', 'intermediate', 'compressed')],
           'best_method_by_f1', 'best_level_by_f1', 'best_f1', 'best_payload_Mbit'}


def eff_matrix(df):
    return df[['eff_f1_L', 'eff_f1_C16', 'eff_f1_C256']].to_numpy()


def mask_of(df):
    m = np.zeros((len(df), 3), bool)
    m[:, 1] = df['bler_C16'].to_numpy() >= BLER_INFEASIBLE
    m[:, 2] = df['bler_C256'].to_numpy() >= BLER_INFEASIBLE
    return m


def realised(df, actions):
    eff = eff_matrix(df); idx = np.array([ACTIONS.index(a) for a in actions])
    return float(np.array([PAYLOAD[a] for a in actions]).mean()), float(eff[np.arange(len(df)), idx].mean())


def lambda_actions(df, lam):
    """Feasibility-masked Lagrangian argmax over eff - lam*payload."""
    obj = eff_matrix(df) - lam * PAYVEC[None, :]
    obj = np.where(mask_of(df), -np.inf, obj)
    return np.array(ACTIONS)[obj.argmax(1)]


def run_split(name, df, train_df, rf):
    pts = {}
    for a in ACTIONS:
        pts[f'Fixed {a}'] = (PAYLOAD[a], float(eff_matrix(df)[:, ACTIONS.index(a)].mean()))
    pts['Oracle'] = realised(df, lambda_actions(df, 0.0))          # lam=0 masked oracle
    lams = np.concatenate([[0.0], np.geomspace(1e-3, 5.0, 40)])
    front, c256_rows = [], []
    for l in lams:
        acts = lambda_actions(df, l)
        pay, f1 = realised(df, acts)
        front.append((pay, f1))
        c256_rows.append(dict(split=name, lam=round(float(l), 5),
                              frac_C256=round(float((acts == 'C256').mean()), 5),
                              frac_C16=round(float((acts == 'C16').mean()), 5),
                              frac_L=round(float((acts == 'L').mean()), 5),
                              payload=round(pay, 4), f1=round(f1, 4)))
    front = np.array(front)
    pred = rf.predict(df[list(rf.feature_names_in_)])
    pts['CA-TOSG (RF, deployed)'] = realised(df, pred)
    # RF retrained on lambda-cost labels (learned achievable frontier)
    rfl = []
    tcols = list(rf.feature_names_in_)
    for lam in [0.0, 0.05, 0.2, 0.5, 1.0, 2.0]:
        y = lambda_actions(train_df, lam)
        m = RandomForestClassifier(n_estimators=400, max_depth=10, min_samples_leaf=4,
                                   random_state=SEED, n_jobs=-1).fit(train_df[tcols], y)
        rfl.append((lam, *realised(df, m.predict(df[tcols]))))
    return pts, front, np.array(rfl), c256_rows


def plot(name, pts, front, rfl):
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    ax.plot(front[:, 0], front[:, 1], '-', lw=1.3, zorder=1, color='0.4',
            label='Lagrangian oracle frontier')
    if rfl is not None and len(rfl):
        ax.plot(rfl[:, 1], rfl[:, 2], 'o--', ms=4, lw=1.1, zorder=2,
                label=r'CA-TOSG (RF) $\lambda$-sweep')
    for k, (x, y) in pts.items():
        ax.scatter([x], [y], s=70, zorder=4, edgecolors='k', linewidths=0.5, label=k)
    ax.set_xlabel('Average payload (Mbit/frame, log)'); ax.set_ylabel('Mean realised F1')
    ax.set_xscale('log'); ax.grid(True, alpha=0.3, which='both')
    ax.legend(fontsize=7, loc='center left', bbox_to_anchor=(1.01, 0.5))
    ax.set_title(f'OPV2V {name}', fontsize=9); fig.tight_layout()
    out = os.path.join(FIGDIR, f'fig_pareto_{name}.pdf')
    fig.savefig(out, bbox_inches='tight'); fig.savefig(out.replace('.pdf', '_preview.png'), dpi=140, bbox_inches='tight')
    print('wrote', out)


def main():
    rf = pickle.load(open(os.path.join(DATA, 'selector_rf.pkl'), 'rb'))
    val = pd.read_csv(os.path.join(DATA, 'dataset_validate_v3.csv'))
    test = pd.read_csv(os.path.join(DATA, 'dataset_test_v3.csv'))
    culver = pd.read_csv(os.path.join(DATA, 'dataset_culver_v3.csv'))
    v_tr, v_te = train_test_split(val, test_size=0.30, random_state=SEED, stratify=val['oracle_3way'])

    rows, c256_all = [], []
    for name, df, tdf in [('validate', v_te, v_tr), ('test', test, val), ('culver', culver, val)]:
        pts, front, rfl, c256_rows = run_split(name, df, tdf, rf)
        plot(name, pts, front, rfl); c256_all += c256_rows
        for k, (x, y) in pts.items():
            rows.append(dict(split=name, policy=k, payload=round(x, 4), f1=round(y, 4)))
        cmax = max(r['frac_C256'] for r in c256_rows)
        print(f"\n=== {name} ===  max C256 activation over the lambda frontier = {cmax:.5f}")
        for k, (x, y) in pts.items():
            print(f"  {k:28s} payload={x:.4f}  F1={y:.4f}")
    pd.DataFrame(rows).to_csv(os.path.join(OUTDIR, 'a1_pareto_points.csv'), index=False)
    pd.DataFrame(c256_all).to_csv(os.path.join(OUTDIR, 'a1_c256_frontier.csv'), index=False)
    print('\n=== C256 activation along the Lagrangian frontier (max per split) ===')
    for sp in ('validate', 'test', 'culver'):
        sub = [r for r in c256_all if r['split'] == sp]
        cmax = max(r['frac_C256'] for r in sub)
        at = [r for r in sub if r['frac_C256'] == cmax][0]
        print(f"  {sp:9s} max frac_C256={cmax:.5f} at lam={at['lam']} (payload={at['payload']}, F1={at['f1']})")
    print('wrote', os.path.join(OUTDIR, 'a1_pareto_points.csv'), '+ a1_c256_frontier.csv')


if __name__ == '__main__':
    main()
