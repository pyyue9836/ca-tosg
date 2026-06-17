#self+ Peiyi: qualitative BEV figure — object-level (L) vs feature-level (C) detections
"""
Two-panel BEV visualisation on one test frame, built entirely from cached npy
(no inference re-run). Left: object-level late-fusion prediction (L). Right:
compressed feature-level prediction (C). Both overlaid on the same LiDAR BEV
points and ground-truth boxes. Illustrates that when the channel can support it,
feature-level communication recovers objects that the compact object-level
message misses (this frame: late F1 0.67 -> compressed F1 0.95).
Output: paper/figures/fig_qualitative_bev.pdf
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from scipy.spatial import ConvexHull

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
PRE = os.path.join(REPO, 'peiyi_work/05_pretrained_models')
LATE = os.path.join(PRE, 'pointpillar_late_fusion_test_eval', 'npy')
COMP = os.path.join(PRE, 'pointpillar_attentive_fusion',
                    'pointpillar_attentive_fusion_compression_test_eval', 'npy')
OUT = os.path.join(REPO, 'peiyi_work/01_paper_ca_tosg/paper/figures/fig_qualitative_bev.pdf')
FRAME = 1436   # late_f1=0.67, comp_f1=0.95, 9 GT objects, 3 CAVs


def boxes_bev(arr):
    """(N,8,3) corner boxes -> list of (M,2) BEV convex-hull polygons."""
    polys = []
    for b in arr:
        xy = b[:, :2]
        try:
            h = ConvexHull(xy)
            polys.append(xy[h.vertices])
        except Exception:
            polys.append(xy)
    return polys


def draw(ax, pcd, gt, pred, pred_color, pred_label, title):
    if pcd.ndim == 2 and pcd.shape[0] > 10:
        ax.scatter(pcd[:, 0], pcd[:, 1], s=0.15, c='0.7', linewidths=0, zorder=1,
                   rasterized=True)
    for p in boxes_bev(gt):
        ax.add_patch(Polygon(p, closed=True, facecolor='#2ca02c', alpha=0.45,
                             edgecolor='#1a701a', lw=1.2, zorder=2))
    for p in boxes_bev(pred):
        ax.add_patch(Polygon(p, closed=True, fill=False, edgecolor=pred_color,
                             lw=1.6, ls='-', zorder=4))
    # legend proxies
    ax.add_patch(Polygon([[0, 0]], facecolor='#2ca02c', alpha=0.30,
                         edgecolor='#2ca02c', label='Ground truth'))
    ax.plot([], [], color=pred_color, lw=1.6, label=pred_label)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel('x (m)', fontsize=8)
    ax.set_aspect('equal')
    ax.legend(fontsize=7, loc='upper right', framealpha=0.9)


def main():
    gt = np.load(os.path.join(COMP, f'{FRAME:04d}_gt.npy_test.npy'))
    late_pred = np.load(os.path.join(LATE, f'{FRAME:04d}_pred.npy'))
    comp_pred = np.load(os.path.join(COMP, f'{FRAME:04d}_pred.npy'))
    pcd = np.load(os.path.join(COMP, f'{FRAME:04d}_pcd.npy'))

    # crop to the union of GT + both predictions (+margin) so that the
    # object-level branch's false positives are NOT cropped away
    allxy = np.concatenate([gt.reshape(-1, 3)[:, :2],
                            late_pred.reshape(-1, 3)[:, :2],
                            comp_pred.reshape(-1, 3)[:, :2]], axis=0)
    xmin, ymin = allxy.min(0) - 6
    xmax, ymax = allxy.max(0) + 6

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.2), sharey=True)
    draw(axes[0], pcd, gt, late_pred, '#1f77b4',
         'Object-level $L$', r'Object-level $L$ (F1 = 0.67)')
    draw(axes[1], pcd, gt, comp_pred, '#d62728',
         'Feature-level $C_{16}$', r'Feature-level $C_{16}$ (F1 = 0.95)')
    for ax in axes:
        ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax)
    axes[0].set_ylabel('y (m)', fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT, bbox_inches='tight', dpi=200)
    # also a PNG preview for quick visual inspection
    fig.savefig(OUT.replace('.pdf', '_preview.png'), bbox_inches='tight', dpi=140)
    print('wrote', OUT, '| GT', len(gt), 'late', len(late_pred), 'comp', len(comp_pred))


if __name__ == '__main__':
    main()
