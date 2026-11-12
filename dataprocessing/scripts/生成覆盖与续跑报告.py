"""检查增量数据的出处与主键，输出覆盖矩阵和中断续跑入口。"""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from 持续补采 import ROOT,OUT,records,save

ranks=list(csv.DictReader((ROOT/'data/月榜_OCR待核查.csv').open(encoding='utf-8-sig')))
assert len(ranks)==len({r['ranking_id'] for r in ranks})==800
rankids={r['ranking_id'] for r in ranks}
def load(name):
    p=OUT/(name+'.json');return json.loads(p.read_text()) if p.exists() else []
meta=load('上榜记录_简介封面增量');byid={r['ranking_id']:r for r in meta}
delivery_path=ROOT/'data/红果400条交付/红果400条_简介封面总表.json'
delivery=json.loads(delivery_path.read_text()) if delivery_path.exists() else []
delivery_byid={r['ranking_id']:r for r in delivery}
third=load('第三方日榜作品资料');thirdids={rid for r in third if r.get('description') for rid in r['candidate_ranking_ids']}
novel=load('第三方作品证据');baike=load('百科原著线索');bookids={rid for r in novel+baike if r.get('book_id') or r.get('book_record_url') for rid in r['candidate_ranking_ids']}
coverage=[]
for r in ranks:
    m=byid.get(r['ranking_id'],{})
    d=delivery_byid.get(r['ranking_id'],{})
    coverage.append({'ranking_id':r['ranking_id'],'month':r['month'],'platform':r['platform'],'rank':r['rank'],'title':r['title_raw'],'review_status':r['review_status'],'has_hongguo_candidate_description':bool(m.get('description')),'has_hongguo_cover_file':bool(m.get('cover_file')),'has_third_party_description_candidate':r['ranking_id'] in thirdids,'has_third_party_book_candidate':r['ranking_id'] in bookids,'identity_status':m.get('identity_status','待核实'),'hongguo_delivery_material_status':d.get('material_status',''),'has_hongguo_delivery_material_bundle':bool(d.get('material_ids'))})
records('800条覆盖矩阵',coverage)
summary=[]
for month,platform in sorted({(r['month'],r['platform']) for r in ranks}):
    rr=[r for r in coverage if r['month']==month and r['platform']==platform]
    summary.append({'month':month,'platform':platform,'ranking_rows':len(rr),'verified_ocr':sum(r['review_status'].startswith('已') for r in rr),**{k:sum(bool(r[k]) for r in rr) for k in ['has_hongguo_candidate_description','has_hongguo_cover_file','has_third_party_description_candidate','has_third_party_book_candidate']}})
records('分月分平台覆盖',summary)
checked=0
for name in ['连续日榜全表','第三方作品证据','第三方日榜作品资料','百科原著线索','作品资料_简介封面增量','原著官方书目核验','红果名次分层评论']:
    for r in load(name):
        if r.get('source_file') and r.get('source_sha256'):
            path=ROOT/r['source_file'];assert path.exists(),str(path)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256'],str(path)
            checked+=1
        for rid in r.get('candidate_ranking_ids',[]):assert rid in rankids,rid
daily=load('连续日榜全表');assert len(daily)==len({(r['date'],r['rank']) for r in daily})==3000
report={'updated_at':datetime.now(timezone.utc).isoformat(),'ranking_rows':800,'verified_ocr':sum(r['review_status'].startswith('已') for r in ranks),'hongguo_candidate_descriptions':len(meta),'hongguo_works_with_cover':sum(bool(r.get('cover_file')) for r in load('作品资料_简介封面增量')),'daily_rows':len(daily),'third_party_description_pages':len(third),'third_party_original_candidate_ranking_rows':len(bookids),'provenance_records_checked':checked,'limits':'候选关联与已核实身份分开；第三方简介不填作抖音官方简介；搜索索引评论与原页热评不合并。'}
report['flagged_pending_ocr']=sum(bool(r['review_notes']) and not r['review_status'].startswith('已') for r in ranks)
delivery_stats=ROOT/'data/红果400条交付/采集校验结果.json'
if delivery_stats.exists():report['hongguo_delivery']=json.loads(delivery_stats.read_text())
relationship_stats=ROOT/'data/红果400条交付/关系核实/核实统计.json'
if relationship_stats.exists():report['hongguo_relationship_verification']=json.loads(relationship_stats.read_text())
all_comment_stats=ROOT/'data/红果400条交付/评论全覆盖/采集统计.json'
if all_comment_stats.exists():report['hongguo_all_ranked_comments']=json.loads(all_comment_stats.read_text())
ai_stats=ROOT/'data/作品匹配/AI核实统计.json'
if ai_stats.exists():report['AI制作证据统计']=json.loads(ai_stats.read_text())
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
lines=['# 持续补采进度与续跑入口','',f'更新：{report["updated_at"]}。任务继续进行，范围7—10月。','', '## 已落盘成果','']
for k,v in report.items():lines.append(f'- {k}：{v}')
lines+=['','## 当前优先事项','', '- 按用户最新要求扩大红果全部上榜作品的公开页热评；抖音暂不处理。统一交付入口为data/红果400条交付/说明.md。', '- 系列合并和系列号—季号ID见data/红果400条交付/系列合并；最新关系证据见data/红果400条交付/关系核实/说明.md。', '- 优先查看评论全覆盖/失败与待定位.csv，补6条入口或页面；公开页通常仅展示9条，历史评论分页尚未实现。出品与原著关系保留独立核实队列。', '- 简介封面400条均有候选材料，仍有5条缺红果原页、1条同名版本待核，保留原待核清单。',f'- 既有OCR待核记录{800-report["verified_ocr"]}条，保持待核状态。','','## 红果本地重建命令','', '```bash','python3 scripts/批量补齐红果简介.py extract','python3 scripts/持续补采.py audit-covers','python3 scripts/红果剩余材料.py','python3 scripts/整合红果交付.py','python3 scripts/合并红果系列.py','python3 scripts/核实红果关系.py','python3 scripts/合并红果系列.py','python3 scripts/生成覆盖与续跑报告.py','```','', '首次系列合并提供稳定ID；关系核实后再次合并只增补证据字段，不改ID。新增下载使用scripts/原子下载队列.py生成的curl配置；HTTP成功、非空并核实标题/ID后才归档。下载进行时不启动写同一文件的另一批任务。']
(OUT/'进度与续跑.md').write_text('\n'.join(lines)+'\n')
text=(OUT/'进度与续跑.md').read_text().replace('两条OCR疑点及',f'{report["flagged_pending_ocr"]}条带疑点OCR及')
(OUT/'进度与续跑.md').write_text(text)
print(json.dumps(report,ensure_ascii=False))
