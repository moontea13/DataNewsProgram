"""批量检索索引 → 公开详情页下载计划 → 简介提取。保留未匹配清单。

阶段1：python3 scripts/批量补齐红果简介.py plan
阶段2：curl -L --config data/红果简介封面/补采/作品页下载.curl
阶段3：python3 scripts/批量补齐红果简介.py extract

search_*.json 是批量公开搜索工具的原始导出。只把搜索作为网址线索；
必须读取红果页面，并对照完整剧名/季号，才关联简介。没有简介不填造。
"""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from 作品匹配 import ROOT, parse_title, router_data
from 采集红果简介封面 import now, save_json, save_records, location, parse_work

OUT = ROOT / "data/红果简介封面/补采"
RAW = ROOT / "data/raw/work_catalogs"


def get_targets():
    ranks = list(csv.DictReader((ROOT / 'data/作品匹配/上榜记录_作品系列映射.csv').open(encoding='utf-8-sig')))
    return [r for r in ranks if r['platform'] == '红果']


def download_plan():
    OUT.mkdir(parents=True, exist_ok=True)
    ids = set()
    origins = defaultdict(list)
    for p in sorted(OUT.glob('search_*.json')):
        text = p.read_text()
        urls = re.findall(r'https://hongguoduanju\.com/(?:player/\d+|detail\?series_id=\d+)', text)
        for url in urls:
            sid = re.search(r'(\d{10,25})$', url)[1]
            ids.add(sid)
            origins[sid].append(location(p))
    # 从已留存页面的推荐卡片扩展地址。只用来发现具体作品页，不推断系列关系。
    ranks = get_targets()
    title_keys = {parse_title(r['title_raw'])['title_key'] for r in ranks}
    base_keys = {parse_title(r['title_raw'])['base_key'] for r in ranks}
    for p in sorted(RAW.glob('*.html')):
        soup = BeautifulSoup(p.read_text(), 'html.parser')
        for card in soup.select("a[href^='/player/']"):
            title = card.select_one("p[class*='title']")
            match = re.fullmatch(r'/player/(\d+)',card['href'])
            if title and match:
                parsed = parse_title(title.get_text(strip=True))
                if parsed['title_key'] in title_keys or parsed['base_key'] in base_keys:
                    sid=match[1];ids.add(sid);origins[sid].append(location(p))
    jobs = []
    for sid in sorted(ids):
        path = RAW / f'player_{sid}.html'
        if path.exists():
            continue
        jobs.append({'platform_work_id': sid, 'url': f'https://hongguoduanju.com/player/{sid}',
                     'file': str(path), 'search_evidence_files': sorted(set(origins[sid]))})
    save_json(OUT / '作品页下载任务.json', jobs)
    # curl config 由JSON编码URL/文件名；无shell字符串拼接和命令替换。
    commands = ['fail', 'silent', 'show-error', 'location', 'ipv4', 'noproxy = "*"',
                'connect-timeout = 8', 'max-time = 30', 'max-filesize = 12582912',
                'rate = "1/s"', 'proto = "=https"', 'proto-redir = "=https"']
    for job in jobs:
        commands += ['url = ' + json.dumps(job['url']), 'output = ' + json.dumps(job['file'], ensure_ascii=False)]
    (OUT / '作品页下载.curl').write_text('\n'.join(commands) + '\n')
    print(json.dumps({'discovered_ids': len(ids), 'missing_pages': len(jobs)}, ensure_ascii=False))


def extract():
    ranks = get_targets()
    by_key = defaultdict(dict)
    pages = []
    failures = []
    for path in sorted(RAW.glob('player_*.html')):
        sid = path.stem.split('_')[-1]
        try:
            data = path.read_bytes()
            work = parse_work(data.decode('utf-8'), sid)
            row = {**work, 'source_url': f'https://hongguoduanju.com/player/{sid}',
                   'source_file': location(path), 'source_sha256': hashlib.sha256(data).hexdigest(),
                   'snapshot_scope': '采集时快照，不代表历史月榜当月简介'}
            by_key[parse_title(work['title'])['title_key']][sid] = row
            pages.append(row)
        except Exception as e:
            failures.append({'file':location(path), 'error':str(e)})
    matched, missing, ambiguous = [], [], []
    reviewed_path=ROOT/'data/补采/红果身份人工核对.json'
    reviewed=json.loads(reviewed_path.read_text()) if reviewed_path.exists() else {}
    pages_by_id={w['platform_work_id']:w for w in pages}
    version_candidates = []
    for rank in ranks:
        candidates = by_key.get(parse_title(rank['title_raw'])['title_key'], {})
        # 晚于上榜月份才首见的同名ID不能直接回填历史榜单。
        year,month=map(int,rank['month'].split('-'))
        cutoff=datetime(year+(month==12),1 if month==12 else month+1,1,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        eligible={sid:w for sid,w in candidates.items()
                  if not w.get('first_visible_time','').isdigit() or int(w['first_visible_time']) < cutoff}
        selection='完整规范剧名/季号对应单一公开作品ID；版本仍待核实'
        choice = eligible.get(rank['platform_work_id']) if rank['platform_work_id'] else None
        review=reviewed.get(rank['ranking_id'])
        if review:
            sid=review['platform_work_id'];work=pages_by_id.get(sid)
            if not work:raise ValueError('人工核对ID缺少已解析作品页：'+sid)
            if work.get('first_visible_time','').isdigit() and int(work['first_visible_time'])>=cutoff:raise ValueError('人工核对作品晚于上榜月份：'+sid)
            for file in review['evidence_files']:
                if not (ROOT/file).exists():raise ValueError('人工核对缺证据文件：'+file)
            if review.get('series_anchor_id'):
                anchor=pages_by_id[review['series_anchor_id']]
                if not work['platform_group_id'] or work['platform_group_id']!=anchor['platform_group_id']:raise ValueError('系列组不一致：'+sid)
            if review.get('expected_producer') and review['expected_producer'] not in re.split(r'[，,、/；;]\s*',rank['producer_raw']):raise ValueError('出品署名不一致：'+sid)
            if review.get('alias_evidence_file'):
                heading=BeautifulSoup((ROOT/review['alias_evidence_file']).read_text(),'html.parser').find('h1')
                if not heading or parse_title(heading.get_text(strip=True))['title_key']!=parse_title(rank['title_raw'])['title_key']:raise ValueError('旧名证据标题不符：'+sid)
            choice=work;selection=review['method']+'；'+review['confidence_note']
        if choice is None and len(eligible)>1:
            # 保留“完结篇”等限定词，避免季号规范化把两个版本混到一起。
            exact={sid:w for sid,w in eligible.items()
                   if unicodedata.normalize('NFKC',w['title']).strip()==unicodedata.normalize('NFKC',rank['title_raw']).strip()}
            if len(exact)==1:
                choice=next(iter(exact.values()))
                selection='完整剧名字面（含限定词/标点）唯一候选；其他同名版本另列，身份仍待核实'
        if choice is None and len(eligible) == 1:
            choice = next(iter(eligible.values()))
            if len(candidates)>1:selection='完整规范剧名/季号匹配；排除晚于上榜月首见版本后为唯一候选'
        row = {'ranking_id': rank['ranking_id'], 'month':rank['month'], 'rank':rank['rank'],
               'ranking_title':rank['title_raw'], 'candidate_work_id':rank['candidate_work_id']}
        if choice:
            matched.append({**row, **choice, 'identity_status':selection,'identity_review_file':location(reviewed_path) if review else ''})
        else:
            reason=('候选页面首见时间均晚于上榜月；不回填历史身份' if candidates and not eligible else
                    '同名/同季多ID，待核查版本' if candidates else '尚无完整剧名/季号匹配的作品页')
            row.update(candidate_platform_ids=sorted(candidates), missing_reason=reason)
            (ambiguous if candidates else missing).append(row)
        if len(candidates)>1:
            for sid,w in candidates.items():
                version_candidates.append({**row, **w, 'primary_candidate':bool(choice and sid==choice['platform_work_id']),
                                           'visible_before_month_end':sid in eligible,
                                           'identity_status':'同名各版本简介已采集；保留候选，不自动认定历史榜单身份'})
    save_records(OUT, '全部红果上榜记录_已取得简介', matched)
    save_records(OUT, '未取得简介_待检索', missing)
    save_records(OUT, '同名多版本_待核查', ambiguous)
    save_records(OUT, '同名各版本_全部候选简介', version_candidates)
    indexed={r['ranking_id']:r for r in matched+missing+ambiguous}
    full=[{**indexed[r['ranking_id']], 'description_link_status':
           '已取得候选简介，身份待核实' if indexed[r['ranking_id']].get('description') else '尚未完成一对一匹配'} for r in ranks]
    save_records(OUT, '红果400条_简介全表', full)
    grouped=defaultdict(list)
    for row in matched:grouped[row['platform_work_id']].append(row)
    unique=[{**rows[0], 'ranking_ids':[r['ranking_id'] for r in rows],
             'ranking_months':sorted({r['month'] for r in rows})} for rows in grouped.values()]
    save_records(OUT, '每作品一份简介', unique)
    # 为OCR错字/改名保留近名作品的原文，不把这些候选自动填成正式匹配。
    fuzzy=[]
    for row in missing:
        title=row['ranking_title']
        transformed=title[len(row['rank']):] if title.startswith(row['rank']) else title
        a=parse_title(transformed)
        options=[]
        for work in pages:
            b=parse_title(work['title'])
            if a['season_number']!=b['season_number'] or a['installment_unit']!=b['installment_unit']:
                continue
            score=SequenceMatcher(None,a['title_key'],b['title_key']).ratio()
            prefix=(min(len(a['base_key']),len(b['base_key']))>=10 and
                    (a['base_key'].startswith(b['base_key']) or b['base_key'].startswith(a['base_key'])))
            if score>=0.85 or prefix:
                options.append((score,work,'同季且一方包含另一方完整长前缀' if prefix and score<0.85 else '同季完整剧名相似度至少0.85'))
        for score,work,rule in sorted(options,key=lambda x:-x[0])[:3]:
            fuzzy.append({**row, **work, 'name_similarity':round(score,6),
                          'candidate_rule':rule,
                          'query_title':transformed,
                          'identity_status':'近名/OCR候选；原文已采集，须核查榜图和版本；未回填一对一主表'})
    save_records(OUT, '近名或OCR差异_候选简介', fuzzy)
    save_records(OUT, '解析失败', failures, ['file','error'])
    # 样本外命中单独保存索引，不把它们加入正式样本。
    save_records(OUT, '公开作品元数据索引', pages)
    stats = {'generated_at':now(), 'hongguo_ranking_rows':len(ranks),
             'rows_with_title_or_reviewed_identity_candidate':len(matched),
             'unique_ids_with_description':len({r['platform_work_id'] for r in matched if r['description']}),
             'rows_with_description':sum(bool(r['description']) for r in matched),
             'rows_missing_description':len(ranks)-sum(bool(r['description']) for r in matched),
             'unmatched_rows':len(missing), 'ambiguous_rows':len(ambiguous),
             'unmatched_rows_with_near_name_description':len({r['ranking_id'] for r in fuzzy}),
             'all_same_name_version_candidates_saved':len(version_candidates),
             'page_parse_failures':len(failures),
             'limits':'完整规范剧名/季号及有证据的人工核对候选；改名保留旧名证据和当前名称，跨平台不直接套用；未完成一对一匹配的条目另列'}
    save_json(OUT / '补采统计.json', stats)
    print(json.dumps(stats,ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['plan','extract'])
    a=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    download_plan() if a.stage=='plan' else extract()


if __name__=='__main__':
    main()
