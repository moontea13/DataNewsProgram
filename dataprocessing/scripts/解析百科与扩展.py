"""百科原著线索和目标剧名扩展；不把第三方标注视作已确认改编。"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from 作品匹配 import parse_title
from 持续补采 import ROOT,OUT,records,save

ranks=list(csv.DictReader((ROOT/'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig')))
keys={};bases={}
for r in ranks:
    pt=parse_title(r['title_raw']);keys.setdefault(pt['title_key'],[]).append(r['ranking_id']);bases.setdefault(pt['base_key'],[]).append(r['ranking_id'])
rows=[];found={};states=[]
paths=list((OUT/'raw').glob('百科作品_*.html'))+[OUT/'raw/短剧百科_纨绔.html']
for path in paths:
    if not path.exists():continue
    s=BeautifulSoup(path.read_text(),'html.parser');h=s.find('h1')
    if not h:
        states.append({'file':str(path),'status':'无作品标题，页面待核'});continue
    title=h.get_text(strip=True);parsed=parse_title(title);sid=re.search(r'\d{15,25}',path.name)
    sid=sid[0] if sid else '7673067074104593432'
    row={'title':title,'platform_work_id_candidate':sid,'source_url':'https://www.duanjubaike.net/manju/info-'+sid+'.html','source_file':str(path.relative_to(ROOT)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'candidate_ranking_ids':keys.get(parsed['title_key'],[]),'evidence_status':'第三方作品/原著标注，待原著页与出品资料确认'}
    book=s.select_one("a[href^='/xiaoshuo/info-']")
    if book:
        row['book_record_url']=urljoin(row['source_url'],book['href']);row['book_id_candidate']=re.search(r'info-(\d+)',book['href'])[1]
        image=book.find('img');row['original_title_as_listed']=(image.get('alt','').removeprefix('小说《').removesuffix('》')) if image else ''
        author=next((x.get_text(strip=True) for x in book.select('span') if x.get_text(strip=True).startswith('作者：')),'')
        row['author_as_listed']=author.removeprefix('作者：')
    rows.append(row)
    for a in s.select("a[href*='/manju/info-']"):
        titleattr=a.get('title','');t=titleattr.removeprefix('漫剧《').removesuffix('》')
        if not t:continue
        p=parse_title(t);match=re.search(r'info-(\d+)',a['href'])
        if match and (p['title_key'] in keys or p['base_key'] in bases):
            nid=match[1];found[nid]={'title':t,'platform_work_id':nid,'source_url':urljoin(row['source_url'],a['href']),'discovered_from':row['source_file']}
records('百科原著线索',rows);records('百科页面状态',states);records('百科目标作品发现',list(found.values()))
jobs=[]
for sid,w in found.items():
    for kind,url,p in [('百科','https://www.duanjubaike.net/manju/info-'+sid+'.html',OUT/'raw'/('百科作品_'+sid+'.html')),('红果','https://hongguoduanju.com/player/'+sid,ROOT/'data/raw/work_catalogs'/('player_'+sid+'.html'))]:
        if not p.exists():jobs.append({'kind':kind,'url':url,'file':str(p.resolve()),'title':w['title'],'discovered_from':w['discovered_from']})
save('百科扩展下载任务.json',jobs)
config=['fail','silent','show-error','location','connect-timeout = 8','max-time = 25','rate = "1/s"']
for j in jobs:config+=['url = '+json.dumps(j['url']),'output = '+json.dumps(j['file'],ensure_ascii=False)]
(OUT/'百科扩展下载.curl').write_text('\n'.join(config)+'\n')
stats={'pages':len(rows),'with_book_link':sum(bool(r.get('book_record_url')) for r in rows),'monthly_title_candidate_pages':sum(bool(r['candidate_ranking_ids']) for r in rows),'new_download_jobs':len(jobs)}
save('百科线索统计.json',stats);print(json.dumps(stats,ensure_ascii=False))
