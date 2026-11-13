"""将队友的交付材料转成网页数据；不重新计算模型、不改动原交付。"""
import json
import csv
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'web'
PART = ROOT / '临时/解包/part123'
STYLE = ROOT / '临时/解包/style'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def payload(root, name):
    value = read(root / 'data' / f'{name}.json')
    return value.get('data', value) if isinstance(value, dict) else value

def write(name, value):
    target = WEB / 'public/data' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

def prepare_cover_neighbors():
    """宽阈值仅用于逐对浏览，保留原主分析标准与已排除的关联配对。"""
    variants = {'dinov2_full': [], 'dinov2_center': []}
    with (STYLE / 'tables/model_pairs.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            variant, score = row['model_variant'], float(row['score'])
            if variant in variants and score >= .60:
                variants[variant].append([row['series_a'], row['series_b'], round(score, 7)])
    summaries = {}
    for key, pairs in variants.items():
        pairs.sort(key=lambda row: (-row[2], row[0], row[1]))
        summaries[key] = []
        for threshold in [.60, .65, .70, .75, .80, .85]:
            selected = [row for row in pairs if row[2] >= threshold]
            summaries[key].append({'threshold': threshold, 'pairs':len(selected), 'series':len({sid for row in selected for sid in row[:2]})})
    features = payload(STYLE, 'cover_layout')['features']
    layouts = {row['series_id']: {'valid':row['valid_title_layout'], 'width':row['width'], 'height':row['height'], 'polygons':[box['polygon_normalized'] for box in row.get('title_boxes', [])], 'signature':row.get('layout_signature')} for row in features}
    identity = payload(STYLE, 'identity')
    write('cover_neighbors.json', {'model_labels':{'dinov2_full':'DINOv2 · 完整图补边','dinov2_center':'DINOv2 · 中心裁切'}, 'minimum_exported_threshold':.60, 'default_display_threshold':.70, 'valid_series':169, 'valid_pairs':identity['valid_pairs'], 'excluded_pairs':[[row['series_a'],row['series_b']] for row in identity['rows']], 'pairs':variants, 'summaries':summaries, 'layouts':layouts, 'note':'各相近封面均与指定参照逐对比较，不推断组内所有封面两两相似。0.70是新增探索展示阈值，原0.85主分析结果不变。'})

def main():
    remote = read(WEB / 'source-data/part45.json')
    style_series = payload(STYLE, 'series')
    genre_map = {}
    for row in payload(PART, 'series'):
        rep = row.get('representatives', {}).get('description', {})
        genre_map[row['series_id']] = rep
    series = []
    for row in style_series:
        rep = genre_map.get(row['series_id'], {})
        series.append({**row, 'months': rep.get('months', []), 'rank': rep.get('rank'), 'month': rep.get('month')})
    write('gallery.json', series)
    write('part45.json', remote)
    for name in ['story', 'sequels', 'producers', 'adaptations', 'phrases', 'aigc', 'audience', 'governance']:
        value = payload(PART, name)
        if name == 'aigc':
            value = {k: value[k] for k in ['valid_series_texts', 'score_quantiles', 'histogram', 'official_demo_ai_label_rate', 'matched_comparison']}
        write(f'{name}.json', value)
    for name in ['title_style', 'cover_models', 'cover_layout', 'cases', 'metrics']:
        value = payload(STYLE, name)
        if name == 'cover_layout':
            value = {k: v for k, v in value.items() if 'pairs' not in k}
        if name == 'cover_models':
            value['variants'] = {k: {kk: vv for kk, vv in v.items() if kk not in ['top_pairs', 'pairs', 'top3', 'top3_neighbors']} for k, v in value['variants'].items()}
        write(f'{name}.json', value)
    dest = WEB / 'public/assets/covers'
    dest.mkdir(parents=True, exist_ok=True)
    for row in series:
        src = STYLE / row['cover']
        if not src.is_file():
            raise FileNotFoundError(src)
        shutil.copy2(src, dest / src.name)
    provenance = {
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'sample': '2026年7—10月红果月榜，400条上榜记录',
        'part123': '红果新闻网页_Part1-3_交付包.zip',
        'style': '红果风格补充实验_交付包.zip',
        'part45': {'url': 'http://123.56.64.232:8088/data.js', 'version': remote['meta']['version'], 'captured_on': '2026-11-13'},
        'scope_note': '全篇196个系列；封面、剧名与早期简介规则实验沿用交付包169个固定代表材料子集；结构标注180个系列、85个全局簇。',
        'precedence': '风格补充实验的关联排除后结果优先于Part1—3旧版语义相似率；第4、5部分采用远程定稿统计。',
        'mock_data': False,
    }
    write('provenance.json', provenance)
    prepare_cover_neighbors()
    subprocess.run(['python3', str(WEB / 'scripts/prepare_cover_groups.py')], check=True)
    print(f'已导出：{len(series)}张封面；{len(remote["nodes"])}条榜位；{len(remote["clusters"])}个结构簇。')

if __name__ == '__main__':
    main()
