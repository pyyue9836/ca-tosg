#self+ CA-TOSG P1 Step-4 discussion artifact: "collaboration is sometimes harmful".
# -*- coding: utf-8 -*-
"""frac(ego_f1 > late_f1) per split -- the fraction of frames where single-vehicle ego-only
detection BEATS multi-vehicle late fusion (the collaborator's boxes net-introduce false positives).
This is the phenomenon the feasibility-masked oracle exposed: on a guaranteed-failure channel the
payload-blind oracle used to prefer a failed C-request (-> ego fallback) over L, precisely on these
frames. The mask removes that artifact from the LABEL; the phenomenon itself is a free paper
discussion point (§5.1.1 action-space review: an explicit 'do-not-request' ego-only 4th action is
free in the 2-bit codebook -- '11' is reserved). Writes results/main/step4_collaboration_harm.csv.
"""
import os
import numpy as np
import pandas as pd

# was an absolute path into the OpenCOOD tree, so this script read the RETIRED cue tables
# and wrote its CSV outside the repository entirely (which is why re-running it changed
# nothing under results/). Repointed to the repo and to the P0-corrected tables.
P1 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))   # 4 levels: evaluation -> ca_tosg -> projects -> root
DATA = os.path.join(P1, 'data/p2'); RESULTS = os.path.join(P1, 'results')


def main():
    rows = []
    for sp in ('validate', 'test', 'culver'):
        d = pd.read_csv(os.path.join(DATA, f'dataset_{sp}_n1.csv'))
        ego = d['ego_f1'].to_numpy(); late = d['late_f1'].to_numpy()
        comp = d['compressed_f1'].to_numpy()
        harm = ego > late
        # R28-4: the second harm quantifier -- the delivered feature message scoring BELOW the
        # ego-only fallback -- was quoted from the pre-corrigendum C256 dominance file (1.0/5.8/0.9%).
        # It is re-derived here from the same N=1 caches as the first one: 1.3/6.5/0.9%.
        harm_f = comp < ego
        rows.append(dict(
            split=sp, n=len(d),
            frac_ego_gt_late=round(float(harm.mean()), 4),
            n_ego_gt_late=int(harm.sum()),
            mean_ego_f1=round(float(ego.mean()), 4),
            mean_late_f1=round(float(late.mean()), 4),
            mean_ego_minus_late_on_harm=round(float((ego - late)[harm].mean()), 4) if harm.any() else 0.0,
            frac_comp_lt_ego=round(float(harm_f.mean()), 4),
            n_comp_lt_ego=int(harm_f.sum()),
            mean_ego_minus_comp_on_harm=(round(float((ego - comp)[harm_f].mean()), 4)
                                         if harm_f.any() else 0.0)))
    out = pd.DataFrame(rows)
    # R28-4: write where the message says. The generator wrote results/step4_collaboration_harm.csv
    # while printing "wrote results/main/..."; the results/main/ copy was a 2026-08-12 pre-corrigendum
    # file nothing regenerated, and both were indexed as products.
    dest = os.path.join(RESULTS, 'main', 'step4_collaboration_harm.csv')
    out.to_csv(dest, index=False)
    print(out.to_string(index=False))
    print('\nwrote results/main/step4_collaboration_harm.csv')


if __name__ == '__main__':
    main()
