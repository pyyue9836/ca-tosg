"""
Fig. 1 framework schematic (matplotlib, python-only, no graphviz dependency).

Draws the importance-map JSCC cooperative-perception pipeline:
    F = Phi(X)   ->  C = P(F)  ->  M = F (x) C  ->  T = Psi_s(M)  ->  channel
    ->  R = Psi_d(T')  ->  D = chi(R, F'_ego)  ->  Yhat = Gamma(D)
matching Sheng et al., WCSP 2023, Fig. 1.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


def box(ax, xy, w, h, text, fc):
    x, y = xy
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                linewidth=1.3, edgecolor="#333", facecolor=fc))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)


def arrow(ax, p0, p1):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=12,
                                 linewidth=1.2, color="#333"))


def main():
    out_dir = Path("experiment_logs/importance_map_jscc/paper_range_figures")
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")

    tx = "#dbe9ff"; eg = "#e9ffe6"; ch = "#ffe9d6"

    # CAV (transmitter) row.
    box(ax, (0.2, 4.2), 1.5, 1.0, "CAV LiDAR\n$X_i$", "#f0f0f0")
    box(ax, (2.0, 4.2), 1.6, 1.0, "Backbone\n$F_i=\\Phi(X_i)$", tx)
    box(ax, (3.9, 5.0), 1.7, 0.8, "Importance map\n$C_i=P(F_i)$", tx)
    box(ax, (3.9, 3.9), 1.7, 0.8, "Mask\n$M_i=F_i\\odot C_i$", tx)
    box(ax, (5.9, 4.2), 1.7, 1.0, "Semantic enc.\n$T_i=\\Psi_s(M_i)$", tx)
    box(ax, (7.9, 4.2), 1.7, 1.0, "Channel\nAWGN/Rayleigh/OFDM", ch)
    box(ax, (9.9, 4.2), 1.8, 1.0, "Semantic dec.\n$R_i=\\Psi_d(T'_i)$", tx)

    arrow(ax, (1.7, 4.7), (2.0, 4.7))
    arrow(ax, (3.6, 4.7), (3.9, 5.4))
    arrow(ax, (3.6, 4.7), (3.9, 4.3))
    arrow(ax, (5.6, 5.4), (5.9, 4.9))   # C into mask path
    arrow(ax, (5.6, 4.3), (5.9, 4.5))
    arrow(ax, (7.6, 4.7), (7.9, 4.7))
    arrow(ax, (9.6, 4.7), (9.9, 4.7))

    # Ego (receiver) row.
    box(ax, (0.2, 0.6), 1.5, 1.0, "Ego LiDAR\n$X'_i$", "#f0f0f0")
    box(ax, (2.0, 0.6), 1.6, 1.0, "Backbone\n$F'_i=\\Phi(X'_i)$", eg)
    box(ax, (6.0, 0.6), 2.2, 1.0, "Attention fusion\n$D_i=\\chi(R_i,F'_i)$", eg)
    box(ax, (8.8, 0.6), 2.0, 1.0, "Detection\n$\\hat{Y}_i=\\Gamma(D_i)$", eg)

    arrow(ax, (1.7, 1.1), (2.0, 1.1))
    arrow(ax, (3.6, 1.1), (6.0, 1.1))
    arrow(ax, (8.2, 1.1), (8.8, 1.1))
    # Received remote feature down into fusion.
    arrow(ax, (10.8, 4.2), (7.1, 1.6))

    ax.text(6.0, 5.9, "Importance-Map JSCC Cooperative Perception (Sheng et al., WCSP 2023)",
            ha="center", va="center", fontsize=11, fontweight="bold")

    for ext in ("png", "pdf"):
        fig.savefig(out_dir / f"fig1_framework.{ext}", bbox_inches="tight", dpi=180)
    print("[DONE] Fig.1 framework ->", out_dir / "fig1_framework.png")


if __name__ == "__main__":
    main()
