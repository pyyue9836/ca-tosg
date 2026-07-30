# Final-gate batch 2 — raw diff text (main.tex, f2df4ca -> HEAD)

Chat delivery kept truncating; this file carries the raw hunks so the gate read can close.

Regenerate any hunk with `git diff f2df4ca HEAD -- paper1/paper/main.tex`.


## Two hanging rulings — landed (commit b4e8f34)

- sec:threshold title: `Feature Ablation and an SNR-Threshold Rule` -> `Comparison with an SNR-Threshold Rule` (grep: no prose locates the section by old title; 4 \ref{sec:threshold} are title-agnostic).

- tab:two_regime caption: `the cues add no F1 there` -> `add no significant F1 there` (caption family swept; no bare `add no F1` remains).


## #18 — harm seam + tab:two_regime (@@ -806)

```diff
@@ -806,22 +800,27 @@ task-oriented selector this paper proposes.
 \begin{table}[t]
 \centering
 \caption{Learned-selector edge over the best (oracle-tuned) SNR-threshold rule on the
-same $1{,}000$ validate frames, $200$-seed protocol. The edge is insignificant under the
-LDPC cliff (SNR is a sufficient statistic) but significant under graceful JSCC (the
-perception cues become necessary).}
+same $2{,}170$ test frames, $200$-seed protocol. The edge is small under the
+LDPC cliff (the selector's function-form margin over a threshold, not a cue gain---the
+cues add no significant F1 there, Section~\ref{sec:ablation}) but $5$--$6{\times}$ larger under
+graceful JSCC, where an SNR threshold cannot reach it.}
 \label{tab:two_regime}
 \begin{tabular}{llc}
 \toprule
 Feature codec & Channel & Edge (RF $-$ threshold) F1 \\
 \midrule
-LDPC + QAM (cliff)      & AWGN     & $+0.002$~$[-0.001,+0.006]$ \\
-Importance-map JSCC     & AWGN     & $\mathbf{+0.017}$~$[+0.012,+0.022]$ \\
-Importance-map JSCC     & Rayleigh & $\mathbf{+0.015}$~$[+0.011,+0.020]$ \\
-Importance-map JSCC     & OFDM     & $\mathbf{+0.015}$~$[+0.011,+0.019]$ \\
+LDPC + QAM (cliff)      & AWGN     & $+0.005$~$[+0.004,+0.006]$ \\
+Importance-map JSCC     & AWGN     & $\mathbf{+0.027}$~$[+0.024,+0.029]$ \\
+Importance-map JSCC     & Rayleigh & $\mathbf{+0.022}$~$[+0.020,+0.025]$ \\
+Importance-map JSCC     & OFDM     & $\mathbf{+0.025}$~$[+0.023,+0.028]$ \\
 \bottomrule
 \end{tabular}
 \end{table}
 
+\subsection{Collaboration Is Not Always Beneficial}\label{sec:harm}
+
+Collaboration is not unconditionally beneficial, and that is what makes an explicit per-frame selector necessary rather than a convenience. Two failure modes call for two responses. When the channel cannot carry a feature message, requesting one spends the collaborator's transmission budget for nothing and collapses the output to the ego-only floor (the ego vehicle's own pre-fusion detection); the design answer is already in place -- the oracle removes any action whose frame-level failure probability is $\ge 0.999$ from its feasible set (the same $0.999$ constant as the \S\ref{sec:method} mask), and on failure the pipeline reverts to the ego-only output rather than a phantom feature. When the channel \emph{can} carry the message, requesting it can still cost accuracy: on the easy stratum the selector's realised output falls below even the always-object-level (Fixed-$L$) baseline.\footnote{Test Easy stratum (top tercile of the ego's own object-level F1, the \S\ref{sec:difficulty} stratification), evaluated under a deterministic reliable-channel condition (AWGN $16$~dB; frame-level BLER ${\approx}0$, well above the $8.0$~dB onset), isolating the difficulty axis from channel variability: the selector's realised F1 is $0.9719$ vs the Fixed-$L$ baseline $0.9866$ -- a gain of $-0.0147$ (frame-level paired $95\%$ CI $[-0.0179,-0.0115]$; $n=713$ frames; a2\_difficulty\_reliable\_v3.csv). The selector requests $C_{16}$ on $635$ of these $713$ frames; on the remaining $78$, where it requests $L$, its output is frame-identical to Fixed-$L$, so the paired difference arises entirely on the $C_{16}$-request frames (verified, harm\_stratum\_structural.csv) -- the loss is a structural consequence of requesting features on already-easy frames.} This mode has no masking answer; its remedy is left to future work. Two CSV-verified quantifiers bound where the ego-side harm sits: the ego-only output strictly exceeds the object-level fused output on 0.9 / 7.4 / 0.2\% of validation / test / Culver-City frames, and -- from the same per-frame $(\mathrm{comp}-\mathrm{ego})$ identity and CSV as the C256 analysis (\S\ref{sec:candidates}) -- the compressed-feature message, when delivered, yields lower frame F1 than the ego-only fallback on 1.0 / 5.8 / 0.9\% of frames. Test carries the harm most, consistent with fusion having the least to add in thin scenes (mean $15.2$ ground-truth objects on test vs $27.8$ on validate and $41.0$ on Culver-City). A remedy adds no signalling overhead: the `11' codeword of the 2-bit request is unused, so an explicit do-not-request (ego-only) action can be added without any change to the two-bit message format.
+
 \subsection{Comparison with Where2comm}\label{sec:where2comm}
 
 To provide a same-codebase reference against the most prominent
```


## #3 — CoDS insertion seam (@@ -104)

```diff
@@ -104,6 +104,8 @@ For vehicular perception, this channel dependence is especially important. V2V l
 
 Existing semantic communication methods mainly focus on how to encode and transmit feature-level information more robustly. Some further make this transmission channel-adaptive at a fixed granularity: SmartCooper~\cite{zhang2024smartcooper} adjusts the feature compression ratio from the estimated channel state, while AccBEV~\cite{accbev2025} conditions a feature-repair module on the SNR to compensate for feature loss over lossy V2V links. These methods adapt \emph{how} the feature-level message is encoded or repaired, but still commit to feature-level transmission. Our work is complementary to these methods. A semantic codec or channel coding module can be used inside the feature-level branch of \method{}. The key difference is that \method{} operates before the transmission mode is chosen: it decides whether the sender should transmit object-level information or feature-level information under the current task and channel state. This channel-aware semantic granularity selection is particularly suitable for vehicular systems, where communication resources are limited and channel quality can change rapidly.
 
+A concurrent line of work pushes semantic communication for collaborative perception into the digital domain. CoDS~\cite{gan2025cods} pairs a task-oriented semantic compression codec with a semantic analog-to-digital converter, so that learned features traverse a standard digital V2X bitstream -- LDPC-coded and QAM-modulated, the same cliff-prone class of digital transport we characterise -- rather than an analog channel. On the sender side a feature-selection network identifies task-important spatial locations for transmission; on the receiver side an uncertainty-aware network discards features corrupted by decoding failures, mitigating the LDPC cliff after decoding. CoDS thus selects by task importance at the sender and filters by decode reliability at the receiver. \method{} makes the prevailing channel state a first-class conditioning signal alongside the task: from local task cues and the estimated channel state it selects the message \emph{granularity} per frame -- the compact object-level message or one of the feature-level variants -- and signals the choice through the 2-bit request before any high-payload transmission; when the channel cannot carry a feature message, the feature-level actions are gated out of the feasible set and the selector defaults to the compact object-level message. The two are complementary rather than competing -- a digital semantic codec such as that of CoDS could serve as the feature-level branch that \method{} activates, placing channel-conditioned granularity selection one level above codec and spatial-selection design. Both address the cliff effect, at different points: CoDS discards corrupted features after they are received, whereas \method{} avoids spending the collaborator's transmission budget on an undeliverable feature message.
+
 \section{System Model and Problem Formulation}\label{sec:system}
 
 \subsection{Cooperative Perception Setting}
```


## #9 — payload accounting + NR sentence (@@ -312)

```diff
@@ -312,11 +317,11 @@ We evaluate \method{} on the OPV2V dataset~\cite{xu2022opv2v} using the OpenCOOD
 
 \subsection{Message Construction and Payload Accounting}
 
-The two payloads are derived from first principles rather than assumed. The object-level message $L$ carries the collaborator's detected objects; on the OPV2V validate split a frame contains on average $27$ detected objects, and encoding each as an ETSI-CPM-style perceived-object container (3D box, dimensions, class, confidence and position covariance, ${\approx}110$~bytes) gives $B_L \approx 27 \times 110 \times 8 \approx 0.024$~Mbit/frame---a deliberately conservative figure that, if anything, overstates the object-level cost. The feature-level message encodes the transmitted BEV feature tensor of size $256 \times 48 \times 176 \approx 2.16\times10^{6}$ elements: the $281.6 \times 76.8$~m detection range at $0.4$~m voxels yields a $704 \times 192$ pillar grid, down-sampled by $4$ to $48 \times 176$ with $256$ channels; at a compact ${\approx}1$-bit-per-element encoding this is $B_C \approx 1.98$~Mbit/frame, matching the value adopted by the importance-map JSCC baseline~\cite{sheng2024importance} for a like-for-like comparison. The feature-level message is therefore ${\approx}82\times$ the object-level payload. Both feature modes $C_{16}$ and $C_{256}$ carry this same $1.98$~Mbit perception payload but require different numbers of channel uses: $B_{C_{16}}=1.98/4 \approx 0.495$~Mbit/frame for 16-QAM and $B_{C_{256}}=1.98/8 \approx 0.248$~Mbit/frame for 256-QAM, the divisors being the bits-per-symbol of each modulation. All payload comparisons in this paper use this channel-use-equivalent definition.
+The two payloads are derived from first principles rather than assumed. The object-level message $L$ carries the collaborator's detected objects; on the OPV2V validate split a frame contains on average $27$ detected objects, and encoding each as an ETSI-CPM-style perceived-object container (3D box, dimensions, class, confidence and position covariance, ${\approx}110$~bytes) gives $B_L \approx 27 \times 110 \times 8 \approx 0.024$~Mbit/frame---a deliberately conservative figure that, if anything, overstates the object-level cost. The feature-level message encodes the transmitted BEV feature tensor of size $256 \times 48 \times 176 \approx 2.16\times10^{6}$ elements: the $281.6 \times 76.8$~m detection range at $0.4$~m voxels yields a $704 \times 192$ pillar grid, down-sampled by $4$ to $48 \times 176$ with $256$ channels; at a compact ${\approx}1$-bit-per-element encoding this is $B_C \approx 1.98$~Mbit/frame, matching the value adopted by the importance-map JSCC baseline~\cite{sheng2024importance} for a like-for-like comparison. The feature-level message is therefore ${\approx}82\times$ the object-level payload. Both feature modes $C_{16}$ and $C_{256}$ carry this same $1.98$~Mbit perception payload but require different numbers of channel uses; applying the rate-$1/2$ coded-bit conversion of Eq.~(\ref{eq:payload}) gives $B_{C_{16}} \approx 0.99$~Mbit/frame for 16-QAM and $B_{C_{256}} \approx 0.495$~Mbit/frame for 256-QAM. All payload comparisons in this paper use this channel-use-equivalent definition.
 
 \subsection{Channel Settings}
 
-We sweep the estimated SNR over $\gamma \in \{0,2,4,\ldots,20\}$~dB, giving $11$ SNR points per channel. We evaluate two channel models: AWGN and Rayleigh fading. For training data, each of the $1{,}980$ frames is independently assigned a SNR uniformly sampled from $[0,20]$~dB and a channel type uniformly sampled from $\{\text{AWGN},\text{Rayleigh}\}$, mirroring the training-SNR sweep used by~\cite{sheng2024importance,gan2026scomcp}. The BLER functions $\mathrm{BLER}_q(\gamma,\text{ch})$ are tabulated from a separate LDPC + QAM simulation. For Rayleigh fading we average the AWGN BLER table over the exponential instantaneous-SNR distribution to obtain the effective BLER at each mean SNR.
+We sweep the estimated SNR over $\gamma \in \{0,2,4,\ldots,20\}$~dB, giving $11$ SNR points per channel. We evaluate two channel models: AWGN and Rayleigh fading. For training data, each of the $1{,}980$ frames is independently assigned a SNR uniformly sampled from $[0,20]$~dB and a channel type uniformly sampled from $\{\text{AWGN},\text{Rayleigh}\}$, mirroring the training-SNR sweep used by~\cite{sheng2024importance,gan2026scomcp}. The BLER functions $\mathrm{BLER}_q(\gamma,\text{ch})$ are tabulated from a separate LDPC + QAM simulation; we instantiate this transport with the 5G NR LDPC (Sionna) under TR 37.885 Urban NLOSv. For Rayleigh fading we average the AWGN BLER table over the exponential instantaneous-SNR distribution to obtain the effective BLER at each mean SNR.
 
 \subsection{Selector Training}
 
```


## #13 — tab:true_e2e table + generalisation (@@ -561)

```diff
@@ -561,53 +569,53 @@ Table~\ref{tab:e2e} reports the deployment-mode \emph{frame-level F1} aggregated
 \toprule
 Channel & SNR (dB) & $\rho_L$ & AP@0.5 & AP@0.7 \\
 \midrule
-AWGN     & 0.0  & 1.000 & 0.893 & 0.839 \\
-AWGN     & 8.0  & 1.000 & 0.893 & 0.839 \\
-AWGN     & 12.0 & 0.909 & 0.895 & 0.844 \\
-AWGN     & 14.0 & 0.331 & \textbf{0.911} & \textbf{0.865} \\
-AWGN     & 16.0 & 0.326 & 0.912 & 0.866 \\
-AWGN     & 20.0 & 0.362 & 0.912 & 0.867 \\
-Rayleigh & 0.0  & 1.000 & 0.893 & 0.839 \\
-Rayleigh & 10.0 & 1.000 & 0.893 & 0.839 \\
-Rayleigh & 20.0 & 0.998 & 0.893 & 0.839 \\
+AWGN     & 0.0  & 1.000 & 0.890 & 0.836 \\
+AWGN     & 8.0  & 0.984 & 0.890 & 0.835 \\
+AWGN     & 12.0 & 0.385 & 0.916 & 0.857 \\
+AWGN     & 14.0 & 0.370 & \textbf{0.916} & \textbf{0.857} \\
+AWGN     & 16.0 & 0.372 & 0.916 & 0.858 \\
+AWGN     & 20.0 & 0.439 & 0.917 & 0.857 \\
+Rayleigh & 0.0  & 1.000 & 0.890 & 0.836 \\
+Rayleigh & 10.0 & 1.000 & 0.890 & 0.836 \\
+Rayleigh & 20.0 & 1.000 & 0.890 & 0.836 \\
 \bottomrule
 \end{tabular}
 \end{table}
 
-Two observations support the central claim. First, the deployment-mode AP at AWGN $14$~dB reaches $0.911$ at IoU $0.5$ and $0.865$ at IoU $0.7$, sitting within $0.006$ AP of the perfect-channel reference of the underlying attentive-compression model ($0.917$, see Section~\ref{sec:headline}). The selector therefore captures essentially all of the benefit of feature-level transmission once the LDPC threshold is crossed, while paying only $0.339$~Mbit/frame instead of $0.495$. Second, the Rayleigh AP curve is flat across the full SNR range and matches Fixed $L$, confirming that the selector's conservative fading-regime behaviour, identified in Section~\ref{sec:headline}, is not a frame-F1 artefact but a genuine end-to-end property.
+Two observations support the central claim. First, the deployment-mode AP at AWGN $14$~dB reaches $0.916$ at IoU $0.5$ and $0.857$ at IoU $0.7$, sitting within $0.001$ AP of the perfect-channel reference of the underlying attentive-compression model ($0.917$, see Section~\ref{sec:headline}). The selector therefore captures essentially all of the benefit of feature-level transmission once the LDPC threshold is crossed, while paying only $0.632$~Msym/frame at this operating point instead of the $0.990$ of always-on Fixed $C_{16}$. Second, the Rayleigh AP curve is flat across the full SNR range and matches Fixed $L$, confirming that the selector's conservative fading-regime behaviour, identified in Section~\ref{sec:headline}, is not a frame-F1 artefact but a genuine end-to-end property.
 
 \subsection{Generalisation to OPV2V Test and Culver-City Splits}\label{sec:generalisation}
 
 All results above are computed on the OPV2V validate split. To test whether the selector overfits to that split, we re-run the entire pipeline---per-frame late-fusion and attentive-compression inference, the ego-side cues, the channel-aware oracle labelling, and the true end-to-end AP scoring---on two held-out splits never seen during selector training: (a) the OPV2V \emph{test} split ($T=2{,}170$ frames, scene-disjoint from validate), and (b) the OPV2V \emph{Culver-City} split ($T=550$ frames), a domain shift in which the simulated scenes follow the real road network of Culver City rather than the default CARLA towns used in the other splits. Crucially, the deployed Random Forest selector is \emph{not} retrained on either split: the exact validate-trained model is applied unchanged, so this measures genuine cross-split and cross-domain generalisation rather than re-fitting.
 
-Table~\ref{tab:gen_headline} reports the headline comparison on both splits. The validate-trained selector reproduces $88.9\%$ of the $3$-way oracle's per-frame decisions on test and $91.3\%$ on Culver-City. Because the oracle activates a feature-level message on only $\approx 11\%$ of frames, raw decision agreement is close to the always-$L$ base rate ($0.895$ on test, $0.845$ on Culver-City) and is thus a weak diagnostic in isolation; the meaningful evidence of transfer is that the policy ordering is identical to validate on both splits: the fixed feature-level policies remain strictly dominated by Fixed $L$, the oracle sits marginally above Fixed $L$, and \method{} recovers $99.4\%$ (test) and $99.6\%$ (Culver-City) of the oracle's F1 at $16.4\%$ and $17.1\%$ of the Fixed $C_{16}$ bandwidth respectively. The absolute F1 values differ across splits because the frozen backbone finds the test scenes easier and the Culver-City scenes harder than validate; the \emph{relative} payload--F1 frontier is preserved in both cases, confirming that the cue distribution and the BLER tables transfer across splits and across the Culver-City domain shift without recalibration. Notably, on the harder Culver-City domain the selector's margin over Fixed $L$ widens (selection accuracy $0.913$ vs.\ $0.845$ for always-$L$), as feature-level transmission is worth more when object-level detection is more strained.
+Table~\ref{tab:gen_headline} reports the headline comparison on both splits. The validate-trained selector reproduces $85.4\%$ of the $3$-way oracle's per-frame decisions on test and $87.0\%$ on Culver-City. Because the oracle activates a feature-level message on only ${\approx}16\%$ (test) and ${\approx}24\%$ (Culver-City) of frames, raw decision agreement is close to the always-$L$ base rate ($0.839$ on test, $0.759$ on Culver-City) and is thus a weak diagnostic in isolation; the meaningful evidence of transfer is that the policy ordering is identical to validate on both splits: the fixed feature-level policies remain dominated by Fixed $L$ at matched channel use, the oracle sits marginally above Fixed $L$, and \method{} recovers $99.4\%$ (test) and $99.3\%$ (Culver-City) of the oracle's F1---between $99.3\%$ and $99.8\%$ across all three splits---at $25.3\%$ and $16.0\%$ of the Fixed $C_{16}$ channel use respectively. The absolute F1 values differ across splits because the object-level detection baseline itself differs---Fixed-$L$ AP@0.5 is $0.919$ on test and $0.890$ on validate but only $0.783$ under the Culver-City domain shift---while the \emph{relative} payload--F1 frontier is preserved in all cases, confirming that the cue distribution and the BLER tables transfer across splits and across the Culver-City domain shift without recalibration. Notably, on the harder Culver-City domain the selector's margin over Fixed $L$ widens (selection accuracy $0.870$ vs.\ $0.759$ for always-$L$), as feature-level transmission is worth more when object-level detection is more strained.
 
 \begin{table}[t]
 \centering
-\caption{Generalisation of the \emph{validate-trained} selector (no retraining) to the OPV2V test ($T=2{,}170$ frames, scene-disjoint) and Culver-City ($T=550$ frames, real-road-layout domain shift) splits. Mean over SNR $\in[0,20]$~dB with $50/50$ AWGN/Rayleigh mix. On both splits \method{} recovers $99.3$--$99.7\%$ of the oracle's F1 at $15.8$--$18.4\%$ of the Fixed $C_{16}$ bandwidth, mirroring the validate frontier of Table~\ref{tab:headline}.}
+\caption{Generalisation of the \emph{validate-trained} selector (no retraining) to the OPV2V test ($T=2{,}170$ frames, scene-disjoint) and Culver-City ($T=550$ frames, real-road-layout domain shift) splits. Mean over SNR $\in[0,20]$~dB with $50/50$ AWGN/Rayleigh mix. On both splits \method{} recovers $99.3$--$99.8\%$ of the oracle's F1 at $16$--$25\%$ of the Fixed $C_{16}$ channel use, mirroring the validate frontier of Table~\ref{tab:headline}.}
 \label{tab:gen_headline}
 \begin{tabular}{lcc}
 \toprule
-Policy & Payload (Mbit/frame) & Mean F1 \\
+Policy & Channel use (Msym/frame) & Mean F1 \\
 \midrule
 \multicolumn{3}{l}{\emph{OPV2V test} ($T=2{,}170$)} \\
-Channel-aware oracle           & 0.074 & \textbf{0.894} \\
-Fixed $L$ (PointPillar\_Late)   & 0.024 & 0.887 \\
-Fixed $C_{16}$ (LDPC + 16-QAM)  & 0.495 & 0.426 \\
-Fixed $C_{256}$ (LDPC + 256-QAM)& 0.248 & 0.116 \\
-\method{} (ours, RF + CSI + ch) & \textbf{0.081} & \textbf{0.888} \\
+Channel-aware oracle           & 0.179 & 0.914 \\
+Fixed $L$ (PointPillar\_Late)   & 0.024 & 0.901 \\
+Fixed $C_{16}$ (LDPC + 16-QAM)  & 0.990 & 0.852 \\
+Fixed $C_{256}$ (LDPC + 256-QAM)& 0.495 & 0.826 \\
+\method{} (ours, RF + est.\ SNR + ch.\ type) & \textbf{0.251} & \textbf{0.909} \\
 \midrule
 \multicolumn{3}{l}{\emph{OPV2V Culver-City} ($T=550$)} \\
-Channel-aware oracle           & 0.097 & \textbf{0.894} \\
-Fixed $L$ (PointPillar\_Late)   & 0.024 & 0.887 \\
-Fixed $C_{16}$ (LDPC + 16-QAM)  & 0.495 & 0.467 \\
-Fixed $C_{256}$ (LDPC + 256-QAM)& 0.248 & 0.132 \\
-\method{} (ours, RF + CSI + ch) & \textbf{0.085} & \textbf{0.891} \\
+Channel-aware oracle           & 0.257 & 0.889 \\
+Fixed $L$ (PointPillar\_Late)   & 0.024 & 0.872 \\
+Fixed $C_{16}$ (LDPC + 16-QAM)  & 0.990 & 0.817 \\
+Fixed $C_{256}$ (LDPC + 256-QAM)& 0.495 & 0.781 \\
+\method{} (ours, RF + est.\ SNR + ch.\ type) & \textbf{0.158} & \textbf{0.883} \\
 \bottomrule
 \end{tabular}
 \end{table}
 
-Tables~\ref{tab:gen_true_e2e} and~\ref{tab:gen_true_e2e_culver} report the true end-to-end AP on the test and Culver-City splits respectively. The qualitative behaviour matches validate closely on both. On test, the selector remains at Fixed $L$ up to $8$~dB, begins activating $C_{16}$ at $12$~dB ($\rho_L=0.95$), and crosses to a feature-dominant policy at $14$~dB ($\rho_L=0.33$), lifting AP@$0.5$ from $0.905$ to $0.921$ and AP@$0.7$ from $0.856$ to $0.866$---within $0.001$ AP@$0.5$ of the test-split perfect-channel reference of the attentive-compression model ($0.922$). On Culver-City the same knee appears at $12$--$14$~dB ($\rho_L: 0.97 \to 0.20$), lifting AP@$0.5$ from $0.811$ to $0.866$ ($+5.5$ points) and AP@$0.7$ from $0.724$ to $0.771$ ($+4.7$ points); the \emph{relative} adaptation gain is in fact larger on the harder domain, consistent with the wider per-frame margin noted above. A single deviation from a clean monotone appears at the top of the AWGN range: on both transfer splits the AP peaks near $16$~dB and dips mildly at $20$~dB (test $0.921\!\to\!0.918$; Culver-City $0.866\!\to\!0.858$~AP@$0.5$) as the selector's $\rho_L$ rebounds ($0.33\!\to\!0.53$ and $0.20\!\to\!0.34$). This coincides with the $20$~dB upper edge of the training SNR grid and is negligible on validate ($\rho_L: 0.33\!\to\!0.36$), whose frames are in-distribution for the frozen selector; we therefore attribute it to a selector-side grid-edge artefact rather than a channel effect, and it leaves the $\ge14$~dB operating point used throughout unaffected. Under Rayleigh the selector stays at the Fixed-$L$ operating point across the entire $0$--$20$~dB range on both splits, because the deep-fade BLER never falls low enough to make feature-level transmission worthwhile. The channel-adaptive AP gain---the actual value proposition of \method{}---therefore reproduces both on a scene-disjoint split and across a real-road-layout domain shift, with a frozen selector.
+Tables~\ref{tab:gen_true_e2e} and~\ref{tab:gen_true_e2e_culver} report the true end-to-end AP on the test and Culver-City splits respectively. On test, the selector remains at Fixed $L$ up to $8$~dB and begins activating $C_{16}$ at $12$~dB ($\rho_L=0.13$), lifting AP@$0.5$ from $0.919$ to $0.921$ while leaving AP@$0.7$ essentially unchanged ($0.869\!\to\!0.865$)---within $0.002$ AP@$0.5$ of the test-split perfect-channel reference of the attentive-compression model ($0.922$); on this sparser split, where object-level detection is already near the feature-level ceiling, the feature-level message adds no significant AP. On Culver-City the knee appears at $12$--$14$~dB ($\rho_L: 1.00 \to 0.44$), lifting AP@$0.5$ from $0.783$ to $0.857$ ($+7.4$ points) and AP@$0.7$ from $0.698$ to $0.756$ ($+5.8$ points); the \emph{relative} adaptation gain is far larger on the harder domain, consistent with the wider per-frame margin noted above. A single deviation from a clean monotone appears at the top of the AWGN range: the Culver-City AP peaks near $16$~dB and dips mildly at $20$~dB ($0.857\!\to\!0.840$~AP@$0.5$) as the selector's $\rho_L$ rebounds ($0.44\!\to\!0.57$). This coincides with the $20$~dB upper edge of the training SNR grid; we attribute it to a selector-side grid-edge artefact rather than a channel effect, and it leaves the $\ge14$~dB operating point used throughout unaffected. Under Rayleigh the selector stays at the Fixed-$L$ operating point across the entire $0$--$20$~dB range on both splits, because the deep-fade BLER never falls low enough to make feature-level transmission worthwhile. The channel-adaptive AP gain---the value proposition of \method{}---therefore reproduces on the real-road-layout Culver-City domain shift and remains comparable to object-level on the sparser scene-disjoint test split, with a frozen selector.
 
 \begin{table}[t]
 \centering
```


## #8 — B1 feasibility-mask sentence (@@ -277)

```diff
@@ -277,13 +282,13 @@ The role of $(\hat\gamma_t,c_t)$ is fundamentally different from the perception
 The object-level branch transmits compact detection results $m_t^L = \{(b_k,c_k,p_k)\}_{k=1}^{N_t}$. Its average payload is approximately $B_L = 0.024$~Mbit/frame, allowing it to be transmitted with strong channel coding and treated as channel-invariant in the evaluated SNR range.
 
 \subsubsection{Feature-Level Branches}
-The feature-level branches transmit compressed BEV representations $m_t^{C_q} = \phi_q(F_{j,t})$, where $\phi_q(\cdot)$ uses $q$-QAM modulation under rate-$1/2$ LDPC coding. The $C_{16}$ mode is more reliable but less spectrally efficient (channel-use payload $B_{C_{16}} \approx 0.495$~Mbit/frame), while the $C_{256}$ mode is more spectrally efficient but more channel-sensitive (channel-use payload $B_{C_{256}} \approx 0.248$~Mbit/frame).
+The feature-level branches transmit compressed BEV representations $m_t^{C_q} = \phi_q(F_{j,t})$, where $\phi_q(\cdot)$ uses $q$-QAM modulation under rate-$1/2$ LDPC coding. The $C_{16}$ mode is more reliable but less spectrally efficient (channel-use payload $B_{C_{16}} \approx 0.99$~Mbit/frame), while the $C_{256}$ mode is more spectrally efficient but more channel-sensitive (channel-use payload $B_{C_{256}} \approx 0.495$~Mbit/frame).
 
 \subsection{Channel-Aware Semantic Granularity Selector}
 
 The selector implements the policy $g(z_t,\hat\gamma_t,c_t)$ of Eq.~\eqref{eq:selector} as a Random Forest classifier with $N_T=400$ trees, depth bound $D_{\max}=10$, minimum samples per leaf of $4$, and balanced class weighting to compensate for the heavy class imbalance in the channel-aware oracle labels. We choose Random Forest for three practical reasons. First, the selector should be \emph{training-free with respect to the perception backbone and detection head}: it should be deployable on top of any pretrained cooperative perception stack without retraining the perception model. Random Forest fits this constraint because it operates purely on tabular cues. Second, Random Forest provides \emph{interpretable feature importance} (Section~\ref{sec:feat_imp}), which is valuable for safety certification of vehicular systems. Third, its per-frame inference cost on a single CPU core is $52.8 \pm 5.7$~ms ($\mathrm{P95} = 59.1$~ms), measured over $2{,}000$ trials (Section~\ref{sec:robustness}); this fits the $100$~ms budget of a $10$~Hz LiDAR cycle without requiring a GPU, dedicated accelerator, or framework-level optimisation. We emphasise that the contribution is not the Random Forest itself: it is an interpretable implementation of the channel-aware granularity policy, and Section~\ref{sec:robustness} together with Table~\ref{tab:headline_agg} shows lighter models and even a hand-tuned SNR-threshold rule reach the same realised F1.
 
-The selector is trained to imitate the channel-aware oracle defined in Eq.~\eqref{eq:oracle}. The oracle uses ground-truth detection outputs and is therefore not deployable; it is used only to generate training labels and as an upper-bound reference. At deployment, the selector uses only the online cues $z_t$ and the channel state $(\hat\gamma_t,c_t)$:
+The selector is trained to imitate the channel-aware oracle defined in Eq.~\eqref{eq:oracle}. The oracle uses ground-truth detection outputs and is therefore not deployable; it is used only to generate training labels and as an upper-bound reference. Before taking the argmax in Eq.~\eqref{eq:oracle}, the oracle applies a \emph{feasibility mask}: any mode whose frame-level block-error rate exceeds $0.999$ at the operating $(\gamma_t,\mathrm{ch}_t)$ grid point is removed from $\mathcal{S}$, so that neither the oracle labels nor the deployed selector request a message the channel almost surely cannot deliver; when a requested feature block is nonetheless lost, the pipeline reverts to the ego-only output rather than a zero-utility state (Eq.~\eqref{eq:eff_C}). At deployment, the selector uses only the online cues $z_t$ and the channel state $(\hat\gamma_t,c_t)$:
 \begin{equation}
 s_t = g(z_t,\hat\gamma_t,c_t).
 \end{equation}
```


## #12 — merged ablation table, full (@@ -449)

```diff
@@ -449,56 +452,61 @@ Fig.~\ref{fig:decision_ratio} shows the per-mode selection ratios $\rho_s$ as a
 
 \subsection{Feature Importance}\label{sec:feat_imp}
 
-Fig.~\ref{fig:feat_imp} and Table~\ref{tab:feat_imp} report the top Gini feature importances of the deployed selector. The two channel-side features dominate: $\hat\gamma_t$ alone contributes $40.5\%$ of importance and the channel-type indicator $c_t$ contributes a further $24.5\%$, totalling $65\%$ of importance from just two features. The next strongest scene-side cue, \texttt{pcd\_mean\_range}, contributes only $3.3\%$, and no individual perception-side cue exceeds $4\%$. This quantifies the central design claim of the paper: channel-state information is the dominant signal for the granularity decision, and the $21$ perception-side cues serve a secondary refinement role.
+Fig.~\ref{fig:feat_imp} and Table~\ref{tab:feat_imp} report the top Gini feature importances of the deployed selector. The two channel-side features dominate: the channel-type indicator $c_t$ contributes $34.9\%$ of importance and the estimated SNR $\hat\gamma_t$ a further $27.5\%$, totalling $62.4\%$ of importance from just two features. The next strongest scene-side cue, \texttt{pcd\_mean\_range}, contributes only $3.6\%$, and no individual perception-side cue exceeds $4\%$. This quantifies the central design claim of the paper: channel-state information is the dominant signal for the granularity decision, and the $21$ perception-side cues serve a secondary refinement role. That the channel-type indicator $c_t$ outranks the estimated SNR $\hat\gamma_t$ is consistent with the frame-level channel physics: under Rayleigh fading the feasible set collapses to $L$ regardless of SNR, so the channel-type flag is the single highest-information split for the decision.
 
 \begin{figure}[t]
     \centering
     \includegraphics[width=\linewidth]{fig_feature_importance.pdf}
-    \caption{Top-12 features by Gini importance of the deployed selector. The channel-side features (red) jointly account for $65\%$ of total importance, dominating all $21$ perception-side LiDAR cues (blue).}
+    \caption{Top-12 features by Gini importance of the deployed selector. The channel-side features (red) jointly account for $62.4\%$ of total importance, dominating all $21$ perception-side LiDAR cues (blue).}
     \label{fig:feat_imp}
 \end{figure}
 
 \begin{table}[t]
 \centering
-\caption{Top-7 features by Gini importance for the deployed \method{} selector (trained on OPV2V validate, $T=1{,}980$ frames). The two channel-side features account for $65\%$ of total importance.}
+\caption{Top-7 features by Gini importance for the deployed \method{} selector (trained on OPV2V validate, $T=1{,}980$ frames). The two channel-side features account for $62.4\%$ of total importance.}
 \label{tab:feat_imp}
 \begin{tabular}{lc}
 \toprule
 Feature & Gini importance \\
 \midrule
-\texttt{est\_snr\_db}             & \textbf{0.405} \\
-\texttt{channel\_is\_rayleigh}    & \textbf{0.245} \\
-\texttt{pcd\_mean\_range}         & 0.033 \\
-\texttt{pcd\_std\_range}          & 0.024 \\
-\texttt{pcd\_left\_points}        & 0.021 \\
-\texttt{pcd\_density\_20\_50}     & 0.019 \\
-\texttt{pcd\_max\_range}          & 0.018 \\
+\texttt{channel\_is\_rayleigh}    & \textbf{0.349} \\
+\texttt{est\_snr\_db}             & \textbf{0.275} \\
+\texttt{pcd\_mean\_range}         & 0.036 \\
+\texttt{pcd\_mid\_20\_50m}        & 0.026 \\
+\texttt{pcd\_density\_20\_50}     & 0.025 \\
+\texttt{pcd\_max\_range}          & 0.024 \\
+\texttt{num\_cavs}                & 0.023 \\
 \midrule
-$\hat\gamma_t + c_t$ subtotal     & \textbf{0.650} \\
+$\hat\gamma_t + c_t$ subtotal     & \textbf{0.624} \\
 \bottomrule
 \end{tabular}
 \end{table}
 
 \subsection{Ablation: Effect of Channel-State Features}\label{sec:ablation}
 
-To isolate the contribution of the two channel-state features, we train three variants of the selector under identical RF hyperparameters: \textsc{RF-base} uses only the $21$ LiDAR cues; \textsc{RF+CSI} adds $\hat\gamma_t$; \textsc{RF+CSI+ch} adds both $\hat\gamma_t$ and $c_t$ and is the deployed configuration. Table~\ref{tab:ablation} summarises the results.
+To isolate the contribution of the two channel-state features, we train selector variants under identical RF hyperparameters over the feature subsets of Table~\ref{tab:ablation}: perception cues only ($21$ LiDAR cues); the perception cues plus the estimated SNR $\hat\gamma_t$; the full configuration adding the channel-type indicator $c_t$ (the deployed selector); and, for reference, channel state alone ($\hat\gamma_t,c_t$) and a hand-tuned SNR threshold. Table~\ref{tab:ablation} summarises the results.
 
 \begin{table}[t]
 \centering
-\caption{Ablation of the channel-state features on the $30\%$ test split. Means and standard deviations for the deployed variant are computed over $5$ random splits (seeds $0$--$4$). Adding $\hat\gamma_t$ improves F1 by $0.012$; adding $c_t$ on top improves F1 by a further $0.014$ and lifts accuracy versus the oracle by $5.3$ percentage points on average.}
+\caption{Selector feature ablation and the SNR-threshold challenger (train: validate, eval: frozen OPV2V test, $T=2{,}170$ frames, $200$ SNR/channel realisations). Realised frame F1 is nearly invariant across feature subsets---channel state alone ($2$ features) already reaches $0.909$ and the full $23$-feature selector matches it to within $0.001$---while the deployed channel use varies with the action mix. Each row is a selector retrained on its feature subset; the deployed selector is the Full configuration, whose channel-averaged operating point in Table~\ref{tab:headline_agg} ($0.909$ at $0.251$~Msym) differs slightly from the per-cut Full row ($0.240$~Msym) only as a separately trained instance. The rigorous channel-averaged payload--F1 comparison (with CIs) is in Table~\ref{tab:headline_agg}.}
 \label{tab:ablation}
-\begin{tabular}{lcccc}
+\begin{tabular}{lccc}
 \toprule
-Variant & Features & Acc.\ vs.\ oracle & Payload & Mean F1 \\
+Selector & \#feat & Realised F1 & Deployed payload (Msym) \\
+\midrule
+Channel only ($\hat\gamma,c$)        & 2  & 0.909 & 0.271 \\
+Perception cues only                 & 21 & 0.900 & 0.089 \\
+Perception $+\ \hat\gamma$           & 22 & 0.897 & 0.182 \\
+Full (all features)                  & 23 & \textbf{0.909} & 0.240 \\
+SNR-threshold ($\tau{=}8.5$)         & -- & 0.910 & 0.303 \\
 \midrule
-\textsc{RF-base}    & $21$ cues only          & 0.864 & 0.048 & 0.839 \\
-\textsc{RF+CSI}     & $+\hat\gamma_t$         & 0.860 & 0.089 & 0.851 \\
-\textsc{RF+CSI+ch}  & $+\hat\gamma_t,c_t$     & \textbf{0.917 $\pm$ 0.015} & 0.089 $\pm$ 0.011 & \textbf{0.865 $\pm$ 0.007} \\
+Oracle (upper bound)                 & -- & 0.914 & 0.179 \\
+Fixed $L$                            & -- & 0.901 & 0.024 \\
 \bottomrule
 \end{tabular}
 \end{table}
 
-Two findings stand out. First, $\hat\gamma_t$ alone improves F1 from $0.839$ to $0.851$ but actually \emph{increases} payload, because the selector tends to over-select $C_{16}$ when it cannot distinguish AWGN from Rayleigh and treats the average SNR as informative on both. Second, adding $c_t$ corrects this by enabling a channel-conditional policy: under Rayleigh the selector becomes $L$-dominant, lowering payload from $0.089$ to $0.076$, while under AWGN it activates $C_{16}$ above the LDPC threshold. The full selector reaches $93.3\%$ accuracy versus the oracle.
+Two findings stand out. First, on this cliff codec the perception cues barely move realised F1: channel state alone reaches $0.909$ and the full selector matches it, and adding $\hat\gamma_t$ to the perception cues even nudges F1 down ($0.900\!\to\!0.897$) while raising payload, because SNR alone cannot separate AWGN from Rayleigh and the selector over-requests $C_{16}$. These extra $C_{16}$ requests are channel-blind---the same $0.07\!\to\!0.16$ request share on every channel, since $\hat\gamma_t$ carries no channel type---so on features-infeasible channels, Rayleigh and OFDM below its ${\approx}24$~dB threshold, where the LDPC block almost always fails, they collapse to the ego floor: the loss is channel-specific ($+0.006$ on AWGN, $-0.011$ on both Rayleigh and OFDM). The channel-type flag $c_t$ restores the gating, the same root that makes it the model's top feature (Section~\ref{sec:feat_imp}). This does not contradict the sufficiency of the SNR threshold in Section~\ref{sec:threshold}: SNR is decisive as the \emph{threshold signal} that gates the feature request under AWGN, but as an \emph{additional RF feature} atop the perception cues it adds a noisy continuous dimension without an F1 gain---the two roles are distinct. Second, adding $c_t$ enables a channel-conditional policy---under Rayleigh the selector becomes $L$-dominant while under AWGN it activates $C_{16}$ above the LDPC threshold---so what the cues change is \emph{deployed channel use}, not accuracy: by selecting the low-payload $L$ action more often at equal F1, the full selector spends $0.240$~Msym versus $0.271$ for channel state alone (the channel-averaged ${\approx}12\%$ reduction is quantified in Section~\ref{sec:headline}).
 
 \subsection{End-to-end Deployment Verification}\label{sec:e2e}
 
```


## #1 — Abstract, changed lines (@@ -31)

```diff
@@ -31,7 +31,7 @@ Peiyi Yue%
 \maketitle
 
 \begin{abstract}
-Connected and automated vehicles can improve perception reliability by exchanging information through vehicle-to-vehicle (V2V) links. However, cooperative perception must operate under limited bandwidth and time-varying vehicular channels. Existing communication-efficient perception methods mainly reduce redundancy within a fixed semantic representation, such as object-level detections or feature-level messages. This paper shows that fixed semantic granularity is suboptimal: feature-level messages are potentially more informative but can become unreliable or wasteful under poor channel quality, while object-level messages are compact and stable but less expressive. We propose \emph{Channel-Aware Task-Oriented Semantic Granularity Selection} (\method), a receiver-driven framework in which the ego vehicle selects the communication granularity for each frame from its own perception cues and estimated channel state, and signals the choice to the collaborator via a $2$-bit request piggy-backed on periodic V2X awareness messages, such as CAM/BSM, over 802.11bd or NR sidelink. \method{} chooses one message type from object-level communication and compressed feature-level communication modes before any high-payload transmission. We derive the selector as the Lagrangian-relaxed solution of a constrained perception-communication problem and instantiate it with a $400$-tree Random Forest. Experiments on the OPV2V dataset (validate, scene-disjoint test, and the Culver-City domain shift) under AWGN and Rayleigh channels show that, when the channel can carry feature-level messages, \method{} lifts true end-to-end AP@0.5 by up to $+0.05$ over object-level communication, while---averaged over all channel states---using $15.8$--$18.4\%$ of the bandwidth of fixed $C_{16}$ feature-level transmission under LDPC + 16-QAM coding; under fading it safely falls back to the robust object-level message. The estimated SNR and channel-type features jointly account for $65\%$ of the selector's feature importance, dominating $21$ ego-side cues. Crucially, we show that whether the task-oriented perception cues are needed at all is determined by the feature codec's channel response: under an LDPC + QAM cliff the estimated SNR is a near-sufficient statistic and a one-line threshold matches the learned selector, whereas under graceful importance-map JSCC the SNR becomes uninformative and the cue-based selector beats the best SNR threshold by $+0.017$ realised F1 ($95\%$ CI $[+0.012,+0.022]$). The deployed selector incurs $52.8$~ms per frame on a single CPU core, fitting the $100$~ms budget of a 10~Hz LiDAR cycle. These results demonstrate that channel-aware semantic granularity adaptation is an effective strategy for bandwidth-constrained V2V cooperative perception.
+Connected and automated vehicles can improve perception reliability by exchanging information through vehicle-to-vehicle (V2V) links. However, cooperative perception must operate under limited bandwidth and time-varying vehicular channels. Existing communication-efficient perception methods mainly reduce redundancy within a fixed semantic representation, such as object-level detections or feature-level messages. This paper shows that fixed semantic granularity is suboptimal: feature-level messages are potentially more informative but can become unreliable or wasteful under poor channel quality, while object-level messages are compact and stable but less expressive. We propose \emph{Channel-Aware Task-Oriented Semantic Granularity Selection} (\method), a receiver-driven framework in which the ego vehicle selects the communication granularity for each frame from its own perception cues and estimated channel state, and signals the choice to the collaborator via a $2$-bit request piggy-backed on periodic V2X awareness messages, such as CAM/BSM, over 802.11bd or NR sidelink. \method{} chooses one message type from object-level communication and compressed feature-level communication modes before any high-payload transmission. We derive the selector as the Lagrangian-relaxed solution of a constrained perception-communication problem and instantiate it with a $400$-tree Random Forest. Experiments on the OPV2V dataset (validate, scene-disjoint test, and the Culver-City domain shift) under AWGN and Rayleigh channels show that, when the channel can carry feature-level messages, \method{} lifts true end-to-end AP@0.5 by up to $+0.07$ over object-level communication where the channel carries feature-level messages (Culver-City), remaining comparable to object-level on the sparser test split, while---averaged over all channel states---using $16$--$25\%$ of the per-frame channel use of fixed $C_{16}$ feature-level transmission under rate-1/2 LDPC + 16-QAM coding; under fading it safely falls back to the robust object-level message. The channel-type and estimated SNR features jointly account for $62\%$ of the selector's feature importance, dominating $21$ ego-side cues. Crucially, the feature codec's channel response determines the \emph{currency} in which the perception cues pay: under an LDPC + QAM cliff channel state is a near-sufficient statistic---cues add no significant realised-F1 gain over channel state alone yet lower the selector's deployed channel use by ${\approx}12\%$ at matched F1---whereas under graceful importance-map JSCC the SNR becomes uninformative and the cue-based selector beats the best SNR threshold by $+0.027$ realised F1 ($95\%$ CI $[+0.024,+0.029]$); under deep fading the codec instead sets feasibility, the digital feature branch turning infeasible over the evaluated SNR range while analog JSCC survives. The deployed selector incurs $52.8$~ms per frame on a single CPU core, fitting the $100$~ms budget of a 10~Hz LiDAR cycle. These results demonstrate that channel-aware semantic granularity adaptation is an effective strategy for bandwidth-constrained V2V cooperative perception.
 \end{abstract}
 
 \begin{IEEEkeywords}
```


## #22 — conclusion, full -/+ (@@ -899)

```diff
@@ -899,7 +898,7 @@ Request delay & $1$-frame-stale decision & $\ge -0.057$ (pessimistic i.i.d.\ bou
 
 We presented \method{}, a channel-aware task-oriented semantic granularity selector for V2V cooperative perception. The selector takes per-frame LiDAR-derived perception cues together with an estimated SNR and a channel-type indicator and outputs one of three communication modes: a compact object-level message $L$, or a compressed feature-level message under 16- or 256-QAM coding. The selector is implemented as a lightweight Random Forest that adds no learnable parameters to the perception pipeline; the contribution is not the Random Forest itself but the channel-aware granularity policy, of which the forest is one interpretable implementation (a hand-tuned SNR-threshold rule captures much of the same effect, Section~\ref{sec:threshold}). It runs in $52.8 \pm 5.7$~ms ($\mathrm{P95} = 59.1$~ms) per frame on a single CPU core, within the $100$~ms budget of a $10$~Hz LiDAR cycle, and a decision tree or logistic-regression selector reaches the same F1 at $>10\times$ lower latency (Section~\ref{sec:robustness}).
 
-The results support three conclusions. First, under the evaluated LDPC + QAM feature-transmission setting, fixed feature-level communication is often dominated by compact object-level communication because of channel-induced cliff effects. Second, channel-aware semantic granularity selection recovers the feature-level detection gain only when the channel and task state justify it: when the channel can carry features it lifts true end-to-end AP@0.5 by up to $+0.05$ over object-level communication, while averaged over all channel states it spends $15.8$--$18.4\%$ of the bandwidth of fixed $C_{16}$, and this trade-off transfers to the scene-disjoint test split and the Culver-City domain shift with a frozen selector. Third, the dominant decision signal is channel state rather than selector-model complexity: a simple SNR-threshold rule already matches the learned selector on the channel-averaged payload--F1 frontier, and the $21$ ego-side perception cues add $<0.001$ aggregate F1 over channel state alone. The granularity policy's gain over object-level communication is itself frame-selective, reaching $+0.045$ F1 ($95\%$ CI $[+0.033,+0.059]$) on hard frames under a usable channel; we attribute the limited marginal value of the perception cues to the sharp LDPC + QAM SNR cliff, which makes the estimated SNR a near-sufficient statistic. When the feature branch instead uses graceful importance-map JSCC, the estimated SNR becomes uninformative and the picture reverses: the best SNR threshold collapses to object-level performance, and the cue-based selector beats it by $+0.017$ F1 ($95\%$ CI $[+0.012,+0.022]$) under AWGN and $+0.015$ under Rayleigh (Section~\ref{sec:jscc_aware}). Whether task-oriented perception cues are needed is thus determined by the feature codec's channel response: superfluous under a cliff codec, necessary under a graceful one.
+The results support three conclusions. First, under the evaluated LDPC + QAM feature-transmission setting, fixed feature-level communication is often dominated by compact object-level communication because of channel-induced cliff effects. Second, channel-aware semantic granularity selection recovers the feature-level detection gain only when the channel and task state justify it: when the channel can carry features it lifts true end-to-end AP@0.5 by up to $+0.074$ over object-level communication on the Culver-City domain shift ($+0.026$ on validate, and comparable to object-level on the sparser test split), while averaged over all channel states it spends $16$--$25\%$ of the channel use of fixed $C_{16}$, and this trade-off transfers to the scene-disjoint test split and the Culver-City domain shift with a frozen selector. Third, the dominant decision signal is channel state rather than selector-model complexity: a simple SNR-threshold rule closely tracks the learned selector on the channel-averaged payload--F1 frontier---which the selector marginally Pareto-dominates at matched channel use---and the $21$ ego-side perception cues add no significant aggregate F1 over channel state alone. The granularity policy's gain over object-level communication is itself frame-selective, reaching $+0.090$ F1 ($95\%$ CI $[+0.083,+0.096]$) on hard frames under a reliable channel; we attribute the limited marginal value of the perception cues to the sharp LDPC + QAM SNR cliff, which makes channel state a near-sufficient statistic. When the feature branch instead uses graceful importance-map JSCC, the estimated SNR becomes uninformative and the picture reverses: the best SNR threshold collapses to object-level performance, and the cue-based selector beats it by $+0.027$ F1 ($95\%$ CI $[+0.024,+0.029]$) under AWGN and $+0.022$ under Rayleigh (Section~\ref{sec:jscc_aware}). Whether task-oriented perception cues are needed is thus determined by the feature codec's channel response: under a cliff codec they pay in bandwidth (${\approx}12\%$ lower channel use at matched F1), while under a graceful codec they become necessary for accuracy ($+0.027$ F1).
 
 
 

```


## #16 — central-message sentence continuation (context, unchanged)

```latex
The interpretation is the central message of this paper: \emph{whether task-oriented
perception cues are needed for granularity selection is determined by the feature codec's
channel response.} Under a cliff codec the decision is channel-bound and SNR is sufficient;
under a graceful codec the decision becomes content-bound, the channel is no longer the
bottleneck, and the ego-side perception cues---which predict whether a frame's object-level
detection is already adequate---become the operative signal. A deployment that pairs an
object-level fallback with a JSCC feature branch therefore genuinely requires the
task-oriented selector this paper proposes.
```

**TG-12 sister check:** currency form (channel-bound/content-bound), no superfluous binary -> not changed.
