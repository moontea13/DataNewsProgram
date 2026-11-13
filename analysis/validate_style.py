"""Independent artifact reconciliation, source preservation and semantic-boundary checks."""
import csv
import json
import re
import sys
import unittest
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from common import ROOT, RESULTS, WORKSPACE, DEFAULT_SOURCE, load, save, sha256
from style_features import OUTPUT, STYLE_RESULTS, title_features, seasonless

class BoundaryTests(unittest.TestCase):
    def row(self,title,season='SU'):
        return dict(series_id='test',title_raw=title,season_code=season,content_type='test',source_url='https://example.com')
    def test_plot_numbers_preserved(self):
        self.assertEqual(seasonless(self.row('三天后穿越古代，第九季','S09')),'三天后穿越古代')
        self.assertEqual(seasonless(self.row('第九季商店的秘密','SU')),'第九季商店的秘密')
        self.assertEqual(seasonless(self.row('镇国驸马爷3D版第十季','S10')),'镇国驸马爷3D版')
    def test_pending_number_is_not_season(self):
        self.assertEqual(seasonless(self.row('御狐3玄凤榜首','N03')),'御狐3玄凤榜首')
    def test_common_word_not_specific_template(self):
        self.assertEqual(title_features(self.row('皇后之梦'))['templates'],[])
        self.assertEqual(title_features(self.row('山海相逢，春日同行'))['templates'],[])
    def test_role_sequence_matters(self):
        hit=title_features(self.row('让你当保安，没让你镇压诡异'))
        self.assertIn('让你…，没让你…',{x['label'] for x in hit['templates']})
        self.assertNotIn('让你…，没让你…',{x['label'] for x in title_features(self.row('没让你当保安，让你去读书'))['templates']})

def validate():
    checks=[]
    def check(label,ok):
        checks.append({'check':label,'passed':bool(ok)})
        if not ok:raise AssertionError(label)
    def d(name):return load(OUTPUT/'data'/f'{name}.json')['data']
    def csvrows(name):
        with (OUTPUT/'tables'/name).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
    def pkey(a,b):return tuple(sorted([a,b]))
    series=d('series');ids={r['series_id'] for r in series};n=len(ids)
    check('169个唯一平台系列',n==169 and len(series)==169)
    check('原代表版本文件未变化',sha256(RESULTS/'representatives.json')==d('protocol')['representatives_sha256'])
    check('实验规则与提取前锁定指纹一致',sha256(ROOT/'style_protocol.json')==d('protocol')['protocol_sha256'])
    for r in load(RESULTS/'input_fingerprints.json'):
        check('原始采集数据指纹未变化：'+r['source'],sha256(DEFAULT_SOURCE/r['source'])==r['sha256'])
    identity=d('identity');blocked={pkey(r['series_a'],r['series_b']) for r in identity['rows']}
    allowed={p for p in combinations(sorted(ids),2) if p not in blocked}
    check('样本内两组身份疑点均排除',sum(a in ids and b in ids for a,b in blocked)==2)
    check('有效无序配对14194',len(allowed)==14194 and identity['valid_pairs']==14194)
    for s in series:
        check('封面与叠图存在：'+s['series_id'],all((OUTPUT/s[k]).is_file() for k in ['cover','ocr_overlay']))
    title=d('title_style');td={r['series_id']:r for r in title['rows']}
    check('标题样本与封面系列集合相同',set(td)==ids)
    for row in title['rows']:
        for field in ['templates','content_cues','rhetoric']:
            for x in row[field]:check('标题原文证据定位：'+row['series_id']+':'+field+':'+x['label'],row['title_style'][x['start']:x['end']]==x['evidence'])
    pairs=csvrows('title_style_pairs.csv');title_pair_csv=pairs
    check('标题配对明细完整',len(pairs)==len(allowed) and {pkey(r['series_a'],r['series_b']) for r in pairs}==allowed)
    for field,summary in [('template_repeat',title['template_coverage']),('template_and_content_repeat',title['specific_and_content'])]:
        selected=[r for r in pairs if r[field]=='True'];members={r[k] for r in selected for k in ['series_a','series_b']}
        check('标题覆盖可从明细重算：'+field,len(members)==summary['series_rate']['numerator'] and len(selected)==summary['pair_rate']['numerator'])
        check('标题配对内容与标志一致：'+field,all(bool(json.loads(r['shared_specific_templates'])) and (field=='template_repeat' or bool(json.loads(r['shared_content_cues']))) for r in selected))
    layout=d('cover_layout');valid={r['series_id'] for r in layout['features'] if r['valid_title_layout']}
    check('OCR有效与缺失对账',len(valid)==162 and layout['missing_series']==7 and len(layout['features'])==169)
    private_ocr={r['series_id']:r for r in load(STYLE_RESULTS/'cover_ocr.json')}
    for r in load(RESULTS/'representatives.json'):
        if r['modality']=='cover':
            check('OCR输入图片指纹未变化：'+r['series_id'],sha256(r['cover_path'])==private_ocr[r['series_id']]['image_sha256'])
    for r in layout['features']:
        check('OCR证据框坐标有界：'+r['series_id'],all(-.02<=v<=1.02 for b in r['boxes'] for point in b['polygon_normalized'] for v in point))
    lp=csvrows('cover_layout_pairs.csv');la={p for p in allowed if all(s in valid for s in p)}
    check('OCR有效配对完整且排除关联',len(lp)==len(la) and {pkey(r['series_a'],r['series_b']) for r in lp}==la)
    color_pairs=set()
    for flag,summary in [('close_layout',layout['close_layout']),('close_layout_and_region_color',layout['close_layout_and_color'])]:
        chosen=[r for r in lp if r[flag]=='True'];members={r[k] for r in chosen for k in ['series_a','series_b']}
        check('布局分子分母可重算：'+flag,len(members)==summary['series_rate']['numerator'] and summary['series_rate']['denominator']==len(valid) and len(chosen)==summary['pair_rate']['numerator'])
        if flag=='close_layout_and_region_color':color_pairs={pkey(r['series_a'],r['series_b']) for r in chosen}
    variants=d('cover_models')['variants'];scores=defaultdict(dict)
    with (OUTPUT/'tables/model_pairs.csv').open(encoding='utf-8-sig',newline='') as stream:
        for r in csv.DictReader(stream):
            key=pkey(r['series_a'],r['series_b']);score=float(r['score'])
            assert key in allowed and -1.00001<=score<=1.00001
            assert key not in scores[r['model_variant']]
            scores[r['model_variant']][key]=score
    check('全部模型配对均跨系列且未包含身份疑点',bool(scores))
    for name,model in variants.items():
        if model['status']!='已计算':continue
        values=scores[name];check('模型配对总数：'+name,len(values)==model['valid_pairs'])
        for curve in model['thresholds']:
            pairs={p for p,s in values.items() if s>=curve['threshold']};members={sid for p in pairs for sid in p}
            check('阈值系列覆盖及配对可重算：'+name+':'+str(curve['threshold']),len(members)==curve['series_rate']['numerator'] and len(pairs)==curve['pair_rate']['numerator'])
        last=[c for c in model['thresholds'] if c['threshold']==.85][0]
        if name in ['bge_title','bge_description']:check('身份疑点排除后的文字0.85结果为零：'+name,last['series_rate']['numerator']==0)
    for joint in d('cover_models')['joint_layout_image']:
        chosen={p for p,s in scores['dinov2_full'].items() if s>=joint['dinov2_full_min'] and p in color_pairs}
        check('画面、布局、颜色为同一配对交集：'+str(joint['dinov2_full_min']),len(chosen)==joint['pair_rate']['numerator'] and {s for p in chosen for s in p}==set(joint['series_ids']))
    originalpairs={pkey(r['series_a'],r['series_b']) for r in title_pair_csv if r['template_repeat']=='True'}
    intersection=originalpairs & color_pairs
    check('标题和封面同对交集准确',len(intersection)==d('intersections')['template_and_layout_color']['pair_rate']['numerator'])
    for r in d('metrics'):
        check('指标分子分母与比例：'+r['id'],r['denominator']>0 and r['percent']==round(100*r['numerator']/r['denominator'],4))
    for case in d('cases'):check('主案例不含排除配对：'+case['case_id'],pkey(case['series_a'],case['series_b']) in allowed)
    labels=d('visual_labels')
    if 'rows' in labels:
        for field in labels['rows'][0]['fields']:
            check('视觉模型未知与候选各类合计169：'+field,sum(x['numerator'] for x in labels['field_distributions'] if x['field']==field)==169)
        check('视觉三项非未知不足样本如实保留',labels['complete_signature_series']==sum(all(r['fields'][k]['label'] for k in ['render_style','people_count','shot']) for r in labels['rows']))
    def walk(value):
        if isinstance(value,str):
            assert not re.match(r'^[A-Za-z]:[\\/]|^file:/',value),'Absolute local path: '+value[:100]
        elif isinstance(value,dict):
            for x in value.values():walk(x)
        elif isinstance(value,list):
            for x in value:walk(x)
    for p in (OUTPUT/'data').glob('*.json'):
        walk(load(p));check('JSON无本机绝对路径：'+p.name,True)
    for p in (OUTPUT/'preview').glob('*'):
        check('预览依赖非空：'+p.name,p.stat().st_size>0)
    check('离线数据嵌入有效',(OUTPUT/'preview/data.js').read_text(encoding='utf-8').startswith('window.STYLE_DATA = '))
    check('模板缺数据时有明确提示','数据尚未加载' in (OUTPUT/'preview/index.html').read_text(encoding='utf-8'))
    check('预览不需要fetch加载JSON','fetch(' not in (OUTPUT/'preview/app.js').read_text(encoding='utf-8'))
    # Full independent behavioral tests run once, after data reconciliation.
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryTests))
    check('季号、数字、普通字词、语序边界测试',result.wasSuccessful())
    save(OUTPUT/'验收结果.json',{'passed':True,'checks_passed':len(checks),'boundary_tests':result.testsRun,'checks':checks,
          'limits':'自动验收验证完整性、证据位置和计算一致性，不证明视觉/语义准确率。'})
    files=[p for p in OUTPUT.rglob('*') if p.is_file() and p.name!='文件校验清单.json']
    save(OUTPUT/'文件校验清单.json',{'files':[{'path':p.relative_to(OUTPUT).as_posix(),'sha256':sha256(p),'bytes':p.stat().st_size} for p in sorted(files)]})
    print(json.dumps({'passed':True,'checks':len(checks),'boundary_tests':result.testsRun,'files_hashed':len(files)},ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');validate()
