"""离线解析已下载日榜，保留逐日状态与月榜精确名称关联。"""
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from 作品匹配 import parse_title
from 持续补采 import ROOT, OUT, records, save

ranks=list(csv.DictReader((ROOT/'data/作品匹配/上榜记录_作品系列映射.csv').open(encoding='utf-8-sig')))
bykey={}
for r in ranks:bykey.setdefault(parse_title(r['title_raw'])['title_key'],[]).append(r['ranking_id'])
rows=[];states=[];manifest=[]
for job in json.loads((OUT/'材料下载任务.json').read_text()):
    p=Path(job['file'])
    if not p.exists():
        states.append({**job,'status':'页面未下载'});continue
    raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    evidence={'source_url':job['url'],'source_file':str(p.relative_to(ROOT)),'source_sha256':sha,'captured_at':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()}
    manifest.append({**job,**evidence})
    if job['kind']!='daily':continue
    s=BeautifulSoup(raw.decode('utf-8'),'html.parser');d=datetime.fromisoformat(job['date']);label=f'{d.year}年{d.month}月{d.day}日'
    h=s.find('h1');table=next((t for t in s.find_all('table') if '当日热播指数' in t.get_text()),None)
    if not h or label not in h.get_text() or table is None:
        states.append({**job,'status':'标题日期或表格校验失败'});continue
    day=[]
    try:
        for tr in table.select('tbody tr'):
            cells=tr.find_all('td',recursive=False)
            if len(cells)!=5:raise ValueError('列数不是5')
            rank,_,title,genre,index=cells;a=title.find('a',href=True)
            key=parse_title(a.get_text(strip=True))['title_key']
            day.append({'date':job['date'],'rank':int(rank.get_text(strip=True)),'title':a.get_text(strip=True),'genre':genre.get_text(strip=True),'daily_index':int(index.get_text(strip=True).replace(',','')),'detail_url':urljoin(job['url'],a['href']),'metric':'短剧工程当日热播指数（第三方）','candidate_monthly_ranking_ids':bykey.get(key,[]),'match_status':'完整规范剧名/季数候选，平台版本待核实',**evidence})
        if sorted(r['rank'] for r in day)!=list(range(1,101)):raise ValueError('不是完整1—100名')
        rows.extend(day);states.append({**job,'status':'完整100条已解析','rows':100})
    except Exception as e:states.append({**job,'status':'解析失败','error':str(e)})
records('连续日榜全表',rows);records('日榜页面状态',states)
records('日榜_月榜同名候选', [r for r in rows if r['candidate_monthly_ranking_ids']])
save('来源留存清单.json',manifest)
stats={'complete_days':len({r['date'] for r in rows}),'daily_rows':len(rows),'monthly_title_candidate_rows':sum(bool(r['candidate_monthly_ranking_ids']) for r in rows),'missing_or_failed_days':[r['date'] for r in states if r.get('kind')=='daily' and r['status']!='完整100条已解析']}
save('日榜统计.json',stats);print(json.dumps(stats,ensure_ascii=False))
