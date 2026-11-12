"""生成逐月双榜完整名称/季数交集及原始名次；不是最终版本确认。"""
import csv
import hashlib
import sys
from pathlib import Path
from 作品匹配 import parse_title
from 持续补采 import ROOT,OUT,records,save

ranks=list(csv.DictReader((ROOT/'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig')))
rows=[];stats=[]
for month in ['2026-07','2026-08','2026-09','2026-10']:
    platforms={p:{parse_title(r['title_raw'])['title_key']:r for r in ranks if r['month']==month and r['platform']==p} for p in ['抖音','红果']}
    a,b=platforms['抖音'],platforms['红果'];both=a.keys()&b.keys()
    for key in sorted(both):
        x,y=a[key],b[key]
        rows.append({'month':month,'title_key':key,'douyin_ranking_id':x['ranking_id'],'hongguo_ranking_id':y['ranking_id'],'douyin_title_raw':x['title_raw'],'hongguo_title_raw':y['title_raw'],'douyin_rank':int(x['rank']),'hongguo_rank':int(y['rank']),'rank_difference_douyin_minus_hongguo':int(x['rank'])-int(y['rank']),'douyin_producer_raw':x['producer_raw'],'hongguo_producer_raw':y['producer_raw'],'douyin_review_status':x['review_status'],'hongguo_review_status':y['review_status'],'identity_status':'完整规范剧名/季数相同；跨平台版本仍待核实','douyin_source_image':x['source_image'],'hongguo_source_image':y['source_image']})
    expected={'2026-09':13,'2026-10':8}.get(month)
    stats.append({'month':month,'douyin_rows':len(a),'hongguo_rows':len(b),'same_title_candidate_pairs':len(both),'douyin_only_title_candidates':len(a.keys()-b.keys()),'hongguo_only_title_candidates':len(b.keys()-a.keys()),'report_same_name_count':expected,'agrees_with_report_count':len(both)==expected if expected is not None else '', 'report_reference':'https://www.thepaper.cn/newsDetail_forward_34442821' if expected is not None else '', 'limits':'同名口径对照；数量一致不等于版本已核实或全部OCR已核'})
records('双榜同月交集统计_同名口径',stats)
byid={r['ranking_id']:r for r in ranks}
for row in rows:
    for prefix in ['douyin','hongguo']:
        source=byid[row[prefix+'_ranking_id']];printed=source['rank_ocr']
        row[prefix+'_rank_position']=int(source['rank'])
        row[prefix+'_source_rank_text']=printed
        card_rank=int(source['rank'])<=3 and source['review_status'].startswith('已')
        row[prefix+'_rank']=int(printed) if printed.isdigit() else int(source['rank']) if card_rank else ''
        row[prefix+'_rank_note']='已核对前三名卡片位次，非表格数字列' if card_rank and not printed else '原图印数与行序不同，两个值分别保留' if printed!=source['rank'] else 'OCR/核对名次，核查状态另列'
    a,b=row['douyin_rank'],row['hongguo_rank']
    row['rank_difference_douyin_minus_hongguo']=a-b if isinstance(a,int) and isinstance(b,int) else ''
records('双榜同月作品候选_原始名次',rows)
save('双榜候选检查.json',{'candidate_pairs':len(rows),'ranking_references_unique':len({(r['douyin_ranking_id'],r['hongguo_ranking_id']) for r in rows})==len(rows),'title_season_match':all(parse_title(r['douyin_title_raw'])['title_key']==parse_title(r['hongguo_title_raw'])['title_key'] for r in rows),'original_rank_texts_preserved':all(r[p+'_source_rank_text']==byid[r[p+'_ranking_id']]['rank_ocr'] for r in rows for p in ['douyin','hongguo']),'rank_positions_preserved':all(r[p+'_rank_position']==int(byid[r[p+'_ranking_id']]['rank']) for r in rows for p in ['douyin','hongguo']),'printed_rank_discrepancies':sum(bool(r[p+'_source_rank_text']) and r[p+'_source_rank_text']!=str(r[p+'_rank_position']) for r in rows for p in ['douyin','hongguo']),'limits':'rank为原图印数的OCR/核对值，rank_position为榜图行序；前三名按已核卡片位次；未核记录不能当作最终源值。'})
print('same-month candidate pairs',len(rows),[(r['month'],r['same_title_candidate_pairs']) for r in stats])
