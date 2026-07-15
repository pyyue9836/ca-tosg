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
C16. We retain C256 for completeness of the 2-bit request codebook, yet it earns no operational role:
trained to imitate an oracle that assigns C256 zero support at this operating point, the learned selector
never requests it -- 0 of $3.96/4.34/1.10\times10^{5}$ deployment predictions[^req] -- and even the oracle's
payload-penalised frontier activates it at only 2.5 / 3.2 / 4.5\% of frames. That a rate-matched,
lower-channel-use action earns no more than a marginal share is itself a finding.

[^req]: Measured by replaying the 200-realisation deployment (drawn CSI) through the deployed selector and
counting C256 predictions -> 0 / 0 / 0 (validate/test/culver). The deployed classifier's class set is
$\{L, \mathrm{C16}\}$ -- the imitated oracle labels carry zero C256 at this operating point -- so the count
is structurally zero; we report the measured count rather than infer it. src c256_dominance_verify.csv
(columns selector_C256_requests, selector_has_C256_class).

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

## 3. Collaboration-is-sometimes-harmful (Discussion) -- DRAFT v1 (2026-07-15). Anchor 1.0/5.8/0.9% from the
## c256 verify CSV (F1-based, NO payload kinship) -> unaffected by the item-12 payload fix; independent of C256 landing.

Collaboration is not unconditionally beneficial, and that is what makes an explicit selector necessary rather
than a convenience. A feature request the channel cannot deliver spends the collaborator's transmission
budget for nothing and collapses the fused output to the ego-only floor; on a frame where the ego detector
already suffices it can instead add false positives that a single-vehicle detector would avoid. This is
precisely why the oracle carries a feasibility mask -- an action whose frame-level failure probability
exceeds $0.999$ is removed from its feasible set -- and why the failure fallback is the ego-only output
rather than a phantom feature. The effect is measurable but small, and we report it as a mechanism, not a
headline: on the Easy stratum of the test split the collaborator's message changes realised F1 by $-0.0147$
(frame-level paired $95\%$ CI excludes $0$), i.e.\ single-vehicle ego-only detection is ahead of fusion
there. Two descriptive quantifiers bound where this occurs: the ego-only output exceeds the object-level
fused output on 0.9 / 7.4 / 0.2\% of validation / test / Culver-City frames, and -- from the same per-frame
account and identity as the C256 analysis (\S\ref{sec:method}) -- the compressed-feature message's delivered
utility falls below the ego-only fallback on 1.0 / 5.8 / 0.9\% of frames. Test is the sparsest split (mean
$15$ ground-truth objects vs $28/43$), where thin scenes give fusion the least to add. A free remedy remains
for future work: the `11' codeword of the 2-bit request is unused, so an explicit do-not-request (ego-only)
action costs nothing to add.

Word count ~235. src results/c256_dominance_verify.csv (frac_comp_lt_ego = 1.0/5.8/0.9%, same run/commit as
the C256 fractions), results/ablation_v3/a2_difficulty*.csv (-0.0147 CI), results/step4_collaboration_harm_v3
.csv (frac ego>late 0.9/7.4/0.2%). Cross-refs \S\ref{sec:method} placeholder. WELD: shares the (comp-ego)
identity and the SAME CSV as the C256 paragraph -- the sign of (comp-ego) drives both dominance reversal and
collaboration harm. WORDING SELF-CHECK: the one directional claim (-0.0147) carries a CI that excludes 0; all
other statements descriptive (changes/exceeds/falls below/ahead), no unqualified harms/degrades/hurts.
