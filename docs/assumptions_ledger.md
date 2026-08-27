# Assumptions ledger — physical semantics vs accounting convention

One row per **input artefact or physical quantity** the pipeline consumes. Each row states what the
thing *physically is*, what the pipeline *charges or assumes about it*, and whether those two agree.

This file exists because they did not agree, and nothing in the repository was positioned to notice:
the perception caches fused every collaborator in the frame while the payload model charged a single
message (Change-log **P0**). No gate could have caught that, because each half was internally
consistent — the mismatch lived in the join, which nothing wrote down.

**Rule: a new input artefact is registered here before it is used.** `tests/test_assumptions_ledger.py`
enforces it: an input-artefact reference in pipeline code that matches no registered pattern fails
the gate.

Status values: **OK** = semantics and accounting agree · **MISMATCH** = they do not · **BOUNDED** =
they agree only under a stated assumption, and the assumption is itself checked or bracketed.

---

## Perception caches

| artefact | physical semantics | accounting convention | status |
|---|---|---|---|
| `gs_rerun/ego_{split}.npz` | ego vehicle's own detections, no message received | action `E`, `B_E = 0`, always delivered | **OK** |
| `gs_rerun/late_{split}.npz` | late fusion of the ego with **every collaborator present in the frame** (2–3 CAVs on much of OPV2V) | action `L`, charged **one** message `B_L = 0.024` Msym, `BLER_L = 0` | **MISMATCH** — N-collaborator perception at 1-collaborator cost (P0) |
| `gs_rerun/comp_{split}.npz` | intermediate (compressed-feature) fusion over **every collaborator in the frame** | action `F`, charged **one** message `B_F = 0.99` Msym with a single link's frame BLER | **MISMATCH** — same defect (P0) |
| `gs_rerun/p4c_N1/{late,intermediate}_{split}.npz`, `p4c_N1/{branch}_{split}.npz` | fusion with the **nearest single collaborator** | one message paid, one collaborator received | **OK** — the corrected convention, ruling P0 (a) |
| `results/v2/wp2_per_agent_{split}.npz` | **v2, plan A.** Per-agent detections from the ONE unified checkpoint: the ego alone and the nearest single collaborator alone, each at `record_len=[1]` (an exact `AttFusion` identity), plus the frame's two-CAV cooperative GT. Collaborator chosen by the v1 P4-C rule via `CATOSG_MAX_COLLAB=1`. | inputs to actions `E` and `L`; **nothing is charged here** — payload is assigned in work package 7 from `N_box,t` and the measured `B_F` | **OK** — one checkpoint, one FOV, one GT, one collaborator; the four v1 confounds are absent by construction |
| `results/v2/wp5_tpfp_{split}.npz` | **v2, plan A.** Per-frame `(tp, fp, score)` decompositions of the clean-F, ego-only and total-loss predictions, at IoU 0.5 and 0.7 **stored separately** — matching is a function of the threshold, so one decomposition may not serve both. Produced by the single forward pass the main sweep had not persisted. | inputs to the message-regime Monte Carlo; **nothing is charged here** — this is scoring machinery, not a payload | **OK** — the only forward cost that had to be paid twice, and the reason it is stored is so no later analysis re-runs inference (V2-R15 C-2) |
| `gs_rerun/p4c_N{2,3}/…`, `p4c_N{n}/{branch}_{split}.npz` | fusion with the N nearest collaborators | `B_a × k_eff`, `k_eff = min(N, collaborators in frame)`; delivery `(1−b)^N` (semantics A) | **OK** — P4-C rulings 2–4 |
| `gs_rerun_second/*.npz` | the same branches under a SECOND/VoxelNet backbone | equal-budget protocol, `B_F ≡ 0.99` Msym, mainline `N_cw` | **OK** for the arm's own comparison; **not** comparable in absolute terms to the mainline |

## Payload and channel

| artefact | physical semantics | accounting convention | status |
|---|---|---|---|
| payload constants `B_L`, `B_F`, `B_{C256}` | bits on the wire for one message of each kind | declared convention: channel-use-equivalent Msym/frame under rate-1/2 LDPC with 16-/256-QAM; `main.tex` Eq. (7) + `tab:notation` | **OK** — bit-checked by `tests/test_payload.py` |
| `results/channel/bler_sionna.csv` | Sionna link-level simulation: codeword BLER `bler_cw` at a given `esno_db`, and the frame BLER `bler_frame` obtained from it over `n_cw` codewords | looked up per (QAM, channel, SNR) and applied **once per frame per message**: `eff_F = comp·(1−b) + ego·b` | **OK at N=1.** At N>1 the same table is composed as `(1−b)^N`, which assumes **independent links** — stated, not measured |
| SNR grid | 11 points, 0–20 dB, both channel types | the deterministic training substrate: every frame × 11 SNR × 2 channels | **OK** |
| CSI draws | per-frame block fading, one `(SNR, channel)` per frame per realisation | 200 realisations, `seed = 20260809`, **paired** across policies; CI by paired bootstrap (10,000 resamples, `seed = 12345`) | **BOUNDED** — i.i.d. per frame, no temporal correlation; the Jakes-model and stale-decision rows of `tab:robustness` bracket that assumption |

## Labels and scoring

| artefact | physical semantics | accounting convention | status |
|---|---|---|---|
| canonical union GT (`comp_{split}.npz['gts']`) | the union of ground-truth objects over the **full** collaborator set | held **fixed for every arm**, whatever N that arm fuses (P4-C ruling 1) | **BOUNDED** — deliberate: per-N GT would score each arm on a different ruler. The consequence must be stated when N=1 numbers are quoted: objects only a *non-fused* collaborator could see stay in the denominator, so N=1 F1 is a lower bound against a full-set ruler, not a re-based metric |
| per-frame F1 | IoU-0.5, unit scores, no crop or visibility filter | the same scorer for every branch and every arm | **OK** |
| oracle labels | argmax over the **feasibility-masked** `{E, L, F}` utilities | `F` masked out where `BLER_F ≥ 0.999`; ties resolved to the earlier/cheaper action | **OK** — PROTOCOL §4 |
| 23 selector cues | 21 LiDAR/scene cues + estimated SNR + channel-type flag | none of them encodes N, so the per-frame **action** is N-independent; N changes what an action costs and delivers | **OK** — and it is why the P0 correction can reuse the frozen cue definitions |

## Derived per-frame tables and substrates

| artefact | physical semantics | accounting convention | status |
|---|---|---|---|
| `dataset_validate.csv`, `dataset_{split}.csv`, `dataset_{split}_v3.csv` | the per-frame table: 21 LiDAR/scene cues plus `ego_f1` / `late_f1` / `compressed_f1` read from the caches above, i.e. **full-collaborator** utilities | consumed by the grid builder as "the utility of each action for this frame", charged as one message | **MISMATCH** — inherits the P0 defect from its source caches; superseded for the main experiment by `dataset_{split}_n1.csv` |
| `dataset_{split}_n1.csv` | the same table with `late_f1` / `compressed_f1` rebuilt from the N=1 caches, `ego_f1` and the cues unchanged (both N-independent) | one message paid, one collaborator received | **OK** — the P0-corrected main experiment |
| `dataset_{split}_second.csv` | the same table under the SECOND backbone | equal-budget arm accounting | **OK** within the arm; absolute numbers not comparable to the mainline |
| `p2_grid_{split}.csv` | the deterministic training substrate: every frame × 11 SNR × 2 channels, with `eff_E/L/F` and the feasibility-masked oracle label | pure arithmetic over the per-frame table and the BLER table; **inherits whatever convention its source table carries** | **OK as a transform** — its status is exactly that of the `dataset_*` row it was built from |
| `p4c_B_second/{late,intermediate}_{split}.npz`, `p4c_B_second/{branch}_{split}.npz` | the second-nearest collaborator **alone** delivering | semantics-B bracket for P4-C only, never a main-experiment input | **OK** — bracket, not a deployed convention |

## Appendix / prior-protocol arm inputs

| artefact | physical semantics | accounting convention | status |
|---|---|---|---|
| `jscc_perframe_f1_{split}_snr{split}.npz`, `jscc_{split}_snr{split}.npz`, `jscc_{split}_snr{split}.npz` glob form `jscc_*_snr*.npz` | per-frame F1 of the JSCC feature branch at each SNR grid point, full-collaborator fusion | Appendix A arm: reported as F1 and `com_rate`, with **no** Msym payload conversion | **BOUNDED** — self-consistent inside the appendix; it carries the same full-collaborator semantics as the retired mainline, so its absolute levels are not comparable to the P0-corrected main experiment, and the appendix says so |
| `ldpc_qam_bler_table.csv` | the WCSP-era LDPC + QAM block-error table used by the prior-protocol arms | looked up per (QAM, SNR) exactly as `bler_sionna.csv` is in the mainline | **BOUNDED** — a *different* table from the mainline's Sionna chain; the two are never mixed within one arm |
| `bler_sionna_ofdm.csv` | frame BLER over the frequency-selective TDL/OFDM link (τ_rms = 46.2 ns) | used only in the codec-comparison analysis, never in the headline | **OK** |
| `bler_frame_second.csv`, `bler_onset_second.csv` | frame BLER and activation onset re-derived at the SECOND arm's own `N_cw` | equal-budget protocol: `B_F ≡ 0.99` Msym with `N_cw` re-derived, never inherited | **OK** — P4-B-d |
| `data/where2comm_v2/{split}_thr{thr}.npz` | cached per-frame Where2comm detections (boxes, scores, GT) and the MEASURED communication rate, one file per (threshold, split), produced with `CATOSG_MAX_COLLAB=1` | R51-R55 adjacent-arm products, DESCRIPTIVE: the threshold is the control, the sparsity is an output, and the payload is a counterfactual under the pre-registered sparse convention. Not a deployed product and not in any frozen table |

---

## How to register a new artefact

1. Add a row with all four columns filled. "Unknown" is not a status; if the semantics are unclear,
   that is the finding, and it belongs in the change-log before the artefact is used.
2. If the status is **MISMATCH** or **BOUNDED**, say in the same row what the consequence is and
   where it is bracketed.
3. `python tests/test_assumptions_ledger.py` must pass before the artefact is consumed.
