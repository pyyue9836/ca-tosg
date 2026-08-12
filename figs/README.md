# figs/ — README and framework assets

`figs/` holds the **sources** of the hand-drawn assets and the images the root `README.md`
displays. It is not where the paper's figures live: those are generated into `paper/figures/`
by `python tools/generate_figures.py`.

| asset | role | authority |
|---|---|---|
| `ca_tosg_overview.svg` | **SOURCE** of the system framework figure | hand-drawn (draw.io), see `DRAW_OVERVIEW_FIGURE.md` |
| `paper/figures/ca_tosg_method_overview.pdf` | **EXPORT** of `ca_tosg_overview.svg` for LaTeX | derived — never edit it directly |
| `results/*.png`, `results/*.svg` | README display copies of generated result figures | derived from `paper/figures/*.pdf` |
| `DRAW_OVERVIEW_FIGURE.md` | drawing instructions for the overview figure | source of record |

**Direction of derivation is one-way**: `figs/ca_tosg_overview.svg` → `paper/figures/*.pdf` → the
manuscript. If the overview figure needs a change, change the SVG and re-export; a PDF edited on
its own is a fork with no source.

`selector_pipeline.svg` is named in `RESTRUCTURE_PLAN.md` but **does not exist**: there is no source
asset for it, and a system diagram invented during a refactor would state a mechanism nobody
checked. It is listed as `NOT-CREATED` in `RESTRUCTURE_MAP.csv`.
