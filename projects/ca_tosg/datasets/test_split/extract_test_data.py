#self+ Peiyi: one-off extractor for OPV2V test split (3-layer nested archives)
"""
OPV2V test split is distributed as three nested layers:
  L1  Google-Drive split zips:  test_chunks-...-00N.zip / test_culver_city_chunks-...-00N.zip
        -> contain:             <name>_chunks/<name>.zip.partXX   (500MB `split` parts)
  L2  concatenate parts      -> <name>.zip                       (zip64, ~24 GB)
  L3  unzip                   -> scene directories

Final layout (STANDARD OPV2V, two separate domains — user decision 2026-06-15):
    opv2v_data_dumping/test/<scene_dir>/...              <- from test.zip
    opv2v_data_dumping/test_culver_city/<scene_dir>/...  <- from test_culver_city.zip
The pipeline (TEST_PATH='opv2v_data_dumping/test') evaluates the regular test
split only; culver_city is kept as a sibling for optional later use.

NOTE the OpenCOOD loader treats every dir under test/ as a scenario, so the
downloaded DATA_test/ (zips + parts) must NOT remain inside test/. After a
successful extract we relocate it to opv2v_data_dumping/DATA_test_archive/.

Safety/resume: L1 always re-`unzip -o` (idempotent overwrite — a kill mid-write
is repaired on rerun). L2 skips an already-complete .zip by exact size. L3 uses
a fresh staging dir each run.
"""
import os, sys, glob, subprocess, zipfile, shutil

DATASET_ROOT = '/mnt/h/opencood_project/datasets/opv2v_data_dumping'
TEST_DIR     = os.path.join(DATASET_ROOT, 'test')
CULVER_DIR   = os.path.join(DATASET_ROOT, 'test_culver_city')
SRC          = os.path.join(TEST_DIR, 'DATA_test')   # holds the downloaded zips

def log(m): print(m, flush=True)

def sh(cmd):
    log('  $ ' + ' '.join(cmd))
    subprocess.run(cmd, check=True)

# ---- L1: unzip Google-Drive bundles into SRC (always overwrite => kill-safe) ----
def unzip_bundles(prefix):
    bundles = sorted(glob.glob(os.path.join(SRC, f'{prefix}-*.zip')))
    log(f'[L1] {prefix}: {len(bundles)} drive bundles -> part files')
    for b in bundles:
        log(f'  unzip {os.path.basename(b)}')
        sh(['unzip', '-q', '-o', b, '-d', SRC])

# ---- L2: cat parts -> SRC/<name>.zip ----
def concat_parts(name):
    out = os.path.join(SRC, f'{name}.zip')
    parts = sorted(glob.glob(os.path.join(SRC, f'{name}_chunks', f'{name}.zip.part*')))
    if not parts:
        log(f'[L2] {name}: NO parts found - abort'); sys.exit(1)
    total = sum(os.path.getsize(p) for p in parts)
    if os.path.exists(out) and os.path.getsize(out) == total:
        log(f'[L2] {name}: {name}.zip already complete ({total/1e9:.1f} GB), skip')
        return out
    log(f'[L2] {name}: concat {len(parts)} parts -> {name}.zip ({total/1e9:.1f} GB)')
    with open(out, 'wb') as fo:
        for p in parts:
            with open(p, 'rb') as fi:
                shutil.copyfileobj(fi, fo, length=64 * 1024 * 1024)
    return out

# ---- L3: unzip into staging, flatten any wrapper, move scenes into dest_dir ----
def unzip_final(zip_path, name, dest_dir):
    stage = os.path.join(DATASET_ROOT, f'_staging_{name}')
    if os.path.exists(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)
    log(f'[L3] {name}: unzip -> staging')
    sh(['unzip', '-q', '-o', zip_path, '-d', stage])

    children = [d for d in os.listdir(stage) if os.path.isdir(os.path.join(stage, d))]
    src = stage
    if len(children) == 1 and children[0] in (name, 'test', 'test_culver_city'):
        src = os.path.join(stage, children[0])
        log(f'  flatten wrapper dir: {children[0]}/')

    os.makedirs(dest_dir, exist_ok=True)
    scenes = sorted(os.listdir(src))
    log(f'  moving {len(scenes)} scene dirs -> {dest_dir}')
    moved = 0
    for s in scenes:
        d = os.path.join(dest_dir, s)
        if os.path.exists(d):
            log(f'  WARN exists, skip: {s}')
            continue
        shutil.move(os.path.join(src, s), d)
        moved += 1
    shutil.rmtree(stage)
    log(f'  moved {moved} scene dirs into {os.path.basename(dest_dir)}/')

def count_scenes(d):
    if not os.path.isdir(d):
        return []
    return sorted(x for x in os.listdir(d)
                  if os.path.isdir(os.path.join(d, x)) and x != 'DATA_test')

def main():
    # regular test -> opv2v_data_dumping/test/  (scenes directly, pipeline reads this)
    unzip_bundles('test_chunks')
    unzip_final(concat_parts('test'), 'test', TEST_DIR)
    # culver_city -> opv2v_data_dumping/test_culver_city/  (sibling, separate domain)
    unzip_bundles('test_culver_city_chunks')
    unzip_final(concat_parts('test_culver_city'), 'test_culver_city', CULVER_DIR)

    # move the download archive out of test/ so the loader doesn't see it as a scene
    archive = os.path.join(DATASET_ROOT, 'DATA_test_archive')
    if os.path.isdir(SRC):
        log(f'[cleanup] relocate DATA_test -> {archive}')
        if os.path.exists(archive):
            shutil.rmtree(archive)
        shutil.move(SRC, archive)

    log('=== EXTRACTION COMPLETE ===')
    t = count_scenes(TEST_DIR)
    c = count_scenes(CULVER_DIR)
    log(f'test/            : {len(t)} scene dirs')
    for e in t[:6]: log('    ' + e)
    log(f'test_culver_city/: {len(c)} scene dirs')
    for e in c[:6]: log('    ' + e)

if __name__ == '__main__':
    main()
