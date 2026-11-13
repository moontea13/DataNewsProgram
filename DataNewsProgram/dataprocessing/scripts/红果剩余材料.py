"""留存红果样本的公开补充材料，明确区别于已取得的红果详情页。"""
import csv
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from PIL import Image
from 持续补采 import ROOT,OUT,records,save

configs=[
 ('2026-07_红果_036','赠物得长生，老头修仙记！','百科作品_7658670507000073278.html','https://www.duanjubaike.net/manju/info-7658670507000073278.html','baike'),
 ('2026-07_红果_047','为他守棺，出世即金眼第二季','百科作品_7657863395504311320.html','https://www.duanjubaike.net/manju/info-7657863395504311320.html','baike'),
 ('2026-07_红果_054','高考落榜，我靠系统成渔王','高考落榜_公开补充页.html','https://sofatv.vip/home/detail/5af61d77141164b5','sofa'),
 ('2026-07_红果_068','中年囧途：我靠透视逆袭','红果补齐来源_中年囧途_浪花湾.html','https://snapbay.tv/drama/26458','snap'),
 ('2026-10_红果_045','招惹督军，他高调求娶我为妻','百科作品_7687650704235711513.html','https://www.duanjubaike.net/manju/info-7687650704235711513.html','baike'),
 ('2026-10_红果_066','牢狱蒙尘，都市起风云第一季','百科作品_7689391734379269144.html','https://www.duanjubaike.net/manju/info-7689391734379269144.html','baike'),
 ('2026-10_红果_067','一块钱硬币，玩出万亿商业帝国','红果补齐来源_硬币_TVLab.html','https://tvlab.ai/short/yi-kuai-qian-ying-bi-wan-chu-wan-yi-shang-ye-di/','tvlab'),
 ('2026-10_红果_071','人到中年，系统逼我年少轻狂','红果补齐来源_人到中年_果果.html','https://guoguoju.com/zh-hans/series/w97jiiezm6h947wk66bwkhnn/1','guoguo'),
 ('2026-10_红果_080','真千金她真没有背景通天','红果补齐来源_真千金_爱玉.html','https://aiyushort.com/video/125819','aiyu'),
]
rows=[];jobs=[]
for rid,title,name,url,kind in configs:
    path=OUT/'raw'/name;raw=path.read_bytes();s=BeautifulSoup(raw.decode('utf-8'),'html.parser')
    h=s.find('h1');assert h and title in h.get_text(strip=True),(name,'作品标题不符')
    desc='';image=''
    if kind=='baike':
        heading=next(h for h in s.select('h3') if '剧情介绍' in h.get_text())
        desc=heading.find_next_sibling('div').get_text(strip=True)
        im=next(x for x in s.select('img') if title in x.get('alt','') and '海报' in x.get('alt',''))
        image=im['src']
    elif kind=='sofa':
        desc=next(x.get_text(strip=True) for x in s.select('p') if x.get_text(strip=True).startswith('高考落榜渔村青年'))
    elif kind=='snap':desc=s.select_one('.d-syn').get_text(strip=True)
    elif kind=='guoguo':
        desc=s.select_one('p.whitespace-pre-line').get_text(strip=True)
        image=s.find('img',alt=title)['src']
    elif kind=='aiyu':
        desc=next(x.get_text(strip=True) for x in s.select('p') if x.get_text(strip=True).startswith('医药世家林家'))
        image=s.find('img',alt=title)['src']
    elif kind=='tvlab':
        heading=next(h for h in s.select('h2,h3') if h.get_text(strip=True)=='剧情简介')
        desc=heading.find_next('p').get_text(strip=True)
        image=next(im['src'] for im in s.select('img') if title in im.get('alt','') and '海报' in im.get('alt',''))
    if not image:
        meta=s.select_one('meta[property="og:image"]');image=meta['content'] if meta else ''
    assert len(desc)>40 and image,(name,'缺少有效简介或图片')
    image=urljoin(url,image);dest=OUT/'covers'/('supplement_'+rid+('_poster' if kind in ['guoguo','tvlab'] else '')+'.jpg');extra={}
    if dest.exists():
        with Image.open(dest) as im:im.load();extra={'cover_width':im.width,'cover_height':im.height,'cover_format':im.format,'cover_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
    else:jobs.append({'url':image,'file':str(dest.resolve())})
    rows.append({'ranking_id':rid,'ranking_title':title,'description':desc,'cover_url':image,'cover_file':str(dest.relative_to(ROOT)) if dest.exists() else '',**extra,'source_url':url,'source_file':str(path.relative_to(ROOT)),'source_sha256':hashlib.sha256(raw).hexdigest(),'captured_at':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),'source_kind':'公开网页补充材料；非红果详情页原文','identity_status':'完整剧名/季数对应；红果版本待独立核实','analysis_usage':'可作查找和内容线索；同源平台简介主分析暂排除，待核实后再纳入'})
records('红果9条公开补充资料',rows);save('红果补充封面任务.json',jobs)
print('supplement rows',len(rows),'cover jobs',len(jobs))
