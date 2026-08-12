#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Command 2/6: build the Sionna 5G-LDPC + QAM block-error-rate tables.

  python tools/build_bler_table.py                 # AWGN / Rayleigh -> results/channel/bler_sionna.csv
  python tools/build_bler_table.py --ofdm          # OFDM            -> results/channel/bler_sionna_ofdm.csv
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


sys.path.insert(0, os.path.join(ROOT, 'projects/ca_tosg/communication'))

if __name__ == '__main__':
    if '--ofdm' in sys.argv:
        sys.argv.remove('--ofdm')
        import channel
        channel.main()
    else:
        import ldpc_qam
        ldpc_qam.main()
