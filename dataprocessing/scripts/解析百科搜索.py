"""从百科公开搜索页提取作品候选，搜索命中不直接回填月榜。"""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin,urlencode
from 作品匹配 import parse_title
from 持续补采 import ROOT,OUT,records,save

targets=[]
for source in sorted(OUT.glob('百科搜索任务*.json')):targets.extend(json.loads(source.read_text()))
targets=list({j['file']:j for j in targets}.values());rows=[];states=[];jobs={}
for j in targets:
    p=Path(j['file'])
    if not p.exists():states.append({**j,'status':'未下载'});continue
    raw=p.read_bytes();s=__import__('bs4').BeautifulSoup(raw.decode('utf-8'),'html.parser');hits=0
    for a in s.select("a[href*='/manju/info-']"):
        m=re.search(r'info-(\d+)\.html',a['href']);title=a.get('title','').removeprefix('漫剧《').removesuffix('》')
        if not m or not title:continue
        sid=m[1];hits+=1;url=urljoin('https://www.duanjubaike.net',a['href']);parsed=parse_title(title);target=parse_title(j.get('original_title') or j['title'])
        rows.append({'ranking_id':j['ranking_id'],'query_title':j['title'],'candidate_title':title,'platform_work_id_candidate':sid,'candidate_url':url,'same_base_key':parsed['base_key']==target['base_key'],'source_file':str(p.relative_to(ROOT)),'source_sha256':hashlib.sha256(raw).hexdigest(),'status':'公开搜索命中线索；作品页身份及历史时间待核'})
        for kind,u,fp in [('百科',url,OUT/'raw'/('百科作品_'+sid+'.html')),('红果','https://hongguoduanju.com/player/'+sid,ROOT/'data/raw/work_catalogs'/('player_'+sid+'.html'))]:
            if not fp.exists():jobs[str(fp)]={'kind':kind,'url':u,'file':str(fp.resolve()),'candidate_title':title,'discovered_from':str(p.relative_to(ROOT))}
    states.append({**j,'status':'已提取候选' if hits else '本次关键词未见结果，下一轮缩短关键词','hits':hits})
records('百科搜索命中候选',rows);records('百科搜索覆盖',states);save('搜索候选下载任务.json',list(jobs.values()))
config=['fail','silent','show-error','location','connect-timeout = 8','max-time = 25','rate = "1/s"']
for j in jobs.values():config+=['url = '+json.dumps(j['url']),'output = '+json.dumps(j['file'],ensure_ascii=False)]
(OUT/'搜索候选下载.curl').write_text('\n'.join(config)+'\n')
print(json.dumps({'queries':len(targets),'queries_with_results':sum(bool(r.get('hits')) for r in states),'candidate_rows':len(rows),'new_jobs':len(jobs)},ensure_ascii=False))
