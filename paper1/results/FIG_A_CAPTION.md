# Figure A caption (for main.tex; covers all 4 dead panels + coincidence note + Fixed-L within bounds)

\caption{Channel $\times$ codec delivery AP@0.5 on the OPV2V test split---a fixed-codec characterisation:
each curve is the AP of always transmitting the feature message through that codec, with ego-only detection
as the failure fallback (this is a codec-response figure; it shows no selector curve). Rows: AWGN / Rayleigh
/ OFDM; columns: LDPC + 16-QAM / LDPC + 256-QAM / JSCC. Reference lines: the error-free delivery ceiling
(identity channel, AP $=0.922$); the object-level $L$ alternative available to an adaptive selector
(AP $=0.919$)---on this test split the two nearly coincide, the graphical form of the $+0.002$ ``comparable''
result of Table~\ref{tab:headline}; and the ego-only failure floor (AP $=0.735$). Digital LDPC delivery shows
a cliff whose feasibility threshold rises as the diversity order falls: AWGN (no fading) clears the
frame-error cliff by $8$~dB; OFDM (frequency-selective, empirical diversity order $\approx 2$ from a BLER
slope fit) only near $24$~dB, above the evaluated $0$--$20$~dB range; flat Rayleigh (no diversity, frame
BLER $\approx 1$ because the coherence time is far shorter than the frame airtime) never clears it---so the
flat LDPC lines at the ego floor on \emph{both} Rayleigh and OFDM are the physical feasibility limit, not a
plotting artefact. Analog JSCC degrades gracefully and delivers on all three channels.}

Body sentence (same monotone, must appear in text too): the OFDM-LDPC feasibility threshold (${\approx}24$~dB,
empirical diversity order ${\approx}2$, BLER slope fit) and the unbounded flat-Rayleigh threshold both lie
above the evaluated SNR range; feasibility is monotone in diversity order (8 / ${\approx}24$ / unbounded dB).
