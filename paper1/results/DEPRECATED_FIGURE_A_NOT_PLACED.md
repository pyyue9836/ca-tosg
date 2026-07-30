# Figure A (channel_codec_ap 9-panel) -- APPROVED FIGURE-OUT, NOT PLACED IN MANUSCRIPT

Explicit decision (final-gate, figure-side). NOT an evaporation.

## What happened
- The 9-panel channel_codec_ap figure was generated to the frozen convention and its
  caption sentence (OFDM-LDPC ~24 dB feasibility threshold, empirical diversity order ~2)
  was ruled "prose + caption both". Figure-out artifact: fig_channel_codec_ap_test.pdf
  (approval commit 85e4b72), retained in paper/figures/ as the archived render.
- git log -S "channel_codec_ap" -- paper/main.tex is EMPTY: \includegraphics for this
  figure NEVER appeared in main.tex in any commit. It was approved-out but never landed.

## Decision: not placed in the final manuscript (TVT page constraint)
Verified there is NO orphaned claim -- the OFDM/diversity-order/~24 dB LDPC-feasibility
finding is carried in full by:
- intro L70 prose: "8 dB on AWGN, ~24 dB under OFDM (empirical diversity order ~2), and
  unbounded under flat Rayleigh";
- ablation prose (sec:ablation): "Rayleigh and OFDM below its ~24 dB threshold, where the
  LDPC block almost always fails, they collapse to the ego floor";
- tab:two_regime: the OFDM JSCC edge (+0.025);
- fig:bler: the AWGN/Rayleigh BLER cliff (16- vs 256-QAM).
The "four flat-dead panels" explanation therefore has a complete prose home; the 9-panel
visual was the only unique content, and it is dropped under page constraints.

## Housekeeping
fig_channel_codec_ap_test.pdf stays in paper/figures/ (archived figure-out, unreferenced).
Supervisor-package note recommended: one line that Figure A was cut for space, its claims
retained in prose/tables (in case an early reviewer/Angela saw a version with it).
