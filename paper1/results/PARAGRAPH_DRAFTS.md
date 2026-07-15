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
C16. We retain C256 for completeness of the granularity ladder spanned by the 2-bit request, yet it earns no operational role:
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

## 2. Collaboration-is-sometimes-harmful (Discussion) -- DRAFT v2 (2026-07-15; 6 revisions applied).
## RELABELLED #2 (writing order: C256=1, collab-harm=2, CoDS=3). Anchor 1.0/5.8/0.9% from the c256 verify CSV
## (F1-based, NO payload kinship) -> unaffected by item-12; independent of C256 landing.
## PROVENANCE CATCH (report, do not bury): the old "-0.0147, 95% CI excludes 0" does NOT reproduce -- grep of
## the whole results tree finds no -0.0147 and NO Easy-stratum harm CI anywhere. The CSV-direct value is
## -0.0134 (test Easy, good channel AWGN SNR>=14, n=108, fixedL 0.9849 vs CATOSG 0.9715;
## difficulty_strata_goodchannel.csv). No CI -> per the section-3 wording rule the harm claim is now
## DESCRIPTIVE (point value in a footnote, not a headline magnitude+CI). Supervisor to rule on the substitution.

Collaboration is not unconditionally beneficial, and that is what makes an explicit per-frame selector
necessary rather than a convenience. Two failure modes call for two responses. When the channel cannot carry
a feature message, requesting one spends the collaborator's transmission budget for nothing and collapses the
output to the ego-only floor (the ego vehicle's own pre-fusion detection); the design answer is already in
place -- the oracle removes any action whose frame-level failure probability is $\ge 0.999$ from its feasible
set (the same $0.999$ constant as the \S\ref{sec:method} mask) and falls back to the ego-only output rather
than a phantom feature. When the channel \emph{can} carry the message it can still hurt: on easy frames where
ego-only detection already suffices, feature-level fusion can leave the fused output below the ego-only
one.[^harm] This mode has no masking answer; its remedy is left to future work. Two CSV-verified quantifiers
bound where harm occurs: the ego-only output strictly exceeds the object-level fused output on 0.9 / 7.4 /
0.2\% of validation / test / Culver-City frames, and -- from the same per-frame $(\mathrm{comp}-\mathrm{ego})$
identity and CSV as the C256 analysis (\S\ref{sec:method}) -- the compressed-feature message, when delivered,
yields lower frame F1 than the ego-only fallback on 1.0 / 5.8 / 0.9\% of frames. Test carries the harm most,
consistent with fusion having the least to add in thin scenes (mean $15$ ground-truth objects on test vs $28$
on validate and $41$ on Culver-City). A remedy adds no signalling overhead: the `11' codeword of the 2-bit
request is unused, so an explicit do-not-request (ego-only) action is free to add.

[^harm]: On the test Easy stratum under a usable channel (AWGN SNR $\ge 14$~dB, $n=108$) feature-level fusion
sits just below the object-level baseline ($0.9715$ vs $0.9849$; difficulty table, \S\ref{sec:difficulty});
the effect is small and reported as a mechanism, not a magnitude -- no CI is available for this stratum.

Word count (body, excl. footnote) ~230. src results/c256_dominance_verify.csv (frac_comp_lt_ego =
1.0/5.8/0.9%, same run/commit as the C256 fractions); results/step4_collaboration_harm_v3.csv (frac_ego_gt_
late = 0.9/7.4/0.2%, STRICT inequality, ties excluded); results/difficulty_strata_goodchannel.csv (test Easy
-0.0134, n=108); results/gt_object_stats_v3.csv (mean late_num_gt: test 15.2 / validate 27.8 / culver 41.0).
Cross-refs \S\ref{sec:method}, \S\ref{sec:difficulty} placeholders.
### 6 REVISIONS APPLIED: 1 causal split (undeliverable->mask+ego = existing design; deliverable-but-harmful
### -> quantified + remedy explicitly future work, no "precisely why" over-attribution); 2 cross-para fix
### (C256 "granularity ladder spanned by the 2-bit request", not "codebook" -- the '11'-unused sentence no
### longer breaks it); 3 provenance (-0.0147->-0.0134 CSV-direct + no-CI->descriptive; 0.9/7.4/0.2 strict
### frac_ego_gt_late; 15/28/41 from gt_object_stats_v3.csv, 43->41 corrected); 4 FP claim removed (no ego/
### compressed confusion columns exist -> result-level "below the ego-only one", mechanism-bar not met);
### 5 precision (>=0.999; "when delivered, yields lower frame F1"; "consistent with...thin scenes"; "adds no
### signalling overhead"; ego-only glossed once, single-vehicle term dropped); 6 "per-frame selector" first line.
### WORDING SELF-CHECK: no directional claim carries an unsourced CI; the sole magnitude (-0.0134) is in a
### footnote, descriptive; body statements are hedged/descriptive (can leave/strictly exceeds/yields lower/
### carries most). WELD: shares the (comp-ego) identity + same CSV as C256 -> one causal chain.
