#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command 1/6: build the channel grid and the independent scene manifest.

  python tools/prepare_data.py --split validate          # grid  -> data/p2/p2_grid_validate.csv
  python tools/prepare_data.py --scene-manifest          # manifest -> results/manifests/
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/datasets'))

if __name__ == '__main__':
    if '--scene-manifest' in sys.argv:
        sys.argv.remove('--scene-manifest')
        import scene_split
        scene_split.main()
    else:
        import grid_builder
        grid_builder.main()
