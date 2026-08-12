#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E / L / F action set, payload vector, and the Lagrangian labelling rule (experiment_protocol sec 6).

    label(frame) = argmax_a [ eff(frame, a) - lambda * payload(a) ]

with F masked out when the feature message cannot be delivered (frame BLER >= BLER_INFEASIBLE).

Relocated verbatim from code/p2_dataprep/train_p2_loso.py by the restructure (commit 2/4).
"""
import numpy as np

ACTIONS = ['E', 'L', 'F']
PAYLOAD = {'E': 0.0, 'L': 0.024, 'F': 0.99}
PAYVEC = np.array([PAYLOAD[a] for a in ACTIONS])
BLER_INFEASIBLE = 0.999


def lam_labels(eff, bler_F, lam):
    util = eff - lam * PAYVEC[None, :]
    util[bler_F >= BLER_INFEASIBLE, 2] = -np.inf
    return util.argmax(1)
