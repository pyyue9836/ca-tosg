# DEPRECATED -- v2 difficulty-stratum artifacts. DO NOT read; DO NOT cite.
Second poster for the stale-artifact protocol (after the payload orphans) -- and this one did not lie
passively: it actively supplied a WRONG number that briefly replaced a correct one (the -0.0134/n=108 that
the agent swapped in for the correct v3 -0.0147/n=713 after a scope-less negative-existence claim).

STALE (Jun-17 v2; est_snr>=14 "good channel" stratum def; NO CI; no live reader found in code/):
- results/difficulty_strata_goodchannel.csv   (test Easy -0.0134, n=108)  -- the number the agent wrongly used
- results/difficulty_strata.csv               (all-channel, act_ cols, no CI)

CANONICAL v3 (Jul-13; deterministic reliable channel AWGN 16 dB; WITH frame-level paired CIs):
- code/extra_experiments/out/a2_difficulty_reliable_v3.csv  (test Easy -0.0147, 95% CI [-0.0179,-0.0115], n=713)
- code/extra_experiments/out/a2_difficulty_v3.csv           (all-channel 200-real, with CIs)

Rule (same as the payload orphans): a superseded artifact is either regenerated or marked DEPRECATED here.
The v3 threshold moved 14->16 dB for a documented reason (cliff ~8 dB; a2_difficulty.py) -- but that
v2->v3 rationale is INTERNAL (ledger: the paper presents v3 only, no version comparison).
