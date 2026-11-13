import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
import unicodedata
from PIL import Image, ImageOps
from common import ROOT, DEFAULT_SOURCE, DEFAULT_OUTPUT, RESULTS, load, save, csv_save, sha256

CHOICE = '合格材料中全期最好榜次→最早月份→稳定作品ID→上榜记录ID；每项实验每系列一个固定代表版本'

def title_core(title, season_code):
    title = unicodedata.normalize('NFKC', title)
    if season_code and re.fullmatch(r'S\d+', season_code):
        title = re.sub(r'第[零〇一二两三四五六七八九十百千\d]+季', '', title)
    return re.sub(r'[\s，。！？、：；“”‘’（）《》【】,!?\-—:;"\'()\[\]·]', '', title).casefold()

def prepare(source=DEFAULT_SOURCE, output=DEFAULT_OUTPUT):
    source, output = Path(source), Path(output)
    hg = source / '红果400条交付'
    rankings = load(hg / '系列合并/上榜记录_系列季映射.json')
    works = load(hg / '系列合并/季作品表.json')
    groups = load(hg / '系列合并/系列汇总.json')
    materials = load(hg / '简介封面材料明细.json')
    evidence = load(source / '作品匹配/AI制作逐条核实.json') if (source / '作品匹配/AI制作逐条核实.json').exists() else []
    import csv
    with (source / '交付索引/上榜记录总索引.csv').open(encoding='utf-8-sig', newline='') as stream:
        index = {r['上榜记录ID']: r for r in csv.DictReader(stream) if r['平台'] == '红果'}
    work_map = {r['work_id']: r for r in works}
    group_map = {r['series_id']: r for r in groups}
    mat_map = {(r['ranking_id'], r['material_id']): r for r in materials}
    confirmed = {r['series_id'] for r in groups if r.get('platform_group_id')}
    by_series = defaultdict(list)
    for row in rankings:
        by_series[row['series_id']].append(row)
    records, exclusions, registry, source_audit = [], [], [], []
    for sid, group in sorted(group_map.items()):
        rows = sorted(by_series[sid], key=lambda r: (int(r['rank']), r['month'], r['work_id'], r['ranking_id']))
        selected = {}
        for modality in ['title', 'cover', 'description']:
            eligible = []
            for row in rows:
                mid = row.get('selected_material_id')
                mat = mat_map.get((row['ranking_id'], mid), {})
                reasons = []
                if sid not in confirmed:
                    reasons.append('缺平台系列号或版本未定，不进入跨系列主分析')
                if row.get('material_status') == '同名多版本待判定' or not mid:
                    reasons.append('版本选择未定')
                if modality in ['description', 'cover'] and mat.get('source_kind') not in ['红果原始HTML', '红果网页工具快照']:
                    reasons.append('非红果同源候选材料')
                if modality == 'description' and not mat.get('description', '').strip():
                    reasons.append('简介缺失')
                if modality == 'cover':
                    cover = hg / mat.get('cover_file', '__missing__')
                    if not cover.is_file():
                        reasons.append('封面文件缺失')
                    else:
                        try:
                            with Image.open(cover) as im:
                                im.verify()
                        except Exception:
                            reasons.append('封面不可解码')
                if modality == 'title' and not row.get('title_raw', '').strip():
                    reasons.append('榜单标题缺失')
                if reasons:
                    exclusions.append({'series_id': sid, 'ranking_id': row['ranking_id'], 'modality': modality, 'reasons': reasons})
                else:
                    eligible.append((row, mat))
            if not eligible:
                continue
            row, mat = eligible[0]
            work = work_map[row['work_id']]
            record = {
                'series_id': sid, 'series_title': group['series_title'], 'modality': modality,
                'ranking_id': row['ranking_id'], 'work_id': row['work_id'], 'material_id': row['selected_material_id'],
                'title_raw': row['title_raw'], 'current_title': mat.get('title'),
                'title_core': title_core(row['title_raw'], work['season_code']),
                'description': mat.get('description', ''), 'season_code': work['season_code'],
                'content_type': row['content_type_raw'], 'rank': int(row['rank']), 'month': row['month'],
                'months': sorted({x['month'] for x in rows}), 'identity_status': row['identity_status'],
                'ai_status': index[row['ranking_id']]['AI制作核实状态'],
                'ai_direct_work_evidence': index[row['ranking_id']]['AI制作核实状态'] in ['有本季AI制作直接证据', '有本作品AI制作直接证据（未标季）'],
                'source_url': mat.get('source_url') or row['source_url'],
                'source_sha256': mat.get('source_sha256'), 'source_kind': mat.get('source_kind'),
                'selection_reason': CHOICE, 'cover_captured_at': mat.get('cover_captured_at'),
            }
            if modality == 'cover':
                cover = hg / mat['cover_file']
                record['cover_path'] = str(cover.resolve())
                with Image.open(cover) as im:
                    rgb = ImageOps.exif_transpose(im).convert('RGB')
                    import hashlib
                    record['pixel_sha256'] = hashlib.sha256(f'{rgb.width}x{rgb.height}'.encode() + rgb.tobytes()).hexdigest()
                    rgb.thumbnail((480, 720))
                    asset = output / 'assets' / 'covers' / f'{sid}.webp'
                    asset.parent.mkdir(parents=True, exist_ok=True)
                    rgb.save(asset, 'WEBP', quality=86)
                record['asset'] = 'assets/covers/' + sid + '.webp'
            records.append(record)
            selected[modality] = {k: v for k, v in record.items() if k not in ['cover_path']}
            if mat.get('source_file'):
                snapshot = source.parent / mat['source_file']
                actual = sha256(snapshot) if snapshot.exists() else None
                source_audit.append({'ranking_id': row['ranking_id'], 'modality': modality, 'source_file': mat['source_file'],
                                     'expected_sha256': mat.get('source_sha256'), 'actual_sha256': actual,
                                     'matches': actual is not None and actual == mat.get('source_sha256')})
        registry.append({
            'series_id': sid, 'title': group['series_title'], 'confirmed_group': sid in confirmed,
            'work_count': group['work_count'], 'ranking_count': group['ranking_count'],
            'months': sorted(group['months']), 'titles': group['titles'], 'season_codes': group['season_codes'],
            'representatives': selected,
            'ai_status_counts': dict(Counter(index[x['ranking_id']]['AI制作核实状态'] for x in rows)),
            'has_direct_ai_work_evidence': any(index[x['ranking_id']]['AI制作核实状态'] in ['有本季AI制作直接证据', '有本作品AI制作直接证据（未标季）'] for x in rows),
            'ranking_details': [{'ranking_id': r['ranking_id'], 'month': r['month'], 'rank': int(r['rank']),
                                 'title': r['title_raw'], 'work_id': r['work_id'], 'season_code': r['season_code'],
                                 'producer': r['producer_raw'], 'source_url': r['source_url']} for r in rows],
        })
    pairs = {}
    # Existing unresolved links are authoritative; exact normalized names are conservatively unresolved.
    for work in works:
        for target in work.get('candidate_series_ids_by_title', []):
            if target != work['series_id']:
                a, b = sorted([target, work['series_id']])
                pairs[(a, b)] = '原表已有待核系列关联'
    for reviewed in load(ROOT / 'identity_review.json'):
        key = tuple(sorted([reviewed['series_a'], reviewed['series_b']]))
        pairs[key] = reviewed['reason']
    titles = [r for r in records if r['modality'] == 'title']
    for i, a in enumerate(titles):
        for b in titles[i + 1:]:
            if a['title_core'] == b['title_core']:
                pairs[tuple(sorted([a['series_id'], b['series_id']]))] = '跨系列号规范标题相同，保守排除身份疑点'
    excluded_pairs = [{'series_a': a, 'series_b': b, 'reason': reason} for (a, b), reason in sorted(pairs.items())]
    # Input fingerprints make later source changes detectable.
    files = ['系列合并/上榜记录_系列季映射.json', '系列合并/季作品表.json', '系列合并/系列汇总.json', '简介封面材料明细.json']
    save(RESULTS / 'input_fingerprints.json', [{'source': '红果400条交付/' + f, 'sha256': sha256(hg / f)} for f in files])
    save(RESULTS / 'representatives.json', records)
    save(RESULTS / 'exclusions.json', exclusions)
    save(RESULTS / 'excluded_pairs.json', excluded_pairs)
    save(RESULTS / 'source_audit.json', source_audit)
    save(output / 'data/series.json', registry)
    csv_save(output / 'tables/代表版本.csv', [{k: v for k, v in r.items() if k != 'cover_path'} for r in records])
    csv_save(output / 'tables/排除记录.csv', exclusions)
    csv_save(output / 'tables/配对排除.csv', excluded_pairs)
    result = {'ranking_rows': len(rankings), 'work_candidates': len(works), 'confirmed_series': len(confirmed),
              'pending_units': len(groups) - len(confirmed), 'representatives': dict(Counter(r['modality'] for r in records)),
              'excluded_identity_pairs': len(pairs), 'source_hash_failures': sum(not r['matches'] for r in source_audit)}
    save(RESULTS / 'sample_summary.json', result)
    print(result, flush=True)
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    prepare(args.source, args.output)
