"""Download pinned public model files into this task's cache (never into source data)."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import time
import requests

from common import ROOT, MODEL_CACHE
CACHE = MODEL_CACHE
MODELS = {
    'dinov2': {'repo': 'facebook/dinov2-small', 'revision': 'ed25f3a31f01632728cabb09d1542f84ab7b0056',
                'files': ['config.json', 'preprocessor_config.json', 'model.safetensors', 'README.md']},
    'bge_m3': {'repo': 'BAAI/bge-m3', 'revision': '5617a9f61b028005a4858fdac845db406aefb181',
               'files': ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'pytorch_model.bin', 'README.md']},
    'aigc': {'repo': 'yuchuantian/AIGC_detector_zhv3short', 'revision': '7bf6e1d6496353a88365f1dcdb3a6ace35f46b39',
             'files': ['config.json', 'tokenizer_config.json', 'special_tokens_map.json', 'vocab.txt', 'pytorch_model.bin', 'README.md']},
}

def fetch(key, filename):
    meta = MODELS[key]
    folder = CACHE / key
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if target.exists() and target.stat().st_size:
        return {'model': key, 'file': filename, 'bytes': target.stat().st_size}
    part = target.with_name(target.name + '.part')
    for attempt in range(5):
        try:
            offset = part.stat().st_size if part.exists() else 0
            url = f"https://huggingface.co/{meta['repo']}/resolve/{meta['revision']}/{filename}"
            with requests.get(url, params={'download': 'true', 'task_retry': str(attempt)},
                              headers={'Range': f'bytes={offset}-'} if offset else {}, stream=True,
                              timeout=(30, 90)) as response:
                response.raise_for_status()
                append = offset > 0 and response.status_code == 206
                expected = int(response.headers.get('Content-Length', 0))
                received = 0
                with part.open('ab' if append else 'wb') as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            stream.write(chunk)
                            received += len(chunk)
                if expected and received != expected:
                    raise IOError(f'Incomplete: {received}/{expected}')
            part.replace(target)
            print(f"downloaded {key}/{filename}: {target.stat().st_size:,} bytes", flush=True)
            return {'model': key, 'file': filename, 'bytes': target.stat().st_size}
        except Exception as exc:
            print(f'{key}/{filename} retry {attempt + 1}: {type(exc).__name__}: {str(exc)[:150]}', flush=True)
            if attempt == 4:
                raise
            time.sleep(2)

if __name__ == '__main__':
    tasks = [(key, filename) for key, model in MODELS.items() for filename in model['files']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda item: fetch(*item), tasks))
    for item in results:
        path = CACHE / item['model'] / item['file']
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
        item['sha256'] = digest.hexdigest()
    (CACHE / 'manifest.json').write_text(json.dumps({'models': MODELS, 'files': results}, ensure_ascii=False, indent=2), encoding='utf-8')
    # Save the official label mapping and decision rule used by the detector demo.
    demo = requests.get('https://huggingface.co/spaces/yuchuantian/AIGC_text_detector/raw/main/app.py', timeout=30)
    demo.raise_for_status()
    (CACHE / 'aigc' / 'official_demo.py.txt').write_text(demo.text, encoding='utf-8')
    print('Pinned model manifest complete.', flush=True)
