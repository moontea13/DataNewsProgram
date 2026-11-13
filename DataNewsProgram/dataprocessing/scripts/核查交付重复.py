"""对统一交付材料查重，并将图片内容、作品版本、月榜记录逐层关联。"""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from 红果简介封面查重 import cover_features
from 持续补采 import ROOT

DEST = ROOT / 'data/红果400条交付'
OUT = DEST / '重复核查'


def save(name, rows, fields=None):
    (OUT / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                    for k, v in r.items()} for r in rows)


def main():
    OUT.mkdir(exist_ok=True)
    rows = json.loads((DEST / '红果400条_简介封面总表.json').read_text())
    materials = json.loads((DEST / '简介封面材料明细.json').read_text())
    unique, links = {}, defaultdict(list)
    for r in materials:
        mid = r['material_id']
        if mid in unique:
            assert unique[mid]['cover_sha256'] == r['cover_sha256']
        unique[mid] = r
        links[mid].append(r)
    features, image_groups, byte_groups = {}, defaultdict(list), defaultdict(list)
    for mid, m in unique.items():
        path = DEST / m['cover_file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == m['cover_sha256']
        features[mid] = cover_features(path)
        image_groups[features[mid]['pixel_sha256']].append(mid)
        byte_groups[m['cover_sha256']].append(mid)
    def group_id(mid):
        return 'IMG_' + features[mid]['pixel_sha256']

    repeated = []
    selected = defaultdict(list)
    for r in rows:
        if r['selected_material_id']:
            selected[r['selected_material_id']].append(r)
    for mid, rr in selected.items():
        if len(rr) > 1:
            repeated.append({'material_id': mid, 'platform_work_id': unique[mid].get('platform_work_id', ''),
                             'title': unique[mid].get('title', unique[mid]['ranking_title']),
                             'ranking_count': len(rr), 'extra_ranking_rows': len(rr) - 1,
                             'ranking_ids': [r['ranking_id'] for r in rr],
                             'months': sorted({r['month'] for r in rr}),
                             'cover_file': str(Path('..') / unique[mid]['cover_file']),
                             'cover_image_group': group_id(mid),
                             'identity_status': unique[mid].get('identity_status', '')})
    repeated.sort(key=lambda r: (-r['ranking_count'], r['material_id']))
    save('同作品重复上榜对应', repeated)

    cover_links = []
    for m in materials:
        mid = m['material_id']
        cover_links.append({'cover_image_group': group_id(mid), 'material_id': mid,
                            'platform_work_id': m.get('platform_work_id', ''),
                            'title': m.get('title', m['ranking_title']),
                            'ranking_title': m['ranking_title'], 'ranking_id': m['ranking_id'],
                            'month': m['month'], 'rank': int(m['rank']),
                            'selected_for_row': m['selected_for_row'],
                            'source_kind': m['source_kind'],
                            'cover_file': str(Path('..') / m['cover_file']),
                            'cover_url': m['cover_url'], 'cover_sha256': m['cover_sha256'],
                            'pixel_sha256': features[mid]['pixel_sha256'],
                            'same_pixel_material_count': len(image_groups[features[mid]['pixel_sha256']]),
                            'work_source_url': m['source_url']})
    save('封面到作品和榜单对应', cover_links)

    exact = []
    for pixel_sha, ids in image_groups.items():
        if len(ids) < 2:
            continue
        rank_links = [r for mid in ids for r in links[mid]]
        exact.append({'cover_image_group': 'IMG_' + pixel_sha, 'material_count': len(ids),
                      'material_ids': ids,
                      'platform_work_ids': [unique[mid].get('platform_work_id', '') for mid in ids],
                      'titles': [unique[mid].get('title', unique[mid]['ranking_title']) for mid in ids],
                      'cover_files': [str(Path('..') / unique[mid]['cover_file']) for mid in ids],
                      'ranking_ids': [r['ranking_id'] for r in rank_links],
                      'months': sorted({r['month'] for r in rank_links}),
                      'group_ids': sorted({unique[mid].get('platform_group_id', '') for mid in ids}),
                      'reason': '解码并校正EXIF方向后的RGB尺寸和全部像素完全一致；不代表不同季是同一部作品'})
    save('不同作品共用同图分组', exact)

    near = []
    for a, b in combinations(unique, 2):
        fa, fb = features[a], features[b]
        distance = (fa['dhash'] ^ fb['dhash']).bit_count()
        same_pixel = fa['pixel_sha256'] == fb['pixel_sha256']
        if distance > 6 or min(fa['grayscale_stdev'], fb['grayscale_stdev']) <= 5:
            continue
        ma, mb = unique[a], unique[b]
        ga, gb = ma.get('platform_group_id', ''), mb.get('platform_group_id', '')
        near.append({'material_id_a': a, 'title_a': ma.get('title', ma['ranking_title']),
                     'material_id_b': b, 'title_b': mb.get('title', mb['ranking_title']),
                     'cover_file_a': str(Path('..') / ma['cover_file']),
                     'cover_file_b': str(Path('..') / mb['cover_file']),
                     'ranking_ids_a': [r['ranking_id'] for r in links[a]],
                     'ranking_ids_b': [r['ranking_id'] for r in links[b]],
                     'cover_pixel_exact': same_pixel, 'dhash_distance': distance,
                     'series_relation': '相同平台系列组' if ga and gb and ga == gb else
                                        '不同平台系列组' if ga and gb else '系列组待核',
                     'includes_unselected_version': not ma['selected_for_row'] or not mb['selected_for_row'],
                     'review_status': '像素相同已机械核实' if same_pixel else '粗略相似候选，待人工看图；不是同质化结论'})
    save('不同作品封面相似候选', near)
    summary = {'generated_at': datetime.now(timezone.utc).isoformat(),
               'scope': '红果2026年7—10月，不同季分别计作品候选；尚有5条来源及1条版本待核',
               'ranking_rows': len(rows),
               'single_selected_work_candidates': len(selected),
               'unresolved_ranking_rows_with_multiple_versions': sum(not r['selected_material_id'] for r in rows),
               'provisional_work_count_treating_unresolved_row_as_one': len(selected) + sum(not r['selected_material_id'] for r in rows),
               'repeated_work_candidates': len(repeated),
               'ranking_rows_of_repeated_work_candidates': sum(r['ranking_count'] for r in repeated),
               'extra_ranking_rows': sum(r['extra_ranking_rows'] for r in repeated),
               'cover_material_files': len(unique), 'unique_file_contents': len(byte_groups),
               'unique_decoded_images': len(image_groups),
               'exact_same_image_groups_across_materials': len(exact),
               'materials_using_exact_same_image': sum(r['material_count'] for r in exact),
               'extra_material_files_with_same_pixels': sum(r['material_count'] - 1 for r in exact),
               'exact_image_pairs': sum(r['cover_pixel_exact'] for r in near),
               'dhash_similar_but_not_pixel_equal_pairs': sum(not r['cover_pixel_exact'] for r in near),
               'dhash_threshold': 6,
               'note': '369份按作品候选版本保留的封面文件，内容去重为366张图。多出的一个候选版本来自同名未定作品。跨月重复上榜、同系列不同季、同图和近似图分别记录。相似候选尚未用DINOv2分析或逐对人工确认。'}
    (OUT / '查重统计.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    assert len(cover_links) == len(materials)
    assert {r['ranking_id'] for r in cover_links} == {r['ranking_id'] for r in rows}
    assert sum(r['extra_ranking_rows'] for r in repeated) == sum(r['material_count'] == 1 for r in rows) - len(selected)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
