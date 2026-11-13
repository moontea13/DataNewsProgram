"""制作方官网项目卡片独立留存；不冒充平台当月简介或封面。"""
import hashlib
from datetime import datetime,timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image
from 持续补采 import ROOT,OUT,records,save
import json

p=OUT/'raw/不鸣官方项目.html';raw=p.read_bytes();s=BeautifulSoup(raw.decode('utf-8'),'html.parser');rows=[];jobs=[]
for i,card in enumerate(s.select('article.work-card'),1):
    h=card.find('h3');intro=card.select_one('.work-card-copy > p');im=card.find('img');roles=[x.get_text(strip=True) for x in card.select('.work-role span')]
    if not h:continue
    url=urljoin('https://szbuming.com/ai-short-drama',im['src']) if im else '';dest=OUT/'covers'/f'producer_buming_{i}.jpg'
    image_meta={'cover_status':'未下载'}
    if dest.exists():
        try:
            with Image.open(dest) as image:
                image.load();image_meta.update(cover_width=image.width,cover_height=image.height)
            image_meta.update(cover_status='可解码',cover_file=str(dest.relative_to(ROOT)),cover_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),cover_captured_at=datetime.fromtimestamp(dest.stat().st_mtime,timezone.utc).isoformat())
        except Exception as e:image_meta.update(cover_status='解码失败',cover_error=str(e))
    rows.append({'evidence_work_id':f'BUMING_PROJECT_{i:02}','title':h.get_text(strip=True),'description_as_listed':intro.get_text(strip=True) if intro else '', 'roles_as_listed':roles,'cover_url':url,'cover_file':'',**image_meta,'source_url':'https://szbuming.com/ai-short-drama','source_file':str(p.relative_to(ROOT)),'source_sha256':hashlib.sha256(raw).hexdigest(),'captured_at':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),'source_type':'制作方官网项目卡片；非平台详情页','scope_note':'官网文字/海报为采集时材料；不能当作历史月份的平台简介/封面快照'})
    if url and not dest.exists():jobs.append({'url':url,'file':str(dest.resolve())})
records('制作方官网作品资料',rows);save('制作方海报下载任务.json',jobs)
print('producer cards',len(rows),'poster jobs',len(jobs))
