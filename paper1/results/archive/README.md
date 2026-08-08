# results/archive/ — retired result CSVs (P1)

Files here are **retired**: no paper number should be sourced from them. They are kept for
provenance/rollback only. Each is superseded by a P2 regeneration under the frozen protocol
(`paper1/PROTOCOL.md`). No replacement value is pre-set here — P2 measures it.

| Archived file | Why retired | Replaced by |
|---|---|---|
| `latency_benchmark.csv` | The old **52.8 ms** per-frame selector latency was measured on the retired v2 selector (`runs/v2/rf_full.pkl`). It is **no longer used**; the deployed-selector latency must be re-measured on the P2 frozen model. | P2 re-measurement on the frozen selector (`code/rf_latency_benchmark.py`, repointed) — value not pre-set. |
| `robustness_rician.csv` | Rician-fading / K-factor robustness rows whose **measurement convention is in doubt** (built on the deprecated codeword-level BLER path, `code/extra_experiments/c_channels.py`). | P2 regeneration under the current (bler_sionna, ego-fallback, S={E,L,F}) system — value not pre-set. |
