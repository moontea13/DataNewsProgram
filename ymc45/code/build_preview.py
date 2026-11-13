"""从定稿结果构建静态预览数据；无需外部库，本地双击HTML即可使用。"""
import csv
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

BASE=Path(__file__).resolve().parents[1]
SOURCE=BASE/'results/reviewed'
DEST=BASE/'result-preview/dist'


def rows(name):
    with (SOURCE/name).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def main():
    full=json.loads((SOURCE/'可视化数据.json').read_text(encoding='utf-8'))
    raw_series=rows('系列结构标注.csv')
    raw_comments=rows('评论筛选与标签.csv')
    comments={c['comment_key']:c for c in raw_comments}
    series=[]
    for s in raw_series:
        series.append({k:s[k] for k in ['series_id','anonymous_series','series_title','cluster_id','cluster_name','core_conflict','turning_mechanism',
                                        'response_path','core_narrative','assignment_reason','evidence_excerpt','evidence_origin','source_url','exclusion_reason']}
                      |{'supplementary_evidence':json.loads(s['supplementary_evidence'])})
    grouped=defaultdict(list)
    for o in rows('评论观点明细.csv'):
        if comments[o['comment_key']]['eligibility']=='有效观众':
            grouped[(o['comment_key'],o['comparison_scope'],o['similarity_relation'])].append(o)
    cases=[]
    for (key,scope,relation),ops in grouped.items():
        c=comments[key]
        cases.append(dict(id=c['local_id'],comment_key=key,title=c['work_title_as_captured'],text=c['text'],scope=scope,relation=relation,
                          likes=int(c['likes_native'] or 0),source_url=c['source_url'],
                          opinions=[{k:o[k] for k in ['object','attitude','comparison_target']} for o in ops]))
    cases.sort(key=lambda c:(-c['likes'],c['id']))
    data=dict(meta=dict(version=full['version'],samplePeriod='2026年7—10月',date='2026-11-13',status='结果预览 · 非最终作品'),
              counts=dict(rankings=len(full['ranking_nodes']),works=len({r['work_id'] for r in full['ranking_nodes']}),series=len(series),
                          clusters=len(full['clusters']),codableSeries=sum(bool(s['cluster_id']) for s in series),
                          validComments=sum(c['eligibility']=='有效观众' for c in raw_comments)),
              nodes=full['ranking_nodes'],series=series,
              clusters=[{k:c[k] for k in ['cluster_id','cluster_name','common_chain','inclusion_rule','nearest_cluster_difference',
                                         'member_series_ids','member_titles','member_count','color']} for c in full['clusters']],
              novelty=full['novelty'],reuse=full['reuse'],
              commentMetrics=full['comment_metrics'],attitudes=full['object_attitudes'],
              cases=cases,excludedSeries=[dict(title=s['series_title'],reason=s['exclusion_reason'],series_id=s['series_id']) for s in series if not s['cluster_id']],
              qualification=dict(Counter(c['eligibility'] for c in raw_comments)))
    # 页面只携带展示所需字段；作者哈希、人工表和操作日志不打入网页。
    for node in data['nodes']:
        for key in ['assignment_reason','evidence_excerpt','review_status']:
            node.pop(key,None)
    for a in data['attitudes']:
        a.pop('comment_keys',None)
    for m in data['commentMetrics']:
        m.pop('member_ids',None)
    text=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</',r'<\/')
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'data.js').write_text('window.PREVIEW_DATA='+text+';\n',encoding='utf-8')
    (DEST/'data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    csv_names=['指标1_三层换新.csv','指标2_新系列结构沿用.csv','指标3_相似反馈统计.csv','指标4_对象态度分布.csv',
               '分组簇统计.csv','系列结构排除清单.csv']
    with ZipFile(DEST/'统计结果CSV.zip','w',ZIP_DEFLATED) as archive:
        for name in csv_names:
            archive.write(SOURCE/name,name)
    assert data['counts']==dict(rankings=400,works=368,series=196,clusters=85,codableSeries=180,validComments=3049)
    assert len(data['excludedSeries'])==16 and len({c['cluster_id'] for c in data['clusters']})==85
    assert len({n['ranking_id'] for n in data['nodes']})==400
    assert sum(bool(n['cluster_id']) for n in data['nodes'])==374
    assert data['commentMetrics'][0]['numerator']==27
    source=SOURCE/'可视化数据.json'
    (BASE/'result-preview/qa/数据构建核对.json').write_text(json.dumps(dict(source=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                 counts=data['counts'],case_groups=len(cases),external_dependencies=0,verified=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print('预览数据已构建：400节点、85簇、196系列；统计数值与定稿一致。')


if __name__=='__main__':
    main()
