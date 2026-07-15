# Hand-written paragraph drafts (agent-drafted per Josh's 2026-07-15 reassignment; Josh reviews wording)

Working file. Each draft here is pending Josh's wording review; only on approval does it enter main.tex
(during the .tex pass). Numbers are CSV-direct from the committed verification artifacts. Section/figure
cross-refs (\S, Fig.) are placeholders to resolve in the .tex pass. Target: 150-250 words, one-pass approval.

## 1. C256 dominance (Method / message candidates) -- FINAL (v2, 9 revisions + hard-error fix applied
## 2026-07-15; supervisor: land without re-review). Deployed-point activation = 0 verified vs CSV (branch 1).

Among the feature-message candidates we also expose a 256-QAM variant (C256), which halves the per-frame
channel use of the 16-QAM feature message (0.495 vs. 0.99 Msym for C256 and C16, respectively[^pay]) and is
thus an apparent bandwidth bargain. The learned selector nonetheless never requests it, for a structural
reason whose scope we verify empirically. The two variants carry the identical feature payload and hence
share comp; writing the effective F1 as $\mathrm{eff}=\mathrm{comp}(1-b)+\mathrm{ego}\,b$ -- the expected
utility of a delivery that reverts to the ego-only fallback with frame-level failure probability $b$ -- they
obey the identity
$\mathrm{eff}_{\mathrm{C256}}-\mathrm{eff}_{\mathrm{C16}}=(\mathrm{comp}-\mathrm{ego})(b_{16}-b_{256})$.[^id]
Since the denser constellation is never better protected ($b_{256}\ge b_{16}$, with equality only where both
flatline or both deliver), the sign is set by $(\mathrm{comp}-\mathrm{ego})$. C256 is thus dominated
($\mathrm{eff}_{\mathrm{C256}}\le\mathrm{eff}_{\mathrm{C16}}$) on 99.7 / 98.5 / 100.0\% of validation / test /
Culver-City frames;[^round] the margin over $\mathrm{frac}(\mathrm{comp}\ge\mathrm{ego})=$ 99.0 / 94.2 /
99.1\% is the 0.7 / 4.2 / 0.9\% of frames where $\mathrm{comp}<\mathrm{ego}$ but $b_{16}=b_{256}$ -- both
flatline, or both deliver at high SNR -- which tie rather than reverse. Dominance reverses only in the
collaboration-harm regime ($\mathrm{comp}<\mathrm{ego}$, $b_{16}<b_{256}$; \S\ref{sec:harm}). Physically,
256-QAM right-shifts the AWGN frame-error cliff from 8.0 to 16.5 dB,[^cliff] while under Rayleigh and OFDM
(0--20 dB) both flatline at the ego floor (frame-level BLER $\approx 1$); no SNR window opens C256 before
C16. We retain C256 for completeness of the 2-bit request codebook: that a rate-matched, lower-channel-use
action is never requested at the deployed operating point, and peaks at only 2.5 / 3.2 / 4.5\% of frames on
the oracle's payload-penalised frontier, is itself a finding.

[^pay]: Feature payload 1.98 Mbit (Eq.~(7)) at LDPC rate-$1/2$ gives 3.96 Mbit of coded bits (Eq.~(11));
$\div 8$ bit/sym (256-QAM) $=0.495$ Msym, $\div 4$ bit/sym (16-QAM) $=0.99$ Msym.

[^id]: comp and ego are the frame's own measured F1; $b$ is the frame-level BLER table value at that frame's
(channel, SNR) grid point -- a per-grid constant. The identity is therefore algebraic and holds by
construction; verification confirms it to $\max|\cdot|=0$, checking the implementation for transcription
error rather than an empirical regularity.

[^round]: Fractions rounded to 0.1 pp. All four come from one run of verify_c256_dominance.py ->
c256_dominance_verify.csv, which asserts $\mathrm{frac\_dominated}=\mathrm{frac}(\mathrm{comp}\ge\mathrm{ego})
+\mathrm{frac}(\mathrm{comp}<\mathrm{ego}\wedge b_{16}=b_{256})$.

[^cliff]: Es/N0 onset at which the frame-level BLER first falls below 0.999 -- the same 0.999 constant that
defines the feasibility mask -- with 16-QAM at 8.0 dB. Fig.~\ref{fig:channel_codec_ap}'s coarse grid renders
this cliff as the 16$\to$20 dB AP transition.

Word count (body, excl. footnotes): ~250. Cross-refs \S\ref{sec:harm}, Fig.~\ref{fig:channel_codec_ap},
Eq.~(7)/(11) are placeholders to resolve in the .tex pass.
### 9 REVISIONS APPLIED (supervisor 2026-07-15): hard-error [deployed never-requests + frontier minority,
### two non-conflicting claims, CSV-verified support 0/0/0]; 1 payload bind-direction + Eq.7/11 provenance;
### 2 "structural...whose scope we verify empirically" (dichotomy dropped); 3 "never better protected" (not
### strictly); 4 shared-payload->shared-comp clause (grounds rate-matched); 5 "frame-level failure
### probability" + grid-constant footnote; 6 "flatline at the ego floor (BLER~1)"; 7 subject = "learned
### selector requests"; 8 last-sentence grammar + "a finding" (not "the result") + payload-penalised
### frontier (lambda not assumed defined); 9 footnote-4 0.999 shared with feasibility mask.
