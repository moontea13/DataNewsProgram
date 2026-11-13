"""可续跑增量工具：plan-covers / audit-covers / inventory。网络下载用生成的 curl 配置。"""
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

from 项目路径 import ROOT
OUT = ROOT / 'data/补采'

def save(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)

def records(name, rows):
    save(name + '.json', rows)
    lines=OUT/(name+'.jsonl');tmp=lines.with_suffix('.jsonl.tmp')
    tmp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows));tmp.replace(lines)
    target=OUT/(name+'.csv');temporary=target.with_suffix('.csv.tmp')
    if rows:
        fields = list(dict.fromkeys(k for r in rows for k in r))
    elif target.exists():
        with target.open(encoding='utf-8-sig',newline='') as f:fields=next(csv.reader(f),[])
    else:fields=[]
    with temporary.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fields)
        if fields:writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)
    temporary.replace(target)

def works():
    return [json.loads(l) for l in (ROOT/'data/红果简介封面/补采/每作品一份简介.jsonl').read_text().splitlines()]

def cover_path(sid):
    old = ROOT/'data/红果简介封面/covers'/f'{sid}.jpg'
    return old if old.exists() else OUT/'covers'/f'{sid}.jpg'

def plan():
    jobs = []
    for w in works():
        p = cover_path(w['platform_work_id'])
        if not p.exists() and w.get('cover_url','').startswith('https://'):
            jobs.append({'platform_work_id':w['platform_work_id'], 'title':w['title'], 'url':w['cover_url'], 'file':str(p)})
    config = ['fail','silent','show-error','location','ipv4','connect-timeout = 10','max-time = 40','max-filesize = 12582912','rate = "1/s"','proto = "=https"','proto-redir = "=https"']
    for j in jobs:
        config += ['url = '+json.dumps(j['url']), 'output = '+json.dumps(j['file'],ensure_ascii=False)]
    (OUT/'covers').mkdir(parents=True,exist_ok=True)
    (OUT/'封面下载.curl').write_text('\n'.join(config)+'\n')
    save('封面下载任务.json',jobs)
    print(json.dumps({'missing_covers':len(jobs)},ensure_ascii=False))

def audit():
    rows=[]
    for w in works():
        sid=w['platform_work_id'];p=cover_path(sid)
        r={**w,'cover_file':'','cover_status':'待下载'}
        if p.exists():
            try:
                with Image.open(p) as im:
                    im.load();r.update(cover_width=im.width,cover_height=im.height,cover_format=im.format)
                r.update(cover_file=str(p.relative_to(ROOT)),cover_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),cover_status='文件可解码；采集时版本',cover_captured_at=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat())
            except Exception as e:
                r.update(cover_status='文件校验失败',cover_error=str(e))
        rows.append(r)
    records('作品资料_简介封面增量',rows)
    byid={r['platform_work_id']:r for r in rows}
    linked=[]
    for line in (ROOT/'data/红果简介封面/补采/全部红果上榜记录_已取得简介.jsonl').read_text().splitlines():
        r=json.loads(line);w=byid[r['platform_work_id']]
        linked.append({**r,**{k:v for k,v in w.items() if k.startswith('cover_')}})
    records('上榜记录_简介封面增量',linked)
    result={'at':datetime.now(timezone.utc).isoformat(),'candidate_works':len(rows),'valid_covers':sum(bool(r['cover_file']) for r in rows),'ranking_rows_with_candidate_description':len(linked),'ranking_rows_with_cover':sum(bool(r['cover_file']) for r in linked),'identity_note':'完整剧名/季数匹配候选，未升级为已核实历史版本'}
    save('封面补采统计.json',result);print(json.dumps(result,ensure_ascii=False))

def inventory():
    tables={}
    for p in (ROOT/'data').rglob('*.csv'):
        if OUT in p.parents:continue
        try:
            with p.open(encoding='utf-8-sig',newline='') as f:
                rr=list(csv.DictReader(f))
            tables[str(p.relative_to(ROOT))]={'rows':len(rr),'fields':list(rr[0]) if rr else []}
        except Exception as e:tables[str(p)]={'error':str(e)}
    save('表清点.json',tables)
    print(json.dumps({'tables':len(tables)},ensure_ascii=False))

if __name__=='__main__':
    {'plan-covers':plan,'audit-covers':audit,'inventory':inventory}[sys.argv[1]]()
