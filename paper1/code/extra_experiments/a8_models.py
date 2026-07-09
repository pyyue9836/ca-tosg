#self+ A8: selector model comparison -- accuracy / realised-F1 / payload / latency / size
"""
RF predict() at batch 1 costs 52.8 ms. We compare candidate selectors of varying
complexity to justify the choice (or motivate a faster one): Decision Tree,
Logistic Regression, RBF-SVM, small MLP, Random Forest, and the zero-cost
SNR-threshold rule. Train on validate, evaluate on test; latency measured at
batch size 1 (the 10 Hz online operating point), warmed then averaged.
Output: out/a8_models.csv
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
    train = pd.read_csv(C.VAL_CSV)
    test = pd.read_csv(C.TEST_CSV)
    cols = C.feat_cols(train, 'full')
    Xtr, ytr = train[cols], train['oracle_3way']
    Xte = test[cols]
    X1 = Xte.iloc[[0]]

    models = {
        'Decision Tree': DecisionTreeClassifier(max_depth=10, min_samples_leaf=4,
                                                random_state=C.SEED),
        'Logistic Regression': make_pipeline(StandardScaler(),
            LogisticRegression(max_iter=2000, multi_class='multinomial')),
        'RBF-SVM': make_pipeline(StandardScaler(), SVC(kernel='rbf', C=2.0)),
        'Small MLP (32,16)': make_pipeline(StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=800,
                          random_state=C.SEED)),
        'Random Forest (400)': RandomForestClassifier(n_estimators=400, max_depth=10,
            min_samples_leaf=4, random_state=C.SEED, n_jobs=1),
    }
    rows = []
    for name, m in models.items():
        m.fit(Xtr, ytr)
        pred = m.predict(Xte)
        acc = float((pred == test['oracle_3way'].to_numpy()).mean())
        pay, f1 = C.realised(test, pred)
        lat = latency_ms(m, X1)
        rows.append(dict(model=name, oracle_acc=round(acc, 4),
                         realised_f1=round(f1, 4), payload=round(pay, 4),
                         latency_ms=round(lat, 3), size_kb=round(size_kb(m), 1)))
    # SNR-threshold rule (near-zero cost), tau=16 (low-payload operating point)
    awgn = test['channel_type'].to_numpy() == 'awgn'
    snr = test['est_snr_db'].to_numpy()
    pred = np.where(awgn & (snr > 16), 'C16', 'L')
    acc = float((pred == test['oracle_3way'].to_numpy()).mean())
    pay, f1 = C.realised(test, pred)
    rows.append(dict(model='SNR-threshold rule (tau=16)', oracle_acc=round(acc, 4),
                     realised_f1=round(f1, 4), payload=round(pay, 4),
                     latency_ms=0.001, size_kb=0.0))

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(C.OUTDIR, 'a8_models.csv'), index=False)
    print(out.to_string())


if __name__ == '__main__':
    main()
