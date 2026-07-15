# INVARIANCE note (highest-risk item; gates the C256 paragraph landing alongside item 12)

The C256 paragraph cites the 2.5/3.2/4.5% C256 frontier share. That number lives on the payload-penalised
(lambda>0) frontier, so it depends on the payload correction being correctly propagated INTO the utility --
not merely into reported summaries. Three checks, all closed:

(a) WHERE the payload dict enters the utility. recompute_policy_200seed.py:127 `obj = eff - lam*PAYVEC + mask`
    then `argmax(1)`; PAYVEC from :45 PAYLOAD = {L:0.024, C16:0.99, C256:0.495} (corrected, rate-1/2 coded).
    This is the ONLY place payload enters the frontier decision.

(b) L payload source and value. B_L = 0.024 Mbit, derived in main.tex L315 (27 objects x ~110 B x 8), an
    OBJECT-level cost -- it did NOT change in the payload correction (only the coded feature modes did). L is
    the fixed anchor that breaks any global rescale (see c).

(c) lambda per-frame equivalence -- DERIVATION (one line): the frontier is argmax_a (eff_a - lam*B_a). The
    correction kept B_L=0.024 but doubled B_C16 (0.495->0.99) and B_C256 (0.2475->0.495). No single lam'
    gives eff_a - lam'*B_old,a == eff_a - lam*B_new,a for ALL a: the L term forces lam'=lam, the C16 term
    forces lam'=2*lam -- contradiction. So the correction is NOT a lambda-reparametrisation; lambda>0
    decisions genuinely change. "F1/edges byte-identical, only payload rescaled" holds ONLY at lambda=0 (the
    payload term vanishes -> pure-eff argmax -> deployed F1/edges truly invariant). The lambda>0 frontier must
    be RECOMPUTED on the corrected PAYVEC, never rescaled.

VERDICT (SAFE, not a stop/retrain): the committed frontier WAS recomputed on the corrected PAYVEC, verified
programmatically (verify_frontier_payload_invariance.py -> frontier_payload_invariance.csv,
verification-derive-not-hardcode): for every committed frontier row, payload reconciles with NEW
(max err 0.00005 all splits) and NOT with OLD (err 0.068/0.079/0.120). frontier_is_corrected=True all splits;
max_frac_C256 = 0.02546/0.03155/0.04517 = the cited 2.5/3.2/4.5%. Therefore the C256 frontier share is the
corrected-payload object and the paragraph's use of it is valid.

HAD the check failed (committed frontier == OLD), this would have been a full-stop recompute/retrain
decision, NOT a paragraph edit -- recorded so the failure branch is explicit.
