#self+ CA-TOSG P1 Step-4 discussion artifact: "collaboration is sometimes harmful".
# -*- coding: utf-8 -*-
"""frac(ego_f1 > late_f1) per split -- the fraction of frames where single-vehicle ego-only
detection BEATS multi-vehicle late fusion (the collaborator's boxes net-introduce false positives).
This is the phenomenon the feasibility-masked oracle exposed: on a guaranteed-failure channel the
payload-blind oracle used to prefer a failed C-request (-> ego fallback) over L, precisely on these
frames. The mask removes that artifact from the LABEL; the phenomenon itself is a free paper
discussion point (§5.1.1 action-space review: an explicit 'do-not-request' ego-only 4th action is
free in the 2-bit codebook -- '11' is reserved). Writes results/step4_collaboration_harm_v3.csv.
"""
import os
import numpy as np
import pandas as pd

P1 = '/home/josh/cooperative_semantic_perception/OpenCOOD/peiyi_work/paper1'
DATA = os.path.join(P1, 'data'); RESULTS = os.path.join(P1, 'results')


def main():
    rows = []
    for sp in ('validate', 'test', 'culver'):
        d = pd.read_csv(os.path.join(DATA, f'dataset_{sp}_v3.csv'))
        ego = d['ego_f1'].to_numpy(); late = d['late_f1'].to_numpy()
        harm = ego > late
        rows.append(dict(
            split=sp, n=len(d),
            frac_ego_gt_late=round(float(harm.mean()), 4),
            n_ego_gt_late=int(harm.sum()),
            mean_ego_f1=round(float(ego.mean()), 4),
            mean_late_f1=round(float(late.mean()), 4),
            mean_ego_minus_late_on_harm=round(float((ego - late)[harm].mean()), 4) if harm.any() else 0.0))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RESULTS, 'step4_collaboration_harm_v3.csv'), index=False)
    print(out.to_string(index=False))
    print('\nwrote results/step4_collaboration_harm_v3.csv')


if __name__ == '__main__':
    main()
