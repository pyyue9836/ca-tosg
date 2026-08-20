#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R53: record each branch checkpoint's CONFIGURED perception range as a committed product.

The paper now states both ranges (x +-70.4 for the late-fusion branch, x +-140.8 for the
compression branch). Those numbers lived only in checkpoint configs outside this repository, so
`p6_numbers_vs_csv` reported the 70.4 as unbound -- correctly: a number in the paper that no
committed product carries is exactly what that check exists to find.

    python baselines/where2comm_v2/branch_ranges.py
"""
import csv, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = {
    'late_fusion_L_branch': '/mnt/h/opencood_project/pretrained_models/pointpillar_late_fusion/config.yaml',
    'attentive_compression_F_branch':
        '/mnt/h/opencood_project/pretrained_models/pointpillar_attentive_fusion/pointpillar_attentive_fusion_compression/config.yaml',
    'where2comm_reproduction':
        '/mnt/h/wsl_backup/OpenCOOD_20260601_1326/opencood/logs/point_pillar_where2comm_2026_05_22_17_56_51/config.yaml',
}
OUT = os.path.join(ROOT, 'results/diagnostics/branch_ranges.csv')


def lidar_range(path):
    """The first `lidar_range:` block, read as six floats."""
    txt = open(path, encoding='utf-8').read()
    m = re.search(r'lidar_range:[^\n]*\n((?:\s*-\s*-?[\d.]+\n){6})', txt)
    if not m:
        return None
    return [float(x) for x in re.findall(r'-?[\d.]+', m.group(1))]


def main():
    rows = []
    for name, p in SRC.items():
        if not os.path.exists(p):
            print(f'SKIP {name}: {p} not present on this machine')
            continue
        r = lidar_range(p)
        if r is None:
            print(f'SKIP {name}: no lidar_range block in {p}')
            continue
        rows.append(dict(branch=name, config=p, x_min=r[0], y_min=r[1], z_min=r[2],
                         x_max=r[3], y_max=r[4], z_max=r[5],
                         x_half_extent=abs(r[3]), y_half_extent=abs(r[4])))
    if not rows:
        print('FAIL: no config was readable; the product would be empty')
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['branch']:32s} x +-{r['x_half_extent']:g}  y +-{r['y_half_extent']:g}")
    print(f'wrote {os.path.relpath(OUT, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
