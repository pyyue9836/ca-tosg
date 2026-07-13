# Phase F edit map — main.tex v2->v3 number/claim substitution ledger

Every stale v2 number in main.tex (909 lines) mapped to its v3 replacement + source. `[OFDM]` = awaits
the OFDM BLER table (running). Do the substitution as one reviewable batch; OFDM-tagged rows land after
the table + supervisor pin the TR 37.885 delay-spread value. Sources: results/policy_v3/*,
results/ablation_v3/*, results/jscc_v3/*.

## LOCKED framing (currency) — central claim, done this turn
- L70 (intro central finding) + L34 (abstract): "codec response determines the CURRENCY in which task
  cues pay: bandwidth under cliff codecs, accuracy under graceful codecs" + Rayleigh feasibility
  sub-finding. Qualitative wording LOCKED (3 evidence lines confirmed). Numbers below.

## Headline / generalisation tables (tab:headline, tab:gen_headline; L~350-605) — v3, NO OFDM dep
Source: results/policy_v3/generalisation_{split}.csv (200-real, canonical GT v3).
| policy | validate F1@pay | test F1@pay | culver F1@pay |
|---|---|---|---|
| Channel-aware oracle | 0.9129@0.0886 | 0.9140@0.0995 | 0.8891@0.1378 |
| Clairvoyant upper (NEW row) | 0.9139@0.0969 | 0.9170@0.1228 | 0.8900@0.1386 |
| CA-TOSG (RF) | 0.9108@0.1015 | 0.9088@0.1346 | 0.8831@0.0894 |
| SNR-threshold (retuned) | 0.9100@0.1481 (tau9.5) | 0.9096@0.1599 (tau8.5) | 0.8874@0.1661 (tau8.0) |
| Fixed L | 0.9067@0.024 | 0.9011@0.024 | 0.8722@0.024 |
| Fixed C16 | 0.7907@0.495 | 0.8519@0.495 | 0.8166@0.495 |
| Fixed C256 | 0.7499@0.2475 | 0.8263@0.2475 | 0.7811@0.2475 |
- v2 tab:gen_headline rows (0.074/0.887/0.888 test; 0.097/0.891 culver) all REPLACED.
- Selector accuracy (rf_full acc): validate 0.9234 (in-sample), test 0.8535, culver 0.8703 (was 88.9/91.3).
- C-activation (oracle C base-rate): test 0.160, culver 0.2415 (was ~11%). always-L base rate: test 0.8394,
  culver 0.7585 (was 0.895/0.845).
- oracle-F1 recovery = RF/oracle: validate 99.8%, test 99.4%, culver 99.3% (was 99.4/99.6 — HOLDS).

## Payload wording -> CHANNEL USES + band update (whole-paper unit sweep)
- Payload accounting -> channel uses: C coefficients x2 (C16 0.495->0.99 ch-use? NO -- 0.495 IS already the
  Mbit channel-use-equiv; supervisor's "x2" = express the two C variants' CHANNEL USES: C16 1.98/4=0.495,
  C256 1.98/8=0.2475 Mbit-eq; L stays 0.024). SWEEP the whole paper: label payload axis "Mbit channel-use
  equivalent" consistently; L unchanged. (Verify each Mbit figure/caption uses channel-use-eq, not raw info bit.)
- "15.8-18.4% of Fixed C16 bandwidth" (abstract L34, obs, captions) -> GONE. v3 RF payload/0.495 = validate
  20.5% / test 27.2% / culver 18.1% => new band "18-27% of Fixed C16" (per-split; NO single-threshold claim).
- v2 payloads 0.074/0.081/0.085 (oracle/test/culver) -> v3 oracle 0.089/0.100/0.138; RF 0.102/0.135/0.089.

## Central-finding numbers (currency) — PARTIAL v3, [OFDM] for the OFDM edge
Source: results/jscc_v3/two_regime_edge_v3.csv + results/ablation_v3/a7_cue_value_v3.csv.
- LDPC cliff -> cues buy BANDWIDTH: a7 Full vs Channel-only F1 -0.00024 [-.00052,+.00003] NOT sig; PAYLOAD
  -0.01495 [-.01689,-.01306] SIG (cues save ~10% bandwidth at equal F1). + RF Pareto-dominates retuned tau
  at matched payload: +0.00194/+0.00049/+0.00325 (val/test/culver), frame CI excludes 0 (threshold_vs_rf.csv).
- Graceful JSCC -> cues buy ACCURACY: RF-tau edge awgn +0.0044/+0.0266 (val/test), rayleigh +0.0040/+0.0223;
  threshold structurally useless (best-tau=20/0). [OFDM edge pending table.] REPLACES v2 "+0.017 [+.012,+.022]".
- Rayleigh FEASIBILITY sub-finding: LDPC edge +0.0004/+0.0019 (~0, all-L) vs JSCC +0.0040/+0.0223 (~10-12x).
  => "codec decides feasibility, not just currency". [OFDM refines this: diversity opens a window? pending.]
- Selector-side "SNR/ch-type = 65% importance" -> recompute from v3 feature_importance (a7: channel state
  dominates; a7 channel-only F1 0.9089 ~ full 0.9086). [need v3 feature_importance CSV -- TODO regen.]

## Difficulty / gain-concentration (sec:difficulty, L676+) — v3, NO OFDM dep
Source: results/ablation_v3/a2_difficulty*.csv (200-real, frame paired CI).
- "up to +0.045 F1 on hard frames" -> v3 all-channel hard gain +0.0095/+0.0240/+0.0264 (val/test/culver, sig);
  RELIABLE-channel (AWGN 16dB) hard gain +0.0347/+0.0896/+0.1064 => "up to +0.09-0.11 F1 on hard frames under
  a reliable channel". DECLARE the condition redefine (v2 sampled snr>=14 -> v3 deterministic 16 dB).
- Easy-stratum gain SIG NEGATIVE (test -0.0147) = collaboration-sometimes-harmful; NEW honest sentence.

## Robustness (sec 4.4.4) — v3, NO OFDM dep. Source: results/ablation_v3/robustness_*_v3.csv
- csi_noise@5dB 0.0037 [.0035,.0038] / aging@50ms 0.0044 [.0042,.0047] / staleness@1fr 0.0193 [.0184,.0203]
  (was 0.003/0.015/0.057; aging+staleness LOWER = more robust). All frame-level paired CI, all sig.
- "lighter models same accuracy" -> precisely within 0.003 F1 (a8: DT/LogReg/SVM/MLP 0.906-0.907 vs RF 0.9086)
  at 15-18x lower latency (0.8-1.1 vs 13.9 ms). Latency 52.8 ms (abstract) vs 13.9 ms (a8) -- unify protocol note.

## Ledger items (supervisor) — prose, mostly no number dep
- CoDS positioning paragraph (related work) -- NEW.
- L583/L605: "CSI" label -> "estimated SNR + channel-type indicator" (NOT CSI -- reviewer landmine). Body
  per-split numbers per the tables above.
- v2->v3 bridge paragraph: F1 basis +~0.045 from canonical-GT change (v2 0.8656 vs v3 0.9108 NOT comparable);
  payload band moved; cliff 12-14->8 dB (Sionna frame-level); a2 condition redefine; C256 dominance+foothold.
- HARQ motivation sentence: Rayleigh frame BLER=1 across 0-20 dB (flat, no diversity) -> feature infeasible
  -> HARQ/retransmission or [OFDM] frequency diversity needed. [OFDM result sharpens this.]
- C256: lambda=0 dominance theorem + lambda>0 minority foothold (<=5% across low-payload region 0.024-0.13 Mbit).

## OFDM-DEPENDENT (hold until bler_sionna_ofdm.csv merged + TR 37.885 value pinned)
- Figure A OFDM-LDPC panels; two-regime OFDM edge (both regimes); the Rayleigh->diversity feasibility
  refinement in the sub-finding + HARQ sentence; abstract/intro "+0.015 under OFDM" number.
