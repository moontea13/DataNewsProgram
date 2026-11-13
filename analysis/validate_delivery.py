"""Independent reconciliation of source records, pairwise rates and offline assets."""
import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path
import json
import math
import re
from common import DEFAULT_SOURCE, DEFAULT_OUTPUT, RESULTS, THRESHOLDS, load, save, ratio, sha256

def validate(source=DEFAULT_SOURCE, output=DEFAULT_OUTPUT):
    source, output = Path(source), Path(output)
    checks, errors = [], []
    def check(name, condition, detail=None):
        checks.append({'name': name, 'passed': bool(condition), 'detail': detail})
        if not condition:
            errors.append(name)
    rankings = load(source / '红果400条交付/系列合并/上榜记录_系列季映射.json')
    works = load(source / '红果400条交付/系列合并/季作品表.json')
    work_to_series = {r['work_id']: r['series_id'] for r in works}
    series = load(output / 'data/series.json')
    registry = {r['series_id']: r for r in series}
    confirmed = {r['series_id'] for r in series if r['confirmed_group']}
    reps = load(RESULTS / 'representatives.json')
    check('400条来源主键唯一', len(rankings) == len({r['ranking_id'] for r in rankings}) == 400)
    check('每月100条红果记录', Counter(r['month'] for r in rankings) == {f'2026-{m:02d}':100 for m in range(7,11)})
    check('169个确认平台系列及27个待核单元', len(confirmed) == 169 and len(series)-len(confirmed) == 27)
    check('368部分季作品候选对账', len(works) == 368)
    check('代表版本按模态和系列唯一', len({(r['series_id'],r['modality']) for r in reps}) == len(reps))
    check('全部代表作品归属正确且有确认系列号', all(r['series_id'] in confirmed and work_to_series[r['work_id']] == r['series_id'] for r in reps))
    source_audit = load(RESULTS / 'source_audit.json')
    check('所选来源快照哈希全部匹配', all(r['matches'] for r in source_audit), {'checks':len(source_audit)})
    for item in load(RESULTS / 'input_fingerprints.json'):
        check('源数据未被改写：'+item['source'], sha256(source / item['source']) == item['sha256'])
    excluded = {tuple(sorted([r['series_a'],r['series_b']])) for r in load(RESULTS / 'excluded_pairs.json')}
    for mode in ['cover','title','description']:
        data = load(output / f'data/similarity_{mode}.json')['data']
        pairs = load(RESULTS / f'{mode}_pairs.json')
        ids = {r['series_id'] for r in reps if r['modality']==mode}
        expected_pairs = {tuple(sorted(p)) for p in combinations(sorted(ids),2)} - excluded
        actual_pairs = {tuple(sorted([r['series_a'],r['series_b']])) for r in pairs}
        check(mode+' 无重复、同系列及身份疑点配对', len(pairs)==len(actual_pairs) and actual_pairs==expected_pairs)
        check(mode+' 配对两端作品属于不同确认系列', all(work_to_series[r['work_a']] == r['series_a'] and work_to_series[r['work_b']] == r['series_b'] and r['series_a']!=r['series_b'] for r in pairs))
        check(mode+' 直方图总数对账', sum(r['count'] for r in data['histogram']) == len(pairs))
        top = data['top3']
        check(mode+' Top3无自身/重复邻居', all(r['series_id'] != r['neighbor_series_id'] for r in top) and
              len(top)==len({(r['series_id'],r['neighbor_series_id']) for r in top}) and all(v<=3 for v in Counter(r['series_id'] for r in top).values()))
        for threshold in THRESHOLDS:
            selected = [r for r in pairs if r['score']>=threshold]
            members = {sid for r in selected for sid in [r['series_a'],r['series_b']]}
            result = next(r for r in data['thresholds'] if r['threshold']==threshold)
            connected = {sid for r in pairs for sid in [r['series_a'],r['series_b']]}
            check(f'{mode} {threshold}系列比例独立重算', result['series_rate']==ratio(len(members),len(connected)))
            check(f'{mode} {threshold}配对比例独立重算', result['pair_rate']==ratio(len(selected),len(pairs)))
    sequel = load(output / 'data/sequels.json')['data']
    for row in sequel['monthly']:
        counts=Counter(r['series_id'] for r in rankings if r['month']==row['month'] and r['series_id'] in confirmed)
        check(row['month']+' 确认额外榜位独立重算', sum(v-1 for v in counts.values())==row['confirmed_extra_slots'])
        check(row['month']+' 榜位分解', row['known_ranking_rows']+row['pending_ranking_rows']==100)
    story = load(output / 'data/story.json')['data']
    coded = [s['story'] for s in series if 'story' in s]
    check('题材合计等于有效简介系列数', sum(r['count'] for r in story['genres'])==len(coded)==story['n'])
    from story_rules import validate as validate_coding
    check('编码证据原文定位', all(not validate_coding(r) for r in coded))
    covered = {r['series_id'] for r in coded if set(story['top3_reversals']) & {v['label'] for v in r['reversal_type']}}
    eligible = {r['series_id'] for r in coded if r['reversal_type']}
    check('Top3翻盘方式并集独立重算', story['top3_union']['numerator']==len(covered) and story['top3_union']['denominator']==len(eligible))
    inter = load(output / 'data/similarity_intersections.json')['data']
    hit_sets = {}
    for mode in ['cover','title','description']:
        p=load(RESULTS / f'{mode}_pairs.json')
        hit_sets[mode]={sid for r in p if r['score']>=.85 for sid in [r['series_a'],r['series_b']]}
    for row in inter['rows']:
        actual=set.intersection(*(hit_sets[m] for m in row['modalities']))
        check('跨模态系列并集：'+row['label'], set(row['series_ids'])==actual)
    producer = load(output / 'data/producers.json')['data']
    for row in producer['concentration']:
        ids={sid for brand in producer['ranking'][:row['top_k']] for sid in brand['series_ids']}
        check('Top品牌覆盖并集'+str(row['top_k']), row['numerator']==len(ids) and row['denominator']==len(confirmed))
    adaptations = load(output / 'data/adaptations.json')['data']
    node_ids={n['id'] for n in adaptations['nodes']}
    check('网络节点ID唯一', len(node_ids)==len(adaptations['nodes']))
    check('网络无悬空边', all(e['source'] in node_ids and e['target'] in node_ids for e in adaptations['edges']))
    check('改编主分类互斥合计169', sum(r['count'] for r in adaptations['confirmed_series_distribution'])==169)
    metrics=load(output / 'data/metrics.json')
    check('指标ID唯一', len(metrics)==len({r['id'] for r in metrics}))
    check('指标比例重算', all(r['value']==ratio(r['numerator'],r['denominator'])['percent'] for r in metrics if r['unit']=='%' and r['denominator'] is not None))
    aigc=load(output / 'data/aigc.json')['data']
    for row in aigc['rows']:
        if row['score_ai'] is not None:
            a,b=row['raw_logits'];expected=1/(1+math.exp(max(-700,min(700,a-b))))
            check('AIGC softmax及官方标签：'+row['sample_id'], abs(expected-row['score_ai'])<1e-6 and row['predicted_label']==('AI' if b>a else '人类') and row['token_count']<=512)
    check('AIGC有效与排除对账', aigc['valid_series_texts']+len(aigc['excluded_series'])==169)
    asset_errors, abs_paths, ratio_errors = [], [], []
    def scan(value, context=''):
        if isinstance(value,dict):
            if {'numerator','denominator','percent'} <= value.keys():
                expected=ratio(value['numerator'],value['denominator'])['percent']
                if value['percent']!=expected:ratio_errors.append(context)
            for k,v in value.items():scan(v,context+'.'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):scan(v,context+f'[{i}]')
        elif isinstance(value,str):
            if re.search(r'(?:^|\s)[A-Za-z]:[\\/]',value) or value.startswith('file://'):
                abs_paths.append(context)
            if value.startswith('assets/') and not (output/value).is_file():
                asset_errors.append(value)
    for p in (output/'data').glob('*.json'):
        scan(load(p),p.name)
    check('网页JSON无本机绝对路径', not abs_paths, abs_paths)
    check('全部封面引用有效', not asset_errors, asset_errors)
    check('所有嵌套比例分子分母一致', not ratio_errors, ratio_errors)
    manifest=load(output/'data/manifest.json')
    check('数据目录每个文件存在', all((output/r['file']).is_file() for r in manifest['files']))
    check('预览入口及脚本存在', all((output/'preview'/name).is_file() for name in ['index.html','app.js','style.css','data.js']))
    report={'passed':not errors,'check_count':len(checks),'failed_count':len(errors),'errors':errors,'checks':checks,
            'limits':'自动校验核对结构、计数和证据定位，不是历史身份或模型语义准确率认证。'}
    save(output/'验收结果.json',report)
    file_hashes=[]
    for p in sorted(output.rglob('*')):
        if p.is_file() and p.name!='文件校验清单.json':file_hashes.append({'path':p.relative_to(output).as_posix(),'bytes':p.stat().st_size,'sha256':sha256(p)})
    save(output/'文件校验清单.json',file_hashes)
    print(json.dumps({'passed':not errors,'checks':len(checks),'errors':errors},ensure_ascii=False),flush=True)
    if errors:raise SystemExit(1)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    validate(args.source,args.output)
