"""Actual neural inference. Runs separately to release RAM between models.

Only this module needs torch/transformers; table export can use the bundled runtime.
"""
import argparse
import gc
import time
import numpy as np
import torch
from pathlib import Path
from PIL import Image
from transformers import AutoImageProcessor, AutoModel, AutoModelForSequenceClassification, AutoTokenizer
from common import RESULTS, ROOT, DEFAULT_SOURCE, MODEL_CACHE, load, save, sha256
from fetch_models import MODELS

torch.set_num_threads(6)
torch.manual_seed(20261112)
np.random.seed(20261112)
CACHE = MODEL_CACHE

def metadata(key, rows, extra):
    return {'model': MODELS[key]['repo'], 'revision': MODELS[key]['revision'],
            'torch': torch.__version__, 'device': 'cpu', 'seed': 20261112,
            'input_sha256': sha256(RESULTS / 'representatives.json'),
            'series_ids': [r['series_id'] for r in rows], **extra}

def cover():
    rows = [r for r in load(RESULTS / 'representatives.json') if r['modality'] == 'cover']
    folder = CACHE / 'dinov2'
    processor = AutoImageProcessor.from_pretrained(folder, local_files_only=True)
    model = AutoModel.from_pretrained(folder, local_files_only=True).eval()
    vectors = []
    start = time.time()
    with torch.inference_mode():
        for i in range(0, len(rows), 2):
            images = []
            for row in rows[i:i + 2]:
                with Image.open(row['cover_path']) as image:
                    images.append(image.convert('RGB'))
            inputs = processor(images=images, return_tensors='pt')
            features = model(**inputs).last_hidden_state[:, 0]
            vectors.append(torch.nn.functional.normalize(features, dim=1).cpu().numpy())
            if i % 20 == 0:
                print(f'cover {min(i + 2, len(rows))}/{len(rows)} {time.time() - start:.0f}s', flush=True)
    np.save(RESULTS / 'cover_embeddings.npy', np.concatenate(vectors))
    save(RESULTS / 'cover_model.json', metadata('dinov2', rows, {'processor': processor.to_dict(),
         'pooling': 'last_hidden_state CLS token, L2 normalization', 'elapsed_seconds': round(time.time() - start, 2)}))

def text():
    folder = CACHE / 'bge_m3'
    tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True)
    model = AutoModel.from_pretrained(folder, local_files_only=True).eval()
    all_rows = load(RESULTS / 'representatives.json')
    for modality, field in [('title', 'title_core'), ('description', 'description')]:
        rows = [r for r in all_rows if r['modality'] == modality]
        vectors, lengths = [], []
        start = time.time()
        with torch.inference_mode():
            for i in range(0, len(rows), 4):
                texts = [r[field] for r in rows[i:i + 4]]
                token_lengths = [len(tokenizer.encode(t, add_special_tokens=True)) for t in texts]
                assert max(token_lengths) <= 8192, 'Text exceeds the model context; do not silently truncate'
                lengths.extend(token_lengths)
                inputs = tokenizer(texts, padding=True, truncation=False, return_tensors='pt')
                features = model(**inputs).last_hidden_state[:, 0]
                vectors.append(torch.nn.functional.normalize(features, dim=1).cpu().numpy())
                if i % 20 == 0:
                    print(f'{modality} {min(i + 4, len(rows))}/{len(rows)} {time.time() - start:.0f}s', flush=True)
        np.save(RESULTS / f'{modality}_embeddings.npy', np.concatenate(vectors))
        save(RESULTS / f'{modality}_model.json', metadata('bge_m3', rows, {'pooling': 'CLS dense embedding, L2 normalization; no query instruction',
              'token_lengths': lengths, 'truncated_texts': 0, 'elapsed_seconds': round(time.time() - start, 2)}))

def aigc(source=DEFAULT_SOURCE):
    folder = CACHE / 'aigc'
    tokenizer = AutoTokenizer.from_pretrained(folder, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(folder, local_files_only=True).eval()
    rows = [dict(r, sample_kind='series_description', sample_id=r['series_id'], text=r['description'])
            for r in load(RESULTS / 'representatives.json') if r['modality'] == 'description']
    books = load(Path(source) / '红果400条交付/关系核实/红果原著官方书目.json')
    rows += [{'sample_kind': 'book_reference', 'sample_id': r['book_id'], 'text': r.get('official_description', ''),
              'book_title': r['official_book_title'], 'source_url': r['source_url']} for r in books]
    output = []
    for row in rows:
        tokens = tokenizer(row['text'], add_special_tokens=True, truncation=False)
        n = len(tokens['input_ids'])
        record = {k: row.get(k) for k in ['sample_kind', 'sample_id', 'series_id', 'book_title', 'source_url', 'ai_status']}
        record.update({'char_count': len(row['text']), 'token_count': n, 'text_sha256': __import__('hashlib').sha256(row['text'].encode()).hexdigest(),
                       'score_ai': None, 'predicted_label': None, 'raw_logits': None, 'status': '未计算'})
        if not row['text'].strip():
            record.update(status='文本缺失')
        elif n > 512:
            record.update(status='超过512 token；主分析排除，未截断')
        else:
            with torch.inference_mode():
                inputs = tokenizer(row['text'], return_tensors='pt', truncation=False)
                logits = model(**inputs).logits[0]
                probabilities = logits.softmax(dim=0).cpu().numpy()
                record.update(score_ai=float(probabilities[1]), raw_logits=logits.cpu().numpy().tolist(),
                              predicted_label='AI' if int(probabilities.argmax()) == 1 else '人类', status='仅供探索')
        output.append(record)
        if len(output) % 25 == 0:
            print(f'aigc {len(output)}/{len(rows)}', flush=True)
    save(RESULTS / 'aigc_scores.json', output)
    save(RESULTS / 'aigc_model.json', metadata('aigc', [], {
        'official_demo_url': 'https://huggingface.co/spaces/yuchuantian/AIGC_text_detector/blob/main/app.py',
        'official_demo_sha256': sha256(folder / 'official_demo.py.txt'),
        'score_definition': 'softmax(logits)[1], official demo class order [人类, AI]',
        'decision_rule': 'official demo argmax of the two logits; tie goes to class 0',
        'max_tokens_including_special_tokens': 512, 'truncated_texts': 0,
        'limits': '无本项目真实作者标签，无法测准确率或校准概率；模型分数不能确定作者或视频AI制作。',
    }))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['cover', 'text', 'aigc'])
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    {'cover': cover, 'text': text, 'aigc': lambda: aigc(args.source)}[args.mode]()
