# Uncovered numeric literals -- the R23-15 debt register

`tests/test_numeric_literals.py` requires every decimal literal in the delivered text to be covered
by a verified binding: a claim literal confirmed inside the CSV its own ledger row names, a located
or declared-derived table cell, a registry-derived quantity, or a structural entry.

The literals below are **not** covered today. They are recorded here so the gate can fail on anything
NEW while the existing debt is burned down deliberately: adding a number to the paper that nothing
verifies is a failure, and shrinking this file is the work. Each line is `file:line literal context`.

**Count when the register was opened (R23-15, 2026-08-18): 115.**
Most are prose CI bounds and inline differences whose ledger rows carry no CSV binding at all --
they are among the 67 rows `p6_numbers_vs_csv` reports as `unbound-or-no-literal` -- plus
`docs/model_zoo.md`, which quotes model-zoo AP values that live in no committed product of this repo.

- `paper/main.tex:161` `1.98` -- where $\phi_q(\cdot)$ denotes a feature encoding and communication process for mode $C_q$. The two f
- `paper/main.tex:192` `3.96` -- B_L = 0.024, \quad B_{F} = 3.96/4 \approx 0.99, \quad B_{C_{256}} = 3.96/8 \approx 0.495,
- `paper/main.tex:192` `3.96` -- B_L = 0.024, \quad B_{F} = 3.96/4 \approx 0.99, \quad B_{C_{256}} = 3.96/8 \approx 0.495,
- `paper/main.tex:195` `3.96` -- all in Msym/frame, where $3.96 = 1.98/(1/2)$ is the coded-bit count produced by rate-$1/2$ LDPC from
- `paper/main.tex:195` `1.98` -- all in Msym/frame, where $3.96 = 1.98/(1/2)$ is the coded-bit count produced by rate-$1/2$ LDPC from
- `paper/main.tex:195` `1.98` -- all in Msym/frame, where $3.96 = 1.98/(1/2)$ is the coded-bit count produced by rate-$1/2$ LDPC from
- `paper/main.tex:235` `3.96` -- From a rate-distortion perspective, the effective F1 model of Eq.~\eqref{eq:eff_C} is a channel-indu
- `paper/main.tex:311` `0.999` -- The selector is trained to imitate the channel-aware oracle defined in Eq.~\eqref{eq:oracle}. The or
- `paper/main.tex:436` `0.67` -- \caption{Qualitative BEV comparison on one OPV2V frame (shaded green: ground-truth boxes; outlines: 
- `paper/main.tex:436` `0.95` -- \caption{Qualitative BEV comparison on one OPV2V frame (shaded green: ground-truth boxes; outlines: 
- `paper/main.tex:466` `0.58` -- Under the corrected single-collaborator convention this limitation became \emph{cheaper without beco
- `paper/main.tex:466` `0.61` -- Under the corrected single-collaborator convention this limitation became \emph{cheaper without beco
- `paper/main.tex:466` `0.44` -- Under the corrected single-collaborator convention this limitation became \emph{cheaper without beco
- `paper/main.tex:466` `0.47` -- Under the corrected single-collaborator convention this limitation became \emph{cheaper without beco
- `paper/main.tex:532` `0.0090` -- Under the corrected convention the cues do add accuracy on this axis ($+0.0090$ over channel state a
- `paper/main.tex:657` `0.0074` -- monotonically with difficulty: on test it is $-0.0047$ ($95\%$ CI $[-0.0074,-0.0024]$) on
- `paper/main.tex:657` `0.0024` -- monotonically with difficulty: on test it is $-0.0047$ ($95\%$ CI $[-0.0074,-0.0024]$) on
- `paper/main.tex:658` `0.0056` -- easy frames, $+0.0056$ ($[+0.0027,+0.0085]$) on medium frames and
- `paper/main.tex:658` `0.0027` -- easy frames, $+0.0056$ ($[+0.0027,+0.0085]$) on medium frames and
- `paper/main.tex:658` `0.0085` -- easy frames, $+0.0056$ ($[+0.0027,+0.0085]$) on medium frames and
- `paper/main.tex:659` `0.0660` -- $\mathbf{+0.0660}$ ($[+0.0591,+0.0730]$) on hard frames. Validate has the same shape
- `paper/main.tex:659` `0.0591` -- $\mathbf{+0.0660}$ ($[+0.0591,+0.0730]$) on hard frames. Validate has the same shape
- `paper/main.tex:659` `0.0730` -- $\mathbf{+0.0660}$ ($[+0.0591,+0.0730]$) on hard frames. Validate has the same shape
- `paper/main.tex:660` `0.0441` -- ($+0.0058 / +0.0441 / +0.0470$); Culver-City is weaker throughout
- `paper/main.tex:660` `0.0470` -- ($+0.0058 / +0.0441 / +0.0470$); Culver-City is weaker throughout
- `paper/main.tex:661` `0.0011` -- ($+0.0011 / +0.0021 / +0.0310$). The value of \method{} is therefore two-dimensional:
- `paper/main.tex:661` `0.0310` -- ($+0.0011 / +0.0021 / +0.0310$). The value of \method{} is therefore two-dimensional:
- `paper/main.tex:664` `0.0040` -- slightly over-requests $F$ on test, a $-0.0040$ F1 effect that a payload-penalised
- `paper/main.tex:677` `0.0660` -- $+0.0660$ ($95\%$ CI $[+0.0591,+0.0730]$).}
- `paper/main.tex:677` `0.0591` -- $+0.0660$ ($95\%$ CI $[+0.0591,+0.0730]$).}
- `paper/main.tex:677` `0.0730` -- $+0.0660$ ($95\%$ CI $[+0.0591,+0.0730]$).}
- `paper/main.tex:698` `0.00067` -- $+0.00067$ rather than behind. Neither half of the input is sufficient on its own, and the shape of 
- `paper/main.tex:715` `0.00002` -- ${\approx}0.0001$ ($95\%$ CI upper bound $-0.00002$, so still entirely below zero) yet within the
- `paper/main.tex:779` `0.0300` -- $+0.0300$ F1 for $+0.1183$~Msym, and the third collaborator adds only $+0.0061$ more F1 for a furthe
- `paper/main.tex:779` `0.1183` -- $+0.0300$ F1 for $+0.1183$~Msym, and the third collaborator adds only $+0.0061$ more F1 for a furthe
- `paper/main.tex:779` `0.0061` -- $+0.0300$ F1 for $+0.1183$~Msym, and the third collaborator adds only $+0.0061$ more F1 for a furthe
- `paper/main.tex:780` `0.0991` -- $+0.0991$~Msym---about a fifth of the gain for three-quarters of the extra channel use. On test the
- `paper/main.tex:781` `0.0008` -- pattern is the same but flatter ($+0.0096$ then $+0.0008$), because that split is thinner and
- `paper/main.tex:789` `0.0003` -- differ by $+0.0001$ to $+0.0003$ F1 across the three budgets, so the conclusions here do not depend
- `paper/main.tex:813` `0.01` -- $\mathrm{BLER}_L\in\{0.01,0.05,0.10\}$, with every policy frozen and blind to it, leaves the payload
- `paper/main.tex:819` `0.00010` -- against it, from $-0.00010$ to $-0.00056$ --- the threshold rule leans harder on the feature action
- `paper/main.tex:819` `0.00056` -- against it, from $-0.00010$ to $-0.00056$ --- the threshold rule leans harder on the feature action
- `paper/main.tex:820` `0.12` -- ($\rho_F=0.20$ against $0.12$) and is correspondingly less exposed to an unreliable $L$. We report
- `paper/main.tex:889` `0.89` -- JSCC feature F1, by contrast, is \emph{essentially flat} at $\approx 0.89$ across the
- `paper/main.tex:914` `0.0032` -- $+0.002 < +0.0032 < +0.0090$: the cue axis, smallest and indistinguishable from zero under the
- `paper/main.tex:914` `0.0090` -- $+0.002 < +0.0032 < +0.0090$: the cue axis, smallest and indistinguishable from zero under the
- `paper/main.tex:920` `0.012` -- split, and to $+0.012$--$+0.015$ on the Culver-City domain shift (all CIs exclude zero). In the sepa
- `paper/main.tex:920` `0.015` -- split, and to $+0.012$--$+0.015$ on the Culver-City domain shift (all CIs exclude zero). In the sepa
- `paper/main.tex:931` `0.14` -- over-selects the feature action (JSCC C-request rate $0.14\!\to\!0.42$) and its realised F1
- `paper/main.tex:931` `0.42` -- over-selects the feature action (JSCC C-request rate $0.14\!\to\!0.42$) and its realised F1
- `paper/main.tex:953` `0.89` -- whereas the learned JSCC feature is flat at $\approx 0.89$ (SNR uninformative).
- `paper/main.tex:1009` `0.7752` -- late-fusion model ($0.7752$ vs.\ $0.775$; $0.6822$ vs.\ $0.682$) and to within $+0.0019$ for the
- `paper/main.tex:1009` `0.775` -- late-fusion model ($0.7752$ vs.\ $0.775$; $0.6822$ vs.\ $0.682$) and to within $+0.0019$ for the
- `paper/main.tex:1009` `0.6822` -- late-fusion model ($0.7752$ vs.\ $0.775$; $0.6822$ vs.\ $0.682$) and to within $+0.0019$ for the
- `paper/main.tex:1009` `0.682` -- late-fusion model ($0.7752$ vs.\ $0.775$; $0.6822$ vs.\ $0.682$) and to within $+0.0019$ for the
- `paper/main.tex:1009` `0.0019` -- late-fusion model ($0.7752$ vs.\ $0.775$; $0.6822$ vs.\ $0.682$) and to within $+0.0019$ for the
- `README.md:41` `0.8915` -- | 0.10 | CA-TOSG | 0.8915 | **0.0368** | 0.8697 |
- `README.md:42` `0.8925` -- | 0.10 | SNR-threshold (nominal) | 0.8925 | 0.0724 | -- |
- `README.md:44` `0.8970` -- | 0.20 | SNR-threshold (nominal) | 0.8970 | 0.2168 | -- |
- `README.md:45` `0.8978` -- | 0.30 | CA-TOSG | 0.8978 | **0.2120** | 0.8742 |
- `README.md:46` `0.8990` -- | 0.30 | SNR-threshold (nominal) | 0.8990 | 0.3125 | -- |
- `README.md:49` `0.7350` -- 0.8931, ego-only = 0.7350 (headroom 0.0240).
- `README.md:56` `0.00067` -- selector's favour (+0.00067). Quote both or neither.
- `README.md:93` `0.9070` -- | 0.10 | `selector_B010` | 0.05 | 18.0 dB | 0.9070 | 0.0679 |
- `README.md:93` `0.0679` -- | 0.10 | `selector_B010` | 0.05 | 18.0 dB | 0.9070 | 0.0679 |
- `README.md:94` `0.9087` -- | 0.20 | `selector_B020` | 0.02 | 12.0 dB | 0.9087 | 0.0992 |
- `README.md:94` `0.0992` -- | 0.20 | `selector_B020` | 0.02 | 12.0 dB | 0.9087 | 0.0992 |
- `README.md:95` `0.9094` -- | 0.30 | `selector_B030` | 0.00 | 8.0 dB | 0.9094 | 0.1570 |
- `README.md:95` `0.1570` -- | 0.30 | `selector_B030` | 0.00 | 8.0 dB | 0.9094 | 0.1570 |
- `docs/model_zoo.md:10` `3.10` -- **Frozen** 2026-08-09 15:12:53 UTC, seed 0, python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2
- `docs/model_zoo.md:10` `1.7` -- **Frozen** 2026-08-09 15:12:53 UTC, seed 0, python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2
- `docs/model_zoo.md:10` `1.26` -- **Frozen** 2026-08-09 15:12:53 UTC, seed 0, python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2
- `docs/model_zoo.md:10` `2.2` -- **Frozen** 2026-08-09 15:12:53 UTC, seed 0, python 3.10.18 / sklearn 1.7.0 / numpy 1.26.4 / pandas 2
- `docs/model_zoo.md:27` `0.8555` -- | 0.10 | 0.8555 | 0.8783 | 0.03276 | 0.8611 | 0.080803 | yes |
- `docs/model_zoo.md:27` `0.8783` -- | 0.10 | 0.8555 | 0.8783 | 0.03276 | 0.8611 | 0.080803 | yes |
- `docs/model_zoo.md:27` `0.03276` -- | 0.10 | 0.8555 | 0.8783 | 0.03276 | 0.8611 | 0.080803 | yes |
- `docs/model_zoo.md:27` `0.8611` -- | 0.10 | 0.8555 | 0.8783 | 0.03276 | 0.8611 | 0.080803 | yes |
- `docs/model_zoo.md:27` `0.080803` -- | 0.10 | 0.8555 | 0.8783 | 0.03276 | 0.8611 | 0.080803 | yes |
- `docs/model_zoo.md:28` `0.8606` -- | 0.20 | 0.8606 | 0.8807 | 0.188792 | 0.8646 | 0.150158 | yes |
- `docs/model_zoo.md:28` `0.8807` -- | 0.20 | 0.8606 | 0.8807 | 0.188792 | 0.8646 | 0.150158 | yes |
- `docs/model_zoo.md:28` `0.188792` -- | 0.20 | 0.8606 | 0.8807 | 0.188792 | 0.8646 | 0.150158 | yes |
- `docs/model_zoo.md:28` `0.8646` -- | 0.20 | 0.8606 | 0.8807 | 0.188792 | 0.8646 | 0.150158 | yes |
- `docs/model_zoo.md:28` `0.150158` -- | 0.20 | 0.8606 | 0.8807 | 0.188792 | 0.8646 | 0.150158 | yes |
- `docs/model_zoo.md:29` `0.8622` -- | 0.30 | 0.8622 | 0.884 | 0.262262 | 0.8662 | 0.201607 | yes |
- `docs/model_zoo.md:29` `0.884` -- | 0.30 | 0.8622 | 0.884 | 0.262262 | 0.8662 | 0.201607 | yes |
- `docs/model_zoo.md:29` `0.262262` -- | 0.30 | 0.8622 | 0.884 | 0.262262 | 0.8662 | 0.201607 | yes |
- `docs/model_zoo.md:29` `0.8662` -- | 0.30 | 0.8622 | 0.884 | 0.262262 | 0.8662 | 0.201607 | yes |
- `docs/model_zoo.md:29` `0.201607` -- | 0.30 | 0.8622 | 0.884 | 0.262262 | 0.8662 | 0.201607 | yes |
- `docs/model_zoo.md:35` `0.9892` -- | 0.10 | **E** | 0.9892 | 0.7244 | 0.8364 | 635 |
- `docs/model_zoo.md:35` `0.7244` -- | 0.10 | **E** | 0.9892 | 0.7244 | 0.8364 | 635 |
- `docs/model_zoo.md:35` `0.8364` -- | 0.10 | **E** | 0.9892 | 0.7244 | 0.8364 | 635 |
- `docs/model_zoo.md:36` `0.9566` -- | | **L** | 0.9566 | 0.9981 | 0.9769 | 38834 |
- `docs/model_zoo.md:36` `0.9981` -- | | **L** | 0.9566 | 0.9981 | 0.9769 | 38834 |
- `docs/model_zoo.md:36` `0.9769` -- | | **L** | 0.9566 | 0.9981 | 0.9769 | 38834 |
- `docs/model_zoo.md:37` `0.972` -- | | **F** | 0.972 | 0.6113 | 0.7506 | 4091 |
- `docs/model_zoo.md:37` `0.6113` -- | | **F** | 0.972 | 0.6113 | 0.7506 | 4091 |
- `docs/model_zoo.md:37` `0.7506` -- | | **F** | 0.972 | 0.6113 | 0.7506 | 4091 |
- `docs/model_zoo.md:38` `0.9918` -- | 0.20 | **E** | 0.9918 | 0.8043 | 0.8883 | 603 |
- `docs/model_zoo.md:38` `0.8043` -- | 0.20 | **E** | 0.9918 | 0.8043 | 0.8883 | 603 |
- `docs/model_zoo.md:38` `0.8883` -- | 0.20 | **E** | 0.9918 | 0.8043 | 0.8883 | 603 |
- `docs/model_zoo.md:39` `0.9655` -- | | **L** | 0.9655 | 0.9964 | 0.9807 | 36211 |
- `docs/model_zoo.md:39` `0.9964` -- | | **L** | 0.9655 | 0.9964 | 0.9807 | 36211 |
- `docs/model_zoo.md:39` `0.9807` -- | | **L** | 0.9655 | 0.9964 | 0.9807 | 36211 |
- `docs/model_zoo.md:40` `0.9758` -- | | **F** | 0.9758 | 0.8246 | 0.8939 | 6746 |
- `docs/model_zoo.md:40` `0.8246` -- | | **F** | 0.9758 | 0.8246 | 0.8939 | 6746 |
- `docs/model_zoo.md:40` `0.8939` -- | | **F** | 0.9758 | 0.8246 | 0.8939 | 6746 |
- `docs/model_zoo.md:41` `1.0` -- | 0.30 | **E** | 1.0 | 1.0 | 1.0 | 529 |
- `docs/model_zoo.md:41` `1.0` -- | 0.30 | **E** | 1.0 | 1.0 | 1.0 | 529 |
- `docs/model_zoo.md:41` `1.0` -- | 0.30 | **E** | 1.0 | 1.0 | 1.0 | 529 |
- `docs/model_zoo.md:42` `0.9994` -- | | **L** | 0.9994 | 1.0 | 0.9997 | 34988 |
- `docs/model_zoo.md:42` `1.0` -- | | **L** | 0.9994 | 1.0 | 0.9997 | 34988 |
- `docs/model_zoo.md:42` `0.9997` -- | | **L** | 0.9994 | 1.0 | 0.9997 | 34988 |
- `docs/model_zoo.md:43` `1.0` -- | | **F** | 1.0 | 0.9974 | 0.9987 | 8043 |
- `docs/model_zoo.md:43` `0.9974` -- | | **F** | 1.0 | 0.9974 | 0.9987 | 8043 |
- `docs/model_zoo.md:43` `0.9987` -- | | **F** | 1.0 | 0.9974 | 0.9987 | 8043 |
