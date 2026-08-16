# SComCP baseline — pre-registered fuse check (SC-2)

**descriptive baseline, no decision.** Conditions and references are the ones registered before the run; every reference is read from a committed product.

| fuse | condition | result |
|---|---|---|
| F1 | validate AP@0.5 at 20 dB AWGN below the Fixed-L reference | **FIRED** |
| F2 | per-frame F1 flat in SNR (span < 0.005) | **FIRED** |

## F1

validate AWGN 20 dB AP@0.5 = 0.7262 vs Fixed-L reference 0.8902 (delta -0.1640); ego-only floor 0.6116, perfect-channel ceiling 0.9169

## F2

test/awgn: F1 span over the 11-point grid = 0.0003 (mean 0.8374); test/rayleigh: F1 span over the 11-point grid = 0.0003 (mean 0.8374); validate/awgn: F1 span over the 11-point grid = 0.0001 (mean 0.8318); validate/rayleigh: F1 span over the 11-point grid = 0.0001 (mean 0.8318)

## Supporting observations

- com_rate is constant within each split: test: 0.004699..0.004699 (1 distinct value); validate: 0.004972..0.004972 (1 distinct value)
- validate: max |AWGN - Rayleigh| per-frame F1 across the grid = 0.0001 -- the two channels are indistinguishable
- test: max |AWGN - Rayleigh| per-frame F1 across the grid = 0.0003 -- the two channels are indistinguishable
- ImportanceMapJSCC on the same split/channel spans 0.8106..0.8156 (span 0.0050) over its SNR points. NOTE: near-flatness is a KNOWN and expected property of that codec (graceful degradation), so F2 on its own does not separate "codec is graceful" from "codec is not engaged" -- the AWGN-vs-Rayleigh identity and the perfect-channel diagnostic below are what separate them
- PERFECT-CHANNEL DIAGNOSTIC (validate, lossless): F1 0.8318 / AP@0.5 0.7261 / com_rate 0.004972 -- versus AWGN 20 dB 0.8319/0.7262 and Rayleigh 0 dB 0.8318/0.7261. A lossless channel and the worst modelled channel give the SAME result to 1e-4, so the channel path is INERT: this is not graceful degradation, the transmitted representation is contributing essentially nothing.
- ROOT CAUSE (diagnosed, not asserted): com_rate = 0.004972 means the trained selector keeps ~0.50% of tokens, so there is almost no remote content for any channel to corrupt, and the fused output is determined by the ego branch. AP@0.5 0.7261 sits between the ego-only floor 0.6116 and Fixed-L 0.8902, consistent with a near-ego-only output.

## Reading (pre-registered)

A fired fuse here is a **scaffold / training-budget finding, not a finding about SComCP as a method**, and the two may not be conflated in any write-up. The arm is reported as-is; nothing was retrained, no data was adjusted, no hyperparameter was changed after seeing these numbers.
