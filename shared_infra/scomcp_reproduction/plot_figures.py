# -*- coding: utf-8 -*-
"""
Plot SComCP Fig. 6 (AWGN) and Fig. 7 (Rayleigh) from the sweep CSVs in results/.
Each CSV has columns: scheme, channel, snr_db, ap50, ap70.
"""
import csv
import glob
import os
from collections import defaultdict

import matplotlib.pyplot as plt

R = os.path.join(os.path.dirname(__file__), 'results')


def load():
    data = defaultdict(lambda: defaultdict(list))  # channel -> scheme -> [(snr,ap50,ap70)]
    for path in glob.glob(os.path.join(R, '*.csv')):
        with open(path) as f:
            for row in csv.DictReader(f):
                data[row['channel'] if row['channel'] in ('awgn', 'rayleigh')
                     else _norm(row['channel'])][row['scheme']].append(
                    (float(row['snr_db']), float(row['ap50']), float(row['ap70'])))
    return data


def _norm(ch):
    # perfect_comm / ldpc overlays are filed by the sweep's --channel; we group
    # them by the physical channel they were swept against via filename.
    return ch


def plot_channel(data_for_ch, channel_name, fname):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for scheme, pts in sorted(data_for_ch.items()):
        pts = sorted(pts)
        snr = [p[0] for p in pts]
        axes[0].plot(snr, [p[1] for p in pts], marker='o', label=scheme)
        axes[1].plot(snr, [p[2] for p in pts], marker='o', label=scheme)
    for ax, title in zip(axes, ['AP@0.5', 'AP@0.7']):
        ax.set_xlabel('SNR (dB)'); ax.set_ylabel(title)
        ax.set_title('%s over %s channel' % (title, channel_name))
        ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    out = os.path.join(R, fname)
    fig.savefig(out, dpi=150)
    print('wrote %s' % out)


def main():
    # Group csvs by the physical channel encoded in the filename suffix.
    by_channel = {'awgn': defaultdict(list), 'rayleigh': defaultdict(list)}
    for path in glob.glob(os.path.join(R, '*.csv')):
        base = os.path.basename(path)
        phys = 'awgn' if base.endswith('_awgn.csv') else \
               'rayleigh' if base.endswith('_rayleigh.csv') else None
        if phys is None:
            continue
        with open(path) as f:
            for row in csv.DictReader(f):
                by_channel[phys][row['scheme']].append(
                    (float(row['snr_db']), float(row['ap50']), float(row['ap70'])))
    plot_channel(by_channel['awgn'], 'AWGN', 'fig6_awgn.png')
    plot_channel(by_channel['rayleigh'], 'Rayleigh', 'fig7_rayleigh.png')


if __name__ == '__main__':
    main()
