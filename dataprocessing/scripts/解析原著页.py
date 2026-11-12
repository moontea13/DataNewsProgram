"""保存原著官方书目核验；改编声明与具体剧集身份分别记录。"""
import hashlib
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from 持续补采 import ROOT,OUT,records,save
if len(sys.argv)>1 and sys.argv[1]=='plan':
    ids=set()
    for name,field in [('百科原著线索','book_id_candidate'),('第三方作品证据','book_id')]:
        p=OUT/(name+'.json')
        if p.exists():ids.update(r[field] for r in json.loads(p.read_text()) if r.get(field))
    jobs=[{'book_id_candidate':bid,'url':'https://fanqienovel.com/page/'+bid,'file':str((OUT/'raw'/('原著_'+bid+'.html')).resolve())} for bid in sorted(ids)]
    save('原著下载任务.json',jobs)
    config=['fail','silent','show-error','location','connect-timeout = 8','max-time = 25','rate = "1/s"']
    missing=[j for j in jobs if not Path(j['file']).exists()]
    for j in missing:config+=['url = '+json.dumps(j['url']),'output = '+json.dumps(j['file'],ensure_ascii=False)]
    (OUT/'原著下载.curl').write_text('\n'.join(config)+'\n')
    print('原著待下载',len(missing));sys.exit(0)
rows=[]
for p in sorted(list((OUT/'raw').glob('原著_*.html'))+list((OUT/'raw').glob('原著补核_*.html'))):
    s=BeautifulSoup(p.read_text(),'html.parser');h=s.find('h1');bid=p.stem.split('_')[-1]
    if not h:continue
    metadata={}
    for script in s.select('script'):
        text=script.get_text();m=re.search(r'window\.__INITIAL_STATE__\s*=\s*',text)
        if m:
            try:metadata=json.JSONDecoder().raw_decode(text[m.end():])[0].get('page',{})
            except (ValueError,TypeError):pass
    if str(metadata.get('bookId',''))!=bid:continue
    author=s.select_one('.author-name-text');intro=s.select_one('.page-abstract-content')
    if not intro:
        intro=next((x for x in s.select('div') if x.get('class') and any('abstract' in c for c in x.get('class',[])) and x.find('p')),None)
    text=intro.get_text('\n',strip=True) if intro else ''
    claim=bool(re.search('改编.{0,20}(漫|剧)|(漫|剧).{0,20}改编',text))
    rows.append({'book_id':bid,'official_book_title':h.get_text(strip=True),'official_author':author.get_text(strip=True) if author else '', 'official_author_id':str(metadata.get('authorId','')),'identity_status':'公开元数据bookId与请求ID一致','official_description':text,'has_adaptation_statement':claim,'adaptation_statement_status':'官方书页包含改编声明；具体剧名/季数须另核' if claim else '未提取到明确改编声明；不等于未改编','source_url':'https://fanqienovel.com/page/'+bid,'source_file':str(p.relative_to(ROOT)),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
records('原著官方书目核验',rows)
save('原著官方核验统计.json',{'official_book_pages':len(rows),'pages_with_adaptation_statement':sum(r['has_adaptation_statement'] for r in rows)})
print('原著官方页',len(rows),'含改编声明',sum(r['has_adaptation_statement'] for r in rows))
