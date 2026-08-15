# P4-B second-backbone arm — §8 anomaly checklist

**second-backbone arm, not deployed.** Descriptive with paired CIs; no decision is taken here and `delta` is untouched. §8 handling rule 3 applies throughout: where an expectation and the measurement disagree, the finding changes, not the data.

| # | expectation | result |
|---|---|---|
| 1 | validate mean payload <= B_max at every budget | PASS |
| 2 | no C256 in the deployed action distribution | PASS |
| 3 | Rayleigh shows BOTH E and L for the selector (not 100% L) | **FUSE** |
| 4 | AWGN high-SNR F share does not fall | PASS |
| 5 | one frozen model + lambda*/tau* per budget, no per-split refit | PASS |
| 6 | selector-vs-oracle agreement holds off validate (>= 0.75) | **FUSE** |
| 7 | paired dF vs tau is non-negative off validate | **FUSE** |

**3 of 7 expectations not met.**


### PASS — validate mean payload <= B_max at every budget

B=0.1: pay=0.04654; B=0.2: pay=0.18537; B=0.3: pay=0.18537

### PASS — no C256 in the deployed action distribution

action columns: ['rf_E', 'rf_L', 'rf_F', 'or_E', 'or_L', 'or_F']

### FUSE — Rayleigh shows BOTH E and L for the selector (not 100% L)

culver B=0.1: rf_E=0.0000 rf_L=1.0000 (oracle E=0.3018); culver B=0.2: rf_E=0.0000 rf_L=1.0000 (oracle E=0.3018); culver B=0.3: rf_E=0.0000 rf_L=1.0000 (oracle E=0.3018); test B=0.1: rf_E=0.0037 rf_L=0.9963 (oracle E=0.3525); test B=0.2: rf_E=0.0164 rf_L=0.9836 (oracle E=0.3525); test B=0.3: rf_E=0.0164 rf_L=0.9836 (oracle E=0.3525); validate B=0.1: rf_E=0.1485 rf_L=0.8515 (oracle E=0.1419); validate B=0.2: rf_E=0.1419 rf_L=0.8581 (oracle E=0.1419); validate B=0.3: rf_E=0.1419 rf_L=0.8581 (oracle E=0.1419)

### PASS — AWGN high-SNR F share does not fall

culver B=0.1: F share 0.0000 (<=6 dB) -> 0.0000 (>=14 dB); culver B=0.2: F share 0.0000 (<=6 dB) -> 0.0331 (>=14 dB); culver B=0.3: F share 0.0000 (<=6 dB) -> 0.0331 (>=14 dB); test B=0.1: F share 0.0000 (<=6 dB) -> 0.0001 (>=14 dB); test B=0.2: F share 0.0000 (<=6 dB) -> 0.0562 (>=14 dB); test B=0.3: F share 0.0000 (<=6 dB) -> 0.0562 (>=14 dB); validate B=0.1: F share 0.0000 (<=6 dB) -> 0.0980 (>=14 dB); validate B=0.2: F share 0.0000 (<=6 dB) -> 0.5702 (>=14 dB); validate B=0.3: F share 0.0000 (<=6 dB) -> 0.5702 (>=14 dB)

### PASS — one frozen model + lambda*/tau* per budget, no per-split refit

B=0.10: cand#66 cw=balanced lam*=0.1 tau*=18.0; B=0.20: cand#78 cw=balanced lam*=0.02 tau*=12.0; B=0.30: cand#78 cw=balanced lam*=0.02 tau*=8.0

### FUSE — selector-vs-oracle agreement holds off validate (>= 0.75)

culver: 0.5340; test: 0.5784; validate: 0.8327

### FUSE — paired dF vs tau is non-negative off validate

validate B=0.1: dF=+0.00580 [+0.00573,+0.00587]; validate B=0.2: dF=+0.00949 [+0.00942,+0.00957]; validate B=0.3: dF=+0.00811 [+0.00805,+0.00818]; test B=0.1: dF=-0.00139 [-0.00145,-0.00134]; test B=0.2: dF=-0.00473 [-0.00483,-0.00464]; test B=0.3: dF=-0.00659 [-0.00670,-0.00648]; culver B=0.1: dF=-0.00293 [-0.00303,-0.00283]; culver B=0.2: dF=-0.01170 [-0.01189,-0.01150]; culver B=0.3: dF=-0.01671 [-0.01692,-0.01649]
