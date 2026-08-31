# `paper/` — 论文源码 / Paper source

## 中文

**这里只有一份正式稿。** 版本后缀目录（`v2_draft/`、`v2_full/` 之类）不再存在（V2-R47 A-3）。

- `main.tex` —— 期刊正文（IEEEtran）。
- `supplementary.tex` —— 补充材料。
- `references.bib` —— 参考文献（BibTeX）。
- `figures/` —— 正文与补充材料的插图（PDF），由 `tools/build_v2_figures.py` 生成。
- `tables/` —— **全部由 `tools/build_v2_paper_numbers.py` 生成**：`generated_numbers.tex`（宏）
  与 `tbl_*.tex`（表体）。**论文里任何数字都不得手敲**；`--check` 逐字节校验。
- `archive/` —— **已封存的旧文档，只读**。见下。

### `archive/` 里是什么，为什么不能改

`docs/STOP_WORK_v1_freeze.md`（V2-R47 A 修正案）冻结了这些文件。它们用 `git mv` 移入，
历史保留，内容逐字节不可改；`results/manifests/V1_FREEZE_WITNESS.json` 用**原哈希**钉住它们，
`tools/build_publication_manifest.py` 每次门禁运行都比对 **HEAD 里的** blob。改一个字节即 FAIL。

- `manuscript_frozen.tex` / `.pdf` —— v1 正文（原 `paper/main.tex`）
- `supplementary_frozen.tex` / `.pdf` —— v1 补充材料
- `results_brief.tex` / `.pdf` —— 4 页结果简报（原 `paper/v2_draft/main.tex`）
- `figures/`、`refs.bib`、`tables/` —— 上述文档自带的素材。这些 `.tex` 用
  `\graphicspath{{figures/}}` 与 `\bibliography{refs}`，都是相对自身目录的，所以搬家后
  **不用改一个字节**仍然自洽。
- `paragraph_drafts.md`、`SKELETON.md`、`DRAFT_P5.md` —— 当时的写作素材。

归档件只能作为**结构与文献素材**使用；实验数字、图、表、结论一律来自封账产物（A-4）。

**怎么编译**：`~/miniconda3/envs/latex/bin/tectonic main.tex`，或把 `main.tex`、
`supplementary.tex`、`references.bib`、`figures/`、`tables/` 传 Overleaf。

## English

**One official manuscript lives here.** No version-suffixed directories (V2-R47 A-3).

- `main.tex`, `supplementary.tex`, `references.bib`
- `figures/` — written by `tools/build_v2_figures.py`
- `tables/` — **entirely generated** by `tools/build_v2_paper_numbers.py`: `generated_numbers.tex`
  (macros) and `tbl_*.tex` (table bodies). No number in the manuscript is typed by hand; `--check`
  verifies byte for byte.
- `archive/` — **superseded documents, frozen and read-only.**

`docs/STOP_WORK_v1_freeze.md` (amendment V2-R47 A) freezes everything under `archive/`. The files
moved there with `git mv`, so the history follows the content;
`results/manifests/V1_FREEZE_WITNESS.json` pins them by their **original** SHA-256 and
`tools/build_publication_manifest.py` re-verifies the **committed** blobs on every gate run. A
one-byte edit is a gate failure. The archived `.tex` files use `\graphicspath{{figures/}}` and
`\bibliography{refs}`, both relative to their own directory, so the move left them self-consistent
without editing a byte.

The archive may be used for structure and bibliography only. Every experimental number, figure,
table and conclusion comes from the closed-out products (A-4).

---

**编译门禁会重写这两个 PDF。** `tests/test_compile.py` 每次运行都重建 `main.pdf` 与
`supplementary.pdf`,字节不完全一致(tectonic 的元数据会变)。这两份现在是**活稿**、不在冻结名单里,
所以重写本身无害;但跑完全套门禁后工作树会出现两处 PDF diff。内容没变时用
`git restore paper/main.pdf paper/supplementary.pdf` 丢掉即可。

**The compile gate rewrites both PDFs.** They are the live deliverable, not frozen, so the rewrite
is harmless — but a full gate run leaves two PDF diffs in the tree. When the content has not
changed, `git restore paper/main.pdf paper/supplementary.pdf`.
