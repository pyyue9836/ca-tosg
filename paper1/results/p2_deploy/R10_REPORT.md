# R10-family diagnostic report (auto-generated from the CSVs; do not hand-edit)

_Every number below is recomputed by `code/p2_dataprep/make_r10_report.py` from `r10c_missed_e_cost.csv` / `r10c_vs_oracle_account.csv`. Post-unblinding; nothing confirmatory. This is the **vs-frozen-λ-clairvoyant-oracle** account and is SEPARATE from the R9 vs-τ decision._


## Missed-E cost per class and TOTAL (per frame-realisation)

_"strict-benefit missed-E cost" and "total E-collapse F1 cost" are **two different numbers**; do not conflate. cost-induced is **non-empty** where λ>0 and its F1 cost is included in the TOTAL._


### test


**B_max = 0.1** (λ\* = 0.05)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 23833 | 23833 | 0.002658 | 0.001694 |
| tie | 33430 | 32446 | 0.000112 | 0.002778 |
| cost-induced | 4809 | 4788 | 0.000252 | 0.000843 |
| TOTAL(all-classes) | 62072 | 61067 | 0.003021 | 0.005316 |

**B_max = 0.2** (λ\* = 0.02)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 23833 | 23833 | 0.002658 | 0.001576 |
| tie | 33430 | 33217 | 0.000123 | 0.003662 |
| cost-induced | 2121 | 2121 | 0.000107 | 0.000611 |
| TOTAL(all-classes) | 59384 | 59171 | 0.002888 | 0.005850 |

**B_max = 0.3** (λ\* = 0.0)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 23833 | 23833 | 0.002705 | 0.003299 |
| tie | 33114 | 32766 | 0.000325 | 0.007733 |
| cost-induced | 0 | 0 | 0.000000 | 0.000000 |
| TOTAL(all-classes) | 56947 | 56599 | 0.003030 | 0.011032 |

### culver


**B_max = 0.1** (λ\* = 0.05)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 135 | 135 | 0.000026 | 0.000029 |
| tie | 9699 | 9699 | 0.000000 | 0.002116 |
| cost-induced | 1035 | 1035 | 0.000013 | 0.000226 |
| TOTAL(all-classes) | 10869 | 10869 | 0.000039 | 0.002371 |

**B_max = 0.2** (λ\* = 0.02)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 135 | 135 | 0.000026 | 0.000029 |
| tie | 9699 | 9699 | 0.000000 | 0.002116 |
| cost-induced | 276 | 276 | 0.000001 | 0.000060 |
| TOTAL(all-classes) | 10110 | 10110 | 0.000027 | 0.002206 |

**B_max = 0.3** (λ\* = 0.0)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 135 | 135 | 0.000026 | 0.000029 |
| tie | 9699 | 9699 | 0.000000 | 0.002116 |
| cost-induced | 0 | 0 | 0.000000 | 0.000000 |
| TOTAL(all-classes) | 9834 | 9834 | 0.000026 | 0.002146 |

### validate


**B_max = 0.1** (λ\* = 0.05)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 2605 | 0 | 0.000000 | 0.000000 |
| tie | 397 | 0 | 0.000000 | 0.000000 |
| cost-induced | 648 | 7 | -0.000001 | 0.000018 |
| TOTAL(all-classes) | 3650 | 7 | -0.000001 | 0.000018 |

**B_max = 0.2** (λ\* = 0.02)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 2605 | 0 | 0.000000 | 0.000000 |
| tie | 397 | 0 | 0.000000 | 0.000000 |
| cost-induced | 513 | 57 | -0.000002 | 0.000143 |
| TOTAL(all-classes) | 3515 | 57 | -0.000002 | 0.000143 |

**B_max = 0.3** (λ\* = 0.0)

| class | clairvoyant-E cells | missed by RF | F1 cost /frame | payload extra /frame |
|---|---|---|---|---|
| strict | 2605 | 1 | -0.000000 | 0.000002 |
| tie | 394 | 0 | 0.000000 | 0.000000 |
| cost-induced | 0 | 0 | 0.000000 | 0.000000 |
| TOTAL(all-classes) | 2999 | 1 | -0.000000 | 0.000002 |

## Headline (test, from CSV)

| B_max | strict-benefit F1/frame | total E-collapse F1/frame | cost-induced cells |
|---|---|---|---|
| 0.1 | 0.002658 | 0.003021 | 4788 |
| 0.2 | 0.002658 | 0.002888 | 2121 |
| 0.3 | 0.002705 | 0.003030 | 0 |

## vs-frozen-λ-clairvoyant-oracle account (separate from the R9 vs-τ table)

| split | B_max | F1 gap (RF below clairvoyant) | clairvoyant payload | exceeds B_max? |
|---|---|---|---|---|
| validate | 0.1 | -0.000014 | 0.06715 | False |
| validate | 0.2 | 0.001027 | 0.11690 | False |
| validate | 0.3 | 0.000096 | 0.15464 | False |
| test | 0.1 | 0.011699 | 0.11211 | True |
| test | 0.2 | 0.011676 | 0.15214 | False |
| test | 0.3 | 0.009170 | 0.17060 | False |
| culver | 0.1 | 0.014132 | 0.15451 | True |
| culver | 0.2 | 0.015194 | 0.22297 | True |
| culver | 0.3 | 0.006209 | 0.25423 | False |

## Semantic notes

1. This is a **vs-clairvoyant-oracle** account; it is SEPARATE from and must not be cross-referenced with the R9 **vs-τ** decision (`r10c_vs_tau_account.csv`, `r9_result_claims.md`).
2. The tiny validate gaps (max |F1 gap| ≈ 0.001027, some ~1e-6 negative) are normal for the corrected (R10d) classification: in-sample the selector ≈ the clairvoyant oracle and the residual is numerical, not a real reversal.
