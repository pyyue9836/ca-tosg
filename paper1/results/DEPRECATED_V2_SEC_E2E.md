# DEPRECATED: sec:e2e / tab:e2e (End-to-end Deployment Verification) -- DELETED TG-21c

Why deleted (three locks):
1. Function superseded -- its mission (verify the analytical F1 proxy holds under
   deployment) is carried by sec:true_e2e (v3 true end-to-end AP verification).
2. Model deprecated -- it used a FIXED ego-only floor F_floor=0.63; the v3 pipeline
   replaced this with per-frame ego fallback baked into eff_C. Re-running would revive a
   dead model.
3. No v3 source -- its numbers (0.864/0.875/0.878 F1, v2 pre-canonical-GT basis) have
   no bit-correspondence in any v3 CSV; the experiment was never re-run under v3.

Honest v2-era work; removed for manuscript convergence, not buried.

--- original section text (main.tex L513-561, pre-deletion) ---

\subsection{End-to-end Deployment Verification}\label{sec:e2e}

Throughout Sections~\ref{sec:headline}--\ref{sec:ablation} the realised
frame F1 is computed by the analytical block-loss model of
Eq.~\eqref{eq:eff_C}, in which a block-error event contributes zero F1.
A receiver in a deployed V2X stack can detect block loss and fall back
to ego-only inference instead, recovering an empirical F1 floor of
approximately $0.63$ observed in our earlier reproduction of the
LDPC+QAM baselines~\cite{sheng2024importance}. To verify that the
analytical model is conservative and that our reported numbers survive
this softer floor, we re-evaluate the deployed selector under a
\emph{deployment-mode} pipeline: per frame, the selector picks $s_t$
from $(\hat\gamma_t,c_t)$; for each $C_q$-selected frame, the message
either survives with probability $1-\mathrm{BLER}_q(\gamma_t,\text{ch}_t)$
and contributes its clean F1, or is dropped with probability
$\mathrm{BLER}_q$ and contributes the ego-only floor $F_{\mathrm{floor}}=0.63$.
The Bernoulli realisations are averaged over $50$ runs per operating point.

\begin{table}[t]
\centering
\caption{End-to-end deployment-mode verification at single operating points (OPV2V validate, $T=1{,}980$ frames; deployed selector). The deployment-mode F1 with empirical ego-only floor is equal to or higher than the analytical lower bound used during selector training, confirming that the analytical numbers in Section~\ref{sec:headline}--\ref{sec:ablation} are conservative.}
\label{tab:e2e}
\begin{tabular}{lccccc}
\toprule
Channel & SNR (dB) & $\rho_L$ & Analytical F1 & E2E F1 (floor=0.63) & Payload \\
\midrule
AWGN     & 0.0  & 1.000 & 0.864 & $0.864 \pm 0.000$ & 0.024 \\
AWGN     & 10.0 & 1.000 & 0.864 & $0.864 \pm 0.000$ & 0.024 \\
AWGN     & 12.0 & 0.909 & 0.866 & $0.867 \pm 0.000$ & 0.067 \\
AWGN     & 14.0 & 0.331 & 0.864 & $\mathbf{0.875 \pm 0.001}$ & 0.339 \\
AWGN     & 16.0 & 0.326 & 0.878 & $0.878 \pm 0.000$ & 0.342 \\
AWGN     & 20.0 & 0.362 & 0.879 & $0.879 \pm 0.000$ & 0.324 \\
Rayleigh & 0.0  & 1.000 & 0.864 & $0.864 \pm 0.000$ & 0.024 \\
Rayleigh & 10.0 & 1.000 & 0.864 & $0.864 \pm 0.000$ & 0.024 \\
Rayleigh & 20.0 & 0.998 & 0.864 & $0.864 \pm 0.000$ & 0.025 \\
\bottomrule
\end{tabular}
\end{table}

Table~\ref{tab:e2e} confirms two properties. First, at every operating
point the deployment-mode F1 is at least as large as the analytical F1;
the gap reaches $0.010$~F1 at AWGN $14$~dB, where the selector is
transitioning between $L$ and $C_{16}$ and a non-negligible fraction of
$C_{16}$ frames experience block loss. The selector training objective is
therefore conservative, and the headline numbers in
Section~\ref{sec:headline} are a valid lower bound on the realised
deployment performance. Second, the Bernoulli sampling variance is small
(at most $0.001$ F1 across the table), which means that the analytical
expectation is a tight estimator of the deployment-mode realised F1.
