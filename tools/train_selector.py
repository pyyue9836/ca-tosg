#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command 3/6: fit and freeze the CA-TOSG selector.

Reads the candidate block from docs/experiment_protocol.md (the single normative source),
runs the scene-level 9-fold LOSO, walks the pre-registered candidate order per budget, and
freezes one model per budget with results/manifests/FROZEN_MANIFEST.json.

  python tools/train_selector.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


from projects.ca_tosg.models import selector

if __name__ == '__main__':
    selector.main()
