#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""P2-R3 E-1 — a GPU-time ESTIMATE for the V2V4Real plan. Nothing is run on the GPU.

Every measured input is a P1 product recorded on this machine for this checkpoint architecture; every
assumption is named as one. The output is a range, and its width is the honest size of what is not
known. It is not a measurement and must not be quoted as one; the first GPU step after approval is a
one-epoch timing probe that replaces it.

    python projects/ca_tosg_p2/protocol/gpu_estimate.py [--check]
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT_JSON = os.path.join(HERE, 'gpu_estimate.json')
OUT_MD = os.path.join(HERE, 'gpu_estimate.md')
PROBE = os.path.join(ROOT, 'results/manifests/P4B_PROBE_pointpillar_compression.json')

# V2V4Real split sizes, quoted: Xu et al., CVPR 2023 (arXiv:2303.07601): "The dataset is split into the
# train/validation/test set with 14,210/2,000/3,986 frames, respectively, for all three tasks."
V2V4REAL_FRAMES = {'train': 14210, 'validate': 2000, 'test': 3986}
# ASSUMPTION, not measured: one training step (forward + backward + optimiser) costs 2-3x a forward pass
TRAIN_OVER_INFERENCE = (2.0, 3.0)
# ASSUMPTION: a V2V4Real frame costs about what an OPV2V frame cost in P1 (32-beam clouds are sparser;
# not measured)
SPLITS_MEASURED = ('validate', 'test', 'culver')


def gpu_name():
    try:
        return subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                              capture_output=True, text=True, timeout=10).stdout.strip() or 'unknown'
    except Exception:
        return 'unknown'


def build():
    wp2 = {s: json.load(open(os.path.join(ROOT, f'results/v2/wp2_per_agent_{s}.json'))) for s in SPLITS_MEASURED}
    s_inf = {s: float(wp2[s]['sec_per_frame']) for s in SPLITS_MEASURED}
    w5 = json.load(open(os.path.join(ROOT, 'results/v2/wp5_final_validate.json')))
    if 'sec_per_frame' not in w5:
        raise SystemExit('GPU ESTIMATE: wp5_final_validate.json has no sec_per_frame -- refusing to guess')
    s_f = float(w5['sec_per_frame'])
    ckpt = yaml.load(open(os.path.join(json.load(open(PROBE))['ckpt_dir'], 'config.yaml')), Loader=yaml.UnsafeLoader)  # trusted local OpenCOOD checkpoint config; it holds numpy-tagged values SafeLoader rejects
    epochs = int(ckpt['train_params']['epoches'])
    batch = int(ckpt['train_params']['batch_size'])

    lo, hi = min(s_inf.values()), max(s_inf.values())
    train_frames = V2V4REAL_FRAMES['train']
    train_h = (train_frames * epochs * lo * TRAIN_OVER_INFERENCE[0] / 3600,
               train_frames * epochs * hi * TRAIN_OVER_INFERENCE[1] / 3600)
    eval_frames = V2V4REAL_FRAMES['validate'] + V2V4REAL_FRAMES['test']
    per_agent_h = (eval_frames * lo / 3600, eval_frames * hi / 3600)
    f_products_h = eval_frames * s_f / 3600
    total = (train_h[0] + per_agent_h[0] + f_products_h, train_h[1] + per_agent_h[1] + f_products_h)
    return {
        'schema': 'catosg-p2-gpu-estimate/1', 'kind': 'ESTIMATE -- nothing was run on the GPU',
        'gpu': gpu_name(),
        'measured_inputs': {
            'wp2_per_agent_sec_per_frame': s_inf,
            'wp2_note': 'P1 per-agent inference (ego and collaborator forwards, data loading and writing '
                        'included). The validate figure is several times the other two; the cause is not '
                        'established, so the range keeps it rather than discarding it.',
            'wp5_f_products_sec_per_frame_validate': s_f,
            'wp5_note': 'P1 F products on validate: every loss rate, regime and replicate, per frame',
            'checkpoint_train_params': {'epoches': epochs, 'batch_size': batch}},
        'assumptions': {'v2v4real_frames': V2V4REAL_FRAMES,
                        'train_step_over_inference': list(TRAIN_OVER_INFERENCE),
                        'v2v4real_frame_cost_equals_p1_frame_cost': True,
                        'gpu_memory_for_batch_size_verified': False},
        'components_gpu_hours': {
            'train_unified_checkpoint': list(train_h),
            'per_agent_inference_val_plus_test': list(per_agent_h),
            'f_products_val_plus_test_one_F_variant': f_products_h},
        'total_gpu_hours_one_F_variant': list(total),
        'not_included': ['checkpoint-selection evaluation passes', 'failed or repeated runs',
                         'each additional F variant (block size, ranking, receiver rule) repeats the '
                         'F-product component', 'any fusion adaptation of P2-R3 C-6'],
        'first_gpu_step_after_approval': 'a one-epoch timing probe on V2V4Real train, which replaces the '
                                         'training row of this estimate',
        'command': 'python projects/ca_tosg_p2/protocol/gpu_estimate.py'}


def markdown(m):
    c = m['components_gpu_hours']
    L = ['<!-- GENERATED by projects/ca_tosg_p2/protocol/gpu_estimate.py -- do not edit by hand -->',
         '# GPU estimate for the V2V4Real plan (P2-R3 E-1)', '',
         f"**{m['kind']}.** GPU: {m['gpu']}.", '',
         '| component | GPU-hours |', '|---|---:|',
         f"| train the unified checkpoint | {c['train_unified_checkpoint'][0]:.0f} – {c['train_unified_checkpoint'][1]:.0f} |",
         f"| per-agent inference, validate + test (E and L products) | {c['per_agent_inference_val_plus_test'][0]:.1f} – {c['per_agent_inference_val_plus_test'][1]:.1f} |",
         f"| F products, validate + test, one F variant | {c['f_products_val_plus_test_one_F_variant']:.1f} |",
         f"| **total, one F variant** | **{m['total_gpu_hours_one_F_variant'][0]:.0f} – {m['total_gpu_hours_one_F_variant'][1]:.0f}** |",
         '', '**Measured inputs** (P1 products, this machine):', '']
    mi = m['measured_inputs']
    L += [f"* per-agent inference s/frame: " + ', '.join(f'{k} {v:.3f}' for k, v in mi['wp2_per_agent_sec_per_frame'].items())
          + f". {mi['wp2_note']}",
          f"* F products s/frame (validate): {mi['wp5_f_products_sec_per_frame_validate']:.3f}. {mi['wp5_note']}.",
          f"* checkpoint config: {mi['checkpoint_train_params']['epoches']} epochs, batch size "
          f"{mi['checkpoint_train_params']['batch_size']}.", '', '**Assumptions:**', '']
    a = m['assumptions']
    L += [f"* V2V4Real frames {a['v2v4real_frames']} (quoted from the dataset paper).",
          f"* a training step costs {a['train_step_over_inference'][0]:g}–{a['train_step_over_inference'][1]:g}× a forward pass (not measured).",
          '* a V2V4Real frame costs about what an OPV2V frame cost in P1 (not measured).',
          '* GPU memory for the checkpoint batch size on this card: not verified.', '',
          '**Not included:** ' + '; '.join(m['not_included']) + '.', '',
          f"**First GPU step after approval:** {m['first_gpu_step_after_approval']}."]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    m = build()
    m_check = dict(m); m_check['gpu'] = 'recorded'          # the card name is informational, not reproduced
    js, md = json.dumps(m, indent=1) + '\n', markdown(m)
    if a.check:
        rec = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else None
        if rec is not None:
            rec['gpu'] = 'recorded'
        ok = rec == json.loads(json.dumps(m_check))
        print('gpu estimate:', 'reproduced' if ok else 'FAIL -- not what the generator writes')
        return 0 if ok else 1
    open(OUT_JSON, 'w').write(js); open(OUT_MD, 'w').write(md)
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main())
