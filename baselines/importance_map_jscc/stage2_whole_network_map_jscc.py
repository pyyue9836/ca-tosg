import argparse
import os
import csv
import torch
from torch.utils.data import DataLoader

from opencood.hypes_yaml.yaml_utils import load_yaml
from opencood.tools import train_utils
from opencood.data_utils.datasets import build_dataset


def make_param_groups(model, lr_base=1e-5, lr_new=5e-5, weight_decay=1e-4):
    new_params = []
    base_params = []

    for name, p in model.named_parameters():
        p.requires_grad = True

        if ("fusion_net.importance_map" in name) or ("fusion_net.semantic_codec" in name):
            new_params.append(p)
        else:
            base_params.append(p)

    print("[INFO] Base trainable params:", len(base_params))
    print("[INFO] New module trainable params:", len(new_params))

    return [
        {"params": base_params, "lr": lr_base, "weight_decay": weight_decay},
        {"params": new_params, "lr": lr_new, "weight_decay": weight_decay},
    ]


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
        "--stage1_ckpt",
        default="experiment_logs/importance_map_jscc/stage1_rec_pretrain_sttopk_snr10/stage1_rec_sttopk_1000steps.pth"
    )
    parser.add_argument(
        "--out_dir",
        default="experiment_logs/importance_map_jscc/stage2_whole_map_snr10_3000steps"
    )
    parser.add_argument("--max_steps", type=int, default=6000)
    parser.add_argument("--lambda_rec", type=float, default=0.5)
    return parser.parse_args()


def main():
    args = parse_args()
    yaml_path = args.yaml_path
    stage1_ckpt = args.stage1_ckpt

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    max_steps = args.max_steps
    lambda_rec = args.lambda_rec

    print("[INFO] Strict MAP Stage-2 whole-network joint training")
    print("[INFO] YAML:", yaml_path)
    print("[INFO] Stage-1 checkpoint:", stage1_ckpt)
    print("[INFO] max_steps:", max_steps)
    print("[INFO] lambda_rec:", lambda_rec)

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

    print("[INFO] Loading Stage-1 checkpoint...")
    state = torch.load(stage1_ckpt, map_location="cpu")
    model.load_state_dict(state, strict=True)

    print("[INFO] Creating detection loss...")
    criterion = train_utils.create_loss(hypes)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("[INFO] Device:", device)

    model = model.to(device)
    model.train()

    optimizer = torch.optim.Adam(
        make_param_groups(model),
    )

    log_path = os.path.join(out_dir, "stage2_whole_map_log.csv")

    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "step",
            "total_loss",
            "det_loss",
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

            det_loss = criterion(output_dict, batch_data["ego"]["label_dict"])
            if isinstance(det_loss, tuple):
                det_loss = det_loss[0]

            rec_loss = output_dict.get("rec_loss", None)
            if rec_loss is None:
                raise RuntimeError("rec_loss not found in output_dict.")

            total_loss = det_loss + lambda_rec * rec_loss

            optimizer.zero_grad()
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=10.0)
            optimizer.step()

            com_value = scalar_from_output(output_dict, "com")
            paper_cr = scalar_from_output(output_dict, "paper_cr_actual")
            remote_cr = scalar_from_output(output_dict, "remote_payload_cr_actual")
            remote_tokens = scalar_from_output(output_dict, "remote_payload_tokens")
            remote_total_tokens = scalar_from_output(output_dict, "remote_payload_total_tokens")
            com_including_ego = scalar_from_output(output_dict, "com_including_ego")

            total_float = float(total_loss.detach().cpu())
            det_float = float(det_loss.detach().cpu())
            rec_float = float(rec_loss.detach().cpu())

            writer.writerow([
                step,
                total_float,
                det_float,
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
                    f"total={total_float:.6f}, "
                    f"det={det_float:.6f}, "
                    f"rec={rec_float:.6f}, "
                    f"paper_cr={paper_cr:.6f}, "
                    f"remote_cr={remote_cr:.6f}"
                )

    ckpt_path = os.path.join(out_dir, f"stage2_whole_map_{max_steps}steps.pth")
    torch.save(model.state_dict(), ckpt_path)

    print("[OK] Strict MAP Stage-2 whole-network training finished.")
    print("[INFO] Saved checkpoint:", ckpt_path)
    print("[INFO] Saved log:", log_path)


if __name__ == "__main__":
    main()
