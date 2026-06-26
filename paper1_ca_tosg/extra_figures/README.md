# `extra_figures/` — 两张概念图脚本 / Two conceptual-figure scripts

## 中文

本次修订新增的两张图的绘制脚本。图直接写到 `../paper/figures/`。

- `make_bler_figure.py` —— **信道 BLER 曲线**：LDPC+16/256-QAM 在 AWGN（实线）和 Rayleigh（虚线）下的
  误块率 vs SNR。直观展示「16-QAM 的 cliff 在 ~12dB（selector 拐点）、256-QAM cliff 远靠右（被 dominated）、
  Rayleigh 始终不可靠（所以守 L）」。→ `fig_channel_bler.pdf`
- `make_qualitative_figure.py` —— **定性 BEV 对比**：某一帧上，物体级 L（左）vs 特征级 C（右）的检测框叠加
  在点云 + GT 上。展示 L 误检多、C 干净。全用缓存的 `.npy` 画，不重跑推理。→ `fig_qualitative_bev.pdf`

**怎么跑**：`PYTHONPATH=. python extra_figures/make_bler_figure.py`（另一个同理）。

## English

Scripts for the two figures added in this revision. Figures are written into `../paper/figures/`.

- `make_bler_figure.py` — **channel BLER curves**: block-error rate vs SNR for LDPC+16/256-QAM under AWGN
  (solid) and Rayleigh (dashed). Shows the 16-QAM cliff at ~12 dB (the selector knee), the 256-QAM cliff
  far to its right (dominated), and Rayleigh never reliable (hence stay at L). → `fig_channel_bler.pdf`
- `make_qualitative_figure.py` — **qualitative BEV comparison**: on one frame, object-level L (left) vs
  feature-level C (right) detections overlaid on the point cloud + ground truth, built entirely from
  cached `.npy` (no re-inference). → `fig_qualitative_bev.pdf`

**Run**: `PYTHONPATH=. python extra_figures/make_bler_figure.py` (same for the other).
