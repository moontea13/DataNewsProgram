"""按原图行定位生成核查联系表；只生成辅助材料，不自动标记已核。"""
import argparse
import csv
import hashlib
import json
import re
import statistics
from pathlib import Path
from PIL import Image,ImageDraw
from 持续补采 import ROOT,OUT,save

p=argparse.ArgumentParser();p.add_argument('--month',required=True);p.add_argument('--platform',default='红果');p.add_argument('--missing-descriptions',action='store_true');p.add_argument('--pending',action='store_true');p.add_argument('--ids',nargs='*');p.add_argument('--label',required=True);args=p.parse_args()
ranks=list(csv.DictReader((ROOT/'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig')))
missing={json.loads(l)['ranking_id'] for l in (ROOT/'data/红果简介封面/补采/未取得简介_待检索.jsonl').read_text().splitlines()}
rows=[r for r in ranks if r['month']==args.month and r['platform']==args.platform and int(r['rank'])>=4 and (not args.missing_descriptions or r['ranking_id'] in missing) and (not args.pending or not r['review_status'].startswith('已'))]
if args.ids:rows=[r for r in rows if r['ranking_id'] in args.ids]
stem=args.month+'_'+args.platform;boxes=json.loads((ROOT/'data/ocr'/(stem+'.json')).read_text());anchors=[]
for b in boxes:
    cx=sum(x[0] for x in b['box'])/4;cy=sum(x[1] for x in b['box'])/4
    if cx<145 and 1180<cy<6400 and re.fullmatch(r'\d{1,3}',b['text']) and 4<=int(b['text'])<=100:anchors.append((int(b['text']),cy))
intercept=statistics.median(y-52.77*n for n,y in anchors);good=[(n,y) for n,y in anchors if abs(52.77*n+intercept-y)<15];slope,intercept=statistics.linear_regression([n for n,y in good],[y for n,y in good])
im=Image.open(ROOT/rows[0]['source_image']) if rows else None;manifest=[]
for offset in range(0,len(rows),10):
    group=rows[offset:offset+10];sheet=Image.new('RGB',(1080,100*len(group)),'white');draw=ImageDraw.Draw(sheet);target=OUT/f'{args.label}_{offset//10}.png'
    for i,r in enumerate(group):
        y=round(slope*int(r['rank'])+intercept);sheet.paste(im.crop((0,y-27,1080,y+28)),(0,i*100+25));draw.text((10,i*100+5),r['ranking_id'].replace('红果','HG'),fill='black');manifest.append({**r,'contact_sheet':str(target.relative_to(ROOT)),'crop_center_y':y,'source_image_sha256':hashlib.sha256((ROOT/r['source_image']).read_bytes()).hexdigest()})
    sheet.save(target)
save(args.label+'_记录.json',manifest);print('rows',len(rows),'sheets',(len(rows)+9)//10)
