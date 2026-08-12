# projects/ca_tosg — the method

Library code. Nothing here is an entry point: `tools/` runs it, `configs/` parameterises it,
`docs/experiment_protocol.md` governs it.

```
models/           selector.py         RF construction, LOSO, frozen walk, freeze
                  oracle.py           E/L/F action set, payload vector, Lagrangian label rule
                  feature_encoder.py  the 23-column input: 21 ego cues + est SNR + channel flag
                  train_rf_v3.py      the superseded P1-v3 trainer (kept: it generated the P1 rows)

datasets/         opv2v.py            per-frame oracle labels on the canonical v3 datasets
                  grid_builder.py     frame x 11 SNR x 2 channels, built AFTER the scene split
                  scene_split.py      frame->scene, two independent traversals the gate cross-checks
                  test_split/         the pipeline that produces the test-split cue CSV
                  run_ego_only.py, regen_preds_with_scores.py   DATA_MANIFEST-registered caches

communication/    ldpc_qam.py         Sionna 5G-LDPC(500,1000) rate-1/2 + 16/256-QAM BLER
                  channel.py          OFDM / Rayleigh / Rician variants
                  payload.py          the per-frame channel-use chain (1.98 Mbit -> 0.99 Msym)
                  fallback.py         ego-only failure fallback

evaluation/       deployment.py       200-realisation replay of the frozen selectors
                  end_to_end_ap.py    true end-to-end AP, global-sort scorer
                  sensitivity.py      the pre-registered sensitivity items
                  metrics.py          shared F1 / AP helpers
                  figures/            one generator per figure main.tex includes
                  ablations/          a1-a9, c_channels, robustness
                  verifiers/          one-shot claim verifiers

utils/            manifest.py         manifest load + sha256 verification
                  configs.py          THE generator of configs/ from the protocol
                  results_index.py    THE generator of results/README.md
                  provenance.py, seed.py, paper_style.py
```

## Two rules this layout enforces

1. **One normative source.** `docs/experiment_protocol.md` defines intent. `configs/*.yaml` are
   generated from it and byte-compared by `tests/test_manifest.py`. If a generator disagrees with
   the protocol, that is a code bug — fix the code, never the protocol.
2. **Frozen means frozen.** Every evaluation loads its selector through the manifest and verifies
   the sha256 first. A re-freeze re-audits its winners against the existing manifest and refuses
   to overwrite on a mismatch.
