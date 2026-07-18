# DEPRECATED: two-regime figure/table — VALIDATE render

`fig_two_regime.pdf` and `tab:two_regime` were moved from the **validate** split to
the frozen **test** split (2,170 frames) to match the rest of Section~\ref{sec:jscc_aware}.

## What changed
- Figure/table source: `two_regime_edge_v3.csv`, rows `channel=awgn, split=test`.
- Panel (b) bars (test): L 0.9011, best-thr 0.9179 (LDPC) / 0.9011 (JSCC),
  RF 0.9226 (LDPC) / 0.9277 (JSCC), oracle 0.9280 / 0.9324.
- Edges (RF − threshold), bit-reproduced by `make_two_regime_figure.py` against
  `two_regime_edge_v3.csv`: LDPC **+0.00468** (→ prose/table +0.005),
  JSCC **+0.02657** (→ +0.027). Both asserted to <1e-9 in the generator.
- Panel (a) JSCC feature F1 flat level: validate ≈0.86 → **test ≈0.89** (0.8905–0.8916
  across 0–20 dB). main.tex L746/L788 updated accordingly.

## Deprecated artifacts
- Old **validate** `fig_two_regime.pdf` (git blob dated 2026-06-27) — REPLACED in place
  by the test render (md5 `46e87a5a…`). No separate validate copy is retained.
- `results/two_regime_bars.csv` — VALIDATE-era orphan. The current generator prints the
  plotted bars to stdout and no longer writes this CSV; the file is stale and unused.

## Why not deleted
Kept as a paper trail per the block-exit discipline (stale-fingerprint ledger). The
manuscript points only at the test render; nothing live reads the validate artifacts.
