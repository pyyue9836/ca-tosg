#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 data prep (item 9): expand the clean per-frame F1 cache into the deterministic channel grid.

DATA ONLY -- no GPU, no training, no model. Pure table-lookup BLER + arithmetic.

Per split (validate/test/culver):
  1. Read the clean per-frame F1 cache dataset_{split}_v3.csv and ASSERT the three clean-utility
     columns are all present and finite (late_f1 = L, compressed_f1 = F clean, ego_f1 = E). This is
     the "assert the caches are complete" precondition -- every action's clean per-frame F1 exists.
  2. Reconstruct frame -> scene (_scene_map, fail-closed on the frame-count assertion).
  3. Expand each frame across the DETERMINISTIC grid  SNR {0,2,..,20} dB x channel {AWGN,Rayleigh}
     (11 x 2 = 22 cells/frame). For each cell compute, under S = {E, L, F}:
        BLER_F  = frame-level BLER of the 16-QAM rate-1/2 feature message (Sionna table lookup)
        eff_E   = ego_f1                                  (B_E = 0, always delivered)
        eff_L   = late_f1                                 (BLER_L = 0 mainline: object msg reliable)
        eff_F   = compressed_f1*(1-BLER_F) + ego_f1*BLER_F   (ego-only failure fallback)
        oracle  = argmax over the FEASIBILITY-MASKED [E, L, F] (PROTOCOL sec 4): where BLER_F>=0.999
                  F's oracle target is set to -inf, so an undeliverable F is never labelled; the
                  eff_F column keeps the true utility. Ties -> the earlier/cheaper action (E, then L).
  4. Write data/p2/p2_grid_{split}.csv (git-excluded) + results/p2_dataprep/PROVENANCE_grid[_split].txt.

--split (PROTOCOL sec 10): default 'validate' (the only split allowed PRE-FREEZE). test / culver may
be built ONLY after FROZEN_MANIFEST.json exists; this script refuses otherwise (structural §10 guard).

This is the P2 TRAINING SUBSTRATE, not the deployment eval: it is a dense deterministic product,
distinct from the frozen single random draw in dataset_*_v3.csv and from the 200-realisation MC.
The oracle here is over {E,L,F} and DIFFERS from the legacy oracle_3way over {L,C16,C256}.

Run:  /path/to/env/python paper1/code/p2_dataprep/expand_grid_clean.py
"""
import argparse
import hashlib
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _scene_map import scene_labels  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(os.path.dirname(HERE))                       # paper1
OPENCOOD = os.path.join(os.path.dirname(os.path.dirname(P1)), 'OpenCOOD')
DATA = os.path.join(OPENCOOD, 'peiyi_work/paper1/data')           # clean per-frame caches (v3)
BLER_CSV = os.path.join(P1, 'results/bler_sionna/bler_sionna.csv')  # frame-level, Es/N0
OUT_DATA = os.path.join(P1, 'data/p2')                            # git-excluded artifacts
OUT_PROV = os.path.join(P1, 'results/p2_dataprep')               # tracked provenance
MANIFEST = os.path.join(OUT_PROV, 'FROZEN_MANIFEST.json')         # P2 freeze marker (PROTOCOL sec 10)

# versionless pipeline naming (P2 submit-A migration); test/culver stay _v3 until P2 submit-B rebuild
DATASET_NAME = {'validate': 'dataset_validate.csv',
                'test': 'dataset_test_v3.csv', 'culver': 'dataset_culver_v3.csv'}
SNR_GRID = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
CHANNELS = ['awgn', 'rayleigh']
QAM_F = 16                                                        # F = feature-level, 16-QAM rate-1/2
BLER_INFEASIBLE = 0.999                                           # F undeliverable -> masked from the LABEL (PROTOCOL sec 4)
PAYLOAD_MSYM = {'E': 0.0, 'L': 0.024, 'F': 0.99}                 # report-only (see PROTOCOL.md / payload_audit.py)
ACTIONS = ['E', 'L', 'F']
CLEAN_COLS = {'E': 'ego_f1', 'L': 'late_f1', 'F': 'compressed_f1'}


def bler_frame(snr_arr, tbl, qam, channel):
    """Frame-level BLER at Es/N0=snr for a QAM order over a channel; mirrors make_dataset.py exactly
    (interp on bler_frame vs esno_db; below-table -> 1, above -> last)."""
    s = tbl[(tbl['qam'] == qam) & (tbl['channel'] == channel)].sort_values('esno_db')
    xs = s['esno_db'].to_numpy(); ys = s['bler_frame'].to_numpy()
    return np.clip(np.interp(snr_arr, xs, ys, left=1.0, right=float(ys[-1])), 0.0, 1.0)


def expand_split(split, tbl):
    path = os.path.join(DATA, DATASET_NAME[split])
    if not os.path.exists(path):
        raise SystemExit(f'{split}: clean cache absent -> {path}')
    df = pd.read_csv(path)
    n = len(df)
    # (1) assert the clean per-frame F1 caches are complete for every action
    for a, col in CLEAN_COLS.items():
        if col not in df.columns:
            raise SystemExit(f'{split}: missing clean-utility column {col} (action {a})')
        if not np.isfinite(df[col].to_numpy()).all():
            raise SystemExit(f'{split}: non-finite values in {col} -- cache incomplete')
    # (2) frame -> scene (fail-closed)
    labels, counts = scene_labels(OPENCOOD, split, n)
    df = df.copy(); df['scene'] = labels

    ego = df['ego_f1'].to_numpy(); late = df['late_f1'].to_numpy()
    comp = df['compressed_f1'].to_numpy()
    sample_id = (df['sample_id'].to_numpy() if 'sample_id' in df.columns else np.arange(n))
    scene = df['scene'].to_numpy()

    # (3) deterministic expansion
    blocks = []
    for ch in CHANNELS:
        for snr in SNR_GRID:
            bF = bler_frame(np.full(n, float(snr)), tbl, QAM_F, ch)
            eff_E = ego
            eff_L = late                                         # BLER_L = 0 mainline
            eff_F = comp * (1.0 - bF) + ego * bF
            util = np.stack([eff_E, eff_L, eff_F], axis=1)       # true effective utility, order [E, L, F]
            masked = util.copy()                                 # PROTOCOL sec 4 feasibility mask (LABEL only):
            masked[bF >= BLER_INFEASIBLE, 2] = -np.inf           #   BLER_F>=0.999 -> F cannot be the oracle target
            oracle = np.array(ACTIONS)[masked.argmax(1)]         # ties -> E, then L
            blocks.append(pd.DataFrame(dict(
                sample_id=sample_id, scene=scene, snr_db=snr, channel=ch,
                bler_F=np.round(bF, 6),
                eff_E=np.round(eff_E, 6), eff_L=np.round(eff_L, 6), eff_F=np.round(eff_F, 6),
                oracle_ELF=oracle)))
    grid = pd.concat(blocks, ignore_index=True)
    assert len(grid) == n * len(SNR_GRID) * len(CHANNELS), 'grid row count mismatch'

    os.makedirs(OUT_DATA, exist_ok=True)
    out = os.path.join(OUT_DATA, f'p2_grid_{split}.csv')
    grid.to_csv(out, index=False)
    md5 = hashlib.md5(open(out, 'rb').read()).hexdigest()
    base = {a: float((grid['oracle_ELF'] == a).mean()) for a in ACTIONS}
    return dict(split=split, n_frames=n, n_scenes=len(counts), rows=len(grid),
                out=out, md5=md5, base_rate=base, counts=counts,
                src_md5=hashlib.md5(open(path, 'rb').read()).hexdigest())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='validate', choices=['validate', 'test', 'culver'],
                    help="split to build (default validate -- the ONLY split allowed pre-freeze)")
    split = ap.parse_args().split

    # PROTOCOL sec 10: test / culver may be built ONLY after the freeze manifest exists.
    if split != 'validate' and not os.path.exists(MANIFEST):
        raise SystemExit(
            f"expand_grid_clean: --split {split} is POST-FREEZE only (PROTOCOL sec 10). "
            f"{os.path.relpath(MANIFEST, P1)} not found -- build the validate grid, freeze the "
            f"model, THEN regenerate test/Culver by a separate post-manifest command.")

    tbl = pd.read_csv(BLER_CSV)
    os.makedirs(OUT_PROV, exist_ok=True)
    r = expand_split(split, tbl)
    print(f"[{r['split']}] frames={r['n_frames']} scenes={r['n_scenes']} rows={r['rows']} "
          f"oracle base-rate(E/L/F)={r['base_rate']}  md5={r['md5']}")

    prov = os.path.join(OUT_PROV, 'PROVENANCE_grid.txt' if split == 'validate'
                        else f'PROVENANCE_grid_{split}.txt')
    with open(prov, 'w') as f:
        f.write(f"CA-TOSG P2 data prep -- clean-cache grid expansion (expand_grid_clean.py --split {split})\n")
        f.write("=" * 72 + "\n")
        f.write(f"SNR grid: {SNR_GRID} dB (Es/N0)  x  channels: {CHANNELS}\n")
        f.write(f"Action set S = {ACTIONS}; F = {QAM_F}-QAM rate-1/2 LDPC.\n")
        f.write("eff_E=ego_f1 (B_E=0); eff_L=late_f1 (BLER_L=0 mainline); "
                "eff_F=compressed_f1*(1-BLER_F)+ego_f1*BLER_F (ego fallback).\n")
        f.write(f"oracle_ELF = argmax over FEASIBILITY-MASKED [E,L,F] (BLER_F>={BLER_INFEASIBLE} -> F=-inf, "
                "LABEL only; eff_F column keeps true utility). Ties -> E then L. NOT legacy oracle_3way.\n")
        f.write(f"BLER source: {os.path.relpath(BLER_CSV, P1)} (frame-level bler_frame, "
                f"md5 {hashlib.md5(open(BLER_CSV, 'rb').read()).hexdigest()}).\n")
        f.write(f"Payload (Msym, report-only): {PAYLOAD_MSYM}.\n")
        f.write("Grid artifacts are git-excluded (data/p2/); regenerate with expand_grid_clean.py.\n")
        if split != 'validate':
            f.write("POST-FREEZE artifact: built after FROZEN_MANIFEST.json (PROTOCOL sec 10).\n")
        f.write("\n")
        f.write(f"[{r['split']}] src={DATASET_NAME[r['split']]} md5={r['src_md5']}\n")
        f.write(f"    frames={r['n_frames']} scenes={r['n_scenes']} rows={r['rows']}\n")
        f.write(f"    out={os.path.relpath(r['out'], P1)} md5={r['md5']}\n")
        f.write(f"    oracle base-rate E/L/F = {r['base_rate']}\n")
        f.write(f"    scene frame-counts = {r['counts']}\n")
    print('wrote', prov)


if __name__ == '__main__':
    main()
