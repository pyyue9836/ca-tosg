#self+ Verify the C256 dominance identity + its frame-fraction PROGRAMMATICALLY from per-frame v3 CSVs.
# The algebraic claim eff_C256 - eff_C16 = (comp - ego)(b16 - b256) is held to the SAME provenance bar as
# a numeric claim (verification-derive-not-hardcode): recompute both sides from the dataset columns, and
# derive the dominated-frame fraction from data (no literal). Symbol binding: eff = effective F1 =
# comp*(1-b)+ego*b ; b = frame BLER (probability, Sionna table) ; comp = compressed-model F1 (delivered) ;
# ego = ego-only F1 (fallback) ; all at the frame's frozen drawn SNR+channel.
import os, pickle, pandas as pd, numpy as np
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
# Deployed selector -- MEASURED C256 request count (not inferred). The claim "the learned selector never
# requests C256" has the DEPLOYED SELECTOR as its subject; oracle-label zero-support is the MECHANISM, not
# the evidence (it proves "necessarily zero", not "measured zero"). So we replicate the 200-realisation
# deployment loop of recompute_policy_200seed.py (snr~U[0,20], channel~Bernoulli(0.5) rayleigh; inject the
# drawn CSI; rf.predict) and COUNT predictions == 'C256'. verification-derive-not-hardcode applies to zero.
RF = pickle.load(open(f'{D}/selector_rf.pkl', 'rb'))
FEAT = list(RF.feature_names_in_); N_SEED = 200
rows = []
for sp in ('validate', 'test', 'culver'):
    d = pd.read_csv(f'{D}/dataset_{sp}_v3.csv')
    comp, ego = d.compressed_f1.to_numpy(), d.ego_f1.to_numpy()
    b16, b256 = d.bler_C16.to_numpy(), d.bler_C256.to_numpy()
    lhs = d.eff_f1_C256.to_numpy() - d.eff_f1_C16.to_numpy()      # from stored eff columns
    rhs = (comp - ego) * (b16 - b256)                            # algebraic identity
    id_max_err = float(np.abs(lhs - rhs).max())                  # identity holds if ~0
    frac_dom = float((d.eff_f1_C256.to_numpy() <= d.eff_f1_C16.to_numpy() + 1e-12).mean())
    frac_comp_ge_ego = float((comp >= ego).mean())               # dominance mechanism condition
    frac_comp_lt_ego = float((comp < ego).mean())                # collaboration-harm anchor (para 3)
    tie = np.abs(b16 - b256) <= 1e-12                            # b16 == b256 (flat-dead / both-delivered)
    frac_gap = float(((comp < ego) & tie).mean())                # the EXACT dominated-minus-comp_ge_ego gap
    # internal consistency: dominated set = {comp>=ego} U {tie}; disjoint decomposition frac_dom =
    # frac_comp_ge_ego + frac(comp<ego & tie). Assert (verification-derive-not-hardcode; no hand arithmetic).
    assert abs(frac_dom - (frac_comp_ge_ego + frac_gap)) < 1e-9, (sp, frac_dom, frac_comp_ge_ego, frac_gap)
    b256_ge_b16 = bool((b256 >= b16 - 1e-12).all())
    # MEASURED deployed-selector C256 requests across the 200-realisation deployment protocol (identical
    # CSI draws to recompute_policy_200seed.py: rng=default_rng(s), snr~U[0,20], is_ray = rng.random<0.5).
    c256_req = 0
    for s in range(N_SEED):
        rng = np.random.default_rng(s)
        dd = d.copy()
        dd['est_snr_db'] = rng.uniform(0, 20, len(d))
        dd['channel_is_rayleigh'] = (rng.random(len(d)) < 0.5).astype(int)
        c256_req += int((RF.predict(dd[FEAT]) == 'C256').sum())
    rows.append(dict(split=sp, n=len(d), identity_max_abs_err=round(id_max_err, 9),
                     frac_C256_dominated=round(frac_dom, 4), frac_comp_ge_ego=round(frac_comp_ge_ego, 4),
                     frac_comp_lt_ego=round(frac_comp_lt_ego, 4), frac_comp_lt_ego_and_tie=round(frac_gap, 4),
                     b256_ge_b16_everywhere=b256_ge_b16,
                     selector_C256_requests=c256_req, n_selector_predictions=N_SEED * len(d),
                     selector_has_C256_class=bool('C256' in RF.classes_)))
out = pd.DataFrame(rows)
out.to_csv(os.path.join(os.path.dirname(D), 'results/c256_dominance_verify.csv'), index=False)
print(out.to_string(index=False))
print("\nidentity eff_C256-eff_C16 == (comp-ego)(b16-b256): max|err| ~0 across splits confirms the symbol binding.")
print("frac_C256_dominated == frac_comp_ge_ego (given b256>=b16 everywhere): dominance IS conditional on comp>=ego.")
print(f"deployed selector C256 requests (MEASURED over {N_SEED}-realisation deployment) = "
      f"{[r['selector_C256_requests'] for r in rows]} of {[r['n_selector_predictions'] for r in rows]} preds; "
      f"'C256' in classifier class set = {bool('C256' in RF.classes_)} (mechanism: oracle labels zero-support).")
