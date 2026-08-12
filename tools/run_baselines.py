#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Baselines. Each baseline owns a README in baselines/<name>/ stating source paper,
modifications, checkpoint, data split, run command and output.

  python tools/run_baselines.py contextual_bandit --train
  python tools/run_baselines.py contextual_bandit --evaluate
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


import argparse

BASELINES = {
    'contextual_bandit': ('baselines/contextual_bandit', 'train', 'evaluate'),
}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('baseline', choices=sorted(BASELINES))
    ap.add_argument('--train', action='store_true')
    ap.add_argument('--evaluate', action='store_true')
    a, rest = ap.parse_known_args()
    sys.argv = [sys.argv[0]] + rest
    d, train_mod, eval_mod = BASELINES[a.baseline]
    sys.path.insert(0, os.path.join(ROOT, d))
    if a.train:
        __import__(train_mod).main()
    if a.evaluate:
        __import__(eval_mod).main()
    if not (a.train or a.evaluate):
        ap.error('pick --train and/or --evaluate')
