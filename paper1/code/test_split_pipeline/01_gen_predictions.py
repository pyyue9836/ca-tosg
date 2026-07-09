#self+ Test-split pipeline 01: run OpenCOOD inference on OPV2V test split for late_fusion and attentive_compression backbones; cache per-frame .npy predictions for downstream cue / F1 / AP computation
"""
Generates per-frame predictions on the OPV2V test split for two backbones:
  - PointPillar_Late          (used as the L message ground-truth detection set)
  - PointPillar_Attentive_Compressed (used as the clean C16/C256 message)

The output .npy files mirror the existing validate-split layout under
peiyi_work/05_pretrained_models/<model>/npy/. We write the test predictions
into a SIBLING npy_test/ directory to avoid clobbering the existing validate
predictions.

Usage:
  PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \\
      peiyi_work/01_paper_ca_tosg/test_split_pipeline/01_gen_predictions.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
PYTHON = '/home/josh/miniconda3/envs/sionna310/bin/python'

CKPTS = [
    {
        'name': 'late',
        'fusion_method': 'late',
        'ckpt_dir': os.path.join(REPO, 'peiyi_work/05_pretrained_models/'
                                       'pointpillar_late_fusion'),
    },
    {
        'name': 'compressed',
        'fusion_method': 'intermediate',
        'ckpt_dir': os.path.join(REPO, 'peiyi_work/05_pretrained_models/'
                                       'pointpillar_attentive_fusion/'
                                       'pointpillar_attentive_fusion_compression'),
    },
]

SPLIT = os.environ.get('CATOSG_SPLIT', 'test')   # 'test' or 'test_culver_city'
TAG = 'culver' if 'culver' in SPLIT else 'test'  # eval-dir suffix tag
TEST_PATH = f'opv2v_data_dumping/{SPLIT}'


def make_test_eval_dir(original_dir):
    """Build a sibling directory that mirrors the ckpt but with a test config.

    We copy (not move) the config.yaml, swap root_dir/validate_dir to point at
    the test split, and symlink the actual .pth checkpoint(s) so we don't
    duplicate the large model file.
    """
    parent = os.path.dirname(original_dir)
    name = os.path.basename(original_dir) + f'_{TAG}_eval'
    test_dir = os.path.join(parent, name)
    os.makedirs(test_dir, exist_ok=True)

    # Load and patch config.
    src_cfg = os.path.join(original_dir, 'config.yaml')
    with open(src_cfg) as f:
        # OpenCOOD configs embed numpy objects (e.g. grid_size) via python/object
        # tags, which yaml.safe_load rejects. Use the full Loader like OpenCOOD's
        # own load_yaml (opencood/hypes_yaml/yaml_utils.py).
        cfg = yaml.load(f, Loader=yaml.Loader)
    if 'root_dir' in cfg:
        cfg['root_dir'] = TEST_PATH
    if 'validate_dir' in cfg:
        cfg['validate_dir'] = TEST_PATH
    with open(os.path.join(test_dir, 'config.yaml'), 'w') as f:
        yaml.dump(cfg, f)

    # Symlink any *.pth checkpoint files in the original dir.
    for fname in os.listdir(original_dir):
        if fname.endswith('.pth'):
            src = os.path.join(original_dir, fname)
            dst = os.path.join(test_dir, fname)
            if not os.path.exists(dst):
                os.symlink(src, dst)

    # Symlink eval.yaml if present (some ckpts have one).
    eval_src = os.path.join(original_dir, 'eval.yaml')
    if os.path.exists(eval_src):
        eval_dst = os.path.join(test_dir, 'eval.yaml')
        if not os.path.exists(eval_dst):
            os.symlink(eval_src, eval_dst)

    return test_dir


def run_inference(test_dir, fusion_method):
    """Invoke opencood.tools.inference with --save_npy."""
    cmd = [
        PYTHON, '-u', os.path.join(REPO, 'opencood/tools/inference.py'),
        '--model_dir', test_dir,
        '--fusion_method', fusion_method,
        '--save_npy',
    ]
    env = os.environ.copy()
    env['PYTHONPATH'] = REPO
    print(f'  cmd: {" ".join(cmd)}')
    subprocess.check_call(cmd, env=env, cwd=REPO)


def main():
    for ckpt in CKPTS:
        print(f'\n===== {ckpt["name"]} on OPV2V test =====')
        test_dir = make_test_eval_dir(ckpt['ckpt_dir'])
        print(f'  test_eval dir: {test_dir}')
        npy_dir = os.path.join(test_dir, 'npy')
        if os.path.exists(npy_dir) and len(os.listdir(npy_dir)) > 0:
            print(f'  SKIP: npy/ already populated ({len(os.listdir(npy_dir))} files)')
            continue
        run_inference(test_dir, ckpt['fusion_method'])
        print(f'  done. predictions at {npy_dir}')

    print('\nAll predictions generated. Next step: 02_extract_cues_and_f1.py')


if __name__ == '__main__':
    main()
