"""Shared, file-based interfaces for the red-fruit news experiment."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent


def configured_path(name, default):
    """Resolve relative settings against the repository, not the invoking shell."""
    path = Path(os.environ.get(name) or default).expanduser()
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


WORKSPACE = PROJECT_ROOT  # Compatibility for modules which only need the project root.
DEFAULT_SOURCE = configured_path('HONGGUO_SOURCE', 'dataprocessing/data')
DEFAULT_OUTPUT = configured_path('HONGGUO_OUTPUT', 'outputs/part1-3')
STYLE_OUTPUT = configured_path('HONGGUO_STYLE_OUTPUT', 'outputs/style')
RESULTS = configured_path('HONGGUO_RESULTS', 'analysis/results')
MODEL_CACHE = configured_path('HONGGUO_MODEL_CACHE', 'analysis/.cache/models')
OCR_RUNTIME = configured_path('HONGGUO_OCR_RUNTIME', 'analysis/.cache/style_runtime')
THRESHOLDS = [0.80, 0.85, 0.90]
MONTHS = ['2026-07', '2026-08', '2026-09', '2026-10']
WARNINGS = [
    '样本为2026年7—10月红果月榜，不能代表全部短剧。',
    '确认平台系列归组不等于确认历史榜单版本或独立故事；部分身份仍待核。',
    '简介、封面为采集时材料，不代表上榜当月版本；模型高相似只表示候选。',
    '全榜包含AI制作证据不足的作品，不能将全榜结果表述为已确认AI作品结果。',
]

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(encoded + '\n', encoding='utf-8')
    temporary.replace(path)

def csv_save(path, rows, fields=None):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or ['status'])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def ratio(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'percent': round(100 * numerator / denominator, 4) if denominator else None}

def quantiles(values):
    values = sorted(float(x) for x in values if x is not None and math.isfinite(float(x)))
    def q(p):
        if not values:
            return None
        idx = (len(values) - 1) * p
        lo, hi = int(idx), min(int(idx) + 1, len(values) - 1)
        return round(values[lo] * (hi - idx) + values[hi] * (idx - lo), 7) if hi != lo else round(values[lo], 7)
    return {'n': len(values), 'min': q(0), 'q25': q(.25), 'median': q(.5), 'q75': q(.75), 'max': q(1)}

def envelope(id_, title, data, unit='个系列', denominator_definition='', method='', sources=None, limits=None, status='可展示', chart='bar'):
    return {'id': id_, 'title': title, 'unit': unit, 'scope': '2026年7—10月红果月榜400条记录',
            'status': status, 'chart': chart, 'denominator_definition': denominator_definition,
            'method': method, 'data': data, 'sources': sources or [], 'limits': limits or []}
