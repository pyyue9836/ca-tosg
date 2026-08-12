#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Feature encoder: the 23-column selector input.

21 ego-side cues joined from the per-frame cue CSV (validated many_to_one on a unique sample_id),
plus est_snr_db and channel_is_rayleigh taken from the channel grid. EXCLUDE names every column
that must NOT reach the model -- outcome columns, oracle labels, and the two channel columns that
are re-added explicitly -- so a leaked label cannot slip in under a rename.

Relocated verbatim from code/p2_dataprep/train_p2_loso.py by the restructure (commit 2/4).
"""
import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
OPENCOOD = os.path.join(os.path.dirname(ROOT), 'OpenCOOD')
CUES_CSV = os.path.join(OPENCOOD, 'peiyi_work/paper1/data', 'dataset_validate.csv')
GRID_CSV = os.path.join(ROOT, 'data/p2/p2_grid_validate.csv')

EXCLUDE = {
    'sample_id', 'cav_keys', 'channel_type',
    *[f'{m}_{s}' for m in ('late', 'early', 'intermediate', 'compressed')
      for s in ('num_pred', 'num_gt', 'tp', 'fp', 'fn', 'precision', 'recall', 'f1', 'payload_Mbit')],
    *[f'{m}_f1_gain_over_late' for m in ('late', 'early', 'intermediate', 'compressed')],
    *[f'{m}_gain_per_extra_Mbit' for m in ('late', 'early', 'intermediate', 'compressed')],
    'best_method_by_f1', 'best_level_by_f1', 'best_f1', 'best_payload_Mbit',
    'bler_C16', 'bler_C256', 'eff_f1_L', 'eff_f1_C16', 'eff_f1_C256', 'oracle_3way', 'ego_f1',
    'est_snr_db', 'channel_is_rayleigh',
}


def load():
    grid = pd.read_csv(GRID_CSV)
    cues = pd.read_csv(CUES_CSV)
    if cues['sample_id'].duplicated().any():                    # merge guard: cue source must be per-frame
        raise SystemExit('dataset_validate.csv has duplicate sample_id -- cue source not one-per-frame.')
    feat_cols = [c for c in cues.columns if c not in EXCLUDE]
    merged = grid.merge(cues[['sample_id'] + feat_cols], on='sample_id', how='left',
                        validate='many_to_one')
    assert not merged[feat_cols].isna().any().any(), 'cue join produced NaNs'
    X = merged[feat_cols].copy()
    X['est_snr_db'] = merged['snr_db'].to_numpy()
    X['channel_is_rayleigh'] = (merged['channel'] == 'rayleigh').astype(int).to_numpy()
    names = feat_cols + ['est_snr_db', 'channel_is_rayleigh']
    return (merged, X[names].to_numpy(), names, merged[['eff_E', 'eff_L', 'eff_F']].to_numpy(),
            merged['bler_F'].to_numpy(), merged['scene'].to_numpy())
