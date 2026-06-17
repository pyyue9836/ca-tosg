# Paper #2 LaTeX source

IEEEtran-style skeleton for "CSI-Aware Semantic Granularity Selection
for Bandwidth-Constrained V2V Cooperative Perception".

## Files

- `main.tex`  — paper skeleton with abstract, 6 sections, figure
  includes, headline table, contribution bullets.
- `refs.bib`  — pre-populated with the 9 citations the paper currently
  references (OPV2V, Where2comm, ImportanceMapJSCC, SComCP, PointPillars,
  802.11bd, V2X-ViT, Random Forest, Transformer).
- `figures/` — empty; figures are pulled from
  `../runs/v3_with_rf/`, `../runs/v2/`, `../runs/v1/` via the
  `\graphicspath{}` directive in `main.tex`.

## Build (two options)

### Option A — Overleaf (recommended)
1. Zip this `paper/` folder together with the figures you reference:
   ```bash
   cd /home/josh/cooperative_semantic_perception/OpenCOOD/paper2_csi
   zip -r paper_overleaf.zip paper \
       runs/v3_with_rf/fig_ap50_*.png runs/v3_with_rf/fig_ap70_*.png \
       runs/v2/fig_decisions_*.png
   ```
2. Upload `paper_overleaf.zip` to Overleaf as a new project. IEEEtran is
   pre-installed; click Recompile.

### Option B — Local
```bash
sudo apt install texlive-publishers texlive-latex-extra latexmk
cd /home/josh/cooperative_semantic_perception/OpenCOOD/peiyi_work/01_paper_ca_tosg/paper
latexmk -pdf main.tex
```
Output is `main.pdf` in the same dir.

## TODOs flagged inside `main.tex`

Search for `% TODO:` in `main.tex` — each TODO marks a paragraph you
still need to write. Approximate writing budget:

- Section 1 (Intro): 3 paragraphs + contribution bullets (~1 page)
- Section 2 (Related Work): 4 subsections, ~0.75 page total
- Section 3 (System Model): mostly written, ~1 page with eqs
- Section 4 (Method): mostly written, add 1 paragraph on RF choice
- Section 5 (Experiments): subsections drafted; need feature-importance
  paragraph, ablations, negative result discussion
- Section 6 (Conclusion): 2 paragraphs

Total prose to write: about 4 pages of single-column body text.

## Numbers to cite verbatim in the prose

From `runs/v2/summary.csv`:
- Oracle 3-way: payload 0.074 Mbit, F1 0.868
- Fixed L: payload 0.024 Mbit, F1 0.862
- Fixed C-16: payload 0.495 Mbit, F1 0.385
- Fixed C-256: payload 0.248 Mbit, F1 0.101
- RF + CSI + channel type: payload 0.076 Mbit, F1 0.865

Feature importances (CSI-aware RF, `runs/v2/feature_importance_full.csv`):
- `est_snr_db`: 0.405
- `channel_is_rayleigh`: 0.245
- `pcd_mean_range`: 0.033
- next strongest cues all < 0.025

From `runs/v3/`-`runs/v3_with_rf/`:
- ImportanceMapJSCC AP@0.5 at SNR=0 dB AWGN: 0.833
- ImportanceMapJSCC AP@0.5 at SNR=12 dB AWGN: 0.863
- Fixed L AP@0.5 (channel-invariant): 0.840
- LDPC+16-QAM AP@0.5 at SNR=10 dB AWGN: 0.650
- Upper bound AP@0.5: 0.870
