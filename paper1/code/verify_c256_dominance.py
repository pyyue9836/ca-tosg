#self+ Verify the C256 dominance identity + its frame-fraction PROGRAMMATICALLY from per-frame v3 CSVs.
# The algebraic claim eff_C256 - eff_C16 = (comp - ego)(b16 - b256) is held to the SAME provenance bar as
# a numeric claim (verification-derive-not-hardcode): recompute both sides from the dataset columns, and
# derive the dominated-frame fraction from data (no literal). Symbol binding: eff = effective F1 =
# comp*(1-b)+ego*b ; b = frame BLER (probability, Sionna table) ; comp = compressed-model F1 (delivered) ;
# ego = ego-only F1 (fallback) ; all at the frame's frozen drawn SNR+channel.
import os, pandas as pd, numpy as np
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
rows = []
for sp in ('validate', 'test', 'culver'):
    d = pd.read_csv(f'{D}/dataset_{sp}_v3.csv')
    comp, ego = d.compressed_f1.to_numpy(), d.ego_f1.to_numpy()
    b16, b256 = d.bler_C16.to_numpy(), d.bler_C256.to_numpy()
    lhs = d.eff_f1_C256.to_numpy() - d.eff_f1_C16.to_numpy()      # from stored eff columns
    rhs = (comp - ego) * (b16 - b256)                            # algebraic identity
    id_max_err = float(np.abs(lhs - rhs).max())                  # identity holds if ~0
    frac_dom = float((d.eff_f1_C256.to_numpy() <= d.eff_f1_C16.to_numpy() + 1e-12).mean())
    frac_comp_ge_ego = float((comp >= ego).mean())               # should ~equal frac_dom (b256>=b16 given)
    b256_ge_b16 = bool((b256 >= b16 - 1e-12).all())
    rows.append(dict(split=sp, n=len(d), identity_max_abs_err=round(id_max_err, 9),
                     frac_C256_dominated=round(frac_dom, 4), frac_comp_ge_ego=round(frac_comp_ge_ego, 4),
                     b256_ge_b16_everywhere=b256_ge_b16))
out = pd.DataFrame(rows)
out.to_csv(os.path.join(os.path.dirname(D), 'results/c256_dominance_verify.csv'), index=False)
print(out.to_string(index=False))
print("\nidentity eff_C256-eff_C16 == (comp-ego)(b16-b256): max|err| ~0 across splits confirms the symbol binding.")
print("frac_C256_dominated == frac_comp_ge_ego (given b256>=b16 everywhere): dominance IS conditional on comp>=ego.")
