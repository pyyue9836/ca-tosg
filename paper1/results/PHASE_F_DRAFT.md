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
3. **JSCC two-regime edge** (Track A, DONE 2026-07-12, results/jscc_v3/two_regime_edge_v3.csv): under the
   graceful JSCC codec (no cliff) cues pay in ACCURACY. RF - best-tau edge, 200-real, frame-level paired
   95% CI, ALL significant:
       awgn      LDPC +0.0033/+0.0047 (val/test)   JSCC +0.0044/+0.0266
       rayleigh  LDPC +0.0004/+0.0019               JSCC +0.0040/+0.0223
   JSCC edge is 1.3x-12x the LDPC edge, LARGEST on the hard channels (test, rayleigh). The SNR threshold
   is structurally useless under JSCC (best-tau=20 or 0; JSCC F1 is ~SNR-flat, no cliff) -> the JSCC-side
   selector value is ENTIRELY perception-cue. JSCC F1 curves confirm graceful (awgn ~0.81 val/~0.89 test,
   rayleigh ~0.81/~0.88, ofdm 0.79-0.82 with a low-SNR-0dB dip). Interp bias <=0.0012 (JSCC side only).

### SHARPER SUB-FINDING (Rayleigh): codec response determines FEASIBILITY, not just currency
On Rayleigh the frame BLER is 1 across 0-20 dB, so DIGITAL LDPC feature transmission is INFEASIBLE -- the
selector collapses to all-L and the LDPC edge is ~0 (+0.0004 val / +0.0019 test; RF payload 0.03/0.07 =
mostly L). ANALOG JSCC survives the fading (no cliff) and the selector extracts +0.0040/+0.0223 -- a
~10-12x edge gap on the SAME channel. Under deep fading the codec choice decides whether feature-level
cooperation is POSSIBLE at all, not merely how the cues pay. This is the strongest single figure in the
two-regime story and the direct HARQ / analog-JSCC-advantage motivation.

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
