# `paper/` — 论文源码 / Paper source

## 中文

这里是论文本体的 LaTeX 源码。
- `main.tex` —— 论文正文（IEEEtran 格式，约 18–20 页）。所有章节、公式、表格、图引用都在这里。
- `refs.bib` —— 参考文献（BibTeX）。
- `figures/` —— 所有插图（PDF）。每张图由哪个脚本生成，见 `figures/README.md`。
- `DRAW_OVERVIEW_FIGURE.md` —— 系统总览图 `ca_tosg_method_overview.pdf` 的绘制说明（手工绘制）。

**怎么编译**：把本文件夹（含 `figures/`）传到 Overleaf；或本地装好 texlive 后 `latexmk -pdf main.tex`。
仓库根目录的 `paper_overleaf.zip` 就是 `main.tex + refs.bib + figures/` 打好的包，可直接上传 Overleaf。

## English

LaTeX source of the paper itself.
- `main.tex` — the manuscript (IEEEtran, ~18–20 pages): all sections, equations, tables, figure refs.
- `refs.bib` — bibliography (BibTeX).
- `figures/` — all figures (PDF). See `figures/README.md` for which script produces each one.
- `DRAW_OVERVIEW_FIGURE.md` — drawing notes for the hand-made system-overview figure.

**Build**: upload this folder (with `figures/`) to Overleaf, or locally run `latexmk -pdf main.tex`
(needs `texlive-publishers texlive-latex-extra latexmk`). The repo-root `paper_overleaf.zip` is a
ready-to-upload bundle.
