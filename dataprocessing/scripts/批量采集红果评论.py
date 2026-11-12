"""按已取得简介的月榜样本，批量保存红果公开详情页并提取页面展示热评。

python3 scripts/批量采集红果评论.py plan
curl -L --config data/公开评论/红果评论下载.curl
python3 scripts/批量采集红果评论.py extract
每月最多5个未重复系列，每作品保留页面展示顺序的前9条。不是全量或随机评论。
"""
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from 作品匹配 import ROOT, parse_title, router_data
from 采集红果简介封面 import location, now, save_json, save_records

OUT=ROOT/'data/公开评论'
RAW=ROOT/'data/raw/hongguo_comments'
SOURCE=ROOT/'data/红果简介封面/补采/全部红果上榜记录_已取得简介.jsonl'


def plan():
    OUT.mkdir(parents=True,exist_ok=True);RAW.mkdir(parents=True,exist_ok=True)
    works=[json.loads(l) for l in SOURCE.read_text().splitlines()]
    original={r['ranking_id']:r for r in csv.DictReader((ROOT/'data/作品匹配/上榜记录_作品系列映射.csv').open(encoding='utf-8-sig'))}
    picked=[];seen_ids=set();seen_series=set();per_month=Counter()
    for w in sorted(works,key=lambda x:(x['month'],int(x['rank']))):
        group=w.get('platform_group_id') or parse_title(w['title'])['base_key']
        sid=w['platform_work_id']
        if per_month[w['month']]>=5 or sid in seen_ids or group in seen_series:continue
        per_month[w['month']]+=1;seen_ids.add(sid);seen_series.add(group)
        rank=original[w['ranking_id']]
        picked.append({'platform':'红果','platform_work_id':sid,'title':w['title'],'ranking_id':w['ranking_id'],
                       'sample_month':w['month'],'rank':w['rank'],'platform_group_id':w.get('platform_group_id',''),
                       'ai_production_status':rank.get('ai_production_status','待核实'),
                       'identity_status':w['identity_status'],
                       'url':'https://hongguoduanju.com/detail?series_id='+sid,
                       'file':str(RAW/f'detail_{sid}.html'),
                       'sampling_rule':'7—10月每月按名次优先选5个已匹配候选，跨月作品/系列不重复；非随机样本'})
    save_records(OUT,'红果评论抽样清单',picked)
    jobs=[x for x in picked if not Path(x['file']).exists()]
    config=['fail','silent','show-error','location','ipv4','noproxy = "*"','connect-timeout = 8','max-time = 30','rate = "1/s"']
    for j in jobs:config+=['url = '+json.dumps(j['url']),'output = '+json.dumps(j['file'],ensure_ascii=False)]
    (OUT/'红果评论下载.curl').write_text('\n'.join(config)+'\n')
    save_json(OUT/'红果评论待下载.json',jobs)
    print(json.dumps({'sample_works':len(picked),'by_month':dict(per_month),'missing_pages':len(jobs)},ensure_ascii=False))


def extract():
    targets=[json.loads(l) for l in (OUT/'红果评论抽样清单.jsonl').read_text().splitlines()]
    rows=[];states=[]
    for target in targets:
        path=Path(target['file']);sid=target['platform_work_id']
        if not path.exists():
            states.append({'platform_work_id':sid,'title':target['title'],'status':'未下载作品页','comments':0});continue
        data=path.read_bytes();soup=BeautifulSoup(data.decode('utf-8'),'html.parser')
        loaders=router_data(soup);sd=None;reviews=[]
        for v in loaders.values():
            if not isinstance(v,dict):continue
            detail=v.get('seriesDetail')
            if isinstance(detail,dict) and str(detail.get('series_id'))==sid:
                sd=detail
                social=v.get('seriesSocialInfo') or {}
                reviews=(social.get('reviews') or {}).get('reviews',[]) if isinstance(social,dict) else []
        if not sd:
            states.append({'platform_work_id':sid,'title':target['title'],'status':'作品ID未通过页面校验','comments':0});continue
        cards=soup.select("article[class*='mobile-review-card']")[:9]
        taken=0
        for pos,card in enumerate(cards,1):
            text_node=card.select_one("p[class*='mobile-review-content']")
            if not text_node:continue
            text=text_node.get_text().replace('\x00','').strip()
            if not text:continue
            meta=reviews[pos-1] if pos<=len(reviews) and isinstance(reviews[pos-1],dict) else {}
            # JSON的顺序与DOM不一致时不移植点赞、用户名等信息。
            if meta.get('content')!=text:meta={}
            name_node=card.select_one("span[class*='user-name']")
            username=name_node.get_text(strip=True) if name_node else str(meta.get('user_name') or '')
            author_hash=hashlib.sha256(username.encode()).hexdigest()[:16] if username else ''
            date=card.find('time');published=date.get('datetime','') if date else ''
            likes=card.select_one("div[class*='mobile-review-meta'] small")
            content_key=hashlib.sha256(text.encode()).hexdigest()
            surrogate=hashlib.sha256((sid+'|'+author_hash+'|'+published+'|'+text).encode()).hexdigest()[:24]
            rows.append({'platform':'红果','comment_key':'HG_COMMENT_'+surrogate,'native_comment_id':'',
                         'platform_work_id':sid,'work_title':sd.get('series_name'),
                         'sample_month':target['sample_month'],'ranking_id':target['ranking_id'],
                         'source_position':pos,'text':text,'text_sha256':content_key,
                         'author_hash':author_hash,'author_role':'待核对；不能默认普通观众',
                         'possible_promo_or_creator':text.startswith(('诸位妖友，我是','我是作者','新剧开播')),
                         'published_at':published,'published_display':date.get_text(strip=True) if date else '',
                         'likes_display':likes.get_text(strip=True) if likes else '',
                         'likes_native':meta.get('digg_count'),
                         'source_url':target['url'],'source_file':location(path),
                         'source_sha256':hashlib.sha256(data).hexdigest(),
                         'captured_at':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
                         'entry_type':'公开作品详情页展示热评；未抓取全部评论或随机样本',
                         'sampling_rule':target['sampling_rule'],'ai_production_status':target['ai_production_status'],
                         'comment_period_scope':'采集时可见评论；并非仅上榜月份内发布的评论'})
            taken+=1
        states.append({'platform_work_id':sid,'title':sd.get('series_name'),'status':'已提取' if taken else '页面没有展示热评','comments':taken})
    # 同一来源重复抓取合并；不同作品/不同作者同文保留并标记，避免误删短评。
    unique={r['comment_key']:r for r in rows};rows=list(unique.values());texts=Counter(r['text_sha256'] for r in rows)
    for row in rows:row['same_text_occurrences']=texts[row['text_sha256']]
    save_records(OUT,'红果公开热评',rows);save_records(OUT,'红果评论覆盖情况',states)
    stats={'generated_at':now(),'target_works':len(targets),'works_with_comments':sum(r['comments']>0 for r in states),
           'comments':len(rows),'possible_creator_or_promo_comments':sum(r['possible_promo_or_creator'] for r in rows),
           'comments_with_repeated_text':sum(r['same_text_occurrences']>1 for r in rows),
           'limits':'仅7—10月20个候选作品/系列的当前网页热评；抽样有名次和可获得性偏差；身份待核对；不能当作全部观众意见或当月评论'}
    save_json(OUT/'红果评论统计.json',stats);print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['plan','extract']);a=p.parse_args()
    plan() if a.stage=='plan' else extract()
