"""按红果平台系列号合并；作品ID为系列号-季号，未标季和编号候选另标。"""
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from 作品匹配 import cn_number, parse_title, normalize
from 持续补采 import ROOT, OUT as COLLECT

BASE = ROOT / 'data/红果400条交付'
OUT = BASE / '系列合并'
UNKNOWN_PRODUCERS = {'待认领', '待确认', '待核实', '未知', '不详'}


def save(name, rows):
    (OUT / (name + '.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                     for k, v in r.items()} for r in rows)


def temporary_id(key):
    return 'TMP_' + hashlib.sha256(key.encode()).hexdigest()[:16]


def season_info(title, group_titles):
    parsed = parse_title(title)
    if parsed['season_number'] and parsed['installment_unit'] == '季':
        return parsed['base_title'], parsed['season_number'], f'S{parsed["season_number"]:02d}', '剧名明确标季'
    # 标季后还有副标题的情况，例如“第六季：……大结局篇”。
    matches = list(re.finditer(r'第([0-9零〇一二三四五六七八九十百千两]+)季', unicodedata.normalize('NFKC', title)))
    if len(matches) == 1:
        match = matches[0]
        number = cn_number(match[1])
        base = title[:match.start()].rstrip(' ：:，,·—-!！ ')
        return base, number, f'S{number:02d}', '剧名明确标季，季号后附副标题'
    # 数字只是续作编号候选，不能悄悄升级为平台确认季数。
    tail = re.fullmatch(r'(.+?)([0-9]{1,3})', title)
    if tail:
        prefix, number = tail[1], int(tail[2])
        siblings = [x for x in group_titles if x == prefix or re.fullmatch(re.escape(prefix) + r'[0-9]{1,3}', x)]
        if len(set(siblings)) >= 2:
            return prefix, '', f'N{number:02d}', '同平台系列组、同名前缀及标题数字对应；仅续作编号候选，季数待核'
    fox = re.fullmatch(r'(御狐)([0-9]{1,3})(.+)', title)
    if fox and sum(bool(re.fullmatch(r'御狐[0-9]{1,3}.+', x)) for x in set(group_titles)) >= 2:
        return fox[1], '', f'N{int(fox[2]):02d}', '同平台系列组标题为御狐2/御狐3加副标题；仅续作编号候选，季数待核'
    return title, '', 'SU', '未明确标季；SU表示未知，不默认第一季'


def main():
    OUT.mkdir(exist_ok=True)
    ranks = json.loads((BASE / '红果400条_简介封面总表.json').read_text())
    material_rows = json.loads((BASE / '简介封面材料明细.json').read_text())
    materials = {r['material_id']: r for r in material_rows}
    selected = {r['material_id']: r for r in material_rows if r['selected_for_row']}
    group_titles = defaultdict(set)
    for m in materials.values():
        if m.get('platform_group_id'):
            group_titles[m['platform_group_id']].add(m.get('title', m['ranking_title']))
    # 全目录只帮助识别同系列数字标题的编号形式，不把样本外作品加入样本。
    for line in (ROOT / 'data/红果简介封面/补采/公开作品元数据索引.jsonl').read_text().splitlines():
        m = json.loads(line)
        if m.get('platform_group_id') in group_titles:
            group_titles[m['platform_group_id']].add(m['title'])
    workmap, assignments, work_rows = {}, [], []
    for rank in ranks:
        key = rank['selected_material_id'] or 'AMB_' + rank['ranking_id']
        if key not in workmap:
            m = materials.get(key, {})
            group = m.get('platform_group_id', '')
            title = m.get('title', rank['title_raw'])
            series = 'HG_' + group if group else temporary_id(key)
            base, number, code, status = season_info(title, group_titles.get(group, []))
            record = {'work_id': series + '-' + code, 'series_id': series,
                      'platform_group_id': group, 'platform_work_id': m.get('platform_work_id', ''),
                      'season_number': number, 'season_code': code, 'season_status': status,
                      'series_title': base, 'title': title, 'ranking_titles': [],
                      'series_basis': '平台series_group_id一致' if group else
                                      '版本未定占位，未与其他系列合并' if not m else '缺平台系列号，暂按作品独立占位',
                      'identity_status': rank['identity_status'],
                      'material_ids': rank['material_ids'],
                      'selected_material_id': rank['selected_material_id'],
                      'description': rank['description'],
                      'cover_file': str(Path('..') / rank['cover_file']) if rank['cover_file'] else '',
                      'description_source_url': rank['description_source_url'],
                      'group_evidence_url': m.get('source_url', '') if group else '',
                      'group_evidence_file': m.get('source_file', '') if group else '',
                      'group_evidence_sha256': m.get('source_sha256', '') if group else '',
                      'ranking_ids': [], 'months': [], 'producer_labels_as_listed': [],
                      'maker_rights_labels_as_listed': [], 'candidate_series_ids_by_title': []}
            workmap[key] = record
            work_rows.append(record)
        w = workmap[key]
        for field, value in [('ranking_ids', rank['ranking_id']), ('months', rank['month']),
                             ('ranking_titles', rank['title_raw']), ('producer_labels_as_listed', rank['producer_raw']),
                             ('maker_rights_labels_as_listed', rank['maker_rights_raw'])]:
            if value and value not in w[field]:
                w[field].append(value)
        assignments.append({**rank, 'previous_work_id': rank.get('work_id', ''),
                            'work_id': w['work_id'], 'series_id': w['series_id'],
                            'platform_group_id': w['platform_group_id'], 'season_number': w['season_number'],
                            'season_code': w['season_code'], 'season_status': w['season_status'],
                            'series_basis': w['series_basis'],
                            'cover_file': w['cover_file']})
    # 不存在系列号-季号碰撞才可作为作品主键。
    counts = Counter(w['work_id'] for w in work_rows)
    collisions = [w for w in work_rows if counts[w['work_id']] > 1]
    if collisions:
        save('主键冲突待核', collisions)
        raise ValueError('系列号-季号发生碰撞；已保留冲突，不覆盖作品')
    official_names = defaultdict(set)
    for w in work_rows:
        if w['platform_group_id']:
            official_names[normalize(w['series_title'])].add(w['series_id'])
    for w in work_rows:
        if not w['platform_group_id']:
            w['candidate_series_ids_by_title'] = sorted(official_names.get(normalize(w['series_title']), []))
    # 原著边沿用稳定ranking_id连接，不靠文字相似度再次拼接。
    existing_books = json.loads((COLLECT / '月榜_原著_作者关系候选.json').read_text())
    assigned = {r['ranking_id']: r for r in assignments}
    book_edges = [{**r, 'series_id': assigned[r['ranking_id']]['series_id'],
                   'work_id': assigned[r['ranking_id']]['work_id'],
                   'season_code': assigned[r['ranking_id']]['season_code']}
                  for r in existing_books if r['ranking_id'] in assigned]
    book_by_series = defaultdict(list)
    for r in book_edges:
        book_by_series[r['series_id']].append(r)
    grouped = defaultdict(list)
    for w in work_rows:
        grouped[w['series_id']].append(w)
    series_rows, producer_edges = [], []
    for series, ww in grouped.items():
        ranking_ids = [rid for w in ww for rid in w['ranking_ids']]
        rr = [assigned[rid] for rid in ranking_ids]
        producers = sorted({r['producer_raw'] for r in rr if r['producer_raw'] and r['producer_raw'] not in UNKNOWN_PRODUCERS})
        edges = book_by_series.get(series, [])
        series_rows.append({'series_id': series, 'platform_group_id': ww[0]['platform_group_id'],
                            'series_title': Counter(w['series_title'] for w in ww).most_common(1)[0][0],
                            'series_basis': ww[0]['series_basis'], 'work_count': len(ww),
                            'ranking_count': len(rr), 'work_ids': [w['work_id'] for w in ww],
                            'season_codes': [w['season_code'] for w in ww],
                            'titles': [w['title'] for w in ww], 'ranking_ids': ranking_ids,
                            'months': sorted({r['month'] for r in rr}),
                            'producer_labels_as_listed': producers,
                            'producer_status': '多个署名，需核实别名/合作方/识别差异' if len(producers) > 1 else
                                               '榜单有具名署名，企业主体待核' if producers else '署名待认领或缺失',
                            'candidate_book_ids': sorted({r['book_id_candidate'] for r in edges}),
                            'official_book_ids': sorted({r['book_id_candidate'] for r in edges if r.get('official_book_url')}),
                            'official_author_ids': sorted({r['official_author_id'] for r in edges if r.get('official_author_id')}),
                            'adaptation_status': '有第三方线索，具体改编关系仍待确认' if edges else '尚无原著关系线索；不能据此判原创'})
        for r in rr:
            producer_edges.append({'series_id': series, 'work_id': r['work_id'], 'season_code': r['season_code'],
                                   'ranking_id': r['ranking_id'], 'month': r['month'], 'title': r['title_raw'],
                                   'producer_label_as_listed': r['producer_raw'],
                                   'maker_rights_label_as_listed': r['maker_rights_raw'],
                                   'source_url': r['source_url'], 'source_image': r['source_image'],
                                   'review_status': r['review_status'],
                                   'entity_resolution_status': '榜单署名原文，未将相似名称自动合并为同一企业'})
    monthly = []
    for month in sorted({r['month'] for r in assignments}):
        rr = [r for r in assignments if r['month'] == month]
        monthly.append({'month': month, 'ranking_rows': len(rr), 'work_count': len({r['work_id'] for r in rr}),
                        'known_platform_series': len({r['series_id'] for r in rr if r['platform_group_id']}),
                        'pending_series_units': len({r['series_id'] for r in rr if not r['platform_group_id']}),
                        'provisional_series_units': len({r['series_id'] for r in rr})})
    save('系列汇总', sorted(series_rows, key=lambda r: (-r['ranking_count'], r['series_id'])))
    save('季作品表', work_rows)
    save('上榜记录_系列季映射', assignments)
    save('出品署名_系列季关系', producer_edges)
    save('原著作者_系列季候选关系', book_edges)
    cover_links = []
    for m in material_rows:
        rank = assigned[m['ranking_id']]
        cover_links.append({'series_id': rank['series_id'], 'work_id': rank['work_id'],
                            'season_code': rank['season_code'], 'season_status': rank['season_status'],
                            'ranking_id': m['ranking_id'], 'month': m['month'], 'rank': int(m['rank']),
                            'ranking_title': m['ranking_title'], 'material_id': m['material_id'],
                            'platform_work_id': m.get('platform_work_id', ''),
                            'material_platform_group_id': m.get('platform_group_id', ''),
                            'selected_for_row': m['selected_for_row'], 'source_kind': m['source_kind'],
                            'cover_file': str(Path('..') / m['cover_file']),
                            'cover_url': m['cover_url'], 'cover_sha256': m['cover_sha256'],
                            'source_url': m['source_url'],
                            'relation_note': '同名未定候选版本，仅挂到待核单元，不据此确认榜单版本'
                                             if not m['selected_for_row'] else rank['series_basis']})
    save('封面_系列季对应', cover_links)
    save('各月合并统计', monthly)
    save('系列季号待核', [w for w in work_rows if not w['platform_group_id'] or not w['season_number']])
    # 独立保存的关系证据作为增补，不改变原有候选表和作品/系列主键。
    relation_dir = BASE / '关系核实'
    if (relation_dir / '系列_原著作者关系.json').exists():
        rels = json.loads((relation_dir / '系列_原著作者关系.json').read_text())
        for s in series_rows:
            rr = [r for r in rels if r['series_id'] == s['series_id']]
            s['book_ids_after_relationship_verification'] = sorted({r['book_id'] for r in rr})
            s['adaptation_evidence_ids'] = sorted({eid for r in rr for eid in r['direct_evidence_ids']})
            if s['adaptation_evidence_ids']:
                s['adaptation_status'] = '有公开改编关系证据；系列/具体季及A/B层级见关系核实/改编证据登记'
        save('系列汇总', sorted(series_rows, key=lambda r: (-r['ranking_count'], r['series_id'])))
    known = [r for r in series_rows if r['platform_group_id']]
    stats = {'generated_at': datetime.now(timezone.utc).isoformat(), 'ranking_rows': len(assignments),
             'work_candidates': len(work_rows), 'known_platform_series': len(known),
             'works_in_known_platform_series': sum(r['work_count'] for r in known),
             'known_series_with_multiple_sample_works': sum(r['work_count'] > 1 for r in known),
             'pending_series_units': len(series_rows) - len(known),
             'provisional_series_units': len(series_rows),
             'explicit_season_works': sum(bool(w['season_number']) for w in work_rows),
             'numbered_title_candidates': sum(w['season_code'].startswith('N') for w in work_rows),
             'unknown_season_works': sum(w['season_code'] == 'SU' for w in work_rows),
             'ranking_rows_with_named_producer': sum(bool(r['producer_raw']) and r['producer_raw'] not in UNKNOWN_PRODUCERS for r in assignments),
             'ranking_rows_producer_pending': sum(r['producer_raw'] == '待认领' for r in assignments),
             'ranking_rows_producer_unconfirmed': sum(r['producer_raw'] in UNKNOWN_PRODUCERS - {'待认领'} for r in assignments),
             'ranking_rows_producer_missing': sum(not r['producer_raw'] for r in assignments),
             'book_candidate_ranking_rows': len({r['ranking_id'] for r in book_edges}),
             'book_candidate_series_units': len(book_by_series),
             'distinct_candidate_books': len({r['book_id_candidate'] for r in book_edges}),
             'distinct_official_books': len({r['book_id_candidate'] for r in book_edges if r.get('official_book_url')}),
             'distinct_official_authors': len({r['official_author_id'] for r in book_edges if r.get('official_author_id')}),
             'official_book_linked_ranking_rows': len({r['ranking_id'] for r in book_edges if r.get('official_book_url')}),
             'adaptation_evidence_note': '改编证据由关系核实脚本独立维护，见latest_relationship_verification；本基础候选统计不代表核实结论',
             'limits': '平台系列号相同才正式合并；27个缺号/版本未定单元暂独立，不声称独立故事共196个。分季ID为项目ID，平台作品ID另存。原著与出品方关系仍保留证据层级及OCR状态。'}
    (OUT / '统计.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    if (relation_dir / '核实统计.json').exists():
        stats['latest_relationship_verification'] = json.loads((relation_dir / '核实统计.json').read_text())
        (OUT / '统计.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    assert len(assignments) == 400 and len({r['ranking_id'] for r in assignments}) == 400
    assert len(work_rows) == len({r['work_id'] for r in work_rows})
    assert sum(s['ranking_count'] for s in series_rows) == 400
    assert all(r['work_id'] == r['series_id'] + '-' + r['season_code'] for r in assignments)
    assert all((ROOT / w['group_evidence_file']).exists() and
               hashlib.sha256((ROOT / w['group_evidence_file']).read_bytes()).hexdigest() == w['group_evidence_sha256']
               for w in work_rows if w['platform_group_id'])
    for r in assignments:
        assert r['material_ids'] == next(x['material_ids'] for x in ranks if x['ranking_id'] == r['ranking_id'])
        if r['cover_file']:
            assert (OUT / r['cover_file']).exists()
    lines = ['# 红果系列合并及系列号—季号ID', '',
             f'400条上榜记录，368部作品候选。平台系列号已合并为{len(known)}个系列；另{len(series_rows)-len(known)}个缺号或版本未定单元暂独立。总计{len(series_rows)}个统计单元，不等于已核实的独立故事数。', '',
             '## ID规则', '',
             '- 系列ID：`HG_平台series_group_id`。缺号采用稳定的`TMP_哈希`项目占位号，不伪造平台系列号。',
             '- 作品ID：`系列ID-季号代码`，例如`HG_7624475539960499262-S09`。平台原作品编号另存platform_work_id。',
             '- `S02`表示剧名明确写第二季；`N02`表示标题数字为续作编号候选，季数未确认；`SU`表示未标季，不自动当第一季。',
             '- 相同系列ID合并统计，各季作品、简介、封面和月榜记录仍分别保留；没有合成一份“系列简介”或任意选一张系列封面。',
             '- 缺系列号但剧名相近的关系只写candidate_series_ids_by_title，不据此强制合并。', '',
             '## 文件', '',
             '- 系列汇总：每个系列/待核单元一行，列出所含作品、各季、月份、出品署名和原著候选。',
             '- 季作品表：每部作品候选一行，用新work_id连接材料与上榜记录。',
             '- 上榜记录_系列季映射：400条全部保留，每条写入新work_id和series_id。',
             '- 出品署名_系列季关系：原榜署名逐行对应，不把“出品方、制作方/版权方”混为一列。',
             '- 原著作者_系列季候选关系：只保留红果，以ranking_id关联到新ID；官方书页已核实不等于改编关系已确认。',
             '- 封面_系列季对应：401条材料关联到400条榜单及新系列季ID；同名未定作品的两个版本保留各自材料编号。',
             '- 系列季号待核：缺号、未标季及只有数字编号的条目。', '',
             'cover_file相对于本目录；证据source_file/group_evidence_file相对于dataprocessing目录。原材料表与原平台ID没有被覆盖。', '',
             '## 红果还可继续挖掘', '',
             f'- 出品方：{stats["ranking_rows_with_named_producer"]}条有具名榜单署名，{stats["ranking_rows_producer_pending"]}条待认领，{stats["ranking_rows_producer_unconfirmed"]}条待确认/待核，{stats["ranking_rows_producer_missing"]}条为空。后续核实企业/账号主体、名称别名和合作关系，再统计系列集中度。',
             f'- 原著基础候选：{stats["book_candidate_ranking_rows"]}条上榜记录、{stats["book_candidate_series_units"]}个系列单元、{stats["distinct_candidate_books"]}本候选书。最新补页、作者数量及改编证据层级请见../关系核实/核实统计.json与../关系核实/说明.md，不以本基础候选表作为最终覆盖数。',
             '- 先补“出品方—系列—原著—作者”关系，再分析一书多系列、同一作者反复改编、出品方题材集中、同系列续季占榜。不能把缺原著线索的作品归为原创。',
             '- 内容层仍可做：跨系列封面DINOv2相似度、简介题材/剧情结构、剧名语义、与出品方或原著的交叉比较；目前粗略dHash封面候选都在同系列内。',
             '- 评论已有20部180条正式分层样本可继续编码；与其他批次分开。抖音本阶段不处理。']
    (OUT / '说明.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
