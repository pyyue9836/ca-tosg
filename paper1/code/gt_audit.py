#self+ P1 GT audit: codify the ground-truth diagnosis as a script + CSV artifact.
# Rule (2026-07-12): any "I read the code" claim about GT is backed by this script + its output,
# not chat. Facts established:
#   - EVAL-time GT = post_processor.generate_gt_bbx (base_postprocessor.py L45-96): projects EVERY
#     CAV's object_bbx_center to ego, unions + dedups by object_id, filters to GT_RANGE. Both the
#     LateFusionDataset and IntermediateFusionDataset eval GTs go through this -> both are UNION GTs,
#     ~identical. (The generate_object_center([ego]) read in round 1 is the TRAIN-time dataset GT,
#     a different path -- source of the two rounds' contradiction.)
#   - GT_RANGE = [-140,-40,-3,140,40,1] (standard OPV2V eval range).
#   - Q4: late predictions DO contain |x|>70.4 boxes (collaborator boxes projected to ego) -> no
#     structural range asymmetry; the ±70.4-crop idea is rejected.
# Output: results/gt_audit.csv
import os, sys
import numpy as np
REPO = '/home/josh/cooperative_semantic_perception/OpenCOOD'; sys.path.insert(0, REPO)
GS = os.path.join(REPO, 'peiyi_work/paper1/gs_rerun')
GT_RANGE = [-140, -40, -3, 140, 40, 1]
R = 70.4
import pandas as pd


def cx(arr):
    a = np.asarray(arr)
    return a.reshape(len(a), -1, 3).mean(1)[:, 0] if a.size else np.array([])


def near_far(seq):
    near = far = 0
    for b in seq:
        x = np.abs(cx(b))
        near += int((x <= R).sum()); far += int((x > R).sum())
    return near, far


def centroid_overlap(a, b, thr=0.5):
    fr = []
    for i in range(len(a)):
        A = cx(a[i]); B = cx(b[i])
        Ay = np.asarray(a[i]).reshape(-1, 3).reshape(len(a[i]) if len(a[i]) else 0, -1, 3)
        if len(A) == 0 and len(B) == 0: fr.append(1.0); continue
        if len(A) == 0 or len(B) == 0: fr.append(0.0); continue
        ca = np.asarray(a[i]).reshape(len(a[i]), -1, 3).mean(1)
        cb = np.asarray(b[i]).reshape(len(b[i]), -1, 3).mean(1)
        m = sum(1 for p in ca if np.min(np.linalg.norm(cb - p, axis=1)) < thr)
        fr.append(m / max(len(ca), len(cb)))
    return float(np.mean(fr))


def main():
    rows = []
    for sp in ('validate', 'test', 'culver'):
        la = np.load(f'{GS}/late_{sp}.npz', allow_pickle=True)
        co = np.load(f'{GS}/comp_{sp}.npz', allow_pickle=True)
        eg = np.load(f'{GS}/ego_{sp}.npz', allow_pickle=True)
        lgn, lgf = near_far(la['gts']); cgn, cgf = near_far(co['gts'])
        lpn, lpf = near_far(la['boxes']); cpn, cpf = near_far(co['boxes']); epn, epf = near_far(eg['boxes'])
        ov = centroid_overlap(la['gts'], co['gts'])
        n = len(la['gts'])
        rows.append(dict(split=sp, n=n,
                         lateGT_near=round(lgn/n, 2), lateGT_far=round(lgf/n, 2),
                         compGT_near=round(cgn/n, 2), compGT_far=round(cgf/n, 2),
                         GT_centroid_overlap=round(ov, 4),
                         latePRED_far_total=lpf, compPRED_far_total=cpf, egoPRED_far_total=epf,
                         Q4_late_far_preds_exist=bool(lpf > 0)))
        print(f"{sp:9s} GT late {lgn/n:.2f}/{lgf/n:.2f} comp {cgn/n:.2f}/{cgf/n:.2f} (near/far) overlap={ov:.3f} "
              f"| PRED far: late={lpf} comp={cpf} ego={epf} | Q4 late-far-preds={'EXIST' if lpf>0 else 'ABSENT'}")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results/gt_audit.csv'), index=False)
    print(f"\nGT_RANGE = {GT_RANGE} (standard OPV2V eval range)")
    print("EVAL GT path = post_processor.generate_gt_bbx (all-CAV union, object_id dedup, GT_RANGE).")
    print("[artifact] results/gt_audit.csv")


if __name__ == '__main__':
    main()
