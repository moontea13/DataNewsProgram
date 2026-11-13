"""提取公开第三方作品资料，精确剧名候选与系列线索分别保存。"""
import csv
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from 作品匹配 import parse_title
from 持续补采 import ROOT, OUT, records, save

ranks=list(csv.DictReader((ROOT/'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig')))
keys={};bases={}
for r in ranks:
    p=parse_title(r['title_raw']);keys.setdefault(p['title_key'],[]).append(r['ranking_id']);bases.setdefault(p['base_key'],[]).append(r['ranking_id'])
rows=[];discover={};books={}
for path in sorted((OUT/'raw').glob('网文作品_*.html')):
    soup=BeautifulSoup(path.read_text(),'html.parser');h=soup.find('h1')
    if not h:continue
    title=h.get_text(strip=True);sid=path.stem.split('_')[-1];parsed=parse_title(title)
    row={'title':title,'third_party_work_id':sid,'source_url':'https://novelcatch.com/drama/'+sid,'source_file':str(path.relative_to(ROOT)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'candidate_ranking_ids':keys.get(parsed['title_key'],[]),'same_base_ranking_ids':bases.get(parsed['base_key'],[]),'evidence_status':'第三方页面标注；须复核身份与改编关系'}
    for dt in soup.select('dt'):
        dd=dt.find_next_sibling('dd')
        if not dd:continue
        label=dt.get_text(strip=True);text=dd.get_text(' ',strip=True)
        if label=='制作公司':row['maker_as_listed']=text if text!='—' else ''
        if label=='原著':
            row['original_note']=text;row['original_status']='第三方疑似标注' if '疑似' in text else '第三方标注，待原著页核实'
            a=dd.select_one("a[href^='/book/']")
            if a:
                bid=a['href'].rsplit('/',1)[1];row.update(book_id=bid,original_title=a.get_text(strip=True).strip('《》'),book_url='https://fanqienovel.com/page/'+bid)
                author=a.find_next_sibling('span');row['author_as_listed']=author.get_text(strip=True).lstrip(' ·') if author else ''
                books[bid]={'url':row['book_url'],'file':str((OUT/'raw'/('原著_'+bid+'.html')).resolve())}
        if label=='上线日':row['release_as_listed']=text
    p=soup.select_one("p[class*='intro']")
    if p:row['third_party_description']=p.get_text(strip=True)
    for a in soup.select("a[href^='/drama/']"):
        href=a['href'];t=a.get_text(strip=True);pt=parse_title(t)
        if href.rsplit('/',1)[-1].isdigit() and (pt['title_key'] in keys or pt['base_key'] in bases):
            nid=href.rsplit('/',1)[1];discover[nid]={'title':t,'url':urljoin('https://novelcatch.com',href),'file':str((OUT/'raw'/('网文作品_'+nid+'.html')).resolve()),'discovered_from':row['source_file']}
    rows.append(row)
records('第三方作品证据',rows)
records('原著关联候选',[r for r in rows if r.get('book_id') and r['candidate_ranking_ids']])
records('原著系列线索',[r for r in rows if r.get('book_id') and not r['candidate_ranking_ids'] and r['same_base_ranking_ids']])
jobs=[j for j in [*discover.values(),*books.values()] if not Path(j['file']).exists()]
save('扩展证据下载任务.json',jobs)
config=['fail','silent','show-error','location','connect-timeout = 8','max-time = 30','rate = "1/s"']
for j in jobs:config+=['url = '+json.dumps(j['url']),'output = '+json.dumps(j['file'],ensure_ascii=False)]
(OUT/'扩展证据下载.curl').write_text('\n'.join(config)+'\n')
stats={'pages':len(rows),'exact_title_candidate_pages':sum(bool(r['candidate_ranking_ids']) for r in rows),'original_book_candidate_pages':sum(bool(r.get('book_id')) and bool(r['candidate_ranking_ids']) for r in rows),'next_downloads':len(jobs)}
save('第三方证据统计.json',stats);print(json.dumps(stats,ensure_ascii=False))
