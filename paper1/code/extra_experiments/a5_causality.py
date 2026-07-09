#self+ A5: request latency / causality -- decision staleness across frames
"""
The ego decides on frame t, signals a 2-bit request, the collaborator transmits,
and the ego fuses. The 2-bit request is tiny so sub-frame request delays do not
change the decided frame; the real risk is whole-frame staleness: at a 10 Hz LiDAR
rate, a one-frame round trip means the decision made on frame t is applied to
frame t+1 (100 ms later).

We quantify, per delay d (in frames, i.e. d*100 ms), over consecutive frames within
each scenario:
  - stale-decision rate: fraction of frames where the oracle action would change
    between frame t and t+d (the scene/channel state moved),
  - the realised-F1 cost of acting on the stale (frame t-d) decision vs the
    same-frame decision.
Scenario boundaries are detected from sample_id resets. Mitigation (persistent mode
preference across a communication round) is discussed in the paper.
Output: out/a5_causality.csv
"""
import os
import numpy as np
import pandas as pd
import _common as C


def segments(df):
    """Yield index arrays for each scenario (sample_id resets to a smaller value)."""
    sid = df['sample_id'].to_numpy()
    bounds = [0] + list(np.where(np.diff(sid) < 0)[0] + 1) + [len(df)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b - a >= 3:
            yield np.arange(a, b)


def main():
    df = pd.read_csv(C.TEST_CSV).reset_index(drop=True)
    rf = C.load_rf()
    rf_act = np.asarray(C.rf_predict(rf, df))
    oracle = df['oracle_3way'].to_numpy()
    eff = C.eff_matrix(df)
    aidx = {a: i for i, a in enumerate(C.ACTIONS)}

    rows = []
    for d in [0, 1, 2, 5]:
        stale_num = stale_den = 0
        f1_sum = n = 0
        for seg in segments(df):
            if len(seg) <= d:
                continue
            cur = seg[d:]; past = seg[:len(seg) - d]
            # staleness on oracle action
            stale_num += int((oracle[past] != oracle[cur]).sum())
            stale_den += len(cur)
            # realised F1 acting on the (stale) RF decision from frame t-d, evaluated on frame t
            acts = rf_act[past]
            f1_sum += eff[cur, [aidx[a] for a in acts]].sum()
            n += len(cur)
        rows.append(dict(delay_frames=d, delay_ms=d * 100,
                         stale_decision_rate=round(stale_num / stale_den, 4),
                         realised_f1_stale=round(f1_sum / n, 4)))
    out = pd.DataFrame(rows)
    # F1 drop vs d=0
    base = out.loc[out.delay_frames == 0, 'realised_f1_stale'].iloc[0]
    out['f1_drop_vs_d0'] = (base - out['realised_f1_stale']).round(4)
    out.to_csv(os.path.join(C.OUTDIR, 'a5_causality.csv'), index=False)
    print('=== A5: decision staleness vs request/round-trip delay (OPV2V test, 10 Hz) ===')
    print(out.to_string())


if __name__ == '__main__':
    main()
