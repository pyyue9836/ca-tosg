#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sensitivity sweep: channel ratio, non-uniform SNR, channel misclassification,
object-message BLER, Rician proxy, plus the baseline-sanity reproduction.

  python tools/run_sensitivity.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
import sensitivity

if __name__ == '__main__':
    sensitivity.main()
