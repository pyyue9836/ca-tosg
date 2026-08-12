#self+ CA-TOSG: re-run inference saving per-frame (boxes, SCORES, gt) so true-e2e can use GLOBAL-sort AP.
# Usage:
#   PYTHONPATH=. python regen_preds_with_scores.py --model_dir <dir> --fusion_method {late,intermediate} --out <npz> [--limit N]
import argparse, os, sys
import numpy as np, torch
from torch.utils.data import DataLoader

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, REPO)
from opencood.hypes_yaml import yaml_utils
from opencood.tools import train_utils, inference_utils
from opencood.data_utils.datasets import build_dataset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', required=True)
    ap.add_argument('--fusion_method', required=True, choices=['late', 'intermediate', 'early'])
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    opt = ap.parse_args()

    class O:  # yaml_utils.load_yaml expects an object with .model_dir
        model_dir = opt.model_dir
    hypes = yaml_utils.load_yaml(None, O)
    ds = build_dataset(hypes, visualize=False, train=False)
    n = len(ds)
    print(f'{n} samples; fusion={opt.fusion_method}; model_dir={opt.model_dir}', flush=True)
    loader = DataLoader(ds, batch_size=1, num_workers=8,
                        collate_fn=ds.collate_batch_test, shuffle=False, pin_memory=False)
    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(opt.model_dir, model)
    model.eval()

    inf = {'late': inference_utils.inference_late_fusion,
           'intermediate': inference_utils.inference_intermediate_fusion,
           'early': inference_utils.inference_early_fusion}[opt.fusion_method]

    boxes_all, scores_all, gts_all = [], [], []
    for i, batch in enumerate(loader):
        if opt.limit and i >= opt.limit:
            break
        with torch.no_grad():
            batch = train_utils.to_device(batch, device)
            pred_box, pred_score, gt_box = inf(batch, model, ds)
        def np_(t, shp):
            return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
        boxes_all.append(np_(pred_box, (0, 8, 3)))
        scores_all.append(np_(pred_score, (0,)))
        gts_all.append(np_(gt_box, (0, 8, 3)))
        if i % 200 == 0:
            print(f'  {i}/{n}', flush=True)

    os.makedirs(os.path.dirname(opt.out) or '.', exist_ok=True)
    np.savez(opt.out,
             boxes=np.array(boxes_all, dtype=object),
             scores=np.array(scores_all, dtype=object),
             gts=np.array(gts_all, dtype=object))
    print('saved', opt.out, 'frames:', len(boxes_all), flush=True)


if __name__ == '__main__':
    main()
