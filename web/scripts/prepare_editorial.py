"""将联合交付包中已核对的数据冻结为前三章的展示数据。

python scripts/prepare_editorial.py --delivery /path/to/红果数据新闻_联合交付版
不重跑模型，也不修改第四、五章的原始快照。
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delivery', required=True, type=Path)
    args = parser.parse_args()
    data_dir = args.delivery / 'data'
    manifest = []

    def read(name):
        path = data_dir / (name + '.json')
        raw = path.read_bytes()
        manifest.append({'file': 'data/' + name + '.json', 'sha256': hashlib.sha256(raw).hexdigest()})
        return json.loads(raw)

    structure = read('structure')
    series = read('series')
    producers = read('producers')
    adaptations = read('adaptations')
    sequels = read('sequels')
    style = {name: read('style/' + name) for name in ['cover_layout', 'cover_models', 'title_style']}
    gallery = json.loads((ROOT / 'public/data/gallery.json').read_text('utf-8'))
    gallery_ids = {r['series_id'] for r in gallery}
    members = {sid for c in structure['clusters'] for sid in c['members']}
    semantic = [r['semantic'] for r in series if r['series_id'] in members]
    assert len(members) == structure['valid_series'] == len(semantic)
    assert members <= gallery_ids
    assert all(r['main_included'] for r in semantic)
    result = {
        'version': '2026-11-14-editorial-v1',
        'structure': {k: structure[k] for k in ['valid_series', 'cluster_count', 'repeated_cluster_coverage', 'top3_mechanisms', 'top3_union', 'distributions', 'excluded_missing', 'excluded_identity']},
        'clusters': structure['clusters'],
        'semantic': semantic,
        'producer_concentration': producers['concentration'],
        'adaptation_evidence': adaptations['evidence_details'],
        'source_manifest': manifest,
        'limits': '简介共同核心的自动归类，不是正片故事相同率；未测量人工标注准确率。第四、五章保留原分支探索快照。',
    }
    (ROOT / 'public/data/editorial.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    # 同步有修订的数据；封面与标题结果保持原有阈值和计算方法。
    for name, obj in [('producers', producers), ('adaptations', adaptations), ('sequels', sequels), *style.items()]:
        (ROOT / 'public/data' / (name + '.json')).write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), 'utf-8')
    print(f'已冻结 {len(semantic)} 个结构样本、{len(structure["clusters"])} 个分组及来源证据。')


if __name__ == '__main__':
    main()
