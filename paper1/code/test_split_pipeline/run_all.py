#self+ Test-split pipeline orchestrator: runs scripts 01-05 in order with timing + status output, ready to fire once OPV2V test split is downloaded and unzipped
"""
Master orchestrator for the OPV2V test-split generalisation pipeline.

Prerequisite: OPV2V test split unzipped to
    /mnt/h/opencood_project/datasets/opv2v_data_dumping/test/
which is reachable via the symlinked path
    OpenCOOD/opv2v_data_dumping/test/

Stages:
  01_gen_predictions.py        ~15 min on RTX 5070  (GPU)
  02_extract_cues_and_f1.py    ~20 min              (CPU+IO)
  03_build_test_dataset.py     ~10 s                (CPU)
  04_eval_rf_on_test.py        ~30 s                (CPU)
  05_true_e2e_ap_on_test.py    ~10 min              (CPU)
Total: ~45-50 min

Usage:
  PYTHONPATH=. /home/josh/miniconda3/envs/sionna310/bin/python \\
      peiyi_work/01_paper_ca_tosg/test_split_pipeline/run_all.py
"""
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = '/home/josh/miniconda3/envs/sionna310/bin/python'

STAGES = [
    '01_gen_predictions.py',
    '02_extract_cues_and_f1.py',
    '03_build_test_dataset.py',
    '04_eval_rf_on_test.py',
    '05_true_e2e_ap_on_test.py',
]

SPLIT = os.environ.get('CATOSG_SPLIT', 'test')   # 'test' or 'test_culver_city'
TEST_DIR = os.path.join(REPO, f'opv2v_data_dumping/{SPLIT}')
RUNS_SUBDIR = 'runs' if 'culver' not in SPLIT else 'runs_culver'


def main():
    if not os.path.isdir(TEST_DIR):
        print(f'ERROR: {TEST_DIR} not found.')
        print(f'  Download OPV2V test split and unzip to'
              f' /mnt/h/opencood_project/datasets/opv2v_data_dumping/test/')
        sys.exit(1)

    n_scenes = len(os.listdir(TEST_DIR))
    print(f'{SPLIT}/ has {n_scenes} scene dirs.  -> outputs in {RUNS_SUBDIR}/')

    env = os.environ.copy()
    env['PYTHONPATH'] = REPO

    t_start = time.time()
    for stage in STAGES:
        script = os.path.join(HERE, stage)
        if not os.path.exists(script):
            print(f'ERROR: script not found {script}')
            sys.exit(1)
        print(f'\n{"=" * 60}\n  STAGE: {stage}\n{"=" * 60}')
        t0 = time.time()
        try:
            subprocess.check_call([PYTHON, '-u', script], cwd=REPO, env=env)
        except subprocess.CalledProcessError as e:
            print(f'\n!!! STAGE FAILED: {stage}  (exit code {e.returncode})')
            sys.exit(e.returncode)
        print(f'\n  STAGE {stage} done in {(time.time() - t0) / 60:.1f} min')

    print(f'\n{"=" * 60}')
    print(f'ALL STAGES COMPLETE in {(time.time() - t_start) / 60:.1f} min')
    print(f'Results:')
    runs = os.path.join(HERE, RUNS_SUBDIR)
    for f in sorted(os.listdir(runs)):
        path = os.path.join(runs, f)
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        print(f'  {f}  ({size} bytes)')


if __name__ == '__main__':
    main()
