"""日榜站作品简介、署名和海报链接，全部标为第三方来源。"""
import csv
import hashlib
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from 作品匹配 import parse_title
from 持续补采 import ROOT,OUT,records,save

ranks=list(csv.DictReader((ROOT/'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig')))
keys={}
for r in ranks:keys.setdefault(parse_title(r['title_raw'])['title_key'],[]).append(r['ranking_id'])
rows=[]
for p in sorted((OUT/'raw').glob('日榜作品_*.html')):
    soup=BeautifulSoup(p.read_text(),'html.parser');h=soup.find('h1')
    if not h:continue
    title=h.get_text(strip=True);key=parse_title(title)['title_key']
    section=next((x.find_parent('section') for x in soup.find_all(['h2','h3']) if x.get_text(strip=True)=='作品详情'),None)
    intro=section.find('p') if section else None
    image=soup.find('img',alt=title+'封面')
    rows.append({'title':title,'description':intro.get_text(strip=True) if intro else '', 'cover_url':image.get('src','') if image else '', 'candidate_ranking_ids':keys.get(key,[]),'source_url':'https://www.duanjugongcheng.com/cn/bangdan/ju/'+p.stem.removeprefix('日榜作品_'),'source_file':str(p.relative_to(ROOT)),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'platform':'第三方汇编；不能认定为抖音官方元数据','identity_status':'完整剧名/季数候选，须核实版本'})
records('第三方日榜作品资料',rows)
save('第三方日榜作品统计.json',{'pages':len(rows),'with_description':sum(bool(r['description']) for r in rows),'with_cover_url':sum(bool(r['cover_url']) for r in rows),'monthly_candidate_pages':sum(bool(r['candidate_ranking_ids']) for r in rows)})
print('第三方作品资料',len(rows))
