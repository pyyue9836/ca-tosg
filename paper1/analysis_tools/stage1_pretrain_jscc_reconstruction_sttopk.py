import argparse
import os
import csv
import torch
from torch.utils.data import DataLoader

from opencood.hypes_yaml.yaml_utils import load_yaml
from opencood.tools import train_utils
from opencood.data_utils.datasets import build_dataset


def load_matching_weights(model, ckpt_path):
    source_state = torch.load(ckpt_path, map_location="cpu")
    target_state = model.state_dict()

    matched = {}
    for k, v in source_state.items():
        if k in target_state and target_state[k].shape == v.shape:
            matched[k] = v

    target_state.update(matched)
    model.load_state_dict(target_state, strict=True)

    print(f"[INFO] Loaded matched weights: {len(matched)}")
    return model


def set_trainable_stage1(model):
    for p in model.parameters():
        p.requires_grad = False

    for p in model.fusion_net.importance_map.parameters():
        p.requires_grad = True
    for p in model.fusion_net.semantic_codec.parameters():
        p.requires_grad = True

    trainable = [n for n, p in model.named_parameters() if p.requires_grad]
    print("[INFO] Number of trainable tensors:", len(trainable))
    for n in trainable[:50]:
        print("  ", n)


def scalar_from_output(output_dict, name, default=-1.0):
    value = output_dict.get(name, None)
    if torch.is_tensor(value):
        return float(value.detach().cpu())
    if value is None:
        return default
    return float(value)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--yaml_path",
        default="opencood/hypes_yaml/point_pillar_importance_map_jscc_awgn.yaml"
    )
    parser.add_argument(
        "--warm_ckpt",
        default="opencood/logs/point_pillar_where2comm_2026_05_20_16_39_22/net_epoch50.pth"
    )
    parser.add_argument(
        "--out_dir",
        default="experiment_logs/importance_map_jscc/stage1_rec_pretrain_sttopk_snr10"
    )
    parser.add_argument("--max_steps", type=int, default=3000)
    parser.add_argument("--lr", type=float, default=1e-4)
    return parser.parse_args()


def main():
    args = parse_args()
    yaml_path = args.yaml_path
    warm_ckpt = args.warm_ckpt
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    max_steps = args.max_steps
    lr = args.lr

    print("[INFO] YAML:", yaml_path)
    print("[INFO] Warm checkpoint:", warm_ckpt)
    print("[INFO] Training mode: learned importance map + straight-through top-k")

    hypes = load_yaml(yaml_path)

    print("[INFO] Building dataset...")
    dataset = build_dataset(hypes, visualize=False, train=True)

    loader = DataLoader(
        dataset,
        batch_size=1,
        num_workers=0,
        collate_fn=dataset.collate_batch_train,
        shuffle=True,
        pin_memory=False,
        drop_last=True
    )

    print("[INFO] Creating model...")
    model = train_utils.create_model(hypes)
    model = load_matching_weights(model, warm_ckpt)
    set_trainable_stage1(model)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("[INFO] Device:", device)

    model = model.to(device)
    model.train()

    optimizer = torch.optim.Adam(
        [p for p in model.parameters() if p.requires_grad],
        lr=lr,
        weight_decay=1e-4
    )

    log_path = os.path.join(out_dir, "stage1_rec_sttopk_log.csv")

    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "step",
            "rec_loss",
            "communication_rate",
            "paper_cr_actual",
            "remote_payload_cr_actual",
            "remote_payload_tokens",
            "remote_payload_total_tokens",
            "com_including_ego",
        ])

        for step, batch_data in enumerate(loader, start=1):
            if step > max_steps:
                break

            batch_data = train_utils.to_device(batch_data, device)

            output_dict = model(batch_data["ego"])
            rec_loss = output_dict["rec_loss"]

            optimizer.zero_grad()
            rec_loss.backward()
            optimizer.step()

            com_value = scalar_from_output(output_dict, "com")
            paper_cr = scalar_from_output(output_dict, "paper_cr_actual")
            remote_cr = scalar_from_output(output_dict, "remote_payload_cr_actual")
            remote_tokens = scalar_from_output(output_dict, "remote_payload_tokens")
            remote_total_tokens = scalar_from_output(output_dict, "remote_payload_total_tokens")
            com_including_ego = scalar_from_output(output_dict, "com_including_ego")
            rec_float = float(rec_loss.detach().cpu())

            writer.writerow([
                step,
                rec_float,
                com_value,
                paper_cr,
                remote_cr,
                remote_tokens,
                remote_total_tokens,
                com_including_ego,
            ])

            if step == 1 or step % 50 == 0:
                print(
                    f"[STEP {step:04d}] "
                    f"rec_loss={rec_float:.6f}, "
                    f"paper_cr={paper_cr:.6f}, "
                    f"remote_cr={remote_cr:.6f}"
                )

    ckpt_path = os.path.join(out_dir, f"stage1_rec_sttopk_{max_steps}steps.pth")
    torch.save(model.state_dict(), ckpt_path)

    print("[OK] Stage-1 ST top-k reconstruction pretraining finished.")
    print("[INFO] Saved checkpoint:", ckpt_path)
    print("[INFO] Saved log:", log_path)


if __name__ == "__main__":
    main()
