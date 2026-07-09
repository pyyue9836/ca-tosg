# SComCP Reproduction

Faithful reproduction of **Gan et al., "SComCP: Task-Oriented Semantic
Communication for Collaborative Perception", IEEE TVT 2026** on OPV2V, built on
top of this repo's existing importance-map-JSCC pipeline.

## Why this is ~70% done already

Your existing `ImportanceMapJSCC` (`opencood/models/fuse_modules/importance_map_jscc_fuse.py`)
**is essentially the paper's "Baseline [35]"** (importance map + CNN JSCC codec).
The full surrounding pipeline already matches the paper:

| Paper needs | Already in repo |
|---|---|
| PointPillars backbone, attention fusion, detection head | ✅ |
| Complex AWGN / Rayleigh channels, power norm (eq. 6, 20) | ✅ |
| Importance masking + variable CR | ✅ |
| AP@0.5 / AP@0.7 (VOC) eval | ✅ `eval_utils.calculate_ap` |
| OPV2V, SNR sweep, LDPC-QAM & upper-bound overlays | ✅ |

SComCP adds exactly **three deltas**, which is all this folder implements:

1. **Cross-attention + spatial-attention feature selector** (eq. 11-15) →
   `CrossAttentionSelector` in `opencood/models/fuse_modules/scomcp_fuse.py`
2. **Transformer + Channel-Attention JSCC codec** (eq. 16-20) →
   `TransformerCACodec` (operates on the K selected tokens, as in the paper)
3. **Three-stage training** (paper Algorithm 1) → `train_scomcp.py` + 3 configs

`SComCPFuse` subclasses `ImportanceMapJSCC` and swaps only those two modules;
`point_pillar_importance_map_jscc.py` dispatches to it on `variant: scomcp`.

## Data — aligned to the paper

- Dataset: **OPV2V**, default split (6764 train / 1981 val / 2170 test).
- Eval metrics: **AP@0.5 and AP@0.7**.
- Channels: **train on Rayleigh only**, test on **AWGN (Fig. 6)** and
  **Rayleigh (Fig. 7)**; SNR swept **0–20 dB**.
- Schemes in the figures: Upper Bound, Proposed SComCP, Baseline [35],
  LDPC-16QAM, LDPC-256QAM.

⚠️ **One data caveat to decide.** The paper uses range `x∈[-140,140], y∈[-40,40]`.
The configs here use this repo's existing grid `x∈[-140.8,140.8], y∈[-38.4,38.4]`
so you can **reuse your already-trained PointPillars backbone**. The y extent
differs by ±1.6 m (negligible for AP, but not bit-identical to the paper). To be
100% faithful, retrain a PointPillars backbone at `[-140,-40,-3,140,40,1]`
(700×200 grid) and update `cav_lidar_range` in all four configs — but that adds a
backbone-training stage. Recommendation: start with the existing grid; switch
only if a reviewer demands exact range parity.

## Run

```bash
# 1. Point BASE_CKPT in run_scomcp.sh at a pretrained PointPillars checkpoint
#    (backbone + detection head; frozen in stages 1-2).
# 2. Three-stage train + sweep + plot:
bash peiyi_work/02_scomcp_reproduction/run_scomcp.sh
```

Or stage-by-stage:

```bash
python peiyi_work/02_scomcp_reproduction/train_scomcp.py --hypes_yaml peiyi_work/02_scomcp_reproduction/configs/scomcp_stage1_selector.yaml --warm_start <BASE_CKPT>
python peiyi_work/02_scomcp_reproduction/train_scomcp.py --hypes_yaml peiyi_work/02_scomcp_reproduction/configs/scomcp_stage2_codec.yaml   --warm_start <stage1_last.pth>
python peiyi_work/02_scomcp_reproduction/train_scomcp.py --hypes_yaml peiyi_work/02_scomcp_reproduction/configs/scomcp_stage3_joint.yaml   --warm_start <stage2_last.pth>
```

Figures land in `peiyi_work/02_scomcp_reproduction/results/` (`fig6_awgn.png`, `fig7_rayleigh.png`).

## Three-stage training (paper Algorithm 1)

| Stage | Trains | Frozen | Channel | Loss |
|---|---|---|---|---|
| 1 | selector | backbone, heads | lossless (`perfect_comm`) | Lcls + Lreg |
| 2 | codec | backbone, heads, selector | Rayleigh | + 0.05·MSE (eq. 22) |
| 3 | everything | — | Rayleigh | Lcls + Lreg |

`freeze:` in each config drives the freezing; `scomcp_train.rec_loss_weight` is γ.

## Implementation deviations (auditable)

- **Cross-attention** (eq. 12) on the dense BEV would be O((HW)²); we use a
  context-pooled cross-attention (queries = importance pixels, keys/values = an
  adaptive-pool summary of M_j). Flagged in `scomcp_fuse.py`.
- **Codec on K tokens**: faithful to the paper's `F_j ∈ R^{K×C}` — the codec
  gathers only kept tokens, so the Transformer is cheap.

## Honest status & effort

These files are a **structurally complete, runnable scaffold**, not a validated
result. Before trusting numbers you must:

1. **Smoke-test the forward pass** on a tiny batch (1 stage-1 step) — catches
   shape/device bugs in the new modules.
2. **Tune** depth/heads/`c_complex`/lr per stage to track the paper trends
   (absolute AP≈0.88 will not match exactly without the authors' checkpoints).
3. Add the **Baseline [35]** curve by sweeping your non-`scomcp` model.

Realistic effort from here: ~1 week to working SNR-AP curves; 2–4 weeks to
trend/relative-gain parity with the paper.
