# Phase F draft — CANDIDATE framings for the v3 rewrite (NOT locked)

Working notes for the main.tex rewrite once Step-5 lands. Everything here is CANDIDATE until the JSCC
edge (Track A) is in and the three evidence lines are confirmed to interlock.

## CANDIDATE central finding — "task cues change currency, not existence"
> **Codec response determines the currency in which task cues pay: bandwidth under cliff codecs,
> accuracy under graceful codecs.**

This SUPERSEDES the v2 binary ("cues needed / not needed"). It is more precise, harder to argue with,
and rests on three interlocking evidence lines — DO NOT lock the wording until line 3 (JSCC edge) lands.

Evidence lines (all under the v3 canonical protocol: 200 real. + v3 GT + Sionna frame BLER + ego):
1. **RF vs retuned-tau Pareto dominance** (results/policy_v3/threshold_vs_rf.csv): at MATCHED bandwidth,
   RF > tau on all 3 splits, frame-level paired 95% CI excludes 0 (+0.00194/+0.00049/+0.00325). A
   channel-only threshold must OVER-transmit 46-86% payload to match RF's F1 -> cues buy bandwidth.
2. **a7 feature ablation** (results/ablation_v3/a7_cue_value_v3.csv): over channel state alone, cues add
   -0.00024 F1 (NOT significant, "cues add <0.001" holds) BUT save payload (Full vs Channel-only,
   frame-level CI: see a7 run) -> under the LDPC cliff codec, cues pay in BANDWIDTH not accuracy.
3. **JSCC two-regime edge** (Track A, PENDING): under the graceful JSCC codec (no cliff), cues are
   expected to pay in ACCURACY (the v2 +0.017 side) -- to be measured under v3 GT, per-channel edge with
   frame-level paired CI, validate & test separate. NO direction predicted (supervisor down-weighted his
   own direction calls after 4 data-driven corrections; acceptance = structure only).

## Error-path assignment (keep the two regimes' uncertainties SEPARATE)
- JSCC side carries the interpolation systematic term: aggregate bias <=0.0012 (mid-grid probe, SNR 10),
  an order below the edge (~0.015). Wording: "interpolation-induced aggregate bias <=0.0012 (mid-grid
  probe), an order below the measured edge."
- LDPC side goes through the Sionna BLER table and NEVER touches JSCC interpolation. The 0.0012 must NOT
  be set against the LDPC +0.0005 edge. State which error path attaches to which regime so a reviewer
  does not wrongly divide.

## v2->v3 differences to DECLARE explicitly (not silently substitute)
- Absolute F1 basis shifted ~+0.045 from the canonical-GT change alone: v2 0.8656 and v3 0.9108 are NOT
  comparable across tables.
- Oracle/RF payloads ROSE vs v2 (ego floor + higher Sionna BLER); the "15.8-18.4% of Fixed C16" band
  does NOT return -- not chased.
- a2 difficulty "reliable-channel" condition redefined: v2 sampled est_snr>=14 dB (a frozen-frame
  subset) -> v3 deterministic AWGN 16 dB (a conditional; the channel is now a per-realisation draw). 14
  ->16 because the frame cliff moved to ~8 dB.
- Frame cliff moved 12-14 dB (v2 codeword) -> ~8 dB (Sionna frame-level); Rayleigh infeasible across
  0-20 dB (frame BLER=1) -> all policies collapse to L on Rayleigh (HARQ-motivation sentence).
- C256 = lambda=0 dominance theorem + lambda>0 empirical minority foothold (<=5% spread across the
  low-payload region 0.024-0.13 Mbit, never a majority).
