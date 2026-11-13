#!/usr/bin/env python3
"""只读原始采集结果，重建交付索引、导航与缺口；不联网，不改原始数据。"""
import csv
import hashlib
import json
import os
import re
from functools import cache
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

from 项目路径 import ROOT
OUT = ROOT / 'data/交付索引'
HG = 'data/红果400条交付'
INC = 'data/补采'
BASE = 'data/作品匹配/上榜记录_作品系列映射.csv'
MAP = HG + '/系列合并/上榜记录_系列季映射.csv'
MAT = HG + '/简介封面材料明细.csv'
WORK = HG + '/系列合并/季作品表.csv'
SERIES = HG + '/系列合并/系列汇总.csv'
COMMENT = HG + '/评论全覆盖/评论主表.csv'
BOOK = HG + '/关系核实/系列_原著作者关系.csv'
ADAPT = HG + '/关系核实/改编关系_400条覆盖.csv'
PRODUCER = HG + '/关系核实/出品品牌_主体_系列季关系.csv'


def read(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def arr(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [parsed]
    except (ValueError, TypeError):
        return [value]


def packed(values):
    return json.dumps(list(dict.fromkeys(v for v in values if v != '')), ensure_ascii=False)


def group(rows, key):
    result = defaultdict(list)
    for row in rows:
        result[row[key]].append(row)
    return result


def csvout(name, rows, fields=None):
    if fields is None:
        fields = list(rows[0]) if rows else ['状态']
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@cache
def localpath(value, owner):
    """source_file通常根相对，cover_file通常表所在目录相对。"""
    value = str(value).strip()
    if not value or re.match(r'^[a-z]+://', value):
        return ''
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p if value.startswith(('data/', 'scripts/')) else (ROOT / owner).parent / p
    return os.path.relpath(p.resolve(), ROOT)


@cache
def exists(path):
    return bool(path) and (ROOT / path).is_file() and (ROOT / path).stat().st_size > 0


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def link(label, path, owner='README.md', anchor=''):
    if not path or not exists(path):
        return cell(label) + '（未落盘）'
    rel = os.path.relpath(ROOT / path, (ROOT / owner).parent)
    return f'[{cell(label)}]({quote(rel, safe="/._-")}{anchor})'


@cache
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / '按月查看').mkdir(exist_ok=True)
    base = read(BASE)
    hgm = {r['ranking_id']: r for r in read(MAP)}
    materials = read(MAT)
    mats = group(materials, 'ranking_id')
    mat_unique = {r['material_id']: r for r in materials}
    works = read(WORK)
    work_by_id = {r['work_id']: r for r in works}
    series = read(SERIES)
    series_by_id = {r['series_id']: r for r in series}
    ccover_path = HG + '/评论全覆盖/上榜记录覆盖.csv'
    ccover = {r['ranking_id']: r for r in read(ccover_path)}
    cp = group(read(HG + '/评论全覆盖/作品覆盖.csv'), 'work_id')
    comments = read(COMMENT)
    comment_by_mat = group(comments, 'material_id')
    books = group(read(BOOK), 'series_id')
    adaptations = {r['ranking_id']: r for r in read(ADAPT)}
    producer = group(read(PRODUCER), 'ranking_id')
    candidates = group(base, 'candidate_work_id')
    work_rankings = group(list(hgm.values()), 'work_id')
    monthly_pages = { (r['month'], r['platform']): f'data/交付索引/按月查看/{r["month"]}_{r["platform"]}.md' for r in base }
    gaps = []

    def gap(kind, rid='', detail='', scope='红果', evidence='', workid='', sid=''):
        r = hgm.get(rid, next((x for x in base if x['ranking_id'] == rid), {}))
        gaps.append({'缺口类别': kind, '范围': r.get('platform', scope), '上榜记录ID': rid,
                     '作品ID': workid or r.get('work_id', ''), '系列ID': sid or r.get('series_id', ''),
                     '标题': r.get('title_raw', ''), '说明': detail, '依据表路径': evidence})

    # 统一到项目根相对路径，保留所有候选，绝不按同名择一。
    material_rows = []
    for m in materials:
        r = hgm[m['ranking_id']]
        material_rows.append({'上榜记录ID': m['ranking_id'], '系列ID': r['series_id'], '作品ID': r['work_id'],
            '素材ID': m['material_id'], '材料标题': m['title'], '平台作品编号': m['platform_work_id'],
            '是否选定候选': m['selected_for_row'], '来源类别': m['source_kind'], '简介正文': m['description'],
            '封面路径': localpath(m['cover_file'], MAT), '原始页面路径': localpath(m['source_file'], MAT),
            '封面SHA256': m['cover_sha256'], '原始页面SHA256': m['source_sha256'],
            '来源网址': m['source_url'], '身份状态': m['identity_status'], '来源明细表': MAT})
    material_group = group(material_rows, '上榜记录ID')
    master = []
    for b in base:
        rid = b['ranking_id']
        r = hgm.get(rid, b)
        is_hg = rid in hgm
        wm = work_by_id.get(r.get('work_id'), {})
        mm = material_group.get(rid, [])
        cc = ccover.get(rid, {})
        selected_comments = cc.get('visible_comments_selected_material', '')
        all_comments = cc.get('candidate_comments_all_versions', '')
        if is_hg and not any(comment_by_mat[m['素材ID']] for m in mm):
            selected_comments = all_comments = '缺失'
        if is_hg and not r['selected_material_id']:
            selected_comments = '版本未定'
        sid = r.get('series_id', '') if is_hg else ''
        wk = r['work_id'] if is_hg else b['candidate_work_id']
        peers = work_rankings[wk] if is_hg else candidates[b['candidate_work_id']]
        same = [x['ranking_id'] for x in peers if x['ranking_id'] != rid]
        bk = books.get(sid, [])
        cs = cc.get('status', '未取得评论')
        row = {'上榜记录ID': rid, '月份': b['month'], '平台': b['platform'], '名次': int(b['rank']),
            '榜单原名': b['title_raw'], '当前材料标题': r.get('current_title', ''),
            '作品ID': wk, 'ID口径': '红果系列季作品候选',
            '系列ID': sid or '未确认', '系列名称': wm.get('series_title', '') or '未确认',
            '系列状态': r.get('series_basis', b.get('franchise_status', '')),
            '季号': r.get('season_code', '') if is_hg else (b.get('season_number') or '未确认'),
            '平台作品编号': r.get('platform_work_id') or '未定位或版本未定',
            '榜图路径': b['source_image'], '榜图核查状态': b['review_status'],
            '身份状态': r['identity_status'],
            '材料状态': r['material_status'],
            '素材ID列表': packed(m['素材ID'] for m in mm), '素材明细表路径': 'data/交付索引/素材路径明细.csv' if mm else '缺失',
            '简介原文': r.get('description') or '版本未定，查看全部候选素材',
            '封面路径列表': packed(m['封面路径'] for m in mm), '简介来源快照路径列表': packed(m['原始页面路径'] for m in mm),
            '评论状态': cs, '选定候选可见热评数': selected_comments if is_hg else '未取得正式作品评论',
            '全部候选可见热评数': all_comments if is_hg else '未取得正式作品评论',
            '评论表路径': COMMENT if all_comments != '缺失' else '缺失',
            '同作品其他上榜记录': packed(same),
            '同系列作品ID列表': series_by_id[sid]['work_ids'] if sid else '未确认',
            '出品原署名': b['producer_raw'] or '空值', '制作版权原署名': b['maker_rights_raw'] or '空值',
            '原著候选书ID列表': packed(x['book_id'] for x in bk),
            '原著候选书名列表': packed(x['book_title'] for x in bk), '作者候选列表': packed(x['author'] for x in bk),
            '改编核实状态': adaptations[rid]['adaptation_status'],
            '当前权威映射表路径': MAP if is_hg else BASE, '本条缺口类别': ''}
        if not b['review_status'].startswith('已对照'):
            gap('榜图OCR待核', rid, b['review_status'], evidence=BASE)
        if is_hg:
            if r['material_status'] == '其他公开来源':
                gap('红果原页缺失', rid, '已有其他来源简介封面，红果原页及历史版本待核', evidence=MAT)
            if not r['selected_material_id']:
                gap('同名版本未定', rid, '两套简介、封面与评论候选均保留，未选定单一历史版本', evidence=MAT)
            if all_comments == '缺失':
                gap('评论入口或页面缺失', rid, cs + '；不代表零评论', evidence=ccover_path)
            if not r['platform_group_id']:
                gap('系列号待核', rid, r['series_basis'], evidence=WORK)
            if r['season_code'] == 'SU' or r['season_code'].startswith('N'):
                gap('季号未确认', rid, r['season_status'], evidence=WORK)
            if b['producer_raw'] in ('', '待认领', '待确认', '待核'):
                gap('出品署名待核', rid, b['producer_raw'] or '原榜出品署名为空', evidence=PRODUCER)
            if not bk:
                gap('原著线索缺失', rid, '当前没有系列原著候选关系；不据此认定原创', evidence=BOOK)
            if adaptations[rid]['adaptation_status'] != '平台作品简介有本季直接改编声明':
                gap('具体季改编关系待核', rid, adaptations[rid]['adaptation_status'], evidence=ADAPT)
            if '待' in r['identity_status'] or '未确定' in r['identity_status']:
                gap('历史版本身份待核', rid, r['identity_status'], evidence=MAP)
        master.append(row)

    gap('分析尚未完成', detail='跨系列DINOv2/BGE-M3、简介与评论编码及正式图表未完成', scope='分析', evidence='README.md')
    gap_by_rank = group(gaps, '上榜记录ID')
    for r in master:
        r['本条缺口类别'] = '；'.join(dict.fromkeys(x['缺口类别'] for x in gap_by_rank[r['上榜记录ID']])) or '无已登记缺口'
    csvout('上榜记录总索引.csv', master)
    csvout('素材路径明细.csv', material_rows)
    csvout('缺口明细.csv', gaps)

    # 关系边分类型保存：跨月重复、系列不同季、同图、近似图、同名版本。
    relations = []
    def edge(kind, left, right, note, evidence, ranking_ids=()):
        relations.append({'关系类型': kind, '对象A': left, '对象B': right, '对应上榜记录ID列表': packed(ranking_ids), '判断说明': note, '依据表路径': evidence})
    for w in works:
        ids = arr(w['ranking_ids'])
        edge('作品归属系列' if w['platform_group_id'] else '系列占位待核', w['work_id'], w['series_id'], w['series_basis'], WORK, ids)
        if len(ids) > 1:
            for rid in ids:
                edge('同作品跨月重复上榜', rid, w['work_id'], '保留每月名次，不重复复制作品材料', WORK, ids)
    for r in read(HG + '/重复核查/不同作品共用同图分组.csv'):
        for mid in arr(r['material_ids']):
            edge('不同作品共用同图', mid, r['cover_image_group'], r['reason'], HG + '/重复核查/不同作品共用同图分组.csv', arr(r['ranking_ids']))
    for r in read(HG + '/重复核查/不同作品封面相似候选.csv'):
        edge('封面精确同图' if r['cover_pixel_exact'] == 'True' else '封面近似候选待看图', r['material_id_a'], r['material_id_b'], 'dHash距离=' + r['dhash_distance'] + '；' + r['series_relation'] + '；' + r['review_status'], HG + '/重复核查/不同作品封面相似候选.csv', arr(r['ranking_ids_a']) + arr(r['ranking_ids_b']))
    for rid, r in hgm.items():
        if not r['selected_material_id']:
            for mid in arr(r['material_ids']):
                edge('同名不同版本待定', rid, mid, '保留候选，不自动选定或合并', MAT, [rid])
    csvout('系列及重复关系.csv', relations)
    wr = []
    for w in works:
        material_ids = arr(w['material_ids'])
        wr.append({'系列ID': w['series_id'], '系列名称': w['series_title'], '作品ID': w['work_id'], '剧名': w['title'],
            '季号': w['season_code'], '系列状态': w['series_basis'], '上榜次数': len(arr(w['ranking_ids'])),
            '上榜记录ID列表': w['ranking_ids'], '同系列其他作品ID': packed(x for x in arr(series_by_id[w['series_id']]['work_ids']) if x != w['work_id']),
            '素材ID列表': w['material_ids'], '封面路径列表': packed(localpath(mat_unique[mid]['cover_file'], MAT) for mid in material_ids),
            '候选热评数': sum(len(comment_by_mat[mid]) for mid in material_ids),
            '身份状态': w['identity_status'], '季号状态': w['season_status'], '来源表路径': WORK})
    csvout('红果作品与系列.csv', wr)

    # 检查实际引用。失败下载目标保留字符串状态，不在导航里伪造可点击文件。
    path_checks = []
    source_tables = [BASE, MAP, MAT, WORK, SERIES, COMMENT, BOOK, ADAPT, PRODUCER,
        HG + '/评论全覆盖/作品覆盖.csv', HG + '/评论全覆盖/上榜记录_评论关联.csv',
        HG + '/关系核实/改编证据登记.csv', HG + '/关系核实/红果原著官方书目.csv',
        HG + '/重复核查/封面到作品和榜单对应.csv']
    for table in source_tables:
        for i, r in enumerate(read(table), 2):
            for field, value in r.items():
                if not value or not (field.endswith(('_file', '_image')) or field in ('file', 'cover_file_a', 'cover_file_b')):
                    continue
                p = localpath(value, table)
                if not p:
                    continue
                ok = exists(p)
                is_failed = table.endswith('作品覆盖.csv') and not r.get('source_sha256')
                path_checks.append({'引用表路径': table, 'CSV行号': i, '记录ID': r.get('ranking_id', r.get('work_id', r.get('material_id', r.get('comment_key', '')))),
                    '字段': field, '项目根相对路径': p, '核验状态': '存在且非空' if ok else ('未落盘的失败下载目标，非可用材料' if is_failed else '引用缺失'),
                    'SHA256状态': ('一致' if sha(ROOT / p) == r[field.replace('_file', '_sha256')] else '不一致') if ok and field.endswith('_file') and r.get(field.replace('_file', '_sha256')) else '未提供对应哈希'})
    csvout('路径核验明细.csv', path_checks)

    # 原目录完整清单及字节相同文件组。仅列实际文件，索引自身不参与重复计数。
    files = []
    hash_groups = defaultdict(list)
    for p in sorted((ROOT / 'data').rglob('*')):
        if not p.is_file() or OUT in p.parents or p.name in {'.DS_Store', '数据包文件清单.sha256'}:
            continue
        rel = p.relative_to(ROOT).as_posix()
        digest = sha(p)
        hash_groups[digest].append(rel)
        level = '历史备份' if '/合并前备份/' in rel else ('当前红果交付' if rel.startswith(HG + '/') else ('原始证据/OCR' if rel.startswith(('data/raw/', 'data/ocr/')) else '中间表或补充批次'))
        n = ''
        if p.suffix == '.csv':
            with p.open(encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                next(reader, None)
                n = sum(1 for _ in reader)
        files.append({'路径': rel, '层级': level, '字节数': p.stat().st_size, 'CSV数据行数': n, 'SHA256': digest,
            '文件状态': '未完成下载片段' if p.suffix == '.part' else ('仅表头/空表' if n == 0 else ('空文件' if not p.stat().st_size else '已落盘'))})
    csvout('原目录文件清单.csv', files)
    file_dupes = [{'文件重复组': 'FILE_' + h[:16], '文件数': len(paths), '文件路径列表': packed(paths),
                   '说明': '文件字节完全相同；包含备份或交付副本，未删除；不代表同一作品'} for h, paths in hash_groups.items() if len(paths) > 1]
    csvout('字节相同文件组.csv', file_dupes)

    # 按采集内容列出当前可复用入口，补充材料也有位置，不只呈现红果主样本。
    catalog = []
    entries = [
        ('红果月榜底表', BASE, 'DataEye月报及保存的月榜图片', '2026年7—10月400条，均已核查榜图转录'),
        ('红果简介封面', MAT, '红果原页/网页快照及单列的第三方补充', '401条材料关联，369个版本；含5条第三方来源与1条同名未定'),
        ('红果系列分季', WORK, '红果平台series_group_id及剧名季号', '368部作品候选；未标季、数字续作及缺号保留状态'),
        ('红果全榜公开热评', COMMENT, '红果作品详情页', '3260条采集时可见热评，非历史全量；与早期批次分开'),
        ('红果早期热评', 'data/公开评论/红果公开热评.csv', '红果详情页早期分层样本', '20部180条，历史批次，不能追加进全榜样本重复计数'),
        ('红果探索评论', INC + '/评论分层/红果公开热评.csv', '红果详情页探索批次', '独立保存，不和当前全榜评论混算'),
        ('第三方作品及改编线索', INC + '/第三方作品证据.csv', '短剧百科等第三方资料', '保存原著、作者和出品线索，关系不自动视为确认'),
        ('百科原著索引', INC + '/百科原著线索.csv', '短剧百科公开作品目录', '含非样本与候选作品，不作为正式样本量'),
        ('红果当前官方书目', HG + '/关系核实/红果原著官方书目.csv', '番茄小说官方书页', '79本候选书有官方资料；书目存在不代表改编已确认'),
        ('全项目官方书目候选', INC + '/原著官方书目核验.csv', '番茄小说官方书页', '范围大于当前红果候选书集合，不与79本相加'),
        ('出品品牌及主体', PRODUCER, '原榜署名、官网与平台账号自述', '联合署名拆分为关系边；品牌与企业主体分开'),
        ('具体作品官网制作职责', HG + '/关系核实/制作发行_具体作品官网证据.csv', '制作方官网', '按具体作品保存制作/发行等职责，不能外推所有作品'),
        ('行业人数口径', INC + '/行业人数口径登记.json', 'DataEye半年报告', '实际规模、机构估计与未来预测分开，缺同口径观看人数序列'),
        ('治理原文', INC + '/治理材料登记.json', '国家广播电视总局', '保存治理原文与发布日期，作为背景材料'),
    ]
    for name, p, source, note in entries:
        assert exists(p), p
        data = read(p) if p.endswith('.csv') else json.loads((ROOT / p).read_text())
        snapshots = [localpath(r['source_file'], p) for r in data if r.get('source_file')]
        catalog.append({'采集内容': name, '当前入口路径': p, '记录数': len(data), '来源': source,
            '原始材料路径示例': snapshots[0] if snapshots else '按入口表内证据字段或榜图路径追溯', '口径与缺口': note})
    csvout('采集内容目录.csv', catalog)

    master_by_id = {r['上榜记录ID']: r for r in master}
    # 按月文档可直接点开榜图、简介快照及每个版本的封面。
    for (month, platform), page in monthly_pages.items():
        lines = [f'# {month} {platform}采集目录', '', '[返回总入口](../../../README.md)', '',
                 '每条记录均有状态；缺失文件只显示原因，不生成空链接。简介、封面为采集时快照，历史身份以待核状态为准。', '']
        for b in (x for x in base if (x['month'], x['platform']) == (month, platform)):
            rid = b['ranking_id']; r = master_by_id[rid]
            lines += [f'<a id="r-{rid}"></a>', f'## {b["rank"]}. {b["title_raw"]}', '',
                f'记录 `{rid}`；作品 `{r["作品ID"]}`；系列 `{r["系列ID"]}`；季号 `{r["季号"]}`。', '',
                link('榜单原图', b['source_image'], page) + '；' + cell(r['榜图核查状态']) + '。', '',
                '材料：' + cell(r['材料状态']) + '。身份：' + cell(r['身份状态']) + '。', '']
            for m in material_group.get(rid, []):
                lines += [f'素材 `{m["素材ID"]}`（{m["来源类别"]}，选定={m["是否选定候选"]}）：' + link('封面', m['封面路径'], page) + ' · ' + link('来源快照', m['原始页面路径'], page), '', '> ' + m['简介正文'].replace('\n', '\n> '), '']
            lines += ['评论：' + cell(r['评论状态']) + '；' + (link('评论表', r['评论表路径'], page) if exists(r['评论表路径']) else '缺失，未生成文件链接') + '。', '',
                '同作品其他上榜记录：' + ('、'.join(link(x, monthly_pages[(master_by_id[x]['月份'], master_by_id[x]['平台'])], page, '#r-' + x) for x in arr(r['同作品其他上榜记录'])) or '无') + '。', '',
                ('同系列：' + link(r['系列名称'], 'data/交付索引/红果系列导航.md', page, '#' + r['系列ID']) + '。') if platform == '红果' else '系列身份未确认。', '',
                '缺口：' + cell(r['本条缺口类别']) + '。', '']
        (ROOT / page).write_text('\n'.join(lines), encoding='utf-8')

    navpath = 'data/交付索引/红果系列导航.md'
    lines = ['# 红果系列、各季与重复上榜对应', '', '[返回总入口](../../README.md)', '',
             '169个有平台编号的系列、27个待核单元。不同季保留独立作品；SU表示未标季，N表示标题数字候选。同名版本候选不强合并。', '']
    for s in series:
        lines += [f'<a id="{s["series_id"]}"></a>', f'## {s["series_title"]}', '',
            f'系列 `{s["series_id"]}`；{s["series_basis"]}；{s["work_count"]}部作品候选，{s["ranking_count"]}条上榜记录。', '',
            '| 作品 / 季号 | 月榜记录（可点开材料） | 封面 | 评论候选条数 |', '| --- | --- | --- | ---: |']
        for wid in arr(s['work_ids']):
            w = work_by_id[wid]
            ranklinks = [link(rid, monthly_pages[(master_by_id[rid]['月份'], '红果')], navpath, '#r-' + rid) for rid in arr(w['ranking_ids'])]
            coverlinks = [link(mid, localpath(mat_unique[mid]['cover_file'], MAT), navpath) for mid in arr(w['material_ids'])]
            n = sum(len(comment_by_mat[mid]) for mid in arr(w['material_ids']))
            lines.append('| ' + ' | '.join([cell(w['title']) + '<br>`' + wid + '`', '<br>'.join(ranklinks), '<br>'.join(coverlinks), str(n) if n else '缺失']) + ' |')
        bs = books[s['series_id']]
        lines += ['', '原著候选：' + ('；'.join(link(x['book_title'] + ' / ' + x['author'], x['book_source_file'], navpath) + '（' + x['adaptation_status'] + '）' for x in bs) if bs else '尚无线索，不据此认定原创') + '。', '']
    (ROOT / navpath).write_text('\n'.join(lines), encoding='utf-8')

    for doc in [HG + '/说明.md', HG + '/关系核实/说明.md', HG + '/评论全覆盖/说明.md']:
        p = ROOT / doc
        old = p.read_text(encoding='utf-8')
        rel = os.path.relpath(ROOT / 'README.md', p.parent)
        banner = f'> 统一导航：当前全部目录、逐条材料、缺口及同系列对应关系见[项目交付入口]({rel})。本页保留本目录的方法和字段口径。\n\n'
        if not old.startswith('> 统一导航：'):
            p.write_text(banner + old, encoding='utf-8')

    counts = Counter(g['缺口类别'] for g in gaps)
    actual_path_errors = [x for x in path_checks if x['核验状态'] == '引用缺失' or x['SHA256状态'] == '不一致']
    summary = {'生成时间UTC': datetime.now(timezone.utc).isoformat(), '上榜记录': len(master),
        '红果上榜记录': len(hgm), '红果作品候选': len(works), '红果系列统计单元': len(series),
        '材料关联': len(material_rows), '唯一素材版本': len(mat_unique), '评论': len(comments),
        '评论覆盖上榜记录': sum(1 for r in ccover.values() if int(r['candidate_comments_all_versions'] or 0) > 0),
        '路径引用检查次数': len(path_checks), '失败下载目标引用': sum(x['核验状态'].startswith('未落盘') for x in path_checks),
        '实际来源引用或哈希异常': len(actual_path_errors), '原目录文件': len(files),
        '文件重复组': len(file_dupes), '未完成片段': sum(x['文件状态'] == '未完成下载片段' for x in files),
        '空表或空文件': sum(x['文件状态'] in ('仅表头/空表', '空文件') for x in files),
        '缺口类别计数': dict(counts), '关系类型计数': dict(Counter(x['关系类型'] for x in relations)),
        '说明': '缺口一条记录可有多项，不可相加当作品数；所有新表内本地路径统一相对于dataprocessing目录。'}

    readme = f'''# 数据爬取与处理

本目录为项目的 `dataprocessing/` 模块。以下命令均在本目录内执行；克隆代码后先在dataprocessing目录解压独立数据包，再运行脚本。

当前范围：2026年7—10月红果月榜400条，全部作品已由项目负责人核实为AI短剧，榜图转录已全部核查。400条均有简介封面候选，3260条公开热评关联394条上榜记录。

## 常用入口

| 要找什么 | 位置 |
| --- | --- |
| 按剧名、月份筛选全部记录 | [上榜记录总索引](data/交付索引/上榜记录总索引.csv) |
| 简介、封面和原始页面路径 | [素材明细](data/交付索引/素材路径明细.csv) |
| 同系列、各季、重复上榜 | [系列导航](data/交付索引/红果系列导航.md) |
| 评论正文 | [评论主表](data/红果400条交付/评论全覆盖/评论主表.csv) |
| 还缺什么、哪些分析没做 | [缺口明细](data/交付索引/缺口明细.csv) · [阅读导览](../数据梳理/成员A数据阅读导览.md) |
| 出品方、原著和作者证据 | [关系核实说明](data/红果400条交付/关系核实/说明.md) |
| OCR核查与修正记录 | [核查说明](data/红果400条交付/OCR核查_20261112/说明.md) |

## 按月查看

| 月份 | 红果 |
| --- | --- |
| 7月 | [100条](data/交付索引/按月查看/2026-07_红果.md) |
| 8月 | [100条](data/交付索引/按月查看/2026-08_红果.md) |
| 9月 | [100条](data/交付索引/按月查看/2026-09_红果.md) |
| 10月 | [100条](data/交付索引/按月查看/2026-10_红果.md) |

## 目录分工

```text
dataprocessing目录
├── scripts/                       全部采集、处理、核查脚本，平放
├── data/
│   ├── 红果400条交付/             当前红果数据：简介封面、系列、评论、关系
│   ├── 交付索引/                  筛选表、按月导航、缺口与路径核验
│   ├── raw/                       原始榜图和网页证据
│   ├── ocr/                       榜图识别文本框
│   ├── 作品匹配/                  红果作品、分季与系列匹配
│   ├── 补采/                      补采原页与中间表
│   ├── 红果简介封面/              简介处理输入与历史材料
│   └── 公开评论/                  早期试采批次，不与新评论重复计数
├── outputs/                       可筛选Excel清单
└── 资料/                          文件整理记录
```

所有脚本说明见 [脚本说明](../DataNewsProgram/dataprocessing/scripts/README.md)。在代码目录 `DataNewsProgram/dataprocessing` 运行 `bash scripts/重建数据.sh`；只刷新索引运行 `python3 scripts/生成交付索引.py`。脚本兼容代码与数据分开存放的目录布局。

研究范围统一为2026年7—10月红果月榜。原始证据与核查记录保留，当前表格和导航为日常阅读入口。

当前仍有6条红果评论入口/页面待补、5条红果原页缺失、1条同名版本待定。核查与分析的不同缺口可以落在同一记录上，不相加当作品数。

最近索引核验：400条主键唯一，均连接作品、系列和候选素材，{len(path_checks)}次路径检查中实际来源引用/哈希异常{len(actual_path_errors)}次。详情见[校验结果](data/交付索引/校验结果.json)。
'''

    workbook_path = 'outputs/采集交付清单.xlsx'
    if exists(workbook_path):
        readme = readme.replace('## 按月查看', f'可筛选的Excel清单：[采集交付清单.xlsx]({workbook_path})。包含总览、上榜索引、红果作品、素材明细、缺口明细和关系对应六张表。Excel为导出时快照，完整简介保留在素材CSV与按月导航中。\n\n## 按月查看', 1)
    (ROOT / 'README.md').write_text(readme, encoding='utf-8')

    # 先写核验对象，随后验证包含本文件在内的导航链接。
    (OUT / '校验结果.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    # 导航链接及核心关联均执行断言，失败则不宣称完整。
    assert len(master) == len({r['上榜记录ID'] for r in master}) == len(base)
    assert set(hgm) == {r['ranking_id'] for r in base if r['platform'] == '红果'}
    assert all(r['work_id'] in work_by_id and r['series_id'] in series_by_id for r in hgm.values())
    assert all(material_group[rid] for rid in hgm)
    assert all(exists(m['封面路径']) and exists(m['原始页面路径']) and m['简介正文'] for m in material_rows)
    assert all(r['work_id'] in work_by_id and r['series_id'] in series_by_id and r['material_id'] in mat_unique for r in comments)
    assert set(x['comment_key'] for x in comments) == {x['comment_key'] for x in read(HG + '/评论全覆盖/上榜记录_评论关联.csv')}
    assert not actual_path_errors, actual_path_errors[:3]
    nav_errors = []
    docfiles = [ROOT / 'README.md', ROOT / navpath] + [ROOT / p for p in monthly_pages.values()]
    for p in docfiles:
        for target in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            if '://' in target:
                continue
            path, _, anchor = unquote(target).partition('#')
            dest = (p.parent / path).resolve() if path else p
            if not dest.is_file():
                nav_errors.append([str(p), target])
            elif anchor and f'id="{anchor}"' not in dest.read_text(encoding='utf-8'):
                nav_errors.append([str(p), target])
    assert not nav_errors, nav_errors[:5]
    summary['生成导航文档'] = len(docfiles)
    summary['导航空链接或错误锚点'] = len(nav_errors)
    summary['核心关联核验'] = '全部通过'
    (OUT / '校验结果.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    # 供Excel导出使用，CSV为主，不在电子表格中重复保留6000多条文件清单。
    payload = {'总览': [
        {'项目': '红果榜单', '数量': len(master), '说明': '7—10月4张榜图，原始ID及名次保留'},
        {'项目': '红果上榜记录', '数量': len(hgm), '说明': '每条均有候选简介与封面，身份按原状态'},
        {'项目': '红果作品候选', '数量': len(works), '说明': '不同季分开计数，含同名未定占位'},
        {'项目': '系列统计单元', '数量': len(series), '说明': '169个已知系列、27个待核单元'},
        {'项目': '红果公开热评', '数量': len(comments), '说明': '覆盖394条上榜，缺失不记零，非历史全量'},
        {'项目': '实际来源路径或哈希异常', '数量': len(actual_path_errors), '说明': '失败下载目标另列，非已取得材料'}],
        '上榜索引': master, '红果作品': wr, '素材明细': material_rows, '缺口明细': gaps, '关系对应': relations}
    (OUT / '表格数据.json').write_text(json.dumps(payload, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
