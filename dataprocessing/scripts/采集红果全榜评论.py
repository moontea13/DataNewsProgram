"""plan / extract：覆盖红果全部上榜作品的公开页热评，不等于全部历史评论。"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from 作品匹配 import router_data
from 采集红果简介封面 import parse_work
from 持续补采 import ROOT

BASE = ROOT / 'data/红果400条交付'
OUT = BASE / '评论全覆盖'
RAW = ROOT / 'data/raw/hongguo_comments/all_ranked_20261112'
UNKNOWN = {'', '待认领', '待确认', '待核实', '未知', '不详'}


def save(name, rows):
    for suffix in ['json', 'csv']:
        path = OUT / (name + '.' + suffix)
        tmp = path.with_suffix(path.suffix + '.tmp')
        if suffix == 'json':
            tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        else:
            fields = list(dict.fromkeys(k for r in rows for k in r))
            with tmp.open('w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, fields)
                w.writeheader()
                w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in r.items()} for r in rows)
        tmp.replace(path)


def inputs():
    materials = json.loads((BASE / '简介封面材料明细.json').read_text())
    ranks = json.loads((BASE / '系列合并/上榜记录_系列季映射.json').read_text())
    return materials, ranks


def native_id(m):
    if m.get('platform_work_id'):
        return m['platform_work_id'], '已保存红果作品元数据编号；榜单身份仍按原状态'
    url = urlparse(m['source_url'])
    match = re.fullmatch(r'/manju/info-(\d{19})\.html', url.path)
    if url.hostname == 'www.duanjubaike.net' and match:
        return match[1], '第三方同名目录编号入口候选，须由红果页面校验，不当作已核实身份'
    return '', '尚未定位红果作品编号，不推断为无评论'


def snapshot_fallback(target):
    """只读已归档的红果网页工具快照；与原始HTML方法明确区分。"""
    for path in (ROOT / 'data/补采/raw').glob('*红果网页工具快照.json'):
        data = json.loads(path.read_text())
        if data['source_url'] != target['source_url']:
            continue
        text = '\n'.join(re.sub(r'^L\d+: ?', '', line) for line in data['result'].splitlines() if re.match(r'^L\d+:', line))
        assert re.search(r'^# ' + re.escape(target['title']) + r'$', text, re.M), path
        if '热评剧评' not in text:
            continue
        section = text.split('热评剧评', 1)[1].split('查看全部', 1)[0]
        dates = list(re.finditer(r'(?m)^(\d{4}-\d{2}-\d{2})[ \t]*$', section))
        result = []
        for i, date in enumerate(dates):
            chunk = section[date.end():dates[i + 1].start() if i + 1 < len(dates) else len(section)]
            name = re.search(r'(?m)^【[^\n]*头像[^\n]*】([^\n]+)$', chunk)
            if not name:
                continue
            body = re.sub(r'【[^】]*】', '', chunk[:name.start()]).strip()
            likes = re.findall(r'(?m)^([0-9]+)[ \t]*$', chunk[name.end():])
            if not body:
                continue
            ah = hashlib.sha256(name[1].strip().encode()).hexdigest()[:16]
            key = 'HG_SNAPSHOT_COMMENT_' + hashlib.sha256((target['platform_work_id'] + '|' + ah + '|' + date[1] + '|' + body).encode()).hexdigest()[:24]
            result.append({'comment_key': key, 'native_comment_id': '', 'platform': '红果',
                           'platform_work_id': target['platform_work_id'], 'work_id': target['work_id'],
                           'series_id': target['series_id'], 'season_code': target['season_code'],
                           'material_id': target['material_id'], 'selected_for_row': target['selected_for_row'],
                           'identity_status': target['identity_status'], 'work_title_as_captured': target['title'],
                           'text': body, 'text_sha256': hashlib.sha256(body.encode()).hexdigest(),
                           'author_hash': ah, 'author_hash_scope': '展示名哈希，不能作为唯一用户ID',
                           'published_at': date[1], 'published_precision': 'day', 'published_display': date[1],
                           'likes_display': likes[-1] if likes else '', 'likes_native': None, 'rating_native': None,
                           'source_position': i + 1, 'possible_creator_or_promo': False, 'role_flag_reason': '',
                           'author_role': '角色待核，不能自动当作普通观众',
                           'entry_method': '网页工具文本快照，非原始HTML', 'source_url': data['source_url'],
                           'source_file': str(path.relative_to(ROOT)), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                           'captured_at': datetime.strptime(data['retrieved_at']['current_time'], '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc).isoformat(), 'sampling_batch': '全榜作品公开页热评',
                           'collection_scope': '网页工具快照中的热评，不是当前HTTP原始HTML；未翻页',
                           'period_scope': '快照可见评论，非限定上榜月份内评论'})
        if result:
            return result, re.match(r'\d+', section)[0] if re.match(r'\d+', section) else ''
    return [], ''


def plan(refresh=False):
    OUT.mkdir(exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    snapshot_dir = RAW.parent / ('all_ranked_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')) if refresh else RAW
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    materials, ranks = inputs()
    ri = {r['ranking_id']: r for r in ranks}
    grouped = defaultdict(list)
    for m in materials:
        grouped[m['material_id']].append(m)
    ids = {native_id(mm[0])[0] for mm in grouped.values()} - {''}
    # 优先复用最新且作品编号已校验的详情页。缓存日期逐条保存。
    paths = defaultdict(list)
    for path in (ROOT / 'data').rglob('*.html'):
        match = re.search(r'(\d{19})', path.name)
        if match and match[1] in ids and ('detail_' in path.name or '详情_' in path.name):
            paths[match[1]].append(path)
    valid = {}
    invalid = []
    for sid, pp in paths.items():
        for path in sorted(pp, key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                parse_work(path.read_text(), sid)
                valid[sid] = path
                break
            except (ValueError, TypeError, KeyError) as e:
                invalid.append({'platform_work_id': sid, 'file': str(path.relative_to(ROOT)), 'error': str(e)})
    targets, jobs = [], {}
    for mid, mm in grouped.items():
        m = mm[0]
        sid, basis = native_id(m)
        cache = valid.get(sid) if not refresh else None
        dest = snapshot_dir / ('detail_' + sid + '.html') if sid else None
        path = cache or dest
        rr = [ri[x['ranking_id']] for x in mm]
        labels = sorted({token.strip() for r in rr for token in re.split(r'[，,、/；;]', r['producer_raw'])
                         if token.strip() not in UNKNOWN})
        targets.append({'material_id': mid, 'platform_work_id': sid, 'title': m.get('title', m['ranking_title']),
                        'work_id': rr[0]['work_id'], 'series_id': rr[0]['series_id'],
                        'season_code': rr[0]['season_code'], 'ranking_ids': [r['ranking_id'] for r in rr],
                        'months': sorted({r['month'] for r in rr}), 'selected_for_row': m['selected_for_row'],
                        'identity_status': m.get('identity_status', ''), 'id_basis': basis,
                        'producer_labels': labels, 'source_url': 'https://hongguoduanju.com/detail?series_id=' + sid if sid else '',
                        'source_file': str(path.relative_to(ROOT)) if path else '',
                        'page_status': '复用已校验缓存' if cache else '待下载' if sid else '平台编号待定位'})
        if sid and not cache:
            jobs[sid] = {'url': targets[-1]['source_url'], 'file': str(dest.resolve())}
    save('采集目标', targets)
    save('缓存未通过校验', invalid)
    jobs_path = OUT / '详情页下载任务.json'
    jobs_path.write_text(json.dumps(list(jobs.values()), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'material_targets': len(targets), 'ranking_rows': len(ranks), 'native_ids': len(ids),
                      'validated_cached_pages': len(valid), 'missing_download_pages': len(jobs),
                      'unresolved_native_ids': sum(not t['platform_work_id'] for t in targets)}, ensure_ascii=False))


def extract():
    targets = json.loads((OUT / '采集目标.json').read_text())
    _, ranks = inputs()
    comments, states, comment_links = {}, [], []
    for target in targets:
        sid = target['platform_work_id']
        state = {**target, 'visible_comments': None, 'page_total_review_count_as_displayed': '',
                 'status': '平台编号待定位' if not sid else '未取得可解析的详情页',
                 'source_sha256': '', 'captured_at': '', 'error': ''}
        path = ROOT / target['source_file'] if target['source_file'] else None
        if not sid or not path or not path.exists():
            logs = sorted(path.parent.glob(path.name + '.*.part.result.json'), key=lambda p: p.stat().st_mtime, reverse=True) if path else []
            if logs:
                response = json.loads(logs[0].read_text())
                state.update(last_http_status=response.get('http_code'), download_exit_code=response.get('exitcode'),
                             download_error=response.get('errormsg', ''))
            cached, total = snapshot_fallback(target) if sid else ([], '')
            if cached:
                state.update(status='已提取网页工具快照热评，非原始HTML', visible_comments=len(cached),
                             page_total_review_count_as_displayed=total,
                             **{k: cached[0][k] for k in ['source_file', 'source_url', 'source_sha256', 'captured_at']})
                for c in cached:
                    comments[c['comment_key']] = c
                    for rid in target['ranking_ids']:
                        comment_links.append({'ranking_id': rid, 'work_id': target['work_id'], 'series_id': target['series_id'],
                                              'season_code': target['season_code'], 'material_id': target['material_id'],
                                              'platform_work_id': sid, 'comment_key': c['comment_key'],
                                              'selected_for_row': target['selected_for_row'], 'identity_status': target['identity_status'],
                                              'analysis_usage': '网页工具快照补充热评，单独标注来源方法'})
            states.append(state)
            continue
        try:
            raw = path.read_bytes()
            metadata = parse_work(raw.decode('utf-8'), sid)
            soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
            reviews, total = [], ''
            for value in router_data(soup).values():
                if not isinstance(value, dict) or str((value.get('seriesDetail') or {}).get('series_id')) != sid:
                    continue
                social = value.get('seriesSocialInfo') or {}
                native = social.get('reviews') or {}
                reviews = native.get('reviews') or []
                total = str(native.get('total_count', ''))
            state.update(current_page_title=metadata['title'], page_total_review_count_as_displayed=total,
                         source_sha256=hashlib.sha256(raw).hexdigest(),
                         captured_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
            cards = soup.select("article[class*='mobile-review-card']")
            taken = 0
            for pos, card in enumerate(cards, 1):
                node = card.select_one("p[class*='mobile-review-content']")
                if not node:
                    continue
                text = node.get_text().replace('\x00', '').strip()
                if not text:
                    continue
                date = card.find('time')
                published = date.get('datetime', '') if date else ''
                author = card.select_one("span[class*='user-name']")
                name = author.get_text(strip=True) if author else ''
                author_hash = hashlib.sha256(name.encode()).hexdigest()[:16] if name else ''
                digest = hashlib.sha256(text.encode()).hexdigest()
                key = 'HG_COMMENT_' + hashlib.sha256((sid + '|' + author_hash + '|' + published + '|' + text).encode()).hexdigest()[:24]
                meta = reviews[pos - 1] if pos <= len(reviews) and isinstance(reviews[pos - 1], dict) else {}
                if str(meta.get('content', '')).replace('\x00', '').strip() != text:
                    meta = {}
                likes = card.select_one("div[class*='mobile-review-meta'] small")
                name_matches_credit = name in target['producer_labels']
                first_person_claim = bool(re.search(r'我是.{0,70}(主创|出品方|作者)|主创团队|制作人员|我们.{0,30}(团队|制作|改编|创作)|本团队', text))
                flag = name_matches_credit or first_person_claim
                record = {'comment_key': key, 'native_comment_id': '', 'platform': '红果', 'platform_work_id': sid,
                          'work_id': target['work_id'], 'series_id': target['series_id'], 'season_code': target['season_code'],
                          'material_id': target['material_id'], 'selected_for_row': target['selected_for_row'],
                          'identity_status': target['identity_status'],
                          'work_title_as_captured': metadata['title'], 'text': text, 'text_sha256': digest,
                          'author_hash': author_hash, 'author_hash_scope': '展示名哈希，不能作为唯一用户ID',
                          'published_at': published, 'published_display': date.get_text(strip=True) if date else '',
                          'published_precision': 'datetime' if published else 'unknown', 'entry_method': '原始HTML公开热评卡片',
                          'likes_display': likes.get_text(strip=True) if likes else '',
                          'likes_native': meta.get('digg_count'), 'rating_native': meta.get('rating'),
                          'source_position': pos, 'possible_creator_or_promo': flag,
                          'role_flag_reason': '展示名与榜单署名相同' if name_matches_credit else
                                              '正文包含第一人称主创/制作自述词，需核角色' if first_person_claim else '',
                          'author_role': '疑似主创/推广，待人工核对' if flag else '角色待核，不能自动当作普通观众',
                          'source_url': target['source_url'], 'source_file': target['source_file'],
                          'source_sha256': state['source_sha256'], 'captured_at': state['captured_at'],
                          'sampling_batch': '全榜作品公开页热评',
                          'collection_scope': '提取页面实际展示的全部热评卡片；未翻页，不是全部历史评论',
                          'period_scope': '采集时可见评论，非限定上榜月份内评论'}
                if key in comments:
                    assert comments[key]['text'] == text
                else:
                    comments[key] = record
                for rid in target['ranking_ids']:
                    comment_links.append({'ranking_id': rid, 'work_id': target['work_id'], 'series_id': target['series_id'],
                                          'season_code': target['season_code'], 'material_id': target['material_id'],
                                          'platform_work_id': sid, 'comment_key': key,
                                          'selected_for_row': target['selected_for_row'],
                                          'identity_status': target['identity_status'],
                                          'analysis_usage': '候选身份保留，按研究口径核实后使用' if target['selected_for_row'] else
                                                            '同名未定版本的候选评论；主分析暂排除'})
                taken += 1
            state['visible_comments'] = taken
            state['embedded_review_count'] = len(reviews)
            state['status'] = '已提取公开页热评' if taken else '页面无可解析热评卡片，结构化数据需另核' if reviews else '页面未展示热评'
        except (ValueError, KeyError, TypeError) as e:
            state.update(status='页面身份或解析校验失败', error=str(e))
        states.append(state)
    rows = list(comments.values())
    text_counts = Counter(r['text_sha256'] for r in rows)
    for r in rows:
        r['same_text_occurrences_across_work_comments'] = text_counts[r['text_sha256']]
    links = list({(r['ranking_id'], r['material_id'], r['comment_key']): r for r in comment_links}.values())
    byrank = defaultdict(list)
    for s in states:
        for rid in s['ranking_ids']:
            byrank[rid].append(s)
    coverage = []
    for r in ranks:
        ss = byrank[r['ranking_id']]
        selected = [s for s in ss if s['selected_for_row']]
        available = [s for s in ss if (s['visible_comments'] or 0) > 0]
        coverage.append({'ranking_id': r['ranking_id'], 'month': r['month'], 'rank': int(r['rank']),
                         'title': r['title_raw'], 'work_id': r['work_id'], 'series_id': r['series_id'],
                         'material_ids': [s['material_id'] for s in ss],
                         'status': '有单一候选作品评论' if selected and available else
                                   '同名版本未定，有候选评论，暂不择一' if available else
                                   '已取得页面但未展示热评' if any(s['visible_comments'] == 0 for s in ss) else '入口或页面待补',
                         'visible_comments_selected_material': selected[0]['visible_comments'] if selected else None,
                         'candidate_comments_all_versions': sum(s['visible_comments'] or 0 for s in ss),
                         'material_statuses': [s['status'] for s in ss], 'identity_status': r['identity_status']})
    save('评论主表', rows)
    save('作品覆盖', states)
    save('上榜记录覆盖', coverage)
    save('上榜记录_评论关联', links)
    save('失败与待定位', [s for s in states if s['visible_comments'] is None])
    save('疑似主创推广_待核', [r for r in rows if r['possible_creator_or_promo']])
    stats = {'generated_at': datetime.now(timezone.utc).isoformat(), 'ranking_rows': len(ranks),
             'material_targets_including_ambiguous_versions': len(targets),
             'native_id_targets': len({s['platform_work_id'] for s in states if s['platform_work_id']}),
             'material_targets_with_validated_pages': sum(s['visible_comments'] is not None for s in states),
             'material_targets_with_comments': sum((s['visible_comments'] or 0) > 0 for s in states),
             'unique_native_works_with_comments': len({r['platform_work_id'] for r in rows}),
             'ranking_rows_with_any_candidate_comments': sum(r['candidate_comments_all_versions'] > 0 for r in coverage),
             'ranking_rows_with_selected_candidate_comments': sum((r['visible_comments_selected_material'] or 0) > 0 for r in coverage),
             'comments': len(rows), 'ranking_comment_links': len(links),
             'unresolved_or_failed_material_targets': sum(s['visible_comments'] is None for s in states),
             'pages_without_visible_comments': sum(s['visible_comments'] == 0 for s in states),
             'possible_creator_promo_comments': sum(r['possible_creator_or_promo'] for r in rows),
             'source_methods': dict(Counter(r['entry_method'] for r in rows)),
             'comments_per_material_distribution': dict(Counter(s['visible_comments'] for s in states if s['visible_comments'] is not None)),
             'limits': '全部上榜作品均列入目标，但入口未定位/不可读不能当作零评论；网页通常只展示9条热评。全作品覆盖不是全历史评论；不是随机观众样本。版本未定、疑似主创及原始OCR状态均保留。缓存复用，各页采集时间不同。'}
    (OUT / '采集统计.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
    assert len(coverage) == len({r['ranking_id'] for r in coverage}) == 400
    keys = {r['comment_key'] for r in rows}
    assert len(keys) == len(rows) and all(r['comment_key'] in keys for r in links)
    assert {rid for s in states for rid in s['ranking_ids']} == {r['ranking_id'] for r in ranks}
    (OUT / '说明.md').write_text('\n'.join([
        '# 红果全部上榜作品的公开页热评', '',
        '以400条红果上榜记录和系列号—季号作品ID为框架；同作品跨月只采一份，不同季分别采。同名未定的两个版本都列为候选，不强选。', '',
        '与以前每月5部的20部180条分层样本分别保存，不覆盖、不直接混算。该批次覆盖所有可定位的上榜作品入口，提取页面实际展示的全部热评卡片。现有页面通常只展示9条；总评论数只是页面计数，不是已抓到的条数。', '',
        '采集目标、作品覆盖和上榜记录覆盖列明每个作品的状态。入口缺失、HTTP失败、身份校验失败与页面未展示评论分开。评论主表按作品去重，上榜记录_评论关联保留一条评论对应各月榜单的关系。', '',
        '只导出正文、日期、点赞、展示顺序及来源。展示名只存哈希，不导出头像、用户名或个人主页；展示名哈希不能算唯一用户。主创/推广自动标记只是待核线索，不能自动算普通观众。', '',
        '评论并非限定上榜月份内发布，所抓为各采集时刻可见热评；不能据此推算全部观众观点占比。source_file相对于dataprocessing目录。所有关系沿用既有series_id/work_id。', '',
        '原始HTML不可读但已有网页工具文本快照时，快照热评单独标注entry_method，发布日期仅精确到日，不与HTML来源混称。', '',
        '可续跑：先plan，使用原子下载队列下载详情页下载任务.json，再extract；重建不覆盖旧分层评论数据。要重新采当前快照，用plan --refresh；该参数自动建立新的带时间目录，不覆盖旧网页快照。',
        '一键命令：bash scripts/一键采集红果全榜评论.sh；刷新所有已定位作品：同一命令追加--refresh。逐个请求，失败不污染原始文件，最终在覆盖表中列出。',
    ]) + '\n')
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['plan', 'extract'])
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    plan(args.refresh) if args.stage == 'plan' else extract()
