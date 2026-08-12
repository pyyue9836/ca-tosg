# Where2comm (baseline)

| | |
|---|---|
| **Source paper** | Hu, Fang, Lei, Zhong, Chen. *Where2comm: Communication-Efficient Collaborative Perception via Spatial Confidence Maps.* NeurIPS 2022. Reference code: <https://github.com/MediaBrain-SJTU/where2comm> |
| **Modifications** | Trained inside the sibling OpenCOOD checkout with this project's PointPillar config and OPV2V split, so the detector, the GT and the AP scorer are identical to every CA-TOSG row. No change to the method itself. |
| **Checkpoint** | `point_pillar_where2comm_2026_05_22_17_56_51`, **epoch 50**, under the git-excluded `experiment_logs/opencood_training_logs/` in the OpenCOOD checkout. |
| **Data split** | OPV2V **validate**, 1980 frames — the same 9 scenes the selector is fitted on, so the comparison is split-matched. |
| **Run command** | The reported row is produced by the OpenCOOD **global-sort** evaluation of that checkpoint (`eval_global_sort.yaml`), not by the script in this folder. See "warning" below. |
| **Output** | `results/baselines/where2comm.csv` — AP@0.3 / 0.5 / 0.7 = 0.8867 / 0.8707 / 0.7897. Provenance: `results/provenance/where2comm_ap_PROVENANCE.txt`. |

## Warning: `compare.py` is not the generator

`compare.py` computes an **epoch-37, perfect-channel, single-point** AP — an early defence line.
The reported row is **epoch-50 global-sort**. Epoch and evaluation protocol both differ; the two
numbers must not be conflated. The file is kept because it is the record of that earlier check.

Protocol match matters here: AP is computed with the same global-sort scorer used for the CA-TOSG
rows (`projects/ca_tosg/evaluation/true_e2e_global.py` family), so the numbers sit on one ruler.
