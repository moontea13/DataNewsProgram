"""Download the pinned Chinese CLIP checkpoint to the task cache."""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from common import ROOT, MODEL_CACHE, load, save, sha256
from fetch_models import MODELS, fetch

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    spec = load(ROOT / 'style_protocol.json')['cover_models']['chinese_clip']
    MODELS['chinese_clip'] = {**spec, 'files': ['config.json', 'preprocessor_config.json', 'pytorch_model.bin', 'vocab.txt', 'README.md']}
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(lambda f: fetch('chinese_clip', f), MODELS['chinese_clip']['files']))
    for row in records:
        row['sha256'] = sha256(MODEL_CACHE / 'chinese_clip' / row['file'])
    save(MODEL_CACHE / 'chinese_clip/manifest.json', {'repo': spec['repo'], 'revision': spec['revision'], 'files': records})
    print('Chinese CLIP ready', flush=True)
