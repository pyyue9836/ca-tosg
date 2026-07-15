#self+ INVARIANCE note (highest-risk item, 2026-07-15): does the 2.5/3.2/4.5% C256 frontier share rest on
# the CORRECTED payload account, or on an invalid lambda-rescale of the old (uncoded) one?
#
# DERIVATION (one line): the frontier is per-frame argmax_a (eff_a - lam * B_a). The payload correction kept
# B_L = 0.024 fixed but doubled B_C16 (0.495->0.99) and B_C256 (0.2475->0.495). No single lam' satisfies
# eff_a - lam'*B_old,a == eff_a - lam*B_new,a for ALL a: the L term forces lam'=lam, the C16 term forces
# lam'=2*lam. So the correction is NOT a lambda-reparametrisation; lam>0 decisions genuinely change, and the
# frontier MUST be recomputed on the corrected PAYVEC (not rescaled). "F1/edges byte-identical" holds only at
# lam=0 (payload term vanishes -> pure-eff argmax -> invariant).
#
# CHECK (verification-derive-not-hardcode): for each committed frontier row, derive payload from the frac
# columns under BOTH payvecs and compare to the committed `payload` column. If it reconciles with NEW and NOT
# with OLD, the committed frontier (hence the 2.5/3.2/4.5% C256 share) is the corrected-payload object -> the
# invariance question is SAFE (recomputed, not rescaled). If it matches OLD -> STOP: the share is stale, a
# recompute/retrain decision, not a paragraph edit.
import os, pandas as pd, numpy as np
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results/policy_v3')
NEW = {'L': 0.024, 'C16': 0.99, 'C256': 0.495}      # corrected (rate-1/2 coded)
OLD = {'L': 0.024, 'C16': 0.495, 'C256': 0.2475}    # stale (uncoded)
rows = []
for sp in ('validate', 'test', 'culver'):
    d = pd.read_csv(os.path.join(R, f'frontier_{sp}.csv'))
    pay_new = d.frac_L * NEW['L'] + d.frac_C16 * NEW['C16'] + d.frac_C256 * NEW['C256']
    pay_old = d.frac_L * OLD['L'] + d.frac_C16 * OLD['C16'] + d.frac_C256 * OLD['C256']
    err_new = float(np.abs(pay_new - d.payload).max())   # committed payload reconciles with NEW?
    err_old = float(np.abs(pay_old - d.payload).max())   # ... or with OLD?
    rows.append(dict(split=sp, max_frac_C256=round(float(d.frac_C256.max()), 5),
                     reconcile_err_NEW=round(err_new, 5), reconcile_err_OLD=round(err_old, 5),
                     frontier_is_corrected=bool(err_new < 1e-3 and err_old > 1e-2)))
out = pd.DataFrame(rows)
out.to_csv(os.path.join(os.path.dirname(R), 'frontier_payload_invariance.csv'), index=False)
print(out.to_string(index=False))
verdict = bool(out.frontier_is_corrected.all())
print(f"\nfrontier_is_corrected (payload reconciles with NEW, not OLD) all splits = {verdict}")
print("=> 2.5/3.2/4.5% C256 frontier share is the CORRECTED-payload object; INVARIANCE safe (recomputed, "
      "not lambda-rescaled)." if verdict else "=> STOP: frontier is stale, recompute/retrain decision.")
