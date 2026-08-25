# `archive/retired-scripts/` — scripts kept as a record, removed from the live tree

Nothing here is runnable against the current tree, and nothing here may be quoted as current state.
A script lands here instead of being deleted when its *reasoning* is worth keeping but its
*execution* is not: it targets a retired engine, a retired action set, a retired path layout, or a
product that `tests/retired_products.md` records as deleted.

`tests/test_no_retired_writes.py` does not scan this directory. That is the point of the directory:
a live script that can rebuild a deleted product is a resurrection hazard, and an archived one is a
document.

| script | archived | why it is not live |
|---|---|---|
| `action_dist.py` | R69-2 | Three separate retirements in one file. Its action set is the v3 `{L, C16, C256}`, not the deployed `{E, L, F}`; its paths are the pre-restructure runtime (`/home/josh/.../peiyi_work/paper1`, `results/bler_sionna/bler_sionna.csv`), neither of which exists in this layout; and its output `results/main/step4_oracle_action_dist.csv` was deleted in R67 (c) with its index entry. It had no live caller. The frozen action mix is `results/main/action_distribution.csv`, written by `tools/evaluate_selector.py`. |
