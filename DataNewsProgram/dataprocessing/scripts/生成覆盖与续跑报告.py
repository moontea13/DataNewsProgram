"""检查增量数据的出处与主键，输出覆盖矩阵和中断续跑入口。"""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from 持续补采 import ROOT,OUT,records,save

ranks=list(csv.DictReader((ROOT/'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig')))
assert len(ranks)==len({r['ranking_id'] for r in ranks})==400
rankids={r['ranking_id'] for r in ranks}
def load(name):
    p=OUT/(name+'.json');return json.loads(p.read_text()) if p.exists() else []
meta=load('上榜记录_简介封面增量');byid={r['ranking_id']:r for r in meta}
delivery_path=ROOT/'data/红果400条交付/红果400条_简介封面总表.json'
delivery=json.loads(delivery_path.read_text()) if delivery_path.exists() else []
delivery_byid={r['ranking_id']:r for r in delivery}
novel=load('第三方作品证据');baike=load('百科原著线索');bookids={rid for r in novel+baike if r.get('book_id') or r.get('book_record_url') for rid in r['candidate_ranking_ids']}
coverage=[]
for r in ranks:
    m=byid.get(r['ranking_id'],{})
    d=delivery_byid.get(r['ranking_id'],{})
    coverage.append({'ranking_id':r['ranking_id'],'month':r['month'],'platform':r['platform'],'rank':r['rank'],'title':r['title_raw'],'review_status':r['review_status'],'has_hongguo_candidate_description':bool(m.get('description')),'has_hongguo_cover_file':bool(m.get('cover_file')),'has_third_party_book_candidate':r['ranking_id'] in bookids,'identity_status':m.get('identity_status','待核实'),'hongguo_delivery_material_status':d.get('material_status',''),'has_hongguo_delivery_material_bundle':bool(d.get('material_ids'))})
records('红果400条覆盖矩阵',coverage)
summary=[]
for month,platform in sorted({(r['month'],r['platform']) for r in ranks}):
    rr=[r for r in coverage if r['month']==month and r['platform']==platform]
    summary.append({'month':month,'platform':platform,'ranking_rows':len(rr),'verified_ocr':sum(r['review_status'].startswith('已') for r in rr),**{k:sum(bool(r[k]) for r in rr) for k in ['has_hongguo_candidate_description','has_hongguo_cover_file','has_third_party_book_candidate']}})
records('分月分平台覆盖',summary)
checked=0
for name in ['第三方作品证据','百科原著线索','作品资料_简介封面增量','原著官方书目核验','红果名次分层评论']:
    for r in load(name):
        if r.get('source_file') and r.get('source_sha256'):
            path=ROOT/r['source_file'];assert path.exists(),str(path)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256'],str(path)
            checked+=1
        for rid in r.get('candidate_ranking_ids',[]):assert rid in rankids,rid
report={'updated_at':datetime.now(timezone.utc).isoformat(),'ranking_rows':len(ranks),'verified_ocr':sum(r['review_status'].startswith('已') for r in ranks),'hongguo_candidate_descriptions':len(meta),'hongguo_works_with_cover':sum(bool(r.get('cover_file')) for r in load('作品资料_简介封面增量')),'third_party_original_candidate_ranking_rows':len(bookids),'provenance_records_checked':checked,'limits':'范围为红果2026年7—10月，候选关联与已核实身份分开。'}
report['flagged_pending_ocr']=sum(bool(r['review_notes']) and not r['review_status'].startswith('已') for r in ranks)
delivery_stats=ROOT/'data/红果400条交付/采集校验结果.json'
if delivery_stats.exists():report['hongguo_delivery']=json.loads(delivery_stats.read_text())
relationship_stats=ROOT/'data/红果400条交付/关系核实/核实统计.json'
if relationship_stats.exists():report['hongguo_relationship_verification']=json.loads(relationship_stats.read_text())
all_comment_stats=ROOT/'data/红果400条交付/评论全覆盖/采集统计.json'
if all_comment_stats.exists():report['hongguo_all_ranked_comments']=json.loads(all_comment_stats.read_text())
save('本轮检查与覆盖.json',report)
for name in ['红果评论增量统计','原著官方核验统计','原著作者关系统计','百科线索统计']:
    if (OUT/(name+'.json')).exists():report[name]=load(name)
save('本轮检查与覆盖.json',report)
jobs=[]
for path in OUT.glob('*下载任务.json'):
    try:
        rr=json.loads(path.read_text());missing=[j for j in rr if not Path(j['file']).exists()]
        jobs.append({'task_file':str(path.relative_to(ROOT)),'jobs':len(rr),'missing_files':len(missing)})
    except (KeyError,TypeError):pass
save('续跑下载状态.json',jobs)
print(json.dumps(report,ensure_ascii=False))
