#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command 5/6: true end-to-end AP under the frozen selectors (global-sort scorer).

  python tools/evaluate_ap.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
import end_to_end_ap

if __name__ == '__main__':
    end_to_end_ap.main()
