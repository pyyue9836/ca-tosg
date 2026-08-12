#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-frame selector inference latency on the frozen selectors + the end-to-end timing table.

  python tools/benchmark_latency.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
import latency

if __name__ == '__main__':
    latency.main()
