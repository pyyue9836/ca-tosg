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

RESIDUAL (a) -- B-class scripts, "what the stale dict feeds" (one line each; supervisor 2026-07-15):
- train_rf_multiseed.py: the PAYLOAD dict fills a REPORTED payload column only (best_method_by_f1 / best_f1
  -> selection is by F1, `best_payload_Mbit` is a label of the F1-chosen method). NO model/seed/method
  selection is payload-weighted. => report-only: multiseed_hardening.csv's pay_* columns are stale (halved),
  but NO committed DECISION was made under the old account. Model selection is F1-only; all committed metrics
  that are payloads must be re-derived under the corrected account, but no retrain is implied.
- e2e_inference_verify.py, test_split_pipeline/04_eval_rf_on_test.py: same -- PAYLOAD labels the payload
  column of already-decided actions (from the deployed selector); report-only, no selection influence.
The DEPLOYED selector itself (train_rf.py) imitates lambda=0 masked-argmax oracle labels -> payload-
independent by construction; no committed decision is under the old account.

RESIDUAL (b) -- family EXHAUSTIVE (supervisor: the 7th name appeared silently; declare the total + closure).
Unambiguous-fingerprint grep (`0.2475` / `1.98/4` / `1.98/8` in live .py, excluding comments/data/logs and
the correction-documenting scripts) => EXACTLY 6 live stale-hardcode scripts: plot_pareto_payload,
snr_decision_plot (Class A); train_rf_multiseed, e2e_inference_verify, 04_eval_rf_on_test (Class B);
csi_noise_ablation (Class C). The list is CLOSED at 6. plot_with_rf uses `1.98` flat (perception payload, not
a channel-use /4 or /8) -> NOT in this family; flagged separately for intent confirmation only.
