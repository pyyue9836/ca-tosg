#self+ P1 Step 2: ego-only (single-vehicle) per-frame predictions with scores + GT.
# Same frozen PointPillar late-fusion checkpoint, but only the EGO cav is post-processed
# (no collaborator fusion) -> the physically-correct fallback when a requested feature
# message fails (the ego has only its own detection, not the L / late-fusion result).
# GT is the ego-frame GT (identical to the Fixed-L / late branch), so ego-only F1/AP is a
# fair, strictly-lower comparison against Fixed-L.
#   PYTHONPATH=. python regen_ego_only.py --model_dir <late_dir> --out <ego_npz> [--limit N]
import argparse, os, sys
from collections import OrderedDict
import numpy as np, torch
from torch.utils.data import DataLoader

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, REPO)
from opencood.hypes_yaml import yaml_utils
from opencood.tools import train_utils
from opencood.data_utils.datasets import build_dataset


def inference_ego_only(batch_data, model, dataset):
    """Late-fusion post-process on the EGO cav alone (no collaborators)."""
    assert 'ego' in batch_data, f'no ego key in batch: {list(batch_data.keys())}'
    output_dict = OrderedDict()
    output_dict['ego'] = model(batch_data['ego'])
    return dataset.post_process(OrderedDict({'ego': batch_data['ego']}), output_dict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model_dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    opt = ap.parse_args()

    class O:
        model_dir = opt.model_dir
    hypes = yaml_utils.load_yaml(None, O)
    ds = build_dataset(hypes, visualize=False, train=False)
    n = len(ds)
    print(f'{n} samples; EGO-ONLY; model_dir={opt.model_dir}', flush=True)
    loader = DataLoader(ds, batch_size=1, num_workers=4,
                        collate_fn=ds.collate_batch_test, shuffle=False, pin_memory=False)
    model = train_utils.create_model(hypes)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        model.cuda()
    _, model = train_utils.load_saved_model(opt.model_dir, model)
    model.eval()

    boxes_all, scores_all, gts_all = [], [], []
    for i, batch in enumerate(loader):
        if opt.limit and i >= opt.limit:
            break
        with torch.no_grad():
            batch = train_utils.to_device(batch, device)
            pred_box, pred_score, gt_box = inference_ego_only(batch, model, ds)
        def np_(t, shp):
            return t.cpu().numpy() if t is not None and len(t) > 0 else np.zeros(shp, np.float32)
        boxes_all.append(np_(pred_box, (0, 8, 3)))
        scores_all.append(np_(pred_score, (0,)))
        gts_all.append(np_(gt_box, (0, 8, 3)))
        if i % 200 == 0:
            print(f'  {i}/{n}', flush=True)

    os.makedirs(os.path.dirname(opt.out) or '.', exist_ok=True)
    np.savez(opt.out, boxes=np.array(boxes_all, dtype=object),
             scores=np.array(scores_all, dtype=object), gts=np.array(gts_all, dtype=object))
    print('saved', opt.out, 'frames:', len(boxes_all), flush=True)


if __name__ == '__main__':
    main()
