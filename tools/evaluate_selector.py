#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command 4/6: 200-realisation deployment replay of the frozen selectors.

  python tools/evaluate_selector.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/evaluation'))
import deployment

if __name__ == '__main__':
    deployment.main()
