#self+ A8 v3 (PUBLICATION): selector model comparison. realised-F1 + payload are 200-REALISATION
# (publication protocol); oracle-accuracy is classification vs the frozen v3 labels; latency + size are
# channel-independent and kept as-is (4.4.4 "lighter models reach the same accuracy" + latency table).
"""
Compare candidate selectors (Decision Tree, Logistic Regression, RBF-SVM, small MLP, Random Forest) +
the zero-cost SNR-threshold rule. Train on validate (frozen v3 oracle_3way labels), evaluate realised
F1 + payload over 200 channel realisations on test; latency at batch 1 (10 Hz online point); model size.
Output: out/a8_models_v3.csv
"""
import os, time, pickle, io
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import _common as C
import v3_eval as V

RETUNED_TAU = 8.5   # engine best-tau on test (results/policy_v3/threshold_vs_rf.csv)


def latency_ms(model, X1, n_warm=100, n_meas=1000):
    for _ in range(n_warm):
        model.predict(X1)
    t0 = time.perf_counter()
    for _ in range(n_meas):
        model.predict(X1)
    return (time.perf_counter() - t0) / n_meas * 1e3


def size_kb(model):
    buf = io.BytesIO(); pickle.dump(model, buf); return buf.tell() / 1024.0


def main():
    train = pd.read_csv(C.VAL_CSV); test = pd.read_csv(C.TEST_CSV)
    cols = C.feat_cols(train, 'full')
    Xtr, ytr = train[cols], train['oracle_3way']; X1 = test[cols].iloc[[0]]
    # ALL models trained with class_weight='balanced' (where supported) to match the DEPLOYED selector's
    # objective -- otherwise the RF row here (unbalanced) disagrees with the headline deployed RF
    # (0.9045@0.0508 unbalanced vs 0.9088@0.1346 balanced), i.e. two conflicting "RF" numbers. MLP does
    # NOT support class_weight (noted); it is the one exception.
    models = {
        'Decision Tree': DecisionTreeClassifier(max_depth=10, min_samples_leaf=4,
            class_weight='balanced', random_state=C.SEED),
        'Logistic Regression': make_pipeline(StandardScaler(),
            LogisticRegression(max_iter=2000, multi_class='multinomial', class_weight='balanced')),
        'RBF-SVM': make_pipeline(StandardScaler(), SVC(kernel='rbf', C=2.0, class_weight='balanced')),
        'Small MLP (32,16) [no class_weight]': make_pipeline(StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=800, random_state=C.SEED)),
        'Random Forest (400)': RandomForestClassifier(n_estimators=400, max_depth=10,
            min_samples_leaf=4, class_weight='balanced', random_state=C.SEED, n_jobs=1),
    }
    rows = []
    for name, m in models.items():
        m.fit(Xtr, ytr)
        acc = float((m.predict(test[cols]) == test['oracle_3way'].to_numpy()).mean())
        f1s, pays = V.eval_series(test, 'rf', feat=cols, model=m)   # 200-realisation
        rows.append(dict(model=name, oracle_acc=round(acc, 4),
                         realised_f1=round(float(f1s.mean()), 4), realised_f1_std=round(float(f1s.std()), 4),
                         payload=round(float(pays.mean()), 4),
                         latency_ms=round(latency_ms(m, X1), 3), size_kb=round(size_kb(m), 1)))
    # zero-cost retuned SNR-threshold reference (200-real)
    f1s, pays = V.eval_series(test, f'threshold:{RETUNED_TAU}')
    rows.append(dict(model=f'SNR-threshold (retuned tau={RETUNED_TAU})',
                     oracle_acc=float('nan'), realised_f1=round(float(f1s.mean()), 4),
                     realised_f1_std=round(float(f1s.std()), 4), payload=round(float(pays.mean()), 4),
                     latency_ms=0.001, size_kb=0.0))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(C.OUTDIR, 'a8_models_v3.csv'), index=False)
    print('=== A8 v3 model comparison (realised F1/payload = 200-realisation; latency batch-1) ===')
    print(out.to_string(index=False))
    rf_f1 = [r['realised_f1'] for r in rows if r['model'].startswith('Random Forest')][0]
    print('\nlighter-vs-RF realised F1 gap (200-real):')
    for r in rows:
        if not r['model'].startswith('Random Forest') and not np.isnan(r['oracle_acc']):
            print(f"  {r['model']:24s} {r['realised_f1']-rf_f1:+.4f}  (latency {r['latency_ms']} ms)")


if __name__ == '__main__':
    main()
